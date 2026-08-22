from __future__ import annotations

from contextlib import asynccontextmanager
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .database import init_database
from .routers.api import router

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_database()
    yield


app = FastAPI(
    title="Personal AI Learning OS",
    version="0.1.0",
    description="A local-first learning workspace for publicly accessible course materials.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


def _frontend_dist() -> Path:
    project_root = Path(__file__).resolve().parents[2]
    return Path(os.getenv("PALO_FRONTEND_DIST", project_root / "frontend" / "dist")).expanduser().resolve()


frontend_dist = _frontend_dist()
if frontend_dist.is_dir():
    # Add this after the API router so /api remains handled by FastAPI.
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
