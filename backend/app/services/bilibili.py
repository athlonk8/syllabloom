"""First-party Bilibili web-API client for logged-in, in-app playback.

The learner signs in with an official Bilibili QR code inside Syllabloom.
Cookies stay in the local database and are only ever attached to requests the
learner's own machine makes to api.bilibili.com / passport.bilibili.com.
Media bytes are streamed through this process in memory; nothing is written
to disk and no entitlement beyond the learner's own account is unlocked.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import time
from dataclasses import dataclass
from typing import Any, Iterator
from urllib.parse import quote, urlencode, urljoin, urlparse

import httpx
from sqlalchemy import select
from ..models import AppSetting, Course, CourseSource, Lecture, Module, Video
from .utils import bilibili_embed_url, bilibili_video_url, extract_bilibili_video_id

BILIBILI_API = "https://api.bilibili.com"
PASSPORT_API = "https://passport.bilibili.com"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
REFERER = "https://www.bilibili.com/"

COOKIES_SETTING_KEY = "bilibili_cookies"
PROFILE_SETTING_KEY = "bilibili_profile"

# Registered domains that legitimately serve Bilibili media segments.  The
# proxy refuses anything else so it can never act as an open relay.
STREAM_ALLOWED_DOMAINS = frozenset(
    {"bilivideo.com", "bilivideo.cn", "akamaized.net", "szbdyd.com"}
)

# WBI parameter obfuscation table published in Bilibili's web client.
MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
    33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
    61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
    36, 20, 34, 44, 52,
]

# ---------------------------------------------------------------------------
# Uploader title hygiene.  Bilibili reposts stack separator spam ("|大模型|
# 深度学习|…"), bracketed meta ("(中英字幕完结)", "【搬运】") and clickbait
# tails ("草履虫看了都能学会!") onto the real series name.  Strip them so a
# learner's library does not fill with junk.

SEPARATOR_SPAM = re.compile(r"\s*[|｜丨]\s*")
BRACKET_META = re.compile(
    r"[（(][^（）()]{0,30}?(?:完结|字幕|搬运|转载|全集|持续更新|合集|修复|熟肉)[^（）()]{0,30}?[）)]"
    r"|【[^】]{0,24}】"
)
CLICKBAIT = re.compile(
    r"(?:草履虫|小白|零基础|保姆级|手把手|都能学会|包会|一学就会|学不会|看完就会|看这[一集]个?就?够)"
)
EPISODE_PREFIX = re.compile(r"^\d{1,3}\s*[.、:：\-—]\s*")
TRIM_CHARS = " 　\t\r\n，。,;；!！?？：:·…-—_~"


def clean_series_title(raw: str) -> str:
    """Return the meaningful head of an uploader-styled series title."""
    text = (raw or "").strip()
    if not text:
        return text
    text = SEPARATOR_SPAM.split(text, maxsplit=1)[0]
    while True:
        stripped = BRACKET_META.sub("", text).strip(TRIM_CHARS)
        if stripped == text:
            break
        text = stripped
    match = CLICKBAIT.search(text)
    if match and match.start() >= 8:
        text = text[: match.start()]
    text = text.strip(TRIM_CHARS)
    return text or raw.strip()[:120]


def clean_part_title(raw: str, index: int) -> str:
    """Return the per-episode label from an uploader-styled part title."""
    text = clean_series_title(raw)
    segments = [segment.strip(TRIM_CHARS) for segment in re.split(r"\s+[-—–]\s+", text)]
    candidate = EPISODE_PREFIX.sub("", segments[-1]).strip(TRIM_CHARS) if segments else ""
    return candidate or f"P{index}"

QR_POLL_STATUS = {
    0: "confirmed",
    86038: "expired",
    86090: "scanned",
    86101: "waiting",
}


class BilibiliError(RuntimeError):
    """Any failure talking to Bilibili's official web endpoints."""


def registered_domain(host: str) -> str:
    parts = host.lower().rsplit(".", 2)
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def validate_stream_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError("Only https media URLs are accepted.")
    host = parsed.hostname or ""
    if registered_domain(host) not in STREAM_ALLOWED_DOMAINS:
        raise ValueError(f"Host {host!r} is not a Bilibili media CDN.")
    return url


def mixin_key(original: str) -> str:
    return "".join(original[index] for index in MIXIN_KEY_ENC_TAB)[:32]


def sign_wbi(params: dict[str, Any], img_key: str, sub_key: str) -> dict[str, Any]:
    signed = {key: value for key, value in params.items() if value is not None}
    signed["wts"] = int(time.time())
    query = urlencode(
        {
            key: "".join(char for char in str(value) if char not in "!'()*")
            for key, value in sorted(signed.items())
        }
    )
    digest = hashlib.md5((query + mixin_key(img_key + sub_key)).encode()).hexdigest()
    signed["w_rid"] = digest
    return signed


def qr_svg(payload: str) -> str:
    import qrcode.image.svg  # imported lazily; only needed for the login flow

    image = qrcode.make(payload, image_factory=qrcode.image.svg.SvgPathImage, box_size=12, border=2)
    buffer = io.BytesIO()
    image.save(buffer)
    return buffer.getvalue().decode()


@dataclass(frozen=True)
class ProxyResponse:
    status_code: int
    headers: dict[str, str]
    iterator: Iterator[bytes]


class BilibiliService:
    """Stateless-per-call client; cookie state lives in the local database."""

    WBI_TTL_SECONDS = 3_600

    _wbi_cache: dict[str, tuple[str, str, float]] = {}

    def __init__(self, db: Session) -> None:
        self._db = db

    # ------------------------------------------------------------------ store

    def _read_setting(self, key: str) -> str | None:
        item = self._db.scalar(select(AppSetting).where(AppSetting.key == key))
        return item.value if item else None

    def _write_setting(self, key: str, value: str, *, secret: bool) -> None:
        item = self._db.scalar(select(AppSetting).where(AppSetting.key == key))
        if item:
            item.value = value
            item.is_secret = secret
        else:
            self._db.add(AppSetting(key=key, value=value, is_secret=secret))
        self._db.commit()

    def _cookies(self) -> dict[str, str]:
        raw = self._read_setting(COOKIES_SETTING_KEY)
        if not raw:
            return {}
        try:
            cookies = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return cookies if isinstance(cookies, dict) and cookies.get("SESSDATA") else {}

    def session_status(self) -> dict[str, Any]:
        raw = self._read_setting(PROFILE_SETTING_KEY)
        profile: dict[str, Any] = {}
        if raw:
            try:
                loaded = json.loads(raw)
                if isinstance(loaded, dict):
                    profile = loaded
            except json.JSONDecodeError:
                profile = {}
        logged_in = bool(self._cookies())
        return {
            "logged_in": logged_in,
            "mid": profile.get("mid"),
            "uname": profile.get("uname"),
            "vip_status": profile.get("vip_status"),
        }

    def clear_session(self) -> None:
        for key in (COOKIES_SETTING_KEY, PROFILE_SETTING_KEY):
            item = self._db.scalar(select(AppSetting).where(AppSetting.key == key))
            if item:
                self._db.delete(item)
        self._db.commit()

    # ------------------------------------------------------------------ login

    def login_qrcode(self) -> dict[str, Any]:
        with httpx.Client(base_url=PASSPORT_API, headers=self._headers(), timeout=15) as client:
            response = client.get("/x/passport-login/web/qrcode/generate")
        payload = self._payload(response)
        data = payload["data"]
        return {"qrcode_key": data["qrcode_key"], "qr_svg": qr_svg(data["url"])}

    def login_poll(self, qrcode_key: str) -> dict[str, Any]:
        with httpx.Client(base_url=PASSPORT_API, headers=self._headers(), timeout=15) as client:
            response = client.get(
                "/x/passport-login/web/qrcode/poll", params={"qrcode_key": qrcode_key}
            )
        body = self._payload(response, check_code=False)
        # The outer envelope is always code 0; the scan state lives in data.code.
        status = QR_POLL_STATUS.get(int((body.get("data") or {}).get("code", -1)), "unknown")
        result: dict[str, Any] = {"status": status}
        if status == "confirmed":
            cookies = {name: value for name, value in response.cookies.items()}
            missing = [name for name in ("SESSDATA", "bili_jct", "DedeUserID") if name not in cookies]
            if missing:
                raise BilibiliError(f"Bilibili login response lacked cookies: {', '.join(missing)}")
            self._write_setting(
                COOKIES_SETTING_KEY, json.dumps(cookies, ensure_ascii=False), secret=True
            )
            result["session"] = self._fetch_profile(cookies)
        return result

    def _fetch_profile(self, cookies: dict[str, str]) -> dict[str, Any]:
        with httpx.Client(headers=self._headers(), cookies=cookies, timeout=15) as client:
            response = client.get(f"{BILIBILI_API}/x/web-interface/nav")
        body = self._payload(response, check_code=False)
        data = body.get("data") or {}
        profile = {
            "mid": data.get("mid"),
            "uname": data.get("uname"),
            "vip_status": data.get("vipStatus"),
        }
        self._write_setting(
            PROFILE_SETTING_KEY, json.dumps(profile, ensure_ascii=False), secret=False
        )
        return self.session_status()

    # --------------------------------------------------------------- playback

    def video_info(self, bvid: str) -> dict[str, Any]:
        with httpx.Client(headers=self._headers(), timeout=15) as client:
            response = client.get(f"{BILIBILI_API}/x/web-interface/view", params={"bvid": bvid})
        body = self._payload(response)
        data = body["data"]
        return {
            "bvid": data["bvid"],
            "title": data.get("title") or "",
            "pages": [
                {"page": page.get("page"), "cid": page["cid"], "part": page.get("part"), "duration_seconds": page.get("duration")}
                for page in data.get("pages") or []
            ],
        }

    def _resolve_page(self, info: dict[str, Any], page: int) -> dict[str, Any]:
        pages = info["pages"]
        if not pages:
            raise BilibiliError("This video exposes no playable pages.")
        index = min(max(page, 1), len(pages)) - 1
        return pages[index]

    def _wbi_keys(self) -> tuple[str, str]:
        cached = self._wbi_cache.get("keys")
        if cached and time.monotonic() - cached[2] < self.WBI_TTL_SECONDS:
            return cached[0], cached[1]
        with httpx.Client(headers=self._headers(), timeout=15) as client:
            response = client.get(f"{BILIBILI_API}/x/web-interface/nav")
        body = self._payload(response, check_code=False)
        wbi_img = (body.get("data") or {}).get("wbi_img") or {}
        img_url = wbi_img.get("img_url")
        sub_url = wbi_img.get("sub_url")
        if not img_url or not sub_url:
            raise BilibiliError("Unable to read Bilibili WBI keys.")
        keys = (
            urlparse(img_url).path.rsplit("/", 1)[-1].split(".")[0],
            urlparse(sub_url).path.rsplit("/", 1)[-1].split(".")[0],
        )
        self._wbi_cache["keys"] = (*keys, time.monotonic())
        return keys

    def playback(self, bvid: str, page: int = 1, qn: int | None = None) -> dict[str, Any]:
        info = self.video_info(bvid)
        selected = self._resolve_page(info, page)
        img_key, sub_key = self._wbi_keys()
        cookies = self._cookies()
        params = sign_wbi(
            {
                "bvid": bvid,
                "cid": selected["cid"],
                "qn": qn or 127,
                "fnval": 1,
                "fnver": 0,
                "platform": "html5",
                "high_quality": 1,
            },
            img_key,
            sub_key,
        )
        with httpx.Client(headers=self._headers(), cookies=cookies, timeout=20) as client:
            response = client.get(f"{BILIBILI_API}/x/player/wbi/playurl", params=params)
        body = self._payload(response)
        data = body.get("data") or {}
        durl = data.get("durl") or []
        if not durl:
            raise BilibiliError("Bilibili did not return a playable MP4 stream for this video.")
        accept_ids = data.get("accept_quality") or []
        accept_labels = data.get("accept_description") or []
        qualities = [
            {"id": int(qid), "label": label}
            for qid, label in zip(accept_ids, accept_labels)
            if str(qid).lstrip("-").isdigit()
        ]
        chosen = durl[0].get("url")
        if not chosen:
            raise BilibiliError("Bilibili returned an empty stream URL.")
        return {
            "bvid": bvid,
            "cid": selected["cid"],
            "page": selected["page"] or page,
            "pages_total": len(info["pages"]),
            "title": info["title"],
            "part": selected.get("part") or "",
            "duration_seconds": selected.get("duration_seconds"),
            "timelength_ms": data.get("timelength"),
            "quality_id": int(data.get("quality") or 0),
            "qualities": qualities,
            "logged_in": bool(cookies),
            "stream_url": "/api/bilibili/stream?url=" + quote(chosen, safe=""),
        }

    def import_course(self, url: str, name: str | None = None) -> Course:
        """Parse a learner-provided Bilibili link into a local course.

        Multi-part (multi-P) videos become one lecture per part so a whole
        series can be imported from a single link.  Metadata comes from the
        public view API only; nothing here implies the video is official
        course material.
        """
        bvid = extract_bilibili_video_id(url)
        if not bvid:
            raise BilibiliError("This is not a direct Bilibili BV video URL.")
        info = self.video_info(bvid)
        pages = info["pages"] or [{"page": 1, "cid": None, "part": info["title"], "duration_seconds": None}]
        series_title = clean_series_title(info["title"]) or bvid
        course = Course(
            name=(name or series_title).strip()[:300] or bvid,
            official_course_url=bilibili_video_url(bvid),
            source_type="bilibili_manual",
            import_status="ready",
        )
        self._db.add(course)
        self._db.flush()
        module = Module(course_id=course.id, title="Course videos", order_index=1)
        self._db.add(module)
        self._db.add(
            CourseSource(
                course_id=course.id,
                source_url=bilibili_video_url(bvid),
                source_type="bilibili_learner_selected",
                title=course.name,
                detected_as_official=False,
                explanation=(
                    "Parsed from a learner-provided Bilibili link; metadata was read "
                    "from Bilibili's public view API and remains third-party content."
                ),
            )
        )
        for index, page in enumerate(pages, start=1):
            page_number = int(page.get("page") or index)
            suffix = "" if page_number <= 1 else f"?p={page_number}"
            raw_part = str(page.get("part") or "")
            part_title = clean_part_title(raw_part, page_number) if len(pages) > 1 else series_title
            lecture = Lecture(
                course_id=course.id,
                module_id=module.id,
                title=part_title[:500],
                order_index=index,
                source_url=bilibili_video_url(bvid) + suffix,
                duration_seconds=float(page["duration_seconds"]) if page.get("duration_seconds") else None,
            )
            self._db.add(lecture)
            self._db.flush()
            self._db.add(
                Video(
                    lecture_id=lecture.id,
                    provider="bilibili",
                    external_id=bvid + suffix,
                    embed_url=bilibili_embed_url(bvid) + (f"&page={page_number}" if suffix else ""),
                    is_embeddable=True,
                )
            )
        self._db.flush()
        return course

    # ------------------------------------------------------------------ shared

    @staticmethod
    def _headers() -> dict[str, str]:
        return {
            "User-Agent": USER_AGENT,
            "Referer": REFERER,
            "Origin": "https://www.bilibili.com",
        }

    @staticmethod
    def _payload(response: httpx.Response, *, check_code: bool = True) -> dict[str, Any]:
        try:
            body = response.json()
        except ValueError as exc:
            raise BilibiliError(f"Bilibili returned non-JSON (HTTP {response.status_code}).") from exc
        if not isinstance(body, dict):
            raise BilibiliError("Unexpected Bilibili response shape.")
        if check_code and body.get("code") not in (0, None):
            message = body.get("message") or body.get("msg") or "unknown reason"
            raise BilibiliError(f"Bilibili API error {body.get('code')}: {message}")
        return body


# ---------------------------------------------------------------------- proxy


def _send_following_redirects(client: httpx.Client, request: httpx.Request, hops: int = 3) -> httpx.Response:
    """Follow CDN redirects while re-validating every hop against the allowlist."""
    response = client.send(request, stream=True)
    followed = 0
    while response.is_redirect:
        followed += 1
        if followed > hops:
            response.close()
            raise BilibiliError("Too many redirects from the media CDN.")
        location = urljoin(str(response.url), response.headers.get("location", ""))
        response.close()
        try:
            validate_stream_url(location)
        except ValueError as exc:
            raise BilibiliError(f"CDN redirected outside the allowed hosts: {exc}") from exc
        response = client.send(client.build_request("GET", location), stream=True)
    return response


def open_media_stream(url: str, range_header: str | None) -> ProxyResponse:
    """Open a validated Bilibili CDN URL for in-memory relay (never stored)."""
    target = validate_stream_url(url)
    client = httpx.Client(
        headers={"User-Agent": USER_AGENT, "Referer": REFERER},
        follow_redirects=False,
        timeout=httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0),
    )
    try:
        request = client.build_request("GET", target)
        if range_header:
            request.headers["Range"] = range_header
        upstream = _send_following_redirects(client, request)
    except BaseException:
        client.close()
        raise
    headers = {
        name: value
        for name, value in upstream.headers.items()
        if name.lower() in {"content-type", "content-length", "content-range", "accept-ranges"}
    }

    def chunks() -> Iterator[bytes]:
        try:
            yield from upstream.iter_raw(chunk_size=256 * 1024)
        finally:
            upstream.close()
            client.close()

    return ProxyResponse(status_code=upstream.status_code, headers=headers, iterator=chunks())
