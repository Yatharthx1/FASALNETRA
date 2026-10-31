"""Agrometeorological advisory logic factors derived from free weather data.

Combines Open-Meteo hourly weather (wind speed, wind gusts, relative humidity,
leaf wetness, precipitation, temperature, VPD) into actionable operational
guidance for farmers and Drone Didis:
  1. Spray Feasibility & Drone Drift Factor (spray windows, wind drift hazard)
  2. Vector Dispersal & Feeding Factor (whitefly flight, Begomovirus pressure)
  3. Fungal Spore & Microclimate Factor (leaf wetness, morning dew, saturation)
"""
from datetime import date, timedelta
from typing import Any

# Spray thresholds based on ICAR-IISR and DGCA agricultural drone operating guidelines
SPRAY_MAX_WIND_OPTIMAL_KMH = 10.0
SPRAY_MAX_WIND_MARGINAL_KMH = 15.0
SPRAY_MAX_GUST_KMH = 20.0
SPRAY_MAX_RAIN_MM = 0.2
SPRAY_MIN_RH = 40.0
SPRAY_MAX_TEMP_C = 35.0


def evaluate_spray_feasibility(hourly: dict, target_date: date | str, start_hour: int = 6, duration_hours: int = 12) -> dict[str, Any]:
    """Evaluates drone and knapsack spray suitability hour-by-hour for a given day."""
    day_str = str(target_date)
    time_series = hourly.get("time", [])

    slots = []
    optimal_slots = []
    marginal_slots = []

    raw_t = hourly.get("temperature_2m")
    raw_rh = hourly.get("relative_humidity_2m")
    raw_p = hourly.get("precipitation")
    raw_w = hourly.get("wind_speed_10m")
    raw_g = hourly.get("wind_gusts_10m")

    for i, t in enumerate(time_series):
        if not t.startswith(day_str):
            continue
        hour = int(t[11:13])
        if not (start_hour <= hour < start_hour + duration_hours):
            continue

        temp = raw_t[i] if raw_t and i < len(raw_t) else None
        rh = raw_rh[i] if raw_rh and i < len(raw_rh) else None
        rain = (raw_p[i] or 0.0) if raw_p and i < len(raw_p) else 0.0
        wind = raw_w[i] if raw_w and i < len(raw_w) else None
        gust = raw_g[i] if raw_g and i < len(raw_g) else None

        wind_val = round(wind, 1) if wind is not None else 0.0
        gust_val = round(gust, 1) if gust is not None else round(wind_val * 1.35, 1)

        # Drift risk assessment
        if wind_val > SPRAY_MAX_WIND_MARGINAL_KMH or gust_val > SPRAY_MAX_GUST_KMH:
            drift = "high"
        elif wind_val > SPRAY_MAX_WIND_OPTIMAL_KMH:
            drift = "moderate"
        else:
            drift = "low"

        # Washout risk
        washout = "high" if rain > 2.0 else "moderate" if rain > SPRAY_MAX_RAIN_MM else "none"

        # Evaporation risk (droplet loss before canopy impact)
        evap = "high" if (temp and temp > SPRAY_MAX_TEMP_C and rh and rh < SPRAY_MIN_RH) else "low"

        is_safe = (rain <= SPRAY_MAX_RAIN_MM and
                   wind_val <= SPRAY_MAX_WIND_MARGINAL_KMH and
                   gust_val <= SPRAY_MAX_GUST_KMH)
        is_optimal = is_safe and wind_val <= SPRAY_MAX_WIND_OPTIMAL_KMH and evap == "low"

        status = "optimal" if is_optimal else "marginal" if is_safe else "unsafe"

        slot = {
            "time": t,
            "hour": hour,
            "temp_c": round(temp, 1) if temp is not None else None,
            "rh_pct": round(rh, 1) if rh is not None else None,
            "rain_mm": round(rain, 1),
            "wind_kmh": wind_val,
            "gust_kmh": gust_val,
            "drift_risk": drift,
            "washout_risk": washout,
            "status": status,
        }
        slots.append(slot)
        if is_optimal:
            optimal_slots.append(slot)
        elif is_safe:
            marginal_slots.append(slot)

    # Determine overall status
    if len(optimal_slots) >= 3:
        overall = "optimal"
    elif len(optimal_slots) + len(marginal_slots) >= 2:
        overall = "marginal"
    else:
        overall = "hazardous"

    # Best recommended window
    target_group = optimal_slots if optimal_slots else marginal_slots
    if target_group:
        first_h = target_group[0]["hour"]
        last_h = target_group[-1]["hour"] + 1
        best_window = f"{first_h:02d}:00 - {last_h:02d}:00"
        avg_wind = round(sum(s["wind_kmh"] for s in target_group) / len(target_group), 1)
    else:
        best_window = None
        avg_wind = round(sum(s["wind_kmh"] for s in slots) / len(slots), 1) if slots else 0.0

    # Plain language voice/UI advisories
    if overall == "optimal":
        advisory_hi = f"हवा की गति {avg_wind} km/h अनुकूल है। सबसे उत्तम छिड़काव का समय सुबह {best_window} है।"
        advisory_en = f"Optimal spray weather (wind {avg_wind} km/h). Recommended window: {best_window}."
    elif overall == "marginal":
        advisory_hi = f"हवा मध्यम है ({avg_wind} km/h)। केवल {best_window} में सावधानीपूर्वक छिड़काव करें, तेज बहाव से बचें।"
        advisory_en = f"Marginal spray conditions ({avg_wind} km/h). Spray carefully within {best_window}."
    else:
        advisory_hi = f"हवा तेज है या बारिश की संभावना है (अधिकतम हवा {avg_wind} km/h)। आज छिड़काव टालें - दवा उड़ जाएगी।"
        advisory_en = f"High drift or rain risk (wind {avg_wind} km/h). Postpone spraying today to avoid chemical drift."

    return {
        "date": day_str,
        "overall_suitability": overall,
        "best_window": best_window,
        "safe_hours_count": len(optimal_slots) + len(marginal_slots),
        "optimal_hours_count": len(optimal_slots),
        "mean_wind_kmh": avg_wind,
        "slots": slots,
        "advisory_hi": advisory_hi,
        "advisory_en": advisory_en,
    }


def vector_dispersal_factor(days_window: list[dict]) -> dict[str, Any]:
    """Calculates whitefly vector mobility and Begomovirus dispersal pressure over a 7-day window."""
    if not days_window:
        return {"factor": 0.0, "status": "low", "drivers": []}

    n = len(days_window)
    warm_days = sum(1 for d in days_window if d.get("tmax", 0) >= 30.0) / n
    dry_days = sum(1 for d in days_window if d.get("rain_mm", 0) < 2.0) / n
    sun_hours = sum(d.get("sunshine_h", 0) for d in days_window) / n
    fav_wind_h = sum(d.get("vector_favorable_h", 0) for d in days_window) / n
    mean_vpd = sum(d.get("vpd_mean_kpa", 0) for d in days_window) / n

    # Factor score 0.0 to 1.0
    score = (
        0.30 * dry_days +
        0.25 * min(1.0, max(0.0, (sun_hours - 5.0) / 5.0)) +
        0.25 * min(1.0, max(0.0, fav_wind_h / 6.0)) +
        0.20 * min(1.0, max(0.0, (mean_vpd - 0.8) / 1.2))
    )

    drivers = [
        {"en": f"{round(fav_wind_h)} h/day light breeze (3-12 km/h) aiding vector spread",
         "hi": f"roz {round(fav_wind_h)} ghante halki hawa (3-12 km/h) makkhi ke phelav ke liye anukool"},
        {"en": f"dry sunny spell (sun {sun_hours:.1f} h/day, rain {sum(d.get('rain_mm', 0) for d in days_window):.1f} mm)",
         "hi": f"sookha aur tez dhoop wala mausam (roz {sun_hours:.0f} ghante dhoop)"},
        {"en": f"high atmospheric demand (VPD {mean_vpd:.2f} kPa) accelerating feeding",
         "hi": f"sukhi hawa (VPD {mean_vpd:.1f} kPa) se fasal par poshan tanav"},
    ]

    return {
        "factor": round(score, 3),
        "status": "high" if score >= 0.7 else "watch" if score >= 0.4 else "safe",
        "fav_wind_hours_daily": round(fav_wind_h, 1),
        "mean_vpd_kpa": round(mean_vpd, 2),
        "drivers": drivers,
    }


def fungal_conduciveness_factor(days_window: list[dict]) -> dict[str, Any]:
    """Calculates fungal spore germination and aerial blight risk over a 7-day window."""
    if not days_window:
        return {"factor": 0.0, "status": "low", "drivers": []}

    n = len(days_window)
    wet_days = sum(1 for d in days_window if d.get("leaf_wet_h", 0) >= 16) / n
    morning_rh = [d["morning_rh"] for d in days_window if d.get("morning_rh") is not None]
    avg_morning_rh = sum(morning_rh) / len(morning_rh) if morning_rh else 80.0
    mean_temp = sum(d.get("tmean", 0) for d in days_window) / n

    temp_favorable = 1.0 if 22.0 <= mean_temp <= 28.5 else 0.4
    dew_factor = min(1.0, max(0.0, (avg_morning_rh - 75.0) / 20.0))

    score = (
        0.50 * wet_days +
        0.30 * dew_factor +
        0.20 * temp_favorable
    )

    drivers = [
        {"en": f"{round(wet_days * n)} days with continuous canopy wetness >= 16 h",
         "hi": f"{round(wet_days * n)} din lagatar 16+ ghante patte geele"},
        {"en": f"morning dew humidity {avg_morning_rh:.0f}% encourages spore germination",
         "hi": f"subah ki nami {avg_morning_rh:.0f}% fungus ke tezi se panapne ke liye anukool"},
    ]

    return {
        "factor": round(score, 3),
        "status": "high" if score >= 0.7 else "watch" if score >= 0.4 else "safe",
        "avg_morning_rh": round(avg_morning_rh, 1),
        "drivers": drivers,
    }
