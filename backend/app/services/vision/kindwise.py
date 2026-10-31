"""Second photo opinion from Kindwise: crop.health (crops) or plant.id health assessment. Needs KINDWISE_API_KEY.

Kindwise answers with its own disease / pest names; they are mapped onto our labels by keyword
(risk/pests.py). Its treatment text is not used: doses come only from the ICAR-NSRI table.

    KINDWISE_API_KEY   key for the product below (keys are per product)
    KINDWISE_PRODUCT   crop (crop.health, default) | plant (plant.id health assessment)
"""
import base64
import logging
import os

import requests

from backend.app.services.risk.pests import KINDWISE_NON_PEST, PESTS

log = logging.getLogger(__name__)

URLS = {"crop": "https://crop.kindwise.com/api/v1/identification",
        "plant": "https://plant.id/api/v3/health_assessment"}
TIMEOUT_S = 25
SOYBEAN = ("glycine max", "soybean", "soya")


def available() -> bool:
    return bool(os.environ.get("KINDWISE_API_KEY"))


def label_for(name: str) -> str:
    """Kindwise suggestion name (common or scientific) -> our photo label."""
    n = name.lower()
    for label, words in KINDWISE_NON_PEST.items():
        if any(w in n for w in words):
            return label
    for cause in ("girdle_beetle", "yellow_mosaic", "chewing_damage", "fungal"):   # most specific first
        if any(w in n for w in PESTS[cause]["kindwise_keywords"]):
            return cause
    return "unsure"


def parse(resp: dict) -> dict:
    """Kindwise result -> {label, confidence, suggestions, is_soybean}; probabilities of names that map to the
    same label are added up."""
    result = resp.get("result") or {}
    sugg = (result.get("disease") or {}).get("suggestions") or []
    mass: dict[str, float] = {}
    for s in sugg:
        name = f"{s.get('name', '')} {s.get('scientific_name', '')}"
        lab = label_for(name)
        mass[lab] = mass.get(lab, 0.0) + float(s.get("probability") or 0)
    known = {k: v for k, v in mass.items() if k != "unsure"}
    label = max(known, key=known.get) if known else "unsure"
    crops = (result.get("crop") or {}).get("suggestions") or []
    top_crop = f"{crops[0].get('name', '')} {crops[0].get('scientific_name', '')}".lower() if crops else ""
    return {"label": label, "confidence": round(min(1.0, known.get(label, 0.0)), 3),
            "is_soybean": any(w in top_crop for w in SOYBEAN) if crops else None,
            "suggestions": [{"name": s.get("name"), "probability": s.get("probability"),
                             "label": label_for(f"{s.get('name', '')} {s.get('scientific_name', '')}")}
                            for s in sugg[:5]]}


def classify(jpeg: bytes, lat: float | None = None, lon: float | None = None) -> dict | None:
    """None when not configured or the call fails: a missing second opinion must never block a photo."""
    key = os.environ.get("KINDWISE_API_KEY")
    if not key:
        return None
    product = os.environ.get("KINDWISE_PRODUCT", "crop")
    body: dict = {"images": [base64.b64encode(jpeg).decode()], "similar_images": False}
    if lat is not None and lon is not None:
        body.update(latitude=lat, longitude=lon)
    try:
        r = requests.post(URLS.get(product, URLS["crop"]), json=body, headers={"Api-Key": key}, timeout=TIMEOUT_S)
        r.raise_for_status()
        return {**parse(r.json()), "provider": f"kindwise_{product}"}
    except (requests.RequestException, ValueError) as exc:
        log.warning("Kindwise %s failed: %s", product, exc)
        return None
