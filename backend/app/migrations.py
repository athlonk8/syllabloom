from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from .config import get_settings
from .models import Base


def _alembic_config() -> Config:
    return Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))


def upgrade_database() -> str:
    """Apply migrations, safely adopting a complete pre-Alembic local schema.

    Early local builds used SQLAlchemy create_all during application startup.
    If every current application table is present but alembic_version is absent,
    the schema is known to be the initial revision and can be stamped. A partial
    database is deliberately not stamped: Alembic should surface that problem.
    """

    settings = get_settings()
    settings.ensure_local_dirs()
    engine = create_engine(
        settings.database_url,
        connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
        future=True,
    )
    try:
        tables = set(inspect(engine).get_table_names())
        version_rows: list[str] = []
        if "alembic_version" in tables:
            with engine.connect() as connection:
                version_rows = [str(value) for value in connection.execute(text("SELECT version_num FROM alembic_version")).scalars() if value]
    finally:
        engine.dispose()

    config = _alembic_config()
    expected_tables = set(Base.metadata.tables)
    if expected_tables <= tables and not version_rows:
        command.stamp(config, "head")
        return "stamped_legacy_schema"

    command.upgrade(config, "head")
    return "upgraded"


if __name__ == "__main__":
    print(upgrade_database())
