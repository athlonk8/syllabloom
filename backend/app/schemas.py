from __future__ import annotations

from datetime import datetime
from typing import Literal
from urllib.parse import urlparse

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


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


class BilibiliLectureSourceUpdate(BaseModel):
    url: str = Field(min_length=12, max_length=1_000)
    title: str | None = Field(default=None, min_length=1, max_length=500)


class BilibiliQrPollRequest(BaseModel):
    qrcode_key: str = Field(min_length=8, max_length=128)


class BilibiliImportRequest(BaseModel):
    url: str = Field(min_length=12, max_length=1_000)
    name: str | None = Field(default=None, min_length=1, max_length=300)


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


class AIProviderConfigUpdate(BaseModel):
    provider: Literal["codex_cli", "openai_compatible", "disabled"]
    base_url: str | None = Field(default=None, max_length=500)
    model: str | None = Field(default=None, max_length=300)
    api_key: str | None = Field(default=None, max_length=10_000)
    clear_api_key: bool = False

    @model_validator(mode="after")
    def validate_openai_compatible_fields(self) -> "AIProviderConfigUpdate":
        self.base_url = self.base_url.strip() if self.base_url is not None else None
        self.model = self.model.strip() if self.model is not None else None
        if self.provider != "openai_compatible":
            return self
        if not self.base_url or not self.model:
            raise ValueError("OpenAI-compatible feedback requires both a base URL and a model.")
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("OpenAI-compatible base URL must be a complete http(s) URL.")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Base URL cannot contain credentials, query parameters, or fragments.")
        return self


class ObsidianConfigUpdate(BaseModel):
    vault_path: str = Field(min_length=1)
    create_if_missing: bool = False


class AssignmentAnswerUpdate(BaseModel):
    """The learner-owned Markdown saved by the assignment workbench."""

    content: str = Field(default="", max_length=500_000)


class GradeCriterion(BaseModel):
    """One transparent part of an AI feedback result.

    The fields are optional because many public course pages do not publish a
    point-by-point rubric.  When one is absent, Codex should use descriptive
    feedback instead of inventing official point values.
    """

    title: str = Field(min_length=1, max_length=300)
    score: float | None = Field(default=None, ge=0, le=100)
    max_score: float | None = Field(default=None, gt=0, le=100)
    feedback: str = Field(default="", max_length=8_000)


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
    summary: str = Field(default="", max_length=8_000)
    detailed_feedback: str = Field(default="", max_length=20_000)
    rubric_breakdown: list[GradeCriterion] = Field(default_factory=list)
    status: Literal["PASS", "NEEDS_REVISION", "ERROR"]


class GradeRequest(BaseModel):
    run_official_tests: bool = True
    run_ai_review: bool = Field(
        default=True,
        validation_alias=AliasChoices("run_ai_review", "run_codex_review"),
    )
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
