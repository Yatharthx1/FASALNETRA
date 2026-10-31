"""Rule-based pest/disease risk per day, with plain-language drivers.

Every rule looks at the 7 days ending on the scored day. Scores are 0-100;
bands follow the PRD: Safe < 40, Watch 40-70, High >= 70.

STATUS: provisional. The PRD rule for yellow mosaic says Tmax > 33 C, but the
Open-Meteo grid for Mandsaur never passed 32.4 C in Jul-Sep 2025, so that
threshold can never fire on this data. We use the pattern the literature
describes (warm, dry, sunny spells build whitefly; rain and humid evenings
suppress it) with a 30 C warmth cut-off. Thresholds must be checked against
the MP yellow-mosaic paper before they are called validated.
"""
from datetime import date

from backend.app.services import advisory
from backend.app.services.risk.weather import days_between

WINDOW = 7
HIGH, WATCH = 70, 40
STAGE_OUTSIDE_WINDOW = 0.4     # a crop outside its vulnerable window still carries some risk
ADVISORY_BONUS = 10            # this week's ICAR-NSRI advisory mentions the pest

RULES = {
    "yellow_mosaic": {"status": "provisional", "tmax_warm_c": 30.0, "dry_day_mm": 2.0,
                      "sun_full_h": 10.0, "sun_zero_h": 5.0, "evening_rh_dry": 72.0, "evening_rh_wet": 88.0},
    "fungal": {"status": "provisional", "wet_day_h": 18, "tmean_lo": 23.0, "tmean_hi": 30.0},
    "chewing_damage": {"status": "provisional", "rain_lo_mm": 3.0, "rain_hi_mm": 30.0, "tmean_lo": 24.0, "tmean_hi": 30.0, "weather_cap": 0.6},
}


def _clip(x: float) -> float:
    return max(0.0, min(1.0, x))


def _yellow_mosaic(w: list[dict]) -> tuple[float, list[tuple[float, str, str]]]:
    r = RULES["yellow_mosaic"]
    dry = sum(d["rain_mm"] < r["dry_day_mm"] for d in w) / len(w)
    sun = sum(d["sunshine_h"] for d in w) / len(w)
    erh = [d["evening_rh"] for d in w if d["evening_rh"] is not None]
    erh = sum(erh) / len(erh) if erh else r["evening_rh_wet"]
    warm = sum(d["tmax"] >= r["tmax_warm_c"] for d in w) / len(w)
    parts = [
        (0.30 * dry, f"{round(dry * len(w))} of last {len(w)} days dry",
         f"pichhle {len(w)} mein se {round(dry * len(w))} din sookhe"),
        (0.25 * _clip((sun - r["sun_zero_h"]) / (r["sun_full_h"] - r["sun_zero_h"])),
         f"{sun:.1f} h sunshine a day", f"roz {sun:.0f} ghante dhoop"),
        (0.25 * _clip((r["evening_rh_wet"] - erh) / (r["evening_rh_wet"] - r["evening_rh_dry"])),
         f"evening humidity only {erh:.0f}%", f"shaam ki nami sirf {erh:.0f}%"),
        (0.20 * warm, f"{round(warm * len(w))} days above {r['tmax_warm_c']:.0f} C",
         f"{round(warm * len(w))} din {r['tmax_warm_c']:.0f} degree se zyada garmi"),
    ]
    return sum(p[0] for p in parts), parts


def _fungal(w: list[dict]) -> tuple[float, list[tuple[float, str, str]]]:
    r = RULES["fungal"]
    wet_days = sum(d["leaf_wet_h"] >= r["wet_day_h"] for d in w)
    lw = sum(d["leaf_wet_h"] for d in w) / len(w)
    tm = sum(d["tmean"] for d in w) / len(w)
    temp_ok = 1.0 if r["tmean_lo"] <= tm <= r["tmean_hi"] else 0.3
    parts = [
        (0.55 * _clip(wet_days / 4), f"{wet_days} days with leaves wet {r['wet_day_h']}+ h",
         f"{wet_days} din patte {r['wet_day_h']} ghante se zyada geele"),
        (0.25 * _clip((lw - 8) / 12), f"leaves wet {lw:.0f} h a day on average", f"roz {lw:.0f} ghante geele patte"),
        (0.20 * temp_ok, f"mean temperature {tm:.1f} C suits fungus", f"taapmaan {tm:.0f} degree, fungus ke liye sahi"),
    ]
    return sum(p[0] for p in parts), parts


def _chewing(w: list[dict]) -> tuple[float, list[tuple[float, str, str]]]:
    r = RULES["chewing_damage"]
    mild = sum(r["rain_lo_mm"] <= d["rain_mm"] <= r["rain_hi_mm"] for d in w) / len(w)
    tm = sum(d["tmean"] for d in w) / len(w)
    temp_ok = 1.0 if r["tmean_lo"] <= tm <= r["tmean_hi"] else 0.3
    parts = [
        (0.6 * mild, f"{round(mild * len(w))} days of light-moderate rain", f"{round(mild * len(w))} din halki baarish"),
        (0.4 * temp_ok, f"mean temperature {tm:.1f} C suits caterpillars", f"taapmaan {tm:.0f} degree, illi ke liye sahi"),
    ]
    # Monsoon weather suits caterpillars almost every week, so weather alone is a weak signal:
    # capped below High so it never triggers a call without a field signal.
    return r["weather_cap"] * sum(p[0] for p in parts), parts


SCORERS = {"yellow_mosaic": _yellow_mosaic, "fungal": _fungal, "chewing_damage": _chewing}


def band(score: float) -> str:
    return "high" if score >= HIGH else "watch" if score >= WATCH else "safe"


def score_days(days: list[dict], sowing: date, from_day: str | None = None,
               advisory_flags: dict[str, bool] | None = None) -> list[dict]:
    """Score every day that has a full window behind it (optionally only from `from_day` on)."""
    flags = advisory_flags or {}
    out = []
    for i in range(WINDOW - 1, len(days)):
        today = days[i]["date"]
        if from_day and today < from_day:
            continue
        w = days[i - WINDOW + 1:i + 1]
        das = days_between(str(sowing), today)
        causes = {}
        for cause, fn in SCORERS.items():
            weather, parts = fn(w)
            lo, hi = advisory.find(cause)["vulnerable_das"]
            in_stage = lo <= das <= hi
            s = 100 * weather * (1.0 if in_stage else STAGE_OUTSIDE_WINDOW)
            drivers = sorted(parts, key=lambda p: -p[0])
            drivers = [{"en": p[1], "hi": p[2]} for p in drivers[:2]]
            drivers.append({"en": f"crop {das} days old ({'vulnerable' if in_stage else 'outside vulnerable'} stage {lo}-{hi})",
                            "hi": f"fasal {das} din ki" + (", khatre wali umar" if in_stage else "")})
            if flags.get(cause):
                s += ADVISORY_BONUS
                drivers[-1] = {"en": "this week's ICAR-NSRI advisory warns about it",
                               "hi": "is hafte ICAR ki salah mein iski chetavani"}
            s = round(min(s, 100.0), 1)
            causes[cause] = {"score": s, "band": band(s), "drivers": drivers}
        top = max(causes, key=lambda c: causes[c]["score"])
        out.append({"date": today, "das": das, "top": top, "score": causes[top]["score"],
                    "band": causes[top]["band"], "causes": causes})
    return out


def weather_vote(scored: list[dict], on: str, lookback_days: int = 14) -> dict[str, float]:
    """0-1 weather fit per cause for the evidence card.

    Symptoms seen today come from conditions 1-3 weeks ago (whitefly spreads the
    virus, then it takes ~2 weeks to show), so take each cause's peak over the lookback.
    """
    window = [d for d in scored if d["date"] <= on][-lookback_days:]
    return {c: max(d["causes"][c]["score"] for d in window) / 100 for c in SCORERS} if window else {}
