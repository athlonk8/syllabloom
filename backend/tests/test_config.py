from __future__ import annotations

from app.config import get_settings


def test_syllabloom_environment_prefix_takes_precedence(tmp_path, monkeypatch) -> None:
    legacy_path = tmp_path / "legacy"
    current_path = tmp_path / "current"
    monkeypatch.setenv("PALO_DATA_DIR", str(legacy_path))
    monkeypatch.setenv("SYLLABLOOM_DATA_DIR", str(current_path))
    get_settings.cache_clear()
    try:
        assert get_settings().data_dir == current_path.resolve()
    finally:
        get_settings.cache_clear()


def test_legacy_environment_prefix_remains_supported(tmp_path, monkeypatch) -> None:
    legacy_path = tmp_path / "legacy"
    monkeypatch.delenv("SYLLABLOOM_DATA_DIR", raising=False)
    monkeypatch.setenv("PALO_DATA_DIR", str(legacy_path))
    get_settings.cache_clear()
    try:
        assert get_settings().data_dir == legacy_path.resolve()
    finally:
        get_settings.cache_clear()


def test_legacy_database_filename_is_preserved_when_no_current_database_exists(tmp_path, monkeypatch) -> None:
    data_dir = tmp_path / "existing-data"
    data_dir.mkdir()
    legacy_database = data_dir / "learning-os.db"
    legacy_database.touch()
    monkeypatch.setenv("SYLLABLOOM_DATA_DIR", str(data_dir))
    get_settings.cache_clear()
    try:
        assert get_settings().database_url.endswith("/learning-os.db")
    finally:
        get_settings.cache_clear()
