"""Twilio webhook renders the same voice script as TwiML: Hindi Say inside a 1-digit Gather, silence handled."""
import pytest

from backend.tests.conftest import needs_data

API = "/api/v1"
pytestmark = [pytest.mark.asyncio, needs_data]


async def _case(client) -> int:
    return (await client.post(f"{API}/cases", json={"field_id": "demo"})).json()["id"]


async def test_warning_prompt_is_a_hindi_gather(client):
    cid = await _case(client)
    r = await client.post(f"{API}/ivr/voice", params={"case_id": cid, "step": "warning"})
    assert r.headers["content-type"].startswith("application/xml")
    assert '<Gather action="/api/v1/ivr/voice?case_id=' in r.text and 'numDigits="1"' in r.text
    assert 'language="hi-IN"' in r.text and "peela mosaic" in r.text


async def test_key_press_from_twilio_moves_to_questions(client):
    cid = await _case(client)
    r = await client.post(f"{API}/ivr/voice", params={"case_id": cid, "step": "warning"}, data={"Digits": "1"})
    assert "safed makkhiyan" in r.text


async def test_second_silence_ends_the_call_politely(client):
    cid = await _case(client)
    first = await client.post(f"{API}/ivr/voice", params={"case_id": cid, "step": "q0", "digit": "9", "retry": 1})
    assert "step=q0_again" in first.text
    second = await client.post(f"{API}/ivr/voice", params={"case_id": cid, "step": "q0_again", "digit": "9", "retry": 1})
    assert "<Hangup" in second.text and "do ghante" in second.text


async def test_unknown_case_is_404(client):
    r = await client.post(f"{API}/ivr/voice", params={"case_id": 999, "step": "warning"})
    assert r.status_code == 404
