from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "FasalNetra"
    app_env: str = "development"
    app_debug: bool = True
    api_v1_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./data/fasalnetra.db"
    cors_origins: list[str] = ["http://localhost:5173"]

    # Public tunnel / URL
    public_base_url: str = "http://localhost:8000"

    # Twilio Voice and SMS
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""
    twilio_validate_signature: bool = False

    # IVR settings
    ivr_default_language: str = "hi-IN"
    ivr_timeout_seconds: int = 8
    ivr_max_reprompts: int = 1
    ivr_repeat_digit: str = "9"
    ivr_callback_sla_seconds: int = 30

    # Paths and links
    audio_prompt_dir: str = "frontend/public/audio/hi"
    sms_link_base_url: str = "http://localhost:5173/field"
    demo_farmer_phone: str = "+919876543210"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
