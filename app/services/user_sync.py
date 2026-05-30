"""
User Sync Service — upserts Clerk user data to Supabase 'users' table via REST API.
Called by ClerkAuthMiddleware on every authenticated request.
"""

from app.core.supabase_client import sb_upsert
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


async def sync_clerk_user_to_db(user_data: dict) -> dict:
    clerk_user_id = user_data.get("clerk_user_id", "")
    if not clerk_user_id:
        return {}

    record = {
        "clerk_user_id": clerk_user_id,
        "email": user_data.get("email", ""),
        "first_name": user_data.get("first_name", ""),
        "last_name": user_data.get("last_name", ""),
        "profile_image_url": user_data.get("profile_image_url", ""),
        "last_synced_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        result = await sb_upsert("users", record, on_conflict="clerk_user_id")
        logger.debug(f"Synced user {clerk_user_id}")
        return result[0] if result else {}
    except Exception as e:
        logger.error(f"Failed to sync user {clerk_user_id}: {e}")
        raise
