from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app.config import get_settings
from app.migrations import upgrade_database
from app.models import Base


def test_alembic_creates_a_fresh_configured_data_directory(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SYLLABLOOM_DATA_DIR", str(tmp_path / "brand-new-data"))
    get_settings.cache_clear()
    try:
        config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
        command.upgrade(config, "head")
        engine = create_engine(get_settings().database_url)
        tables = set(inspect(engine).get_table_names())
        assert {"courses", "watch_segments", "assignments", "grading_runs", "certificates"} <= tables
    finally:
        get_settings.cache_clear()


def test_complete_legacy_schema_is_stamped_before_startup(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SYLLABLOOM_DATA_DIR", str(tmp_path / "legacy-data"))
    get_settings.cache_clear()
    try:
        get_settings().ensure_local_dirs()
        engine = create_engine(get_settings().database_url)
        Base.metadata.create_all(engine)
        assert "alembic_version" not in inspect(engine).get_table_names()

        assert upgrade_database() == "stamped_legacy_schema"
        assert "alembic_version" in inspect(engine).get_table_names()
    finally:
        get_settings.cache_clear()


def test_complete_schema_with_empty_alembic_table_is_stamped(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SYLLABLOOM_DATA_DIR", str(tmp_path / "interrupted-migration-data"))
    get_settings.cache_clear()
    try:
        get_settings().ensure_local_dirs()
        engine = create_engine(get_settings().database_url)
        Base.metadata.create_all(engine)
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))

        assert upgrade_database() == "stamped_legacy_schema"
        with engine.connect() as connection:
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    finally:
        get_settings.cache_clear()
