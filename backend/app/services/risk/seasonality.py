"""When in the year each soybean pest is active, from cached records (never fetched live):

    KCC     data/processed/pests/kcc_soybean.json  Kisan Call Centre questions from soybean farmers (AIKosh), by
            week of year: when farmers actually call about each pest. Local and crop-specific, so preferred.
            Built by scripts/build_kcc_surges.py.
    GBIF    data/processed/pests/gbif.json  occurrence records across India by month. Broad and naturalist-biased
            (few soybean fields), so only a fallback, and only for pests with enough records.
            Built by scripts/fetch_pest_data.py.

A prior is 0-1 per week / month: 1 at the busiest time of year, near 0 when the pest is rarely seen or asked about.
"""
import json
from datetime import date
from functools import lru_cache
from pathlib import Path

from backend.app.services.risk.pests import PESTS

REPO_ROOT = Path(__file__).resolve().parents[4]
PESTS_DIR = REPO_ROOT / "data" / "processed" / "pests"
GBIF_FILE = PESTS_DIR / "gbif.json"
KCC_FILE = PESTS_DIR / "kcc_soybean.json"
GBIF_MIN_RECORDS = 200     # fewer India records than this: no seasonal shape worth trusting
MIN_PRIOR = 0.05           # never claim a pest is impossible in some week


@lru_cache
def _load(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def reload() -> None:
    _load.cache_clear()


def _smooth_circular(xs: list[float], k: int) -> list[float]:
    n = len(xs)
    return [sum(xs[(i + d) % n] for d in range(-k, k + 1)) / (2 * k + 1) for i in range(n)]


def _norm(xs: list[float]) -> list[float]:
    top = max(xs) or 1.0
    return [max(MIN_PRIOR, x / top) for x in xs]


def gbif_month_prior(cause: str) -> list[float] | None:
    data = _load(GBIF_FILE)
    species = (data or {}).get("causes", {}).get(cause)
    if not species:
        return None
    months = [sum(s["india_by_month"][m] for s in species.values()) for m in range(12)]
    if sum(months) < GBIF_MIN_RECORDS:
        return None
    return _norm(_smooth_circular([float(x) for x in months], 1))


def kcc_week_prior(cause: str) -> list[float] | None:
    c = ((_load(KCC_FILE) or {}).get("causes") or {}).get(cause)
    return _norm(c["weekly_mean"]) if c and sum(c["weekly_mean"]) else None


def week_of_year(d: date) -> int:
    """0-based, 0-52, same as the KCC build script."""
    return min(52, (d.timetuple().tm_yday - 1) // 7)


def prior(cause: str, on: date) -> tuple[float | None, str | None]:
    """Seasonal prior for a cause on a date and where it came from ("kcc" / "gbif"), or (None, None)."""
    if (k := kcc_week_prior(cause)) is not None:
        return k[week_of_year(on)], "kcc"
    if (g := gbif_month_prior(cause)) is not None:
        return g[on.month - 1], "gbif"
    return None, None


def _curve(cause: str) -> list[float] | None:
    return kcc_week_prior(cause) or gbif_month_prior(cause)


def in_season(cause: str, on: date) -> float | None:
    """How far above its usual level the pest is at this time of year, 0-1. A pest seen or asked about all year
    round (GBIF caterpillars, which eat dozens of crops across India) scores near 0: a flat curve says nothing."""
    p, _ = prior(cause, on)
    curve = _curve(cause)
    if p is None or not curve:
        return None
    mean = sum(curve) / len(curve)
    return round(max(0.0, (p - mean) / (1 - mean)), 3) if mean < 1 else 0.0


def season_vote(on: date) -> dict[str, float]:
    """Evidence-card vote: which pests are more in season than usual right now. Only causes with data take part."""
    return {c: v for c in PESTS if (v := in_season(c, on))}


def local_presence(cause: str) -> int | None:
    """GBIF records inside the Malwa box for this cause (None without the cache)."""
    species = ((_load(GBIF_FILE) or {}).get("causes") or {}).get(cause)
    return sum(s["malwa_total"] for s in species.values()) if species is not None else None


def calendar() -> dict[str, dict]:
    """Per cause: the busiest time of year and the window around it, from the best source available."""
    out = {}
    kcc = (_load(KCC_FILE) or {}).get("causes") or {}
    for cause in PESTS:
        if cause in kcc and sum(kcc[cause]["weekly_mean"]):
            c = kcc[cause]
            out[cause] = {"source": "kcc", "peak_week": c["peak_week"], "surge_weeks": c["surge_weeks"],
                          "questions": c["total"], "years": (_load(KCC_FILE) or {}).get("years")}
        elif (g := gbif_month_prior(cause)) is not None:
            peak = max(range(12), key=lambda m: g[m])
            out[cause] = {"source": "gbif", "peak_month": peak + 1,
                          "busy_months": [m + 1 for m in range(12) if g[m] >= 0.6], "malwa_records": local_presence(cause)}
        else:
            out[cause] = {"source": None, "malwa_records": local_presence(cause)}
    return out
