"""SMS / WhatsApp adapters (Twilio, waAPI, AWS End User Messaging) and signed SMS links. Without a provider SMS is simulated.

Voice calls live in ivr_service.py and the *_state_machine.py flows."""
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
    error: str | None = None


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
    return f"{settings.walk_link_base}?t={make_token(case_id)}"


def _client():
    from twilio.rest import Client
    return Client(settings.twilio_account_sid, settings.twilio_auth_token)


def _send_aws(to: str, body: str) -> SendResult:
    """AWS End User Messaging SMS (pinpoint-sms-voice-v2); credentials from the usual AWS chain (profile / EC2 role)."""
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError

    req = {"DestinationPhoneNumber": to, "MessageBody": body, "MessageType": "TRANSACTIONAL"}
    if settings.aws_sms_sender_id:
        req["OriginationIdentity"] = settings.aws_sms_sender_id
    if to.startswith("+91") and settings.aws_sms_entity_id and settings.aws_sms_template_id:
        req["DestinationCountryParameters"] = {"IN_ENTITY_ID": settings.aws_sms_entity_id,
                                               "IN_TEMPLATE_ID": settings.aws_sms_template_id}
    try:
        resp = boto3.client("pinpoint-sms-voice-v2", region_name=settings.aws_sms_region).send_text_message(**req)
    except (BotoCoreError, ClientError) as exc:   # sandbox cap, unverified number, missing DLT IDs ...
        log.warning("AWS SMS to %s failed: %s", to, exc)
        return SendResult(simulated=False, sid=None, error=str(exc))
    return SendResult(simulated=False, sid=resp["MessageId"])


def _send_waapi(to: str, body: str) -> SendResult:
    """waapi.app: a WhatsApp number linked like WhatsApp Web; the farmer needs no sandbox opt-in."""
    from backend.app.services.communications import waapi

    try:
        return SendResult(simulated=False, sid=waapi.send_text(to, body))
    except waapi.WaapiError as exc:
        log.warning("waAPI WhatsApp to %s failed: %s", to, exc)
        return SendResult(simulated=False, sid=None, error=str(exc))


def _send_waha(to: str, body: str) -> SendResult:
    from backend.app.services.communications import waha

    try:
        return SendResult(simulated=False, sid=waha.send_text(to, body))
    except waha.WahaError as exc:   # session not linked yet, number not on WhatsApp ...
        log.warning("WAHA WhatsApp to %s failed: %s", to, exc)
        return SendResult(simulated=False, sid=None, error=str(exc))


def send_sms(to: str, body: str) -> SendResult:
    channel = settings.sms_channel
    from_ = settings.twilio_phone_number
    if channel == "aws":
        return _send_aws(to, body)
    if channel == "waapi":
        return _send_waapi(to, body)
    if channel == "waha":
        return _send_waha(to, body)
    if channel == "whatsapp":
        # WhatsApp is not under India's DLT SMS rules; the sandbox delivers free text to numbers that joined it
        to, from_ = f"whatsapp:{to}", f"whatsapp:{settings.twilio_whatsapp_from}"
    elif channel != "twilio":
        log.info("SMS (simulated) to %s: %s", to, body)
        return SendResult(simulated=True, sid=None)
    from twilio.base.exceptions import TwilioException

    try:
        msg = _client().messages.create(to=to, from_=from_, body=body)
    except TwilioException as exc:
        # e.g. trial accounts may only send predefined templates; a failed SMS must never drop the live call
        log.warning("SMS to %s failed: %s", to, exc)
        return SendResult(simulated=False, sid=None, error=str(exc))
    return SendResult(simulated=False, sid=msg.sid)
