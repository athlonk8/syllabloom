from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

import httpx
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Assignment, AssignmentResource, Course, Resource
from .utils import path_is_within, safe_filename, slugify

ASSIGNMENT_RE = re.compile(
    r"\b(?:assignment(?:\s*\d+)?|homework(?:\s*\d+)?|\bhw\s*\d*|problem\s*set|\bpset\s*\d*|exercise(?:s)?|starter\s*code|project)\b",
    re.IGNORECASE,
)
PROTECTED_RE = re.compile(r"(?:canvas|gradescope|login|sso|authenticate|protected)", re.IGNORECASE)


@dataclass(frozen=True)
class AssignmentDecision:
    is_assignment: bool
    title: str
    resource_type: str
    protected_resource: bool
    official: bool
    rationale: str


class OfficialAssignmentResolver:
    """Classifies only resources linked from an already-public official page.

    It never upgrades an arbitrary GitHub URL to "official" on its own. The
    Stanford importer's source_page_url is the provenance evidence required for
    an external resource to be treated as official course material.
    """

    @staticmethod
    def resolve(*, label: str, url: str, source_page_url: str, source_page_is_official: bool) -> AssignmentDecision:
        text = f"{label} {url}".strip()
        protected = bool(PROTECTED_RE.search(text))
        is_assignment = bool(ASSIGNMENT_RE.search(text))
        suffix = Path(urlparse(url).path).suffix.lower()
        if "github.com" in (urlparse(url).hostname or "").lower():
            resource_type = "github_repository"
        elif suffix == ".pdf":
            resource_type = "pdf"
        elif suffix == ".zip":
            resource_type = "zip"
        elif suffix in {".ipynb"}:
            resource_type = "notebook"
        elif suffix in {".py", ".java", ".cpp", ".c", ".js", ".ts"}:
            resource_type = "starter_code"
        else:
            resource_type = "html"
        official = source_page_is_official
        rationale = (
            "Direct link on a public official course page."
            if official
            else "Not linked from a verified official course page."
        )
        return AssignmentDecision(is_assignment, label or "Official assignment resource", resource_type, protected, official, rationale)


def assignment_key(label: str, index: int) -> str:
    match = re.search(r"\b(?:assignment|homework|hw|pset|problem\s*set)\s*([a-z0-9._-]+)", label, re.I)
    if match:
        return f"A{match.group(1).upper()}".replace(" ", "")[:90]
    return f"A{index}"


class OfficialAssignmentDownloader:
    MAX_DOWNLOAD_BYTES = 250 * 1024 * 1024

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()

    def download(self, assignment: Assignment) -> dict:
        if not assignment.official:
            raise ValueError("Only provenance-verified official assignment resources can be downloaded.")
        if assignment.protected_resource:
            raise PermissionError("Requires Stanford authentication. This resource was recorded but will not be accessed.")
        course = assignment.course
        root = self._assignment_root(course, assignment)
        original = root / "original"
        original.mkdir(parents=True, exist_ok=True)
        assignment.local_root = str(root)
        downloaded: list[dict] = []
        skipped: list[dict] = []
        for link in assignment.resources:
            resource = link.resource
            if resource.protected_resource or resource.access_status != "public":
                skipped.append({"resource_id": resource.id, "reason": "Requires Stanford authentication"})
                continue
            try:
                downloaded.append(self._download_resource(resource, original, course, assignment))
            except PermissionError as exc:
                resource.protected_resource = True
                resource.access_status = "protected"
                skipped.append({"resource_id": resource.id, "reason": str(exc)})
            except Exception as exc:  # Preserve the DB record and surface one resource failure without data loss.
                skipped.append({"resource_id": resource.id, "reason": str(exc)})
        self._write_metadata(course, assignment, root)
        self.db.flush()
        return {"assignment_id": assignment.id, "root": str(root), "downloaded": downloaded, "skipped": skipped}

    def _assignment_root(self, course: Course, assignment: Assignment) -> Path:
        course_name = slugify(course.code or course.name, "course")
        version = slugify(course.version or "current", "current")
        root = (self.settings.learning_vault / f"{course_name}_{version}" / "assignments" / slugify(assignment.key)).resolve()
        if not path_is_within(root, self.settings.learning_vault):
            raise RuntimeError("Refusing to create an assignment path outside LearningVault.")
        return root

    def _download_resource(self, resource: Resource, original: Path, course: Course, assignment: Assignment) -> dict:
        parsed = urlparse(resource.resource_url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("Only HTTP(S) public course resources can be downloaded.")
        if parsed.hostname and parsed.hostname.lower() == "github.com" and len([p for p in parsed.path.split("/") if p]) >= 2:
            return self._clone_github_resource(resource, original)

        with httpx.stream(
            "GET",
            resource.resource_url,
            headers={"User-Agent": "PersonalAILearningOS/0.1 (local personal learning tool)"},
            follow_redirects=True,
            timeout=45.0,
        ) as response:
            if response.status_code in {401, 403}:
                raise PermissionError("Requires Stanford authentication")
            if response.status_code >= 400:
                raise RuntimeError(f"Download failed with HTTP {response.status_code}")
            content_length = response.headers.get("content-length")
            if content_length and int(content_length) > self.MAX_DOWNLOAD_BYTES:
                raise RuntimeError("Resource exceeds the 250 MB local download limit.")
            filename = self._filename(resource.resource_url, response.headers.get("content-disposition"), resource.title)
            destination = (original / filename).resolve()
            if not path_is_within(destination, original):
                raise RuntimeError("Refusing an unsafe resource filename.")
            if destination.exists():
                return {"resource_id": resource.id, "path": str(destination), "status": "already_present"}
            digest = hashlib.sha256()
            total = 0
            with destination.open("xb") as stream:
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > self.MAX_DOWNLOAD_BYTES:
                        destination.unlink(missing_ok=True)
                        raise RuntimeError("Resource exceeded the 250 MB local download limit while downloading.")
                    stream.write(chunk)
                    digest.update(chunk)
        resource.local_path = str(destination)
        resource.checksum = digest.hexdigest()
        resource.downloaded_at = datetime.now(timezone.utc)
        resource.provenance = self._provenance(resource, course, assignment)
        return {"resource_id": resource.id, "path": str(destination), "bytes": total, "status": "downloaded"}

    def _clone_github_resource(self, resource: Resource, original: Path) -> dict:
        parsed = urlparse(resource.resource_url)
        parts = [part for part in parsed.path.split("/") if part]
        owner, repo = parts[0], parts[1].removesuffix(".git")
        repository_url = f"https://github.com/{owner}/{repo}.git"
        destination = (original / f"repo-{slugify(owner)}-{slugify(repo)}").resolve()
        if not path_is_within(destination, original):
            raise RuntimeError("Refusing an unsafe GitHub destination.")
        if destination.exists():
            return {"resource_id": resource.id, "path": str(destination), "status": "already_present"}
        result = subprocess.run(
            ["git", "clone", "--depth", "1", "--no-tags", repository_url, str(destination)],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Shallow GitHub clone failed: {result.stderr[-500:]}")
        commit = subprocess.run(
            ["git", "-C", str(destination), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10, check=False
        ).stdout.strip()
        resource.local_path = str(destination)
        resource.checksum = commit or None
        resource.downloaded_at = datetime.now(timezone.utc)
        resource.provenance = {
            **resource.provenance,
            "repository_url": repository_url,
            "commit_hash": commit,
            "downloaded_at": resource.downloaded_at.isoformat(),
            "local_path": str(destination),
        }
        return {"resource_id": resource.id, "path": str(destination), "commit_hash": commit, "status": "cloned"}

    @staticmethod
    def _filename(url: str, content_disposition: str | None, title: str) -> str:
        if content_disposition:
            match = re.search(r"filename\*?=(?:UTF-8''|\")?([^;\"]+)", content_disposition, re.I)
            if match:
                return safe_filename(unquote(match.group(1)))
        name = Path(urlparse(url).path).name
        if name:
            return safe_filename(unquote(name))
        return f"{safe_filename(title)}.bin"

    def _provenance(self, resource: Resource, course: Course, assignment: Assignment) -> dict:
        return {
            "course_name": course.name,
            "course_version": course.version,
            "year": course.year,
            "quarter": course.quarter,
            "official_course_url": course.official_course_url,
            "source_page_url": resource.source_page_url,
            "resource_url": resource.resource_url,
            "resource_type": resource.resource_type,
            "title": resource.title,
            "detected_as_official": resource.detected_as_official,
            "downloaded_at": resource.downloaded_at.isoformat() if resource.downloaded_at else None,
            "local_path": resource.local_path,
            "checksum": resource.checksum,
            "access_status": resource.access_status,
            "assignment_key": assignment.key,
        }

    def _write_metadata(self, course: Course, assignment: Assignment, root: Path) -> None:
        metadata_path = root / "metadata.json"
        if metadata_path.exists():
            return  # Never overwrite original local metadata without explicit future support.
        metadata = {
            "course": course.name,
            "course_url": course.official_course_url,
            "assignment": assignment.title,
            "assignment_key": assignment.key,
            "official": assignment.official,
            "source_page_url": assignment.source_page_url,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "resources": [link.resource.provenance for link in assignment.resources],
        }
        metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
