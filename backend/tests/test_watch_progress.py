from __future__ import annotations

from app.models import Course, Lecture, Module, Video
from app.services.watch_progress import coverage_for_segments, course_progress, merge_intervals, record_watch_segment


def test_merge_intervals_prevents_rewatch_and_seek_overcounting() -> None:
    merged = merge_intervals([(0, 20), (10, 35), (70, 150), (-4, 4)], duration_seconds=100)
    assert merged == [(0.0, 35.0), (70.0, 100)]
    coverage = coverage_for_segments(merged, 100)
    assert coverage.watched_seconds == 65
    assert coverage.fraction == 0.65


def test_video_completion_uses_unique_coverage(db) -> None:
    course = Course(name="Watch test")
    module = Module(course=course, title="Module", order_index=1)
    lecture = Lecture(course=course, module=module, title="Lecture", order_index=1, duration_seconds=100)
    video = Video(lecture=lecture, external_id="dQw4w9WgXcQ")
    db.add_all([course, module, lecture, video])
    db.flush()
    record_watch_segment(db, video=video, start_seconds=0, end_seconds=50, playback_rate=1, session_id=None)
    record_watch_segment(db, video=video, start_seconds=25, end_seconds=90, playback_rate=1, session_id=None)
    progress = course_progress(db, course, threshold=0.85)
    assert progress["lectures"][0]["watched_seconds"] == 90
    assert progress["lectures"][0]["completed"] is True
    assert progress["lecture_completion"] == 1
