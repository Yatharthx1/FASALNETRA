"""waapi.app client: a normal WhatsApp number linked like WhatsApp Web, used for the link, voice notes and the
WhatsApp IVR (routes/whatsapp.py). Docs: https://waapi.readme.io/reference/"""
import base64
import hashlib
import logging

import httpx

from backend.app.core.config import settings

log = logging.getLogger(__name__)
API = "https://waapi.app/api/v1/instances"
TIMEOUT_S = 25

# phone -> chat id as WhatsApp gave it (newer accounts may use "@lid" ids instead of "<number>@c.us")
_chat_ids: dict[str, str] = {}


class WaapiError(RuntimeError):
    pass


def enabled() -> bool:
    return bool(settings.waapi_instance_id and settings.waapi_token)


def phone_of(chat_id: str) -> str:
    """'919876543210@c.us' -> '+919876543210'; the chat id is remembered so replies go back to it."""
    phone = "+" + chat_id.split("@")[0].split(":")[0]
    _chat_ids[phone] = chat_id
    return phone


def chat_id(phone: str) -> str:
    return _chat_ids.get(phone) or f"{phone.lstrip('+')}@c.us"


def webhook_secret() -> str:
    """Path secret for the webhook URL (waAPI does not sign requests)."""
    return settings.waapi_webhook_secret or hashlib.sha256(
        f"waapi.{settings.sms_link_signing_secret}".encode()).hexdigest()[:24]


def _headers() -> dict:
    return {"Authorization": f"Bearer {settings.waapi_token}", "Accept": "application/json"}


def _call(method: str, path: str, json: dict | None = None) -> dict:
    try:
        resp = httpx.request(method, f"{API}/{settings.waapi_instance_id}{path}", headers=_headers(), json=json,
                             timeout=TIMEOUT_S)
        resp.raise_for_status()
        body = resp.json()
    except (httpx.HTTPError, ValueError) as exc:   # 401 token, 409 not linked, 422 not on WhatsApp ...
        raise WaapiError(str(exc)) from exc
    inner = body.get("data") if isinstance(body.get("data"), dict) else body
    if inner.get("status") == "error":             # bad input comes back as HTTP 200 with an inner error
        raise WaapiError(str(inner.get("message") or inner))
    return inner


def _message_id(out: dict) -> str:
    return (((out.get("data") or {}).get("_data") or {}).get("id") or {}).get("_serialized") or "waapi"


def send_text(phone: str, text: str) -> str:
    return _message_id(_call("POST", "/client/action/send-message", {"chatId": chat_id(phone), "message": text}))


def send_voice(phone: str, ogg: bytes) -> str:
    """Ogg/Opus audio as a WhatsApp voice note (plays inline, like a recorded message)."""
    return _message_id(_call("POST", "/client/action/send-media", {
        "chatId": chat_id(phone), "mediaBase64": base64.b64encode(ogg).decode(), "mediaName": "fasalnetra.ogg",
        "asVoice": True}))


def status() -> dict:
    return _call("GET", "/client/status")


def configure(webhook_url: str, greeting_url: str | None, events: list[str]) -> dict:
    """Webhook for messages and calls; a WhatsApp call is answered with the Hindi greeting (or rejected with a
    note pointing to the chat when there is no greeting audio)."""
    policy = ({"mode": "answer_and_play", "audio_url": greeting_url, "hangup_after_seconds": 20} if greeting_url
              else {"mode": "reject_with_message", "message": "नमस्ते! फसलनेत्र आपसे इसी चैट में बात करेगा।"})
    return _call("PUT", "", {"webhook": {"url": webhook_url, "events": events}, "call_policy": policy})


def link_only() -> dict:
    """Sending only: no webhook events and WhatsApp calls to the number are left alone (the IVR is the phone call)."""
    return _call("PUT", "", {"webhook": {"url": None, "events": []}, "call_policy": None})
