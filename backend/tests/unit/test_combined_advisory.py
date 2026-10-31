from datetime import date
import pytest

from backend.app.services.advisory.combined_score import compute_combined_advisory


def test_combined_advisory_demo_field_yellow_mosaic():
    """Sentinel patch + vector favorable weather produces high/critical YMV score with synergy boost."""
    fake_scan = {
        "summary": {
            "cells_in_field": 69,
            "cells_flagged": 27,
            "flagged_acres": 0.67,
            "pattern": "patch",
            "strength": 1.0,
            "low_spot_overlap": 0.04,
            "water_signal": -0.2,
            "worst_cell": {"z_ndvi": -2.016, "z_ndre": -4.635},
        }
    }
    # 7 days of dry, sunny, light-breeze weather
    fake_days = [
        {
            "date": f"2025-08-{10+i:02d}",
            "tmax": 32.0,
            "tmean": 27.0,
            "rain_mm": 0.0,
            "sunshine_h": 9.5,
            "vector_favorable_h": 8.0,
            "vpd_mean_kpa": 1.45,
            "leaf_wet_h": 4.0,
            "morning_rh": 65.0,
        }
        for i in range(7)
    ]

    res = compute_combined_advisory(
        satellite_scan=fake_scan,
        weather_days=fake_days,
        das=40,
        crop_type="soybean",
    )

    assert res["score"] >= 75
    assert res["band"] in ("high", "critical")
    assert res["primary_cause"] == "yellow_mosaic"
    assert res["synergy_multiplier"] > 1.0  # Joint reinforcement
    assert res["action"]["spray_recommended"] is True
    assert res["action"]["code"] == "targeted_spray"
    assert "0.67" in res["action"]["en"] or res["action"]["zone_acres"] == 0.67
    assert len(res["narrative"]["hi"]) > 10
    assert len(res["narrative"]["en"]) > 10
    assert res["components"]["satellite"]["flagged_cells"] == 27


def test_combined_advisory_healthy_field_weather_alert_capped_at_watch():
    """A field with 0 satellite flags must never trigger spray even if weather risk is high."""
    fake_scan = {
        "summary": {
            "cells_in_field": 69,
            "cells_flagged": 0,
            "flagged_acres": 0.0,
            "pattern": "none",
            "strength": 0.0,
            "low_spot_overlap": 0.0,
            "worst_cell": None,
        }
    }
    # High vector weather
    fake_days = [
        {
            "date": f"2025-08-{10+i:02d}",
            "tmax": 33.0,
            "tmean": 28.0,
            "rain_mm": 0.0,
            "sunshine_h": 10.0,
            "vector_favorable_h": 9.0,
            "vpd_mean_kpa": 1.6,
            "leaf_wet_h": 2.0,
            "morning_rh": 55.0,
        }
        for i in range(7)
    ]

    res = compute_combined_advisory(
        satellite_scan=fake_scan,
        weather_days=fake_days,
        das=40,
    )

    # Risk must be capped (no false sprays on a green field!)
    assert res["score"] < 50
    assert res["action"]["spray_recommended"] is False
    assert res["action"]["code"] in ("monitor", "trap_scout")
    assert res["band"] in ("safe", "watch")


def test_combined_advisory_waterlogging_in_low_spots():
    """Satellite anomaly overlapping a topographical depression after rain diagnosed as water stress."""
    fake_scan = {
        "summary": {
            "cells_in_field": 70,
            "cells_flagged": 18,
            "flagged_acres": 0.45,
            "pattern": "patch",
            "strength": 0.9,
            "low_spot_overlap": 0.85,  # 85% in depression
            "water_signal": -0.1,
            "worst_cell": {"z_ndvi": -2.5, "z_ndre": -2.2},
        }
    }
    fake_days = [
        {
            "date": f"2025-08-{10+i:02d}",
            "tmax": 26.0,
            "tmean": 23.0,
            "rain_mm": 25.0 if i < 3 else 2.0,  # recent heavy rain
            "sunshine_h": 2.0,
            "vector_favorable_h": 0.0,
            "vpd_mean_kpa": 0.3,
            "leaf_wet_h": 20.0,
            "morning_rh": 95.0,
        }
        for i in range(7)
    ]

    res = compute_combined_advisory(
        satellite_scan=fake_scan,
        weather_days=fake_days,
        das=35,
    )

    assert res["primary_cause"] == "water_stress"
    assert res["action"]["code"] == "drain_water"
    assert res["action"]["spray_recommended"] is False
    assert "निकासी" in res["action"]["hi"] or "drain" in res["action"]["en"].lower()


def test_combined_advisory_field_wide_nutrient_deficiency():
    """Field-wide uniform canopy decline diagnosed as nutrient deficiency with foliar advice."""
    fake_scan = {
        "summary": {
            "cells_in_field": 80,
            "cells_flagged": 55,
            "flagged_acres": 1.35,
            "pattern": "field_wide",
            "strength": 0.85,
            "low_spot_overlap": 0.1,
            "worst_cell": {"z_ndvi": -1.8, "z_ndre": -2.4},
        }
    }
    fake_days = [
        {
            "date": f"2025-08-{10+i:02d}",
            "tmax": 29.0,
            "tmean": 25.0,
            "rain_mm": 1.0,
            "sunshine_h": 6.0,
            "vector_favorable_h": 3.0,
            "vpd_mean_kpa": 0.9,
            "leaf_wet_h": 8.0,
            "morning_rh": 75.0,
        }
        for i in range(7)
    ]

    res = compute_combined_advisory(
        satellite_scan=fake_scan,
        weather_days=fake_days,
        das=45,
    )

    assert res["primary_cause"] == "nutrient"
    assert res["action"]["code"] == "foliar_nutrition"
    assert res["action"]["spray_recommended"] is False
    assert "19:19:19" in res["action"]["en"]


def test_combined_advisory_weather_hostile_dampens_threat():
    """Satellite patch accompanied by heavy monsoon downpour dampens pest progression."""
    fake_scan = {
        "summary": {
            "cells_in_field": 70,
            "cells_flagged": 20,
            "flagged_acres": 0.5,
            "pattern": "patch",
            "strength": 0.7,
            "low_spot_overlap": 0.1,
            "worst_cell": {"z_ndvi": -2.0, "z_ndre": -3.0},
        }
    }
    # Heavy continuous rain washes out whitefly vectors
    fake_days = [
        {
            "date": f"2025-08-{10+i:02d}",
            "tmax": 24.0,
            "tmean": 22.0,
            "rain_mm": 35.0,
            "sunshine_h": 0.5,
            "vector_favorable_h": 0.0,
            "vpd_mean_kpa": 0.2,
            "leaf_wet_h": 22.0,
            "morning_rh": 98.0,
        }
        for i in range(7)
    ]

    res = compute_combined_advisory(
        satellite_scan=fake_scan,
        weather_days=fake_days,
        das=35,
    )

    ymv_cause = res["causes"]["yellow_mosaic"]
    # Dampened synergy due to vector washout
    assert ymv_cause["synergy_multiplier"] < 1.0
