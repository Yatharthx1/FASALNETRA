"""Rule-based pest/disease risk per day, with plain-language drivers.

Each rule sees the 14 days ending on the scored day (some use only the last 7). Scores are 0-100;
bands follow the PRD: Safe < 40, Watch 40-70, High >= 70.

Calibration (provisional until checked on Malwa field data; regions in brackets):
- Yellow mosaic / whitefly: peaks follow, over the previous two weeks, Tmax > 33 C on 5+ days and a monsoon
  break of more than a week; rain and humid evenings suppress it (Srivastava et al. 2021, IJBB 58(5);
  Bundelkhand and Jabalpur, MP, 2015-19). Gridded data (Open-Meteo / ERA5) reads cooler than field stations in
  the monsoon (the 2025 Mandsaur grid stayed at 29.3-31.0 C through the 1-15 Aug dry break), so warmth is graded
  from 29 C to full at 32 C, i.e. the paper's 33 C less an assumed ~1 C grid cool bias. On the 2025 replay this
  puts High only in the 6-16 Aug break (Jul max 56, Sep max 40); a 30-33 C ramp gave High on one day all season.
  Check the bias against IMD station Tmax for Mandsaur before calling it validated.
- Rhizoctonia aerial blight: weekly Tmax 27-30 C, RH 80-90% (85%+ strongest), more rain the week before
  (central India studies).
- Tobacco caterpillar (Spodoptera litura): development base 12.1 C, ~489 degree-days per generation
  (Prasad et al. 2021, J. Agromet 23(2)); humid monsoon weeks with light rain.
- Girdle beetle: rises with humidity in the current and previous week; peak seen at Tmax ~31.9 C and morning
  RH ~91% (Raipur; Maharashtra CROPSAP data). Correlations only, no published cut-off.
- Waterlogging (not a pest): top soil near saturation for days, or a heavy-rain event (IMD heavy rain 64.5 mm).
"""
from datetime import date

from backend.app.services import advisory
from backend.app.services.risk.weather import days_between

WINDOW = 7
HISTORY = 14
HIGH, WATCH = 70, 40
STAGE_OUTSIDE_WINDOW = 0.4     # a crop outside its vulnerable window still carries some risk
ADVISORY_BONUS = 10            # this week's ICAR-NSRI advisory mentions the pest

RULES = {
    "yellow_mosaic": {"status": "provisional", "hot_c": 32.0, "warm_c": 29.0, "hot_days_full": 5, "dry_day_mm": 2.0,
                      "break_days_full": 7, "evening_rh_dry": 72.0, "evening_rh_wet": 88.0, "rain_14d_wet_mm": 120.0,
                      "sun_full_h": 10.0, "sun_zero_h": 5.0},
    "fungal": {"status": "provisional", "tmax_lo": 27.0, "tmax_hi": 30.0, "rh_humid": 85.0, "prev_week_rain_full_mm": 50.0,
               "wet_day_h": 18},
    "chewing_damage": {"status": "provisional", "base_c": 12.1, "dd_generation": 489.0, "rain_lo_mm": 3.0,
                       "rain_hi_mm": 30.0, "rh_humid": 80.0, "weather_cap": 0.6},
    # monsoon fits girdle beetle most weeks, so like caterpillars it is capped below High and needs a field signal
    "girdle_beetle": {"status": "provisional", "morning_rh_humid": 90.0, "rain_day_mm": 2.0, "tmax_lo": 30.0,
                      "tmax_hi": 33.5, "weather_cap": 0.6},
    # Malwa black soil sits near 0.50 m3/m3 for much of the monsoon (2025: 46 days), so saturation alone means
    # little; a run of 4+ days at 0.51+ marks real episodes (2025: early and late July, after 52-81 mm rain).
    # Capped: weather cannot see standing water; the satellite low-spot check and photos confirm it.
    "water_stress": {"status": "provisional", "soil_saturated": 0.51, "saturated_run_full": 4, "heavy_rain_mm": 64.5,
                     "weather_cap": 0.6},
}


def _clip(x: float) -> float:
    return max(0.0, min(1.0, x))


def _band_fit(x: float, lo: float, hi: float, margin: float = 2.0) -> float:
    """1 inside [lo, hi], falling to 0 at `margin` outside."""
    if lo <= x <= hi:
        return 1.0
    return _clip(1 - (lo - x if x < lo else x - hi) / margin)


def _longest_dry_run(w: list[dict], dry_mm: float) -> int:
    best = run = 0
    for d in w:
        run = run + 1 if d["rain_mm"] < dry_mm else 0
        best = max(best, run)
    return best


def _yellow_mosaic(w: list[dict]) -> tuple[float, list[tuple[float, str, str]]]:
    r = RULES["yellow_mosaic"]
    # hot-day equivalents over two weeks: a 33 C day counts 1, a 31.5 C day 0.5 (graded for the cool grid)
    hot = sum(_clip((d["tmax"] - r["warm_c"]) / (r["hot_c"] - r["warm_c"])) for d in w)
    brk = _longest_dry_run(w, r["dry_day_mm"])
    last = w[-WINDOW:]
    erh = [d["evening_rh"] for d in last if d["evening_rh"] is not None]
    erh = sum(erh) / len(erh) if erh else r["evening_rh_wet"]
    rain = sum(d["rain_mm"] for d in w)
    sun = sum(d["sunshine_h"] for d in last) / len(last)
    parts = [
        (0.30 * _clip(brk / r["break_days_full"]), f"{brk} dry days in a row (monsoon break)",
         f"lagatar {brk} din sookhe (baarish ruki)"),
        (0.30 * _clip(hot / r["hot_days_full"]), f"{hot:.1f} hot days (towards {r['hot_c']:.0f} C) in 2 weeks",
         f"2 hafte mein {hot:.0f} din tez garmi"),
        (0.20 * _clip((r["evening_rh_wet"] - erh) / (r["evening_rh_wet"] - r["evening_rh_dry"])),
         f"evening humidity only {erh:.0f}%", f"shaam ki nami sirf {erh:.0f}%"),
        (0.10 * _clip(1 - rain / r["rain_14d_wet_mm"]), f"only {rain:.0f} mm rain in 2 weeks",
         f"2 hafte mein sirf {rain:.0f} mm baarish"),
        (0.10 * _clip((sun - r["sun_zero_h"]) / (r["sun_full_h"] - r["sun_zero_h"])),
         f"{sun:.1f} h sunshine a day", f"roz {sun:.0f} ghante dhoop"),
    ]
    return sum(p[0] for p in parts), parts


def _fungal(w: list[dict]) -> tuple[float, list[tuple[float, str, str]]]:
    r = RULES["fungal"]
    last, prev = w[-WINDOW:], w[:-WINDOW]
    tmax = sum(d["tmax"] for d in last) / len(last)
    humid = sum((d.get("rh_mean") or 0) >= r["rh_humid"] for d in last)
    prev_rain = sum(d["rain_mm"] for d in prev)
    wet_days = sum(d["leaf_wet_h"] >= r["wet_day_h"] for d in last)
    parts = [
        (0.30 * _clip(humid / 4), f"{humid} days with humidity over {r['rh_humid']:.0f}%",
         f"{humid} din {r['rh_humid']:.0f}% se zyada nami"),
        (0.25 * _band_fit(tmax, r["tmax_lo"], r["tmax_hi"]), f"weekly max temperature {tmax:.1f} C suits blight",
         f"din ka taapmaan {tmax:.0f} degree, jhulsa ke liye sahi"),
        (0.25 * _clip(prev_rain / r["prev_week_rain_full_mm"]), f"{prev_rain:.0f} mm rain the week before",
         f"pichhle hafte {prev_rain:.0f} mm baarish"),
        (0.20 * _clip(wet_days / 4), f"{wet_days} days with leaves wet {r['wet_day_h']}+ h",
         f"{wet_days} din patte {r['wet_day_h']} ghante se zyada geele"),
    ]
    return sum(p[0] for p in parts), parts


def degree_days(days: list[dict], base_c: float) -> float:
    return sum(max(0.0, (d["tmax"] + d["tmin"]) / 2 - base_c) for d in days)


def _chewing(w: list[dict]) -> tuple[float, list[tuple[float, str, str]]]:
    r = RULES["chewing_damage"]
    last = w[-WINDOW:]
    mild = sum(r["rain_lo_mm"] <= d["rain_mm"] <= r["rain_hi_mm"] for d in last) / len(last)
    humid = sum((d.get("rh_mean") or 0) >= r["rh_humid"] for d in last) / len(last)
    dd = degree_days(w, r["base_c"])
    gen_days = len(w) * r["dd_generation"] / dd if dd else None
    parts = [
        (0.40 * mild, f"{round(mild * len(last))} days of light-moderate rain", f"{round(mild * len(last))} din halki baarish"),
        (0.30 * humid, f"{round(humid * len(last))} humid days", f"{round(humid * len(last))} din nami wale"),
        # warmth sets the pace: at ~33 days per generation a new brood of larvae appears every month
        (0.30 * _clip(30 / gen_days) if gen_days else 0.0,
         f"warm enough for a new caterpillar generation every {gen_days:.0f} days" if gen_days else "too cool for caterpillars",
         f"har {gen_days:.0f} din mein illi ki nayi peedhi" if gen_days else "illi ke liye thanda"),
    ]
    # Monsoon weather suits caterpillars almost every week, so weather alone is a weak signal:
    # capped below High so it never triggers a call without a field signal.
    return r["weather_cap"] * sum(p[0] for p in parts), parts


def _girdle(w: list[dict]) -> tuple[float, list[tuple[float, str, str]]]:
    r = RULES["girdle_beetle"]
    mrh = [d for d in w if d.get("morning_rh") is not None]
    humid = sum(d["morning_rh"] >= r["morning_rh_humid"] for d in mrh) / len(mrh) if mrh else 0.0   # this + last week
    last = w[-WINDOW:]
    rainy = sum(d["rain_mm"] >= r["rain_day_mm"] for d in last) / len(last)
    tmax = sum(d["tmax"] for d in last) / len(last)
    parts = [
        (0.40 * humid, f"{round(humid * len(mrh))} of last {len(mrh)} mornings over {r['morning_rh_humid']:.0f}% humidity",
         f"{round(humid * len(mrh))} subah {r['morning_rh_humid']:.0f}% se zyada nami"),
        (0.35 * rainy, f"rain on {round(rainy * len(last))} of last {len(last)} days", f"{round(rainy * len(last))} din baarish"),
        (0.25 * _band_fit(tmax, r["tmax_lo"], r["tmax_hi"]), f"max temperature {tmax:.1f} C suits girdle beetle",
         f"taapmaan {tmax:.0f} degree, chakra bhrung ke liye sahi"),
    ]
    return r["weather_cap"] * sum(p[0] for p in parts), parts


def _waterlogging(w: list[dict]) -> tuple[float, list[tuple[float, str, str]]]:
    r = RULES["water_stress"]
    last = w[-WINDOW:]
    soil = [d["soil_moisture"] for d in last if d.get("soil_moisture") is not None]
    saturated = run = 0
    for s in soil:
        run = run + 1 if s >= r["soil_saturated"] else 0
        saturated = max(saturated, run)
    heavy = max((last[i]["rain_mm"] + (last[i - 1]["rain_mm"] if i else 0) for i in range(len(last))), default=0)
    parts = [
        (0.6 * _clip(saturated / r["saturated_run_full"]) if soil else 0.0,
         f"top soil saturated {saturated} days in a row" if soil else "no soil moisture data",
         f"lagatar {saturated} din mitti paani se bhari" if soil else "mitti ki nami ka data nahin"),
        (0.4 * _clip(heavy / r["heavy_rain_mm"]), f"{heavy:.0f} mm rain in 2 days", f"2 din mein {heavy:.0f} mm baarish"),
    ]
    return r["weather_cap"] * sum(p[0] for p in parts), parts


SCORERS = {"yellow_mosaic": _yellow_mosaic, "fungal": _fungal, "chewing_damage": _chewing,
           "girdle_beetle": _girdle, "water_stress": _waterlogging}


def band(score: float) -> str:
    return "high" if score >= HIGH else "watch" if score >= WATCH else "safe"


def score_days(days: list[dict], sowing: date, from_day: str | None = None,
               advisory_flags: dict[str, bool] | None = None) -> list[dict]:
    """Score every day that has a full history behind it (optionally only from `from_day` on)."""
    flags = advisory_flags or {}
    out = []
    for i in range(HISTORY - 1, len(days)):
        today = days[i]["date"]
        if from_day and today < from_day:
            continue
        w = days[i - HISTORY + 1:i + 1]
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
    if not window:
        return {}
    vote = {c: max(d["causes"][c]["score"] for d in window) / 100 for c in SCORERS}
    # waterlogging shows within days, not weeks: only the last week counts
    vote["water_stress"] = max(d["causes"]["water_stress"]["score"] for d in window[-WINDOW:]) / 100
    return vote
