from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Course, Grade, Lecture, Submission, Video, WatchSegment, WatchSession


@dataclass(frozen=True)
class Coverage:
    watched_seconds: float
    duration_seconds: float | None
    fraction: float
    intervals: list[tuple[float, float]]


def merge_intervals(
    intervals: Iterable[tuple[float, float]], duration_seconds: float | None = None
) -> list[tuple[float, float]]:
    """Return normalized, non-overlapping watched intervals.

    Seeking and replaying create many overlapping segments. This merge is the
    only source for progress calculations, so total watched time never exceeds
    actual video duration.
    """
    normalized: list[tuple[float, float]] = []
    ceiling = duration_seconds if duration_seconds and duration_seconds > 0 else None
    for start, end in intervals:
        start = max(0.0, float(start))
        end = max(0.0, float(end))
        if ceiling is not None:
            start, end = min(start, ceiling), min(end, ceiling)
        if end > start:
            normalized.append((start, end))
    if not normalized:
        return []

    normalized.sort(key=lambda item: (item[0], item[1]))
    merged = [normalized[0]]
    for start, end in normalized[1:]:
        previous_start, previous_end = merged[-1]
        if start <= previous_end:
            merged[-1] = (previous_start, max(previous_end, end))
        else:
            merged.append((start, end))
    return merged


def coverage_for_segments(
    intervals: Iterable[tuple[float, float]], duration_seconds: float | None
) -> Coverage:
    merged = merge_intervals(intervals, duration_seconds)
    watched = sum(end - start for start, end in merged)
    fraction = watched / duration_seconds if duration_seconds and duration_seconds > 0 else 0.0
    return Coverage(
        watched_seconds=watched,
        duration_seconds=duration_seconds,
        fraction=min(1.0, fraction),
        intervals=merged,
    )


def get_video_coverage(db: Session, video: Video) -> Coverage:
    duration = video.lecture.duration_seconds
    intervals = [
        (segment.start_seconds, segment.end_seconds)
        for segment in db.scalars(select(WatchSegment).where(WatchSegment.video_id == video.id)).all()
    ]
    return coverage_for_segments(intervals, duration)


def record_watch_segment(
    db: Session,
    *,
    video: Video,
    start_seconds: float,
    end_seconds: float,
    playback_rate: float,
    session_id: int | None,
    duration_seconds: float | None = None,
) -> tuple[WatchSegment, Coverage, int]:
    if duration_seconds and duration_seconds > 0 and not video.lecture.duration_seconds:
        video.lecture.duration_seconds = duration_seconds

    duration = video.lecture.duration_seconds
    if duration:
        start_seconds, end_seconds = min(start_seconds, duration), min(end_seconds, duration)
    if end_seconds <= start_seconds:
        raise ValueError("No valid watch interval remains after duration bounds were applied.")

    session: WatchSession | None = None
    if session_id:
        session = db.get(WatchSession, session_id)
        if not session or session.video_id != video.id:
            raise ValueError("Watch session does not belong to this video.")
    if session is None:
        session = WatchSession(video_id=video.id, last_position_seconds=end_seconds)
        db.add(session)
        db.flush()
    session.last_position_seconds = end_seconds
    session.ended_at = None

    segment = WatchSegment(
        video_id=video.id,
        session_id=session.id,
        start_seconds=start_seconds,
        end_seconds=end_seconds,
        playback_rate=playback_rate,
    )
    db.add(segment)
    db.flush()
    return segment, get_video_coverage(db, video), session.id


def finish_watch_session(db: Session, session_id: int) -> None:
    session = db.get(WatchSession, session_id)
    if session:
        session.ended_at = datetime.now(timezone.utc)


def lecture_progress(db: Session, lecture: Lecture, threshold: float) -> dict:
    if not lecture.video:
        return {"lecture_id": lecture.id, "fraction": 0.0, "completed": False, "watched_seconds": 0.0}
    coverage = get_video_coverage(db, lecture.video)
    return {
        "lecture_id": lecture.id,
        "video_id": lecture.video.id,
        "duration_seconds": coverage.duration_seconds,
        "watched_seconds": round(coverage.watched_seconds, 2),
        "fraction": round(coverage.fraction, 4),
        "completed": coverage.duration_seconds is not None and coverage.fraction >= threshold,
        "resume_position_seconds": latest_resume_position(db, lecture.video.id),
    }


def latest_resume_position(db: Session, video_id: int) -> float:
    session = db.scalars(
        select(WatchSession)
        .where(WatchSession.video_id == video_id)
        .order_by(WatchSession.updated_at.desc(), WatchSession.id.desc())
    ).first()
    return float(session.last_position_seconds) if session else 0.0


def course_progress(db: Session, course: Course, threshold: float) -> dict:
    lectures = sorted(course.lectures, key=lambda item: item.order_index)
    lecture_items = [lecture_progress(db, lecture, threshold) for lecture in lectures]
    required = [item for item, lecture in zip(lecture_items, lectures, strict=True) if lecture.required]
    completed = sum(1 for item in required if item["completed"])
    lecture_completion = completed / len(required) if required else 0.0

    assignments = [
        assignment
        for assignment in course.assignments
        if assignment.official and not assignment.protected_resource and assignment.requirement_level == "required"
    ]
    assignment_completed = sum(1 for assignment in assignments if assignment.status == "passed")
    assignment_completion = assignment_completed / len(assignments) if assignments else 1.0
    latest_scores: list[float] = []
    for assignment in assignments:
        grade = db.scalars(
            select(Grade)
            .join(Grade.submission)
            .where(Submission.assignment_id == assignment.id, Grade.score.is_not(None))
            .order_by(Grade.created_at.desc(), Grade.id.desc())
        ).first()
        if grade and grade.score is not None:
            latest_scores.append(float(grade.score))

    return {
        "course_id": course.id,
        "lecture_completion": round(lecture_completion, 4),
        "assignment_completion": round(assignment_completion, 4),
        "course_completion": round((lecture_completion * 0.7) + (assignment_completion * 0.3), 4),
        "lectures": lecture_items,
        "required_lecture_count": len(required),
        "completed_lecture_count": completed,
        "required_assignment_count": len(assignments),
        "passed_assignment_count": assignment_completed,
        "average_assignment_score": round(sum(latest_scores) / len(latest_scores), 2) if latest_scores else None,
    }
