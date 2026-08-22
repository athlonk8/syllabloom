from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


class Settings:
    """Local-only runtime configuration.

    Secrets may be stored in the local SQLite AppSetting table through the UI,
    or supplied through environment variables. Runtime data never belongs in Git.
    """

    def __init__(self) -> None:
        self.app_root = Path(__file__).resolve().parents[2]
        load_dotenv(self.app_root / ".env", override=False)
        self.data_dir = Path(os.getenv("PALO_DATA_DIR", self.app_root / "data")).expanduser().resolve()
        self.learning_vault = self.data_dir / "LearningVault"
        self.database_url = os.getenv(
            "PALO_DATABASE_URL", f"sqlite:///{(self.data_dir / 'learning-os.db').as_posix()}"
        )
        self.watch_completion_threshold = float(os.getenv("PALO_WATCH_COMPLETION_THRESHOLD", "0.85"))
        self.crawl_max_pages = int(os.getenv("PALO_CRAWL_MAX_PAGES", "18"))
        self.crawl_max_depth = int(os.getenv("PALO_CRAWL_MAX_DEPTH", "1"))
        self.frontend_origins = [
            origin.strip()
            for origin in os.getenv("PALO_FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
            if origin.strip()
        ]

    def ensure_local_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.learning_vault.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
