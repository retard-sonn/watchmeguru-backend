"""
Discord Message Service
Sends direct messages to students via Discord bot.
"""
import logging
import httpx
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

DISCORD_API = "https://discord.com/api/v10"


async def send_discord_message(user_id: str, message: str) -> bool:
    """Send a DM to a Discord user via the Discord bot."""
    token = settings.discord_bot_token
    if not token or not user_id:
        logger.warning("Discord not configured or no user_id")
        return False

    try:
        # First, create DM channel
        async with httpx.AsyncClient() as client:
            dm_res = await client.post(
                f"{DISCORD_API}/users/@me/channels",
                json={"recipient_id": user_id},
                headers={"Authorization": f"Bot {token}", "Content-Type": "application/json"},
            )
            if dm_res.status_code == 200:
                channel_id = dm_res.json()["id"]
            else:
                # Maybe already have a DM channel; try user_id directly
                channel_id = user_id

            # Send message
            msg_res = await client.post(
                f"{DISCORD_API}/channels/{channel_id}/messages",
                json={"content": message},
                headers={"Authorization": f"Bot {token}", "Content-Type": "application/json"},
            )
            if msg_res.status_code == 200:
                logger.info(f"Discord message sent to {user_id}")
                return True
            else:
                logger.error(f"Discord send failed: {msg_res.status_code} {msg_res.text}")
                return False
    except Exception as e:
        logger.error(f"Discord message error: {e}")
        return False
