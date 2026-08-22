from __future__ import annotations

import re
import shutil
from pathlib import Path

from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Assignment, Course, LearningNote, ObsidianConfig
from .utils import path_is_within, safe_filename, slugify


class ObsidianError(RuntimeError):
    pass


class ObsidianWorkspace:
    """Creates only inside the user-selected AI-Learning subtree.

    Files are created once by default and never overwritten, so edits made in
    Obsidian remain the authoritative version Syllabloom reads on submit.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()

    def configure(self, vault_path: str, create_if_missing: bool = False) -> ObsidianConfig:
        vault = Path(vault_path).expanduser().resolve(strict=False)
        if not vault.exists():
            if not create_if_missing:
                raise ObsidianError("Obsidian Vault Path does not exist. Create it explicitly or choose an existing vault.")
            vault.mkdir(parents=True, exist_ok=True)
        if not vault.is_dir():
            raise ObsidianError("Obsidian Vault Path must be a directory.")
        for config in self.db.scalars(select(ObsidianConfig).where(ObsidianConfig.enabled.is_(True))).all():
            config.enabled = False
        config = ObsidianConfig(vault_path=str(vault), enabled=True)
        self.db.add(config)
        self.db.flush()
        return config

    def get_config(self) -> ObsidianConfig:
        config = self.db.scalars(
            select(ObsidianConfig).where(ObsidianConfig.enabled.is_(True)).order_by(ObsidianConfig.id.desc())
        ).first()
        if not config:
            raise ObsidianError("Set an Obsidian Vault Path in Settings before creating learning notes.")
        vault = Path(config.vault_path)
        if not vault.is_dir():
            raise ObsidianError("Configured Obsidian Vault Path no longer exists.")
        return config

    def export_course(self, course_id: int) -> dict:
        course = self.db.get(Course, course_id)
        if not course:
            raise ObsidianError("Course not found.")
        config = self.get_config()
        vault = Path(config.vault_path).resolve()
        root = (vault / "AI-Learning" / slugify(course.code or course.name, "course")).resolve()
        if not path_is_within(root, vault):
            raise ObsidianError("Refusing to write outside the configured Obsidian vault.")
        root.mkdir(parents=True, exist_ok=True)
        notes: list[str] = []
        dashboard = root / "Course Dashboard.md"
        self._write_if_absent(
            dashboard,
            self._course_dashboard(course),
        )
        notes.append(str(dashboard))
        lecture_dir = root / "Lectures"
        lecture_dir.mkdir(exist_ok=True)
        for lecture in sorted(course.lectures, key=lambda item: item.order_index):
            note = lecture_dir / f"L{lecture.order_index:02d} {safe_filename(lecture.title)}.md"
            self._write_if_absent(note, self._lecture_note(course, lecture))
            self._upsert_note(course.id, lecture.id, None, "lecture", note)
            notes.append(str(note))
        for assignment in sorted(course.assignments, key=lambda item: item.order_index):
            assignment_notes = self.create_assignment_workspace(assignment, root)
            notes.extend(assignment_notes.values())
        self.db.flush()
        return {"course_id": course.id, "root": str(root), "notes": notes}

    def create_assignment_workspace(self, assignment: Assignment, course_root: Path | None = None) -> dict[str, str]:
        course = assignment.course
        if course_root is None:
            config = self.get_config()
            vault = Path(config.vault_path).resolve()
            course_root = (vault / "AI-Learning" / slugify(course.code or course.name, "course")).resolve()
            if not path_is_within(course_root, vault):
                raise ObsidianError("Refusing to write outside the configured Obsidian vault.")
        assignment_dir = (course_root / "Assignments" / f"{slugify(assignment.key)} {safe_filename(assignment.title)}").resolve()
        if not path_is_within(assignment_dir, course_root):
            raise ObsidianError("Refusing an unsafe assignment note path.")
        assignment_dir.mkdir(parents=True, exist_ok=True)
        original_path = self._copy_first_original_pdf(assignment, assignment_dir)
        assignment_note = assignment_dir / "Assignment.md"
        answer_note = assignment_dir / "Answer.md"
        feedback_note = assignment_dir / "Feedback.md"
        self._write_if_absent(assignment_note, self._assignment_note(course, assignment, original_path))
        self._write_if_absent(
            answer_note,
            f"---\ncourse: {course.code or course.name}\nassignment: {assignment.key}\nstatus: not_started\n---\n\n# My Answer - {assignment.title}\n\n",
        )
        self._write_if_absent(feedback_note, "# Feedback\n\nFeedback from each grading run will be linked here; this note is never overwritten.\n")
        self._upsert_note(course.id, None, assignment.id, "assignment", assignment_note)
        self._upsert_note(course.id, None, assignment.id, "answer", answer_note)
        self._upsert_note(course.id, None, assignment.id, "feedback", feedback_note)
        self.db.flush()
        return {"assignment": str(assignment_note), "answer": str(answer_note), "feedback": str(feedback_note)}

    def local_assignment_answer_path(self, assignment: Assignment) -> Path:
        """Use Obsidian Answer.md when configured, otherwise a local workspace file."""
        answer_note = self.db.scalars(
            select(LearningNote)
            .where(LearningNote.assignment_id == assignment.id, LearningNote.kind == "answer")
            .order_by(LearningNote.id.desc())
        ).first()
        if answer_note and Path(answer_note.path).is_file():
            candidate = Path(answer_note.path).resolve()
            try:
                vault = Path(self.get_config().vault_path).resolve()
            except ObsidianError:
                vault = None
            if vault and path_is_within(candidate, vault):
                return candidate
        try:
            return Path(self.create_assignment_workspace(assignment)["answer"])
        except ObsidianError:
            root = Path(assignment.local_root or self._local_assignment_root(assignment)).resolve()
            workspace = (root / "workspace").resolve()
            if not path_is_within(workspace, self.settings.learning_vault):
                raise ObsidianError("Refusing to create a workspace outside LearningVault.")
            workspace.mkdir(parents=True, exist_ok=True)
            assignment.local_root = str(root)
            answer = workspace / "Answer.md"
            self._write_if_absent(answer, f"# My Answer - {assignment.title}\n\n")
            return answer

    def read_assignment_answer(self, assignment: Assignment) -> dict[str, str]:
        """Return the learner-owned answer without exposing arbitrary file reads."""

        answer = self.local_assignment_answer_path(assignment).resolve()
        return {
            "content": answer.read_text(encoding="utf-8", errors="replace"),
            "path": str(answer),
            "storage": "obsidian" if self._is_obsidian_path(answer) else "local",
        }

    def write_assignment_answer(self, assignment: Assignment, content: str) -> dict[str, str]:
        """Atomically persist an answer in the managed local or Obsidian workspace."""

        if "\x00" in content:
            raise ObsidianError("An answer cannot contain null characters.")
        answer = self.local_assignment_answer_path(assignment).resolve()
        if not self._is_managed_answer_path(answer):
            raise ObsidianError("Refusing to write outside the managed assignment workspace.")
        temporary = answer.with_name(f".{answer.name}.syllabloom-writing")
        if not path_is_within(temporary, answer.parent):
            raise ObsidianError("Unable to create a safe temporary answer file.")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(answer)
        return {"content": content, "path": str(answer), "storage": "obsidian" if self._is_obsidian_path(answer) else "local"}

    def local_submission_root(self, assignment: Assignment) -> Path:
        """Create the local, app-owned root used for immutable submission snapshots.

        An Obsidian vault can live anywhere the learner chooses, whereas
        submission snapshots always remain under Syllabloom's LearningVault.
        """

        root = Path(assignment.local_root or self._local_assignment_root(assignment)).resolve()
        if not path_is_within(root, self.settings.learning_vault):
            raise ObsidianError("Refusing to create submission records outside LearningVault.")
        root.mkdir(parents=True, exist_ok=True)
        assignment.local_root = str(root)
        return root

    def _local_assignment_root(self, assignment: Assignment) -> Path:
        course = assignment.course
        return self.settings.learning_vault / f"{slugify(course.code or course.name)}_{slugify(course.version or 'current')}" / "assignments" / slugify(assignment.key)

    def _is_obsidian_path(self, path: Path) -> bool:
        try:
            return path_is_within(path, Path(self.get_config().vault_path).resolve())
        except ObsidianError:
            return False

    def _is_managed_answer_path(self, path: Path) -> bool:
        return path_is_within(path, self.settings.learning_vault) or self._is_obsidian_path(path)

    @staticmethod
    def _write_if_absent(path: Path, content: str) -> None:
        if not path.exists():
            path.write_text(content, encoding="utf-8")

    def _upsert_note(self, course_id: int, lecture_id: int | None, assignment_id: int | None, kind: str, path: Path) -> None:
        existing = self.db.scalar(
            select(LearningNote).where(
                LearningNote.course_id == course_id,
                LearningNote.lecture_id == lecture_id,
                LearningNote.assignment_id == assignment_id,
                LearningNote.kind == kind,
            )
        )
        if existing:
            existing.path = str(path)
        else:
            self.db.add(
                LearningNote(
                    course_id=course_id,
                    lecture_id=lecture_id,
                    assignment_id=assignment_id,
                    kind=kind,
                    path=str(path),
                )
            )

    @staticmethod
    def _course_dashboard(course) -> str:
        return (
            f"---\ncourse: {course.code or course.name}\nsource_url: {course.official_course_url or ''}\n"
            f"official: {str(course.source_type == 'stanford').lower()}\n---\n\n# {course.name}\n\n"
            "## Learning dashboard\n\n- [ ] Review this course's official source and AI policy\n- [ ] Watch required lectures\n- [ ] Complete publicly available official assignments\n\n"
            "This folder was created by Syllabloom. Your note edits remain the source of truth.\n"
        )

    @staticmethod
    def _lecture_note(course, lecture) -> str:
        return (
            f"---\ncourse: {course.code or course.name}\nlecture_order: {lecture.order_index}\n"
            f"source_url: {lecture.source_url or ''}\n---\n\n# {lecture.title}\n\n## Notes\n\n\n## Questions\n\n\n"
        )

    def _assignment_note(self, course, assignment: Assignment, copied_pdf: Path | None) -> str:
        frontmatter = (
            f"---\ncourse: {course.code or course.name}\nversion: {course.version or 'Current'}\n"
            f"assignment: {assignment.key}\nsource_url: {assignment.official_url or ''}\nofficial: {str(assignment.official).lower()}\n"
            "status: not_started\n---\n\n"
        )
        if copied_pdf:
            extracted = self._pdf_questions(copied_pdf)
            if extracted:
                return frontmatter + f"# {assignment.title}\n\n" + extracted
            return (
                frontmatter
                + f"# {assignment.title}\n\n## Original assignment\n\nSee original PDF: [[{copied_pdf.name}]]\n\n"
                + "### My Answer\n\n"
            )
        return (
            frontmatter
            + f"# {assignment.title}\n\n## Official assignment\n\n{assignment.official_url or 'No public URL recorded'}\n\n### My Answer\n\n"
        )

    def _copy_first_original_pdf(self, assignment: Assignment, assignment_dir: Path) -> Path | None:
        for link in assignment.resources:
            resource = link.resource
            if resource.local_path and Path(resource.local_path).suffix.lower() == ".pdf":
                source = Path(resource.local_path)
                if source.is_file():
                    destination = (assignment_dir / safe_filename(source.name)).resolve()
                    if path_is_within(destination, assignment_dir) and not destination.exists():
                        shutil.copy2(source, destination)
                    return destination if destination.exists() else None
        return None

    @staticmethod
    def _pdf_questions(pdf_path: Path) -> str | None:
        try:
            reader = PdfReader(str(pdf_path))
            text = "\n".join((page.extract_text() or "") for page in reader.pages).strip()
        except Exception:
            return None
        if len(text) < 120:
            return None
        chunks = re.split(r"(?=^(?:Question\s+\d+|Q\d+\b|\d+[.)]))", text, flags=re.I | re.M)
        question_chunks = [chunk.strip() for chunk in chunks if re.match(r"^(?:Question\s+\d+|Q\d+\b|\d+[.)])", chunk.strip(), re.I)]
        if not question_chunks:
            return None
        output = ["# Assignment", "", "## Official source extract", ""]
        for index, chunk in enumerate(question_chunks, start=1):
            output.extend([f"## Question {index}", "", chunk[:8000], "", "### My Answer", ""])
        return "\n".join(output)
