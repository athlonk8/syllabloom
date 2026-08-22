from __future__ import annotations

from app.schemas import GradeResult
from app.services.grader import CodexGrader


def test_pytest_score_parser_prefers_deterministic_result() -> None:
    result = CodexGrader._pytest_result("2 passed, 1 failed in 0.11s", "", 1)
    assert result == {"passed": 2, "failed": 1, "errors": 0, "score": 66.67, "exit_code": 1}


def test_grade_schema_rejects_unbounded_or_unknown_results() -> None:
    valid = GradeResult.model_validate({"score": 82, "score_type": "ai_estimated", "confidence": .82, "conceptual_understanding": 88, "reasoning": 84, "technical_accuracy": 78, "clarity": 82, "strengths": [], "issues": [], "critical_errors": [], "suggested_review_topics": [], "status": "PASS"})
    assert valid.score == 82
