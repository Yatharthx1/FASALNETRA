import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from backend.app.api.v1.router import api_router
from backend.app.core.config import REPO_ROOT, settings
from backend.app.db import models  # noqa: F401  (register tables)
from backend.app.db.database import Base, SessionLocal, engine
from backend.app.db.session import init_db
from backend.app.services import didi, fields
from backend.app.services.communications import ivr_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Demo app: create tables on startup. A real deployment would use migrations.
    init_db()   # IVR tables (farmers, ivr_sessions), sync engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as db:
        await fields.seed_demo(db)
        await didi.seed_demo_tickets(db)
    # PRD: the demo farmer is pre-registered, so his missed call goes straight to "report a problem"
    await asyncio.to_thread(ivr_service.ensure_registered, settings.demo_farmer_phone, settings.demo_farmer_name, "Rampura")
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
    audio_path = REPO_ROOT / "frontend" / "public" / "audio"
    if audio_path.exists():
        app.mount("/audio", StaticFiles(directory=str(audio_path)), name="audio")

    @app.get("/call", response_class=HTMLResponse, tags=["ivr"])
    async def call_console() -> HTMLResponse:
        """Web interface to trigger outbound calls and monitor live IVR answers."""
        template_path = REPO_ROOT / "backend" / "app" / "templates" / "call_console.html"
        if template_path.exists():
            return HTMLResponse(content=template_path.read_text(encoding="utf-8"))
        return HTMLResponse(content="<h1>Call console template missing</h1>")

    # Built frontend (npm run build) served from the API's own origin, so one HTTPS tunnel gives the phone
    # the Twilio webhooks, the SMS-link page (/walk, camera needs HTTPS) and Drone Didi's app (/didi).
    dist = REPO_ROOT / "frontend" / "dist"

    @app.get("/{full_path:path}", include_in_schema=False, response_model=None)
    async def frontend(full_path: str) -> FileResponse | dict[str, str]:
        if full_path.startswith(("api/", "uploads/", "audio/")):
            raise HTTPException(404, "Not found")
        if not (dist / "index.html").exists():
            if full_path:
                raise HTTPException(404, "Not found")
            return {"name": settings.app_name, "status": "running", "docs": "/docs"}
        asset = (dist / full_path).resolve()
        if full_path and asset.is_file() and asset.is_relative_to(dist.resolve()):
            return FileResponse(asset)
        return FileResponse(dist / "index.html")   # SPA routes: /, /walk, /didi

    return app


app = create_app()
