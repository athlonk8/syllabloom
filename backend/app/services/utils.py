from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse


def slugify(value: str, fallback: str = "untitled") -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9._-]+", "-", value)
    value = re.sub(r"-+", "-", value).strip(".-")
    return value[:80] or fallback


def safe_filename(value: str, fallback: str = "resource") -> str:
    value = value.replace("\\", "_").replace("/", "_")
    value = re.sub(r'[<>:"|?*\x00-\x1f]', "_", value).strip(" .")
    return value[:150] or fallback


def extract_youtube_video_id(url: str) -> str | None:
    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    if host == "youtu.be":
        return parsed.path.strip("/").split("/")[0] or None
    if host in {"youtube.com", "m.youtube.com", "music.youtube.com"}:
        if parsed.path == "/watch":
            return parse_qs(parsed.query).get("v", [None])[0]
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 2 and parts[0] in {"embed", "shorts", "live"}:
            return parts[1]
    return None


def extract_youtube_playlist_id(url: str) -> str | None:
    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    if host not in {"youtube.com", "m.youtube.com", "music.youtube.com"}:
        return None
    return parse_qs(parsed.query).get("list", [None])[0]


def extract_bilibili_video_id(url: str) -> str | None:
    """Return a BV identifier from a normal Bilibili video or player URL.

    This deliberately accepts only direct Bilibili URLs.  Short links would
    need a network redirect, which keeps source selection less predictable and
    makes it harder to preserve the learner's exact provenance.
    """
    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    if host not in {"bilibili.com", "m.bilibili.com", "player.bilibili.com"}:
        return None
    match = re.search(r"(?:^|/)video/(BV[0-9A-Za-z]{10})(?:/|$)|(?:^|[?&])bvid=(BV[0-9A-Za-z]{10})(?:&|$)", url)
    if not match:
        return None
    return match.group(1) or match.group(2)


def bilibili_video_url(bvid: str) -> str:
    return f"https://www.bilibili.com/video/{bvid}/"


def bilibili_embed_url(bvid: str) -> str:
    return (
        "https://player.bilibili.com/player.html"
        f"?bvid={bvid}&page=1&high_quality=1&danmaku=0"
    )


def is_stanford_url(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return parsed.scheme in {"http", "https"} and (host == "stanford.edu" or host.endswith(".stanford.edu"))


def path_is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False
