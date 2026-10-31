"""Cache GBIF occurrence records for the soybean pests in backend/app/services/risk/pests.py.

GBIF is public (no key). For each species: records per month across India, and the count inside a box around
Malwa / western MP. Written to data/processed/pests/gbif.json; the app only reads that file, never GBIF live.

    python scripts/fetch_pest_data.py
"""
import json
import sys
from datetime import date
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.services.risk.pests import PESTS

OUT = ROOT / "data" / "processed" / "pests" / "gbif.json"
API = "https://api.gbif.org/v1/occurrence/search"
MALWA = {"decimalLatitude": "21.5,26.5", "decimalLongitude": "73.5,79.5"}   # western MP soybean belt


def _search(params: dict) -> dict:
    r = requests.get(API, params={"limit": 0, **params}, timeout=60)
    r.raise_for_status()
    return r.json()


def species_counts(key: int) -> dict:
    india = _search({"taxonKey": key, "country": "IN", "facet": "month", "facetLimit": 12})
    months = {int(c["name"]): c["count"] for f in india.get("facets", []) for c in f["counts"]}
    malwa = _search({"taxonKey": key, "country": "IN", **MALWA})
    return {"india_total": india["count"], "india_by_month": [months.get(m, 0) for m in range(1, 13)],
            "malwa_total": malwa["count"]}


def main() -> None:
    out = {"source": "GBIF.org occurrence search API", "fetched": str(date.today()), "malwa_box": MALWA, "causes": {}}
    for cause, p in PESTS.items():
        out["causes"][cause] = {}
        for name, key in p["species"]:
            c = species_counts(key)
            out["causes"][cause][name] = {"taxon_key": key, **c}
            print(f"{cause:15s} {name:38s} India {c['india_total']:5d}  Malwa {c['malwa_total']:3d}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
