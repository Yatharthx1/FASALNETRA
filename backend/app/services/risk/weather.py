"""Open-Meteo hourly weather -> daily features the risk rules use.

Archive (past seasons, backtest) and forecast (15-day warning) go through the
same feature code. Responses are cached on disk per 0.1 degree grid square,
so one download serves every field in a village.
"""
import json
import time
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[4]
CACHE = REPO_ROOT / "data" / "raw" / "weather"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
HOURLY = "temperature_2m,relative_humidity_2m,dew_point_2m,precipitation,sunshine_duration,wind_speed_10m"
FORECAST_TTL_S = 6 * 3600

LEAF_WET_RH = 90         # PRD: leaf wet when humidity >= 90%
LEAF_WET_DEW_GAP_C = 2   # ...or air within 2 C of dew point
LEAF_WET_RAIN_MM = 0.1   # ...or it is raining
EVENING_HOURS = range(18, 22)


def _square(lat: float, lon: float) -> tuple[float, float]:
    return round(lat, 1), round(lon, 1)


def _get(url: str, params: dict, cache_file: Path, ttl_s: float | None) -> dict:
    if cache_file.exists() and (ttl_s is None or time.time() - cache_file.stat().st_mtime < ttl_s):
        return json.loads(cache_file.read_text())
    data = requests.get(url, params=params, timeout=60).json()
    if "hourly" not in data:
        raise RuntimeError(f"Open-Meteo error: {data}")
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(data))
    return data


def hourly_archive(lat: float, lon: float, start: date, end: date) -> dict:
    la, lo = _square(lat, lon)
    f = CACHE / f"archive_{la}_{lo}_{start}_{end}.json"
    p = {"latitude": la, "longitude": lo, "start_date": str(start), "end_date": str(end),
         "hourly": HOURLY, "timezone": "Asia/Kolkata"}
    return _get(ARCHIVE_URL, p, f, None)["hourly"]


def hourly_forecast(lat: float, lon: float) -> dict:
    """7 past days (rolling windows need them) + 16 forecast days."""
    la, lo = _square(lat, lon)
    f = CACHE / f"forecast_{la}_{lo}.json"
    p = {"latitude": la, "longitude": lo, "past_days": 7, "forecast_days": 16,
         "hourly": HOURLY, "timezone": "Asia/Kolkata"}
    return _get(FORECAST_URL, p, f, FORECAST_TTL_S)["hourly"]


def daily_features(hourly: dict) -> list[dict]:
    by_day = defaultdict(list)
    for i, t in enumerate(hourly["time"]):
        by_day[t[:10]].append(i)

    days = []
    for d, ix in sorted(by_day.items()):
        T = [hourly["temperature_2m"][i] for i in ix]
        if any(v is None for v in T):
            continue
        RH = [hourly["relative_humidity_2m"][i] for i in ix]
        DP = [hourly["dew_point_2m"][i] for i in ix]
        P = [hourly["precipitation"][i] or 0.0 for i in ix]
        S = [hourly["sunshine_duration"][i] or 0.0 for i in ix]
        wet = sum(1 for t, rh, dp, p in zip(T, RH, DP, P, strict=True)
                  if rh >= LEAF_WET_RH or t - dp < LEAF_WET_DEW_GAP_C or p > LEAF_WET_RAIN_MM)
        evening = [RH[k] for k, i in enumerate(ix) if int(hourly["time"][i][11:13]) in EVENING_HOURS]
        days.append({
            "date": d,
            "tmax": max(T), "tmin": min(T), "tmean": sum(T) / len(T),
            "rain_mm": sum(P),
            "sunshine_h": sum(S) / 3600,
            "leaf_wet_h": wet,
            "evening_rh": sum(evening) / len(evening) if evening else None,
        })
    return days


def season(lat: float, lon: float, start: date, end: date) -> list[dict]:
    return daily_features(hourly_archive(lat, lon, start, end))


def outlook(lat: float, lon: float) -> list[dict]:
    return daily_features(hourly_forecast(lat, lon))


def days_between(a: str, b: str) -> int:
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def add_days(d: str, n: int) -> str:
    return str(date.fromisoformat(d) + timedelta(days=n))
