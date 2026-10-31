"""Advisory lookup: the only place spray advice comes from.

The LLM never invents a dose. It picks a cause; this module returns the
ICAR-NSRI row and turns the per-hectare dose into what the farmer or
Drone Didi actually needs for the affected zone.
"""
import json
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
TABLE_PATH = REPO_ROOT / "data" / "seed" / "advisory_table.json"
HA_PER_ACRE = 0.404686


@lru_cache
def load_table() -> dict:
    return json.loads(TABLE_PATH.read_text(encoding="utf-8"))


def find(cause: str) -> dict | None:
    for row in load_table()["rows"]:
        if row["cause"] == cause or row["id"] == cause:
            return row
    return None


def spray_plan(cause: str, zone_acres: float, method: str = "drone", product_index: int = 0) -> dict:
    """Product, quantity and water for one zone. Non-pest causes return no chemical."""
    table = load_table()
    row = find(cause)
    if row is None:
        raise KeyError(f"No advisory row for cause '{cause}'")

    zone_ha = zone_acres * HA_PER_ACRE
    plan = {
        "cause": row["cause"],
        "name_hi": row["name_hi"],
        "name_en": row["name_en"],
        "zone_acres": round(zone_acres, 2),
        "cultural": row["cultural"],
        "source": f"{table['source_org']}, {table['advisory_season']}",
        "source_urls": row["sources"],
        "verified_against_label": table["verified_against_label"],
        "spray": None,
    }
    if not row["chemical"]:
        return plan

    chem = row["chemical"][min(product_index, len(row["chemical"]) - 1)]
    water_l = table["water_l_per_ha"][method] * zone_ha
    plan["spray"] = {
        "product": chem["product"],
        "quantity": round(chem["dose_per_ha"] * zone_ha, 1),
        "unit": chem["unit"],
        "dose_per_acre": round(chem["dose_per_ha"] * HA_PER_ACRE, 1),
        "method": method,
        "water_l": round(water_l, 1),
        "knapsack_tanks": round(water_l / table["knapsack_tank_l"], 1) if method == "knapsack" else None,
        "repeat_after_days": row["repeat_after_days"],
        "alternatives": [c["product"] for c in row["chemical"] if c is not chem],
    }
    return plan


def savings(field_acres: float, zone_acres: float, cause: str, price_per_unit: float | None = None) -> dict:
    """Chemical not used because only the zone is sprayed instead of the whole field."""
    row = find(cause)
    if row is None or not row["chemical"]:
        return {"acres_not_sprayed": round(field_acres, 2), "chemical_saved": 0.0, "unit": None, "rupees_saved": None}
    chem = row["chemical"][0]
    saved = chem["dose_per_ha"] * (field_acres - zone_acres) * HA_PER_ACRE
    return {
        "acres_not_sprayed": round(field_acres - zone_acres, 2),
        "chemical_saved": round(saved, 1),
        "unit": chem["unit"],
        "rupees_saved": round(saved * price_per_unit, 0) if price_per_unit else None,
    }
