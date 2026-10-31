"""Case workflow: warning call (IVR) -> SMS link -> grid walk + photos -> evidence -> advisory or Drone Didi."""
import asyncio
from collections import Counter
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.db.models import Case, DidiJob, Field, FieldOwner, Photo
from backend.app.db.session import SessionLocal as IvrSessionLocal
from backend.app.models.farmer import Farmer as IvrFarmer
from backend.app.services import (
    advisory,
    communications,
    didi,
    evidence,
    fields,
    vision,
)
from backend.app.services.communications import ivr_service
from backend.app.services.communications.registered_state_machine import (
    get_registered_flow_config,
)
from backend.app.services.events import emit
from backend.app.services.mapping import geo
from backend.app.services.vision import knn

TARGET_CELLS = 3          # grid cells the farmer is asked to walk to, worst first
DAMAGE_SEVERITY = 2       # PRD: zone = spots with severity >= 2
LEAF_KINDS = {"leaf_top", "leaf_under", "chewed"}
# Spoken cause names for the IVR (same as frontend/src/locales/hi.json "cause.*")
CAUSE_HI = {"yellow_mosaic": "पीला मोज़ेक", "fungal": "पत्तों का झुलसा", "chewing_damage": "इल्ली का नुकसान",
            "water_stress": "पानी की कमी या जलभराव", "nutrient": "खाद की कमी"}


class CaseNotFound(LookupError):
    pass


class CaseStateError(ValueError):
    """Action not possible in the case's current state (e.g. evidence before any field signal)."""


async def get_case(db: AsyncSession, case_id: int) -> Case:
    c = await db.get(Case, case_id)
    if c is None:
        raise CaseNotFound(case_id)
    return c


async def create(db: AsyncSession, field_id: str) -> Case:
    f = await fields.get_field(db, field_id)
    scan = await asyncio.to_thread(fields.scan, f)
    flagged = sorted((c for c in scan["cells"] if c["flagged"]), key=lambda c: min(c["z_ndvi"] or 0, c["z_ndre"] or 0))
    targets = [{"id": c["id"], "centre": c["centre"], "polygon": c["polygon"], "visited": False}
               for c in flagged[:TARGET_CELLS]]
    case = Case(field_id=f.id, target_cells=targets)
    db.add(case)
    await db.commit()
    await db.refresh(case)
    await emit(db, "case_created", case.id, field=f.id, targets=len(targets), scene=scan["scene_date"],
               flagged_acres=scan["summary"]["flagged_acres"])
    return case


def result_context(case: Case) -> dict | None:
    """What the IVR result call says about this case: cause, confidence, zone and dose, all from the evidence."""
    ev = case.evidence
    if not ev:
        return None
    spray = (ev.get("plan") or {}).get("spray")
    return {"name_hi": CAUSE_HI.get(ev["cause"], ev["name_hi"]), "pct": round(ev["confidence"] * 100), "acres": case.zone_acres,
            "action": ev["action"], "spray": {"quantity": spray["quantity"], "unit": spray["unit"]} if spray else None}


async def ivr_context(db: AsyncSession, phone: str) -> dict | None:
    case = await open_case_for_phone(db, phone)
    return result_context(case) if case else None


def _start_ivr_call(owner: FieldOwner, flow: str, context: dict | None = None) -> dict:
    """Place a registered-farmer call (warning / result) through the IVR in routes/ivr.py; return it with its first prompt."""
    db = IvrSessionLocal()
    try:
        phone = ivr_service.clean_phone_number(owner.phone)
        farmer = db.query(IvrFarmer).filter(IvrFarmer.phone == phone).first()
        if farmer is None:   # field owner known from the khasra map but never onboarded by phone
            farmer = IvrFarmer(phone=phone, name=owner.name, village=owner.village, status="registered")
            db.add(farmer)
        farmer.active_flow = flow
        db.commit()
        call = ivr_service.start_call(db, phone, flow)
        call["prompt"] = get_registered_flow_config(flow, call["step"], farmer, context)
        return call
    finally:
        db.close()


async def warning_call(db: AsyncSession, case: Case) -> dict:
    today = (await asyncio.to_thread(fields.risk, case.field))["days"][0]
    call = await asyncio.to_thread(_start_ivr_call, case.field.farmer, "warning")
    await emit(db, "call_placed", case.id, kind="warning", simulated=not settings.twilio_enabled,
               risk=today["score"], cause=today["top"])
    return call


async def result_call(db: AsyncSession, case: Case) -> dict:
    if not case.evidence:
        raise CaseStateError("no evidence yet")
    call = await asyncio.to_thread(_start_ivr_call, case.field.farmer, "result", result_context(case))
    await emit(db, "call_placed", case.id, kind="result", simulated=not settings.twilio_enabled)
    return call


async def followup_call(db: AsyncSession, case: Case) -> dict:
    """Day +5: "has it improved?" call after the spray."""
    call = await asyncio.to_thread(_start_ivr_call, case.field.farmer, "followup")
    await emit(db, "call_placed", case.id, kind="followup", simulated=not settings.twilio_enabled)
    return call


async def open_case_for_phone(db: AsyncSession, phone: str) -> Case | None:
    q = (select(Case).join(Field).join(FieldOwner).where(FieldOwner.phone == phone)
         .order_by(Case.id.desc()).limit(1))
    return (await db.execute(q)).scalars().first()


async def on_ivr_action(db: AsyncSession, phone: str, step: str, digit: str | None, action: str) -> None:
    """Side effects of a key press in the IVR's registered flows on the farmer's latest case."""
    case = await open_case_for_phone(db, phone)
    if case is None:
        return
    if digit is not None:
        await emit(db, "key_pressed", case.id, step=step, digit=digit)
    if action == "send_sms_link":
        await send_link(db, case)
    elif action == "confirm_drone_booking":
        try:
            await book_didi(db, case)
        except CaseStateError as exc:
            await emit(db, "booking_skipped", case.id, reason=str(exc))
    elif action in ("record_whitefly_yes", "record_whitefly_no"):
        await save_keypad(db, case, {"whitefly_under_leaves": action == "record_whitefly_yes"})
    elif action.startswith("record_feedback_"):
        await emit(db, "followup_recorded", case.id, feedback=action.removeprefix("record_feedback_"))


async def send_link(db: AsyncSession, case: Case) -> tuple[str, communications.SendResult]:
    url = communications.walk_link(case.id)
    body = f"FasalNetra: {case.field.farmer.name}, kheth ki photo ke liye yeh link kholiye: {url}"
    sent = communications.send_sms(case.field.farmer.phone, body)
    case.status = "link_sent"
    await db.commit()
    await emit(db, "sms_sent", case.id, simulated=sent.simulated, url=url)
    return url, sent


async def save_keypad(db: AsyncSession, case: Case, answers: dict[str, bool]) -> Case:
    case.keypad = {**case.keypad, **answers}
    await db.commit()
    await emit(db, "answer_saved", case.id, answers=answers)
    return case


async def save_traps(db: AsyncSession, case: Case, counts: list[int]) -> Case:
    case.trap_counts = counts
    await db.commit()
    await emit(db, "traps_counted", case.id, counts=counts, worst=max(counts))
    return case


async def add_photo(db: AsyncSession, case: Case, data: bytes, kind: str, spot: int, cell_id: str | None,
                    lat: float | None, lon: float | None) -> Photo:
    folder = settings.upload_dir / str(case.id)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{kind}_{spot}_{uuid4().hex[:8]}.jpg"
    path.write_bytes(data)

    result = await asyncio.to_thread(vision.classify, data)
    if knn.available():
        result["match"] = await asyncio.to_thread(knn.vote, data)
    photo = Photo(case_id=case.id, kind=kind, spot=spot, cell_id=cell_id, lat=lat, lon=lon,
                  path=str(path.relative_to(settings.upload_dir)), vision=result)
    db.add(photo)
    if cell_id:
        case.target_cells = [{**c, "visited": c["visited"] or c["id"] == cell_id} for c in case.target_cells]
    case.status = "collecting"
    await db.commit()
    await db.refresh(photo)
    await emit(db, "photo_received", case.id, kind=kind, spot=spot, cell=cell_id, label=result["label"],
               confidence=result["confidence"], retake=result["quality"]["retake_reason"])
    return photo


async def save_walk(db: AsyncSession, case: Case, trail: list[tuple[float, float]]) -> Case:
    zone_m = geo.zone_from_walk(trail, case.field.geometry)
    case.walk_trail = [list(p) for p in trail]
    if not zone_m.is_empty:
        case.zone = geo.to_wgs(zone_m)
        case.zone_acres = round(zone_m.area / geo.M2_PER_ACRE, 2)
    await db.commit()
    await emit(db, "zone_mapped", case.id, source="walk", acres=case.zone_acres)
    return case


def _photo_votes(photos: list[Photo]) -> tuple[dict | None, dict | None]:
    """Combine leaf photos: the label with most confidence mass wins; quality ok if any photo of it was sharp."""
    leaf = [p for p in photos if p.kind in LEAF_KINDS and p.vision.get("label") not in (None, "unsure")]
    if not leaf:
        return (None, None)
    mass = Counter()
    for p in leaf:
        mass[p.vision["label"]] += p.vision["confidence"]
    label = mass.most_common(1)[0][0]
    same = [p for p in leaf if p.vision["label"] == label]
    ai = {"label": label, "confidence": round(sum(p.vision["confidence"] for p in same) / len(same), 3),
          "quality": {"ok": any(p.vision["quality"]["ok"] for p in same)}}
    matches = [p.vision["match"] for p in leaf if p.vision.get("match")]
    match = None
    if matches:
        m = Counter(x["label"] for x in matches).most_common(1)[0][0]
        match = {"label": m, "confidence": round(sum(x["confidence"] for x in matches if x["label"] == m) / len(matches), 3)}
    return ai, match


async def build_evidence(db: AsyncSession, case: Case) -> Case:
    f = case.field
    photo_ai, photo_match = _photo_votes(case.photos)
    if not (photo_ai or case.keypad or case.trap_counts):
        raise CaseStateError("need at least one field signal: photo, keypad answer or trap count")

    if case.zone is None:   # no walk: zone = circles around damaged photo spots
        spots = [(p.lon, p.lat) for p in case.photos
                 if p.lon is not None and p.vision.get("severity", 0) >= DAMAGE_SEVERITY]
        zone_m = geo.zone_from_spots(spots, f.geometry, settings.spot_radius_m) if spots else None
        if zone_m is not None and not zone_m.is_empty:
            case.zone = geo.to_wgs(zone_m)
            case.zone_acres = round(zone_m.area / geo.M2_PER_ACRE, 2)

    scan = await asyncio.to_thread(fields.scan, f)
    weather_fit = await asyncio.to_thread(fields.weather_fit, f)
    das = (fields.today() - f.sowing_date).days
    ev = evidence.build(photo_ai=photo_ai, photo_match=photo_match, trap_counts=case.trap_counts or None,
                        keypad=case.keypad or None, weather_scores=weather_fit, das=das,
                        advisory_flags=fields.advisory_flags(), satellite=scan["summary"],
                        zone_acres=case.zone_acres or scan["summary"]["flagged_acres"])
    ev["savings"] = advisory.savings(f.area_acres, case.zone_acres or 0, ev["cause"],
                                     settings.pesticide_price_inr_per_unit)
    case.evidence = ev
    case.status = "evidence_ready"
    await db.commit()
    await emit(db, "evidence_ready", case.id, cause=ev["cause"], confidence=ev["confidence"], level=ev["level"],
               action=ev["action"])
    if ev["level"] == "high":
        nb = fields.neighbours_within(f)
        await emit(db, "neighbours_warned", case.id, cause=ev["cause"], count=len(nb), fields=nb[:5])
    return case


async def book_didi(db: AsyncSession, case: Case) -> DidiJob:
    if not case.evidence or not case.evidence.get("plan"):
        raise CaseStateError("no evidence / plan to book")
    if not case.evidence["plan"].get("spray"):
        raise CaseStateError("cause needs no pesticide")
    existing = (await db.execute(select(DidiJob).where(DidiJob.case_id == case.id,
                                                       DidiJob.status.not_in(["declined", "done"])))).scalar_one_or_none()
    if existing:
        return existing

    job = await didi.build_job(db, case, case.zone or _flagged_zone(case))
    await emit(db, "didi_booked", case.id, job=job.id, mode=job.mode, minutes=job.route["minutes"],
               best=job.window["best"])
    return job


def _flagged_zone(case: Case) -> dict:
    """Fallback zone: the satellite target cells the farmer was sent to."""
    from shapely.ops import unary_union
    cells = unary_union([geo.to_m(c["polygon"]) for c in case.target_cells])
    return geo.to_wgs(cells.intersection(geo.to_m(case.field.geometry)))
