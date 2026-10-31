"""Open-Meteo hourly weather -> daily features the risk rules use.

Archive (past seasons, backtest) and forecast (15-day warning) go through the
same feature code. Responses are cached on disk per 0.1 degree grid square,
so one download serves every field in a village.
"""
import json
import math
import time
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[4]
CACHE = REPO_ROOT / "data" / "raw" / "weather"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
HOURLY = "temperature_2m,relative_humidity_2m,dew_point_2m,precipitation,sunshine_duration,wind_speed_10m,wind_direction_10m,wind_gusts_10m,vapour_pressure_deficit,soil_moisture_0_to_7cm"
FORECAST_TTL_S = 6 * 3600

LEAF_WET_RH = 90         # PRD: leaf wet when humidity >= 90%
LEAF_WET_DEW_GAP_C = 2   # ...or air within 2 C of dew point
LEAF_WET_RAIN_MM = 0.1   # ...or it is raining
EVENING_HOURS = range(18, 22)
MORNING_HOURS = range(6, 10)
DAYTIME_HOURS = range(6, 19)


def calculate_vpd_kpa(temp_c: float, rh_pct: float) -> float:
    """Vapor Pressure Deficit (kPa) using the Tetens equation."""
    es = 0.61078 * math.exp((17.27 * temp_c) / (temp_c + 237.3))
    ea = es * (max(0.0, min(100.0, rh_pct)) / 100.0)
    return max(0.0, es - ea)


def _square(lat: float, lon: float) -> tuple[float, float]:
    return round(lat, 1), round(lon, 1)


def _get(url: str, params: dict, cache_file: Path, ttl_s: float | None) -> dict:
    if cache_file.exists() and (ttl_s is None or time.time() - cache_file.stat().st_mtime < ttl_s):
        return json.loads(cache_file.read_text(encoding="utf-8"))
    data = requests.get(url, params=params, timeout=60).json()
    if "hourly" not in data:
        raise RuntimeError(f"Open-Meteo error: {data}")
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(data), encoding="utf-8")
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

        # Wind speed & gusts
        raw_w = hourly.get("wind_speed_10m")
        W = [raw_w[i] if raw_w and raw_w[i] is not None else 0.0 for i in ix]
        raw_g = hourly.get("wind_gusts_10m")
        G = [raw_g[i] if raw_g and raw_g[i] is not None else W[k] * 1.35 for k, i in enumerate(ix)]

        # Soil moisture (if provided)
        raw_sm = hourly.get("soil_moisture_0_to_7cm")
        SM = [raw_sm[i] for i in ix if raw_sm and raw_sm[i] is not None]

        # VPD (from API or derived from T and RH)
        raw_vpd = hourly.get("vapour_pressure_deficit")
        if raw_vpd and all(raw_vpd[i] is not None for i in ix):
            VPD = [raw_vpd[i] for i in ix]
        else:
            VPD = [calculate_vpd_kpa(t, rh) for t, rh in zip(T, RH, strict=True)]

        # Leaf wetness
        wet = sum(1 for t, rh, dp, p in zip(T, RH, DP, P, strict=True)
                  if rh >= LEAF_WET_RH or t - dp < LEAF_WET_DEW_GAP_C or p > LEAF_WET_RAIN_MM)

        # Diurnal sub-periods
        evening = [RH[k] for k, i in enumerate(ix) if int(hourly["time"][i][11:13]) in EVENING_HOURS]
        morning = [RH[k] for k, i in enumerate(ix) if int(hourly["time"][i][11:13]) in MORNING_HOURS]

        # Daytime metrics (06:00 - 18:00)
        daytime_indices = [k for k, i in enumerate(ix) if int(hourly["time"][i][11:13]) in DAYTIME_HOURS]
        day_w = [W[k] for k in daytime_indices] if daytime_indices else W
        day_g = [G[k] for k in daytime_indices] if daytime_indices else G

        # Spray suitability: daylight hours with wind <= 12 km/h and rain <= 0.2 mm
        spray_safe_h = sum(1 for k in daytime_indices if W[k] <= 12.0 and P[k] <= 0.2)

        # Whitefly vector favorable flight hours: daytime, warm (24-34C), light-moderate breeze (3-14 km/h), rain-free
        vector_fav_h = sum(1 for k in daytime_indices if 24.0 <= T[k] <= 34.0 and 3.0 <= W[k] <= 14.0 and P[k] < 0.2)

        days.append({
            # Original keys for backward compatibility
            "date": d,
            "tmax": max(T), "tmin": min(T), "tmean": sum(T) / len(T),
            "rain_mm": sum(P),
            "sunshine_h": sum(S) / 3600,
            "leaf_wet_h": wet,
            "evening_rh": sum(evening) / len(evening) if evening else None,

            # Advanced agrometeorological factors
            "diurnal_range": max(T) - min(T),
            "morning_rh": sum(morning) / len(morning) if morning else None,
            "rh_mean": sum(RH) / len(RH),
            "rh_min": min(RH),
            "rh_max": max(RH),
            "wind_mean_kmh": round(sum(W) / len(W), 1) if W else 0.0,
            "wind_max_kmh": round(max(W), 1) if W else 0.0,
            "wind_gust_max_kmh": round(max(G), 1) if G else 0.0,
            "wind_drift_hazard": bool(max(day_w) > 16.0 or max(day_g) > 22.0) if day_w else False,
            "vector_favorable_h": vector_fav_h,
            "spray_safe_h": spray_safe_h,
            "vpd_mean_kpa": round(sum(VPD) / len(VPD), 2) if VPD else 0.0,
            "vpd_max_kpa": round(max(VPD), 2) if VPD else 0.0,
            "soil_moisture": round(sum(SM) / len(SM), 3) if SM else None,
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
