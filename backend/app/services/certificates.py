from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Certificate, CertificatePolicy, Course, Grade, Submission
from .utils import path_is_within, safe_filename
from .watch_progress import course_progress


class CertificateError(RuntimeError):
    pass


class CertificateService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()

    def eligibility(self, course: Course, certificate_type: str) -> dict:
        policy = course.certificate_policy or CertificatePolicy(course_id=course.id)
        progress = course_progress(self.db, course, policy.video_coverage_threshold)
        assignments = [
            item
            for item in course.assignments
            if item.official and not item.protected_resource and item.requirement_level == "required"
        ]
        assignment_scores = [self._latest_score(item.id) for item in assignments]
        assignment_scores = [score for score in assignment_scores if score is not None]
        unmet: list[str] = []
        if progress["lecture_completion"] < 1:
            unmet.append("Required video coverage is below the configured threshold.")
        if any(item.status != "passed" for item in assignments):
            unmet.append("Not all publicly available required official assignments have passed.")
        if certificate_type == "mastery":
            if not assignment_scores or min(assignment_scores) < policy.minimum_assignment_score:
                unmet.append("At least one assignment is below the minimum assignment score.")
            average = sum(assignment_scores) / len(assignment_scores) if assignment_scores else 0
            if average < policy.average_assignment_score:
                unmet.append("Average assignment score is below the mastery threshold.")
            if policy.require_final_review:
                unmet.append("Final Review is required by this policy and is not implemented in the MVP.")
        return {
            "eligible": not unmet,
            "unmet": unmet,
            "policy": {
                "video_coverage_threshold": policy.video_coverage_threshold,
                "minimum_assignment_score": policy.minimum_assignment_score,
                "average_assignment_score": policy.average_assignment_score,
                "require_final_review": policy.require_final_review,
            },
            "progress": progress,
            "assignment_scores": assignment_scores,
        }

    def create(self, course: Course, certificate_type: str, learner_name: str) -> Certificate:
        check = self.eligibility(course, certificate_type)
        if not check["eligible"]:
            raise CertificateError("Certificate requirements are not met: " + " ".join(check["unmet"]))
        certificate_id = f"PALO-{datetime.now(timezone.utc):%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"
        record = {
            "certificate_id": certificate_id,
            "course_id": course.id,
            "course": course.name,
            "learner_name": learner_name,
            "certificate_type": certificate_type,
            "issued_at": datetime.now(timezone.utc).isoformat(),
            "eligibility": check,
        }
        record_hash = hashlib.sha256(json.dumps(record, sort_keys=True).encode("utf-8")).hexdigest()
        target_dir = (self.settings.learning_vault / "certificates").resolve()
        target_dir.mkdir(parents=True, exist_ok=True)
        filename = safe_filename(f"{certificate_id}-{course.code or course.name}.pdf")
        pdf_path = (target_dir / filename).resolve()
        if not path_is_within(pdf_path, target_dir):
            raise CertificateError("Unsafe certificate output path.")
        self._render(pdf_path, course, certificate_type, learner_name, certificate_id, record_hash, check)
        certificate = Certificate(
            course_id=course.id,
            certificate_type=certificate_type,
            certificate_id=certificate_id,
            learner_name=learner_name,
            pdf_path=str(pdf_path),
            record_hash=record_hash,
            policy_snapshot=check,
        )
        self.db.add(certificate)
        self.db.flush()
        return certificate

    def _latest_score(self, assignment_id: int) -> float | None:
        grade = self.db.scalars(
            select(Grade)
            .join(Grade.submission)
            .where(Submission.assignment_id == assignment_id, Grade.score.is_not(None))
            .order_by(Grade.created_at.desc(), Grade.id.desc())
        ).first()
        return float(grade.score) if grade and grade.score is not None else None

    @staticmethod
    def _render(
        pdf_path: Path,
        course: Course,
        certificate_type: str,
        learner_name: str,
        certificate_id: str,
        record_hash: str,
        check: dict,
    ) -> None:
        document = SimpleDocTemplate(
            str(pdf_path), pagesize=A4, rightMargin=22 * mm, leftMargin=22 * mm, topMargin=24 * mm, bottomMargin=22 * mm
        )
        styles = getSampleStyleSheet()
        title = ParagraphStyle("CertificateTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=25, leading=31, textColor=colors.HexColor("#102A43"), alignment=1)
        subtitle = ParagraphStyle("CertificateSubtitle", parent=styles["BodyText"], fontSize=10, leading=15, alignment=1, textColor=colors.HexColor("#486581"))
        name = ParagraphStyle("LearnerName", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=22, leading=28, textColor=colors.HexColor("#0B7285"), alignment=1)
        body = ParagraphStyle("CertificateBody", parent=styles["BodyText"], fontSize=12, leading=19, alignment=1, textColor=colors.HexColor("#243B53"))
        story = [
            Spacer(1, 17 * mm),
            Paragraph("PERSONAL LEARNING CERTIFICATE", title),
            Spacer(1, 6 * mm),
            Paragraph("INDEPENDENT LEARNING CREDENTIAL", subtitle),
            Spacer(1, 16 * mm),
            Paragraph("This certifies that", body),
            Spacer(1, 5 * mm),
            Paragraph(learner_name, name),
            Spacer(1, 7 * mm),
            Paragraph(f"has earned a <b>{certificate_type.title()} Certificate</b> for", body),
            Spacer(1, 4 * mm),
            Paragraph(course.name, ParagraphStyle("CourseName", parent=name, fontSize=17, leading=23)),
            Spacer(1, 9 * mm),
            Paragraph(
                f"Based on publicly available materials from: {course.code or course.name} {course.version or ''}".strip(), body
            ),
            Paragraph("Completed through: Syllabloom", body),
            Spacer(1, 11 * mm),
        ]
        table = Table(
            [
                ["Completed lectures", f"{check['progress']['completed_lecture_count']} / {check['progress']['required_lecture_count']}"],
                ["Public official assignments", f"{check['progress']['passed_assignment_count']} / {check['progress']['required_assignment_count']}"],
                ["Certificate ID", certificate_id],
            ],
            colWidths=[68 * mm, 78 * mm],
        )
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F0F7F7")),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B8D8D8")),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#243B53")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )
        story.extend(
            [
                table,
                Spacer(1, 12 * mm),
                Paragraph("Completed using publicly available course materials.", subtitle),
                Paragraph(
                    "This certificate is not issued, sponsored, endorsed, or accredited by Stanford University.", subtitle
                ),
                Spacer(1, 5 * mm),
                Paragraph(f"Local record hash: {record_hash}", ParagraphStyle("Hash", parent=subtitle, fontSize=7)),
            ]
        )
        document.build(story)
