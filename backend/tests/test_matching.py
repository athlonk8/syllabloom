from __future__ import annotations

from sqlalchemy import select

from app.models import Assignment, Course, Lecture, Module, Resource, Video

from app.services.matching import extract_course_codes, propagate_matching_assignments


def _make_official_course(db, name: str, code_key: str = "assignment-1") -> Course:
    course = Course(name=name, official_course_url="https://cs336.stanford.edu/", source_type="stanford_pages")
    db.add(course)
    db.flush()
    module = Module(course_id=course.id, title="Assignments", order_index=1)
    db.add(module)
    assignment = Assignment(
        course_id=course.id,
        key=code_key,
        title="Assignment 1",
        order_index=1,
        official_url="https://cs336.stanford.edu/assignments/assignment1.pdf",
        source_page_url="https://cs336.stanford.edu/assignments/",
        official=True,
    )
    db.add(assignment)
    db.flush()
    resource = Resource(
        course_id=course.id,
        title="assignment1.pdf",
        resource_url="https://cs336.stanford.edu/assignments/assignment1.pdf",
        source_page_url="https://cs336.stanford.edu/assignments/",
        resource_type="pdf",
        detected_as_official=True,
        local_path=None,
    )
    db.add(resource)
    db.flush()
    from app.models import AssignmentResource

    db.add(AssignmentResource(assignment_id=assignment.id, resource_id=resource.id))
    db.commit()
    return course


def _make_video_course(db, name: str) -> Course:
    course = Course(name=name, source_type="bilibili_manual")
    db.add(course)
    db.flush()
    lecture = Lecture(course_id=course.id, title="P1", order_index=1)
    db.add(lecture)
    db.flush()
    db.add(Video(lecture_id=lecture.id, provider="bilibili", external_id="BV1XX411c7mD"))
    db.commit()
    return course


def test_extract_course_codes_finds_university_codes() -> None:
    assert extract_course_codes("CS336: Language Modeling from Scratch") == {"CS336"}
    assert extract_course_codes("斯坦福CS336：从头开始构建大模型", "MIT 6.S191 intro") >= {"CS336"}
    assert extract_course_codes("大模型课程", None) == set()


def test_propagation_copies_assignments_into_matching_video_course(db) -> None:
    official = _make_official_course(db, "CS336: Language Modeling from Scratch")
    video_course = _make_video_course(db, "斯坦福CS336：从头开始构建大模型")

    stats = propagate_matching_assignments(db, video_course)

    assert stats["matched_assignments"] == 1
    db.expire_all()
    copied = video_course.assignments[0]
    assert copied.key == "assignment-1"
    # The learner's own progress starts fresh in the new course.
    assert copied.status == "not_started" and copied.submissions == []
    mirrored = copied.resources[0].resource
    assert mirrored.resource_url == "https://cs336.stanford.edu/assignments/assignment1.pdf"
    # Downloads are not inherited; the learner re-downloads into this course.
    assert mirrored.local_path is None and mirrored.downloaded_at is None
    assert mirrored.provenance["matched_from_course"] == official.name


def test_propagation_is_idempotent_and_ignores_unrelated_courses(db) -> None:
    official = _make_official_course(db, "CS336: Language Modeling from Scratch")
    unrelated = _make_video_course(db, "张阿姨家常菜教程")

    assert propagate_matching_assignments(db, unrelated)["matched_assignments"] == 0
    video_course = _make_video_course(db, "斯坦福CS336：从头开始构建大模型")
    assert propagate_matching_assignments(db, video_course)["matched_assignments"] == 1

    db.expire_all()
    again = propagate_matching_assignments(db, video_course)
    assert again["matched_assignments"] == 0
    keys = sorted(item.key for item in video_course.assignments)
    assert keys == ["assignment-1"]
    assert db.scalar(select(Course).where(Course.id == official.id)) is not None


def test_reverse_direction_feeds_earlier_video_courses_from_new_official_import(db) -> None:
    video_course = _make_video_course(db, "斯坦福CS336：从头开始构建大模型")
    official = _make_official_course(db, "CS336: Language Modeling from Scratch")

    stats = propagate_matching_assignments(db, official)

    assert stats["matched_assignments"] == 0  # official course already owns its assignments
    assert propagate_matching_assignments(db, video_course)["matched_assignments"] == 1
