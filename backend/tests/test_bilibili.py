from __future__ import annotations

import hashlib
import json
import time

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models import AppSetting
from app.services.bilibili import (
    BILIBILI_API,
    BilibiliError,
    BilibiliService,
    mixin_key,
    qr_svg,
    registered_domain,
    sign_wbi,
    validate_stream_url,
)

IMG_KEY = "7cd084941338484aae1ad9425b84077c"
SUB_KEY = "4932caff0ff746eab6f01bf08b70ac45"
NAV_BODY = {
    "code": 0,
    "data": {
        "isLogin": False,
        "wbi_img": {
            "img_url": f"https://i0.hdslb.com/bfs/wbi/{IMG_KEY}.png",
            "sub_url": f"https://i0.hdslb.com/bfs/wbi/{SUB_KEY}.png",
        },
    },
}


@pytest.fixture(autouse=True)
def _clear_wbi_cache():
    BilibiliService._wbi_cache.clear()
    yield
    BilibiliService._wbi_cache.clear()


def _patch_httpx(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    real_client = httpx.Client

    def factory(*args, **kwargs):
        kwargs.pop("transport", None)
        return real_client(*args, transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(httpx, "Client", factory)


def test_mixin_key_reorders_the_published_reference_keys() -> None:
    mixed = mixin_key(IMG_KEY + SUB_KEY)
    assert len(mixed) == 32
    assert mixed.startswith("ea1db124af3c7062")


def test_sign_wbi_builds_a_stable_deterministic_signature() -> None:
    frozen = 1702204800
    real_time = time.time
    time.time = lambda: frozen
    try:
        first = sign_wbi({"foo": "one one", "bar": "two two", "zab": "three"}, IMG_KEY, SUB_KEY)
        second = sign_wbi({"zab": "three", "foo": "one one", "bar": "two two"}, IMG_KEY, SUB_KEY)
    finally:
        time.time = real_time
    query = "bar=two+two&foo=one+one&wts=1702204800&zab=three"
    expected = hashlib.md5((query + mixin_key(IMG_KEY + SUB_KEY)).encode()).hexdigest()
    assert first["wts"] == frozen
    # Parameter order in the caller must not change the signature.
    assert first["w_rid"] == second["w_rid"] == expected


def test_validate_stream_url_enforces_the_media_cdn_allowlist() -> None:
    assert validate_stream_url("https://upos-sz-mirror08c.bilivideo.com/a.mp4?x=1")
    assert validate_stream_url("https://upos-hz-mirrorakama.akamaized.net/upbos")
    assert validate_stream_url("https://xy.mcdn.bilivideo.cn:4483/upos")
    with pytest.raises(ValueError):
        validate_stream_url("https://evil.example.com/v.mp4")
    with pytest.raises(ValueError):
        validate_stream_url("http://upos-sz-mirror08c.bilivideo.com/a.mp4")
    assert registered_domain("XY.MCDN.Bilivideo.CN") == "bilivideo.cn"


def test_qr_svg_renders_an_embeddable_image() -> None:
    svg = qr_svg("https://passport.bilibili.com/h5-app/passport/login/scan?qrcode_key=demo")
    assert svg.lstrip().startswith("<?xml")


def test_login_poll_walks_waiting_scanned_confirmed(monkeypatch, db) -> None:
    seen_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(f"{request.url.host}{request.url.path}")
        if request.url.path.endswith("/qrcode/generate"):
            return httpx.Response(200, json={"code": 0, "data": {"url": "https://scan.demo/abc", "qrcode_key": "key12345"}})
        if request.url.path.endswith("/qrcode/poll"):
            count = sum(1 for item in seen_paths if item.endswith("/qrcode/poll"))
            if count == 1:
                return httpx.Response(200, json={"code": 0, "data": {"code": 86101, "message": "not scanned"}})
            if count == 2:
                return httpx.Response(200, json={"code": 0, "data": {"code": 86090, "message": "scanned"}})
            return httpx.Response(
                200,
                json={"code": 0, "data": {"code": 0, "url": "https://bilibili.com"}},
                headers=[
                    ("Set-Cookie", "SESSDATA=sess-value; Domain=.bilibili.com; Path=/"),
                    ("Set-Cookie", "bili_jct=jct-value; Domain=.bilibili.com; Path=/"),
                    ("Set-Cookie", "DedeUserID=42; Domain=.bilibili.com; Path=/"),
                ],
            )
        if request.url.path == "/x/web-interface/nav":
            body = json.loads(json.dumps(NAV_BODY))
            body["data"]["isLogin"] = True
            body["data"].update({"mid": 42, "uname": "Learner", "vipStatus": 0})
            return httpx.Response(200, json=body)
        raise AssertionError(f"unexpected upstream call {request.url}")

    _patch_httpx(monkeypatch, handler)
    service = BilibiliService(db)

    generated = service.login_qrcode()
    assert generated["qrcode_key"] == "key12345"
    assert generated["qr_svg"].lstrip().startswith("<?xml")

    assert service.login_poll(generated["qrcode_key"])["status"] == "waiting"
    assert service.login_poll(generated["qrcode_key"])["status"] == "scanned"

    confirmed = service.login_poll(generated["qrcode_key"])
    assert confirmed["status"] == "confirmed"
    assert confirmed["session"] == {"logged_in": True, "mid": 42, "uname": "Learner", "vip_status": 0}
    assert service.session_status()["logged_in"] is True

    cookie_item = db.scalar(select(AppSetting).where(AppSetting.key == "bilibili_cookies"))

    assert any("passport.bilibili.com/x/passport-login/" in path for path in seen_paths)
    assert "api.bilibili.com/x/web-interface/nav" in seen_paths


def test_session_endpoint_never_leaks_cookies_and_logout_clears_them(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/qrcode/generate"):
            return httpx.Response(200, json={"code": 0, "data": {"url": "https://scan.demo/abc", "qrcode_key": "key456789"}})
        if request.url.path.endswith("/qrcode/poll"):
            return httpx.Response(
                200,
                json={"code": 0, "data": {"code": 0}},
                headers=[
                    ("Set-Cookie", "SESSDATA=topsecret; Domain=.bilibili.com"),
                    ("Set-Cookie", "bili_jct=topjct; Domain=.bilibili.com"),
                    ("Set-Cookie", "DedeUserID=7; Domain=.bilibili.com"),
                ],
            )
        body = json.loads(json.dumps(NAV_BODY))
        body["data"]["isLogin"] = True
        body["data"].update({"mid": 7, "uname": "SecretUser", "vipStatus": 1})
        return httpx.Response(200, json=body)

    _patch_httpx(monkeypatch, handler)
    with TestClient(app) as client:
        assert client.get("/api/bilibili/session").json()["logged_in"] is False

        key = client.get("/api/bilibili/login/qrcode").json()["qrcode_key"]
        result = client.post("/api/bilibili/login/poll", json={"qrcode_key": key})
        assert result.status_code == 200 and result.json()["session"]["logged_in"] is True

        listing = client.get("/api/settings")
        cookie_row = next(item for item in listing.json()["settings"] if item["key"] == "bilibili_cookies")
        assert cookie_row["value"] == "configured" and cookie_row["is_secret"] is True
        assert "topsecret" not in listing.text

        assert client.delete("/api/bilibili/session").status_code == 204
        assert client.get("/api/bilibili/session").json()["logged_in"] is False


def test_playback_resolves_cid_signs_request_and_wraps_proxy(monkeypatch, db) -> None:
    requests_seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests_seen.append(request)
        if request.url.path == "/x/web-interface/view":
            return httpx.Response(200, json={
                "code": 0,
                "data": {
                    "bvid": "BV1XX",
                    "title": "CS336 Lecture",
                    "pages": [{"page": 1, "cid": 99, "part": "Part 1", "duration": 600}],
                },
            })
        if request.url.path == "/x/player/wbi/playurl":
            return httpx.Response(200, json={
                "code": 0,
                "data": {
                    "quality": 32,
                    "accept_quality": [80, 64, 32, 16],
                    "accept_description": ["1080P 高清", "720P 高清", "480P 清晰", "360P 流畅"],
                    "timelength": 600000,
                    "durl": [{"url": "https://upos-sz-mirror08c.bilivideo.com/media.mp4?og=1", "backup_url": [], "size": 1, "length": 600000}],
                },
            })
        if request.url.path == "/x/web-interface/nav":
            return httpx.Response(200, json=NAV_BODY)
        raise AssertionError(f"unexpected upstream call {request.url}")

    _patch_httpx(monkeypatch, handler)
    payload = BilibiliService(db).playback("BV1XX")

    assert payload["cid"] == 99 and payload["title"] == "CS336 Lecture"
    assert payload["duration_seconds"] == 600
    assert payload["logged_in"] is False
    assert payload["qualities"][0] == {"id": 80, "label": "1080P 高清"}
    assert payload["stream_url"].startswith("/api/bilibili/stream?url=https%3A%2F%2Fupos-sz-mirror08c.bilivideo.com")

    playurl_call = next(r for r in requests_seen if r.url.path == "/x/player/wbi/playurl")
    assert str(playurl_call.url.params["cid"]) == "99"
    assert str(playurl_call.url.params["platform"]) == "html5"
    assert "w_rid" in playurl_call.url.params and "wts" in playurl_call.url.params


def test_stream_endpoint_blocks_disallowed_hosts() -> None:
    with TestClient(app) as client:
        blocked = client.get("/api/bilibili/stream", params={"url": "https://evil.example.com/v.mp4"})
        assert blocked.status_code == 403


def test_stream_endpoint_relays_range_requests_from_allowed_cdns(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "upos-sz-mirror08c.bilivideo.com"
        assert request.headers["range"] == "bytes=100-"
        assert request.headers["referer"] == "https://www.bilibili.com/"
        return httpx.Response(
            206,
            headers={
                "Content-Type": "video/mp4",
                "Content-Range": "bytes 100-110/1000",
                "Accept-Ranges": "bytes",
            },
            # MockTransport eagerly consumes `content=` payloads; a lazy
            # ByteStream preserves the streaming contract under test.
            stream=httpx.ByteStream(b"media-bytes"),
        )

    _patch_httpx(monkeypatch, handler)
    with TestClient(app) as client:
        response = client.get(
            "/api/bilibili/stream",
            params={"url": "https://upos-sz-mirror08c.bilivideo.com/media.mp4"},
            headers={"Range": "bytes=100-"},
        )
    assert response.status_code == 206
    assert response.content == b"media-bytes"
    assert response.headers["content-range"] == "bytes 100-110/1000"
    assert response.headers["cache-control"] == "no-store"


def test_import_course_splits_multi_part_videos(monkeypatch, db) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/x/web-interface/view":
            return httpx.Response(200, json={
                "code": 0,
                "data": {
                    "bvid": "BV1XX411c7mD",
                    "title": "CS336 Series",
                    "pages": [
                        {"page": 1, "cid": 11, "part": "Tokenization", "duration": 600},
                        {"page": 2, "cid": 22, "part": "Architecture", "duration": 700},
                        {"page": 3, "cid": 33, "part": "Optimizers", "duration": 800},
                    ],
                },
            })
        raise AssertionError(f"unexpected upstream call {request.url}")
    _patch_httpx(monkeypatch, handler)
    course = BilibiliService(db).import_course("https://www.bilibili.com/video/BV1XX411c7mD/")

    assert course.name == "CS336 Series"
    assert course.source_type == "bilibili_manual"
    lectures = sorted(course.lectures, key=lambda item: item.order_index)
    assert [item.title for item in lectures] == ["Tokenization", "Architecture", "Optimizers"]
    assert [item.video.external_id for item in lectures] == ["BV1XX411c7mD", "BV1XX411c7mD?p=2", "BV1XX411c7mD?p=3"]
    assert all(item.video.provider == "bilibili" for item in lectures)
    assert "page=2" in lectures[1].video.embed_url
    assert lectures[0].duration_seconds == 600.0
    source = course.sources[0]
    assert source.source_type == "bilibili_learner_selected" and source.detected_as_official is False


def test_import_course_rejects_non_bilibili_links(db) -> None:
    with pytest.raises(BilibiliError):
        BilibiliService(db).import_course("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
