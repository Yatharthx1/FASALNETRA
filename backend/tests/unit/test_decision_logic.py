"""Behaviour of the pieces that decide what a farmer is told: advisory doses, evidence routing, voice menu, links."""
import pytest
from shapely.geometry import Polygon, mapping

from backend.app.services import advisory, communications, evidence, missions
from backend.app.services.communications.registered_state_machine import (
    get_registered_flow_config,
)
from backend.app.services.mapping import geo

YMV_WEATHER = {"yellow_mosaic": 0.95, "fungal": 0.39, "chewing_damage": 0.45}
PATCH = {"pattern": "patch", "strength": 0.6, "low_spot_overlap": 0.1, "water_signal": 0.4}


# --- advisory -------------------------------------------------------------

def test_spray_plan_scales_dose_to_zone():
    plan = advisory.spray_plan("yellow_mosaic", zone_acres=1.0)
    assert plan["spray"]["quantity"] == pytest.approx(125 * advisory.HA_PER_ACRE, rel=0.01)
    assert plan["spray"]["unit"] == "ml"


@pytest.mark.parametrize("cause", ["water_stress", "nutrient"])
def test_non_pest_causes_never_get_a_chemical(cause):
    assert advisory.spray_plan(cause, 0.4)["spray"] is None


def test_unknown_cause_raises():
    with pytest.raises(KeyError):
        advisory.spray_plan("alien_blight", 0.4)


def test_savings_counts_only_unsprayed_area():
    s = advisory.savings(field_acres=2.0, zone_acres=0.4, cause="yellow_mosaic")
    assert s["acres_not_sprayed"] == 1.6
    assert s["chemical_saved"] == pytest.approx(125 * 1.6 * advisory.HA_PER_ACRE, rel=0.01)


# --- evidence routing -----------------------------------------------------

def _photo(label, conf=0.86, ok=True):
    return {"label": label, "confidence": conf, "quality": {"ok": ok}}


def test_demo_case_with_agreeing_signals_is_high_and_may_spray():
    e = evidence.build(photo_ai=_photo("yellow_mosaic"), trap_counts=[3, 12], keypad={"whitefly_under_leaves": True},
                       weather_scores=YMV_WEATHER, das=40, advisory_flags={"yellow_mosaic": True}, satellite=PATCH,
                       zone_acres=0.4)
    assert (e["cause"], e["level"], e["action"]) == ("yellow_mosaic", "high", "advise_spray")
    assert e["spray_allowed"] is True
    assert len(e["agreeing_signals"]) >= evidence.MIN_AGREEING


def test_weather_alone_never_reaches_high():
    e = evidence.build(weather_scores=YMV_WEATHER, das=40, advisory_flags={"yellow_mosaic": True})
    assert e["level"] != "high"
    assert e["spray_allowed"] is False


def test_blurry_photo_sends_didi_to_verify_first():
    e = evidence.build(photo_ai=_photo("yellow_mosaic", 0.6, ok=False), keypad={"whitefly_under_leaves": True},
                       weather_scores=YMV_WEATHER, das=40, satellite=PATCH, zone_acres=0.4)
    assert e["action"] == "didi_verify"


def test_patch_in_low_spot_blocks_spray_even_if_pest_wins():
    low = {**PATCH, "low_spot_overlap": 0.8}
    e = evidence.build(photo_ai=_photo("yellow_mosaic", 0.95), trap_counts=[15], keypad={"whitefly_under_leaves": True},
                       weather_scores=YMV_WEATHER, das=40, advisory_flags={"yellow_mosaic": True}, satellite=low,
                       zone_acres=0.4)
    assert e["low_spot_warning"] is True
    assert e["spray_allowed"] is False


def test_uniform_signals_do_not_count_as_agreeing():
    e = evidence.build(photo_ai=_photo("fungal"), das=40, satellite=PATCH, zone_acres=0.4)
    assert "crop_stage" not in e["agreeing_signals"]
    assert "satellite" not in e["agreeing_signals"]


def test_wording_is_never_certain():
    e = evidence.build(photo_ai=_photo("fungal", 0.5), das=40)
    assert e["wording"] == "shak"


# --- IVR result call -------------------------------------------------------

def _ctx(action, spray=None):
    return {"name_hi": "पीला मोज़ेक", "pct": 72, "acres": 0.43, "action": action, "spray": spray}


def test_result_call_speaks_case_cause_zone_and_dose():
    cfg = get_registered_flow_config("result", "result_prompt",
                                     context=_ctx("advise_spray", {"quantity": 52.0, "unit": "ml"}))
    assert "72 प्रतिशत पीला मोज़ेक का शक" in cfg["prompt_text"]
    assert "0.4 एकड़" in cfg["prompt_text"] and "52 ml" in cfg["prompt_text"]
    assert cfg["valid_digits"] == ["1"] and not cfg["hangup"]


def test_result_call_without_pesticide_offers_no_booking():
    cfg = get_registered_flow_config("result", "result_prompt", context=_ctx("advise_no_pesticide"))
    assert cfg["hangup"] and cfg["valid_digits"] == [] and "ड्रोन दीदी" not in cfg["prompt_text"]


def test_result_call_falls_back_to_demo_script_without_a_case():
    assert "86 प्रतिशत" in get_registered_flow_config("result", "result_prompt")["prompt_text"]


# --- links ----------------------------------------------------------------

def test_link_token_round_trip():
    assert communications.read_token(communications.make_token(42)) == 42


@pytest.mark.parametrize("bad", ["", "42", "42.99999999999.deadbeef", "x.y.z"])
def test_forged_tokens_rejected(bad):
    with pytest.raises(communications.LinkTokenError):
        communications.read_token(bad)


def test_expired_token_rejected():
    token = communications.make_token(7, now=0)
    with pytest.raises(communications.LinkTokenError, match="expired"):
        communications.read_token(token)


# --- spray route ------------------------------------------------------------

def test_route_stays_inside_zone_plus_buffer():
    lon, lat, d = 75.1218, 24.1035, 0.0002
    zone = mapping(Polygon([(lon, lat), (lon + d, lat), (lon + d, lat + 2 * d), (lon, lat + 2 * d)]))
    route = missions.plan_route(zone, swath_m=4, buffer_m=1, altitude_m=3)
    allowed = geo.to_m(zone).buffer(1.5)
    assert route["passes"] >= 2
    assert all(allowed.contains(geo.to_m({"type": "Point", "coordinates": wp})) for wp in route["waypoints"])


def test_waypoints_file_turns_sprayer_on_and_off(tmp_path):
    lon, lat, d = 75.1218, 24.1035, 0.0002
    zone = mapping(Polygon([(lon, lat), (lon + d, lat), (lon + d, lat + d), (lon, lat + d)]))
    out = missions.waypoints_file(missions.plan_route(zone, 4, 1, 3), tmp_path / "j.waypoints")
    rows = out.read_text().splitlines()
    assert rows[0] == "QGC WPL 110"
    assert sum(r.split("\t")[3] == "216" for r in rows[1:]) == 2   # DO_SPRAYER on + off
    assert rows[-1].split("\t")[3] == "20"                          # ends with RTL


def test_no_key_redirect_keeps_call_sid_query_intact():
    from backend.app.services.communications.ivr_service import generate_twiml_for_registered_step
    twiml = generate_twiml_for_registered_step("warning", "warning_prompt", None, "http://x/ivr/registered/step?call_sid=CA1")
    assert "call_sid=CA1&amp;timeout=1" in twiml


def test_whitefly_question_repeats_once_then_moves_on_as_dont_know():
    from backend.app.services.communications.registered_state_machine import process_registered_step_input
    first = process_registered_step_input("warning", "whitefly_question", None, reprompt_count=0)
    assert first["next_step"] == "whitefly_question" and first["reprompt"]
    second = process_registered_step_input("warning", "whitefly_question", None, reprompt_count=1)
    assert second["next_step"] == "sms_dispatched" and second["action"] == "record_whitefly_unknown"
