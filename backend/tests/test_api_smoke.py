from __future__ import annotations

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import Assignment


def test_manual_course_watch_progress_survives_api_round_trip() -> None:
    with TestClient(app) as client:
        imported = client.post("/api/imports/manual-youtube", json={"name": "API test course", "videos": [{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "title": "Lecture", "duration_seconds": 100}]} )
        assert imported.status_code == 201, imported.text
        course = imported.json()["course"]
        video_id = course["lectures"][0]["video"]["id"]
        watched = client.post("/api/watch/segments", json={"video_id": video_id, "start_seconds": 0, "end_seconds": 90, "playback_rate": 1, "duration_seconds": 100})
        assert watched.status_code == 201, watched.text
        restored = client.get(f"/api/courses/{course['id']}")
        assert restored.status_code == 200
        assert restored.json()["progress"]["lectures"][0]["completed"] is True


def test_learner_can_attach_a_bilibili_source_to_a_lecture() -> None:
    with TestClient(app) as client:
        imported = client.post(
            "/api/imports/manual-youtube",
            json={
                "name": "Source switch test course",
                "videos": [{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "title": "Lecture"}],
            },
        )
        assert imported.status_code == 201, imported.text
        lecture_id = imported.json()["course"]["lectures"][0]["id"]

        attached = client.put(
            f"/api/lectures/{lecture_id}/bilibili-source",
            json={"url": "https://www.bilibili.com/video/BV1Ect2zjEHR/"},
        )
        assert attached.status_code == 200, attached.text
        lecture = attached.json()["course"]["lectures"][0]
        assert lecture["source_url"] == "https://www.bilibili.com/video/BV1Ect2zjEHR/"
        assert lecture["video"]["provider"] == "bilibili"
        assert lecture["video"]["external_id"] == "BV1Ect2zjEHR"
        assert "player.bilibili.com" in lecture["video"]["embed_url"]
        assert any(source["source_type"] == "bilibili_learner_selected" for source in attached.json()["course"]["sources"])


def test_explicit_obsidian_settings_route_is_not_captured_by_generic_setting(tmp_path) -> None:
    with TestClient(app) as client:
        response = client.put(
            "/api/settings/obsidian",
            json={"vault_path": str(tmp_path / "ObsidianVault"), "create_if_missing": True},
        )
        assert response.status_code == 200, response.text
        assert response.json()["enabled"] is True


def test_ai_provider_settings_mask_secret_values() -> None:
    with TestClient(app) as client:
        response = client.put(
            "/api/settings/ai-provider",
            json={
                "provider": "openai_compatible",
                "base_url": "http://localhost:11434/v1",
                "model": "qwen2.5:7b",
                "api_key": "not-returned",
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["api_key_configured"] is True
        assert "not-returned" not in response.text


def test_assignment_workbench_saves_a_local_answer_then_creates_an_immutable_snapshot() -> None:
    with TestClient(app) as client:
        imported = client.post(
            "/api/imports/manual-youtube",
            json={
                "name": "Assignment workbench test course",
                "videos": [{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "title": "Lecture"}],
            },
        )
        assert imported.status_code == 201, imported.text
        course_id = imported.json()["course"]["id"]
        with SessionLocal() as db:
            assignment = Assignment(
                course_id=course_id,
                title="Explain the invariant",
                key="A1",
                description="Give a concise argument for the loop invariant.",
                official=True,
            )
            db.add(assignment)
            db.commit()
            assignment_id = assignment.id

        opened = client.get(f"/api/assignments/{assignment_id}/workspace")
        assert opened.status_code == 200, opened.text
        assert opened.json()["storage"] in {"local", "obsidian"}
        assert "My Answer" in opened.json()["answer"]

        answer = "# My Answer\n\nThe invariant holds before and after every iteration.\n"
        saved = client.put(f"/api/assignments/{assignment_id}/workspace", json={"content": answer})
        assert saved.status_code == 200, saved.text
        assert saved.json()["answer"] == answer
        assert saved.json()["assignment"]["status"] == "in_progress"

        snapshot = client.post(f"/api/assignments/{assignment_id}/submissions")
        assert snapshot.status_code == 201, snapshot.text
        assert snapshot.json()["version"] == 1
        assert snapshot.json()["grades"] == []

        history = client.get(f"/api/assignments/{assignment_id}/history")
        assert history.status_code == 200, history.text
        assert len(history.json()["submissions"]) == 1
        assert history.json()["submissions"][0]["version"] == 1
