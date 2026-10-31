"""FasalNetra IVR Telephony Service

Generates TwiML for Twilio voice calls, manages audio prompts with TTS fallback,
and coordinates farmer record creation.
"""

import logging
from pathlib import Path
from typing import Any
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Gather

from backend.app.core.config import settings
from backend.app.models.farmer import Farmer
from backend.app.models.ivr_session import IVRSession
from backend.app.services.communications.onboarding_state_machine import (
    get_step_config,
    process_step_input,
)
from backend.app.services.communications.registered_state_machine import (
    get_registered_flow_config,
    process_registered_step_input,
)

logger = logging.getLogger(__name__)


def generate_twiml_for_step(
    step: str,
    answers: dict[str, Any],
    action_url: str,
    reprompt_message: str | None = None,
) -> str:
    """Generates TwiML response with <Gather> for the specified onboarding step."""
    response = VoiceResponse()
    step_cfg = get_step_config(step, answers)

    # If there is a reprompt warning message
    if reprompt_message:
        response.say(reprompt_message, language=settings.ivr_default_language, voice="Polly.Aditi")

    # If this is the final completed step
    if step == "completed":
        # Check for pre-recorded audio
        audio_file = Path(settings.audio_prompt_dir) / f"{step_cfg['prompt_id']}.mp3"
        if audio_file.exists():
            response.play(f"{settings.public_base_url}/audio/hi/{step_cfg['prompt_id']}.mp3")
        else:
            response.say(
                step_cfg["prompt_text"],
                language=settings.ivr_default_language,
                voice="Polly.Aditi",
            )
        response.hangup()
        return str(response)

    # Standard gather prompt
    gather = Gather(
        num_digits=step_cfg["num_digits"],
        action=action_url,
        method="POST",
        timeout=settings.ivr_timeout_seconds,
        finish_on_key="",
    )

    audio_file = Path(settings.audio_prompt_dir) / f"{step_cfg['prompt_id']}.mp3"
    if audio_file.exists():
        gather.play(f"{settings.public_base_url}/audio/hi/{step_cfg['prompt_id']}.mp3")
    else:
        gather.say(
            step_cfg["prompt_text"],
            language=settings.ivr_default_language,
            voice="Polly.Aditi",
        )

    response.append(gather)

    # If no key was pressed within timeout, Twilio continues past Gather
    # We redirect to the same action_url without digits to trigger the reprompt handler
    response.redirect(f"{action_url}?timeout=1", method="POST")

    return str(response)


def generate_twiml_for_registered_step(
    flow: str,
    step: str,
    farmer: Any,
    action_url: str,
    reprompt_message: str | None = None,
) -> str:
    """Generates TwiML for registered farmer flows (safe reassurance, warning, result, followup)."""
    response = VoiceResponse()
    step_cfg = get_registered_flow_config(flow, step, farmer)

    if reprompt_message:
        response.say(reprompt_message, language=settings.ivr_default_language, voice="Polly.Aditi")

    # If this step terminates with a hangup
    if step_cfg.get("hangup"):
        audio_file = Path(settings.audio_prompt_dir) / f"{step_cfg['prompt_id']}.mp3"
        if audio_file.exists():
            response.play(f"{settings.public_base_url}/audio/hi/{step_cfg['prompt_id']}.mp3")
        else:
            response.say(step_cfg["prompt_text"], language=settings.ivr_default_language, voice="Polly.Aditi")
        response.hangup()
        return str(response)

    # Gather response
    gather = Gather(
        num_digits=step_cfg["num_digits"],
        action=action_url,
        method="POST",
        timeout=settings.ivr_timeout_seconds,
        finish_on_key="",
    )

    audio_file = Path(settings.audio_prompt_dir) / f"{step_cfg['prompt_id']}.mp3"
    if audio_file.exists():
        gather.play(f"{settings.public_base_url}/audio/hi/{step_cfg['prompt_id']}.mp3")
    else:
        gather.say(step_cfg["prompt_text"], language=settings.ivr_default_language, voice="Polly.Aditi")

    response.append(gather)
    response.redirect(f"{action_url}?timeout=1", method="POST")
    return str(response)


def trigger_outbound_call(phone: str, callback_webhook_url: str) -> str:
    """Triggers outbound phone call via Twilio or returns mock CallSid in dev/demo mode."""
    if (
        settings.twilio_account_sid
        and settings.twilio_auth_token
        and not settings.twilio_account_sid.startswith("ACxxxx")
    ):
        try:
            client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
            call = client.calls.create(
                to=phone,
                from_=settings.twilio_phone_number,
                url=callback_webhook_url,
            )
            logger.info("Twilio outbound call initiated: %s to %s", call.sid, phone)
            return call.sid
        except Exception as e:
            logger.error("Failed to initiate Twilio call: %s", e)
            return f"mock-call-{phone[-4:] if len(phone) >= 4 else '0000'}"
    else:
        mock_sid = f"mock-call-{phone[-4:] if len(phone) >= 4 else '0000'}"
        logger.info("Demo mode: Simulated outbound call %s to %s", mock_sid, phone)
        return mock_sid


def save_farmer_from_onboarding(db, phone: str, answers: dict[str, Any]) -> Farmer:
    """Creates or updates a Farmer record from completed IVR answers."""
    farmer = db.query(Farmer).filter(Farmer.phone == phone).first()
    if not farmer:
        farmer = Farmer(phone=phone)
        db.add(farmer)

    farmer.language = answers.get("welcome", "hi")
    farmer.crop = answers.get("crop", "soybean")
    farmer.sowing_date_bracket = answers.get("sowing_date", "30_60")
    farmer.pincode = answers.get("pincode", "458001")
    farmer.village = answers.get("village", "दलोदा (Daloda)")
    farmer.corner_landmark = answers.get("landmark", None)
    farmer.neighbor_crop = answers.get("neighbor_crop", "urad_moong")
    farmer.grassy_border = answers.get("grass_border", "yes")
    farmer.status = "registered"

    db.commit()
    db.refresh(farmer)
    return farmer


REGISTERED_FIRST_STEP = {
    "safe": "safe_message",
    "warning": "warning_prompt",
    "result": "result_prompt",
    "followup": "followup_prompt",
}
REGISTERED_DONE_STEPS = ["sms_dispatched", "booking_confirmed", "followup_recorded", "completed"]


def clean_phone_number(phone: str) -> str:
    clean = phone.strip()
    return clean if clean.startswith("+") else f"+{clean}"


def start_call(db, phone: str, flow: str | None = None) -> dict[str, Any]:
    """Initiates an immediate outbound call (onboarding for new farmers, else their active flow).

    Used by POST /ivr/trigger-call and by the case workflow's warning/result calls.
    """
    clean_phone = clean_phone_number(phone)
    farmer = db.query(Farmer).filter(Farmer.phone == clean_phone).first()
    is_registered = farmer is not None and farmer.status == "registered"

    # Resolve target flow
    if flow:
        target_flow = flow
    elif is_registered:
        target_flow = farmer.active_flow or "safe"
    else:
        target_flow = "onboarding"

    if target_flow == "onboarding":
        initial_step = "welcome"
        callback_url = f"{settings.public_base_url}{settings.api_v1_prefix}/ivr/onboarding/start?phone={clean_phone}"
    else:
        initial_step = REGISTERED_FIRST_STEP.get(target_flow, "safe_message")
        callback_url = f"{settings.public_base_url}{settings.api_v1_prefix}/ivr/registered/start?phone={clean_phone}&flow={target_flow}"

    # Initialize or reset session
    session = db.query(IVRSession).filter(IVRSession.phone == clean_phone).first()
    if not session:
        session = IVRSession(call_sid=f"call-{clean_phone[-4:]}", phone=clean_phone, flow=target_flow, current_step=initial_step)
        db.add(session)
    else:
        session.flow = target_flow
        session.current_step = initial_step
        session.reprompt_count = 0
        session.answers = {}
        session.status = "in_progress"
    db.commit()

    call_sid = trigger_outbound_call(clean_phone, callback_url)
    session.call_sid = call_sid
    db.commit()

    return {
        "status": "call_initiated",
        "phone": clean_phone,
        "flow": target_flow,
        "step": initial_step,
        "is_registered": is_registered,
        "call_sid": call_sid,
        "webhook_url": callback_url,
    }


def advance_registered(db, session: IVRSession, digits: str | None) -> dict[str, Any]:
    """Runs one keypad press through the registered-farmer state machine and applies its side effects.

    Shared by the Twilio webhook (/ivr/registered/step) and the web keypad (/ivr/simulate/registered).
    Returns the state machine result; the caller reacts to result["action"] outside this DB session.
    """
    farmer = db.query(Farmer).filter(Farmer.phone == session.phone).first()
    step_result = process_registered_step_input(
        flow=session.flow,
        current_step=session.current_step,
        digits=digits,
        reprompt_count=session.reprompt_count,
    )

    action = step_result["action"]
    # Handle action side effects
    if action == "send_sms_link":
        answers = dict(session.answers or {})
        answers["sms_sent"] = True
        session.answers = answers
        logger.info("[SMS DISPATCH] Trap photo upload link requested for %s", session.phone)

    elif action == "confirm_drone_booking":
        if farmer:
            farmer.spray_booked = "yes"
        answers = dict(session.answers or {})
        answers["drone_booked"] = True
        session.answers = answers
        logger.info("[DRONE DISPATCH] Farmer %s confirmed drone spray booking!", session.phone)

    elif action.startswith("record_feedback_"):
        answers = dict(session.answers or {})
        answers["followup_feedback"] = action.replace("record_feedback_", "")
        session.answers = answers

    session.current_step = step_result["next_step"]
    session.reprompt_count = step_result["reprompt_count"]
    if step_result["next_step"] in REGISTERED_DONE_STEPS:
        session.status = "completed"

    db.commit()
    return step_result
