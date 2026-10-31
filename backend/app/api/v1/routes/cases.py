from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from backend.app.api.deps import CaseDep, DbDep
from backend.app.schemas import (CallOut, CaseCreate, CaseOut, IvrOut, JobOut, KeypadIn, LinkOut, PhotoOut,
                                 TrapsIn, WalkIn)
from backend.app.services import cases, communications, fields, vision

router = APIRouter(prefix="/cases")

MAX_PHOTO_BYTES = 12 * 1024 * 1024
PHOTO_KINDS = {"leaf_top", "leaf_under", "chewed", "trap"}


def _prompt_out(case_id: int, p) -> IvrOut:
    return IvrOut(case_id=case_id, step=p.step, say_hi=p.say_hi, options=p.options, next_step=p.next_step,
                  hangup=p.hangup)


@router.post("", response_model=CaseOut, status_code=status.HTTP_201_CREATED)
async def create_case(payload: CaseCreate, db: DbDep) -> CaseOut:
    try:
        return await cases.create(db, payload.field_id)
    except fields.FieldNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Field {payload.field_id} not found") from None


@router.get("/by-token", response_model=CaseOut)
async def case_by_token(t: str, db: DbDep) -> CaseOut:
    """The SMS link carries a signed token, not the case id."""
    try:
        case_id = communications.read_token(t)
    except communications.LinkTokenError:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Link expired or invalid") from None
    try:
        return await cases.get_case(db, case_id)
    except cases.CaseNotFound:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found") from None


@router.get("/{case_id}", response_model=CaseOut)
async def get_case(case: CaseDep) -> CaseOut:
    return case


@router.post("/{case_id}/warning-call", response_model=CallOut)
async def warning_call(case: CaseDep, db: DbDep) -> CallOut:
    sent, first = await cases.warning_call(db, case)
    return CallOut(case_id=case.id, simulated=sent.simulated, call_sid=sent.sid, first_prompt=_prompt_out(case.id, first))


@router.post("/{case_id}/result-call", response_model=CallOut)
async def result_call(case: CaseDep, db: DbDep) -> CallOut:
    try:
        sent, first = await cases.result_call(db, case)
    except cases.CaseStateError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return CallOut(case_id=case.id, simulated=sent.simulated, call_sid=sent.sid, first_prompt=_prompt_out(case.id, first))


@router.post("/{case_id}/link", response_model=LinkOut)
async def send_link(case: CaseDep, db: DbDep) -> LinkOut:
    url, sent = await cases.send_link(db, case)
    return LinkOut(case_id=case.id, url=url, sms_sent=not sent.simulated, simulated=sent.simulated)


@router.post("/{case_id}/keypad", response_model=CaseOut)
async def keypad(payload: KeypadIn, case: CaseDep, db: DbDep) -> CaseOut:
    return await cases.save_keypad(db, case, payload.answers)


@router.post("/{case_id}/traps", response_model=CaseOut)
async def traps(payload: TrapsIn, case: CaseDep, db: DbDep) -> CaseOut:
    return await cases.save_traps(db, case, payload.counts)


@router.post("/{case_id}/photos", response_model=PhotoOut, status_code=status.HTTP_201_CREATED)
async def upload_photo(
    case: CaseDep,
    db: DbDep,
    file: Annotated[UploadFile, File()],
    kind: Annotated[str, Form()],
    spot: Annotated[int, Form(ge=0, le=20)] = 0,
    cell_id: Annotated[str | None, Form()] = None,
    lat: Annotated[float | None, Form(ge=-90, le=90)] = None,
    lon: Annotated[float | None, Form(ge=-180, le=180)] = None,
) -> PhotoOut:
    if kind not in PHOTO_KINDS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"kind must be one of {sorted(PHOTO_KINDS)}")
    data = await file.read(MAX_PHOTO_BYTES + 1)
    if len(data) > MAX_PHOTO_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Photo over 12 MB")
    try:
        return await cases.add_photo(db, case, data, kind, spot, cell_id, lat, lon)
    except vision.VisionUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    except OSError as exc:   # PIL cannot read it
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Not an image: {exc}") from exc


@router.post("/{case_id}/walk", response_model=CaseOut)
async def walk(payload: WalkIn, case: CaseDep, db: DbDep) -> CaseOut:
    return await cases.save_walk(db, case, payload.trail)


@router.post("/{case_id}/evidence", response_model=CaseOut)
async def build_evidence(case: CaseDep, db: DbDep) -> CaseOut:
    try:
        return await cases.build_evidence(db, case)
    except cases.CaseStateError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@router.post("/{case_id}/book-didi", response_model=JobOut, status_code=status.HTTP_201_CREATED)
async def book_didi(case: CaseDep, db: DbDep) -> JobOut:
    """Dashboard / web-keypad booking. Over the phone this happens only after the farmer presses 1 to confirm."""
    try:
        return await cases.book_didi(db, case)
    except cases.CaseStateError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
