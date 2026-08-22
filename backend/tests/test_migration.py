from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.config import get_settings


def test_alembic_creates_a_fresh_configured_data_directory(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PALO_DATA_DIR", str(tmp_path / "brand-new-data"))
    get_settings.cache_clear()
    try:
        config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
        command.upgrade(config, "head")
        engine = create_engine(get_settings().database_url)
        tables = set(inspect(engine).get_table_names())
        assert {"courses", "watch_segments", "assignments", "grading_runs", "certificates"} <= tables
    finally:
        get_settings.cache_clear()
