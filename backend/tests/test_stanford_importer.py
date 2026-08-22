from __future__ import annotations

from pathlib import Path

import pytest

from app.services.stanford import StanfordGenericImporter

FIXTURES = Path(__file__).parent / "fixtures"


class FixtureImporter(StanfordGenericImporter):
    def __init__(self, db, pages: dict[str, str]) -> None:
        super().__init__(db)
        self.pages = pages

    def _fetch(self, url: str) -> dict:
        html = self.pages.get(url)
        return {"status": "ok", "html": html} if html else {"status": "error", "error": "fixture missing"}


@pytest.mark.parametrize(
    ("root", "pages", "expected_code"),
    [
        (
            "https://cs229.stanford.edu/",
            {
                "https://cs229.stanford.edu/": (FIXTURES / "cs229.html").read_text(encoding="utf-8"),
                "https://cs229.stanford.edu/lectures.html": (FIXTURES / "cs229_lectures.html").read_text(encoding="utf-8"),
                "https://cs229.stanford.edu/assignments.html": (FIXTURES / "cs229_assignments.html").read_text(encoding="utf-8"),
            },
            "CS229",
        ),
        (
            "https://web.stanford.edu/class/cs224n/",
            {
                "https://web.stanford.edu/class/cs224n/": (FIXTURES / "cs224n.html").read_text(encoding="utf-8"),
                "https://web.stanford.edu/class/cs224n/materials.html": (FIXTURES / "cs224n_materials.html").read_text(encoding="utf-8"),
            },
            "CS224N",
        ),
        (
            "https://cs336.stanford.edu/",
            {
                "https://cs336.stanford.edu/": (FIXTURES / "cs336.html").read_text(encoding="utf-8"),
                "https://cs336.stanford.edu/schedule.html": (FIXTURES / "cs336_schedule.html").read_text(encoding="utf-8"),
                "https://cs336.stanford.edu/assignments/index.html": (FIXTURES / "cs336_assignments.html").read_text(encoding="utf-8"),
            },
            "CS336",
        ),
    ],
)
def test_bounded_generic_importer_detects_three_course_shapes(db, monkeypatch, root, pages, expected_code) -> None:
    monkeypatch.setattr("app.services.stanford.time.sleep", lambda _: None)
    course, stats = FixtureImporter(db, pages).import_url(root, max_pages=8, max_depth=1)
    assert course.code == expected_code
    assert stats["pages_visited"] >= 2
    assert course.lectures
    assert course.assignments
    assert any(resource.detected_as_official for resource in course.resources)
    external = [resource for resource in course.resources if "github.com" in resource.resource_url]
    if external:
        assert all(resource.provenance["official_external_resource"] is True for resource in external)


def test_protected_link_is_recorded_but_not_followed(db, monkeypatch) -> None:
    monkeypatch.setattr("app.services.stanford.time.sleep", lambda _: None)
    pages = {"https://cs229.stanford.edu/": (FIXTURES / "cs229.html").read_text(encoding="utf-8")}
    course, _ = FixtureImporter(db, pages).import_url("https://cs229.stanford.edu/", max_pages=1, max_depth=0)
    protected = [resource for resource in course.resources if resource.protected_resource]
    assert protected
    assert protected[0].access_status == "protected"


def test_assignment_preview_links_are_grouped_with_their_official_assignment(db, monkeypatch) -> None:
    monkeypatch.setattr("app.services.stanford.time.sleep", lambda _: None)
    root = "https://cs336.stanford.edu/"
    pages = {
        root: """
            <html><body>
              <h1>CS336: Language Modeling from Scratch</h1>
              <p>Spring 2026</p>
              <a href="https://github.com/stanford-cs336/assignment1-basics/tree/main">Assignment 1: Basics</a>
              <a href="https://github.com/stanford-cs336/assignment1-basics/blob/main/README.md">preview</a>
            </body></html>
        """,
    }

    course, _ = FixtureImporter(db, pages).import_url(root, max_pages=1, max_depth=0)

    assert len(course.assignments) == 1
    assert course.assignments[0].key == "A1"
    assert course.assignments[0].title == "Assignment 1: Basics"
    assert len(course.assignments[0].resources) == 2


def test_same_public_video_can_belong_to_two_imported_courses(db, monkeypatch) -> None:
    monkeypatch.setattr("app.services.stanford.time.sleep", lambda _: None)
    first_root = "https://cs336.stanford.edu/"
    second_root = "https://web.stanford.edu/class/cs224n/"
    course_html = """
        <html><body>
          <h1>Public Stanford course</h1>
          <a href="https://www.youtube.com/watch?v=dQw4w9WgXcQ">Lecture recording</a>
        </body></html>
    """
    importer = FixtureImporter(db, {first_root: course_html, second_root: course_html})

    first, _ = importer.import_url(first_root, max_pages=1, max_depth=0)
    second, _ = importer.import_url(second_root, max_pages=1, max_depth=0)

    assert len(first.lectures) == 1
    assert len(second.lectures) == 1
