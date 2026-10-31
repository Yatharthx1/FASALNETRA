"""The literature-calibrated weather rules (risk/rules.py) on synthetic weather, one behaviour per test."""
from datetime import date, timedelta

import pytest

from backend.app.services.risk import rules, weather


def _days(n: int = rules.HISTORY, **kw) -> list[dict]:
    """n calm, mild days; keyword lists (or single values) override one feature per day."""
    start = date(2025, 8, 1)
    base = {"tmax": 29.0, "tmin": 23.0, "tmean": 26.0, "rain_mm": 5.0, "sunshine_h": 5.0, "leaf_wet_h": 8,
            "evening_rh": 88.0, "rh_mean": 75.0, "morning_rh": 80.0, "soil_moisture": 0.45, "vpd_kpa": 0.8}
    out = []
    for i in range(n):
        d = {"date": str(start + timedelta(days=i)), **base}
        for k, v in kw.items():
            d[k] = v[i] if isinstance(v, list) else v
        out.append(d)
    return out


def _score(fn, days):
    return fn(days)[0]


# --- yellow mosaic / whitefly --------------------------------------------------------------------------------------

def test_a_monsoon_break_of_a_week_drives_yellow_mosaic():
    wet = _days(rain_mm=8.0)
    brk = _days(rain_mm=[8.0] * 7 + [0.0] * 7)          # last 7 days dry
    assert rules._longest_dry_run(brk, 2.0) == 7
    assert _score(rules._yellow_mosaic, brk) - _score(rules._yellow_mosaic, wet) >= 0.3


def test_yellow_mosaic_heat_is_graded_up_to_full_credit():
    # ramp 29 -> 32 C: 29.3 C is worth 0.1 hot day, so 14 such days give 1.4 of the 5 needed
    cool, warm, hot = (_score(rules._yellow_mosaic, _days(tmax=t)) for t in (28.0, 29.3, 32.0))
    assert cool < warm < hot
    assert warm - cool == pytest.approx(0.30 * 1.4 / 5, abs=0.01)
    assert hot - cool == pytest.approx(0.30, abs=0.01)    # 14 hot days > 5 needed: the whole 0.30 heat weight


def test_dry_hot_low_humidity_fortnight_is_high_and_wet_one_is_safe():
    peak = _days(rain_mm=0.0, tmax=33.0, evening_rh=70.0, sunshine_h=10.5)
    wet = _days(rain_mm=20.0, tmax=28.0, evening_rh=92.0, sunshine_h=3.0)
    assert 100 * _score(rules._yellow_mosaic, peak) >= rules.HIGH
    assert 100 * _score(rules._yellow_mosaic, wet) < rules.WATCH


# --- aerial blight (fungal) ----------------------------------------------------------------------------------------

def test_aerial_blight_temperature_band_is_27_to_30():
    assert rules._band_fit(28.5, 27.0, 30.0) == 1.0
    assert rules._band_fit(31.0, 27.0, 30.0) == pytest.approx(0.5)
    assert rules._band_fit(33.0, 27.0, 30.0) == 0.0
    inside = _score(rules._fungal, _days(tmax=28.5))
    outside = _score(rules._fungal, _days(tmax=33.0))
    assert inside - outside == pytest.approx(0.25, abs=0.01)


def test_aerial_blight_counts_last_weeks_rain_not_this_weeks():
    prev_wet = _days(rain_mm=[10.0] * 7 + [0.0] * 7)
    this_wet = _days(rain_mm=[0.0] * 7 + [10.0] * 7)
    assert _score(rules._fungal, prev_wet) > _score(rules._fungal, this_wet)


def test_humid_wet_blight_week_scores_high():
    days = _days(tmax=28.5, rh_mean=90.0, leaf_wet_h=20, rain_mm=[12.0] * 7 + [3.0] * 7)
    assert 100 * _score(rules._fungal, days) >= rules.HIGH


# --- caterpillars (Spodoptera litura degree-days) ------------------------------------------------------------------

def test_degree_days_use_the_12_1_c_base():
    days = _days(n=2, tmax=[30.0, 10.0], tmin=[22.0, 5.0])
    assert rules.degree_days(days, 12.1) == pytest.approx(26.0 - 12.1)   # cold day adds nothing, never negative


def test_warmer_weeks_speed_up_caterpillar_generations_and_stay_capped():
    cool = _score(rules._chewing, _days(tmax=22.0, tmin=16.0))
    warm = _score(rules._chewing, _days(tmax=32.0, tmin=25.0))
    assert warm > cool
    best = _days(tmax=32.0, tmin=25.0, rain_mm=10.0, rh_mean=85.0)
    assert _score(rules._chewing, best) <= rules.RULES["chewing_damage"]["weather_cap"] + 1e-9


# --- girdle beetle -------------------------------------------------------------------------------------------------

def test_girdle_beetle_follows_morning_not_daily_humidity():
    humid_mornings = _days(morning_rh=93.0, rh_mean=70.0)
    dry_mornings = _days(morning_rh=75.0, rh_mean=90.0)
    assert _score(rules._girdle, humid_mornings) > _score(rules._girdle, dry_mornings)


def test_girdle_beetle_without_morning_humidity_data_does_not_crash():
    assert _score(rules._girdle, _days(morning_rh=None)) >= 0


# --- waterlogging --------------------------------------------------------------------------------------------------

def test_waterlogging_needs_a_four_day_saturated_run():
    three = _days(soil_moisture=[0.45] * 10 + [0.52] * 3 + [0.45])
    split = _days(soil_moisture=[0.45] * 7 + [0.52, 0.52, 0.45, 0.52, 0.52, 0.45, 0.45])
    four = _days(soil_moisture=[0.45] * 10 + [0.52] * 4)
    s3, s_split, s4 = (_score(rules._waterlogging, d) for d in (three, split, four))
    assert s4 > s3 > s_split
    cap = rules.RULES["water_stress"]["weather_cap"]
    assert s4 == pytest.approx(cap * 0.6 + cap * 0.4 * 5 * 2 / 64.5, abs=0.01)


def test_waterlogging_uses_heavy_rain_over_two_days():
    days = _days(rain_mm=[0.0] * 12 + [40.0, 30.0])
    assert "70 mm rain in 2 days" in rules._waterlogging(days)[1][1][1]


def test_weather_vote_for_waterlogging_only_looks_at_the_last_week():
    scored = rules.score_days(_days(n=28, soil_moisture=[0.52] * 14 + [0.45] * 14), date(2025, 7, 1))
    assert len(scored) == 15
    on = scored[-1]["date"]
    old = max(d["causes"]["water_stress"]["score"] for d in scored) / 100
    vote = rules.weather_vote(scored, on)
    assert old > vote["water_stress"]                       # the saturated spell 2+ weeks ago no longer counts
    assert vote["yellow_mosaic"] == max(d["causes"]["yellow_mosaic"]["score"] for d in scored[-14:]) / 100


# --- missing extra weather layer -----------------------------------------------------------------------------------

def test_rules_still_score_without_the_extra_weather_layer():
    days = _days()
    for d in days:
        for k in ("soil_moisture", "morning_rh", "vpd_kpa", "rh_mean"):
            d.pop(k)
    out = rules.score_days(days, date(2025, 7, 1))
    assert out and set(out[0]["causes"]) == set(rules.SCORERS)
    assert "no soil moisture data" in rules._waterlogging(days)[1][0][1]


def test_daily_features_without_extra_layer_set_new_fields_to_none():
    hourly = {"time": [f"2025-08-01T{h:02d}:00" for h in range(24)], "temperature_2m": [25.0] * 24,
              "relative_humidity_2m": [80.0] * 24, "dew_point_2m": [21.0] * 24, "precipitation": [0.0] * 24,
              "sunshine_duration": [0.0] * 24}
    day = weather.daily_features(hourly)[0]
    assert day["soil_moisture"] is None and day["vpd_kpa"] is None and day["morning_rh"] == 80.0
    with_soil = weather.daily_features({**hourly, "soil_moisture_0_to_7cm": [0.4] * 23 + [0.5]})[0]
    assert with_soil["soil_moisture"] == 0.5             # wettest hour of the day
