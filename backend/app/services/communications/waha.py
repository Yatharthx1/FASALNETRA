"""WAHA (open-source WhatsApp HTTP API, https://waha.devlike.pro) running next to the app on our own server.

A spare WhatsApp number is linked once by QR (GET /api/v1/wa/qr/<secret>); after that the camera link and
Didi's alert go out from it to any number, free, with no trial lock. WAHA is never exposed publicly: the app
reaches it on the private docker network."""
import logging

import httpx

from backend.app.core.config import settings

log = logging.getLogger(__name__)
TIMEOUT_S = 25


class WahaError(RuntimeError):
    pass


def enabled() -> bool:
    return bool(settings.waha_url)


def _req(method: str, path: str, json: dict | None = None, accept: str = "application/json") -> httpx.Response:
    try:
        resp = httpx.request(method, f"{settings.waha_url.rstrip('/')}{path}", json=json, timeout=TIMEOUT_S,
                             headers={"X-Api-Key": settings.waha_api_key, "Accept": accept})
    except httpx.HTTPError as exc:
        raise WahaError(str(exc)) from exc
    if resp.status_code >= 400:
        raise WahaError(f"{resp.status_code}: {resp.text[:300]}")
    return resp


def send_text(phone: str, text: str) -> str:
    out = _req("POST", "/api/sendText", {"session": settings.waha_session,
                                          "chatId": f"{phone.lstrip('+')}@c.us", "text": text}).json()
    msg_id = out.get("id")
    return (msg_id.get("_serialized") if isinstance(msg_id, dict) else msg_id) or "waha"


def session() -> dict:
    """The session, created and started when missing (status: STARTING, SCAN_QR_CODE, WORKING, FAILED ...)."""
    try:
        s = _req("GET", f"/api/sessions/{settings.waha_session}").json()
    except WahaError as exc:
        if not str(exc).startswith("404"):
            raise
        return _req("POST", "/api/sessions", {"name": settings.waha_session}).json()
    if s.get("status") in ("STOPPED", "FAILED"):
        _req("POST", f"/api/sessions/{settings.waha_session}/start")
        s = _req("GET", f"/api/sessions/{settings.waha_session}").json()
    return s


def qr_png() -> bytes:
    return _req("GET", f"/api/{settings.waha_session}/auth/qr?format=image", accept="image/png").content


def me() -> dict | None:
    s = session()
    return s.get("me")
