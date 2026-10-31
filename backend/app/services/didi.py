"""Drone Didi side: her profile, tickets (jobs), spray schedule and what zone-only spraying saved.

Savings compare two real routes on the same field: the zone-only lawnmower route
and the route a whole-field spray would need. Battery and fuel use operator
constants from settings (an assumption until a Didi's own logbook replaces them).
"""
import asyncio
import json
from datetime import date, timedelta

from shapely.geometry import Point
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.db.models import Case, DidiJob, FieldOwner, Field
from backend.app.services import advisory, fields, missions
from backend.app.services.mapping import geo

FOLLOW_UP_DAYS = 3        # record step 7: check after 3-5 days whether it improved
DEMO_TICKETS = [          # neighbour fields that get a seeded ticket so the queue shows 2-3 farmers
    {"khasra": "119", "cause": "fungal", "confidence": 0.61, "level": "medium", "action": "didi_verify",
     "zone_frac": 0.35, "sowing_age_days": 44},
    {"khasra": "123", "cause": "chewing_damage", "confidence": 0.58, "level": "medium", "action": "didi_verify",
     "zone_frac": 0.25, "sowing_age_days": 38},
]


def profile() -> dict:
    return {
        "name": settings.didi_name, "shg": settings.didi_shg, "village": settings.didi_village,
        "drone": settings.didi_drone, "batteries_ready": settings.didi_batteries, "tank_l": settings.didi_tank_l,
        "base": [settings.didi_base_lon, settings.didi_base_lat],
    }


def savings(field_geom: dict, zone_geom: dict, cause: str, zone_route: dict) -> dict:
    """What spraying only the zone saved against spraying the whole field, from two planned routes."""
    full = missions.plan_route(field_geom, settings.drone_swath_m, 0.0, settings.drone_altitude_m)
    field_ha = geo.acres(field_geom) * advisory.HA_PER_ACRE
    zone_ha = geo.acres(zone_geom) * advisory.HA_PER_ACRE
    row = advisory.find(cause)
    chem = row["chemical"][0] if row and row["chemical"] else None
    water_per_ha = advisory.load_table()["water_l_per_ha"]["drone"]
    per_batt = settings.drone_minutes_per_battery

    def batteries(minutes: float) -> float:
        return round(minutes / per_batt, 1)

    full_b, zone_b = batteries(full["minutes"]), batteries(zone_route["minutes"])
    saved_b = round(max(full_b - zone_b, 0.0), 1)
    return {
        "pesticide": {"saved": round(chem["dose_per_ha"] * (field_ha - zone_ha), 1) if chem else 0.0,
                      "used": round(chem["dose_per_ha"] * zone_ha, 1) if chem else 0.0,
                      "unit": chem["unit"] if chem else None},
        "water_l": {"saved": round(water_per_ha * (field_ha - zone_ha), 1), "used": round(water_per_ha * zone_ha, 1)},
        "flight_min": {"saved": round(full["minutes"] - zone_route["minutes"], 1), "used": zone_route["minutes"]},
        "battery": {"saved": saved_b, "used": zone_b, "unit": "charges"},
        "fuel_l": {"saved": round(saved_b * settings.generator_litres_per_charge, 2),
                   "used": round(zone_b * settings.generator_litres_per_charge, 2),
                   "note": f"generator petrol, {settings.generator_litres_per_charge} L per battery charge (assumed)"},
        "acres_not_sprayed": round((field_ha - zone_ha) / advisory.HA_PER_ACRE, 2),
        "full_field_minutes": full["minutes"],
    }


def schedule(cause: str, mode: str, window: dict, today: date) -> list[dict]:
    """Visits for this ticket: first visit at the best slot, a check after 3 days, a repeat spray if the advisory says so."""
    first_day = date.fromisoformat(window["date"]) if window.get("date") else today
    first_time = (window.get("best") or f"{first_day}T06:00")[11:16]
    sessions = [{
        "date": str(first_day), "time": first_time,
        "kind": "spray" if mode == "spray" else "verify_then_spray",
        "note_hi": "छिड़काव" if mode == "spray" else "पहले जाँच, बीमारी हो तो छिड़काव",
        "note_en": "Spray the zone" if mode == "spray" else "Check the zone, spray if confirmed",
    }]
    sessions.append({
        "date": str(first_day + timedelta(days=FOLLOW_UP_DAYS)), "time": "07:00", "kind": "check",
        "note_hi": "जाँच: सुधार हुआ या नहीं", "note_en": "Check whether the patch improved",
    })
    row = advisory.find(cause)
    if row and row.get("repeat_after_days"):
        d = row["repeat_after_days"][0]
        sessions.append({
            "date": str(first_day + timedelta(days=d)), "time": first_time, "kind": "repeat_spray",
            "note_hi": f"दूसरा छिड़काव, अगर ज़रूरत हो ({d} दिन बाद)",
            "note_en": f"Second spray if still needed ({d} days later, per advisory)",
        })
    return sessions


async def build_job(db: AsyncSession, case: Case, zone: dict) -> DidiJob:
    ev = case.evidence
    route = await asyncio.to_thread(missions.plan_route, zone, settings.drone_swath_m, settings.zone_buffer_m,
                                    settings.drone_altitude_m)
    route["zone"] = zone
    window = await asyncio.to_thread(fields.spray_window, case.field)
    mode = "spray" if ev["action"] == "advise_spray" else "verify_then_spray"
    job = DidiJob(case_id=case.id, mode=mode, status="new", plan=ev["plan"], route=route, window=window,
                  schedule=schedule(ev["cause"], mode, window, fields.today()),
                  savings=await asyncio.to_thread(savings, case.field.geometry, zone, ev["cause"], route))
    db.add(job)
    case.status = "didi_booked"
    await db.commit()
    await db.refresh(job)
    missions.waypoints_file(route, settings.waypoints_dir / f"job_{job.id}.waypoints")
    return job


def ticket(job: DidiJob) -> dict:
    """Everything the ticket card and detail need about the farmer, field and problem."""
    case, f = job.case, job.case.field
    ev = case.evidence or {}
    row = advisory.find(ev.get("cause", "")) or {}
    base = profile()["base"]
    dist_km = geo.to_m({"type": "Point", "coordinates": base}).distance(
        geo.to_m({"type": "Point", "coordinates": [f.centroid_lon, f.centroid_lat]})) / 1000
    return {
        "farmer": f.farmer.name, "village": f.farmer.village, "khasra": f.khasra,
        "crop_days": (fields.today() - f.sowing_date).days, "field": f.geometry, "field_acres": f.area_acres,
        "cause": ev.get("cause"), "confidence": ev.get("confidence"), "level": ev.get("level"),
        "symptoms": row.get("symptoms_hi") or row.get("symptoms", []), "symptoms_en": row.get("symptoms", []),
        "name_en": row.get("name_en"), "name_hi": row.get("name_hi"),
        "distance_km": round(dist_km, 1),
    }


async def seed_demo_tickets(db: AsyncSession) -> None:
    """Two more farmers in the queue (neighbour fields, clearly demo data), so Didi has 2-3 tickets."""
    if not settings.demo_mode:
        return
    data = json.loads(settings.demo_field_geojson.read_text(encoding="utf-8"))
    by_khasra = {x["properties"]["khasra"]: x for x in data["features"] if x["properties"].get("role") == "neighbour"}
    for spec in DEMO_TICKETS:
        feat = by_khasra.get(spec["khasra"])
        if feat is None:
            continue
        fid = f"demo-{spec['khasra'].replace('/', '-')}"
        if (await db.execute(select(Case).where(Case.field_id == fid))).first():
            continue
        p = feat["properties"]
        if await db.get(Field, fid) is None:
            farmer = FieldOwner(name=p["owner"], phone=f"+91000000{spec['khasra'].replace('/', '')[:4]:0>4}", village="Rampura")
            db.add(farmer)
            await db.flush()
            c = geo.to_m(feat["geometry"]).centroid
            wgs = geo.to_wgs(c)["coordinates"]
            db.add(Field(id=fid, farmer_id=farmer.id, khasra=p["khasra"], crop="soybean",
                         sowing_date=fields.today() - timedelta(days=spec["sowing_age_days"]),
                         area_acres=round(geo.acres(feat["geometry"]), 2), geometry=feat["geometry"],
                         centroid_lat=wgs[1], centroid_lon=wgs[0]))
            await db.flush()
        field_m = geo.to_m(feat["geometry"])
        r = (field_m.area * spec["zone_frac"] / 3.1416) ** 0.5
        zone_m = Point(field_m.centroid.coords[0]).buffer(r).intersection(field_m)
        zone = geo.to_wgs(zone_m)
        zone_acres = round(zone_m.area / geo.M2_PER_ACRE, 2)
        plan = advisory.spray_plan(spec["cause"], zone_acres)
        case = Case(field_id=fid, status="evidence_ready", zone=zone, zone_acres=zone_acres, evidence={
            "cause": spec["cause"], "confidence": spec["confidence"], "level": spec["level"], "action": spec["action"],
            "plan": plan, "demo_seed": True, "signals": [], "agreeing_signals": [], "spray_allowed": False,
        })
        db.add(case)
        await db.commit()
        await db.refresh(case, attribute_names=["field"])
        await build_job(db, case, zone)
