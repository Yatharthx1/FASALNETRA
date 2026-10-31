---
title: FasalNetra
emoji: 🌱
colorFrom: green
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
short_description: Soybean crop-health IVR, SMS photo walk and Drone Didi API
---

# FasalNetra API

Backend for FasalNetra (AI Manthan 2.0): Twilio IVR (missed call -> voice report -> SMS photo link),
evidence fusion, zone-only Drone Didi missions. The farmer page, Didi app and dashboard are deployed on
Vercel and forward `/api` and `/uploads` here.

Settings (Space -> Settings -> Variables and secrets): `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`,
`TWILIO_PHONE_NUMBER`, `DEMO_FARMER_PHONE`, `VISION_PROVIDER`, `SMS_LINK_SIGNING_SECRET`,
`PUBLIC_BASE_URL` (this Space's URL), `SMS_LINK_BASE_URL` (the Vercel site + `/walk`).
Optional `DATABASE_URL` (Postgres) to keep data across Space restarts; otherwise SQLite, re-seeded on start.
