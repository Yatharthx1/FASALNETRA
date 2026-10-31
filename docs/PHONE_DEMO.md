# Phone demo (real Twilio calls + SMS link on the farmer's phone)

## Live deployment (AWS)

- Server: EC2 `fasalnetra-api` (`i-087d8d71e4ae857fe`, t3.micro, ap-south-1), fixed IP 13.205.168.88
- URL: https://13-205-168-88.sslip.io (Caddy, automatic HTTPS): `/` dashboard, `/walk` farmer, `/didi` Didi, `/call` console
- Twilio number: "A call comes in" = `POST https://13-205-168-88.sslip.io/api/v1/ivr/webhook`,
  "Call status changes" = `POST https://13-205-168-88.sslip.io/api/v1/ivr/status`
- Secrets: AWS Console > Systems Manager > Session Manager > start a session on `fasalnetra-api`, then
  `sudo nano /opt/fasalnetra/.env.server` (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER,
  DEMO_FARMER_PHONE, VISION_PROVIDER, SMS_LINK_SIGNING_SECRET; not PUBLIC_BASE_URL) and
  `cd /opt/fasalnetra && sudo ./deploy/aws/run.sh 13-205-168-88.sslip.io`
- Redeploy code: build a `git archive` tarball, upload to the private bucket `fasalnetra-deploy-323708468843`,
  and run the same script through SSM (no SSH needed)
- Optional Vercel: import the repo with root `FASALNETRA/frontend`; `vercel.json` forwards `/api` and `/uploads`
  here. Set `SMS_LINK_BASE_URL=https://<vercel-site>/walk` in `.env.server` to send farmers there.

The sections below describe the laptop + tunnel setup.

One laptop runs the backend. One HTTPS tunnel to port 8000 carries everything the phone needs:
Twilio webhooks, the SMS link page (`/walk`, the camera needs HTTPS) and Drone Didi's app (`/didi`).

## 1. Settings (`FASALNETRA/.env`)

```
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+1...            # the Twilio number the farmer dials
DEMO_FARMER_PHONE=+91XXXXXXXXXX      # the demo phone (verified in Twilio if the account is a trial)
PUBLIC_BASE_URL=https://<tunnel>     # no trailing slash
SMS_LINK_BASE_URL=                   # leave blank: link = PUBLIC_BASE_URL/walk
```

With the three Twilio values set, calls and SMS are real. Leave them blank to simulate everything.

## 2. Start

```
cd FASALNETRA/frontend && npm run build        # backend serves this build
cd FASALNETRA && uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
ngrok http 8000                                # or: cloudflared tunnel --url http://localhost:8000
```

Put the tunnel's https URL in `PUBLIC_BASE_URL` and restart uvicorn (Twilio callback URLs are built from it).
The demo farmer's phone is re-applied to the demo field at startup.

## 3. Twilio console, phone number

- A call comes in: Webhook, `POST https://<tunnel>/api/v1/ivr/webhook`
- Call status changes: `POST https://<tunnel>/api/v1/ivr/status`

## 4. Demo script

| Who | Screen | What happens |
|---|---|---|
| Farmer phone | dials the Twilio number | call is rejected (free), callback in ~3 s |
| Farmer phone | call | symptom menu (1-4), then "SMS bhej diya", whitefly question (1/2) |
| Farmer phone | SMS | link opens `/walk`: camera, voice-guided spots, walk round the patch |
| Farmer phone | `/walk` result | high: confidence % + dose. Not high: no %, Didi offer spoken + button |
| Farmer phone | call (not high) | "abhi pakka nahin... Drone Didi ke liye 1"; key 1 books her check |
| Didi (2nd phone or laptop) | `https://<tunnel>/didi` | banner + spoken alert; tap "phone par soochna chalu karein" once for notifications |
| Projector | `https://<tunnel>/` or `localhost:5173` | dashboard: map + live event feed |

Fallback if the farmer's call does not get through: the dashboard's "Farmer missed call" button
triggers the same callback to `DEMO_FARMER_PHONE`.

## Trial-account notes

- Calls and SMS only reach numbers verified in the Twilio console.
- Trial calls play a short Twilio message first and ask to press a key before our prompt starts.
- SMS from a non-Indian Twilio number to Indian numbers can be delayed or filtered (DLT rules).
  Test the SMS once before the demo. If it does not arrive, open the link shown on the dashboard
  ("Open walk page") on the phone instead.
