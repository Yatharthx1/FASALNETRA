"""Field-level facade over the risk engine, satellite scout and spray-weather window.

Demo mode replays the 2025 Mandsaur season from the Open-Meteo archive as if
the demo date were today; otherwise the live 16-day forecast is used.
"""
import json
from datetime import date, timedelta

from shapely.geometry import shape
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.db.models import Field, FieldOwner
from backend.app.services.advisory import combined_score, soybean, weather_factors
from backend.app.services.mapping import geo, satellite
from backend.app.services.risk import rules, surge, weather

FORECAST_DAYS = 15
SPRAY_MAX_WIND_KMH = 10.0
SPRAY_MAX_RAIN_MM = 0.2


class FieldNotFound(LookupError):
    pass


def today() -> date:
    return settings.demo_date if settings.demo_mode else date.today()


async def get_field(db: AsyncSession, field_id: str) -> Field:
    f = await db.get(Field, field_id)
    if f is None:
        raise FieldNotFound(field_id)
    return f


def _season_days(f: Field) -> list[dict]:
    if settings.demo_mode:
        y = settings.demo_date.year
        return weather.season(f.centroid_lat, f.centroid_lon, date(y, 6, 1), date(y, 10, 15))
    return weather.outlook(f.centroid_lat, f.centroid_lon)


def risk(f: Field) -> dict:
    scored = rules.score_days(_season_days(f), f.sowing_date, advisory_flags=advisory_flags())
    start = str(today())
    days = [d for d in scored if d["date"] >= start][:FORECAST_DAYS]
    return {"field_id": f.id, "mode": "replay" if settings.demo_mode else "forecast",
            "rule_status": rules.RULES["yellow_mosaic"]["status"], "days": days}


def surge_outlook(f: Field) -> dict:
    """Next surge per pest over the forecast days, with the seasonal calendar behind it."""
    return {"field_id": f.id, **surge.outlook(risk(f)["days"], today())}


def weather_fit(f: Field) -> dict[str, float]:
    scored = rules.score_days(_season_days(f), f.sowing_date)
    return rules.weather_vote(scored, str(today()))


def advisory_flags() -> dict[str, bool]:
    """Which pests this week's ICAR-NSRI advisory warns about. Demo: the Aug 2025 YMV/whitefly advisory."""
    return {"yellow_mosaic": True} if settings.demo_mode else {}


def _scan_source(f: Field) -> str:
    """Satellite cache to read. Fields resolved from an IVR onboarding share the demo cache (khasra lookup is mocked)."""
    return f.id if (satellite.PROCESSED / f.id / "meta.json").exists() else "demo"


def scan(f: Field) -> dict:
    return {"field_id": f.id, **satellite.scan(_scan_source(f), f.geometry, today())}


def demo_walk(f: Field) -> list[tuple[float, float]]:
    """Points around the flagged cells, as a farmer walking the patch edge would record them."""
    from shapely.ops import unary_union
    flagged = [geo.to_m(c["polygon"]) for c in scan(f)["cells"] if c["flagged"]]
    if not flagged:
        return []
    hull = unary_union(flagged).convex_hull.intersection(geo.to_m(f.geometry))
    ring = geo.to_wgs(hull)["coordinates"][0]
    return [tuple(p) for p in ring[:-1]]


def combined_advisory(f: Field) -> dict:
    """Fuses Sentinel-2 satellite anomaly data with local weather factors into a combined score."""
    scan_res = scan(f)
    days = _season_days(f)
    cur_today = today()
    start_str = str(cur_today - timedelta(days=7))
    end_str = str(cur_today)
    window_days = [d for d in days if start_str <= d["date"] <= end_str]
    if not window_days:
        window_days = [d for d in days if d["date"] <= end_str][-7:]
    das = (cur_today - f.sowing_date).days

    next_day = cur_today + timedelta(days=1)
    if settings.demo_mode:
        hourly = weather.hourly_archive(f.centroid_lat, f.centroid_lon, next_day, next_day)
    else:
        hourly = weather.hourly_forecast(f.centroid_lat, f.centroid_lon)

    res = combined_score.compute_combined_advisory(
        satellite_scan=scan_res,
        weather_days=window_days,
        das=das,
        crop_type=f.crop or "soybean",
        hourly_weather=hourly,
        target_date=next_day,
    )
    return {"field_id": f.id, **res}


def soybean_profile(f: Field) -> dict:
    """Specialized ICAR-IISR soybean phenology, growth stage, ETL, and nutrition profile."""
    das = (today() - f.sowing_date).days
    days = _season_days(f)
    cur_today = today()
    start_str = str(cur_today - timedelta(days=7))
    end_str = str(cur_today)
    window_days = [d for d in days if start_str <= d["date"] <= end_str]
    if not window_days:
        window_days = [d for d in days if d["date"] <= end_str][-7:]
    profile = soybean.get_soybean_profile(das=das, weather_days=window_days)
    return {"field_id": f.id, **profile}


def spray_window(f: Field, hours: int = 12) -> dict:
    """Hours in the next half-day when spraying is safe (no rain, low wind), starting 6 am the day after booking."""
    start = today() + timedelta(days=1)
    if settings.demo_mode:
        h = weather.hourly_archive(f.centroid_lat, f.centroid_lon, start, start)
    else:
        h = weather.hourly_forecast(f.centroid_lat, f.centroid_lon)
    slots = []
    for i, t in enumerate(h["time"]):
        if not t.startswith(str(start)) or not 6 <= int(t[11:13]) < 6 + hours:
            continue
        wind = (h.get("wind_speed_10m") or [None] * len(h["time"]))[i]
        rain = h["precipitation"][i] or 0.0
        slots.append({"time": t, "rain_mm": round(rain, 1), "wind_kmh": None if wind is None else round(wind, 1),
                      "ok": rain <= SPRAY_MAX_RAIN_MM and (wind is None or wind <= SPRAY_MAX_WIND_KMH)})
    ok = [s for s in slots if s["ok"]]

    # Advanced agrometeorological feasibility factor
    feasibility = weather_factors.evaluate_spray_feasibility(h, start, start_hour=6, duration_hours=hours)

    return {
        "date": str(start),
        "slots": slots,
        "best": ok[0]["time"] if ok else None,
        "rule": f"rain <= {SPRAY_MAX_RAIN_MM} mm/h, wind <= {SPRAY_MAX_WIND_KMH:.0f} km/h",
        "suitability": feasibility["overall_suitability"],
        "advisory_hi": feasibility["advisory_hi"],
        "advisory_en": feasibility["advisory_en"],
        "mean_wind_kmh": feasibility["mean_wind_kmh"],
    }


def neighbours_within(f: Field, metres: float = 500) -> list[dict]:
    """Soybean neighbours of the demo field to warn when a case is confirmed."""
    data = json.loads(settings.demo_field_geojson.read_text(encoding="utf-8"))
    me = geo.to_m(f.geometry).centroid
    out = []
    for feat in data["features"]:
        p = feat["properties"]
        if p.get("role") != "neighbour" or p.get("recorded_crop") != "Soybean":
            continue
        d = geo.to_m(feat["geometry"]).centroid.distance(me)
        if d <= metres:
            out.append({"khasra": p["khasra"], "owner": p["owner"], "distance_m": round(d)})
    return sorted(out, key=lambda x: x["distance_m"])


# IVR sowing-date answer -> days since sowing (middle of the bracket)
SOWING_AGE_DAYS = {"under_15": 10, "15_30": 22, "30_60": 45, "over_60": 70}


def _hero() -> dict:
    data = json.loads(settings.demo_field_geojson.read_text(encoding="utf-8"))
    return next(x for x in data["features"] if x["properties"].get("role") == "hero")


async def field_for_onboarded(db: AsyncSession, phone: str, answers: dict) -> Field:
    """IVR onboarding (pincode + village) -> the farmer's land parcel.

    Production: village cadastral map / AgriStack lookup with consent. Hackathon: there is no open khasra API,
    so every onboarded farmer gets the demo parcel (the only one with cached Sentinel-2), under their own name,
    crop and sowing date. An existing field for the phone is reused.
    """
    owner = (await db.execute(select(FieldOwner).where(FieldOwner.phone == phone))).scalar_one_or_none()
    if owner is not None:
        existing = (await db.execute(select(Field).where(Field.farmer_id == owner.id))).scalars().first()
        if existing is not None:
            return existing
    village = str(answers.get("village") or "")
    if owner is None:
        owner = FieldOwner(name="किसान भाई", phone=phone, language=answers.get("welcome", "hi"),
                           village=village.split(" (")[0] or "-")
        db.add(owner)
        await db.flush()
    hero = _hero()
    c = shape(hero["geometry"]).centroid
    age = SOWING_AGE_DAYS.get(answers.get("sowing_date", ""), settings.demo_sowing_age_days)
    crop = answers.get("crop") if answers.get("crop") not in (None, "other", "pata_nahi") else "soybean"
    f = Field(id=f"ivr-{phone.lstrip('+')[-10:]}", farmer_id=owner.id, khasra=hero["properties"]["khasra"], crop=crop,
              sowing_date=today() - timedelta(days=age), area_acres=round(geo.acres(hero["geometry"]), 2),
              geometry=hero["geometry"], centroid_lat=c.y, centroid_lon=c.x)
    db.add(f)
    await db.commit()
    return await get_field(db, f.id)


async def seed_demo(db: AsyncSession) -> None:
    existing = await db.get(Field, "demo")
    if existing:
        if existing.farmer.phone != settings.demo_farmer_phone:   # DEMO_FARMER_PHONE changed: calls go to the new phone
            existing.farmer.phone = settings.demo_farmer_phone
            await db.commit()
        return
    data = json.loads(settings.demo_field_geojson.read_text(encoding="utf-8"))
    hero = next(x for x in data["features"] if x["properties"].get("role") == "hero")
    p = hero["properties"]
    farmer = (await db.execute(select(FieldOwner).where(FieldOwner.phone == settings.demo_farmer_phone))).scalar_one_or_none()
    if farmer is None:
        farmer = FieldOwner(name=settings.demo_farmer_name, phone=settings.demo_farmer_phone, village="Rampura")
        db.add(farmer)
        await db.flush()
    c = shape(hero["geometry"]).centroid
    db.add(Field(id="demo", farmer_id=farmer.id, khasra=p["khasra"], crop="soybean",
                 sowing_date=settings.demo_date - timedelta(days=settings.demo_sowing_age_days),
                 area_acres=round(geo.acres(hero["geometry"]), 2), geometry=hero["geometry"],
                 centroid_lat=c.y, centroid_lon=c.x))
    await db.commit()
