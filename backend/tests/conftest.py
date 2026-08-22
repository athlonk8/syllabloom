from __future__ import annotations

import os
import tempfile
from pathlib import Path

# Must be set before application modules are imported in test files.
TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="syllabloom-tests-"))
os.environ["SYLLABLOOM_DATA_DIR"] = str(TEST_DATA_DIR)

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
