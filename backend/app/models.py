from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class Course(Timestamped, Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    code: Mapped[str | None] = mapped_column(String(80))
    version: Mapped[str | None] = mapped_column(String(160))
    year: Mapped[str | None] = mapped_column(String(20))
    quarter: Mapped[str | None] = mapped_column(String(40))
    official_course_url: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(40), default="manual", nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    channel_name: Mapped[str | None] = mapped_column(String(300))
    instructors: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    course_ai_policy: Mapped[str | None] = mapped_column(Text)
    course_ai_policy_url: Mapped[str | None] = mapped_column(Text)
    import_status: Mapped[str] = mapped_column(String(40), default="ready", nullable=False)

    modules: Mapped[list["Module"]] = relationship(back_populates="course", cascade="all, delete-orphan")
    lectures: Mapped[list["Lecture"]] = relationship(back_populates="course", cascade="all, delete-orphan")
    sources: Mapped[list["CourseSource"]] = relationship(back_populates="course", cascade="all, delete-orphan")
    resources: Mapped[list["Resource"]] = relationship(back_populates="course", cascade="all, delete-orphan")
    assignments: Mapped[list["Assignment"]] = relationship(back_populates="course", cascade="all, delete-orphan")
    certificate_policy: Mapped["CertificatePolicy | None"] = relationship(
        back_populates="course", cascade="all, delete-orphan", uselist=False
    )


class Module(Timestamped, Base):
    __tablename__ = "modules"
    __table_args__ = (UniqueConstraint("course_id", "order_index", name="uq_module_course_order"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    course: Mapped[Course] = relationship(back_populates="modules")
    lectures: Mapped[list["Lecture"]] = relationship(back_populates="module")


class Lecture(Timestamped, Base):
    __tablename__ = "lectures"
    __table_args__ = (UniqueConstraint("course_id", "order_index", name="uq_lecture_course_order"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    module_id: Mapped[int | None] = mapped_column(ForeignKey("modules.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[str | None] = mapped_column(String(80))
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    slides_url: Mapped[str | None] = mapped_column(Text)
    notes_url: Mapped[str | None] = mapped_column(Text)

    course: Mapped[Course] = relationship(back_populates="lectures")
    module: Mapped[Module | None] = relationship(back_populates="lectures")
    video: Mapped["Video | None"] = relationship(back_populates="lecture", cascade="all, delete-orphan", uselist=False)
    notes: Mapped[list["LearningNote"]] = relationship(back_populates="lecture")


class Video(Timestamped, Base):
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(primary_key=True)
    lecture_id: Mapped[int] = mapped_column(ForeignKey("lectures.id", ondelete="CASCADE"), unique=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(40), default="youtube", nullable=False)
    external_id: Mapped[str] = mapped_column(String(160), nullable=False)
    embed_url: Mapped[str | None] = mapped_column(Text)
    thumbnail_url: Mapped[str | None] = mapped_column(Text)
    is_embeddable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    lecture: Mapped[Lecture] = relationship(back_populates="video")
    watch_sessions: Mapped[list["WatchSession"]] = relationship(back_populates="video", cascade="all, delete-orphan")
    watch_segments: Mapped[list["WatchSegment"]] = relationship(back_populates="video", cascade="all, delete-orphan")


class CourseSource(Timestamped, Base):
    __tablename__ = "course_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str | None] = mapped_column(String(500))
    detected_as_official: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    protected_resource: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    access_status: Mapped[str] = mapped_column(String(50), default="public", nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text)

    course: Mapped[Course] = relationship(back_populates="sources")


class Resource(Timestamped, Base):
    __tablename__ = "resources"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    lecture_id: Mapped[int | None] = mapped_column(ForeignKey("lectures.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    resource_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_page_url: Mapped[str | None] = mapped_column(Text)
    resource_type: Mapped[str] = mapped_column(String(80), nullable=False)
    detected_as_official: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    protected_resource: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    access_status: Mapped[str] = mapped_column(String(50), default="public", nullable=False)
    local_path: Mapped[str | None] = mapped_column(Text)
    checksum: Mapped[str | None] = mapped_column(String(128))
    downloaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    course: Mapped[Course] = relationship(back_populates="resources")
    assignment_links: Mapped[list["AssignmentResource"]] = relationship(back_populates="resource", cascade="all, delete-orphan")


class Assignment(Timestamped, Base):
    __tablename__ = "assignments"
    __table_args__ = (UniqueConstraint("course_id", "key", name="uq_assignment_course_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    official_url: Mapped[str | None] = mapped_column(Text)
    source_page_url: Mapped[str | None] = mapped_column(Text)
    official: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    protected_resource: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    requirement_level: Mapped[str] = mapped_column(String(40), default="required", nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="not_started", nullable=False)
    local_root: Mapped[str | None] = mapped_column(Text)
    rubric_url: Mapped[str | None] = mapped_column(Text)
    ai_policy: Mapped[str | None] = mapped_column(Text)

    course: Mapped[Course] = relationship(back_populates="assignments")
    resources: Mapped[list["AssignmentResource"]] = relationship(back_populates="assignment", cascade="all, delete-orphan")
    submissions: Mapped[list["Submission"]] = relationship(back_populates="assignment", cascade="all, delete-orphan")
    notes: Mapped[list["LearningNote"]] = relationship(back_populates="assignment")


class AssignmentResource(Timestamped, Base):
    __tablename__ = "assignment_resources"
    __table_args__ = (UniqueConstraint("assignment_id", "resource_id", name="uq_assignment_resource"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False)
    resource_id: Mapped[int] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="original", nullable=False)

    assignment: Mapped[Assignment] = relationship(back_populates="resources")
    resource: Mapped[Resource] = relationship(back_populates="assignment_links")


class Submission(Timestamped, Base):
    __tablename__ = "submissions"
    __table_args__ = (UniqueConstraint("assignment_id", "version", name="uq_submission_assignment_version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    answer_path: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_path: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="submitted", nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    assignment: Mapped[Assignment] = relationship(back_populates="submissions")
    grades: Mapped[list["Grade"]] = relationship(back_populates="submission", cascade="all, delete-orphan")
    grading_runs: Mapped[list["GradingRun"]] = relationship(back_populates="submission", cascade="all, delete-orphan")


class Grade(Timestamped, Base):
    __tablename__ = "grades"

    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False)
    score: Mapped[float | None] = mapped_column(Float)
    score_type: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    submission: Mapped[Submission] = relationship(back_populates="grades")


class GradingRun(Timestamped, Base):
    __tablename__ = "grading_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    command: Mapped[str | None] = mapped_column(Text)
    stdout: Mapped[str | None] = mapped_column(Text)
    stderr: Mapped[str | None] = mapped_column(Text)
    exit_code: Mapped[int | None] = mapped_column(Integer)
    runtime_seconds: Mapped[float | None] = mapped_column(Float)
    request_snapshot_path: Mapped[str | None] = mapped_column(Text)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    submission: Mapped[Submission] = relationship(back_populates="grading_runs")


class WatchSession(Timestamped, Base):
    __tablename__ = "watch_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_position_seconds: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    video: Mapped[Video] = relationship(back_populates="watch_sessions")


class WatchSegment(Timestamped, Base):
    __tablename__ = "watch_segments"

    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("watch_sessions.id", ondelete="SET NULL"))
    start_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    end_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    playback_rate: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    video: Mapped[Video] = relationship(back_populates="watch_segments")


class LearningNote(Timestamped, Base):
    __tablename__ = "learning_notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    lecture_id: Mapped[int | None] = mapped_column(ForeignKey("lectures.id", ondelete="SET NULL"))
    assignment_id: Mapped[int | None] = mapped_column(ForeignKey("assignments.id", ondelete="SET NULL"))
    kind: Mapped[str] = mapped_column(String(80), nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)

    lecture: Mapped[Lecture | None] = relationship(back_populates="notes")
    assignment: Mapped[Assignment | None] = relationship(back_populates="notes")


class CertificatePolicy(Timestamped, Base):
    __tablename__ = "certificate_policies"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), unique=True, nullable=False)
    video_coverage_threshold: Mapped[float] = mapped_column(Float, default=0.85, nullable=False)
    minimum_assignment_score: Mapped[float] = mapped_column(Float, default=70.0, nullable=False)
    average_assignment_score: Mapped[float] = mapped_column(Float, default=75.0, nullable=False)
    require_final_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    course: Mapped[Course] = relationship(back_populates="certificate_policy")


class Certificate(Timestamped, Base):
    __tablename__ = "certificates"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    certificate_type: Mapped[str] = mapped_column(String(50), nullable=False)
    certificate_id: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    learner_name: Mapped[str] = mapped_column(String(300), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    pdf_path: Mapped[str] = mapped_column(Text, nullable=False)
    record_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    policy_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class ImportJob(Timestamped, Base):
    __tablename__ = "import_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    import_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="queued", nullable=False)
    course_id: Mapped[int | None] = mapped_column(ForeignKey("courses.id", ondelete="SET NULL"))
    stats: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    errors: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)


class AppSetting(Timestamped, Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class ObsidianConfig(Timestamped, Base):
    __tablename__ = "obsidian_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    vault_path: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
