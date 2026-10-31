"""Backtest: would the risk engine have warned before the Mandsaur 2025 yellow-mosaic outbreak?

Event: compensation survey for yellow mosaic in Mandsaur ordered on 1 Sept 2025 (PRD).
Uses the Open-Meteo archive only, so no data from after each scored day leaks in
(every score looks back 14 days, rules.HISTORY). Sowing dates vary because farmers sow over ~3 weeks.

    python scripts/backtest_mandsaur.py

Writes artifacts/reports/backtest_mandsaur_2025.json
"""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.services.risk import rules, weather  # noqa: E402

LAT, LON = 24.1036, 75.1218            # demo field, Rampura, Mandsaur
OUTBREAK_REPORT = date(2025, 9, 1)
SEASON = (date(2025, 6, 1), date(2025, 9, 15))
SOWING_DATES = [date(2025, 6, 25) + timedelta(days=d) for d in range(0, 22, 3)]   # 25 Jun - 16 Jul
TARGET_DAYS_EARLY = 10
CAUSE = "yellow_mosaic"
CONTROL_YEARS = [2023, 2024]


def first_high(scored: list[dict], before: date) -> dict | None:
    for d in scored:
        if d["date"] >= str(before):
            return None
        if d["causes"][CAUSE]["band"] == "high":
            return d
    return None


def main() -> None:
    days = weather.season(LAT, LON, *SEASON)
    runs = []
    for sowing in SOWING_DATES:
        scored = rules.score_days(days, sowing)
        hit = first_high(scored, OUTBREAK_REPORT)
        runs.append({
            "sowing": str(sowing),
            "first_high": hit["date"] if hit else None,
            "days_early": (OUTBREAK_REPORT - date.fromisoformat(hit["date"])).days if hit else None,
            "score": hit["causes"][CAUSE]["score"] if hit else None,
            "drivers": [x["en"] for x in hit["causes"][CAUSE]["drivers"]] if hit else None,
            "high_days_before_report": sum(1 for d in scored if d["date"] < str(OUTBREAK_REPORT)
                                           and d["causes"][CAUSE]["band"] == "high"),
        })

    # same rule, same field, seasons with no outbreak record checked: how often would we have called?
    controls = {}
    for year in CONTROL_YEARS:
        scored = rules.score_days(weather.season(LAT, LON, date(year, 6, 1), date(year, 9, 15)), date(year, 7, 6))
        high = [d["date"] for d in scored if d["causes"][CAUSE]["band"] == "high"]
        controls[str(year)] = {"high_days": len(high), "first": high[0] if high else None,
                               "last": high[-1] if high else None, "outbreak_record": "not checked"}

    hits = [r for r in runs if r["days_early"] is not None and r["days_early"] >= TARGET_DAYS_EARLY]
    early = sorted(r["days_early"] for r in runs if r["days_early"] is not None)
    report = {
        "event": "Yellow mosaic outbreak, Mandsaur; compensation survey 2025-09-01",
        "weather": "Open-Meteo archive (ERA5-based), hourly, 0.1 deg grid",
        "rule_status": rules.RULES[CAUSE]["status"],
        "sowing_dates_tested": len(runs),
        "warned_at_least_10_days_early": f"{len(hits)} of {len(runs)}",
        "days_early_range": [early[0], early[-1]] if early else None,
        "runs": runs,
        "other_seasons": controls,
        "caveats": [
            "One outbreak event; this shows the rule fires in time, not its false-alarm rate.",
            "The rule was written after looking at the 2025 weather; thresholds still need checking "
            "against the MP yellow-mosaic paper and against a season without an outbreak.",
            "The report date is when the survey was ordered, not when symptoms first appeared.",
        ],
    }
    out = ROOT / "artifacts" / "reports" / "backtest_mandsaur_2025.json"
    out.write_text(json.dumps(report, indent=1), encoding="utf-8")

    print(f"{'sowing':12s} {'first High':12s} {'days early':>10s}  score")
    for r in runs:
        print(f"{r['sowing']:12s} {str(r['first_high']):12s} {str(r['days_early']):>10s}  {r['score']}")
    print(f"\nwarned >= {TARGET_DAYS_EARLY} days early: {report['warned_at_least_10_days_early']} sowing dates"
          f"  (range {report['days_early_range']} days)")
    for y, c in controls.items():
        print(f"{y}: {c['high_days']} High days ({c['first']} to {c['last']}), outbreak record not checked")
    print(f"saved {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
