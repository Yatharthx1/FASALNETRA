"""Twilio voice/SMS adapter and signed SMS links. Without Twilio credentials everything is simulated."""
import hashlib
import hmac
import logging
import time
from dataclasses import dataclass

from backend.app.core.config import settings

log = logging.getLogger(__name__)


class LinkTokenError(ValueError):
    """Raised for a forged or expired SMS link token."""


@dataclass(frozen=True)
class SendResult:
    simulated: bool
    sid: str | None


def make_token(case_id: int, now: float | None = None) -> str:
    exp = int((time.time() if now is None else now) + settings.sms_link_token_ttl_minutes * 60)
    msg = f"{case_id}.{exp}"
    sig = hmac.new(settings.sms_link_signing_secret.encode(), msg.encode(), hashlib.sha256).hexdigest()[:20]
    return f"{msg}.{sig}"


def read_token(token: str, now: float | None = None) -> int:
    try:
        case_id, exp, sig = token.split(".")
        expected = hmac.new(settings.sms_link_signing_secret.encode(), f"{case_id}.{exp}".encode(),
                            hashlib.sha256).hexdigest()[:20]
    except ValueError as exc:
        raise LinkTokenError("malformed token") from exc
    if not hmac.compare_digest(sig, expected):
        raise LinkTokenError("bad signature")
    if int(exp) < (time.time() if now is None else now):
        raise LinkTokenError("expired")
    return int(case_id)


def walk_link(case_id: int) -> str:
    return f"{settings.sms_link_base_url}?t={make_token(case_id)}"


def _client():
    from twilio.rest import Client
    return Client(settings.twilio_account_sid, settings.twilio_auth_token)


def send_sms(to: str, body: str) -> SendResult:
    if not settings.twilio_enabled:
        log.info("SMS (simulated) to %s: %s", to, body)
        return SendResult(simulated=True, sid=None)
    msg = _client().messages.create(to=to, from_=settings.twilio_phone_number, body=body)
    return SendResult(simulated=False, sid=msg.sid)


def place_call(to: str, case_id: int, step: str) -> SendResult:
    if not settings.twilio_enabled:
        log.info("Call (simulated) to %s, case %s, step %s", to, case_id, step)
        return SendResult(simulated=True, sid=None)
    url = f"{settings.public_base_url}{settings.api_v1_prefix}/ivr/voice?case_id={case_id}&step={step}"
    call = _client().calls.create(to=to, from_=settings.twilio_phone_number, url=url)
    return SendResult(simulated=False, sid=call.sid)
