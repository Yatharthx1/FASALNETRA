from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from backend.app.api.v1.router import api_router
from backend.app.core.config import settings
from backend.app.db import models  # noqa: F401  (register tables)
from backend.app.db.database import Base, SessionLocal, engine
from backend.app.db.session import init_db
from backend.app.services import didi, fields


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Demo app: create tables on startup. A real deployment would use migrations.
    init_db()   # IVR tables (farmers, ivr_sessions), sync engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as db:
        await fields.seed_demo(db)
        await didi.seed_demo_tickets(db)
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix=settings.api_v1_prefix)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")

    # Mount audio files directory if present so Twilio can fetch pre-recorded MP3s
    audio_path = Path("frontend/public/audio")
    if audio_path.exists():
        app.mount("/audio", StaticFiles(directory=str(audio_path)), name="audio")

    @app.get("/", tags=["root"])
    async def root() -> dict[str, str]:
        return {"name": settings.app_name, "status": "running", "docs": "/docs"}

    @app.get("/call", response_class=HTMLResponse, tags=["ivr"])
    async def call_console() -> HTMLResponse:
        """Web interface to trigger outbound calls and monitor live IVR answers."""
        template_path = Path("backend/app/templates/call_console.html")
        if template_path.exists():
            return HTMLResponse(content=template_path.read_text(encoding="utf-8"))
        return HTMLResponse(content="<h1>Call console template missing</h1>")

    return app


app = create_app()
