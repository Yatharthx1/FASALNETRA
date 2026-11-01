from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]
# Services that read os.environ directly (vision keys, model names) see .env values too.
load_dotenv(REPO_ROOT / ".env", override=False)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT / ".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "FasalNetra"
    app_version: str = "0.2.0"
    app_env: str = "development"
    app_debug: bool = True
    api_v1_prefix: str = "/api/v1"
    # Local: SQLite file. Vercel: Postgres (Neon) URL from the Marketplace integration, any of these spellings.
    database_url: str = f"sqlite+aiosqlite:///{(REPO_ROOT / 'data' / 'fasalnetra.db').as_posix()}"
    postgres_url: str = ""
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Demo scenario (PRD): Mandsaur, 15 Aug 2025, crop 40 days old
    demo_mode: bool = True
    demo_date: date = date(2025, 8, 15)
    demo_farmer_name: str = "Ramesh-ji"
    demo_farmer_phone: str = "+919876543210"
    demo_sowing_age_days: int = 40
    demo_farmer_preregistered: bool = False   # True: skip IVR onboarding for DEMO_FARMER_PHONE
    demo_seed_neighbours: bool = False        # True: two sample neighbour tickets in Didi's queue at startup
    demo_problem_level: str = ""   # "high" | "medium" | "low" pins the spoken problem level; blank = from the photos
    demo_field_geojson: Path = REPO_ROOT / "data" / "field-geojson" / "demo-field.geojson"

    # Public tunnel / URL
    public_base_url: str = "http://localhost:8000"

    # Twilio Voice and SMS: left blank -> calls and SMS are simulated
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""
    twilio_validate_signature: bool = False
    # Inbound call to the Twilio number: "answer" runs the IVR in that same call (works on trial accounts,
    # the caller pays their own call); "callback" rejects it (free missed call) and FasalNetra calls back.
    ivr_inbound_mode: str = "answer"

    # Link channel: "twilio" (SMS) | "whatsapp" (Twilio WhatsApp; sandbox works on trial accounts, no DLT) |
    # "waapi" (waapi.app: sends from the team's own WhatsApp number, no sandbox join, no Twilio needed) |
    # "waha" (self-hosted WAHA, free: a team WhatsApp number linked by QR at /api/v1/wa/qr/<secret>) |
    # "aws" (AWS End User Messaging SMS) | blank = Twilio SMS when configured, else simulated.
    # AWS End User Messaging SMS needs, for India, a TRAI DLT entity + approved template and a registered sender ID;
    # a sandbox account can only text verified numbers under a $1/month cap until AWS Support lifts both.
    sms_provider: str = ""
    waha_url: str = ""                 # "waha": self-hosted WAHA on the server's docker network, e.g. http://waha:3000
    waha_api_key: str = ""
    waha_session: str = "default"
    waapi_instance_id: str = ""        # "waapi": waapi.app instance (a normal WhatsApp number linked by QR)
    waapi_token: str = ""              # API token from https://waapi.app/user/api-tokens
    waapi_webhook_secret: str = ""     # path secret of /api/v1/wa/webhook/<secret>; blank = derived from the link secret
    whatsapp_ivr: bool = False         # True: the IVR also runs in a WhatsApp chat (routes/whatsapp.py); False:
                                       # waAPI only sends the camera link and Didi's alert, the IVR is the phone call
    whatsapp_voice_notes: bool = True  # WhatsApp IVR: each prompt also as a Hindi voice note (OpenAI TTS)
    didi_phone: str = ""               # Drone Didi's WhatsApp: gets each new booking with the /didi link
    twilio_whatsapp_from: str = "+14155238886"   # Twilio WhatsApp sandbox number; the farmer sends "join <code>" once
    aws_sms_region: str = "ap-south-1"
    aws_sms_sender_id: str = ""        # DLT-registered sender ID (origination identity)
    aws_sms_entity_id: str = ""        # DLT principal entity ID
    aws_sms_template_id: str = ""      # DLT template ID; the message text must match the template exactly

    # IVR settings (flows live in services/communications/*_state_machine.py)
    ivr_default_language: str = "hi-IN"
    ivr_timeout_seconds: int = 8
    ivr_max_reprompts: int = 1
    ivr_repeat_digit: str = "9"
    ivr_callback_sla_seconds: int = 30

    # Paths and links. The SMS link opens the frontend's /walk page with a signed case token;
    # blank = PUBLIC_BASE_URL/walk (the backend serves the built frontend, so the phone needs only one tunnel).
    audio_prompt_dir: str = str(REPO_ROOT / "frontend" / "public" / "audio" / "hi")
    sms_link_base_url: str = ""
    sms_link_signing_secret: str = "dev-only-change-me"
    sms_link_token_ttl_minutes: int = 1440

    upload_dir: Path = REPO_ROOT / "data" / "uploads"
    waypoints_dir: Path = REPO_ROOT / "artifacts" / "waypoints"

    # Spray mission (agri drone defaults; check the operator's drone)
    drone_swath_m: float = 4.0
    drone_altitude_m: float = 3.0
    zone_buffer_m: float = 1.0
    spot_radius_m: float = 8.0
    pesticide_price_inr_per_unit: float | None = None   # from a local shop quote, per ml/g
    drone_minutes_per_battery: float = 10.0             # spray time per battery charge (check the drone's spec)
    generator_litres_per_charge: float = 0.3            # petrol to recharge one battery in the field (assumed)

    # Drone Didi profile (demo operator; replace with the SHG's real details)
    didi_name: str = "सीमा दीदी"
    didi_shg: str = "जय किसान स्वयं सहायता समूह"
    didi_village: str = "Rampura"
    didi_drone: str = "Agri drone, 10 L tank"
    didi_batteries: int = 4
    didi_tank_l: float = 10.0
    didi_base_lon: float = 75.1180
    didi_base_lat: float = 24.0990

    @property
    def is_postgres(self) -> bool:
        return self._db_url.startswith(("postgres://", "postgresql"))

    @property
    def _db_url(self) -> str:
        return self.postgres_url if self.database_url.startswith("sqlite") and self.postgres_url else self.database_url

    def db_url(self, *, sync: bool) -> str:
        """Driver-specific URL. Postgres uses psycopg 3 for both the async case engine and the sync IVR engine."""
        url = self._db_url
        if self.is_postgres:
            rest = url.split("://", 1)[1]
            return f"postgresql+psycopg://{rest}"
        return url.replace("+aiosqlite", "") if sync else url

    @property
    def walk_link_base(self) -> str:
        return self.sms_link_base_url or f"{self.public_base_url.rstrip('/')}/walk"

    @property
    def sms_channel(self) -> str:
        return self.sms_provider or ("twilio" if self.twilio_enabled else "simulated")

    @property
    def link_channel_hi(self) -> str:
        """What the IVR calls the message the link arrives in."""
        return "व्हाट्सऐप" if self.sms_channel in ("whatsapp", "waapi", "waha") else "SMS"

    @property
    def twilio_enabled(self) -> bool:
        return bool(self.twilio_account_sid and self.twilio_auth_token and self.twilio_phone_number)


settings = Settings()
