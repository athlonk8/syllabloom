from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Assignment, Grade, GradingRun, Submission
from ..schemas import GradeResult
from .obsidian import ObsidianWorkspace
from .utils import path_is_within, slugify


class GradingError(RuntimeError):
    pass


class CloudSubmissionAcknowledgementRequired(GradingError):
    pass


def _trim(value: str | None, limit: int = 20_000) -> str:
    if not value:
        return ""
    return value if len(value) <= limit else value[:limit] + "\n[output truncated]"


class CodexGrader:
    """Stages immutable snapshots and asks Codex for feedback only.

    Codex is launched with the CLI's verified `--sandbox read-only` option.
    The original answer and source files are never passed as writable paths and
    the user must explicitly acknowledge the external Codex submission.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()

    @staticmethod
    def environment_status() -> dict:
        status: dict[str, object] = {"installed": False, "version": None, "help": None, "error": None}
        try:
            version = subprocess.run(["codex", "--version"], capture_output=True, text=True, timeout=10, check=False)
            help_result = subprocess.run(["codex", "--help"], capture_output=True, text=True, timeout=10, check=False)
        except FileNotFoundError:
            status["error"] = "Codex CLI is not installed or is not on PATH."
            return status
        except subprocess.TimeoutExpired:
            status["error"] = "Codex CLI detection timed out."
            return status
        status["installed"] = version.returncode == 0
        status["version"] = version.stdout.strip() or version.stderr.strip()
        status["help"] = _trim(help_result.stdout or help_result.stderr, 3000)
        if version.returncode != 0:
            status["error"] = _trim(version.stderr, 500)
        return status

    def create_submission(self, assignment: Assignment) -> Submission:
        answer_path = ObsidianWorkspace(self.db).local_assignment_answer_path(assignment)
        if not answer_path.is_file():
            raise GradingError("The current Answer.md is missing. Re-open the assignment workspace and try again.")
        root = Path(assignment.local_root or self.settings.learning_vault / "uninitialized" / str(assignment.id)).resolve()
        if not path_is_within(root, self.settings.learning_vault):
            raise GradingError("Assignment workspace is outside the configured LearningVault.")
        submissions_dir = (root / "submission").resolve()
        submissions_dir.mkdir(parents=True, exist_ok=True)
        next_version = (self.db.scalar(select(func.max(Submission.version)).where(Submission.assignment_id == assignment.id)) or 0) + 1
        snapshot = (submissions_dir / f"submission-v{next_version}.md").resolve()
        if not path_is_within(snapshot, root):
            raise GradingError("Unsafe submission snapshot path.")
        shutil.copy2(answer_path, snapshot)
        submission = Submission(
            assignment_id=assignment.id,
            version=next_version,
            answer_path=str(answer_path),
            snapshot_path=str(snapshot),
            status="submitted",
        )
        self.db.add(submission)
        self.db.flush()
        return submission

    def grade(
        self,
        submission: Submission,
        *,
        run_official_tests: bool,
        run_codex_review: bool,
        acknowledge_cloud_submission: bool,
    ) -> list[GradingRun]:
        assignment = submission.assignment
        workspace = self._make_grading_workspace(assignment, submission)
        runs: list[GradingRun] = []
        if run_official_tests:
            test_run, test_grade = self._run_official_tests(submission, workspace)
            if test_run:
                runs.append(test_run)
                if test_grade:
                    self.db.add(test_grade)
        if run_codex_review:
            if not acknowledge_cloud_submission:
                raise CloudSubmissionAcknowledgementRequired(
                    "Codex review may send the staged assignment snapshot to your configured Codex provider. "
                    "Set acknowledge_cloud_submission=true only after explicitly confirming this submission."
                )
            codex_run, codex_grade = self._run_codex_review(submission, workspace)
            runs.append(codex_run)
            if codex_grade:
                self.db.add(codex_grade)
                assignment.status = "passed" if codex_grade.status == "PASS" else "needs_revision"
        self.db.flush()
        return runs

    def _make_grading_workspace(self, assignment: Assignment, submission: Submission) -> Path:
        grading_root = (self.settings.data_dir / "grading-runs").resolve()
        grading_root.mkdir(parents=True, exist_ok=True)
        workspace = Path(tempfile.mkdtemp(prefix=f"{slugify(assignment.key)}-v{submission.version}-", dir=grading_root)).resolve()
        if not path_is_within(workspace, grading_root):
            raise GradingError("Unable to create a safe grading workspace.")
        (workspace / "answer").mkdir()
        shutil.copy2(submission.snapshot_path, workspace / "answer" / "Answer.md")
        assignment_root = Path(assignment.local_root) if assignment.local_root else None
        if assignment_root and assignment_root.is_dir():
            original = assignment_root / "original"
            if original.is_dir():
                shutil.copytree(original, workspace / "official-original", dirs_exist_ok=False)
            user_workspace = assignment_root / "workspace"
            if user_workspace.is_dir():
                shutil.copytree(user_workspace, workspace / "user-workspace", dirs_exist_ok=False)
        return workspace

    def _run_official_tests(self, submission: Submission, workspace: Path) -> tuple[GradingRun | None, Grade | None]:
        has_tests = any(workspace.rglob("test_*.py")) or any(workspace.rglob("*_test.py")) or (workspace / "pytest.ini").exists()
        if not has_tests:
            return None, None
        started = time.monotonic()
        try:
            process = subprocess.run(
                [sys.executable, "-m", "pytest", "-q"],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            stdout, stderr, exit_code, status = process.stdout, process.stderr, process.returncode, "completed"
        except subprocess.TimeoutExpired as exc:
            stdout, stderr, exit_code, status = exc.stdout or "", exc.stderr or "Timed out after 60 seconds.", None, "timed_out"
        runtime = time.monotonic() - started
        result = self._pytest_result(stdout, stderr, exit_code)
        run = GradingRun(
            submission_id=submission.id,
            provider="official_tests",
            status=status,
            command=f"{sys.executable} -m pytest -q",
            stdout=_trim(stdout),
            stderr=_trim(stderr),
            exit_code=exit_code,
            runtime_seconds=runtime,
            request_snapshot_path=str(workspace),
            result=result,
        )
        grade = Grade(
            submission_id=submission.id,
            score=result["score"],
            score_type="official_tests",
            confidence=1.0,
            status="PASS" if exit_code == 0 else "NEEDS_REVISION",
            result=result,
        )
        if exit_code == 0:
            submission.assignment.status = "passed"
        return run, grade

    @staticmethod
    def _pytest_result(stdout: str, stderr: str, exit_code: int | None) -> dict:
        summary = f"{stdout}\n{stderr}"
        passed = int((re.search(r"(\d+)\s+passed", summary) or [0, 0])[1])
        failed = int((re.search(r"(\d+)\s+failed", summary) or [0, 0])[1])
        errors = int((re.search(r"(\d+)\s+errors?", summary) or [0, 0])[1])
        total = passed + failed + errors
        score = round(100 * passed / total, 2) if total else (100.0 if exit_code == 0 else 0.0)
        return {"passed": passed, "failed": failed, "errors": errors, "score": score, "exit_code": exit_code}

    def _run_codex_review(self, submission: Submission, workspace: Path) -> tuple[GradingRun, Grade | None]:
        status = self.environment_status()
        if not status["installed"]:
            raise GradingError(str(status["error"] or "Codex CLI is unavailable."))
        schema_path = workspace / "grade-result.schema.json"
        output_path = workspace / "codex-last-message.json"
        schema_path.write_text(json.dumps(GradeResult.model_json_schema(), indent=2), encoding="utf-8")
        ai_policy = submission.assignment.ai_policy or submission.assignment.course.course_ai_policy or "No course AI policy was found publicly."
        prompt = (
            "You are a strict learning feedback reviewer. Inspect only the staged files in this grading workspace. "
            "Do not modify any files. Do not provide a complete solution, complete replacement code, or an answer that lets the learner bypass the assignment. "
            "Use progressive feedback: identify the affected question, name the concept, then give a bounded hint. "
            f"Course AI policy: {ai_policy}\n"
            "If official tests are present, treat their results as higher-priority evidence than your qualitative view. "
            "Return only the requested JSON object."
        )
        command = [
            "codex",
            "exec",
            "--skip-git-repo-check",
            "--sandbox",
            "read-only",
            "--ask-for-approval",
            "never",
            "-C",
            str(workspace),
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(output_path),
            prompt,
        ]
        started = time.monotonic()
        retries = 1
        process: subprocess.CompletedProcess[str] | None = None
        parse_error: str | None = None
        parsed_grade: GradeResult | None = None
        for _ in range(retries + 1):
            try:
                process = subprocess.run(command, capture_output=True, text=True, timeout=240, check=False)
            except subprocess.TimeoutExpired as exc:
                process = None
                parse_error = "Codex review timed out after 240 seconds."
                stdout, stderr, exit_code = exc.stdout or "", exc.stderr or "", None
                break
            stdout, stderr, exit_code = process.stdout, process.stderr, process.returncode
            try:
                if not output_path.is_file():
                    raise ValueError("Codex did not produce an output file.")
                parsed_grade = GradeResult.model_validate_json(output_path.read_text(encoding="utf-8"))
                parse_error = None
                break
            except Exception as exc:
                parse_error = f"Invalid Codex grading JSON: {exc}"
        runtime = time.monotonic() - started
        result = parsed_grade.model_dump() if parsed_grade else {"error": parse_error}
        run = GradingRun(
            submission_id=submission.id,
            provider="codex",
            status="completed" if parsed_grade and process and process.returncode == 0 else "failed",
            command="codex exec --sandbox read-only --output-schema <schema> --output-last-message <file>",
            stdout=_trim(stdout if "stdout" in locals() else ""),
            stderr=_trim(stderr if "stderr" in locals() else ""),
            exit_code=exit_code if "exit_code" in locals() else None,
            runtime_seconds=runtime,
            request_snapshot_path=str(workspace),
            result=result,
        )
        grade = (
            Grade(
                submission_id=submission.id,
                score=parsed_grade.score,
                score_type=parsed_grade.score_type,
                confidence=parsed_grade.confidence,
                status=parsed_grade.status,
                result=parsed_grade.model_dump(),
            )
            if parsed_grade
            else None
        )
        return run, grade
