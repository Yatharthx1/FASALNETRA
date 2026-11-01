"""Rehearsal server: the full app with phone calls and WhatsApp simulated, on its own database.

    python scripts/run_sim.py            # http://127.0.0.1:8001, /call = web keypad, /didi, /walk links on /

Vision still uses the real provider from .env (OpenAI), so the photo check is the same as on demo day.
"""
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DB = Path(tempfile.gettempdir()) / "fasalnetra-sim.db"

os.environ.update({
    "DATABASE_URL": f"sqlite+aiosqlite:///{DB.as_posix()}",
    "TWILIO_ACCOUNT_SID": "", "TWILIO_AUTH_TOKEN": "", "TWILIO_PHONE_NUMBER": "",   # no real calls
    "SMS_PROVIDER": "",                                                               # no real WhatsApp
    "PUBLIC_BASE_URL": "http://127.0.0.1:8001",
})

if __name__ == "__main__":
    import uvicorn

    sys.path.insert(0, str(REPO))
    os.chdir(REPO)
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=int(os.environ.get("PORT", "8001")))
