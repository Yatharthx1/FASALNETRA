"""Crop knowledge packs: everything the advisory writer may say, assembled from vetted sources.

A pack per crop. A case's facts come only from here: the evidence card (cause, confidence, zone), the ICAR-NSRI
table (product and dose, scaled to the zone), the crop's growth stage with its economic threshold level and
cultural practice (Yatharth's soybean stage model), the pest profile (risk/pests.py), the spray window, and the
farmer's IVR answers. The writer turns these facts into words; it adds no facts of its own.

A crop with no pack is never advised automatically: the case goes to Drone Didi.
"""
import json
import re

from backend.app.services import advisory
from backend.app.services.advisory import soybean
from backend.app.services.risk.pests import PESTS

# Example advisories per crop (in-context examples for the LLM: tone, length, order). Numbers are placeholders.
EXAMPLES = {
    "soybean": [
        {"say_hi": "आपकी सोयाबीन में पीले मोज़ेक का शक है। सिर्फ बीमार हिस्से में {PRODUCT} का छिड़काव करें, पूरे खेत में नहीं।",
         "advisory_hi": "आपकी सोयाबीन फूल आने की अवस्था में है और लगभग {ZONE_ACRES} एकड़ हिस्से में पीले मोज़ेक का शक है। "
                        "पहले बीमार पौधे उखाड़कर नष्ट करें और पीले चिपचिपे जाल लगाएं। फिर सिर्फ उसी हिस्से में {PRODUCT} "
                        "{QUANTITY} {UNIT} को {WATER_L} लीटर पानी में मिलाकर छिड़काव करें। छिड़काव {WINDOW} के समय करें, "
                        "जब हवा धीमी हो और बारिश न हो। पड़ोस के मूंग-उड़द वाले खेतों पर भी नज़र रखें।"},
    ],
}

SIGNAL_HI = {"photo_ai": "फोटो जांच", "photo_match": "फोटो मिलान", "photo_expert": "दूसरी फोटो जांच", "traps": "पीले जाल",
             "keypad": "आपका जवाब", "weather": "मौसम", "crop_stage": "फसल की उम्र", "advisory": "ICAR सलाह",
             "satellite": "सैटेलाइट", "neighbours": "पड़ोसी खेत", "season": "मौसम का समय", "field_profile": "खेत की जानकारी"}

# Spoken names in Devanagari (the table's name_hi is Latin-script Hinglish, which a Hindi voice reads badly)
CAUSE_HI = {"yellow_mosaic": "पीला मोज़ेक (सफेद मक्खी से फैलने वाला)", "fungal": "पत्तों का झुलसा (फफूंद)",
            "chewing_damage": "इल्ली का नुकसान", "girdle_beetle": "गर्डल बीटल (चक्र भृंग)",
            "water_stress": "पानी की कमी या जलभराव", "nutrient": "खाद की कमी"}

CROPS = {
    "soybean": {"name_hi": "सोयाबीन", "stage": soybean.get_soybean_stage},
}


def supported(crop: str | None) -> bool:
    return (crop or "").lower() in CROPS


def build_facts(*, crop: str, evidence: dict, das: int, zone_acres: float | None, field_acres: float,
                spray_window: dict | None = None, profile: dict | None = None) -> dict:
    """The facts of one case, plus the exact numbers the advisory is allowed to contain."""
    pack = CROPS[crop.lower()]
    stage = pack["stage"](das)
    row = advisory.find(evidence["cause"]) or {}
    spray = (evidence.get("plan") or {}).get("spray")
    best = (spray_window or {}).get("best")
    facts = {
        "crop": crop, "crop_hi": pack["name_hi"], "days_after_sowing": das,
        "stage_hi": stage.get("stage_name_hi"), "stage_etl": stage.get("etl"),
        "stage_practice_hi": stage.get("cultural_guidance_hi"),
        "cause": evidence["cause"], "cause_hi": CAUSE_HI.get(evidence["cause"]) or row.get("name_hi"),
        "is_pest": bool(row.get("chemical")),
        "confidence_pct": round(evidence["confidence"] * 100), "level": evidence["level"], "action": evidence["action"],
        "agreeing_hi": [SIGNAL_HI.get(s, s) for s in evidence.get("agreeing_signals", [])],
        "zone_acres": round(zone_acres, 2) if zone_acres else None, "field_acres": round(field_acres, 2),
        "icar_practices": row.get("cultural", []), "icar_threshold": row.get("action_threshold"),
        "pest_habitat": (PESTS.get(evidence["cause"]) or {}).get("habitat"),
        "neighbour_crop": (profile or {}).get("neighbor_crop"), "grassy_border": (profile or {}).get("grassy_border"),
        "spray": {"product": spray["product"], "quantity": spray["quantity"], "unit": spray["unit"],
                  "water_l": spray["water_l"], "repeat_after_days": spray.get("repeat_after_days")} if spray else None,
        "spray_window": best[11:16] if best else None,          # "06:00"
        "source": (evidence.get("plan") or {}).get("source"),
    }
    # Every number the farmer may hear: only numbers already in these vetted facts (doses, zone, thresholds...)
    facts["allowed_numbers"] = sorted(numbers_in(facts))
    return facts


_DEVANAGARI = str.maketrans("०१२३४५६७८९", "0123456789")


def numbers_in(value) -> set[str]:
    """All numbers in a value (nested), normalised: '0.40' -> '0.4', Devanagari digits -> ASCII, '06:00' -> 6, 0."""
    text = json.dumps(value, ensure_ascii=False).translate(_DEVANAGARI)
    return {f"{float(n.replace(',', '.')):g}" for n in re.findall(r"\d+(?:[.,]\d+)?", text)}
