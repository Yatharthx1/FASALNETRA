import pytest
from fastapi.testclient import TestClient

from backend.app.db.session import SessionLocal, init_db
from backend.app.main import app
from backend.app.models.farmer import Farmer
from backend.app.models.ivr_session import IVRSession
from backend.app.services.communications.registered_state_machine import (
    process_registered_step_input,
)


@pytest.fixture(autouse=True)
def setup_database():
    """Ensure clean test database with a registered farmer."""
    init_db()
    db = SessionLocal()
    db.query(Farmer).delete()
    db.query(IVRSession).delete()

    # Pre-register a demo farmer
    farmer = Farmer(
        phone="+918839643926",
        name="Ramesh-ji",
        crop="soybean",
        village="कनाड़िया (Kanadia)",
        status="registered",
        active_flow="safe",
        risk_score=20,
    )
    db.add(farmer)
    db.commit()
    yield
    db.query(Farmer).delete()
    db.query(IVRSession).delete()
    db.commit()
    db.close()


def test_registered_farmer_safe_call():
    """A registered farmer in safe state receives reassurance and call hangs up."""
    with TestClient(app) as client:
        phone = "+918839643926"

        r = client.post(f"/api/v1/ivr/registered/start?phone={phone}&flow=safe")
        assert r.status_code == 200
        assert "<Hangup" in r.text
        assert "खतरा नहीं है" in r.text or "surakshit" in r.text or "नमस्ते" in r.text


def test_registered_farmer_p02_warning_call_and_sms():
    """Warning flow plays whitefly alert and key 1 dispatches SMS link."""
    with TestClient(app) as client:
        phone = "+918839643926"

        # 1. Start warning call
        r = client.post(f"/api/v1/ivr/registered/start?phone={phone}&flow=warning")
        assert r.status_code == 200
        assert "<Gather" in r.text
        assert "सफेद मक्खी" in r.text

        # 2. Farmer presses 1 for link
        r = client.post(
            f"/api/v1/ivr/registered/step?call_sid=session-{phone.replace('+', '')}",
            data={"Digits": "1"},
        )
        assert r.status_code == 200
        assert "<Hangup" in r.text
        assert "SMS" in r.text

        # Verify session records SMS dispatch
        db = SessionLocal()
        session = db.query(IVRSession).filter(IVRSession.phone == phone).first()
        assert session.answers.get("sms_sent") is True
        db.close()


def test_registered_farmer_p06_result_and_drone_booking():
    """Result flow plays diagnosis and key 1 confirms Drone Didi booking."""
    with TestClient(app) as client:
        phone = "+918839643926"

        # 1. Start result call
        r = client.post(f"/api/v1/ivr/registered/start?phone={phone}&flow=result")
        assert r.status_code == 200
        assert "<Gather" in r.text
        assert "पीले मोज़ेक" in r.text

        # 2. Farmer presses 1 to confirm Drone Didi booking
        r = client.post(
            f"/api/v1/ivr/registered/step?call_sid=session-{phone.replace('+', '')}",
            data={"Digits": "1"},
        )
        assert r.status_code == 200
        assert "<Hangup" in r.text
        assert "बुकिंग पक्की" in r.text

        # Verify farmer record updated with booking
        db = SessionLocal()
        farmer = db.query(Farmer).filter(Farmer.phone == phone).first()
        assert farmer.spray_booked == "yes"
        db.close()


def test_registered_farmer_state_switching_api():
    """API endpoint to switch farmer state between safe, warning, and result."""
    with TestClient(app) as client:
        phone = "+918839643926"

        # Switch to warning
        r = client.post(f"/api/v1/ivr/farmer/set-state?phone={phone}&active_flow=warning&risk_score=78")
        assert r.status_code == 200
        data = r.json()
        assert data["active_flow"] == "warning"
        assert data["risk_score"] == 78

        # Trigger call respecting active state
        r = client.post(f"/api/v1/ivr/trigger-call?phone={phone}")
        assert r.status_code == 200
        data = r.json()
        assert data["is_registered"] is True
        assert data["flow"] == "warning"
