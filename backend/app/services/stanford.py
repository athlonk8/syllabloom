from __future__ import annotations

import re
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urldefrag, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Assignment, AssignmentResource, Course, CourseSource, Lecture, Module, Resource, Video
from .assignments import OfficialAssignmentResolver, assignment_key
from .utils import extract_youtube_video_id, is_stanford_url

COURSE_LINK_RE = re.compile(
    r"(?:syllabus|schedule|lecture|recording|video|assignment|homework|\bhw\b|problem\s*set|pset|exercise|"
    r"starter\s*code|handout|project|slides?|notes?|reading|materials?)",
    re.IGNORECASE,
)
LECTURE_RE = re.compile(r"(?:lecture|recording|video|week\s*\d+)", re.IGNORECASE)
PROTECTED_RE = re.compile(r"(?:canvas|gradescope|stanford\s+login|stanford\s+sso|sign\s+in|authentication\s+required)", re.I)
LOGIN_PAGE_RE = re.compile(
    r"(?:stanford\s+(?:web\s+)?login|sign\s+in\s+with\s+stanford|requires\s+stanford\s+authentication|"
    r"authentication\s+required\s+to\s+access)",
    re.I,
)
AI_POLICY_RE = re.compile(r"(?:generative\s+ai|\bllm\b|chatgpt|ai\s+policy|honor\s+code|academic\s+integrity)", re.I)


class StanfordImportError(RuntimeError):
    pass


@dataclass(frozen=True)
class DiscoveredLink:
    url: str
    label: str
    context: str
    is_external: bool
    is_crawl_candidate: bool
    is_protected: bool


@dataclass(frozen=True)
class ParsedCoursePage:
    title: str
    course_code: str | None
    year: str | None
    quarter: str | None
    instructors: list[str]
    ai_policy_text: str | None
    ai_policy_url: str | None
    is_protected: bool
    links: list[DiscoveredLink]
    youtube_embeds: list[str]


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _normal_url(url: str) -> str:
    url, _ = urldefrag(url)
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", parsed.query, ""))


def parse_course_page(html: str, page_url: str, course_host: str | None = None) -> ParsedCoursePage:
    """Pure HTML discovery for importer fixture tests and live crawling."""
    soup = BeautifulSoup(html, "html.parser")
    page_text = _clean_text(soup.get_text(" ", strip=True))
    h1 = soup.find("h1")
    page_title = _clean_text(h1.get_text(" ", strip=True)) if h1 else ""
    if not page_title and soup.title:
        page_title = _clean_text(soup.title.get_text(" ", strip=True))
    page_title = page_title or "Stanford course"

    code_match = re.search(r"\b(?:CS|EE|STAT|MS&E|CME|AA|BIOE)\s*-?\d{2,3}[A-Z]?\b", page_text, re.I)
    year_match = re.search(r"\b(20\d{2})\b", page_text)
    quarter_match = re.search(r"\b(Spring|Summer|Autumn|Fall|Winter)\b", page_text, re.I)
    instructors: list[str] = []
    instructor_match = re.search(
        r"(?:instructors?|professors?|teaching\s+staff)\s*[:\-]?\s*([^|.;]{2,180})", page_text, re.I
    )
    if instructor_match:
        instructors = [item.strip() for item in re.split(r",|\band\b", instructor_match.group(1)) if item.strip()]

    ai_policy_text: str | None = None
    ai_policy_url: str | None = None
    for element in soup.find_all(["a", "p", "li", "section", "div"]):
        text = _clean_text(element.get_text(" ", strip=True))
        if text and AI_POLICY_RE.search(text):
            ai_policy_text = text[:4000]
            if element.name == "a" and element.get("href"):
                ai_policy_url = _normal_url(urljoin(page_url, element["href"]))
            else:
                anchor = element.find("a", href=True)
                if anchor:
                    ai_policy_url = _normal_url(urljoin(page_url, anchor["href"]))
            break

    page_host = (urlparse(page_url).hostname or "").lower()
    course_host = (course_host or page_host).lower()
    links: list[DiscoveredLink] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        raw_url = anchor["href"].strip()
        if raw_url.startswith(("#", "mailto:", "javascript:", "tel:")):
            continue
        absolute_url = _normal_url(urljoin(page_url, raw_url))
        parsed = urlparse(absolute_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or absolute_url in seen:
            continue
        seen.add(absolute_url)
        label = _clean_text(anchor.get_text(" ", strip=True)) or Path(parsed.path).name or absolute_url
        parent = anchor.parent
        context = _clean_text(parent.get_text(" ", strip=True)) if parent else label
        is_external = parsed.hostname.lower() != course_host
        combined = f"{label} {context} {absolute_url}"
        links.append(
            DiscoveredLink(
                url=absolute_url,
                label=label[:500],
                context=context[:1200],
                is_external=is_external,
                is_crawl_candidate=(not is_external and bool(COURSE_LINK_RE.search(combined))),
                is_protected=bool(PROTECTED_RE.search(combined)),
            )
        )
    embeds: list[str] = []
    for iframe in soup.find_all("iframe", src=True):
        external_id = extract_youtube_video_id(iframe["src"])
        if external_id and external_id not in embeds:
            embeds.append(external_id)
    return ParsedCoursePage(
        title=page_title,
        course_code=code_match.group(0).upper().replace(" ", "") if code_match else None,
        year=year_match.group(1) if year_match else None,
        quarter=quarter_match.group(1).title() if quarter_match else None,
        instructors=instructors,
        ai_policy_text=ai_policy_text,
        ai_policy_url=ai_policy_url,
        # A public course page may merely link to Canvas. It is protected only
        # when the page itself presents an authentication gate.
        is_protected=bool(LOGIN_PAGE_RE.search(page_text)),
        links=links,
        youtube_embeds=embeds,
    )


class StanfordGenericImporter:
    """Bounded, public-only Stanford course importer.

    The crawler starts at one user-supplied course URL, follows only selected
    same-host course links, rate-limits requests, respects robots.txt, and
    records protected links instead of attempting to access them.
    """

    USER_AGENT = "PersonalAILearningOS/0.1 (local personal learning tool)"

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self._robots: dict[str, RobotFileParser | None] = {}

    def import_url(self, url: str, max_pages: int | None = None, max_depth: int | None = None) -> tuple[Course, dict]:
        if not is_stanford_url(url):
            raise StanfordImportError("Stanford imports accept only public http(s) .stanford.edu course URLs.")
        root_url = _normal_url(url)
        root_host = (urlparse(root_url).hostname or "").lower()
        max_pages = min(max_pages or self.settings.crawl_max_pages, 50)
        max_depth = min(max_depth if max_depth is not None else self.settings.crawl_max_depth, 3)
        fetched = 0
        errors: list[str] = []
        root_response = self._fetch(root_url)
        fetched += 1
        if root_response["status"] == "blocked":
            course = Course(
                name=Path(urlparse(root_url).path).name or "Protected Stanford course",
                official_course_url=root_url,
                source_type="stanford",
                import_status="protected",
            )
            self.db.add(course)
            self.db.flush()
            self.db.add(
                CourseSource(
                    course_id=course.id,
                    source_url=root_url,
                    source_type="stanford_course_page",
                    title=course.name,
                    detected_as_official=True,
                    protected_resource=True,
                    access_status="protected",
                    explanation="Requires Stanford authentication",
                )
            )
            self.db.flush()
            return course, {"pages_fetched": fetched, "protected": 1, "errors": []}
        if root_response["status"] != "ok":
            raise StanfordImportError(root_response["error"])

        parsed_root = parse_course_page(root_response["html"], root_url, root_host)
        course = Course(
            name=parsed_root.title,
            code=parsed_root.course_code,
            year=parsed_root.year,
            quarter=parsed_root.quarter,
            version=" ".join(item for item in [parsed_root.quarter, parsed_root.year] if item) or None,
            official_course_url=root_url,
            source_type="stanford",
            instructors=parsed_root.instructors,
            course_ai_policy=parsed_root.ai_policy_text,
            course_ai_policy_url=parsed_root.ai_policy_url,
            import_status="importing",
        )
        self.db.add(course)
        self.db.flush()
        module = Module(course_id=course.id, title="Imported course materials", order_index=1)
        self.db.add(module)
        self.db.flush()
        visited: set[str] = set()
        queue: deque[tuple[str, int, str | None]] = deque([(root_url, 0, root_response["html"])])
        protected_count = 0
        while queue and len(visited) < max_pages:
            page_url, depth, cached_html = queue.popleft()
            if page_url in visited:
                continue
            visited.add(page_url)
            if cached_html is None:
                result = self._fetch(page_url)
                fetched += 1
                if result["status"] == "blocked":
                    protected_count += 1
                    self._record_protected_page(course, page_url)
                    continue
                if result["status"] != "ok":
                    errors.append(f"{page_url}: {result['error']}")
                    continue
                html = result["html"]
            else:
                html = cached_html
            parsed = parse_course_page(html, page_url, root_host)
            if parsed.is_protected:
                protected_count += 1
                self._record_protected_page(course, page_url)
                continue
            self._ingest_page(course, module, page_url, parsed)
            if depth < max_depth:
                for link in parsed.links:
                    if link.is_crawl_candidate and not link.is_protected and link.url not in visited:
                        queue.append((link.url, depth + 1, None))
            if queue and len(visited) < max_pages:
                time.sleep(0.35)
        course.import_status = "partial" if errors else "ready"
        self.db.flush()
        # New rows are created through foreign keys while the import is running.
        # Expire any early relationship snapshots before serializing the course.
        self.db.expire(course, ["lectures", "resources", "assignments", "sources"])
        return course, {
            "pages_fetched": fetched,
            "pages_visited": len(visited),
            "protected": protected_count,
            "lectures": self.db.scalar(select(func.count()).select_from(Lecture).where(Lecture.course_id == course.id)),
            "resources": self.db.scalar(select(func.count()).select_from(Resource).where(Resource.course_id == course.id)),
            "assignments": self.db.scalar(select(func.count()).select_from(Assignment).where(Assignment.course_id == course.id)),
            "errors": errors,
        }

    def _fetch(self, url: str) -> dict:
        parsed = urlparse(url)
        robot_status = self._robots_allows(url)
        if robot_status is False:
            return {"status": "blocked", "error": "Blocked by robots.txt"}
        try:
            response = httpx.get(
                url,
                headers={"User-Agent": self.USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
                follow_redirects=True,
                timeout=20.0,
            )
        except httpx.HTTPError as exc:
            return {"status": "error", "error": f"Network error: {exc}"}
        if response.status_code in {401, 403}:
            return {"status": "blocked", "error": "Requires Stanford authentication"}
        if response.status_code >= 400:
            return {"status": "error", "error": f"HTTP {response.status_code}"}
        if "text/html" not in response.headers.get("content-type", "").lower():
            return {"status": "error", "error": "The course URL did not return HTML."}
        html = response.text
        if LOGIN_PAGE_RE.search(_clean_text(BeautifulSoup(html, "html.parser").get_text(" ", strip=True))):
            return {"status": "blocked", "error": "Requires Stanford authentication"}
        return {"status": "ok", "html": html}

    def _robots_allows(self, url: str) -> bool | None:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in self._robots:
            try:
                response = httpx.get(f"{origin}/robots.txt", headers={"User-Agent": self.USER_AGENT}, timeout=10.0)
                if response.status_code == 404:
                    self._robots[origin] = None
                elif response.status_code < 400:
                    robot = RobotFileParser()
                    robot.parse(response.text.splitlines())
                    self._robots[origin] = robot
                else:
                    # Do not crawl unknown crawl policy beyond user-provided root.
                    self._robots[origin] = RobotFileParser()
                    self._robots[origin].parse(["User-agent: *", "Disallow: /"])
            except httpx.HTTPError:
                return None
        robot = self._robots[origin]
        return robot.can_fetch(self.USER_AGENT, url) if robot is not None else True

    def _record_protected_page(self, course: Course, page_url: str) -> None:
        self.db.add(
            CourseSource(
                course_id=course.id,
                source_url=page_url,
                source_type="stanford_course_page",
                title="Protected course resource",
                detected_as_official=True,
                protected_resource=True,
                access_status="protected",
                explanation="Requires Stanford authentication",
            )
        )

    def _ingest_page(self, course: Course, module: Module, page_url: str, parsed: ParsedCoursePage) -> None:
        self.db.add(
            CourseSource(
                course_id=course.id,
                source_url=page_url,
                source_type="stanford_course_page",
                title=parsed.title,
                detected_as_official=True,
                protected_resource=False,
                access_status="public",
            )
        )
        if parsed.ai_policy_text and not course.course_ai_policy:
            course.course_ai_policy = parsed.ai_policy_text
            course.course_ai_policy_url = parsed.ai_policy_url

        for link in parsed.links:
            self._ingest_link(course, module, page_url, link)
        for video_id in parsed.youtube_embeds:
            if self.db.scalar(select(Video).where(Video.external_id == video_id, Video.provider == "youtube")):
                continue
            lecture = Lecture(
                course_id=course.id,
                module_id=module.id,
                title=f"YouTube lecture {self._next_lecture_order(course)}",
                order_index=self._next_lecture_order(course),
                source_url=f"https://www.youtube.com/watch?v={video_id}",
            )
            self.db.add(lecture)
            self.db.flush()
            self.db.add(
                Video(
                    lecture_id=lecture.id,
                    provider="youtube",
                    external_id=video_id,
                    embed_url=f"https://www.youtube.com/embed/{video_id}?enablejsapi=1&origin=http://localhost:5173",
                )
            )

    def _ingest_link(self, course: Course, module: Module, page_url: str, link: DiscoveredLink) -> None:
        combined = f"{link.label} {link.context} {link.url}"
        decision = OfficialAssignmentResolver.resolve(
            label=link.label, url=link.url, source_page_url=page_url, source_page_is_official=True
        )
        youtube_id = extract_youtube_video_id(link.url)
        if youtube_id and LECTURE_RE.search(combined):
            if not self.db.scalar(select(Video).where(Video.external_id == youtube_id, Video.provider == "youtube")):
                lecture = Lecture(
                    course_id=course.id,
                    module_id=module.id,
                    title=link.label,
                    description=link.context,
                    order_index=self._next_lecture_order(course),
                    source_url=link.url,
                )
                self.db.add(lecture)
                self.db.flush()
                self.db.add(
                    Video(
                        lecture_id=lecture.id,
                        provider="youtube",
                        external_id=youtube_id,
                        embed_url=f"https://www.youtube.com/embed/{youtube_id}?enablejsapi=1&origin=http://localhost:5173",
                    )
                )
            return

        suffix = Path(urlparse(link.url).path).suffix.lower()
        resource_keyword = bool(COURSE_LINK_RE.search(combined)) or suffix in {".pdf", ".zip", ".ipynb", ".py"}
        if not resource_keyword:
            return
        resource = self.db.scalar(select(Resource).where(Resource.course_id == course.id, Resource.resource_url == link.url))
        if resource is None:
            resource_type = decision.resource_type
            if "slide" in combined.lower():
                resource_type = "slides"
            elif "note" in combined.lower():
                resource_type = "notes"
            elif "read" in combined.lower():
                resource_type = "reading"
            resource = Resource(
                course_id=course.id,
                title=link.label,
                resource_url=link.url,
                source_page_url=page_url,
                resource_type=resource_type,
                detected_as_official=True,
                protected_resource=link.is_protected,
                access_status="protected" if link.is_protected else "public",
                provenance={
                    "course_name": course.name,
                    "course_version": course.version,
                    "year": course.year,
                    "quarter": course.quarter,
                    "official_course_url": course.official_course_url,
                    "source_page_url": page_url,
                    "resource_url": link.url,
                    "resource_type": resource_type,
                    "title": link.label,
                    "detected_as_official": True,
                    "downloaded_at": None,
                    "local_path": None,
                    "checksum": None,
                    "access_status": "protected" if link.is_protected else "public",
                    "classification_rationale": decision.rationale,
                    "official_external_resource": link.is_external,
                },
            )
            self.db.add(resource)
            self.db.flush()
        if decision.is_assignment:
            assignment = self._find_or_create_assignment(course, link, decision, page_url)
            if not self.db.scalar(
                select(AssignmentResource).where(
                    AssignmentResource.assignment_id == assignment.id, AssignmentResource.resource_id == resource.id
                )
            ):
                self.db.add(AssignmentResource(assignment_id=assignment.id, resource_id=resource.id, role="original"))

    def _find_or_create_assignment(
        self, course: Course, link: DiscoveredLink, decision, source_page_url: str
    ) -> Assignment:
        # Several PDF/starter-code links may describe one assignment. Prefer a
        # stable key derived from its explicit textual label, then make only a
        # collision-safe fallback for unrelated resources.
        assignment_count = self.db.scalar(
            select(func.count()).select_from(Assignment).where(Assignment.course_id == course.id)
        ) or 0
        candidate = assignment_key(link.label, assignment_count + 1)
        assignment = self.db.scalar(select(Assignment).where(Assignment.course_id == course.id, Assignment.key == candidate))
        if assignment is not None:
            return assignment
        assignment = Assignment(
            course_id=course.id,
            title=link.label,
            key=candidate,
            order_index=assignment_count + 1,
            description=link.context,
            official_url=link.url,
            source_page_url=source_page_url,
            official=decision.official,
            protected_resource=decision.protected_resource,
            status="not_started",
        )
        self.db.add(assignment)
        self.db.flush()
        return assignment

    def _next_lecture_order(self, course: Course) -> int:
        maximum = self.db.scalar(select(func.max(Lecture.order_index)).where(Lecture.course_id == course.id))
        return (maximum or 0) + 1
