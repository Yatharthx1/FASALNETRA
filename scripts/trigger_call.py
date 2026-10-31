"""CLI utility to trigger an outbound onboarding or advisory call directly from the terminal.

Usage:
    py scripts/trigger_call.py +918839643926
    py scripts/trigger_call.py          # Uses DEMO_FARMER_PHONE from .env
"""

import sys
import httpx
from twilio.rest import Client
from backend.app.core.config import settings


def trigger_call(target_phone: str | None = None) -> None:
    phone = (target_phone or settings.demo_farmer_phone).strip()
    if not phone.startswith("+"):
        phone = f"+{phone}"

    print(f"\n=======================================================")
    print(f"  FasalNetra - Triggering Outbound Call")
    print(f"  Destination Phone : {phone}")
    print(f"  Caller ID (Twilio): {settings.twilio_phone_number}")
    print(f"  Public Tunnel URL : {settings.public_base_url}")
    print(f"=======================================================\n")

    # 1. First try via local FastAPI endpoint if running
    api_url = f"http://127.0.0.1:8000/api/v1/ivr/trigger-call?phone={phone}"
    try:
        r = httpx.post(api_url, timeout=5.0)
        if r.status_code == 200:
            data = r.json()
            print(f"[SUCCESS] FastAPI accepted the call request!")
            print(f"Call SID: {data.get('call_sid')}")
            print(f"Status  : {data.get('status')}")
            print(f"\nYour phone ({phone}) will ring in 2-5 seconds.")
            return
    except Exception:
        print("[INFO] Local FastAPI endpoint not reachable or offline; initiating directly via Twilio SDK...")

    # 2. Fallback directly via Twilio SDK
    try:
        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        callback_url = f"{settings.public_base_url}{settings.api_v1_prefix}/ivr/onboarding/start?phone={phone}"
        call = client.calls.create(
            to=phone,
            from_=settings.twilio_phone_number,
            url=callback_url,
        )
        print(f"[SUCCESS] Twilio call created directly!")
        print(f"Call SID: {call.sid}")
        print(f"\nYour phone ({phone}) will ring in 2-5 seconds.")
    except Exception as e:
        print(f"[ERROR] Failed to place Twilio call: {e}")
        print("\nTroubleshooting tips:")
        print("1. Ensure your public tunnel is running (e.g. npx localtunnel --port 8000).")
        print("2. Verify that the destination phone number is added under Twilio 'Verified Caller IDs'.")
        print("3. Verify India (+91) is enabled in Twilio Voice Geo-Permissions.")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    trigger_call(target)
