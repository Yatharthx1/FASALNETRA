"""Phone GPS on the walk page: the batched 5 Hz track, and which parcel the farmer is standing in."""
import pytest
from shapely.geometry import shape

from backend.tests.conftest import needs_data

API = "/api/v1"
pytestmark = [pytest.mark.asyncio, needs_data]


async def _case(client) -> tuple[dict, list[float]]:
    case = (await client.post(f"{API}/cases", json={"field_id": "demo"})).json()
    field = (await client.get(f"{API}/fields/demo")).json()
    c = shape(field["geometry"]).representative_point()
    return case, [c.x, c.y]


async def test_track_batches_are_stored(client):
    case, (lon, lat) = await _case(client)
    pts = [{"t": 1_793_560_000_000 + 200 * i, "lat": lat, "lon": lon, "accuracy": 4.0, "heading": 90.0,
            "speed": 1.2, "source": "steps" if i % 5 else "gps"} for i in range(25)]   # 5 s at 5 Hz
    r = (await client.post(f"{API}/cases/{case['id']}/track", json={"points": pts})).json()
    assert r == {"stored": 25, "total": 25}
    r = (await client.post(f"{API}/cases/{case['id']}/track", json={"points": pts[:5]})).json()
    assert r["total"] == 30


async def test_track_rejects_bad_points(client):
    case, _ = await _case(client)
    bad = {"points": [{"t": 1, "lat": 123.0, "lon": 75.1, "accuracy": 5}]}
    assert (await client.post(f"{API}/cases/{case['id']}/track", json=bad)).status_code == 422
    assert (await client.post(f"{API}/cases/{case['id']}/track", json={"points": []})).status_code == 422


async def test_phone_in_the_field_is_on_field_and_parcel_matches(client):
    case, (lon, lat) = await _case(client)
    r = (await client.post(f"{API}/cases/{case['id']}/locate", json={"lat": lat, "lon": lon, "accuracy": 5})).json()
    assert r["status"] == "on_field" and r["distance_m"] == 0
    assert r["parcel"]["khasra"] and r["parcel_is_mapped_field"] is True
    assert "owner" not in r["parcel"]                     # never tell a phone who owns which field


async def test_phone_far_away_is_flagged_once(client):
    case, (lon, lat) = await _case(client)
    far = {"lat": lat + 0.02, "lon": lon, "accuracy": 8}  # ~2 km north
    r = (await client.post(f"{API}/cases/{case['id']}/locate", json=far)).json()
    assert r["status"] == "away" and r["distance_m"] > 1500
    await client.post(f"{API}/cases/{case['id']}/locate", json=far)
    events = [e for e in (await client.get(f"{API}/events?case_id={case['id']}")).json() if e["type"] == "farmer_located"]
    assert len(events) == 1                               # logged when the status changes, not every call
