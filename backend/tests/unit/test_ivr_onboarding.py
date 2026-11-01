import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import settings
from backend.app.db.session import Base, SessionLocal, engine, init_db
from backend.app.main import app
from backend.app.models.farmer import Farmer
from backend.app.models.ivr_session import IVRSession
from backend.app.services.communications.onboarding_state_machine import (
    process_step_input,
)


@pytest.fixture(autouse=True)
def setup_database():
    """Ensure clean test database."""
    init_db()
    db = SessionLocal()
    db.query(Farmer).delete()
    db.query(IVRSession).delete()
    db.commit()
    yield
    db.query(Farmer).delete()
    db.query(IVRSession).delete()
    db.commit()
    db.close()


def test_state_machine_happy_path():
    """Test full sequential journey through the onboarding state machine."""
    answers = {}

    # 1. Welcome -> Hindi (1)
    res = process_step_input("welcome", "1", answers)
    assert res["next_step"] == "crop"
    answers = res["updated_answers"]
    assert answers["welcome"] == "hi"

    # 2. Crop -> Soybean (1)
    res = process_step_input("crop", "1", answers)
    assert res["next_step"] == "sowing_date"
    answers = res["updated_answers"]
    assert answers["crop"] == "soybean"

    # 3. Sowing Date -> 30-60 days (3)
    res = process_step_input("sowing_date", "3", answers)
    assert res["next_step"] == "pincode"
    answers = res["updated_answers"]
    assert answers["sowing_date"] == "30_60"

    # 4. PIN Code -> 458001
    res = process_step_input("pincode", "458001", answers)
    assert res["next_step"] == "village"
    answers = res["updated_answers"]
    assert answers["pincode"] == "458001"

    # 5. Village -> 1 (Daloda)
    res = process_step_input("village", "1", answers)
    assert res["next_step"] == "neighbor_crop"
    answers = res["updated_answers"]
    assert "दलोदा" in answers["village"]

    # 6. Neighbor Crop -> Urad/Moong (1)
    res = process_step_input("neighbor_crop", "1", answers)
    assert res["next_step"] == "completed"   # no grassy-border question any more
    answers = res["updated_answers"]
    assert answers["neighbor_crop"] == "urad_moong"


def test_repeat_prompt_digit_9():
    """Pressing 9 should repeat the current step without changing answers."""
    answers = {"welcome": "hi"}
    res = process_step_input("crop", "9", answers)
    assert res["next_step"] == "crop"
    assert res["reprompt"] is True
    assert res["updated_answers"] == answers


def test_reprompt_and_fallback_on_invalid_key():
    """First invalid key reprompts; second invalid key records pata_nahi and advances."""
    answers = {}

    # First invalid attempt (reprompt_count = 0)
    res1 = process_step_input("crop", "7", answers, reprompt_count=0)
    assert res1["next_step"] == "crop"
    assert res1["reprompt"] is True
    assert res1["reprompt_count"] == 1

    # Second invalid attempt (reprompt_count = 1) -> advances with fallback
    res2 = process_step_input("crop", "7", answers, reprompt_count=1)
    assert res2["next_step"] == "sowing_date"
    assert res2["reprompt"] is False
    assert res2["updated_answers"]["crop"] == "pata_nahi"


def test_simulate_step_api_full_journey():
    """Test full onboarding via the /api/v1/ivr/simulate/step endpoint."""
    with TestClient(app) as client:
        phone = "+919876543210"

        # Step 0: Initialize
        r = client.post("/api/v1/ivr/simulate/step", json={"phone": phone, "reset": True})
        assert r.status_code == 200
        data = r.json()
        assert data["current_step"] == "welcome"
        assert not data["is_completed"]

        # Step 1: Welcome -> 1 (Hindi)
        r = client.post("/api/v1/ivr/simulate/step", json={"phone": phone, "digits": "1"})
        assert r.json()["current_step"] == "crop"

        # Step 2: Crop -> 1 (Soybean)
        r = client.post("/api/v1/ivr/simulate/step", json={"phone": phone, "digits": "1"})
        assert r.json()["current_step"] == "sowing_date"

        # Step 3: Sowing -> 3 (30-60 days)
        r = client.post("/api/v1/ivr/simulate/step", json={"phone": phone, "digits": "3"})
        assert r.json()["current_step"] == "pincode"

        # Step 4: PIN code -> 458001
        r = client.post("/api/v1/ivr/simulate/step", json={"phone": phone, "digits": "458001"})
        assert r.json()["current_step"] == "village"

        # Step 5: Village -> 1
        r = client.post("/api/v1/ivr/simulate/step", json={"phone": phone, "digits": "1"})
        assert r.json()["current_step"] == "neighbor_crop"

        # Step 6: Neighbor crop -> 1 (Urad/Moong): the last question
        r = client.post("/api/v1/ivr/simulate/step", json={"phone": phone, "digits": "1"})
        data = r.json()
        assert data["current_step"] == "completed"
        assert data["is_completed"] is True

        # Verify farmer record saved in database
        db = SessionLocal()
        farmer = db.query(Farmer).filter(Farmer.phone == phone).first()
        assert farmer is not None
        assert farmer.status == "registered"
        assert farmer.crop == "soybean"
        assert farmer.sowing_date_bracket == "30_60"
        assert farmer.grassy_border is None   # not asked any more
        db.close()


def test_inbound_call_answered_in_same_call(monkeypatch):
    """IVR_INBOUND_MODE=answer (trial accounts): the inbound call itself runs onboarding, no reject or callback."""
    monkeypatch.setattr(settings, "ivr_inbound_mode", "answer")
    with TestClient(app) as client:
        r = client.post("/api/v1/ivr/webhook", data={"From": "+919876543210", "CallSid": "CA-inbound-1"})
        assert r.status_code == 200
        assert "<Reject" not in r.text
        assert "/ivr/onboarding/start" in r.text

        r = client.post("/api/v1/ivr/onboarding/start?phone=%2B919876543210",
                        data={"From": "+919876543210", "CallSid": "CA-inbound-1"})
        assert "<Gather" in r.text
        assert "call_sid=CA-inbound-1" in r.text

    db = SessionLocal()
    session = db.query(IVRSession).filter(IVRSession.phone == "+919876543210").first()
    assert (session.call_sid, session.flow, session.current_step) == ("CA-inbound-1", "onboarding", "welcome")
    db.close()


def test_twilio_twiml_webhook_flow(monkeypatch):
    """Test inbound webhook for missed-call rejection and callback TwiML generation."""
    monkeypatch.setattr(settings, "ivr_inbound_mode", "callback")
    with TestClient(app) as client:
        # Inbound call -> immediate reject (missed call flow)
        r = client.post(
            "/api/v1/ivr/webhook",
            data={"From": "+919876543210", "CallSid": "test-call-sid-1"},
        )
        assert r.status_code == 200
        assert "<Reject" in r.text

        # Start onboarding callback entry point also responds with welcome
        r = client.post(
            "/api/v1/ivr/onboarding/start",
            data={"From": "+919876543210", "CallSid": "test-call-sid-1"},
        )
        assert r.status_code == 200
        assert "<Gather" in r.text
        assert "फसलनेत्र" in r.text

        # Advance step with digit 1 (Hindi)
        r = client.post(
            "/api/v1/ivr/onboarding/step?call_sid=test-call-sid-1",
            data={"Digits": "1"},
        )
        assert r.status_code == 200
        assert "<Gather" in r.text
        assert "सोयाबीन" in r.text
