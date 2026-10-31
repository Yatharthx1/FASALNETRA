"""Case workflow: warning call (IVR) -> SMS link -> grid walk + photos -> evidence -> advisory or Drone Didi."""
import asyncio
from collections import Counter
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.db.models import Case, DidiJob, Event, Field, FieldOwner, GpsFix, Photo
from backend.app.db.session import SessionLocal as IvrSessionLocal
from backend.app.models.farmer import Farmer as IvrFarmer
from backend.app.models.ivr_session import IVRSession
from backend.app.services import (
    advisory,
    communications,
    didi,
    evidence,
    fields,
    vision,
)
from backend.app.services.advisory import knowledge, writer
from backend.app.services.communications import ivr_service
from backend.app.services.communications.registered_state_machine import (
    get_registered_flow_config,
)
from backend.app.services.events import emit
from backend.app.services.mapping import geo, parcels, targets
from backend.app.services.risk import seasonality
from backend.app.services.vision import kindwise, knn
from backend.app.services.vision import local as local_model

TARGET_CELLS = 3          # grid cells the farmer is asked to walk to, worst first
DAMAGE_SEVERITY = 2       # PRD: zone = spots with severity >= 2
LEAF_KINDS = {"leaf_top", "leaf_under", "chewed"}
# Spoken cause names for the IVR (same as frontend/src/locales/hi.json "cause.*")
CAUSE_HI = {"yellow_mosaic": "पीला मोज़ेक", "fungal": "पत्तों का झुलसा", "chewing_damage": "इल्ली का नुकसान",
            "girdle_beetle": "गर्डल बीटल (चक्र भृंग)",
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


def field_profile(phone: str) -> dict | None:
    """Neighbour crop and grassy border from the farmer's IVR onboarding (None if never onboarded by phone)."""
    db = IvrSessionLocal()
    try:
        farmer = db.query(IvrFarmer).filter(IvrFarmer.phone == ivr_service.clean_phone_number(phone)).first()
        if farmer is None or not (farmer.neighbor_crop or farmer.grassy_border):
            return None
        return {"neighbor_crop": farmer.neighbor_crop, "grassy_border": farmer.grassy_border}
    finally:
        db.close()


async def create(db: AsyncSession, field_id: str) -> Case:
    f = await fields.get_field(db, field_id)
    scan = await asyncio.to_thread(fields.scan, f)
    profile = await asyncio.to_thread(field_profile, f.farmer.phone)
    stops = await asyncio.to_thread(targets.pick, scan["cells"], f.geometry, profile, TARGET_CELLS)
    case = Case(field_id=f.id, target_cells=stops)
    db.add(case)
    await db.commit()
    await db.refresh(case)
    await emit(db, "case_created", case.id, field=f.id, targets=len(stops), scene=scan["scene_date"],
               reasons=[s["reason"] for s in stops],
               flagged_acres=scan["summary"]["flagged_acres"])
    return case


def result_context(case: Case) -> dict | None:
    """What the IVR result call says about this case: cause, confidence, zone and dose, all from the evidence."""
    ev = case.evidence
    if not ev:
        return None
    spray = (ev.get("plan") or {}).get("spray")
    return {"name_hi": CAUSE_HI.get(ev["cause"], ev["name_hi"]), "pct": round(ev["confidence"] * 100), "acres": case.zone_acres,
            "action": ev["action"], "spray": {"quantity": spray["quantity"], "unit": spray["unit"]} if spray else None,
            "say_hi": (ev.get("advisory") or {}).get("say_hi")}


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


OPEN_STATUSES = ("warned", "link_sent", "collecting")   # case still waiting for photos


async def _case_for_report(db: AsyncSession, phone: str) -> Case | None:
    """Farmer called in about a problem: reuse a case still waiting for photos, else open a new one."""
    latest = await open_case_for_phone(db, phone)
    if latest is not None and latest.status in OPEN_STATUSES:
        return latest
    field = (await db.execute(select(Field).join(FieldOwner).where(FieldOwner.phone == phone))).scalars().first()
    if field is None:   # registered by phone but no mapped field yet
        return None
    case = await create(db, field.id)
    await emit(db, "farmer_reported", case.id, phone=phone)
    return case


async def on_ivr_action(db: AsyncSession, phone: str, step: str, digit: str | None, action: str) -> None:
    """Side effects of a key press in the IVR's registered flows on the farmer's latest case."""
    if action.startswith("report_symptom_"):
        case = await _case_for_report(db, phone)
    else:
        case = await open_case_for_phone(db, phone)
    if case is None:
        return
    if digit is not None:
        await emit(db, "key_pressed", case.id, step=step, digit=digit)
    if action.startswith("report_symptom_"):
        symptom = action.removeprefix("report_symptom_")
        if symptom != "unknown":
            await save_keypad(db, case, {symptom: True})
        await send_link(db, case)
    elif action == "send_sms_link":
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
    if sent.error:   # link still shown on the dashboard ("Open walk page") so the walk can go on
        await emit(db, "sms_failed", case.id, url=url, error=sent.error[:200])
    else:
        await emit(db, "sms_sent", case.id, simulated=sent.simulated, url=url, channel=settings.sms_channel)
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
    if result["quality"]["ok"] and kindwise.available():   # costs a credit: only for photos we keep
        result["expert"] = await asyncio.to_thread(kindwise.classify, data, lat, lon)
    # second, independent vote: the trained offline model next to the LLM, else the CLIP neighbours
    if vision.provider() == "gemini" and local_model.head_trained():
        result["match"] = await asyncio.to_thread(local_model.classify, data)
    elif knn.available():
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


def _expert_vote(photos: list[Photo]) -> dict | None:
    """Kindwise answers over the leaf photos: the label with most probability mass, its mean probability."""
    answers = [p.vision["expert"] for p in photos
               if p.kind in LEAF_KINDS and p.vision.get("expert") and p.vision["expert"]["label"] != "unsure"]
    if not answers:
        return None
    mass = Counter()
    for a in answers:
        mass[a["label"]] += a["confidence"]
    label = mass.most_common(1)[0][0]
    return {"label": label, "confidence": round(mass[label] / len(answers), 3)}


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
                        zone_acres=case.zone_acres or scan["summary"]["flagged_acres"],
                        field_profile=await asyncio.to_thread(field_profile, f.farmer.phone),
                        photo_expert=_expert_vote(case.photos), season=seasonality.season_vote(fields.today()))
    ev["savings"] = advisory.savings(f.area_acres, case.zone_acres or 0, ev["cause"],
                                     settings.pesticide_price_inr_per_unit)
    await asyncio.to_thread(_route, ev, f, das, case.zone_acres or scan["summary"]["flagged_acres"])
    try:
        ev["combined_advisory"] = await asyncio.to_thread(fields.combined_advisory, f)
    except Exception:
        ev["combined_advisory"] = None

    case.evidence = ev
    case.status = "evidence_ready"
    await db.commit()
    await emit(db, "evidence_ready", case.id, cause=ev["cause"], confidence=ev["confidence"], level=ev["level"],
               action=ev["action"])
    if ev["level"] == "high":
        nb = fields.neighbours_within(f)
        await emit(db, "neighbours_warned", case.id, cause=ev["cause"], count=len(nb), fields=nb[:5])
    # The advisory is spoken, not only shown: if the farmer is still on the live call it is said there
    # (see live_tick); otherwise call back. Key 1 books Drone Didi (spray, or her check when not sure).
    if not await asyncio.to_thread(live_holding, case.field.farmer.phone):
        await result_call(db, case)
    return case


def _route(ev: dict, f: Field, das: int, zone_acres: float) -> None:
    """High confidence on a crop we have a knowledge pack for: our advisory goes to the farmer. Anything less, or
    a crop without a pack (no vetted doses for it): Drone Didi checks the field first."""
    if not knowledge.supported(f.crop):
        if ev["action"] in ("advise_spray", "advise_no_pesticide"):
            ev.update(action="didi_verify", spray_allowed=False)
        ev.update(route="drone_didi", route_reason=f"no knowledge pack for {f.crop}")
        return
    if ev["level"] != "high":
        ev.update(route="drone_didi" if ev["action"] == "didi_verify" else "expert",
                  route_reason=f"confidence {ev['level']}")
        return
    try:
        window = fields.spray_window(f)
    except (OSError, ValueError, KeyError):
        window = None
    facts = knowledge.build_facts(crop=f.crop, evidence=ev, das=das, zone_acres=zone_acres, field_acres=f.area_acres,
                                  spray_window=window, profile=field_profile(f.farmer.phone))
    ev.update(route="advisory", advisory=writer.write(facts))


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


# --- Live call: the farmer stays on the line while the camera page runs -------------------------------------

LIVE_TICK_S = 6              # pause between checks while the farmer walks
LIVE_MAX_TICKS = 50          # ~5 minutes on hold, then hang up and call back with the result
LIVE_STALE = timedelta(minutes=8)
LINK_REMIND_TICKS = (4, 12, 24)


def _utcnow_naive() -> datetime:
    """IVR session timestamps are naive UTC (models/ivr_session.py)."""
    return datetime.now(UTC).replace(tzinfo=None)


def live_holding(phone: str) -> bool:
    """Is a call to this phone holding on the line right now (link sent, waiting for photos)?"""
    db = IvrSessionLocal()
    try:
        s = db.query(IVRSession).filter(IVRSession.phone == ivr_service.clean_phone_number(phone)).first()
        return (s is not None and s.current_step == "sms_dispatched" and s.status == "in_progress"
                and s.updated_at is not None and _utcnow_naive() - s.updated_at < LIVE_STALE)
    finally:
        db.close()


async def link_opened(db: AsyncSession, case: Case) -> None:
    await emit(db, "link_opened", case.id)


async def _was_opened(db: AsyncSession, case_id: int) -> bool:
    q = select(Event.id).where(Event.case_id == case_id, Event.type == "link_opened").limit(1)
    return (await db.execute(q)).first() is not None


def _photo_line(p: Photo, first_ok: bool) -> str:
    retake = p.vision.get("quality", {}).get("retake_reason")
    if retake:
        return "फोटो में अंधेरा है, रोशनी की तरफ मुड़कर फिर से लीजिए।" if retake == "dark"             else "फोटो धुंधली है। फोन स्थिर रखिए और पत्ते के पास से फिर लीजिए।"
    adv = p.vision.get("advice")
    if first_ok and adv and p.vision.get("label") not in ("healthy", "unsure"):
        return f"फोटो मिल गई। पहली जांच में {CAUSE_HI.get(adv['cause'], adv['name_hi'])} का शक है। बाकी निशानों की फोटो भी लीजिए।"
    return "फोटो मिल गई, साफ है।"


async def live_tick(db: AsyncSession, phone: str, state: dict) -> tuple[str, str, dict]:
    """One check while the farmer holds: what to say now. Returns (kind, hindi text, new state);
    kind is "wait" (say it, pause, check again), "result" (evidence ready: play the result prompt) or "end"."""
    state = {**state, "live_ticks": state.get("live_ticks", 0) + 1}
    case = await open_case_for_phone(db, phone)
    if case is None:
        return "end", "धन्यवाद। फोटो मिलने पर हम आपको कॉल करेंगे।", state
    if case.evidence:
        return "result", "", state

    lines: list[str] = []
    if not state.get("opened_said") and await _was_opened(db, case.id):
        state["opened_said"] = True
        lines.append("लिंक खुल गया। कैमरा चालू होगा, लाल लाइन के साथ पहले निशान तक चलिए।")
    leaf = [p for p in case.photos if p.kind in LEAF_KINDS]
    said = state.get("photos_said", 0)
    for p in leaf[said:]:
        ok = not p.vision.get("quality", {}).get("retake_reason")
        lines.append(_photo_line(p, ok and not state.get("cause_said")))
        state["cause_said"] = state.get("cause_said") or (ok and p.vision.get("label") not in ("healthy", "unsure"))
    state["photos_said"] = len(leaf)

    if state["live_ticks"] >= LIVE_MAX_TICKS:
        return "end", "कोई बात नहीं। फोटो भेजने के बाद हम आपको जांच का नतीजा बताने के लिए कॉल करेंगे। धन्यवाद।", state
    if not leaf and not state.get("opened_said") and state["live_ticks"] in LINK_REMIND_TICKS:
        lines.append(f"आपके फोन पर {settings.link_channel_hi} में फसलनेत्र का लिंक आया है। उसे दबाइए। कॉल चालू रखिए।")
    return "wait", " ".join(lines), state


async def on_onboarded(db: AsyncSession, phone: str, answers: dict) -> Case | None:
    """IVR onboarding done -> resolve the land parcel -> Sentinel-2 grid -> walk targets -> SMS camera link."""
    try:
        f = await fields.field_for_onboarded(db, phone, answers)
        case = await _case_for_report(db, phone) or await create(db, f.id)
    except (ValueError, OSError) as exc:   # no satellite scene / cache for this field
        await emit(db, "onboarding_unmapped", None, phone=phone, reason=str(exc))
        return None
    await emit(db, "farmer_onboarded", case.id, phone=phone, village=answers.get("village"),
               neighbor_crop=answers.get("neighbor_crop"), grassy_border=answers.get("grass_border"))
    await send_link(db, case)
    return case


# --- Phone GPS: 5 Hz fused track from the walk page, and which parcel the farmer is standing in ---------------

async def save_track(db: AsyncSession, case: Case, points: list[dict]) -> tuple[int, int]:
    db.add_all(GpsFix(case_id=case.id, t_ms=p["t"], lat=p["lat"], lon=p["lon"], accuracy_m=p["accuracy"],
                      heading=p.get("heading"), speed=p.get("speed"), source=p.get("source", "gps")) for p in points)
    await db.commit()
    total = (await db.execute(select(func.count()).select_from(GpsFix).where(GpsFix.case_id == case.id))).scalar_one()
    return len(points), total


async def locate_farmer(db: AsyncSession, case: Case, lon: float, lat: float, accuracy: float) -> dict:
    """Is the farmer at their mapped field? Logged once per change, so the dashboard sees a wrong parcel on record."""
    where = parcels.locate(lon, lat, case.field.geometry, accuracy)
    last = (await db.execute(select(Event).where(Event.case_id == case.id, Event.type == "farmer_located")
                             .order_by(Event.id.desc()).limit(1))).scalars().first()
    if last is None or last.payload.get("status") != where["status"]:
        await emit(db, "farmer_located", case.id, status=where["status"], distance_m=where["distance_m"],
                   khasra=(where["parcel"] or {}).get("khasra"), mapped=where["parcel_is_mapped_field"])
    return where
