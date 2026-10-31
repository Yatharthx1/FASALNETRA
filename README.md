# FasalNetra

FasalNetra is a field-level crop-risk and precision-spraying demo for soybean farmers.

## Repository layout

- `backend/`: FastAPI API, IVR/Twilio integration, risk engine, vision adapters, evidence scoring and mission generation.
- `frontend/`: React/Vite farmer flow, dashboard, map and Drone Didi view.
- `shared/contracts/`: shared API/event contract definitions. Port the exact `Field`, `Risk`, `Signal`, `Evidence`, `Mission` and `Event` shapes from the team's agreed game plan here.
- `data/`: source datasets, seed data, field GeoJSON and uploads.
- `artifacts/`: generated heat maps, maps, reports and `.waypoints`.
- `docs/`: architecture, API notes and pitch material.

## Backend

Run commands from the repository root so `.env` is loaded:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

API health check: `http://127.0.0.1:8000/api/v1/health`

## Frontend

In a second PowerShell window:

```powershell
cd frontend
npm install
npm run dev
```

Frontend: `http://localhost:5173`

## Before connecting live services

1. Add real Twilio credentials to your local `.env` and configure the public webhook URL.
2. Keep `VISION_PROVIDER=mock` until the chosen model/API adapter is ready.
3. Verify the complete MP yellow-mosaic weather rule from the cited paper. The remaining coefficients in `.env` are intentionally blank, not invented.
4. Add the exact ICAR-IISR advisory metadata.
5. Set pesticide dose and price from the actual product label and local shop quote.
6. Keep spray actions disabled unless evidence confidence is High or a human expert has confirmed.

Never commit `.env`, farmer phone numbers, credentials or private field photos.
