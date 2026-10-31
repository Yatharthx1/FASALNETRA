"""Combined Sentinel-2 Satellite + Weather Agro-Advisory Scoring Engine.

Fuses high-resolution Sentinel-2 multispectral anomaly detection (NDRE/NDVI/NDMI
z-scores, spatial patch morphology, elevation depression overlap) with local
agrometeorological risk drivers (pest vector dispersal breeze, VPD, leaf wetness,
spore germination humidity, spray feasibility) into a unified operational score.
"""
from datetime import date
from typing import Any

from backend.app.services.advisory import soybean, weather_factors


# Agronomic constants for soybean (Glycine max)
SOYBEAN_VULNERABILITY = {
    "yellow_mosaic": (15, 50),     # Whitefly-borne Begomovirus: most destructive at early vegetative/flowering
    "fungal": (25, 75),            # Aerial blight / Rhizoctonia / anthracnose: canopy closure to pod filling
    "chewing_damage": (20, 65),    # Spodoptera / semilooper: foliage feeding peak
    "water_stress": (10, 90),      # Moisture sensitivity across entire life cycle
    "nutrient": (15, 80),          # Nutrient deficiency
}

CAUSE_METADATA = {
    "yellow_mosaic": {
        "name_en": "Yellow Mosaic Virus (YMV)",
        "name_hi": "पीला मोज़ेक वायरस (YMV)",
        "icon": "bug",
    },
    "fungal": {
        "name_en": "Aerial Blight / Fungal Spot",
        "name_hi": "फंगल झुलसा रोग (फफूंद)",
        "icon": "leaf",
    },
    "water_stress": {
        "name_en": "Waterlogging or Soil Moisture Stress",
        "name_hi": "जलभराव अथवा नमी की कमी",
        "icon": "droplet",
    },
    "nutrient": {
        "name_en": "Nutrient Deficiency (Nitrogen/Micronutrients)",
        "name_hi": "पोषक तत्वों की कमी (पीलापन)",
        "icon": "activity",
    },
    "healthy": {
        "name_en": "Healthy Crop Canopy",
        "name_hi": "फसल स्वस्थ और सुरक्षित",
        "icon": "check-circle",
    },
}


def compute_combined_advisory(
    satellite_scan: dict[str, Any] | None,
    weather_days: list[dict[str, Any]] | None,
    das: int = 40,
    crop_type: str = "soybean",
    hourly_weather: dict[str, Any] | None = None,
    target_date: date | str | None = None,
) -> dict[str, Any]:
    """Computes a fused 0-100 advisory score combining satellite canopy anomalies and weather drivers.

    Args:
        satellite_scan: Output of satellite.scan() containing summary (cells_flagged, pattern, strength, etc.)
        weather_days: List of daily_features dicts over a rolling 7 to 15 day window
        das: Days after sowing
        crop_type: Crop identifier (default: soybean)
        hourly_weather: Optional Open-Meteo hourly dict for spray feasibility calculation
        target_date: Optional target date for hourly spray evaluation

    Returns:
        Structured combined advisory dictionary with score (0-100), risk band, primary cause,
        component breakdowns, synergy factor, and bilingual farmer guidance.
    """
    days = weather_days or []
    summary = (satellite_scan or {}).get("summary", {})
    soy_stage = soybean.get_soybean_stage(das)

    # --- 1. Extract Satellite Features ---
    flagged_cells = summary.get("cells_flagged", 0)
    flagged_acres = summary.get("flagged_acres", 0.0)
    pattern = summary.get("pattern", "none")
    sat_strength = float(summary.get("strength", 0.0))
    low_spot_overlap = float(summary.get("low_spot_overlap", 0.0))
    water_signal = summary.get("water_signal")

    worst_cell = summary.get("worst_cell") or {}
    z_ndre = worst_cell.get("z_ndre")
    z_ndvi = worst_cell.get("z_ndvi")

    # Satellite cause affinity
    sat_cause_scores: dict[str, float] = {
        "yellow_mosaic": 0.0,
        "fungal": 0.0,
        "water_stress": 0.0,
        "nutrient": 0.0,
    }

    sat_drivers: list[dict[str, str]] = []

    if flagged_cells > 0:
        if pattern == "patch":
            # Compact patch indicates expanding biological foci (vector-spread virus or fungal pocket)
            if low_spot_overlap >= 0.6:
                sat_cause_scores["water_stress"] = sat_strength
                sat_drivers.append({
                    "en": f"Satellite detected {flagged_acres} acre patch concentrated in low-lying depression ({low_spot_overlap*100:.0f}% overlap) - high waterlogging risk",
                    "hi": f"उपग्रह ने निचले हिस्से में {flagged_acres} एकड़ में जलभराव का पैच पहचाना ({low_spot_overlap*100:.0f}% ओवरलैप)",
                })
            else:
                # Chlorophyll drop (NDRE) is a leading indicator for Yellow Mosaic chlorosis
                ndre_drop = abs(z_ndre) if (z_ndre is not None and z_ndre < 0) else 1.5
                ymv_weight = min(1.0, 0.5 + 0.1 * ndre_drop)
                sat_cause_scores["yellow_mosaic"] = round(sat_strength * ymv_weight, 3)
                sat_cause_scores["fungal"] = round(sat_strength * 0.75, 3)

                sat_drivers.append({
                    "en": f"Satellite flagged {flagged_acres} acre localized stress patch (strength {sat_strength:.2f}) with distinct NDRE chlorophyll drop (Z={z_ndre})",
                    "hi": f"उपग्रह ने {flagged_acres} एकड़ में केंद्रित तनाव पैच (तीव्रता {sat_strength:.2f}) और क्लोरोफिल की कमी (Z={z_ndre}) दर्ज की",
                })

        elif pattern == "field_wide":
            # Whole field is evenly declining: typical of nutrient deficiency or generalized moisture stress
            sat_cause_scores["nutrient"] = round(sat_strength * 0.85, 3)
            sat_cause_scores["water_stress"] = round(sat_strength * 0.65, 3)
            sat_drivers.append({
                "en": f"Field-wide uniform canopy decline ({flagged_acres} acres) suggests nutrient deficiency or moisture stress rather than localized pest",
                "hi": f"पूरे खेत में एक समान फैलाव ({flagged_acres} एकड़), जो कीट के बजाय पोषक तत्वों की कमी या पानी की समस्या दर्शाता है",
            })

        elif pattern == "scattered":
            sat_cause_scores["yellow_mosaic"] = round(sat_strength * 0.4, 3)
            sat_cause_scores["fungal"] = round(sat_strength * 0.4, 3)
            sat_drivers.append({
                "en": f"Scattered weak spots ({flagged_acres} acres) detected across field",
                "hi": f"खेत में बिखरे हुए हल्के कमजोर धब्बे ({flagged_acres} एकड़) मिले",
            })
    else:
        sat_drivers.append({
            "en": "Sentinel-2 satellite confirms healthy, uniform crop canopy with zero flagged anomaly cells",
            "hi": "सेंटिनल-2 उपग्रह के अनुसार फसल का फैलाव एक समान और स्वस्थ है, कोई विसंगति नहीं मिली",
        })

    # --- 2. Extract Weather Factors ---
    vector_eval = weather_factors.vector_dispersal_factor(days)
    fungal_eval = weather_factors.fungal_conduciveness_factor(days)

    vector_score = vector_eval.get("factor", 0.0)
    fungal_score = fungal_eval.get("factor", 0.0)

    # Weather moisture / waterlogging score
    recent_rain = sum(d.get("rain_mm", 0.0) for d in days[:3]) if days else 0.0
    water_stress_weather = min(1.0, recent_rain / 70.0) if recent_rain > 30.0 else 0.2

    wea_cause_scores: dict[str, float] = {
        "yellow_mosaic": vector_score,
        "fungal": fungal_score,
        "water_stress": round(water_stress_weather, 3),
        "nutrient": 0.25 if recent_rain > 60.0 else 0.1,  # heavy rain leaches nitrogen
    }

    wea_drivers: list[dict[str, str]] = []
    if vector_score >= 0.5:
        wea_drivers.extend(vector_eval.get("drivers", []))
    if fungal_score >= 0.5:
        wea_drivers.extend(fungal_eval.get("drivers", []))
    if not wea_drivers:
        wea_drivers.append({
            "en": "Weather conditions are currently moderate with low disease pressure",
            "hi": "वर्तमान मौसम सामान्य है और रोग का दबाव कम है",
        })

    # --- 3. Crop Stage Susceptibility ---
    crop_stage_weights: dict[str, float] = {}
    for cause, (d_start, d_end) in SOYBEAN_VULNERABILITY.items():
        if d_start <= das <= d_end:
            crop_stage_weights[cause] = 1.0
        elif (d_start - 7) <= das <= (d_end + 10):
            crop_stage_weights[cause] = 0.6
        else:
            crop_stage_weights[cause] = 0.25

    # --- 4. Fused Scoring & Synergy Computation ---
    fused_causes: dict[str, dict[str, Any]] = {}

    for cause in ["yellow_mosaic", "fungal", "water_stress", "nutrient"]:
        s_val = sat_cause_scores[cause]
        w_val = wea_cause_scores[cause]
        c_val = crop_stage_weights.get(cause, 0.5)

        if flagged_cells > 0:
            base_score = 0.45 * s_val + 0.40 * w_val + 0.15 * c_val

            # Synergy Multiplier:
            # If both satellite detects a patch AND weather conditions strongly favor that disease/pest,
            # they reinforce each other with a synergy boost of up to +25%.
            if s_val >= 0.5 and w_val >= 0.5:
                synergy = 1.25
            elif s_val >= 0.4 and w_val >= 0.4:
                synergy = 1.15
            elif s_val >= 0.5 and w_val < 0.25:
                # Weather is hostile to the threat (e.g. heavy rain suppressing whiteflies)
                synergy = 0.85
            else:
                synergy = 1.0

            final_cause_score = min(1.0, base_score * synergy)
        else:
            # No satellite anomaly: crop is currently clean on the ground.
            # Weather risk serves as a prophylactic watch warning, capped at 0.45
            synergy = 1.0
            final_cause_score = min(0.45, (0.75 * w_val + 0.25 * c_val) * 0.55)

        fused_causes[cause] = {
            "score": round(final_cause_score * 100, 1),
            "sat_component": round(s_val, 3),
            "wea_component": round(w_val, 3),
            "crop_component": round(c_val, 3),
            "synergy_multiplier": synergy,
        }

    # Find primary threat
    if flagged_cells == 0 and all(fc["score"] < 40 for fc in fused_causes.values()):
        primary_cause = "healthy"
        overall_score = max(5.0, max(fc["score"] for fc in fused_causes.values()))
    else:
        primary_cause = max(fused_causes, key=lambda c: fused_causes[c]["score"])
        overall_score = fused_causes[primary_cause]["score"]

    overall_score = round(overall_score, 1)

    # Risk Band Determination
    if overall_score >= 80:
        band = "critical"
        level = "high"
    elif overall_score >= 60:
        band = "high"
        level = "high"
    elif overall_score >= 40:
        band = "watch"
        level = "medium"
    else:
        band = "safe"
        level = "low"

    # Action Recommendations
    if primary_cause == "healthy":
        action_code = "monitor"
        action_en = "Routine field inspection. No intervention required."
        action_hi = "नियमित खेत निरीक्षण करें। किसी छिड़काव की आवश्यकता नहीं है।"
    elif primary_cause == "water_stress":
        action_code = "drain_water" if low_spot_overlap >= 0.5 else "irrigate"
        if action_code == "drain_water":
            action_en = f"Drain standing water from {flagged_acres} acre depression. Do NOT spray chemicals."
            action_hi = f"{flagged_acres} एकड़ निचले हिस्से से जल निकासी करें। कोई रासायनिक दवा न छिड़कें।"
        else:
            action_en = "Provide light irrigation or conserve soil moisture with mulch. No chemical spray."
            action_hi = "हल्की सिंचाई की व्यवस्था करें या नमी बनाए रखें। रासायनिक छिड़काव न करें।"
    elif primary_cause == "nutrient":
        action_code = "foliar_nutrition"
        action_en = f"Apply water-soluble 19:19:19 NPK foliar spray across {flagged_acres} acres to relieve chlorosis."
        action_hi = f"पीलापन दूर करने के लिए {flagged_acres} एकड़ में 19:19:19 NPK का पर्णीय छिड़काव करें।"
    elif primary_cause in ("yellow_mosaic", "fungal"):
        if level == "high":
            action_code = "targeted_spray"
            target_acres = flagged_acres if flagged_acres > 0 else 0.5
            cause_hi = CAUSE_METADATA[primary_cause]["name_hi"]
            action_en = f"Book precision Drone Didi spray targeted ONLY to the {target_acres} acre flagged zone."
            action_hi = f"ड्रोन दीदी द्वारा केवल प्रभावित {target_acres} एकड़ पैच में {cause_hi} के नियंत्रण हेतु छिड़काव कराएं।"
        else:
            action_code = "trap_scout"
            action_en = "Install 5-8 yellow sticky traps per acre and scout the satellite-marked patch."
            action_hi = "प्रति एकड़ 5-8 पीले चिपचिपे ट्रैप लगाएं और उपग्रह द्वारा चिह्नित स्थान की जांच करें।"
    else:
        action_code = "expert_scout"
        action_en = "KVK / Field scout verification recommended."
        action_hi = "कृषि विज्ञान केंद्र (KVK) विशेषज्ञ या जमीनी जांच की सलाह दी जाती है।"

    # Spray Feasibility (if hourly data provided)
    spray_eval = None
    if hourly_weather and target_date:
        spray_eval = weather_factors.evaluate_spray_feasibility(hourly_weather, target_date)

    # Narrative Summary Bilingual Generation
    meta = CAUSE_METADATA.get(primary_cause, CAUSE_METADATA["healthy"])
    if level == "high":
        narrative_en = (
            f"HIGH RISK ({overall_score}/100) for {meta['name_en']}. "
            f"Soybean is at {soy_stage['stage_name_en']} (DAS {das}). "
            f"Sentinel-2 confirms a {flagged_acres} acre active stress patch, "
            f"amplified by highly favorable local weather conditions."
        )
        narrative_hi = (
            f"उच्च जोखिम ({overall_score}/100) - {meta['name_hi']} का गंभीर खतरा! "
            f"सोयाबीन {soy_stage['stage_name_hi']} (DAS {das}) में है। "
            f"सेंटिनल-2 उपग्रह ने {flagged_acres} एकड़ में सक्रिय तनाव पैच दर्ज किया है, "
            f"और स्थानीय मौसम भी इसके फैलाव के पूरी तरह अनुकूल है।"
        )
    elif level == "medium":
        narrative_en = (
            f"WATCH ALERT ({overall_score}/100) for {meta['name_en']} at {soy_stage['stage_name_en']} (DAS {das}). "
            f"Weather pressure is elevated and early canopy signs are emerging. Active scouting advised."
        )
        narrative_hi = (
            f"निगरानी चेतावनी ({overall_score}/100) - {meta['name_hi']} की संभावना ({soy_stage['stage_name_hi']}, DAS {das})। "
            f"मौसम कीट/रोग के अनुकूल हो रहा है। खेत में नियमित निगरानी रखें।"
        )
    else:
        narrative_en = f"LOW RISK ({overall_score}/100). Soybean canopy is healthy at {soy_stage['stage_name_en']} with minimal microclimate pressure."
        narrative_hi = f"सुरक्षित स्थिति ({overall_score}/100)। {soy_stage['stage_name_hi']} में फसल पूरी तरह स्वस्थ है।"

    return {
        "score": overall_score,
        "band": band,
        "level": level,
        "primary_cause": primary_cause,
        "primary_cause_en": meta["name_en"],
        "primary_cause_hi": meta["name_hi"],
        "crop": "soybean",
        "crop_age_das": das,
        "soybean_stage": {
            "code": soy_stage["stage_code"],
            "name_en": soy_stage["stage_name_en"],
            "name_hi": soy_stage["stage_name_hi"],
            "water_sensitivity": soy_stage["water_sensitivity"],
            "foliar_nutrition": soy_stage["foliar_nutrition"],
        },
        "synergy_multiplier": fused_causes[primary_cause]["synergy_multiplier"] if primary_cause in fused_causes else 1.0,
        "action": {
            "code": action_code,
            "en": action_en,
            "hi": action_hi,
            "spray_recommended": action_code == "targeted_spray",
            "zone_acres": flagged_acres if flagged_acres > 0 else None,
        },
        "narrative": {
            "en": narrative_en,
            "hi": narrative_hi,
        },
        "components": {
            "satellite": {
                "score": round(sat_cause_scores.get(primary_cause, 0.0) * 100, 1),
                "pattern": pattern,
                "strength": sat_strength,
                "flagged_cells": flagged_cells,
                "flagged_acres": flagged_acres,
                "z_ndre": z_ndre,
                "z_ndvi": z_ndvi,
                "low_spot_overlap": low_spot_overlap,
                "drivers": sat_drivers,
            },
            "weather": {
                "score": round(wea_cause_scores.get(primary_cause, 0.0) * 100, 1),
                "vector_dispersal_factor": round(vector_score, 3),
                "fungal_conduciveness_factor": round(fungal_score, 3),
                "spray_feasibility": spray_eval,
                "drivers": wea_drivers,
            },
            "crop_stage": {
                "das": das,
                "stage_code": soy_stage["stage_code"],
                "stage_name_en": soy_stage["stage_name_en"],
                "stage_name_hi": soy_stage["stage_name_hi"],
                "vulnerability_factor": crop_stage_weights.get(primary_cause, 0.5),
            },
        },
        "causes": fused_causes,
    }
