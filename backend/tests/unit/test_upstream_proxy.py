"""API_UPSTREAM: the hosted portal forwards /api and /uploads to the laptop's backend and serves only the pages."""
import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app import main
from backend.app.core.config import settings


@pytest.fixture
def proxied(monkeypatch):
    seen: list[httpx.Request] = []

    def laptop(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(201, json={"from": "laptop", "path": request.url.path, "q": request.url.query.decode()})

    monkeypatch.setattr(settings, "api_upstream", "https://laptop.example")
    monkeypatch.setattr(main, "_upstream", httpx.AsyncClient(base_url="https://laptop.example",
                                                             transport=httpx.MockTransport(laptop)))
    with TestClient(main.create_app()) as client:
        yield client, seen


def test_api_calls_go_to_the_laptop_with_the_tunnel_bypass_header(proxied):
    client, seen = proxied
    r = client.post("/api/v1/didi/jobs/3/accept?x=1", json={"note": "ok"})
    assert r.status_code == 201 and r.json() == {"from": "laptop", "path": "/api/v1/didi/jobs/3/accept", "q": "x=1"}
    assert seen[0].method == "POST" and seen[0].content == b'{"note":"ok"}'
    assert seen[0].headers["bypass-tunnel-reminder"] == "1"


def test_pages_are_still_served_here(proxied):
    client, seen = proxied
    client.get("/didi")
    assert not seen


def test_laptop_down_is_a_clear_502(monkeypatch):
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(settings, "api_upstream", "https://laptop.example")
    monkeypatch.setattr(main, "_upstream", httpx.AsyncClient(base_url="https://laptop.example",
                                                             transport=httpx.MockTransport(down)))
    with TestClient(main.create_app()) as client:
        r = client.get("/api/v1/didi/jobs")
    assert r.status_code == 502 and "not reachable" in r.json()["detail"]
