"""Case workflow: warning -> keypad -> SMS link -> grid walk + photos -> evidence -> advisory or Drone Didi."""
import asyncio
from collections import Counter
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.db.models import Case, DidiJob, Photo
from backend.app.services import advisory, communications, didi, evidence, fields, vision
from backend.app.services.communications import ivr
from backend.app.services.events import emit
from backend.app.services.mapping import geo
from backend.app.services.vision import knn

TARGET_CELLS = 3          # grid cells the farmer is asked to walk to, worst first
DAMAGE_SEVERITY = 2       # PRD: zone = spots with severity >= 2
LEAF_KINDS = {"leaf_top", "leaf_under", "chewed"}


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


def _ivr_context(case: Case, risk_today: dict | None) -> dict:
    ctx = {"farmer_name": case.field.farmer.name, "zone_acres": case.zone_acres, "evidence": case.evidence}
    if risk_today:
        top = risk_today["top"]
        ctx["risk"] = {"cause": top, "drivers": risk_today["causes"][top]["drivers"]}
    return ctx


async def warning_call(db: AsyncSession, case: Case) -> tuple[communications.SendResult, ivr.Prompt]:
    r = await asyncio.to_thread(fields.risk, case.field)
    first = ivr.warning(_ivr_context(case, r["days"][0]))
    sent = communications.place_call(case.field.farmer.phone, case.id, "warning")
    await emit(db, "call_placed", case.id, kind="warning", simulated=sent.simulated,
               risk=r["days"][0]["score"], cause=r["days"][0]["top"])
    return sent, first


async def result_call(db: AsyncSession, case: Case) -> tuple[communications.SendResult, ivr.Prompt]:
    if not case.evidence:
        raise CaseStateError("no evidence yet")
    first = ivr.result(_ivr_context(case, None))
    sent = communications.place_call(case.field.farmer.phone, case.id, "result")
    await emit(db, "call_placed", case.id, kind="result", simulated=sent.simulated)
    return sent, first


async def ivr_step(db: AsyncSession, case: Case, step: str, digit: str | None) -> ivr.Prompt:
    risk_today = None
    if step == "warning" or step.startswith("q"):
        risk_today = (await asyncio.to_thread(fields.risk, case.field))["days"][0]
    prompt = ivr.handle(_ivr_context(case, risk_today), step, digit)
    if digit is not None:
        await emit(db, "key_pressed", case.id, step=step, digit=digit)
    if prompt.answers:
        case.keypad = {**case.keypad, **prompt.answers}
        await db.commit()
        await emit(db, "answer_saved", case.id, answers=prompt.answers)
    for action in prompt.actions:
        if action == "send_link":
            await send_link(db, case)
        elif action == "book_didi":
            await book_didi(db, case)
        elif action == "send_dose_sms":
            await send_dose_sms(db, case)
        elif action == "transfer_human":
            await emit(db, "human_requested", case.id, step=step)
    return prompt


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


async def send_dose_sms(db: AsyncSession, case: Case) -> None:
    s = case.evidence["plan"]["spray"]
    plan = advisory.spray_plan(case.evidence["cause"], case.zone_acres or 0.1, method="knapsack")["spray"]
    body = (f"FasalNetra ({case.evidence['plan']['source']}): {s['product']}. Sirf {case.zone_acres} acre: "
            f"{plan['quantity']} {plan['unit']} dawa, {plan['water_l']} L paani ({plan['knapsack_tanks']} tanki). "
            f"Dastane aur mask pehniye.")
    sent = communications.send_sms(case.field.farmer.phone, body)
    await emit(db, "sms_sent", case.id, kind="dose", simulated=sent.simulated)


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
