from __future__ import annotations

from types import SimpleNamespace

from app.models import Assignment, Course, Lecture, Module
from app.services.obsidian import ObsidianWorkspace


def test_obsidian_exports_once_and_reads_the_current_answer(db, tmp_path, monkeypatch) -> None:
    settings = SimpleNamespace(learning_vault=tmp_path / "LearningVault")
    settings.learning_vault.mkdir()
    monkeypatch.setattr("app.services.obsidian.get_settings", lambda: settings)
    course = Course(name="Local Course", code="LC101")
    module = Module(course=course, title="Module", order_index=1)
    lecture = Lecture(course=course, module=module, title="Lecture A", order_index=1)
    assignment = Assignment(course=course, title="Official Assignment", key="A1", order_index=1, official=True)
    db.add_all([course, module, lecture, assignment]); db.flush()
    workspace = ObsidianWorkspace(db)
    workspace.configure(str(tmp_path / "vault"), create_if_missing=True)
    result = workspace.export_course(course.id)
    answer_path = workspace.local_assignment_answer_path(assignment)
    answer_path.write_text("# My Answer\n\nA learner edit\n", encoding="utf-8")
    workspace.export_course(course.id)
    assert "A learner edit" in answer_path.read_text(encoding="utf-8")
    assert str(answer_path) in result["notes"]
