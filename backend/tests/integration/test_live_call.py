"""Phone-only farmer: IVR onboarding -> field + Sentinel-2 walk targets + SMS link -> live hold while the
camera page sends photos -> result spoken in the same call -> key 1 books Drone Didi."""
import pytest

from backend.tests.conftest import jpeg, needs_data

API = "/api/v1"
PHONE = "+919000000001"
ONBOARD = ["1", "1", "3", "458001", "1", "1", "1"]   # Hindi, soybean, 30-60 days, PIN, village, urad/moong, grassy
pytestmark = [pytest.mark.asyncio, needs_data]


async def _onboard(client) -> dict:
    await client.post(f"{API}/ivr/simulate/step", json={"phone": PHONE, "reset": True})
    for d in ONBOARD:
        r = (await client.post(f"{API}/ivr/simulate/step", json={"phone": PHONE, "digits": d})).json()
    return r


async def _poll(client) -> dict:
    return (await client.post(f"{API}/ivr/simulate/registered", json={"phone": PHONE})).json()


async def _events(client, kind: str) -> list[dict]:
    return [e for e in (await client.get(f"{API}/events?limit=200")).json() if e["type"] == kind]


async def test_onboarding_maps_the_field_and_sends_the_camera_link(client):
    done = await _onboard(client)
    assert done["is_completed"] and "SMS link sent" in done["message"]

    sms = await _events(client, "sms_sent")
    assert sms and "/walk?t=" in sms[0]["payload"]["url"]
    case = (await client.get(f"{API}/cases/by-token?t={sms[0]['payload']['url'].split('t=')[1]}")).json()
    assert case["field_id"] == f"ivr-{PHONE[-10:]}"
    assert case["target_cells"] and all("reason" in c for c in case["target_cells"])

    hold = await _poll(client)   # the same call continues as the live hold
    assert hold["current_step"] == "sms_dispatched" and not hold["is_completed"]


async def test_live_call_speaks_photos_then_the_result_and_books_didi(client):
    await _onboard(client)
    url = (await _events(client, "sms_sent"))[0]["payload"]["url"]
    case = (await client.get(f"{API}/cases/by-token?t={url.split('t=')[1]}")).json()
    cid = case["id"]

    await client.post(f"{API}/cases/{cid}/opened")
    assert "लिंक खुल गया" in (await _poll(client))["prompt_text"]

    cell = case["target_cells"][0]
    await client.post(f"{API}/cases/{cid}/photos",
                      data={"kind": "leaf_top", "spot": 0, "cell_id": cell["id"], "lon": cell["centre"][0],
                            "lat": cell["centre"][1]},
                      files={"file": ("leaf.jpg", jpeg(), "image/jpeg")})
    said = (await _poll(client))["prompt_text"]
    assert "फोटो मिल गई" in said and "शक" in said
    assert (await _poll(client))["prompt_text"] == ""     # nothing new: stay quiet, keep holding

    ev = (await client.post(f"{API}/cases/{cid}/evidence")).json()["evidence"]
    assert not await _events(client, "call_placed")       # farmer is on the line: no second call
    assert any(s["name"] == "field_profile" for s in ev["signals"])

    result = await _poll(client)
    assert result["flow"] == "result" and result["current_step"] == "result_prompt"
    assert result["valid_digits"] == ["1", "2", "3"] and "समस्या का स्तर" in result["prompt_text"]
    booked = (await client.post(f"{API}/ivr/simulate/registered", json={"phone": PHONE, "digits": "1"})).json()
    assert booked["current_step"] == "booking_confirmed"
    assert await _events(client, "didi_booked") or await _events(client, "booking_skipped")


async def test_without_a_live_call_the_result_goes_out_as_a_callback(client):
    case = (await client.post(f"{API}/cases", json={"field_id": "demo"})).json()
    await client.post(f"{API}/cases/{case['id']}/keypad", json={"answers": {"whitefly_under_leaves": True}})
    await client.post(f"{API}/cases/{case['id']}/evidence")
    calls = await _events(client, "call_placed")
    assert calls and calls[0]["payload"]["kind"] == "result"


async def test_failed_sms_keeps_the_call_alive_and_logs_the_link(client, monkeypatch):
    from backend.app.services import communications
    monkeypatch.setattr(communications, "send_sms",
                        lambda to, body: communications.SendResult(simulated=False, sid=None, error="trial template"))
    await _onboard(client)
    failed = await _events(client, "sms_failed")
    assert failed and "/walk?t=" in failed[0]["payload"]["url"]
    assert (await _poll(client))["current_step"] == "sms_dispatched"


async def test_key_2_speaks_the_table_dose_then_key_3_ends_the_call(client):
    await _onboard(client)
    url = (await _events(client, "sms_sent"))[0]["payload"]["url"]
    case = (await client.get(f"{API}/cases/by-token?t={url.split('t=')[1]}")).json()
    cell = case["target_cells"][0]
    await client.post(f"{API}/cases/{case['id']}/photos",
                      data={"kind": "leaf_top", "spot": 0, "cell_id": cell["id"], "lon": cell["centre"][0],
                            "lat": cell["centre"][1]},
                      files={"file": ("leaf.jpg", jpeg(), "image/jpeg")})
    await client.post(f"{API}/cases/{case['id']}/evidence")
    assert (await _poll(client))["current_step"] == "result_prompt"

    advice = (await client.post(f"{API}/ivr/simulate/registered", json={"phone": PHONE, "digits": "2"})).json()
    assert advice["current_step"] == "self_advice" and "Thiamethoxam" in advice["prompt_text"]
    assert "प्रति एकड़" in advice["prompt_text"] and advice["valid_digits"] == ["1", "3"]
    bye = (await client.post(f"{API}/ivr/simulate/registered", json={"phone": PHONE, "digits": "3"})).json()
    assert bye["current_step"] == "goodbye" and bye["is_completed"]
    assert not await _events(client, "didi_booked")
