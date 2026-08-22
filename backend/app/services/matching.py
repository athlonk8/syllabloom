"""Content-based matching between locally imported courses.

Video-only imports (for example a Bilibili lecture series) often carry the
university course code somewhere in their title.  When another local course
shares that code — typically an import of the official course website — its
assignments and resources are copied over so the learner studies videos and
assignments in one place.  Copies never carry watch progress, submission
history, or downloaded-file state; those belong to the learner's own work.
"""

from __future__ import annotations

import re

COURSE_CODE = re.compile(r"(?<![A-Za-z0-9])([A-Z]{2,4})[- ]?(\d{2,3}[A-Z]?)(?![A-Za-z0-9])")

from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models import Assignment, AssignmentResource, Course, Resource



def extract_course_codes(*texts: str | None) -> set[str]:
    """Return uppercase course identifiers such as ``CS336`` found in texts."""
    codes: set[str] = set()
    for text in texts:
        if not text:
            continue
        for match in COURSE_CODE.finditer(text):
            codes.add(match.group(1) + match.group(2))
    return codes


def _clone_resource(db: Session, target_course_id: int, resource: Resource, origin: str) -> Resource:
    existing = db.scalar(
        select(Resource).where(
            Resource.course_id == target_course_id,
            Resource.resource_url == resource.resource_url,
        )
    )
    if existing:
        return existing
    clone = Resource(
        course_id=target_course_id,
        lecture_id=None,
        title=resource.title,
        resource_url=resource.resource_url,
        source_page_url=resource.source_page_url,
        resource_type=resource.resource_type,
        detected_as_official=resource.detected_as_official,
        protected_resource=resource.protected_resource,
        access_status=resource.access_status,
        local_path=None,
        checksum=None,
        downloaded_at=None,
        provenance={**(resource.provenance or {}), "matched_from_course": origin},
    )
    db.add(clone)
    db.flush()
    return clone


def propagate_matching_assignments(db: Session, target: Course) -> dict[str, object]:
    """Copy assignments from sibling courses whose course codes intersect."""
    codes = extract_course_codes(target.name, target.official_course_url or "")
    if not codes:
        return {"matched_assignments": 0}

    copied = 0
    matched_from: list[str] = []
    for other in db.scalars(select(Course).where(Course.id != target.id)):
        other_codes = extract_course_codes(other.name, other.official_course_url or "")
        if not (codes & other_codes) or not other.assignments:
            continue
        existing_keys = {item.key for item in target.assignments}
        for source in sorted(other.assignments, key=lambda item: item.order_index):
            if source.key in existing_keys:
                continue
            clone = Assignment(
                course_id=target.id,
                key=source.key[:100],
                title=source.title[:500],
                order_index=source.order_index,
                description=source.description,
                official_url=source.official_url,
                source_page_url=source.source_page_url,
                official=source.official,
                protected_resource=source.protected_resource,
                requirement_level=source.requirement_level,
                status="not_started",
                rubric_url=source.rubric_url,
                ai_policy=source.ai_policy,
            )
            db.add(clone)
            db.flush()
            for link in source.resources:
                mirrored = _clone_resource(db, target.id, link.resource, other.name)
                db.add(AssignmentResource(assignment_id=clone.id, resource_id=mirrored.id, role=link.role))
            db.flush()
            existing_keys.add(source.key)
            copied += 1
        matched_from.append(other.name)

    return {"matched_assignments": copied, "matched_from": matched_from}
