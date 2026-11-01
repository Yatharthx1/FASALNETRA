"""WhatsApp IVR over waapi.app: the same onboarding / result state machines as the Twilio call, in a WhatsApp chat.

The farmer WhatsApp-calls the FasalNetra number (or just writes "नमस्ते"): the call is answered with a short Hindi
greeting (waAPI call_policy), then every prompt arrives as a Hindi voice note plus text, and the farmer answers by
sending the number. The camera link, the live updates while the photo is checked, the result and the 1/2/3 menu
all come in the same chat. Each step runs through the web-keypad handlers in routes/ivr.py, so the logic is the
one the Twilio calls and the tests use.
"""
import asyncio
import logging
import re
import time
from collections import deque

from fastapi import APIRouter, HTTPException, Request, Response

from backend.app.core.config import settings
from backend.app.db.session import SessionLocal
from backend.app.models.farmer import Farmer
from backend.app.models.ivr_session import IVRSession
from backend.app.schemas.ivr import IVRRegisteredSimulateRequest, IVRSimulateRequest
from backend.app.services.communications import ivr_service, tts, waapi, waha
from backend.app.services.communications.registered_state_machine import get_registered_flow_config
from backend.app.api.v1.routes import ivr as ivr_routes

log = logging.getLogger(__name__)
router = APIRouter(prefix="/wa", tags=["whatsapp"])

LIVE_TICK_S = 4            # live hold: check the case this often while the farmer uses the camera link
LIVE_MAX_S = 8 * 60
CALL_DEDUPE_S = 90         # one call fires several call events (offer, ringing ...): start the chat once
START_WORDS = ("hi", "hello", "namaste", "नमस्ते", "start", "शुरू", "helo", "hii")
# Spoken call wording -> chat wording ("press" -> "send", no keypad, no speaker phone)
WA_WORDING = [("कीपैड पर दर्ज करें", "लिखकर भेजिए"), ("दबाइए", "भेजिए"), ("दबाएं", "भेजिए"),
              ("कॉल मत काटिए, फोन स्पीकर पर रखिए।", "यह चैट खुली रखिए।"), ("कॉल पर बने रहिए", "यह चैट खुली रखिए"),
              ("कॉल खत्म करने", "बातचीत खत्म करने"), ("इसी नंबर पर मिस्ड कॉल दीजिए", "इसी नंबर पर व्हाट्सऐप कॉल कीजिए")]
GREETING = ("नमस्ते! फसलनेत्र में आपका स्वागत है। हम आपसे अभी व्हाट्सऐप चैट में बात करेंगे। "
            "फोन काटकर फसलनेत्र की चैट खोलिए और वहां आई आवाज़ सुनिए।")

_seen: deque[str] = deque(maxlen=500)      # waAPI retries on timeout: handle each message once
_call_started: dict[str, float] = {}
_locks: dict[str, asyncio.Lock] = {}
_live: dict[str, asyncio.Task] = {}


def wa_wording(text: str) -> str:
    for old, new in WA_WORDING:
        text = text.replace(old, new)
    return text


def _say(phone: str, text: str) -> None:
    """One prompt: text first (instant), then the same words as a Hindi voice note."""
    text = wa_wording(text).strip()
    if not text:
        return
    try:
        waapi.send_text(phone, text)
        audio = tts.speech(text) if settings.whatsapp_voice_notes else None
        if audio:
            waapi.send_voice(phone, audio.read_bytes())
    except waapi.WaapiError as exc:
        log.warning("WhatsApp IVR to %s failed: %s", phone, exc)


async def say(phone: str, text: str) -> None:
    await asyncio.to_thread(_say, phone, text)


def _session(phone: str) -> IVRSession | None:
    with SessionLocal() as db:
        s = db.query(IVRSession).filter(IVRSession.phone == phone).first()
        if s is not None:
            db.expunge(s)
        return s


def _start_registered(phone: str) -> str:
    """A known farmer starts a chat: same choice as the Twilio callback (report a problem, or a pending result)."""
    with SessionLocal() as db:
        farmer = db.query(Farmer).filter(Farmer.phone == phone).first()
        session = db.query(IVRSession).filter(IVRSession.phone == phone).first()
        flow = ivr_service.inbound_flow(farmer, session)
        if session is None:
            session = IVRSession(call_sid=f"wa-{phone.lstrip('+')}", phone=phone)
            db.add(session)
        session.flow, session.current_step = flow, ivr_service.REGISTERED_FIRST_STEP[flow]
        session.reprompt_count, session.answers, session.status = 0, {}, "in_progress"
        db.commit()
        return flow


async def start(phone: str) -> None:
    """New conversation: onboarding for a new number, else the registered-farmer flow."""
    with SessionLocal() as db:
        farmer = db.query(Farmer).filter(Farmer.phone == phone).first()
        registered = farmer is not None and farmer.status == "registered"
        if not registered:
            r = await ivr_routes.ivr_simulate_step(IVRSimulateRequest(phone=phone, reset=True), db)
            await say(phone, r.prompt_text)
            return
    await asyncio.to_thread(_start_registered, phone)
    await registered_step(phone, None)


async def onboarding_step(phone: str, digits: str) -> None:
    with SessionLocal() as db:
        r = await ivr_routes.ivr_simulate_step(IVRSimulateRequest(phone=phone, digits=digits), db)
    if r.is_completed and "live hold" in r.message:     # field mapped, link sent in this chat: hold for the photo
        hold = get_registered_flow_config("report", "sms_dispatched")["prompt_text"]
        await say(phone, f"{r.prompt_text} {hold}")
        _ensure_live(phone)
    else:
        await say(phone, r.prompt_text)


async def registered_step(phone: str, digits: str | None) -> None:
    with SessionLocal() as db:
        r = await ivr_routes.ivr_simulate_registered(IVRRegisteredSimulateRequest(phone=phone, digits=digits), db)
    await say(phone, r.prompt_text)
    if r.current_step == "sms_dispatched" and not r.is_completed:
        _ensure_live(phone)


def _ensure_live(phone: str) -> None:
    task = _live.get(phone)
    if task is None or task.done():
        _live[phone] = asyncio.create_task(_live_hold(phone))


async def _live_hold(phone: str) -> None:
    """While the farmer uses the camera link: say each photo check, then the result and the 1/2/3 menu."""
    end = time.monotonic() + LIVE_MAX_S
    while time.monotonic() < end:
        await asyncio.sleep(LIVE_TICK_S)
        async with _lock(phone):
            s = await asyncio.to_thread(_session, phone)
            if s is None or s.current_step != "sms_dispatched" or s.status != "in_progress":
                return
            with SessionLocal() as db:
                r = await ivr_routes.ivr_simulate_registered(IVRRegisteredSimulateRequest(phone=phone), db)
            await say(phone, r.prompt_text)
            if r.current_step != "sms_dispatched" or r.is_completed:
                return


def _lock(phone: str) -> asyncio.Lock:
    return _locks.setdefault(phone, asyncio.Lock())


async def on_message(phone: str, body: str) -> None:
    async with _lock(phone):
        s = await asyncio.to_thread(_session, phone)
        digits = "".join(re.findall(r"\d", body))
        active = s is not None and s.status == "in_progress"
        if not active or (not digits and body.strip().lower() in START_WORDS):
            await start(phone)
        elif not digits:
            await say(phone, "कृपया जवाब में सिर्फ नंबर भेजिए, जैसे 1 या 2।")
        elif s.flow == "onboarding":
            await onboarding_step(phone, digits)
        elif s.current_step == "sms_dispatched":
            await say(phone, "फोटो का लिंक ऊपर भेजा है। उसे खोलकर बीमार पत्ते की फोटो लीजिए।")
        else:
            await registered_step(phone, digits)


async def on_call(phone: str) -> None:
    now = time.monotonic()
    if now - _call_started.get(phone, 0) < CALL_DEDUPE_S:
        return
    _call_started[phone] = now
    async with _lock(phone):
        await start(phone)


def _call_peer(data: dict) -> str | None:
    """Caller chat id from a waAPI call event (field names are not documented: take the first user id)."""
    call = data.get("call") or data
    if call.get("fromMe") or call.get("isGroup"):
        return None
    for key in ("from", "peerJid", "peer", "id"):
        v = call.get(key)
        if isinstance(v, str) and "@" in v:
            return v
    return None


def _spawn(coro) -> None:
    task = asyncio.create_task(coro)
    task.add_done_callback(lambda t: t.exception() and log.error("WhatsApp IVR task failed", exc_info=t.exception()))


@router.post("/webhook/{secret}")
async def webhook(secret: str, request: Request) -> dict:
    """waAPI events. Answers at once (waAPI retries slow replies); the conversation runs in the background."""
    if secret != waapi.webhook_secret() or not settings.whatsapp_ivr:
        raise HTTPException(404)
    payload = await request.json()
    event, data = payload.get("event"), payload.get("data") or {}
    if str(payload.get("instanceId", settings.waapi_instance_id)) != str(settings.waapi_instance_id):
        return {"ok": False}
    if event == "message":
        m = data.get("message") or {}
        mid = (m.get("id") or {}).get("_serialized") or f"{m.get('from')}:{m.get('timestamp')}"
        if m.get("fromMe") or m.get("type") != "chat" or "@g.us" in str(m.get("from")) or mid in _seen:
            return {"ok": True}
        _seen.append(mid)
        _spawn(on_message(waapi.phone_of(m["from"]), m.get("body") or ""))
    elif event == "call":
        peer = _call_peer(data)
        if peer:
            _spawn(on_call(waapi.phone_of(peer)))
    return {"ok": True}


@router.get("/status")
async def status() -> dict:
    """Is the WhatsApp number linked and the webhook set? (for the demo checklist)"""
    if settings.sms_channel == "waha":
        try:
            st = await asyncio.to_thread(waha.session)
        except waha.WahaError as exc:
            return {"channel": "waha", "error": str(exc)}
        return {"channel": "waha", "status": st.get("status"), "me": (st.get("me") or {}).get("id")}
    if not waapi.enabled():
        return {"enabled": False}
    try:
        st = await asyncio.to_thread(waapi.status)
    except waapi.WaapiError as exc:
        return {"enabled": True, "error": str(exc)}
    s = st.get("clientStatus", st)
    return {"enabled": True, "whatsapp_ivr": settings.whatsapp_ivr, "instance_status": s.get("instanceStatus"),
            "events": s.get("instanceEvents"), "call_policy": (s.get("instanceCallPolicy") or {}).get("mode")}


async def configure() -> dict:
    """Point the waAPI instance at this server: webhook for messages and calls, calls answered with the greeting.
    With WHATSAPP_IVR off (default) the instance only sends links: no webhook, WhatsApp calls left alone."""
    if not settings.whatsapp_ivr:
        out = await asyncio.to_thread(waapi.link_only)
        log.info("waAPI set to link-only (WhatsApp IVR off)")
        return {"webhook_set": False, "instance_status": out.get("instanceStatus")}
    base = settings.public_base_url.rstrip("/")
    audio = await asyncio.to_thread(tts.speech, GREETING, "mp3")
    greeting_url = f"{base}/tts/{audio.name}" if audio else None
    url = f"{base}{settings.api_v1_prefix}/wa/webhook/{waapi.webhook_secret()}"
    out = await asyncio.to_thread(waapi.configure, url, greeting_url, ["message", "call"])
    log.info("waAPI configured: webhook %s, greeting %s", url.rsplit("/", 1)[0] + "/…", greeting_url)
    return {"webhook_set": True, "greeting": greeting_url, "instance_status": out.get("instanceStatus")}


async def configure_on_startup() -> None:
    """Only on a public HTTPS deployment: waAPI cannot reach localhost. A front for another backend (API_UPSTREAM)
    leaves the webhook to that backend."""
    if settings.api_upstream or not (waapi.enabled() and settings.public_base_url.startswith("https://")):
        return
    try:
        await configure()
    except waapi.WaapiError as exc:
        log.warning("waAPI setup failed (POST /api/v1/wa/setup to retry): %s", exc)


@router.post("/setup")
async def setup() -> dict:
    if not waapi.enabled():
        raise HTTPException(409, "Set WAAPI_INSTANCE_ID and WAAPI_TOKEN first")
    try:
        return await configure()
    except waapi.WaapiError as exc:
        raise HTTPException(502, str(exc)) from exc


@router.get("/qr/{secret}")
async def waha_qr(secret: str) -> Response:
    """Link the bot's WhatsApp to WAHA: open on a laptop, scan with the bot phone (Linked devices > Link a device).
    Shows the linked number once done. The path secret keeps strangers from linking their own phone."""
    if secret != waapi.webhook_secret() or not waha.enabled():
        raise HTTPException(404)
    try:
        s = await asyncio.to_thread(waha.session)
        if s.get("status") == "WORKING":
            me = s.get("me") or {}
            return Response(f"<h1>WhatsApp linked: {me.get('id', '').split('@')[0]} {me.get('pushName', '')}</h1>",
                            media_type="text/html")
        if s.get("status") != "SCAN_QR_CODE":
            return Response(f"<meta http-equiv=refresh content=3><h1>WhatsApp session: {s.get('status')}…</h1>",
                            media_type="text/html")
        png = await asyncio.to_thread(waha.qr_png)
    except waha.WahaError as exc:
        raise HTTPException(502, str(exc)) from exc
    import base64
    img = base64.b64encode(png).decode()
    return Response(f"<meta http-equiv=refresh content=15><h2>Scan with the FasalNetra bot phone</h2>"
                    f"<img src='data:image/png;base64,{img}' width=320>", media_type="text/html")
