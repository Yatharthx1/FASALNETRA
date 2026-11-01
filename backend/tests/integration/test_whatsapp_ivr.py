"""WhatsApp IVR (waAPI): call -> onboarding by chat replies -> camera link in the chat -> photo -> result and the
1/2/3 menu in the chat -> 1 books Drone Didi, who also gets a WhatsApp."""
import asyncio

import pytest

from backend.tests.conftest import jpeg, needs_data

API = "/api/v1"
PHONE = "+919000000042"
CHAT = "919000000042@c.us"
DIDI = "+919000000099"
pytestmark = [pytest.mark.asyncio, needs_data]


@pytest.fixture
async def chat(monkeypatch):
    from backend.app.api.v1.routes import whatsapp
    from backend.app.core.config import settings
    from backend.app.services.communications import tts, waapi

    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(waapi, "send_text", lambda phone, text: sent.append((phone, text)) or "id")
    monkeypatch.setattr(waapi, "send_voice", lambda phone, ogg: sent.append((phone, "<voice>")) or "id")
    monkeypatch.setattr(tts, "speech", lambda text, fmt="opus": None)
    monkeypatch.setattr(whatsapp, "LIVE_TICK_S", 0.5)
    for k, v in {"waapi_instance_id": "7", "waapi_token": "t", "sms_provider": "waapi", "didi_phone": DIDI}.items():
        monkeypatch.setattr(settings, k, v)
    yield sent
    for task in whatsapp._live.values():   # a live hold must not outlive its test database
        task.cancel()
    whatsapp._live.clear()
    whatsapp._call_started.clear()


async def _hook(client, event: str, data: dict) -> None:
    from backend.app.services.communications import waapi

    r = await client.post(f"{API}/wa/webhook/{waapi.webhook_secret()}", json={"event": event, "instanceId": "7", "data": data})
    assert r.status_code == 200


async def _reply(client, chat, body: str, n: int = [0]) -> str:
    """Send one chat message and wait for FasalNetra's answer (the conversation runs in background tasks)."""
    n[0] += 1
    before = len(chat)
    await _hook(client, "message", {"message": {"id": {"_serialized": f"m{n[0]}"}, "from": CHAT, "fromMe": False,
                                                "type": "chat", "body": body, "timestamp": n[0]}})
    return await _wait(chat, before)


async def _wait(chat, before: int, timeout: float = 20) -> str:
    for _ in range(int(timeout / 0.05)):
        await asyncio.sleep(0.05)
        new = [t for p, t in chat[before:] if p == PHONE]
        if new:
            await asyncio.sleep(0.2)   # let the rest of this turn's messages land
            return " ".join(t for p, t in chat[before:] if p == PHONE)
    raise AssertionError("no WhatsApp reply")


async def test_whatsapp_call_runs_the_whole_ivr_in_the_chat(client, chat):
    await client.post(f"{API}/demo/reset")
    before = len(chat)
    await _hook(client, "call", {"call": {"from": CHAT, "fromMe": False}})
    assert "हिंदी के लिए 1" in await _wait(chat, before)
    await _hook(client, "call", {"call": {"from": CHAT, "fromMe": False}})      # same call, another event: ignored

    assert "भेजिए" in (await _reply(client, chat, "1"))                          # chat wording, not "press"
    for answer in ["1", "3", "458001", "1", "1"]:
        await _reply(client, chat, answer)
    done = await _reply(client, chat, "1")
    assert "/walk?t=" in done and "यह चैट खुली रखिए" in done                     # link + hold, same chat

    url = next(t for p, t in chat if "/walk?t=" in t).split("/walk?t=")[1].split()[0]
    case = (await client.get(f"{API}/cases/by-token?t={url}")).json()
    cell = case["target_cells"][0]
    before = len(chat)
    await client.post(f"{API}/cases/{case['id']}/photos", files={"file": ("leaf.jpg", jpeg(), "image/jpeg")},
                      data={"kind": "leaf_top", "cell_id": cell["id"], "lon": cell["centre"][0], "lat": cell["centre"][1]})
    assert "फोटो" in await _wait(chat, before)                                    # live update while holding
    before = len(chat)
    await client.post(f"{API}/cases/{case['id']}/evidence")
    result = await _wait(chat, before)
    assert "समस्या का स्तर" in result and "बातचीत खत्म करने के लिए 3" in result

    advice = await _reply(client, chat, "2")
    assert "प्रति एकड़" in advice
    before = len(chat)
    await _reply(client, chat, "1")
    jobs = (await client.get(f"{API}/didi/jobs")).json()
    assert len(jobs) == 1 and jobs[0]["status"] == "new"
    assert any(p == DIDI and "/didi" in t for p, t in chat[before:])            # Didi's own WhatsApp alert


async def test_webhook_rejects_a_wrong_secret_and_ignores_own_messages(client, chat):
    assert (await client.post(f"{API}/wa/webhook/nope", json={})).status_code == 404
    from backend.app.services.communications import waapi

    await client.post(f"{API}/wa/webhook/{waapi.webhook_secret()}", json={"event": "message", "instanceId": "7", "data": {
        "message": {"id": {"_serialized": "own"}, "from": CHAT, "fromMe": True, "type": "chat", "body": "1"}}})
    await asyncio.sleep(0.3)
    assert chat == []
