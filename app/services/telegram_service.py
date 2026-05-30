"""
Telegram Message Service
Sends messages to students via Telegram bot.
"""
import logging
import httpx
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

TELEGRAM_API = "https://api.telegram.org"


async def send_telegram_message(chat_id: str, message: str) -> bool:
    """Send a message to a Telegram user via the bot."""
    token = settings.telegram_bot_token
    if not token or not chat_id:
        logger.warning("Telegram not configured or no chat_id")
        return False

    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(
                f"{TELEGRAM_API}/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
            )
            if res.status_code == 200:
                logger.info(f"Telegram message sent to {chat_id}")
                return True
            else:
                logger.error(f"Telegram send failed: {res.status_code} {res.text}")
                return False
    except Exception as e:
        logger.error(f"Telegram message error: {e}")
        return False
