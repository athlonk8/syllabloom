from __future__ import annotations

import json

from app.models import Assignment, Course, Submission
from app.schemas import AIProviderConfigUpdate
from app.services.ai_providers import AIProviderConfig, OPENAI_COMPATIBLE, public_ai_provider_config, save_ai_provider_config
from app.services.grader import AssignmentGrader


def _grade_payload() -> dict:
    return {
        "score": 84,
        "score_type": "ai_estimated",
        "confidence": 0.72,
        "conceptual_understanding": 82,
        "reasoning": 85,
        "technical_accuracy": 80,
        "clarity": 88,
        "strengths": ["Clear explanation of the main idea."],
        "issues": ["Add evidence for the edge case."],
        "critical_errors": [],
        "suggested_review_topics": ["Boundary conditions"],
        "status": "PASS",
    }


def test_openai_compatible_config_masks_local_secret(db) -> None:
    save_ai_provider_config(
        db,
        AIProviderConfigUpdate(
            provider="openai_compatible",
            base_url="http://localhost:11434/v1/",
            model="qwen2.5:7b",
            api_key="local-secret",
        ),
    )
    db.flush()

    public = public_ai_provider_config(db)
    assert public == {
        "provider": "openai_compatible",
        "base_url": "http://localhost:11434/v1",
        "model": "qwen2.5:7b",
        "api_key_configured": True,
        "uses_network": True,
    }


def test_openai_compatible_grader_posts_only_staged_answer(db, tmp_path, monkeypatch) -> None:
    course = Course(name="Local course", course_ai_policy="Feedback only.")
    assignment = Assignment(course=course, title="Exercise", key="ex1", description="Explain the invariant.")
    submission = Submission(
        assignment=assignment,
        version=1,
        answer_path=str(tmp_path / "Answer.md"),
        snapshot_path=str(tmp_path / "submission-v1.md"),
    )
    db.add(submission)
    db.flush()
    workspace = tmp_path / "grading"
    (workspace / "answer").mkdir(parents=True)
    (workspace / "answer" / "Answer.md").write_text("My answer is an invariant.", encoding="utf-8")

    captured: dict = {}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"choices": [{"message": {"content": json.dumps(_grade_payload())}}]}

    class FakeClient:
        def __init__(self, **_: object) -> None:
            pass

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def post(self, url: str, *, headers: dict, json: dict) -> FakeResponse:
            captured["url"] = url
            captured["headers"] = headers
            captured["request"] = json
            return FakeResponse()

    monkeypatch.setattr("app.services.grader.httpx.Client", FakeClient)
    provider = AIProviderConfig(
        provider=OPENAI_COMPATIBLE,
        base_url="http://localhost:11434/v1",
        model="qwen2.5:7b",
        api_key="local-secret",
    )

    run, grade = AssignmentGrader(db)._run_openai_compatible_review(submission, workspace, provider, None)

    assert captured["url"] == "http://localhost:11434/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer local-secret"
    assert "My answer is an invariant." in captured["request"]["messages"][1]["content"]
    assert run.provider == OPENAI_COMPATIBLE
    assert "local-secret" not in (run.command or "")
    assert grade and grade.score == 84


def test_grade_parser_accepts_a_json_code_fence() -> None:
    fence = chr(96) * 3
    parsed = AssignmentGrader._parse_ai_grade(f"{fence}json\n{json.dumps(_grade_payload())}\n{fence}")
    assert parsed.status == "PASS"
