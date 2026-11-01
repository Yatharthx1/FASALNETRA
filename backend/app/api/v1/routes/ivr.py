"""FasalNetra IVR Onboarding & Telephony API Routes"""

import asyncio
import logging
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Query, Response
from sqlalchemy.orm import Session
from twilio.twiml.voice_response import VoiceResponse

from backend.app.core.config import settings
from backend.app.db import database
from backend.app.db.session import get_db
from backend.app.models.farmer import Farmer
from backend.app.models.ivr_session import IVRSession
from backend.app.schemas.ivr import (
    IVRRegisteredSimulateRequest,
    IVRRegisteredSimulateResponse,
    IVRSimulateRequest,
    IVRSimulateResponse,
    IVRStepOption,
)
from backend.app.services import cases
from backend.app.services.communications import ivr_service
from backend.app.services.communications.ivr_service import (
    REGISTERED_FIRST_STEP,
    advance_registered,
    clean_phone_number,
    inbound_flow,
    generate_twiml_for_registered_step,
    generate_twiml_for_step,
    generate_twiml_live,
    generate_twiml_say_hangup,
    ivr_url,
    live_url,
    save_farmer_from_onboarding,
    start_call,
    trigger_outbound_call,
)
from backend.app.services.communications.onboarding_state_machine import (
    get_step_config,
    process_step_input,
)
from backend.app.services.communications.registered_state_machine import (
    get_registered_flow_config,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ivr", tags=["ivr"])


async def _case_context(phone: str) -> dict | None:
    """The farmer's latest case result, so the result call speaks the real cause, zone and dose."""
    async with database.SessionLocal() as adb:
        return await cases.ivr_context(adb, phone)


async def _apply_to_case(phone: str, step: str, digits: str | None, action: str) -> None:
    """Hand a registered-flow key press to the farmer's open crop case (SMS walk link, Drone Didi booking)."""
    async with database.SessionLocal() as adb:
        await cases.on_ivr_action(adb, phone, step, digits, action)


async def _onboarded(phone: str, answers: dict) -> bool:
    """Onboarding finished: resolve the field, pick walk targets from Sentinel-2, send the SMS camera link."""
    async with database.SessionLocal() as adb:
        return await cases.on_onboarded(adb, phone, answers) is not None


def _hold_for_photos(session: IVRSession) -> None:
    """Turn the call into the live hold: same state as a registered farmer who was just sent the link."""
    session.flow = "report"
    session.current_step = "sms_dispatched"
    session.reprompt_count = 0
    session.status = "in_progress"
    session.answers = {**(session.answers or {}), "sms_sent": True}


async def _advance_live(db: Session, session: IVRSession) -> tuple[str, str]:
    """One live-hold check. On "result" the session moves to the result call; on "end" it is closed."""
    async with database.SessionLocal() as adb:
        kind, text, state = await cases.live_tick(adb, session.phone, session.answers or {})
    session.answers = state
    if kind == "result":
        farmer = db.query(Farmer).filter(Farmer.phone == session.phone).first()
        if farmer:
            farmer.active_flow = "result"
        session.flow, session.current_step, session.reprompt_count = "result", "result_prompt", 0
    elif kind == "end":
        session.status = "completed"
    db.commit()
    return kind, text


def call_farmer_now(phone: str, db_session_maker) -> dict:
    """Place the IVR call now: onboarding for a new number, else the registered flow (report / pending result)."""
    clean_phone = ivr_service.clean_phone_number(phone)
    db = db_session_maker()
    try:
        farmer = db.query(Farmer).filter(Farmer.phone == clean_phone).first()
        last = db.query(IVRSession).filter(IVRSession.phone == clean_phone).first()
        flow = inbound_flow(farmer, last)
        initial_step = "welcome" if flow == "onboarding" else REGISTERED_FIRST_STEP[flow]
        callback_url = (ivr_url("onboarding/start", phone=clean_phone) if flow == "onboarding"
                        else ivr_url("registered/start", phone=clean_phone, flow=flow))
        call_sid, error = ivr_service.place_call(clean_phone, callback_url)
        session = last or IVRSession(call_sid=call_sid, phone=clean_phone)
        if last is None:
            db.add(session)
        session.call_sid, session.flow, session.current_step = call_sid, flow, initial_step
        session.reprompt_count, session.answers, session.status = 0, {}, "in_progress"
        db.commit()
        return {"phone": clean_phone, "flow": flow, "call_sid": call_sid,
                "simulated": call_sid.startswith("mock-"), "error": error}
    finally:
        db.close()


async def execute_missed_call_callback(phone: str, db_session_maker) -> None:
    """Waits a brief window and triggers the free callback to the farmer.
    If the farmer is already registered, executes their active flow (safe, warning, result, followup)
    instead of asking onboarding questions!
    """
    delay = 3
    logger.info("Scheduling callback to %s in %d seconds...", phone, delay)
    await asyncio.sleep(delay)

    clean_phone = phone.strip()
    if not clean_phone.startswith("+"):
        clean_phone = f"+{clean_phone}"

    db = db_session_maker()
    try:
        farmer = db.query(Farmer).filter(Farmer.phone == clean_phone).first()
        is_registered = farmer is not None and farmer.status == "registered"

        if is_registered:
            last = db.query(IVRSession).filter(IVRSession.phone == clean_phone).first()
            flow = inbound_flow(farmer, last)
            initial_step = REGISTERED_FIRST_STEP[flow]
            callback_url = f"{settings.public_base_url}{settings.api_v1_prefix}/ivr/registered/start?phone={clean_phone}&flow={flow}"
            logger.info("Farmer %s is REGISTERED. Executing flow: %s", clean_phone, flow)
        else:
            flow = "onboarding"
            initial_step = "welcome"
            callback_url = f"{settings.public_base_url}{settings.api_v1_prefix}/ivr/onboarding/start?phone={clean_phone}"
            logger.info("Farmer %s is NEW. Executing onboarding.", clean_phone)

        call_sid = trigger_outbound_call(clean_phone, callback_url)

        session = db.query(IVRSession).filter(IVRSession.phone == clean_phone).first()
        if not session:
            session = IVRSession(call_sid=call_sid, phone=clean_phone, flow=flow, current_step=initial_step)
            db.add(session)
        else:
            session.call_sid = call_sid
            session.flow = flow
            session.current_step = initial_step
            session.reprompt_count = 0
            session.answers = {}
            session.status = "in_progress"
        db.commit()
    finally:
        db.close()


@router.post("/webhook")
async def ivr_inbound_webhook(
    background_tasks: BackgroundTasks,
    From: Optional[str] = Form(None),
    CallSid: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Twilio incoming voice webhook.
    IVR_INBOUND_MODE=answer: the IVR runs in this same call (onboarding for a new number, else the registered flow).
    IVR_INBOUND_MODE=callback: a free 'missed call': rejects so the farmer is charged 0, then calls back in ~3 s.
    """
    farmer_phone = (From or settings.demo_farmer_phone).strip()
    if not farmer_phone.startswith("+"):
        farmer_phone = f"+{farmer_phone}"

    if settings.ivr_inbound_mode == "answer" and CallSid:
        farmer = db.query(Farmer).filter(Farmer.phone == farmer_phone).first()
        session = db.query(IVRSession).filter(IVRSession.phone == farmer_phone).first()
        flow = inbound_flow(farmer, session)
        if session is None:
            session = IVRSession(call_sid=CallSid, phone=farmer_phone)
            db.add(session)
        session.call_sid, session.flow = CallSid, flow
        session.current_step = "welcome" if flow == "onboarding" else REGISTERED_FIRST_STEP[flow]
        session.reprompt_count, session.answers, session.status = 0, {}, "in_progress"
        db.commit()
        logger.info("Inbound call from %s (CallSid: %s): answering with flow %s.", farmer_phone, CallSid, flow)
        response = VoiceResponse()
        response.redirect(ivr_url("onboarding/start", phone=farmer_phone) if flow == "onboarding"
                          else ivr_url("registered/start", phone=farmer_phone, flow=flow), method="POST")
        return Response(content=str(response), media_type="application/xml")

    logger.info("Missed call received from %s (CallSid: %s). Rejecting for free callback.", farmer_phone, CallSid)

    from backend.app.db.session import SessionLocal
    background_tasks.add_task(execute_missed_call_callback, farmer_phone, SessionLocal)

    response = VoiceResponse()
    response.reject(reason="busy")
    return Response(content=str(response), media_type="application/xml")


@router.post("/missed-call")
async def simulate_missed_call(
    background_tasks: BackgroundTasks,
    phone: str = Query(..., description="Farmer phone number"),
):
    """Simulates a farmer dialing in and giving a missed call.
    Instantly triggers the free callback to that phone.
    """
    clean_phone = phone.strip()
    if not clean_phone.startswith("+"):
        clean_phone = f"+{clean_phone}"

    from backend.app.db.session import SessionLocal
    background_tasks.add_task(execute_missed_call_callback, clean_phone, SessionLocal)

    return {
        "status": "missed_call_received",
        "phone": clean_phone,
        "message": f"Missed call logged from {clean_phone}. System is calling back in 3 seconds.",
    }


@router.post("/get-call")
async def get_a_call(phone: str | None = Query(None, description="Farmer phone, E.164; default DEMO_FARMER_PHONE")) -> dict:
    """Dashboard "Get a call": FasalNetra calls the farmer right away (no missed call needed).
    simulated=true: Twilio not configured, use the dashboard keypad. error: Twilio refused the call (shown as is)."""
    from backend.app.db.session import SessionLocal

    out = await asyncio.to_thread(call_farmer_now, phone or settings.demo_farmer_phone, SessionLocal)
    async with database.SessionLocal() as adb:
        from backend.app.services.events import emit
        await emit(adb, "call_placed", None, kind=out["flow"], simulated=out["simulated"], error=out["error"])
    return out


@router.post("/onboarding/start")
async def ivr_onboarding_start(
    phone: Optional[str] = Query(None),
    CallSid: Optional[str] = Form(None),
    From: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Entry point for the outbound callback to start the onboarding questionnaire."""
    farmer_phone = (phone or From or settings.demo_farmer_phone).strip()
    if not farmer_phone.startswith("+"):
        farmer_phone = f"+{farmer_phone}"
    session = (
        db.query(IVRSession)
        .filter((IVRSession.phone == farmer_phone) | (IVRSession.call_sid == CallSid))
        .first()
    )

    if not session:
        session = IVRSession(
            call_sid=CallSid or f"session-{farmer_phone}",
            phone=farmer_phone,
            flow="onboarding",
            current_step="welcome",
            answers={},
        )
        db.add(session)
        db.commit()
        db.refresh(session)

    action_url = f"{settings.public_base_url}{settings.api_v1_prefix}/ivr/onboarding/step?call_sid={session.call_sid}"
    twiml = generate_twiml_for_step("welcome", session.answers or {}, action_url)
    return Response(content=twiml, media_type="application/xml")


@router.post("/onboarding/step")
async def ivr_onboarding_step(
    background_tasks: BackgroundTasks,
    call_sid: Optional[str] = Query(None),
    CallSid: Optional[str] = Form(None),
    Digits: Optional[str] = Form(None),
    timeout: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Processes DTMF keypad digits from Twilio <Gather> and returns the next prompt TwiML."""
    active_sid = call_sid or CallSid
    session = db.query(IVRSession).filter(IVRSession.call_sid == active_sid).first()

    if not session:
        # Fallback session if none found
        session = IVRSession(
            call_sid=active_sid or "unknown-call",
            phone=settings.demo_farmer_phone,
            flow="onboarding",
            current_step="welcome",
            answers={},
        )
        db.add(session)
        db.commit()

    digits_input = None if timeout else Digits
    step_result = process_step_input(
        current_step=session.current_step,
        digits=digits_input,
        current_answers=session.answers or {},
        reprompt_count=session.reprompt_count,
    )

    session.answers = step_result["updated_answers"]
    session.current_step = step_result["next_step"]
    session.reprompt_count = step_result["reprompt_count"]

    if step_result["next_step"] == "completed":
        session.status = "completed"
        save_farmer_from_onboarding(db, session.phone, session.answers)
        # Field mapping, the new case and the WhatsApp/SMS send take seconds: run them after Twilio has its answer
        # (trial webhooks time out at ~5 s) and with no database transaction held across them.
        background_tasks.add_task(_onboarded, session.phone, dict(session.answers or {}))
        # same call continues: "SMS mein link aaya hai, usey dabaiye", then hold while the camera runs
        _hold_for_photos(session)
        session.answers = {**session.answers, "hold_since": cases.utcnow_iso()}   # ignore cases older than this call
        db.commit()
        twiml = generate_twiml_for_registered_step("report", "sms_dispatched", None,
                                                   ivr_url("registered/step", call_sid=session.call_sid),
                                                   reprompt_message=get_step_config("completed", {})["prompt_text"])
        return Response(content=twiml, media_type="application/xml")

    db.commit()
    action_url = f"{settings.public_base_url}{settings.api_v1_prefix}/ivr/onboarding/step?call_sid={session.call_sid}"
    reprompt_msg = step_result["message"] if step_result["reprompt"] else None
    twiml = generate_twiml_for_step(session.current_step, session.answers or {}, action_url, reprompt_msg)
    return Response(content=twiml, media_type="application/xml")


@router.post("/registered/start")
async def ivr_registered_start(
    phone: Optional[str] = Query(None),
    flow: Optional[str] = Query("safe"),
    CallSid: Optional[str] = Form(None),
    From: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Entry point for calls to already registered farmers."""
    farmer_phone = (phone or From or settings.demo_farmer_phone).strip()
    if not farmer_phone.startswith("+"):
        farmer_phone = f"+{farmer_phone}"

    farmer = db.query(Farmer).filter(Farmer.phone == farmer_phone).first()
    active_flow = flow or (farmer.active_flow if farmer else "safe")

    initial_step = REGISTERED_FIRST_STEP.get(active_flow, "safe_message")

    clean_sid = CallSid or f"session-{farmer_phone.replace('+', '')}"
    session = (
        db.query(IVRSession)
        .filter((IVRSession.phone == farmer_phone) | (IVRSession.call_sid == clean_sid))
        .first()
    )
    if not session:
        session = IVRSession(
            call_sid=clean_sid,
            phone=farmer_phone,
            flow=active_flow,
            current_step=initial_step,
            answers={},
            status="in_progress",
        )
        db.add(session)
    else:
        session.call_sid = clean_sid
        session.flow = active_flow
        session.current_step = initial_step
        session.reprompt_count = 0
        session.answers = {}
        session.status = "in_progress"
    db.commit()
    db.refresh(session)

    action_url = f"{settings.public_base_url}{settings.api_v1_prefix}/ivr/registered/step?call_sid={session.call_sid}"
    twiml = generate_twiml_for_registered_step(active_flow, initial_step, farmer, action_url,
                                               context=await _case_context(farmer_phone))
    return Response(content=twiml, media_type="application/xml")


@router.post("/registered/step")
async def ivr_registered_step(
    call_sid: Optional[str] = Query(None),
    CallSid: Optional[str] = Form(None),
    Digits: Optional[str] = Form(None),
    timeout: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Handles DTMF keypad responses for registered farmer calls (Warning, Result, Followup)."""
    raw_sid = (call_sid or CallSid or "").strip()
    session = (
        db.query(IVRSession)
        .filter(
            (IVRSession.call_sid == raw_sid)
            | (IVRSession.call_sid == raw_sid.replace(" ", "+"))
            | (IVRSession.call_sid == raw_sid.replace(" ", ""))
            | (IVRSession.call_sid == raw_sid.replace("+", ""))
        )
        .first()
    )

    if not session:
        session = IVRSession(
            call_sid=raw_sid or "unknown-call",
            phone=settings.demo_farmer_phone,
            flow="safe",
            current_step="safe_message",
            answers={},
        )
        db.add(session)
        db.commit()

    farmer = db.query(Farmer).filter(Farmer.phone == session.phone).first()
    digits_input = None if timeout else Digits
    pressed_on = session.current_step
    step_result = advance_registered(db, session, digits_input)
    await _apply_to_case(session.phone, pressed_on, digits_input, step_result["action"])

    action_url = f"{settings.public_base_url}{settings.api_v1_prefix}/ivr/registered/step?call_sid={session.call_sid}"
    reprompt_msg = step_result["message"] if step_result["reprompt"] else None
    twiml = generate_twiml_for_registered_step(session.flow, session.current_step, farmer, action_url, reprompt_msg,
                                               context=await _case_context(session.phone))
    return Response(content=twiml, media_type="application/xml")


@router.post("/live")
async def ivr_live(
    call_sid: Optional[str] = Query(None),
    CallSid: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Live hold while the farmer uses the camera link: speak each new photo's check, then the result in the same call."""
    sid = (call_sid or CallSid or "").strip()
    session = db.query(IVRSession).filter(IVRSession.call_sid == sid).first()
    if session is None or session.current_step != "sms_dispatched" or session.status != "in_progress":
        return Response(content=generate_twiml_say_hangup("धन्यवाद।"), media_type="application/xml")
    kind, text = await _advance_live(db, session)
    if kind == "wait":
        twiml = generate_twiml_live(text, live_url(session.call_sid), pause_s=cases.LIVE_TICK_S)
    elif kind == "result":
        farmer = db.query(Farmer).filter(Farmer.phone == session.phone).first()
        twiml = generate_twiml_for_registered_step("result", "result_prompt", farmer,
                                                   ivr_url("registered/step", call_sid=session.call_sid),
                                                   context=await _case_context(session.phone))
    else:
        twiml = generate_twiml_say_hangup(text)
    return Response(content=twiml, media_type="application/xml")


@router.post("/status")
async def ivr_call_status(
    CallSid: Optional[str] = Form(None),
    CallStatus: Optional[str] = Form(None),
    CallDuration: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """Twilio call status callback (ringing, answered, completed, busy, no-answer)."""
    logger.info("Call %s status updated: %s (Duration: %ss)", CallSid, CallStatus, CallDuration)
    if CallSid:
        session = db.query(IVRSession).filter(IVRSession.call_sid == CallSid).first()
        if session and CallStatus in ["completed", "failed", "busy", "no-answer"]:
            if session.current_step == "sms_dispatched" and session.status == "in_progress":
                session.status = "completed"   # hung up during the live hold: the result goes out as a callback
            elif session.current_step != "completed" and CallStatus != "completed":
                session.status = "failed"
            db.commit()
    return {"status": "received"}


@router.post("/simulate/step", response_model=IVRSimulateResponse)
async def ivr_simulate_step(
    payload: IVRSimulateRequest,
    db: Session = Depends(get_db),
):
    """Interactive simulator endpoint used by the frontend Web Keypad and automated tests.
    Executes the exact same business logic and state machine as live Twilio calls.
    """
    phone = payload.phone.strip()
    session = db.query(IVRSession).filter(IVRSession.phone == phone).first()

    if payload.reset or not session:
        if not session:
            session = IVRSession(
                call_sid=f"sim-{phone[-4:] if len(phone) >= 4 else '0000'}",
                phone=phone,
                flow="onboarding",
                current_step="welcome",
                answers={},
            )
            db.add(session)
        else:
            session.current_step = "welcome"
            session.reprompt_count = 0
            session.answers = {}
            session.status = "in_progress"
        db.commit()
        db.refresh(session)

    # Process step if digits provided or step already in progress
    if payload.digits is not None and session.current_step != "completed":
        step_result = process_step_input(
            current_step=session.current_step,
            digits=payload.digits,
            current_answers=session.answers or {},
            reprompt_count=session.reprompt_count,
        )
        session.answers = step_result["updated_answers"]
        session.current_step = step_result["next_step"]
        session.reprompt_count = step_result["reprompt_count"]

        if session.current_step == "completed":
            session.status = "completed"
            save_farmer_from_onboarding(db, session.phone, session.answers)
            if await _onboarded(session.phone, session.answers or {}):
                answers = dict(session.answers or {})
                _hold_for_photos(session)
                db.commit()
                step_cfg = get_step_config("completed", answers)
                return IVRSimulateResponse(
                    call_sid=session.call_sid, phone=session.phone, current_step="completed",
                    prompt_id=step_cfg["prompt_id"], prompt_text=step_cfg["prompt_text"], num_digits=0, options=[],
                    answers=answers, is_completed=True, reprompt_count=0,
                    message="Field mapped and SMS link sent; the call continues at /ivr/simulate/registered (live hold).")

        db.commit()
        message = step_result["message"]
    else:
        message = "Session initialized."

    step_cfg = get_step_config(session.current_step, session.answers or {})

    return IVRSimulateResponse(
        call_sid=session.call_sid,
        phone=session.phone,
        current_step=session.current_step,
        prompt_id=step_cfg["prompt_id"],
        prompt_text=step_cfg["prompt_text"],
        num_digits=step_cfg["num_digits"],
        options=[IVRStepOption(digit=opt["digit"], label=opt["label"]) for opt in step_cfg["options"]],
        answers=session.answers or {},
        is_completed=(session.current_step == "completed"),
        reprompt_count=session.reprompt_count,
        message=message,
    )


@router.post("/simulate/registered", response_model=IVRRegisteredSimulateResponse)
async def ivr_simulate_registered(
    payload: IVRRegisteredSimulateRequest,
    db: Session = Depends(get_db),
):
    """Web keypad for registered-farmer calls (warning, result, followup).
    Same state machine and side effects as /ivr/registered/step, answered in JSON instead of TwiML.
    """
    phone = clean_phone_number(payload.phone)
    session = db.query(IVRSession).filter(IVRSession.phone == phone).first()
    if not session or session.flow == "onboarding":
        raise HTTPException(status_code=404, detail="No registered-farmer call in progress for this phone")

    message = "Prompt shown."
    if payload.digits is None and session.current_step == "sms_dispatched" and session.status == "in_progress":
        # each poll is one live-hold check, like the Twilio /ivr/live redirect loop
        kind, text = await _advance_live(db, session)
        farmer = db.query(Farmer).filter(Farmer.phone == phone).first()
        if kind != "result":
            prompt = registered_prompt(phone, "report", "sms_dispatched", farmer, f"live: {kind}")
            return prompt.model_copy(update={"prompt_text": text, "is_completed": kind == "end"})
        message = "live: result ready"
    elif payload.digits is not None and session.status != "completed":
        pressed_on = session.current_step
        step_result = advance_registered(db, session, payload.digits)
        await _apply_to_case(phone, pressed_on, payload.digits, step_result["action"])
        message = step_result["message"]

    farmer = db.query(Farmer).filter(Farmer.phone == phone).first()
    return registered_prompt(phone, session.flow, session.current_step, farmer, message, await _case_context(phone))


def registered_prompt(phone: str, flow: str, step: str, farmer, message: str = "",
                      context: dict | None = None) -> IVRRegisteredSimulateResponse:
    cfg = get_registered_flow_config(flow, step, farmer, context)
    return IVRRegisteredSimulateResponse(
        phone=phone,
        flow=flow,
        current_step=cfg["step"],
        prompt_id=cfg["prompt_id"],
        prompt_text=cfg["prompt_text"],
        valid_digits=cfg["valid_digits"],
        is_completed=cfg["hangup"],
        message=message,
    )


@router.post("/trigger-call")
async def trigger_manual_onboarding_call(
    phone: str = Query(..., description="Target phone number in E.164 format (e.g. +91XXXXXXXXXX)"),
    flow: Optional[str] = Query(None, description="Optional override flow: onboarding | safe | warning | result | followup"),
    db: Session = Depends(get_db),
):
    """Initiates an immediate outbound call.
    If the farmer is registered, respects their active farm state (safe, warning, result)
    unless a specific flow is overridden.
    """
    result = start_call(db, phone, flow)
    result.pop("step")
    return result


@router.post("/farmer/set-state")
async def set_farmer_farm_state(
    phone: str = Query(..., description="Farmer phone number in E.164 format"),
    active_flow: str = Query("safe", description="safe | warning | result | followup"),
    risk_score: Optional[int] = Query(None, description="Risk score 0-100"),
    db: Session = Depends(get_db),
):
    """Sets a farmer's farm alert state (Safe, High Warning, Result, Followup)."""
    clean_phone = phone.strip()
    if not clean_phone.startswith("+"):
        clean_phone = f"+{clean_phone}"

    farmer = db.query(Farmer).filter(Farmer.phone == clean_phone).first()
    if not farmer:
        farmer = Farmer(phone=clean_phone, status="registered", active_flow=active_flow)
        db.add(farmer)
    else:
        farmer.active_flow = active_flow

    if risk_score is not None:
        farmer.risk_score = risk_score

    db.commit()
    db.refresh(farmer)

    return {
        "status": "updated",
        "phone": clean_phone,
        "active_flow": farmer.active_flow,
        "risk_score": farmer.risk_score,
        "spray_booked": farmer.spray_booked,
    }


@router.get("/session/{phone}")
async def get_ivr_session(
    phone: str,
    db: Session = Depends(get_db),
):
    """Fetches the latest IVR session and registered farmer profile for a phone number."""
    clean_phone = phone.strip()
    if not clean_phone.startswith("+"):
        clean_phone = f"+{clean_phone}"

    session = db.query(IVRSession).filter(IVRSession.phone == clean_phone).order_by(IVRSession.id.desc()).first()
    farmer = db.query(Farmer).filter(Farmer.phone == clean_phone).first()

    return {
        "phone": clean_phone,
        "session": {
            "call_sid": session.call_sid if session else None,
            "flow": session.flow if session else None,
            "current_step": session.current_step if session else None,
            "status": session.status if session else "idle",
            "answers": session.answers if session else {},
            "reprompt_count": session.reprompt_count if session else 0,
            "updated_at": session.updated_at.isoformat() if session and session.updated_at else None,
        } if session else None,
        "farmer": {
            "name": farmer.name,
            "crop": farmer.crop,
            "sowing_date_bracket": farmer.sowing_date_bracket,
            "village": farmer.village,
            "status": farmer.status,
        } if farmer else None,
    }


