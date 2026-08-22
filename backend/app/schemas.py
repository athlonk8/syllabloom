from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CourseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    code: str | None = None
    version: str | None = None
    official_course_url: str | None = None
    description: str | None = None


class VideoCreate(BaseModel):
    url: str
    title: str = Field(min_length=1, max_length=500)
    duration_seconds: float | None = Field(default=None, ge=0)
    description: str | None = None
    thumbnail_url: str | None = None


class ManualCourseImport(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    source_url: str | None = None
    channel_name: str | None = None
    videos: list[VideoCreate] = Field(min_length=1, max_length=500)


class YouTubeImportRequest(BaseModel):
    url: str = Field(min_length=10)


class StanfordImportRequest(BaseModel):
    url: str = Field(min_length=12)
    max_pages: int | None = Field(default=None, ge=1, le=50)
    max_depth: int | None = Field(default=None, ge=0, le=3)


class WatchSegmentCreate(BaseModel):
    video_id: int
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    playback_rate: float = Field(default=1.0, gt=0, le=4)
    session_id: int | None = None
    duration_seconds: float | None = Field(default=None, gt=0)

    @field_validator("end_seconds")
    @classmethod
    def end_after_start(cls, value: float, info):
        if "start_seconds" in info.data and value <= info.data["start_seconds"]:
            raise ValueError("end_seconds must be greater than start_seconds")
        return value


class AppSettingUpdate(BaseModel):
    value: str
    is_secret: bool = False


class ObsidianConfigUpdate(BaseModel):
    vault_path: str = Field(min_length=1)
    create_if_missing: bool = False


class GradeResult(BaseModel):
    score: float = Field(ge=0, le=100)
    score_type: Literal["official_tests", "official_rubric", "deterministic", "ai_estimated"]
    confidence: float = Field(ge=0, le=1)
    conceptual_understanding: float = Field(ge=0, le=100)
    reasoning: float = Field(ge=0, le=100)
    technical_accuracy: float = Field(ge=0, le=100)
    clarity: float = Field(ge=0, le=100)
    strengths: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    critical_errors: list[str] = Field(default_factory=list)
    suggested_review_topics: list[str] = Field(default_factory=list)
    status: Literal["PASS", "NEEDS_REVISION", "ERROR"]


class GradeRequest(BaseModel):
    run_official_tests: bool = True
    run_codex_review: bool = True
    acknowledge_cloud_submission: bool = False


class CertificateRequest(BaseModel):
    certificate_type: Literal["completion", "mastery"]
    learner_name: str = Field(min_length=1, max_length=300)


class CourseSummary(ORMModel):
    id: int
    name: str
    code: str | None
    version: str | None
    source_type: str
    official_course_url: str | None
    import_status: str


class ImportJobSummary(ORMModel):
    id: int
    source_url: str
    import_type: str
    status: str
    course_id: int | None
    stats: dict
    errors: list[str]
    created_at: datetime
