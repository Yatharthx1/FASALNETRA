[CmdletBinding()]
param(
    [string]$ProjectPath = ".\FasalNetra"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = [System.IO.Path]::GetFullPath($ProjectPath)
New-Item -ItemType Directory -Path $ProjectRoot -Force | Out-Null

function Add-Directory {
    param([Parameter(Mandatory = $true)][string]$RelativePath)

    $Path = Join-Path $ProjectRoot $RelativePath
    New-Item -ItemType Directory -Path $Path -Force | Out-Null
}

function Add-FileIfMissing {
    param(
        [Parameter(Mandatory = $true)][string]$RelativePath,
        [Parameter(Mandatory = $true)][AllowEmptyString()][string]$Content
    )

    $Path = Join-Path $ProjectRoot $RelativePath
    $Parent = Split-Path -Parent $Path

    if (-not (Test-Path $Parent)) {
        New-Item -ItemType Directory -Path $Parent -Force | Out-Null
    }

    if (Test-Path $Path) {
        Write-Host "Keeping existing file: $RelativePath" -ForegroundColor DarkYellow
    }
    else {
        Set-Content -Path $Path -Value $Content -Encoding UTF8
        Write-Host "Created: $RelativePath" -ForegroundColor Green
    }
}

$Directories = @(
    "backend",
    "backend\app",
    "backend\app\api",
    "backend\app\api\v1",
    "backend\app\api\v1\routes",
    "backend\app\core",
    "backend\app\db",
    "backend\app\domain",
    "backend\app\models",
    "backend\app\repositories",
    "backend\app\schemas",
    "backend\app\services",
    "backend\app\services\communications",
    "backend\app\services\risk",
    "backend\app\services\vision",
    "backend\app\services\mapping",
    "backend\app\services\missions",
    "backend\app\websockets",
    "backend\data\seed",
    "backend\tests\unit",
    "backend\tests\integration",
    "frontend",
    "frontend\public\audio\hi",
    "frontend\src\app",
    "frontend\src\components\layout",
    "frontend\src\components\map",
    "frontend\src\components\ui",
    "frontend\src\features\onboarding",
    "frontend\src\features\ivr",
    "frontend\src\features\risk",
    "frontend\src\features\traps",
    "frontend\src\features\field-walk",
    "frontend\src\features\evidence",
    "frontend\src\features\missions",
    "frontend\src\features\didi",
    "frontend\src\features\dashboard",
    "frontend\src\features\events",
    "frontend\src\lib",
    "frontend\src\types",
    "shared\contracts",
    "data\raw\weather",
    "data\raw\traps",
    "data\raw\leaf-photos",
    "data\raw\soy-net",
    "data\processed",
    "data\field-geojson",
    "data\seed",
    "data\uploads",
    "artifacts\maps",
    "artifacts\heatmaps",
    "artifacts\waypoints",
    "artifacts\reports",
    "docs\api",
    "docs\architecture",
    "docs\pitch",
    "scripts"
)

foreach ($Directory in $Directories) {
    Add-Directory $Directory
}

$EnvContent = @'
# ============================================================
# FASALNETRA - LOCAL ENVIRONMENT
# Never commit this file. Values below are development defaults
# and placeholders; add real credentials only in your local copy.
# ============================================================

# Application
APP_NAME=FasalNetra
APP_ENV=development
APP_DEBUG=true
LOG_LEVEL=INFO
HOST=127.0.0.1
PORT=8000
API_V1_PREFIX=/api/v1
FRONTEND_ORIGIN=http://localhost:5173
CORS_ORIGINS=["http://localhost:5173"]
SECRET_KEY=replace-with-a-long-random-secret-before-deployment
DATABASE_URL=sqlite:///./data/fasalnetra.db

# Project paths (relative to the repository root)
DATA_DIR=data
UPLOAD_DIR=data/uploads
FIELD_GEOJSON_DIR=data/field-geojson
ARTIFACTS_DIR=artifacts
WAYPOINTS_OUTPUT_DIR=artifacts/waypoints
AUDIO_PROMPT_DIR=frontend/public/audio/hi
MAX_UPLOAD_SIZE_MB=12

# Demo scenario from the PRD
DEMO_MODE=true
DEMO_DATE=2025-08-15
DEMO_OUTBREAK_REPORT_DATE=2025-09-01
DEMO_LOCATION_NAME=Mandsaur, Madhya Pradesh, India
DEMO_FARMER_NAME=Ramesh-ji
DEMO_FARMER_PHONE=+91XXXXXXXXXX
DEMO_CROP=soybean
DEMO_SOWING_AGE_DAYS=40
DEMO_FIELD_AREA_ACRES=2.0
DEMO_ZONE_AREA_ACRES=0.4
DEMO_FIELD_GEOJSON=data/field-geojson/demo-field.geojson
DEMO_SEED_FILE=data/seed/demo.json

# Twilio Voice and SMS
# Get these from your Twilio Console. Do not put real credentials in Git.
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=replace-with-your-twilio-auth-token
TWILIO_PHONE_NUMBER=+1XXXXXXXXXX
TWILIO_MESSAGING_SERVICE_SID=
TWILIO_VALIDATE_SIGNATURE=true
PUBLIC_BASE_URL=https://replace-with-your-public-tunnel-domain
TWILIO_VOICE_WEBHOOK_PATH=/api/v1/ivr/webhook
TWILIO_VOICE_STATUS_PATH=/api/v1/ivr/status
TWILIO_SMS_STATUS_PATH=/api/v1/sms/status
TWILIO_CONNECT_TIMEOUT_SECONDS=10

# IVR rules (PRD: 8-second timeout, one repeat, 2-hour retry)
IVR_DEFAULT_LANGUAGE=hi-IN
IVR_TIMEOUT_SECONDS=8
IVR_MAX_REPROMPTS=1
IVR_REPEAT_DIGIT=9
IVR_HUMAN_TRANSFER_DIGIT=0
IVR_CALLBACK_SLA_SECONDS=30
IVR_RETRY_AFTER_MINUTES=120
IVR_MAX_OPTIONS_PER_PROMPT=4
IVR_PROMPT_FORMAT=mp3

# SMS upload-link settings
SMS_LINK_BASE_URL=http://localhost:5173/field
SMS_LINK_TOKEN_TTL_MINUTES=1440
SMS_LINK_SIGNING_SECRET=replace-with-a-different-long-random-secret

# Recorded Hindi prompts are the default. Use an Indian-language TTS
# provider only for dynamic names/numbers after configuring it.
TTS_MODE=recorded
DYNAMIC_TTS_PROVIDER=none
TTS_LANGUAGE=hi-IN
TTS_CACHE_DIR=backend/data/tts-cache

# Weather data: Open-Meteo archive, Mandsaur demo period
WEATHER_PROVIDER=open-meteo
OPEN_METEO_BASE_URL=https://archive-api.open-meteo.com/v1/archive
WEATHER_ARCHIVE_START=2025-06-01
WEATHER_ARCHIVE_END=2025-09-15
WEATHER_TIMEZONE=Asia/Kolkata
LEAF_WETNESS_HUMIDITY_THRESHOLD_PCT=90

# Risk engine
RISK_HIGH_THRESHOLD=70
RISK_WATCH_THRESHOLD=40
CROP_VULNERABLE_MIN_DAYS=30
CROP_VULNERABLE_MAX_DAYS=60
RISK_FORECAST_DAYS=15

# PRD specifies Tmax > 33 C but says the remaining paper thresholds
# must be verified. Keep rule status provisional until Coder A checks it.
MP_YELLOW_MOSAIC_RULE_STATUS=provisional
MP_YELLOW_MOSAIC_TMAX_THRESHOLD_C=33
MP_YELLOW_MOSAIC_SUNSHINE_WEIGHT=
MP_YELLOW_MOSAIC_RAIN_WEIGHT=
MP_YELLOW_MOSAIC_EVENING_HUMIDITY_WEIGHT=

# ICAR-IISR advisory metadata. Populate the exact advisory after verification.
IISR_ADVISORY_ORGANIZATION=ICAR-IISR
IISR_ADVISORY_WEEK=
IISR_ADVISORY_TEXT=
IISR_ADVISORY_SOURCE_URL=
IISR_ADVISORY_FLAG=true

# Vision AI: mock mode lets the UI/backend flow be built before a model is wired in.
VISION_PROVIDER=mock
VISION_MODEL_PATH=
VISION_API_URL=
VISION_API_KEY=
VISION_REQUEST_TIMEOUT_SECONDS=5
VISION_BLUR_CHECK_ENABLED=true
VISION_TRAP_CLASS=whitefly
VISION_LEAF_CLASSES=yellow_mosaic,chewing_damage,fungal,healthy

# Trap analysis and five-spot field walk
TRAP_PHOTO_COUNT=4
FIELD_WALK_SPOT_COUNT=5
FIELD_WALK_PATTERN=W
FIELD_WALK_PHOTOS_PER_SPOT=2
FIELD_WALK_REQUIRE_GPS=true
FIELD_WALK_ALLOW_SEEDED_GPS_FALLBACK=true

# Evidence weighting from the PRD
EVIDENCE_WEIGHT_PHOTO_AI=3
EVIDENCE_WEIGHT_TRAP_COUNTS=2
EVIDENCE_WEIGHT_KEYPAD_ANSWERS=2
EVIDENCE_WEIGHT_WEATHER=2
EVIDENCE_WEIGHT_CROP_STAGE=1
EVIDENCE_WEIGHT_IISR_ADVISORY=1
EVIDENCE_HIGH_CONFIDENCE_PCT=75
EVIDENCE_MEDIUM_CONFIDENCE_PCT=50
SPRAY_REQUIRES_HIGH_CONFIDENCE=true
SPRAY_REQUIRES_HUMAN_CONFIRMATION_WHEN_NOT_HIGH=true

# Mapping and spray mission
MAP_TILE_URL=https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png
ZONE_MIN_SEVERITY=2
DRONE_ROUTE_ALGORITHM=lawnmower
DRONE_WAYPOINT_EXTENSION=.waypoints
DRONE_WAYPOINTS_OUTPUT_DIR=artifacts/waypoints
DRONE_SIMULATION_ENABLED=true
SPRAY_ZONE_BUFFER_METERS=
SPRAY_DOSE_LITRES_PER_ACRE=
PESTICIDE_PRICE_INR_PER_LITRE=
PESTICIDE_PRODUCT_NAME=
# Fill dose and price only from the actual product label and local shop quote.

# Dashboard and live events
WEBSOCKET_PATH=/api/v1/ws/events
WEBSOCKET_HEARTBEAT_SECONDS=25
EVENT_LOG_TO_DATABASE=true
DASHBOARD_DEMO_RESET_ENABLED=true

# Feature flags: P1 items stay off until every P0 path works.
FEATURE_DAY_PLUS_FIVE=false
FEATURE_NEIGHBOUR_WARNINGS=false
FEATURE_EDGE_EXPOSURE_LINE=false
FEATURE_SENTINEL2_LAYER=false
FEATURE_RISK_HEATMAP_AUTOPLAY=false
FEATURE_ARDUPILOT_SITL=false
'@

Add-FileIfMissing ".env" $EnvContent
Add-FileIfMissing ".env.example" $EnvContent

Add-FileIfMissing ".gitignore" @'
# Secrets and local environment
.env
.env.*
!.env.example

# Python
.venv/
venv/
__pycache__/
*.py[cod]
.pytest_cache/
.ruff_cache/
.coverage
htmlcov/

# Node
node_modules/
dist/
.vite/

# Local databases and runtime files
*.db
*.sqlite
*.sqlite3
*.log

# User uploads and generated data (keep folder placeholders)
data/uploads/*
!data/uploads/.gitkeep
backend/data/tts-cache/
artifacts/*
!artifacts/**/
!artifacts/**/.gitkeep

# Editors / OS
.vscode/
.idea/
.DS_Store
Thumbs.db
'@

Add-FileIfMissing "README.md" @'
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
'@

Add-FileIfMissing "backend\requirements.txt" @'
fastapi>=0.115,<1.0
uvicorn[standard]>=0.30
pydantic-settings>=2.4
sqlalchemy>=2.0
httpx>=0.27
twilio>=9.2
python-multipart>=0.0.9
python-dotenv>=1.0
shapely>=2.0
pillow>=10.4
'@

Add-FileIfMissing "backend\requirements-dev.txt" @'
-r requirements.txt
pytest>=8.0
pytest-asyncio>=0.24
ruff>=0.6
'@

Add-FileIfMissing "backend\__init__.py" ""
Add-FileIfMissing "backend\app\__init__.py" ""
Add-FileIfMissing "backend\app\main.py" @'
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.v1.router import api_router
from backend.app.core.config import settings

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/", tags=["root"])
async def root() -> dict[str, str]:
    return {"name": settings.app_name, "status": "running"}
'@

Add-FileIfMissing "backend\app\core\__init__.py" ""
Add-FileIfMissing "backend\app\core\config.py" @'
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "FasalNetra"
    app_env: str = "development"
    app_debug: bool = True
    api_v1_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./data/fasalnetra.db"
    cors_origins: list[str] = ["http://localhost:5173"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
'@

Add-FileIfMissing "backend\app\api\__init__.py" ""
Add-FileIfMissing "backend\app\api\v1\__init__.py" ""
Add-FileIfMissing "backend\app\api\v1\router.py" @'
from fastapi import APIRouter

from backend.app.api.v1.routes import health

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])

# Add routers here as the P0 slices are implemented:
# farmers, ivr, sms, risk, traps, field_walk, evidence, missions, events, demo.
'@

Add-FileIfMissing "backend\app\api\v1\routes\__init__.py" ""
Add-FileIfMissing "backend\app\api\v1\routes\health.py" @'
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "fasalnetra-api"}
'@

Add-FileIfMissing "backend\app\services\README.md" @'
# Service boundaries

Keep external integrations behind service adapters:

- `communications/`: Twilio calls, keypad handling, SMS links and recorded Hindi prompts.
- `risk/`: Open-Meteo retrieval, crop-stage features and the rule-based risk score.
- `vision/`: trap insect counts, leaf symptom classification and image quality checks.
- `mapping/`: field geometry, heat map and affected-zone calculations.
- `missions/`: zone-only lawnmower route, `.waypoints` export and spray savings.

Do not let route handlers contain business logic. Keep low-confidence cases on the human-expert path.
'@

Add-FileIfMissing "backend\app\domain\README.md" @'
# Domain

Place business rules and domain types here. The PRD references shared `Field`, `Risk`, `Signal`, `Evidence`, `Mission` and `Event` JSON contracts; copy the team's agreed shapes into `shared/contracts/` before implementing integrations. Do not silently invent a competing schema.
'@

Add-FileIfMissing "backend\app\db\README.md" @'
# Database

SQLite is the hackathon default. Keep persistence/repository code here. Store generated demo state locally; do not commit the database file.
'@

Add-FileIfMissing "shared\contracts\README.md" @'
# Shared contracts

Keep versioned JSON Schema or TypeScript/Python contract definitions here.

Required contract names from the PRD: `Field`, `Risk`, `Signal`, `Evidence`, `Mission`, `Event`. The PRD points to a separate game-plan contract, so use that agreed source as the schema authority.
'@

Add-FileIfMissing "frontend\package.json" @'
{
  "name": "fasalnetra-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite --host 0.0.0.0",
    "build": "tsc -b && vite build",
    "preview": "vite preview --host 0.0.0.0"
  },
  "dependencies": {
    "leaflet": "^1.9.4",
    "lucide-react": "^0.468.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "react-leaflet": "^5.0.0"
  },
  "devDependencies": {
    "@types/leaflet": "^1.9.15",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "@vitejs/plugin-react": "^4.3.4",
    "typescript": "^5.7.2",
    "vite": "^6.0.5"
  }
}
'@

Add-FileIfMissing "frontend\index.html" @'
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="theme-color" content="#14532d" />
    <title>FasalNetra</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
'@

Add-FileIfMissing "frontend\vite.config.ts" @'
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
  },
});
'@

Add-FileIfMissing "frontend\tsconfig.json" @'
{
  "compilerOptions": {
    "target": "ES2022",
    "useDefineForClassFields": true,
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "Bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true
  },
  "include": ["src"]
}
'@

Add-FileIfMissing "frontend\src\main.tsx" @'
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
'@

Add-FileIfMissing "frontend\src\App.tsx" @'
export default function App() {
  return (
    <main className="app-shell">
      <p className="eyebrow">AI Manthan 2.0 · Hackathon demo</p>
      <h1>FasalNetra</h1>
      <p>
        Weather tells us when. Traps and the guided field walk tell us where.
        Vision AI helps identify what needs attention.
      </p>
      <p className="status">Frontend scaffold is running.</p>
    </main>
  );
}
'@

Add-FileIfMissing "frontend\src\styles.css" @'
:root {
  font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  color: #17251b;
  background: #f4f7f1;
  font-synthesis: none;
  text-rendering: optimizeLegibility;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  min-width: 320px;
  min-height: 100vh;
}

.app-shell {
  max-width: 900px;
  margin: 10vh auto;
  padding: 32px;
}

.eyebrow {
  color: #47734f;
  font-size: 0.8rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

h1 {
  margin-bottom: 12px;
  font-size: clamp(2.5rem, 8vw, 5rem);
}

.status {
  display: inline-block;
  margin-top: 20px;
  padding: 10px 14px;
  border-radius: 999px;
  background: #dcebdc;
  color: #1c5c2b;
  font-weight: 600;
}
'@

Add-FileIfMissing "frontend\src\lib\README.md" @'
# Frontend utilities

Put the typed API client, WebSocket client, audio playback helpers and upload helpers here.
'@

Add-FileIfMissing "frontend\src\types\README.md" @'
# Frontend types

Import types generated from or aligned with `shared/contracts/`. Avoid defining duplicate API shapes here.
'@

Add-FileIfMissing "data\seed\README.md" @'
# Seed data

Store the reproducible demo farmer, field, neighbour fields and event sequence here. Use synthetic/demo contact details only.
'@

Add-FileIfMissing "data\field-geojson\README.md" @'
# Field geometry

Place the demo farmer and neighbour field outlines here as GeoJSON. Keep coordinates and landmarks consistent with the seeded farmer record.
'@

Add-FileIfMissing "frontend\public\audio\hi\README.md" @'
# Hindi IVR prompts

Place the pre-recorded Hindi MP3 prompts here. Keep prompt IDs stable and map them in the backend IVR prompt registry.
'@

Add-FileIfMissing "docs\architecture\README.md" @'
# Architecture notes

Document the request flow, service boundaries, event contract and deployment/tunnel setup here.
'@

Add-FileIfMissing "docs\api\README.md" @'
# API notes

Document endpoints and sample payloads. Keep the authoritative schemas in `shared/contracts/`.
'@

# Preserve otherwise-empty directories in Git.
$KeepDirectories = @(
    "data\raw\weather",
    "data\raw\traps",
    "data\raw\leaf-photos",
    "data\raw\soy-net",
    "data\processed",
    "data\uploads",
    "artifacts\maps",
    "artifacts\heatmaps",
    "artifacts\waypoints",
    "artifacts\reports",
    "backend\tests\unit",
    "backend\tests\integration",
    "backend\data\seed",
    "scripts",
    "docs\pitch"
)

foreach ($Directory in $KeepDirectories) {
    Add-FileIfMissing (Join-Path $Directory ".gitkeep") ""
}

Write-Host ""
Write-Host "FasalNetra scaffold created at: $ProjectRoot" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Open $ProjectRoot\.env and add your real Twilio credentials."
Write-Host "  2. From the project root, create the Python venv and install backend requirements:"
Write-Host "       py -m venv .venv"
Write-Host "       .\.venv\Scripts\Activate.ps1"
Write-Host "       pip install -r backend\requirements.txt"
Write-Host "  3. Start the API from the project root:"
Write-Host "       uvicorn backend.app.main:app --reload"
Write-Host "  4. In another terminal:"
Write-Host "       cd frontend"
Write-Host "       npm install"
Write-Host "       npm run dev"
Write-Host ""
Write-Host "Important: .env is ignored by Git. Commit .env.example, never .env." -ForegroundColor Yellow
