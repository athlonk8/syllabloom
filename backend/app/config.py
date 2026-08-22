from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


def environment_value(name: str, default: str | None = None) -> str | None:
    """Read the current Syllabloom environment name, then the legacy alias."""

    return os.getenv(f"SYLLABLOOM_{name}") or os.getenv(f"PALO_{name}") or default


class Settings:
    """Local-only runtime configuration.

    Secrets may be stored in the local SQLite AppSetting table through the UI,
    or supplied through environment variables. Runtime data never belongs in Git.
    """

    def __init__(self) -> None:
        self.app_root = Path(__file__).resolve().parents[2]
        load_dotenv(self.app_root / ".env", override=False)
        self.data_dir = Path(environment_value("DATA_DIR", str(self.app_root / "data"))).expanduser().resolve()
        self.learning_vault = self.data_dir / "LearningVault"
        current_database = self.data_dir / "syllabloom.db"
        legacy_database = self.data_dir / "learning-os.db"
        default_database = legacy_database if legacy_database.is_file() and not current_database.exists() else current_database
        self.database_url = environment_value(
            "DATABASE_URL", f"sqlite:///{default_database.as_posix()}"
        )
        self.watch_completion_threshold = float(environment_value("WATCH_COMPLETION_THRESHOLD", "0.85"))
        self.crawl_max_pages = int(environment_value("CRAWL_MAX_PAGES", "18"))
        self.crawl_max_depth = int(environment_value("CRAWL_MAX_DEPTH", "1"))
        self.frontend_origins = [
            origin.strip()
            for origin in environment_value(
                "FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
            ).split(",")
            if origin.strip()
        ]

    def ensure_local_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.learning_vault.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
