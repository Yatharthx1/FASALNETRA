"""Twilio voice webhook + web keypad fallback. Both run the same script in services/communications/ivr.py."""
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request, Response, status
from twilio.request_validator import RequestValidator
from twilio.twiml.voice_response import Gather, VoiceResponse

from backend.app.api.deps import CaseDep, DbDep
from backend.app.core.config import settings
from backend.app.schemas import IvrIn, IvrOut
from backend.app.services import cases

router = APIRouter(prefix="/ivr")


def _twiml(case_id: int, prompt) -> Response:
    vr = VoiceResponse()
    if prompt.hangup:
        vr.say(prompt.say_hi, language=settings.ivr_language, voice=settings.ivr_voice)
        vr.hangup()
    else:
        action = f"{settings.api_v1_prefix}/ivr/voice?case_id={case_id}&step={prompt.step}"
        g = Gather(num_digits=1, action=action, method="POST", timeout=settings.ivr_timeout_seconds)
        g.say(prompt.say_hi, language=settings.ivr_language, voice=settings.ivr_voice)
        vr.append(g)
        vr.redirect(action + "&digit=9&retry=1", method="POST")   # no key: repeat once, then end politely
    return Response(content=str(vr), media_type="application/xml")


async def _check_signature(request: Request) -> None:
    if not settings.twilio_enabled:
        return
    form = await request.form()
    url = f"{settings.public_base_url}{request.url.path}?{request.url.query}"
    if not RequestValidator(settings.twilio_auth_token).validate(url, dict(form), request.headers.get("X-Twilio-Signature", "")):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Bad Twilio signature")


@router.post("/voice")
async def voice(request: Request, case_id: int, step: str, db: DbDep,
                Digits: Annotated[str | None, Form()] = None, digit: str | None = None,
                retry: int = 0) -> Response:
    await _check_signature(request)
    if retry and not Digits and step.endswith("_again"):
        vr = VoiceResponse()
        vr.say("Koi button nahi dabaya. Hum do ghante baad phir call karenge. Dhanyavaad.",
               language=settings.ivr_language, voice=settings.ivr_voice)
        vr.hangup()
        return Response(content=str(vr), media_type="application/xml")
    try:
        case = await cases.get_case(db, case_id)
    except cases.CaseNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found") from None
    prompt = await cases.ivr_step(db, case, step.removesuffix("_again"), Digits or digit)
    if retry and not Digits:
        prompt.step = prompt.step + "_again"   # second silence on this prompt ends the call
    return _twiml(case.id, prompt)


@router.post("/web/{case_id}", response_model=IvrOut)
async def web_keypad(payload: IvrIn, case: CaseDep, db: DbDep) -> IvrOut:
    p = await cases.ivr_step(db, case, payload.step, payload.digit)
    return IvrOut(case_id=case.id, step=p.step, say_hi=p.say_hi, options=p.options, next_step=p.next_step, hangup=p.hangup)
