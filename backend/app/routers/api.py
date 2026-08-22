from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..models import AppSetting, Assignment, Certificate, CertificatePolicy, Course, CourseSource, Grade, ImportJob, Lecture, ObsidianConfig, Resource, Submission, Video, WatchSession
from ..schemas import AIProviderConfigUpdate, AppSettingUpdate, AssignmentAnswerUpdate, BilibiliImportRequest, BilibiliLectureSourceUpdate, BilibiliQrPollRequest, CertificateRequest, CourseCreate, GradeRequest, ManualCourseImport, ObsidianConfigUpdate, StanfordImportRequest, WatchSegmentCreate, YouTubeImportRequest
from ..services.ai_providers import AIProviderConfigurationError, public_ai_provider_config, save_ai_provider_config
from ..services.assignments import OfficialAssignmentDownloader
from ..services.bilibili import BilibiliError, BilibiliService, open_media_stream
from ..services.certificates import CertificateError, CertificateService
from ..services.grader import AssignmentGrader, CloudSubmissionAcknowledgementRequired, GradingError
from ..services.obsidian import ObsidianError, ObsidianWorkspace
from ..services.stanford import StanfordGenericImporter, StanfordImportError
from ..services.utils import bilibili_embed_url, bilibili_video_url, extract_bilibili_video_id, path_is_within
from ..services.watch_progress import course_progress, finish_watch_session, latest_resume_position, record_watch_segment
from ..services.youtube import ManualVideo, MissingYouTubeApiKeyError, YouTubeImportError, YouTubeImporter

router = APIRouter(prefix="/api", tags=["syllabloom"])
settings = get_settings()
SETTINGS_ALLOWLIST = {"YOUTUBE_API_KEY", "watch_completion_threshold", "codex_max_retries"}


def _threshold(db: Session) -> float:
    item = db.scalar(select(AppSetting).where(AppSetting.key == "watch_completion_threshold"))
    if item:
        try:
            value = float(item.value)
            if 0 < value <= 1:
                return value
        except ValueError:
            pass
    return settings.watch_completion_threshold


def _commit(db: Session) -> None:
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise


def _course(db: Session, course_id: int) -> Course:
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found.")
    return course


def _assignment(db: Session, assignment_id: int) -> Assignment:
    assignment = db.get(Assignment, assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found.")
    return assignment


def _resource(resource: Resource) -> dict:
    return {
        "id": resource.id,
        "title": resource.title,
        "resource_url": resource.resource_url,
        "source_page_url": resource.source_page_url,
        "resource_type": resource.resource_type,
        "detected_as_official": resource.detected_as_official,
        "protected_resource": resource.protected_resource,
        "access_status": resource.access_status,
        "local_path": resource.local_path,
        "checksum": resource.checksum,
        "provenance": resource.provenance,
    }


def _assignment_payload(item: Assignment) -> dict:
    return {
        "id": item.id,
        "key": item.key,
        "title": item.title,
        "description": item.description,
        "official_url": item.official_url,
        "source_page_url": item.source_page_url,
        "official": item.official,
        "protected_resource": item.protected_resource,
        "requirement_level": item.requirement_level,
        "status": item.status,
        "local_root": item.local_root,
        "rubric_url": item.rubric_url,
        "ai_policy": item.ai_policy,
        "resources": [_resource(link.resource) for link in item.resources],
    }


def _grade_payload(grade: Grade) -> dict:
    return {
        "id": grade.id,
        "score": grade.score,
        "score_type": grade.score_type,
        "confidence": grade.confidence,
        "status": grade.status,
        "result": grade.result,
        "created_at": grade.created_at,
    }


def _run_payload(run) -> dict:
    return {
        "id": run.id,
        "provider": run.provider,
        "status": run.status,
        "result": run.result,
        "stdout": run.stdout,
        "stderr": run.stderr,
        "runtime_seconds": run.runtime_seconds,
        "created_at": run.created_at,
    }


def _submission_payload(submission: Submission) -> dict:
    return {
        "id": submission.id,
        "version": submission.version,
        "status": submission.status,
        "submitted_at": submission.submitted_at,
        "grades": [_grade_payload(grade) for grade in sorted(submission.grades, key=lambda item: item.id)],
        "runs": [_run_payload(run) for run in sorted(submission.grading_runs, key=lambda item: item.id)],
    }


def _assignment_history_payload(assignment: Assignment) -> list[dict]:
    return [_submission_payload(item) for item in sorted(assignment.submissions, key=lambda item: item.version, reverse=True)]


def _course_payload(db: Session, course: Course, details: bool = False) -> dict:
    payload = {
        "id": course.id,
        "name": course.name,
        "code": course.code,
        "version": course.version,
        "year": course.year,
        "quarter": course.quarter,
        "official_course_url": course.official_course_url,
        "source_type": course.source_type,
        "description": course.description,
        "channel_name": course.channel_name,
        "instructors": course.instructors,
        "course_ai_policy": course.course_ai_policy,
        "course_ai_policy_url": course.course_ai_policy_url,
        "import_status": course.import_status,
        "progress": course_progress(db, course, _threshold(db)),
    }
    if not details:
        return payload
    payload["modules"] = [{"id": item.id, "title": item.title, "description": item.description, "order_index": item.order_index} for item in sorted(course.modules, key=lambda item: item.order_index)]
    payload["lectures"] = [
        {
            "id": lecture.id,
            "module_id": lecture.module_id,
            "title": lecture.title,
            "description": lecture.description,
            "order_index": lecture.order_index,
            "source_url": lecture.source_url,
            "duration_seconds": lecture.duration_seconds,
            "slides_url": lecture.slides_url,
            "notes_url": lecture.notes_url,
            "video": {"id": lecture.video.id, "provider": lecture.video.provider, "external_id": lecture.video.external_id, "embed_url": lecture.video.embed_url, "thumbnail_url": lecture.video.thumbnail_url, "is_embeddable": lecture.video.is_embeddable} if lecture.video else None,
        }
        for lecture in sorted(course.lectures, key=lambda item: item.order_index)
    ]
    payload["sources"] = [
        {"id": item.id, "source_url": item.source_url, "source_type": item.source_type, "title": item.title, "detected_as_official": item.detected_as_official, "protected_resource": item.protected_resource, "access_status": item.access_status, "explanation": item.explanation}
        for item in course.sources
    ]
    payload["resources"] = [_resource(item) for item in course.resources]
    payload["assignments"] = [_assignment_payload(item) for item in sorted(course.assignments, key=lambda item: item.order_index)]
    return payload


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "app": "Syllabloom", "time": datetime.now(timezone.utc).isoformat()}


@router.get("/courses")
def list_courses(db: Session = Depends(get_db)) -> list[dict]:
    return [_course_payload(db, course) for course in db.scalars(select(Course).order_by(Course.updated_at.desc(), Course.id.desc())).all()]


@router.post("/courses", status_code=201)
def create_course(payload: CourseCreate, db: Session = Depends(get_db)) -> dict:
    course = Course(name=payload.name, code=payload.code, version=payload.version, official_course_url=payload.official_course_url, description=payload.description)
    db.add(course)
    db.flush()
    db.add(CertificatePolicy(course_id=course.id, video_coverage_threshold=_threshold(db)))
    _commit(db)
    return _course_payload(db, course, details=True)


@router.get("/courses/{course_id}")
def get_course(course_id: int, db: Session = Depends(get_db)) -> dict:
    return _course_payload(db, _course(db, course_id), details=True)


@router.get("/courses/{course_id}/progress")
def get_course_progress(course_id: int, db: Session = Depends(get_db)) -> dict:
    return course_progress(db, _course(db, course_id), _threshold(db))


@router.put("/lectures/{lecture_id}/bilibili-source")
def set_bilibili_lecture_source(
    lecture_id: int, payload: BilibiliLectureSourceUpdate, db: Session = Depends(get_db)
) -> dict:
    lecture = db.get(Lecture, lecture_id)
    if not lecture:
        raise HTTPException(status_code=404, detail="Lecture not found.")
    bvid = extract_bilibili_video_id(payload.url)
    if not bvid:
        raise HTTPException(status_code=422, detail="Paste a direct Bilibili video URL containing a BV identifier.")

    source_url = bilibili_video_url(bvid)
    if lecture.video is None:
        lecture.video = Video(
            provider="bilibili",
            external_id=bvid,
            embed_url=bilibili_embed_url(bvid),
            is_embeddable=True,
        )
    else:
        lecture.video.provider = "bilibili"
        lecture.video.external_id = bvid
        lecture.video.embed_url = bilibili_embed_url(bvid)
        lecture.video.thumbnail_url = None
        lecture.video.is_embeddable = True
    if payload.title and payload.title.strip():
        lecture.title = payload.title.strip()
    lecture.source_url = source_url
    lecture.course.updated_at = datetime.now(timezone.utc)

    source = db.scalar(
        select(CourseSource).where(
            CourseSource.course_id == lecture.course_id,
            CourseSource.source_url == source_url,
        )
    )
    if source is None:
        db.add(
            CourseSource(
                course_id=lecture.course_id,
                source_url=source_url,
                source_type="bilibili_learner_selected",
                title=f"{lecture.title} (Bilibili)",
                detected_as_official=False,
                explanation=(
                    "Learner-selected third-party Bilibili source. Availability and rights remain controlled by "
                    "Bilibili and the uploader."
                ),
            )
        )
    else:
        source.title = f"{lecture.title} (Bilibili)"
        source.source_type = "bilibili_learner_selected"
        source.detected_as_official = False
        source.explanation = (
            "Learner-selected third-party Bilibili source. Availability and rights remain controlled by "
            "Bilibili and the uploader."
        )
    _commit(db)
    return {"course": _course_payload(db, lecture.course, details=True)}




@router.get("/bilibili/session")
def bilibili_session(db: Session = Depends(get_db)) -> dict:
    """Login state only; cookies never leave the local database."""
    return BilibiliService(db).session_status()


@router.delete("/bilibili/session", status_code=204)
def bilibili_logout(db: Session = Depends(get_db)) -> Response:
    BilibiliService(db).clear_session()
    _commit(db)
    return Response(status_code=204)


@router.get("/bilibili/login/qrcode")
def bilibili_login_qrcode(db: Session = Depends(get_db)) -> dict:
    try:
        return BilibiliService(db).login_qrcode()
    except BilibiliError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/bilibili/login/poll")
def bilibili_login_poll(payload: BilibiliQrPollRequest, db: Session = Depends(get_db)) -> dict:
    service = BilibiliService(db)
    try:
        result = service.login_poll(payload.qrcode_key)
    except BilibiliError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    _commit(db)
    if result.get("status") == "confirmed":
        result["session"] = service.session_status()
    return result


@router.get("/bilibili/videos/{bvid}")
def bilibili_video(bvid: str, db: Session = Depends(get_db)) -> dict:
    try:
        return BilibiliService(db).video_info(bvid)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except BilibiliError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/bilibili/playurl")
def bilibili_playurl(
    bvid: str, page: int = 1, qn: int | None = None, db: Session = Depends(get_db)
) -> dict:
    try:
        return BilibiliService(db).playback(bvid, page=page, qn=qn)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except BilibiliError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/bilibili/stream")
def bilibili_stream(url: str, request: Request) -> StreamingResponse:
    """Range-preserving in-memory relay for one validated media CDN URL."""
    try:
        proxied = open_media_stream(url, request.headers.get("range"))
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except BilibiliError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    headers = {**proxied.headers, "Cache-Control": "no-store"}
    return StreamingResponse(proxied.iterator, status_code=proxied.status_code, headers=headers)



@router.post("/imports/manual-bilibili", status_code=201)
def import_manual_bilibili(payload: BilibiliImportRequest, db: Session = Depends(get_db)) -> dict:
    """Parse a learner-provided Bilibili link; multi-P videos split into lectures."""
    job = ImportJob(source_url=payload.url, import_type="bilibili_manual", status="running")
    db.add(job)
    db.flush()
    try:
        course = BilibiliService(db).import_course(payload.url, payload.name)
        db.add(CertificatePolicy(course_id=course.id, video_coverage_threshold=_threshold(db)))
        job.course_id, job.status, job.stats = course.id, "completed", {"lectures": len(course.lectures), "manual": True}
        _commit(db)
        return {"job_id": job.id, "course": _course_payload(db, course, details=True)}
    except (BilibiliError, ValueError) as exc:
        job.status, job.errors = "failed", [str(exc)]
        _commit(db)
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)) -> dict:
    courses = db.scalars(select(Course).order_by(Course.updated_at.desc())).all()
    now = datetime.now(timezone.utc)
    sessions = db.scalars(select(WatchSession).where(WatchSession.started_at >= now - timedelta(days=7))).all()
    today_seconds = sum(max(0.0, session.last_position_seconds) for session in sessions if session.started_at.date() == now.date())
    return {
        "courses": [_course_payload(db, course) for course in courses],
        "today_learning_seconds": today_seconds,
        "weekly_learning_seconds": sum(max(0.0, session.last_position_seconds) for session in sessions),
        "recent_grades": [{"id": grade.id, "score": grade.score, "score_type": grade.score_type, "status": grade.status, "created_at": grade.created_at} for grade in db.scalars(select(Grade).where(Grade.score.is_not(None)).order_by(Grade.created_at.desc()).limit(8)).all()],
        "certificates": [{"id": item.id, "certificate_id": item.certificate_id, "type": item.certificate_type, "course_id": item.course_id} for item in db.scalars(select(Certificate).order_by(Certificate.issued_at.desc()).limit(8)).all()],
        "streak_days": 0,
    }


@router.post("/watch/segments", status_code=201)
def add_watch_segment(payload: WatchSegmentCreate, db: Session = Depends(get_db)) -> dict:
    video = db.get(Video, payload.video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found.")
    try:
        segment, coverage, session_id = record_watch_segment(db, video=video, start_seconds=payload.start_seconds, end_seconds=payload.end_seconds, playback_rate=payload.playback_rate, session_id=payload.session_id, duration_seconds=payload.duration_seconds)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    _commit(db)
    return {"segment_id": segment.id, "session_id": session_id, "coverage": {"watched_seconds": coverage.watched_seconds, "fraction": coverage.fraction, "intervals": coverage.intervals}, "completed": coverage.duration_seconds is not None and coverage.fraction >= _threshold(db)}


@router.post("/watch/sessions/{session_id}/finish", status_code=204)
def close_watch_session(session_id: int, db: Session = Depends(get_db)) -> Response:
    finish_watch_session(db, session_id)
    _commit(db)
    return Response(status_code=204)


@router.get("/lectures/{lecture_id}/resume")
def get_resume_position(lecture_id: int, db: Session = Depends(get_db)) -> dict:
    from ..models import Lecture
    lecture = db.get(Lecture, lecture_id)
    if not lecture or not lecture.video:
        raise HTTPException(status_code=404, detail="Embeddable lecture video not found.")
    return {"lecture_id": lecture.id, "video_id": lecture.video.id, "resume_position_seconds": latest_resume_position(db, lecture.video.id)}


@router.post("/imports/youtube", status_code=201)
def import_youtube(payload: YouTubeImportRequest, db: Session = Depends(get_db)) -> dict:
    job = ImportJob(source_url=payload.url, import_type="youtube", status="running")
    db.add(job); db.flush()
    try:
        course = YouTubeImporter(db).import_url(payload.url)
        db.add(CertificatePolicy(course_id=course.id, video_coverage_threshold=_threshold(db)))
        job.course_id, job.status, job.stats = course.id, "completed", {"lectures": len(course.lectures), "source": "official YouTube Data API"}
        _commit(db)
        return {"job_id": job.id, "course": _course_payload(db, course, details=True)}
    except (MissingYouTubeApiKeyError, YouTubeImportError) as exc:
        job.status, job.errors = "failed", [str(exc)]
        _commit(db)
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/imports/manual-youtube", status_code=201)
def import_manual_youtube(payload: ManualCourseImport, db: Session = Depends(get_db)) -> dict:
    job = ImportJob(source_url=payload.source_url or payload.videos[0].url, import_type="youtube_manual", status="running")
    db.add(job); db.flush()
    try:
        course = YouTubeImporter(db).import_manual(payload.name, [ManualVideo(**video.model_dump()) for video in payload.videos], payload.source_url, payload.channel_name)
        db.add(CertificatePolicy(course_id=course.id, video_coverage_threshold=_threshold(db)))
        job.course_id, job.status, job.stats = course.id, "completed", {"lectures": len(course.lectures), "manual": True}
        _commit(db)
        return {"job_id": job.id, "course": _course_payload(db, course, details=True)}
    except YouTubeImportError as exc:
        job.status, job.errors = "failed", [str(exc)]
        _commit(db)
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/imports/stanford", status_code=201)
def import_stanford(payload: StanfordImportRequest, db: Session = Depends(get_db)) -> dict:
    job = ImportJob(source_url=payload.url, import_type="stanford", status="running")
    db.add(job); db.flush()
    try:
        course, stats = StanfordGenericImporter(db).import_url(payload.url, payload.max_pages, payload.max_depth)
        db.add(CertificatePolicy(course_id=course.id, video_coverage_threshold=_threshold(db)))
        job.course_id, job.status, job.stats = course.id, "completed", stats
        _commit(db)
        return {"job_id": job.id, "course": _course_payload(db, course, details=True), "stats": stats}
    except StanfordImportError as exc:
        job.status, job.errors = "failed", [str(exc)]
        _commit(db)
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/imports/{job_id}")
def get_import_job(job_id: int, db: Session = Depends(get_db)) -> dict:
    job = db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Import job not found.")
    return {"id": job.id, "source_url": job.source_url, "import_type": job.import_type, "status": job.status, "course_id": job.course_id, "stats": job.stats, "errors": job.errors}


@router.post("/assignments/{assignment_id}/download")
def download_assignment(assignment_id: int, db: Session = Depends(get_db)) -> dict:
    assignment = _assignment(db, assignment_id)
    try:
        result = OfficialAssignmentDownloader(db).download(assignment)
        try:
            result["obsidian"] = ObsidianWorkspace(db).create_assignment_workspace(assignment)
        except ObsidianError:
            result["obsidian"] = None
        _commit(db)
        return result
    except (ValueError, PermissionError) as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/courses/{course_id}/obsidian")
def export_obsidian(course_id: int, db: Session = Depends(get_db)) -> dict:
    _course(db, course_id)
    try:
        result = ObsidianWorkspace(db).export_course(course_id)
        _commit(db)
        return result
    except ObsidianError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/assignments/{assignment_id}/prepare-workspace")
def prepare_assignment_workspace(assignment_id: int, db: Session = Depends(get_db)) -> dict:
    try:
        result = ObsidianWorkspace(db).create_assignment_workspace(_assignment(db, assignment_id))
        _commit(db)
        return result
    except ObsidianError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/assignments/{assignment_id}/workspace")
def get_assignment_workspace(assignment_id: int, db: Session = Depends(get_db)) -> dict:
    """Open a managed answer file for the in-browser assignment workbench."""

    assignment = _assignment(db, assignment_id)
    try:
        answer = ObsidianWorkspace(db).read_assignment_answer(assignment)
        _commit(db)
    except (ObsidianError, OSError) as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "assignment": _assignment_payload(assignment),
        "answer": answer["content"],
        "answer_path": answer["path"],
        "storage": answer["storage"],
        "history": _assignment_history_payload(assignment),
    }


@router.put("/assignments/{assignment_id}/workspace")
def save_assignment_workspace(
    assignment_id: int, payload: AssignmentAnswerUpdate, db: Session = Depends(get_db)
) -> dict:
    """Save a learner draft before any external provider is invoked."""

    assignment = _assignment(db, assignment_id)
    try:
        answer = ObsidianWorkspace(db).write_assignment_answer(assignment, payload.content)
        if payload.content.strip() and assignment.status == "not_started":
            assignment.status = "in_progress"
        _commit(db)
    except (ObsidianError, OSError) as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "assignment": _assignment_payload(assignment),
        "answer": answer["content"],
        "answer_path": answer["path"],
        "storage": answer["storage"],
        "saved_at": datetime.now(timezone.utc),
    }


@router.post("/assignments/{assignment_id}/submissions", status_code=201)
def create_assignment_submission(assignment_id: int, db: Session = Depends(get_db)) -> dict:
    """Make an immutable local snapshot without sending it to an AI provider."""

    assignment = _assignment(db, assignment_id)
    try:
        submission = AssignmentGrader(db).create_submission(assignment)
        assignment.status = "submitted"
        _commit(db)
        return _submission_payload(submission)
    except (GradingError, ObsidianError, OSError) as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/submissions/{submission_id}/grade")
def grade_saved_submission(submission_id: int, payload: GradeRequest, db: Session = Depends(get_db)) -> dict:
    """Grade exactly one already-saved snapshot through the configured provider."""

    submission = db.get(Submission, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found.")
    try:
        AssignmentGrader(db).grade(
            submission,
            run_official_tests=payload.run_official_tests,
            run_ai_review=payload.run_ai_review,
            acknowledge_cloud_submission=payload.acknowledge_cloud_submission,
        )
        _commit(db)
        db.refresh(submission)
        return _submission_payload(submission)
    except CloudSubmissionAcknowledgementRequired as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (GradingError, ObsidianError, OSError) as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/assignments/{assignment_id}/submit")
def submit_assignment(assignment_id: int, payload: GradeRequest, db: Session = Depends(get_db)) -> dict:
    assignment = _assignment(db, assignment_id)
    try:
        grader = AssignmentGrader(db)
        submission = grader.create_submission(assignment)
        runs = grader.grade(submission, run_official_tests=payload.run_official_tests, run_ai_review=payload.run_ai_review, acknowledge_cloud_submission=payload.acknowledge_cloud_submission)
        _commit(db)
        return {"submission_id": submission.id, "version": submission.version, "runs": [{"id": run.id, "provider": run.provider, "status": run.status, "result": run.result} for run in runs]}
    except CloudSubmissionAcknowledgementRequired as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except GradingError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/assignments/{assignment_id}/history")
def assignment_history(assignment_id: int, db: Session = Depends(get_db)) -> dict:
    assignment = _assignment(db, assignment_id)
    return {"assignment_id": assignment.id, "status": assignment.status, "submissions": _assignment_history_payload(assignment)}


@router.get("/settings")
def get_settings_endpoint(db: Session = Depends(get_db)) -> dict:
    items = db.scalars(select(AppSetting).order_by(AppSetting.key)).all()
    obsidian = db.scalars(select(ObsidianConfig).where(ObsidianConfig.enabled.is_(True)).order_by(ObsidianConfig.id.desc())).first()
    return {"settings": [{"key": item.key, "value": "configured" if item.is_secret else item.value, "is_secret": item.is_secret} for item in items], "obsidian_vault_path": obsidian.vault_path if obsidian else None, "watch_completion_threshold": _threshold(db)}


@router.put("/settings/value/{key}")
def update_setting(key: str, payload: AppSettingUpdate, db: Session = Depends(get_db)) -> dict:
    if key not in SETTINGS_ALLOWLIST:
        raise HTTPException(status_code=403, detail="This setting is not writable through the local UI.")
    if key == "watch_completion_threshold":
        try:
            value = float(payload.value)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Threshold must be a number from 0 to 1.") from exc
        if not 0 < value <= 1:
            raise HTTPException(status_code=422, detail="Threshold must be greater than 0 and no greater than 1.")
    item = db.scalar(select(AppSetting).where(AppSetting.key == key))
    if item:
        item.value, item.is_secret = payload.value, payload.is_secret or key == "YOUTUBE_API_KEY"
    else:
        item = AppSetting(key=key, value=payload.value, is_secret=payload.is_secret or key == "YOUTUBE_API_KEY")
        db.add(item)
    _commit(db)
    return {"key": key, "value": "configured" if item.is_secret else item.value, "is_secret": item.is_secret}


@router.put("/settings/obsidian")
def update_obsidian_vault(payload: ObsidianConfigUpdate, db: Session = Depends(get_db)) -> dict:
    try:
        config = ObsidianWorkspace(db).configure(payload.vault_path, payload.create_if_missing)
        _commit(db)
        return {"vault_path": config.vault_path, "enabled": config.enabled}
    except ObsidianError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/settings/codex")
def codex_status() -> dict:
    return AssignmentGrader.environment_status()


def _ai_provider_status(db: Session) -> dict:
    try:
        provider = public_ai_provider_config(db)
    except AIProviderConfigurationError as exc:
        provider = {
            "provider": "invalid",
            "base_url": None,
            "model": None,
            "api_key_configured": False,
            "uses_network": False,
            "error": str(exc),
        }
    provider["codex"] = AssignmentGrader.environment_status()
    return provider


@router.get("/settings/ai-provider")
def get_ai_provider_settings(db: Session = Depends(get_db)) -> dict:
    return _ai_provider_status(db)


@router.put("/settings/ai-provider")
def update_ai_provider_settings(payload: AIProviderConfigUpdate, db: Session = Depends(get_db)) -> dict:
    try:
        save_ai_provider_config(db, payload)
        _commit(db)
        return _ai_provider_status(db)
    except AIProviderConfigurationError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/courses/{course_id}/certificate-eligibility/{certificate_type}")
def certificate_eligibility(course_id: int, certificate_type: str, db: Session = Depends(get_db)) -> dict:
    if certificate_type not in {"completion", "mastery"}:
        raise HTTPException(status_code=422, detail="Certificate type must be completion or mastery.")
    return CertificateService(db).eligibility(_course(db, course_id), certificate_type)


@router.post("/courses/{course_id}/certificates", status_code=201)
def create_certificate(course_id: int, payload: CertificateRequest, db: Session = Depends(get_db)) -> dict:
    try:
        certificate = CertificateService(db).create(_course(db, course_id), payload.certificate_type, payload.learner_name)
        _commit(db)
        return {"id": certificate.id, "certificate_id": certificate.certificate_id, "pdf_path": certificate.pdf_path, "download_url": f"/api/certificates/{certificate.id}/file"}
    except CertificateError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/certificates/{certificate_id}/file")
def get_certificate_file(certificate_id: int, db: Session = Depends(get_db)) -> FileResponse:
    certificate = db.get(Certificate, certificate_id)
    if not certificate:
        raise HTTPException(status_code=404, detail="Certificate not found.")
    path = Path(certificate.pdf_path).resolve()
    if not path.is_file() or not path_is_within(path, settings.learning_vault):
        raise HTTPException(status_code=404, detail="Certificate file not found.")
    return FileResponse(path, media_type="application/pdf", filename=path.name)


@router.post("/assignments/{assignment_id}/open-workspace")
def open_assignment_workspace(assignment_id: int, db: Session = Depends(get_db)) -> dict:
    assignment = _assignment(db, assignment_id)
    if not assignment.local_root:
        raise HTTPException(status_code=422, detail="Download the official assignment before opening its workspace.")
    target = Path(assignment.local_root).resolve()
    if not target.is_dir() or not path_is_within(target, settings.learning_vault):
        raise HTTPException(status_code=422, detail="Assignment workspace is unavailable or unsafe.")
    try:
        os.startfile(str(target))  # type: ignore[attr-defined]
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Unable to open the workspace: {exc}") from exc
    return {"opened": str(target)}
