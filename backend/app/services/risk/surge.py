"""Next surge per pest: the 15-day weather risk, weighted by how in season the pest is (seasonality.py).

Weather says whether the next two weeks suit a pest; the calendar says whether farmers usually see it now.
Both together give the outlook: when the risk is expected to peak, whether it crosses the call threshold,
and how many independent sources back it. Recomputed from the forecast every SURGE_REFRESH_DAYS days
(the Sentinel-2 revisit), so field checks and outlook move together.
"""
from datetime import date, timedelta

from backend.app.services.risk import rules, seasonality
from backend.app.services.risk.pests import PESTS

SURGE_REFRESH_DAYS = 5
SEASON_FLOOR = 0.6     # out of season, weather risk still counts for 60%: an early outbreak is possible


def _season_factor(cause: str, d: date) -> tuple[float, str | None]:
    p, source = seasonality.prior(cause, d)
    return (1.0, None) if p is None else (SEASON_FLOOR + (1 - SEASON_FLOOR) * p, source)


def outlook(days: list[dict], today: date) -> dict:
    """days: rules.score_days output for today onwards. One entry per pest, worst first."""
    pests = []
    for cause in rules.SCORERS:
        series = []
        for d in days:
            day = date.fromisoformat(d["date"])
            factor, source = _season_factor(cause, day)
            series.append({"date": d["date"], "weather": d["causes"][cause]["score"],
                           "score": round(d["causes"][cause]["score"] * factor, 1), "source": source})
        if not series:
            continue
        peak = max(series, key=lambda s: s["score"])
        onset = next((s for s in series if s["score"] >= rules.HIGH), None) or \
            next((s for s in series if s["score"] >= rules.WATCH), None)
        source = peak["source"]
        basis = ["weather forecast"] + ({"kcc": ["Kisan Call Centre questions"],
                                         "gbif": ["GBIF pest records"]}.get(source, []))
        local = seasonality.local_presence(cause)
        if local:
            basis.append(f"{local} GBIF records in Malwa")
        in_season = seasonality.in_season(cause, date.fromisoformat(peak["date"]))
        band = rules.band(peak["score"])
        # high only when the weather peak is high AND the pest is clearly in season by a crop-specific calendar
        confidence = ("high" if band == "high" and source == "kcc" and (in_season or 0) >= 0.5
                      else "medium" if band != "safe" and source is not None else "low")
        drivers = days[series.index(peak)]["causes"][cause]["drivers"]
        pests.append({
            "cause": cause, "name_en": PESTS.get(cause, {}).get("name_en", "Waterlogging or water stress (not a pest)"),
            "peak_date": peak["date"], "peak_score": peak["score"], "band": band,
            "onset_date": onset["date"] if onset else None,
            "in_season": in_season, "season_source": source, "confidence": confidence, "basis": basis,
            "drivers": drivers, "habitat": PESTS.get(cause, {}).get("habitat", "low spots and heavy black soil hold water"),
            "series": [{"date": s["date"], "score": s["score"]} for s in series],
        })
    pests.sort(key=lambda p: -p["peak_score"])
    return {"from": str(today), "next_update": str(today + timedelta(days=SURGE_REFRESH_DAYS)),
            "pests": pests, "calendar": seasonality.calendar()}
