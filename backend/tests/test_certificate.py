from __future__ import annotations

from types import SimpleNamespace

from pypdf import PdfReader

from app.models import Assignment, CertificatePolicy, Course, Lecture, Module, Video
from app.services.certificates import CertificateService
from app.services.watch_progress import record_watch_segment


def test_completion_certificate_is_a_real_local_pdf(db, tmp_path, monkeypatch) -> None:
    settings = SimpleNamespace(learning_vault=tmp_path / "LearningVault")
    settings.learning_vault.mkdir()
    monkeypatch.setattr("app.services.certificates.get_settings", lambda: settings)
    course = Course(name="Certificate Test Course", code="TEST101", version="Spring 2026")
    module = Module(course=course, title="Module", order_index=1)
    lecture = Lecture(course=course, module=module, title="Lecture", order_index=1, duration_seconds=100)
    video = Video(lecture=lecture, external_id="dQw4w9WgXcQ")
    assignment = Assignment(course=course, title="Public assignment", key="A1", order_index=1, official=True, status="passed")
    policy = CertificatePolicy(course=course, video_coverage_threshold=.85)
    db.add_all([course, module, lecture, video, assignment, policy]); db.flush()
    record_watch_segment(db, video=video, start_seconds=0, end_seconds=90, playback_rate=1, session_id=None)
    certificate = CertificateService(db).create(course, "completion", "Integration Test Learner")
    assert certificate.pdf_path.endswith(".pdf")
    assert PdfReader(certificate.pdf_path).pages
    text = "\n".join(page.extract_text() or "" for page in PdfReader(certificate.pdf_path).pages)
    assert "PERSONAL LEARNING CERTIFICATE" in text
