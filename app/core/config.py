from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    # Supabase
    supabase_url: str = ""
    supabase_key: str = ""

    # Gemini AI
    gemini_api_key: str = ""

    # Groq AI
    groq_api_key: str = ""

    # Clerk Auth
    clerk_secret_key: str = ""
    clerk_publishable_key: str = ""

    # Telegram
    telegram_bot_token: str = ""

    # Discord
    discord_app_id: str = ""
    discord_public_key: str = ""
    discord_bot_token: str = ""

    # Twilio (WhatsApp)
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_number: str = ""

    # Resend (Email)
    resend_api_key: str = ""

    # Legacy WhatsApp (Meta direct — kept for compat)
    whatsapp_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_verify_token: str = ""

    # Environment
    environment: str = "development"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

@lru_cache
def get_settings():
    return Settings()
