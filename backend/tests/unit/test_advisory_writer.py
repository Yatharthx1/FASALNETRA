"""Crop advisory: routing by confidence and crop, the LLM guardrails, the template fallback."""
from datetime import date
from types import SimpleNamespace

import pytest

from backend.app.services import cases
from backend.app.services.advisory import knowledge, writer
from backend.app.services.communications.registered_state_machine import (
    get_registered_flow_config,
)

SPRAY = {"product": "Thiamethoxam 12.6% + Lambda-cyhalothrin 9.5% ZC", "quantity": 37.9, "unit": "ml", "water_l": 7.6,
         "repeat_after_days": 15}


def _ev(level="high", action="advise_spray", spray=SPRAY, cause="yellow_mosaic"):
    return {"cause": cause, "name_hi": "x", "confidence": 0.79 if level == "high" else 0.6, "level": level,
            "action": action, "agreeing_signals": ["photo_ai", "traps", "keypad"],
            "plan": {"source": "ICAR-NSRI, Kharif 2025", "spray": spray}}


@pytest.fixture
def facts():
    return knowledge.build_facts(crop="soybean", evidence=_ev(), das=40, zone_acres=0.75, field_acres=1.6,
                                 spray_window={"best": "2025-08-16T06:00"})


GOOD = {"say_hi": "आपकी सोयाबीन में पीले मोज़ेक का शक है। सिर्फ बीमार हिस्से में {PRODUCT} छिड़किए।",
        "advisory_hi": "लगभग {ZONE_ACRES} एकड़ में पीले मोज़ेक का शक है। {PRODUCT} {QUANTITY} {UNIT} को {WATER_L} लीटर "
                       "पानी में मिलाकर {WINDOW} बजे छिड़किए।",
        "advisory_en": "Suspected yellow mosaic on {ZONE_ACRES} acres. Spray {QUANTITY} {UNIT} in {WATER_L} L.",
        "model": "fake"}


def test_llm_text_gets_the_dose_from_the_table(facts):
    out = writer.write(facts, ask=lambda f: GOOD)
    assert out["source"] == "llm"
    assert "37.9 ml" in out["advisory_hi"] and "7.6 लीटर" in out["advisory_hi"] and "06:00" in out["advisory_hi"]
    assert "Thiamethoxam" in out["say_hi"]


@pytest.mark.parametrize("bad,why", [
    ({**GOOD, "advisory_hi": "पीले मोज़ेक का शक है। 250 ml दवा पूरे खेत में डालिए।"}, "invented dose"),
    ({**GOOD, "advisory_hi": "पीला मोज़ेक है। {PRODUCT} छिड़किए।"}, "certain diagnosis, no शक"),
    ({**GOOD, "advisory_hi": "शक है। {DOSAGE} डालिए।"}, "unknown placeholder"),
    ({**GOOD, "say_hi": ""}, "empty"),
])
def test_a_rule_breaking_llm_answer_falls_back_to_the_template(facts, bad, why):
    out = writer.write(facts, ask=lambda f: bad)
    assert out["source"] == "template" and "rejected" in out["note"], why
    assert "250" not in out["advisory_hi"]


def test_llm_failure_still_gives_the_farmer_an_advisory(facts):
    def boom(f):
        raise TimeoutError("network")
    out = writer.write(facts, ask=boom)
    assert out["source"] == "template" and out["note"] == "LLM unavailable"


def test_template_obeys_the_same_rules(facts):
    t = writer.template(facts)
    assert writer.check(t, facts)
    assert "शक" in t["advisory_hi"] and "पूरे खेत में छिड़काव मत कीजिए" in t["advisory_hi"]


def test_non_pest_cause_gets_no_spray(facts):
    f = knowledge.build_facts(crop="soybean", evidence=_ev(action="advise_no_pesticide", spray=None, cause="nutrient"),
                              das=40, zone_acres=0.5, field_acres=1.6)
    t = writer.template(f)
    assert "कीटनाशक की ज़रूरत नहीं" in t["advisory_hi"] and f["spray"] is None


def test_numbers_allowed_are_only_those_in_the_facts(facts):
    assert {"37.9", "7.6", "0.75", "40", "79"} <= set(facts["allowed_numbers"])
    assert "250" not in facts["allowed_numbers"]


def _field(crop):
    return SimpleNamespace(crop=crop, area_acres=1.6, farmer=SimpleNamespace(phone="+910000000000"),
                           sowing_date=date(2025, 7, 6))


def test_high_confidence_soybean_goes_to_the_advisory(monkeypatch):
    monkeypatch.setattr(cases.fields, "spray_window", lambda f: {"best": "2025-08-16T06:00"})
    monkeypatch.setattr(cases, "field_profile", lambda phone: None)
    ev = _ev()
    cases._route(ev, _field("soybean"), 40, 0.75)
    assert ev["route"] == "advisory" and ev["advisory"]["say_hi"]


def test_not_high_confidence_goes_to_drone_didi():
    ev = _ev(level="medium", action="didi_verify")
    cases._route(ev, _field("soybean"), 40, 0.75)
    assert ev["route"] == "drone_didi" and "advisory" not in ev


def test_crop_without_a_knowledge_pack_never_gets_an_automatic_dose():
    ev = _ev()                                   # high confidence, but the doses are soybean doses
    cases._route(ev, _field("maize"), 40, 0.75)
    assert ev["action"] == "didi_verify" and ev["spray_allowed"] is False and ev["route"] == "drone_didi"


def test_ivr_result_call_speaks_the_advisory():
    ctx = {"name_hi": "पीला मोज़ेक", "pct": 79, "acres": 0.75, "action": "advise_spray",
           "spray": {"quantity": 37.9, "unit": "ml"}, "say_hi": "सिर्फ बीमार हिस्से में दवा छिड़किए।"}
    text = get_registered_flow_config("result", "result_prompt", None, ctx)["prompt_text"]
    assert "सिर्फ बीमार हिस्से में दवा छिड़किए।" in text and "1 दबाइए" in text
