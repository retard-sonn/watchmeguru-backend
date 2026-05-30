from app.core.supabase_client import sb_insert, sb_select
import logging

logger = logging.getLogger(__name__)


async def log_interaction(student_id: str, direction: str, message_type: str, content: str, platform: str = "whatsapp"):
    try:
        await sb_insert("interactions", {
            "student_id": student_id,
            "direction": direction,
            "message_type": message_type,
            "content": content,
            "platform": platform,
        })
    except Exception as e:
        logger.error(f"Failed to log interaction: {e}")


async def get_student_by_clerk_id(clerk_user_id: str) -> dict:
    try:
        results = await sb_select("students", {"clerk_user_id": clerk_user_id})
        return results[0] if results else {}
    except Exception as e:
        logger.error(f"Failed to fetch student: {e}")
        return {}
