"""Unit tests for free weather data aggregation and agrometeorological advisory factors."""
from datetime import date
import pytest

from backend.app.services.advisory import weather_factors
from backend.app.services.risk import weather, rules


def test_calculate_vpd_physical_accuracy():
    """Verify Tetens equation calculation for saturation and vapor pressure deficit."""
    # At 30 C and 50% RH:
    # es = 0.61078 * exp((17.27 * 30) / (30 + 237.3)) = ~4.246 kPa
    # VPD = 4.246 * (1 - 0.5) = ~2.123 kPa
    vpd = weather.calculate_vpd_kpa(30.0, 50.0)
    assert vpd == pytest.approx(2.12, abs=0.05)

    # At 100% RH, deficit is 0
    assert weather.calculate_vpd_kpa(25.0, 100.0) == 0.0

    # At 0 C and 80% RH, deficit is low
    assert weather.calculate_vpd_kpa(0.0, 80.0) == pytest.approx(0.12, abs=0.02)


def test_spray_feasibility_optimal_morning_window():
    """Verify low wind and zero rain produces optimal drone spray window."""
    hourly_mock = {
        "time": [f"2025-08-16T{h:02d}:00" for h in range(24)],
        "temperature_2m": [22.0 + (h * 0.5) for h in range(24)],
        "relative_humidity_2m": [85.0 - (h * 1.5) for h in range(24)],
        "precipitation": [0.0] * 24,
        "wind_speed_10m": [6.0] * 24,
        "wind_gusts_10m": [9.0] * 24,
    }
    res = weather_factors.evaluate_spray_feasibility(hourly_mock, "2025-08-16", start_hour=6, duration_hours=6)
    assert res["overall_suitability"] == "optimal"
    assert res["best_window"] is not None
    assert "उत्तम" in res["advisory_hi"]
    assert res["mean_wind_kmh"] == 6.0


def test_spray_feasibility_high_wind_drift_hazard():
    """Verify wind speed > 16 km/h flags high drift risk and warns to delay spraying."""
    hourly_mock = {
        "time": [f"2025-08-16T{h:02d}:00" for h in range(24)],
        "temperature_2m": [28.0] * 24,
        "relative_humidity_2m": [60.0] * 24,
        "precipitation": [0.0] * 24,
        "wind_speed_10m": [22.0] * 24,  # Dangerous drift for drones
        "wind_gusts_10m": [30.0] * 24,
    }
    res = weather_factors.evaluate_spray_feasibility(hourly_mock, "2025-08-16", start_hour=6, duration_hours=6)
    assert res["overall_suitability"] == "hazardous"
    assert "टालें" in res["advisory_hi"]
    assert "drift" in res["advisory_en"].lower()


def test_vector_dispersal_factor_dry_breeze_spell():
    """Dry, sunny conditions with light breeze should produce elevated vector mobility factor."""
    days = [
        {
            "date": f"2025-08-{10+i:02d}",
            "tmax": 32.0,
            "rain_mm": 0.0,
            "sunshine_h": 9.5,
            "vector_favorable_h": 6,
            "vpd_mean_kpa": 1.8,
        }
        for i in range(7)
    ]
    res = weather_factors.vector_dispersal_factor(days)
    assert res["status"] in ("watch", "high")
    assert res["factor"] >= 0.6
    assert len(res["drivers"]) >= 2


def test_fungal_conduciveness_morning_dew_and_leaf_wetness():
    """Long leaf wetness and high morning humidity should trigger high fungal risk."""
    days = [
        {
            "date": f"2025-08-{10+i:02d}",
            "leaf_wet_h": 19,
            "morning_rh": 92.0,
            "tmean": 25.5,
        }
        for i in range(7)
    ]
    res = weather_factors.fungal_conduciveness_factor(days)
    assert res["status"] == "high"
    assert res["factor"] >= 0.8
