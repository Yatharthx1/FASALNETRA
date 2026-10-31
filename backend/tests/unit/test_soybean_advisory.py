import pytest

from backend.app.services.advisory.soybean import (
    evaluate_girdle_beetle_risk,
    get_soybean_profile,
    get_soybean_stage,
)


def test_soybean_growth_stages_progression():
    """Verifies phenological stage mapping across the entire soybean lifecycle."""
    s_emergence = get_soybean_stage(5)
    assert s_emergence["stage_code"] == "VE"
    assert "अंकुरण" in s_emergence["stage_name_hi"]

    s_early = get_soybean_stage(15)
    assert s_early["stage_code"] == "VC_V1"
    assert "तिपत्तिया" in s_early["stage_name_hi"]

    s_branching = get_soybean_stage(28)
    assert s_branching["stage_code"] == "V2_V3"

    # Demo field is at DAS 40: Flowering
    s_bloom = get_soybean_stage(40)
    assert s_bloom["stage_code"] == "R1_R2"
    assert s_bloom["water_sensitivity"] == "critical"
    assert "फूल" in s_bloom["stage_name_hi"]
    assert "0:52:34" in s_bloom["foliar_nutrition"]["product"]
    assert "yellow_mosaic" in s_bloom["key_threats"]

    s_pod = get_soybean_stage(60)
    assert s_pod["stage_code"] == "R3_R4"
    assert "फली" in s_pod["stage_name_hi"]

    s_seed = get_soybean_stage(78)
    assert s_seed["stage_code"] == "R5_R6"
    assert "दाना" in s_seed["stage_name_hi"]

    s_mature = get_soybean_stage(95)
    assert s_mature["stage_code"] == "R7_R8"
    assert "परिपक्वता" in s_mature["stage_name_hi"]


def test_girdle_beetle_risk_scoring():
    """Girdle beetle risk elevates during vegetative/branching with intermittent rain and sun."""
    fake_days = [
        {"rain_mm": 5.0, "sunshine_h": 6.5, "tmean": 27.5},
        {"rain_mm": 12.0, "sunshine_h": 5.0, "tmean": 26.0},
        {"rain_mm": 0.0, "sunshine_h": 9.0, "tmean": 28.5},
        {"rain_mm": 4.0, "sunshine_h": 7.0, "tmean": 27.0},
        {"rain_mm": 0.0, "sunshine_h": 8.5, "tmean": 28.0},
        {"rain_mm": 15.0, "sunshine_h": 4.5, "tmean": 26.5},
        {"rain_mm": 2.0, "sunshine_h": 7.5, "tmean": 27.2},
    ]

    gb_vulnerable = evaluate_girdle_beetle_risk(fake_days, das=32)
    assert gb_vulnerable["score"] >= 60
    assert gb_vulnerable["band"] in ("watch", "high")
    assert len(gb_vulnerable["drivers"]) >= 2
    assert "चक्र भृंग" in gb_vulnerable["drivers"][0]["hi"]

    # Outside window (e.g. at 85 DAS), risk is subdued
    gb_old = evaluate_girdle_beetle_risk(fake_days, das=85)
    assert gb_old["score"] < 40
    assert gb_old["band"] == "safe"


def test_soybean_profile_complete():
    """Verifies complete ICAR-IISR soybean agronomic profile generation."""
    profile = get_soybean_profile(das=40, variety="JS 335")
    assert profile["crop"] == "Soybean (सोयाबीन)"
    assert profile["variety"] == "JS 335"
    assert profile["current_stage"]["code"] == "R1_R2"
    assert profile["current_stage"]["water_sensitivity"] == "critical"
    assert profile["foliar_nutrition"] is not None
    assert "0:52:34" in profile["foliar_nutrition"]["product"]
    assert len(profile["icar_iisr_principles"]) >= 3
    assert len(profile["etl_threshold"]) > 5
