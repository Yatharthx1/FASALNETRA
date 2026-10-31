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
    assert f"{round(ev['confidence'] * 100)} प्रतिशत पीला मोज़ेक का शक" in said
    assert f"{walked['zone_acres']:.1f} एकड़" in said and "ICAR-NSRI" in said
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
