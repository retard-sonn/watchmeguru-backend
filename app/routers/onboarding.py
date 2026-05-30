from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List, Any
from app.core.supabase_client import sb_update, sb_select, sb_insert
import logging
import json

router = APIRouter()
logger = logging.getLogger(__name__)


class SetupProfileRequest(BaseModel):
    exam_type: str
    exam_date: Optional[str] = None
    focus_subjects: Optional[str] = None          # comma-separated subjects
    weak_subjects: Optional[str] = None           # alias used by wizard
    mode: str
    guardian_contact: Optional[str] = None
    schedule_type: Optional[str] = "ai"
    schedule_locked: Optional[bool] = True
    setup_complete: Optional[bool] = True
    # Channel fields
    preferred_channel: Optional[str] = "dashboard"
    channel_handle: Optional[str] = None
    # AI-generated schedule — MUST be saved to DB
    schedule_data: Optional[Any] = None


@router.post("/setup")
async def complete_setup(request: Request, payload: SetupProfileRequest, background_tasks: BackgroundTasks):
    clerk_id = getattr(request.state, "clerk_user_id", None)
    if not clerk_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if payload.mode not in ["strict", "moderate", "own_pace"]:
        raise HTTPException(status_code=400, detail="Invalid accountability mode")

    # Normalize subjects — support both field names from wizard
    raw_subjects = payload.focus_subjects or payload.weak_subjects or ""
    weak_array = [s.strip() for s in raw_subjects.split(",") if s.strip()]

    # Map preferred_channel → preferred_platforms array for DB
    channel = payload.preferred_channel or "dashboard"
    preferred_platforms = [channel] if channel != "dashboard" else []

    # Map channel handle to the correct column
    whatsapp_number = None
    discord_user_id = None
    telegram_chat_id = None
    if channel == "whatsapp" and payload.channel_handle:
        whatsapp_number = payload.channel_handle
    elif channel == "discord" and payload.channel_handle:
        discord_user_id = payload.channel_handle
    elif channel == "telegram" and payload.channel_handle:
        telegram_chat_id = payload.channel_handle

    # Serialize schedule_data — store full JSON in daily_schedule column
    daily_schedule = None
    if payload.schedule_data:
        daily_schedule = payload.schedule_data if isinstance(payload.schedule_data, (dict, list)) else None

    try:
        # Get Clerk user info to save name
        clerk_user = getattr(request.state, "clerk_user", {})
        name = f"{clerk_user.get('first_name', '')} {clerk_user.get('last_name', '')}".strip()

        record = {
            "name": name or "",
            "exam_type": payload.exam_type,
            "exam_date": payload.exam_date,
            "weak_subjects": weak_array,
            "mode": payload.mode,
            "guardian_contact": payload.guardian_contact,
            "preferred_platforms": preferred_platforms if preferred_platforms else ["whatsapp"],
            "whatsapp_number": whatsapp_number,
            "discord_user_id": discord_user_id,
            "telegram_chat_id": telegram_chat_id,
            "schedule_locked": payload.schedule_locked if payload.schedule_locked is not None else True,
            "daily_schedule": daily_schedule,
        }

        # Check if student row exists
        existing = await sb_select("students", {"clerk_user_id": clerk_id})

        if existing:
            await sb_update("students", record, {"clerk_user_id": clerk_id})
        else:
            await sb_insert("students", {"clerk_user_id": clerk_id, **record})

        # Send Twilio welcome WhatsApp ping after setup
        if whatsapp_number:
            welcome_body = (
                f"🏆 *Welcome to WatchMeGuru, {name or 'Student'}!*\n\n"
                f"I am your academic mentor. I have locked in your study schedule for *{payload.exam_type}*.\n\n"
                f"Every day, I will monitor your sessions. After each study block, you MUST send a photo of your notebook/work here for proof.\n\n"
                f"If you miss a session, I will ping you. Under strict mode, your guardian ({payload.guardian_contact or 'contact'}) will be alerted after 3 missed days.\n\n"
                f"Your first block is waiting in your dashboard. Let's make it happen! 🚀"
            )
            try:
                from app.services.twilio_service import send_whatsapp
                background_tasks.add_task(send_whatsapp, whatsapp_number, welcome_body)
            except Exception as tw_err:
                logger.error(f"Failed to queue welcome WhatsApp ping: {tw_err}")

        logger.info(f"Profile configured for {clerk_id} — channel={channel}, schedule_saved={daily_schedule is not None}")
        return {"success": True, "message": "Profile configured and schedule locked."}

    except Exception as e:
        logger.error(f"Setup failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
