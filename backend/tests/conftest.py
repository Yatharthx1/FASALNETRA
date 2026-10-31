import io
import os
import tempfile
from pathlib import Path

# Isolate every test run before the app reads its settings.
_TMP = Path(tempfile.mkdtemp(prefix="fasalnetra-test-"))
os.environ.update({
    "DATABASE_URL": f"sqlite+aiosqlite:///{(_TMP / 'test.db').as_posix()}",
    "UPLOAD_DIR": str(_TMP / "uploads"),
    "WAYPOINTS_DIR": str(_TMP / "waypoints"),
    "VISION_PROVIDER": "mock",
    "TWILIO_ACCOUNT_SID": "",          # never place real calls/SMS from tests, whatever .env says
    "TWILIO_AUTH_TOKEN": "",
    "TWILIO_PHONE_NUMBER": "",
    "DEMO_FARMER_PHONE": "+919876543210",
    "PUBLIC_BASE_URL": "http://test",
    "POSTGRES_URL": "",
    "DEMO_MODE": "true",
})

import numpy as np  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from PIL import Image  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
HAS_SATELLITE = (REPO / "data" / "processed" / "demo" / "s2_stack.npz").exists()
HAS_WEATHER = any((REPO / "data" / "raw" / "weather").glob("archive_*.json"))

needs_data = pytest.mark.skipif(not (HAS_SATELLITE and HAS_WEATHER),
                                reason="run scripts/fetch_field_data.py and the backtest once to cache data")


def jpeg(sharp: bool = True) -> bytes:
    arr = (np.random.default_rng(1).random((400, 400, 3)) * 255).astype("uint8") if sharp \
        else np.full((400, 400, 3), 20, dtype="uint8")
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, "JPEG")
    return buf.getvalue()


@pytest_asyncio.fixture
async def client():
    from backend.app.db.database import Base, engine
    from backend.app import main
    from backend.app.main import create_app, lifespan

    main._ready = False   # tables are dropped below, so setup must run again

    from backend.app.db import session as ivr_db

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    ivr_db.Base.metadata.drop_all(bind=ivr_db.engine)   # Yatharth's IVR tables (farmers, ivr_sessions)
    app = create_app()
    async with lifespan(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
