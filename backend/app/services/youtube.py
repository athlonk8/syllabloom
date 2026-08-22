from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import environment_value, get_settings
from ..models import Course, CourseSource, Lecture, Module, Video
from .utils import extract_youtube_playlist_id, extract_youtube_video_id

YOUTUBE_API = "https://www.googleapis.com/youtube/v3"


class MissingYouTubeApiKeyError(RuntimeError):
    pass


class YouTubeImportError(RuntimeError):
    pass


def parse_iso_duration(value: str | None) -> float | None:
    if not value:
        return None
    match = re.fullmatch(
        r"P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?",
        value,
    )
    if not match:
        return None
    parts = {name: int(amount or 0) for name, amount in match.groupdict().items()}
    return float(parts["days"] * 86400 + parts["hours"] * 3600 + parts["minutes"] * 60 + parts["seconds"])


def _youtube_embed_url(video_id: str) -> str:
    return f"https://www.youtube.com/embed/{video_id}?enablejsapi=1&origin=http://localhost:5173"


@dataclass(frozen=True)
class ManualVideo:
    url: str
    title: str
    duration_seconds: float | None = None
    description: str | None = None
    thumbnail_url: str | None = None


class YouTubeImporter:
    """YouTube importer backed only by the official Data API.

    Deliberately does not parse YouTube HTML. When no local API key exists, the
    caller must use the explicit manual-course endpoint.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()

    def _api_key(self) -> str | None:
        from ..models import AppSetting

        setting = self.db.scalar(select(AppSetting).where(AppSetting.key == "YOUTUBE_API_KEY"))
        if setting is not None:
            return setting.value.strip() or None
        return environment_value("YOUTUBE_API_KEY") or None

    def import_url(self, url: str) -> Course:
        playlist_id = extract_youtube_playlist_id(url)
        video_id = extract_youtube_video_id(url)
        api_key = self._api_key()
        if not api_key:
            raise MissingYouTubeApiKeyError(
                "YouTube Data API key missing. Add YOUTUBE_API_KEY in Settings, or use Manual Course Import. "
                "The app will not scrape YouTube HTML as a fallback."
            )
        if playlist_id:
            return self._import_playlist(url, playlist_id, api_key)
        if video_id:
            return self._import_single_video(url, video_id, api_key)
        raise YouTubeImportError("Paste a valid YouTube playlist or video URL.")

    def import_manual(
        self, name: str, videos: list[ManualVideo], source_url: str | None = None, channel_name: str | None = None
    ) -> Course:
        if not videos:
            raise YouTubeImportError("A manual course requires at least one video.")
        course = Course(
            name=name,
            official_course_url=source_url,
            source_type="youtube_manual",
            channel_name=channel_name,
            import_status="ready",
        )
        self.db.add(course)
        self.db.flush()
        module = Module(course_id=course.id, title="Course videos", order_index=1)
        self.db.add(module)
        self.db.add(
            CourseSource(
                course_id=course.id,
                source_url=source_url or videos[0].url,
                source_type="youtube_manual",
                title=name,
                detected_as_official=False,
                explanation="Manually entered by the learner; source authenticity has not been inferred.",
            )
        )
        for index, item in enumerate(videos, start=1):
            video_id = extract_youtube_video_id(item.url)
            if not video_id:
                raise YouTubeImportError(f"Manual video {index} is not a valid YouTube URL.")
            lecture = Lecture(
                course_id=course.id,
                module_id=module.id,
                title=item.title,
                description=item.description,
                order_index=index,
                source_url=item.url,
                duration_seconds=item.duration_seconds,
            )
            self.db.add(lecture)
            self.db.flush()
            self.db.add(
                Video(
                    lecture_id=lecture.id,
                    external_id=video_id,
                    embed_url=_youtube_embed_url(video_id),
                    thumbnail_url=item.thumbnail_url,
                )
            )
        self.db.flush()
        return course

    def _get(self, path: str, api_key: str, **params: Any) -> dict[str, Any]:
        response = httpx.get(
            f"{YOUTUBE_API}/{path}", params={"key": api_key, **params}, timeout=20.0, follow_redirects=True
        )
        if response.status_code >= 400:
            message = response.json().get("error", {}).get("message", response.text[:300])
            raise YouTubeImportError(f"YouTube Data API error ({response.status_code}): {message}")
        return response.json()

    def _import_playlist(self, source_url: str, playlist_id: str, api_key: str) -> Course:
        playlist_payload = self._get("playlists", api_key, part="snippet", id=playlist_id, maxResults=1)
        if not playlist_payload.get("items"):
            raise YouTubeImportError("The playlist was not found or is not publicly available through the Data API.")
        playlist = playlist_payload["items"][0]
        snippet = playlist["snippet"]
        course = Course(
            name=snippet.get("title") or "Untitled YouTube playlist",
            official_course_url=source_url,
            source_type="youtube_playlist",
            description=snippet.get("description"),
            channel_name=snippet.get("channelTitle"),
            import_status="ready",
        )
        self.db.add(course)
        self.db.flush()
        module = Module(course_id=course.id, title="Playlist", order_index=1)
        self.db.add(module)
        self.db.add(
            CourseSource(
                course_id=course.id,
                source_url=source_url,
                source_type="youtube_data_api",
                title=course.name,
                detected_as_official=False,
                explanation="Metadata obtained through the official YouTube Data API.",
            )
        )

        playlist_items: list[dict[str, Any]] = []
        token: str | None = None
        while True:
            payload = self._get(
                "playlistItems", api_key, part="snippet,contentDetails,status", playlistId=playlist_id, maxResults=50,
                **({"pageToken": token} if token else {}),
            )
            playlist_items.extend(payload.get("items", []))
            token = payload.get("nextPageToken")
            if not token:
                break
        ids = [item.get("contentDetails", {}).get("videoId") for item in playlist_items]
        video_details: dict[str, dict[str, Any]] = {}
        for start in range(0, len(ids), 50):
            chunk = [item for item in ids[start : start + 50] if item]
            if not chunk:
                continue
            payload = self._get("videos", api_key, part="snippet,contentDetails,status", id=",".join(chunk), maxResults=50)
            video_details.update({item["id"]: item for item in payload.get("items", [])})
        for index, playlist_item in enumerate(playlist_items, start=1):
            video_id = playlist_item.get("contentDetails", {}).get("videoId")
            detail = video_details.get(video_id or "")
            if not video_id or not detail:
                continue  # Deleted/private playlist items are intentionally skipped and counted below.
            self._add_video(course, module, detail, index, playlist_item.get("snippet", {}).get("publishedAt"))
        self.db.flush()
        return course

    def _import_single_video(self, source_url: str, video_id: str, api_key: str) -> Course:
        payload = self._get("videos", api_key, part="snippet,contentDetails,status", id=video_id, maxResults=1)
        if not payload.get("items"):
            raise YouTubeImportError("The video was not found or is not publicly available through the Data API.")
        detail = payload["items"][0]
        snippet = detail["snippet"]
        course = Course(
            name=snippet.get("title") or "YouTube video",
            official_course_url=source_url,
            source_type="youtube_video",
            description=snippet.get("description"),
            channel_name=snippet.get("channelTitle"),
        )
        self.db.add(course)
        self.db.flush()
        module = Module(course_id=course.id, title="Video", order_index=1)
        self.db.add(module)
        self.db.add(
            CourseSource(
                course_id=course.id,
                source_url=source_url,
                source_type="youtube_data_api",
                title=course.name,
                detected_as_official=False,
                explanation="Metadata obtained through the official YouTube Data API.",
            )
        )
        self._add_video(course, module, detail, 1, snippet.get("publishedAt"))
        self.db.flush()
        return course

    def _add_video(
        self, course: Course, module: Module, detail: dict[str, Any], order_index: int, published_at: str | None
    ) -> None:
        snippet = detail.get("snippet", {})
        thumbnails = snippet.get("thumbnails", {})
        thumbnail = (thumbnails.get("maxres") or thumbnails.get("high") or thumbnails.get("default") or {}).get("url")
        lecture = Lecture(
            course_id=course.id,
            module_id=module.id,
            title=snippet.get("title") or f"Video {order_index}",
            description=snippet.get("description"),
            order_index=order_index,
            source_url=f"https://www.youtube.com/watch?v={detail['id']}",
            duration_seconds=parse_iso_duration(detail.get("contentDetails", {}).get("duration")),
            published_at=published_at,
        )
        self.db.add(lecture)
        self.db.flush()
        self.db.add(
            Video(
                lecture_id=lecture.id,
                external_id=detail["id"],
                embed_url=_youtube_embed_url(detail["id"]),
                thumbnail_url=thumbnail,
                is_embeddable=detail.get("status", {}).get("embeddable", True),
            )
        )
