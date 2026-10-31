"""Drone Didi console API: profile, seeded tickets, ticket details, and a farmer booking from the result page."""
import pytest

from backend.tests.conftest import jpeg, needs_data

API = "/api/v1"
pytestmark = [pytest.mark.asyncio, needs_data]


async def test_queue_has_seeded_tickets_with_everything_the_detail_needs(client):
    jobs = (await client.get(f"{API}/didi/jobs")).json()
    assert len(jobs) >= 2
    for j in jobs:
        tk = j["ticket"]
        assert tk["farmer"] and tk["khasra"] and tk["field"]["type"] == "Polygon" and tk["distance_km"] >= 0
        assert j["schedule"][0]["kind"] in ("spray", "verify_then_spray")
        assert {"pesticide", "water_l", "fuel_l", "battery"} <= set(j["savings"])
        assert j["route"]["waypoints"]


async def test_profile_counts_open_and_done_jobs(client):
    p = (await client.get(f"{API}/didi/profile")).json()
    assert p["name"] and p["jobs_open"] >= 2 and p["jobs_done"] == 0


async def test_reset_keeps_the_seeded_tickets(client):
    await client.post(f"{API}/demo/reset")
    assert len((await client.get(f"{API}/didi/jobs")).json()) >= 2


async def test_farmer_says_yes_on_low_confidence_and_didi_gets_a_verify_ticket(client):
    case = (await client.post(f"{API}/cases", json={"field_id": "demo"})).json()
    cell = case["target_cells"][0]
    await client.post(f"{API}/cases/{case['id']}/photos",
                      data={"kind": "leaf_top", "cell_id": cell["id"], "lon": cell["centre"][0], "lat": cell["centre"][1]},
                      files={"file": ("leaf.jpg", jpeg(), "image/jpeg")})
    ev = (await client.post(f"{API}/cases/{case['id']}/evidence")).json()["evidence"]
    assert ev["level"] != "high"                     # one photo alone never reaches High
    job = (await client.post(f"{API}/cases/{case['id']}/book-didi")).json()
    assert job["mode"] == "verify_then_spray"
    assert job["ticket"] == {} or job["case_id"] == case["id"]
    queue = (await client.get(f"{API}/didi/jobs")).json()
    assert any(j["case_id"] == case["id"] and j["ticket"]["farmer"] for j in queue)
