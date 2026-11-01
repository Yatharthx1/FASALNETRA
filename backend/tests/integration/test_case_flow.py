"""The demo story through the HTTP API: warning call -> keypad -> link -> photos -> walk -> evidence -> Didi."""
import pytest

from backend.tests.conftest import jpeg, needs_data

API = "/api/v1"
pytestmark = [pytest.mark.asyncio, needs_data]


async def _case(client) -> dict:
    r = await client.post(f"{API}/cases", json={"field_id": "demo"})
    assert r.status_code == 201
    return r.json()


async def test_unknown_field_is_404(client):
    assert (await client.get(f"{API}/fields/nowhere")).status_code == 404


async def test_risk_returns_15_days_with_drivers(client):
    r = (await client.get(f"{API}/fields/demo/risk")).json()
    assert len(r["days"]) == 15 and r["days"][0]["date"] == "2025-08-15"
    assert any(d["band"] == "high" for d in r["days"])
    assert r["days"][0]["causes"]["yellow_mosaic"]["drivers"]


async def test_combined_advisory_endpoint(client):
    r = await client.get(f"{API}/fields/demo/combined-advisory")
    assert r.status_code == 200
    data = r.json()
    assert data["field_id"] == "demo"
    assert "score" in data
    assert data["band"] in ("safe", "watch", "high", "critical")
    assert data["primary_cause"] == "yellow_mosaic"
    assert data["components"]["satellite"]["flagged_cells"] > 0
    assert data["components"]["weather"]["vector_dispersal_factor"] > 0
    assert data["action"]["code"] in ("targeted_spray", "trap_scout")


async def test_new_case_gets_flagged_target_cells(client):
    case = await _case(client)
    assert 1 <= len(case["target_cells"]) <= 3
    assert all(not c["visited"] for c in case["target_cells"])


async def test_evidence_needs_a_field_signal(client):
    case = await _case(client)
    assert (await client.post(f"{API}/cases/{case['id']}/evidence")).status_code == 409


async def test_rejects_non_image_upload(client):
    case = await _case(client)
    r = await client.post(f"{API}/cases/{case['id']}/photos", data={"kind": "leaf_top"},
                          files={"file": ("x.jpg", b"not an image", "image/jpeg")})
    assert r.status_code == 422


async def test_full_demo_flow_ends_with_a_zone_only_spray(client):
    case = await _case(client)
    cid = case["id"]

    call = (await client.post(f"{API}/cases/{cid}/warning-call")).json()
    assert call["simulated"] and call["first_prompt"]["current_step"] == "warning_prompt"
    phone = call["first_prompt"]["phone"]
    pressed = (await client.post(f"{API}/ivr/simulate/registered", json={"phone": phone, "digits": "1"})).json()
    assert pressed["current_step"] == "whitefly_question"
    answered = (await client.post(f"{API}/ivr/simulate/registered", json={"phone": phone, "digits": "1"})).json()
    assert answered["current_step"] == "sms_dispatched"
    assert (await client.get(f"{API}/cases/{cid}")).json()["keypad"] == {"whitefly_under_leaves": True}
    await client.post(f"{API}/cases/{cid}/traps", json={"counts": [3, 12, 5, 2]})

    for i, cell in enumerate(case["target_cells"]):
        lon, lat = cell["centre"]
        r = await client.post(f"{API}/cases/{cid}/photos",
                              data={"kind": "leaf_top", "spot": i, "cell_id": cell["id"], "lon": lon, "lat": lat},
                              files={"file": ("leaf.jpg", jpeg(), "image/jpeg")})
        assert r.status_code == 201

    trail = (await client.get(f"{API}/fields/demo/demo-walk")).json()
    walked = (await client.post(f"{API}/cases/{cid}/walk", json={"trail": trail})).json()
    assert 0.1 < walked["zone_acres"] < 1.0
    assert all(c["visited"] for c in walked["target_cells"])

    ev = (await client.post(f"{API}/cases/{cid}/evidence")).json()["evidence"]
    assert ev["level"] == "high" and ev["action"] == "advise_spray"

    said = (await client.post(f"{API}/cases/{cid}/result-call")).json()["first_prompt"]["prompt_text"]
    assert "पीला मोज़ेक का शक" in said and "समस्या का स्तर" in said
    assert "एकड़" not in said and "प्रतिशत" not in said and "नमो ड्रोन दीदी" in said   # farmer hears no numbers
    jobs_for_case = lambda js: [j for j in js if j["case_id"] == cid]  # noqa: E731
    assert not jobs_for_case((await client.get(f"{API}/didi/jobs")).json())   # not booked before the key press
    await client.post(f"{API}/ivr/simulate/registered", json={"phone": phone, "digits": "1"})

    job = jobs_for_case((await client.get(f"{API}/didi/jobs")).json())[0]
    assert job["mode"] == "spray" and job["route"]["passes"] >= 1
    assert (await client.post(f"{API}/didi/jobs/{job['id']}", json={"action": "start"})).status_code == 409
    for action in ("accept", "start", "complete"):
        assert (await client.post(f"{API}/didi/jobs/{job['id']}", json={"action": action})).status_code == 200
    assert (await client.get(f"{API}/didi/jobs/{job['id']}/waypoints")).text.startswith("QGC WPL 110")

    types = [e["type"] for e in (await client.get(f"{API}/events", params={"case_id": cid})).json()]
    for expected in ("call_placed", "sms_sent", "photo_received", "zone_mapped", "evidence_ready",
                     "neighbours_warned", "didi_booked", "didi_complete"):
        assert expected in types


async def test_link_token_opens_only_its_case(client):
    case = await _case(client)
    url = (await client.post(f"{API}/cases/{case['id']}/link")).json()["url"]
    token = url.split("t=")[1]
    assert (await client.get(f"{API}/cases/by-token", params={"t": token})).json()["id"] == case["id"]
    assert (await client.get(f"{API}/cases/by-token", params={"t": token[:-1] + ("1" if token[-1] == "0" else "0")})).status_code == 403


async def test_farmer_missed_call_reports_a_problem_and_gets_the_photo_link(client):
    # Missed call -> free callback (3 s); the pre-registered demo farmer is asked to report a problem, not onboarded
    phone = (await client.post(f"{API}/fields/demo/missed-call")).json()["phone"]
    session = (await client.get(f"{API}/ivr/session/{phone}")).json()["session"]
    assert session["flow"] == "report"

    menu = (await client.post(f"{API}/ivr/simulate/registered", json={"phone": phone})).json()
    assert menu["current_step"] == "report_prompt" and menu["valid_digits"] == ["1", "2", "3", "4"]
    asked = (await client.post(f"{API}/ivr/simulate/registered", json={"phone": phone, "digits": "1"})).json()
    assert asked["current_step"] == "whitefly_question"
    await client.post(f"{API}/ivr/simulate/registered", json={"phone": phone, "digits": "1"})

    events = (await client.get(f"{API}/events")).json()
    cid = next(e["case_id"] for e in reversed(events) if e["type"] == "farmer_reported")
    case = (await client.get(f"{API}/cases/{cid}")).json()
    assert case["keypad"] == {"yellow_mosaic_patches": True, "whitefly_under_leaves": True}
    assert any(e["type"] == "sms_sent" and e["case_id"] == cid for e in events)


async def test_unsure_result_calls_the_farmer_to_offer_drone_didi(client):
    case = await _case(client)
    cid = case["id"]
    await client.post(f"{API}/cases/{cid}/traps", json={"counts": [3, 12, 5, 2]})
    ev = (await client.post(f"{API}/cases/{cid}/evidence")).json()["evidence"]
    assert ev["level"] != "high" and ev["action"] == "didi_verify"

    calls = [e for e in (await client.get(f"{API}/events", params={"case_id": cid})).json() if e["type"] == "call_placed"]
    assert calls and calls[-1]["payload"]["kind"] == "result"
    prompt = (await client.post(f"{API}/ivr/simulate/registered", json={"phone": "+919876543210"})).json()
    assert "प्रतिशत" not in prompt["prompt_text"] and "ड्रोन दीदी" in prompt["prompt_text"]
    await client.post(f"{API}/ivr/simulate/registered", json={"phone": "+919876543210", "digits": "1"})
    job = [j for j in (await client.get(f"{API}/didi/jobs")).json() if j["case_id"] == cid][0]
    assert job["mode"] == "verify_then_spray" and job["status"] == "new"


async def test_event_polling_returns_only_newer_events_and_survives_a_reset(client):
    await _case(client)
    last = (await client.get(f"{API}/events", params={"limit": 1})).json()[0]["id"]
    assert (await client.get(f"{API}/events", params={"after": last})).json() == []
    await _case(client)
    fresh = (await client.get(f"{API}/events", params={"after": last})).json()
    assert [e["type"] for e in fresh] == ["case_created"]

    await client.post(f"{API}/demo/reset")   # SQLite may restart ids below `last`
    after_reset = (await client.get(f"{API}/events", params={"after": fresh[-1]["id"]})).json()
    assert "demo_reset" in [e["type"] for e in after_reset]


async def test_camera_link_is_the_walk_link_and_sends_nothing(client):
    case = await _case(client)
    r = (await client.get(f"{API}/cases/{case['id']}/camera-link")).json()
    assert r["case_id"] == case["id"] and "/walk?t=" in r["url"]
    events = (await client.get(f"{API}/events")).json()
    assert not any(e["type"] == "sms_sent" and e["case_id"] == case["id"] for e in events)
    assert (await client.get(f"{API}/cases/by-token", params={"t": r["url"].split("t=")[1]})).json()["id"] == case["id"]


async def test_every_call_gets_a_fresh_camera_session_and_retires_the_old_link(client):
    async def report_call() -> tuple[int, str]:
        phone = (await client.post(f"{API}/fields/demo/missed-call")).json()["phone"]
        await client.post(f"{API}/ivr/simulate/registered", json={"phone": phone})
        await client.post(f"{API}/ivr/simulate/registered", json={"phone": phone, "digits": "1"})
        events = (await client.get(f"{API}/events")).json()
        sent = next(e for e in reversed(events) if e["type"] == "sms_sent")
        return sent["case_id"], sent["payload"]["url"].split("t=")[1]

    first_id, first_token = await report_call()
    second_id, second_token = await report_call()   # first case still waiting for photos: not reused
    assert second_id != first_id and second_token != first_token
    assert (await client.get(f"{API}/cases/by-token", params={"t": first_token})).status_code == 410
    assert (await client.get(f"{API}/cases/by-token", params={"t": second_token})).json()["id"] == second_id
