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
    database_url: str = f"sqlite+aiosqlite:///{(REPO_ROOT / 'data' / 'fasalnetra.db').as_posix()}"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Demo scenario (PRD): Mandsaur, 15 Aug 2025, crop 40 days old
    demo_mode: bool = True
    demo_date: date = date(2025, 8, 15)
    demo_farmer_name: str = "Ramesh-ji"
    demo_farmer_phone: str = "+919876543210"
    demo_sowing_age_days: int = 40
    demo_field_geojson: Path = REPO_ROOT / "data" / "field-geojson" / "demo-field.geojson"

    # Public tunnel / URL
    public_base_url: str = "http://localhost:8000"

    # Twilio Voice and SMS: left blank -> calls and SMS are simulated
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""
    twilio_validate_signature: bool = False

    # IVR settings (flows live in services/communications/*_state_machine.py)
    ivr_default_language: str = "hi-IN"
    ivr_timeout_seconds: int = 8
    ivr_max_reprompts: int = 1
    ivr_repeat_digit: str = "9"
    ivr_callback_sla_seconds: int = 30

    # Paths and links. The SMS link opens the frontend's /walk page with a signed case token.
    audio_prompt_dir: str = "frontend/public/audio/hi"
    sms_link_base_url: str = "http://localhost:5173/walk"
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
    def twilio_enabled(self) -> bool:
        return bool(self.twilio_account_sid and self.twilio_auth_token and self.twilio_phone_number)


settings = Settings()
