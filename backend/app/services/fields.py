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
from backend.app.db.models import Farmer, Field
from backend.app.services.mapping import geo, satellite
from backend.app.services.risk import rules, weather

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


def weather_fit(f: Field) -> dict[str, float]:
    scored = rules.score_days(_season_days(f), f.sowing_date)
    return rules.weather_vote(scored, str(today()))


def advisory_flags() -> dict[str, bool]:
    """Which pests this week's ICAR-NSRI advisory warns about. Demo: the Aug 2025 YMV/whitefly advisory."""
    return {"yellow_mosaic": True} if settings.demo_mode else {}


def scan(f: Field) -> dict:
    return {"field_id": f.id, **satellite.scan(f.id, f.geometry, today())}


def demo_walk(f: Field) -> list[tuple[float, float]]:
    """Points around the flagged cells, as a farmer walking the patch edge would record them."""
    from shapely.ops import unary_union
    flagged = [geo.to_m(c["polygon"]) for c in scan(f)["cells"] if c["flagged"]]
    if not flagged:
        return []
    hull = unary_union(flagged).convex_hull.intersection(geo.to_m(f.geometry))
    ring = geo.to_wgs(hull)["coordinates"][0]
    return [tuple(p) for p in ring[:-1]]


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
    return {"date": str(start), "slots": slots, "best": ok[0]["time"] if ok else None,
            "rule": f"rain <= {SPRAY_MAX_RAIN_MM} mm/h, wind <= {SPRAY_MAX_WIND_KMH:.0f} km/h"}


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


async def seed_demo(db: AsyncSession) -> None:
    if await db.get(Field, "demo"):
        return
    data = json.loads(settings.demo_field_geojson.read_text(encoding="utf-8"))
    hero = next(x for x in data["features"] if x["properties"].get("role") == "hero")
    p = hero["properties"]
    farmer = (await db.execute(select(Farmer).where(Farmer.phone == settings.demo_farmer_phone))).scalar_one_or_none()
    if farmer is None:
        farmer = Farmer(name=settings.demo_farmer_name, phone=settings.demo_farmer_phone, village="Rampura")
        db.add(farmer)
        await db.flush()
    c = shape(hero["geometry"]).centroid
    db.add(Field(id="demo", farmer_id=farmer.id, khasra=p["khasra"], crop="soybean",
                 sowing_date=settings.demo_date - timedelta(days=settings.demo_sowing_age_days),
                 area_acres=round(geo.acres(hero["geometry"]), 2), geometry=hero["geometry"],
                 centroid_lat=c.y, centroid_lon=c.x))
    await db.commit()
