"""
Onboarding Router — student profile setup and editing.
"""
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Any, Literal
from app.core.supabase_client import sb_upsert, sb_select, sb_update
import logging
import re

router = APIRouter()
logger = logging.getLogger(__name__)

VALID_CHANNELS = ["dashboard", "whatsapp", "discord", "telegram"]
VALID_MODES = ["strict", "moderate", "own_pace"]


class SetupProfileRequest(BaseModel):
    exam_type: str = Field(..., min_length=1, max_length=100)
    exam_date: Optional[str] = None
    focus_subjects: Optional[str] = None
    weak_subjects: Optional[str] = None
    mode: str = Field(default="own_pace", min_length=1, max_length=20)
    guardian_contact: Optional[str] = None
    schedule_type: Optional[str] = "ai"
    schedule_locked: Optional[bool] = None
    setup_complete: Optional[bool] = True
    preferred_channel: Optional[str] = "dashboard"
    channel_handle: Optional[str] = None
    student_email: Optional[str] = None
    parent_email: Optional[str] = None
    schedule_data: Optional[Any] = None
    country: Optional[str] = None
    country_code: Optional[str] = None
    isd_code: Optional[str] = None

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        if v not in VALID_MODES:
            raise ValueError(f"Invalid mode. Must be one of: {', '.join(VALID_MODES)}")
        return v

    @field_validator("preferred_channel")
    @classmethod
    def validate_channel(cls, v: str) -> str:
        if v and v not in VALID_CHANNELS:
            raise ValueError(f"Invalid channel. Must be one of: {', '.join(VALID_CHANNELS)}")
        return v

    @field_validator("student_email", "parent_email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v and not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', v):
            raise ValueError(f"Invalid email format: {v}")
        return v

    @field_validator("schedule_data")
    @classmethod
    def validate_schedule_data(cls, v: Optional[Any]) -> Optional[Any]:
        if v is not None and not isinstance(v, (dict, list)):
            raise ValueError("schedule_data must be a dict or list")
        if v is not None:
            import json
            s = json.dumps(v)
            if len(s) > 500_000:
                raise ValueError("schedule_data exceeds maximum size (500KB)")
        return v


@router.post("/setup")
async def complete_setup(request: Request, payload: SetupProfileRequest, background_tasks: BackgroundTasks):
    clerk_id = getattr(request.state, "clerk_user_id", None)
    if not clerk_id or not str(clerk_id).strip():
        raise HTTPException(status_code=401, detail="Unauthorized")
    clerk_id = str(clerk_id)

    # Normalize subjects
    raw_subjects = payload.focus_subjects or payload.weak_subjects or ""
    weak_array = [s.strip() for s in raw_subjects.split(",") if s.strip()]

    # Map channel
    channel = payload.preferred_channel or "dashboard"
    preferred_platforms = [channel] if channel != "dashboard" else ["whatsapp"]
    whatsapp_number = payload.channel_handle if channel == "whatsapp" else None
    discord_user_id = payload.channel_handle if channel == "discord" else None
    telegram_chat_id = payload.channel_handle if channel == "telegram" else None

    # Serialize schedule
    daily_schedule = None
    if payload.schedule_data and isinstance(payload.schedule_data, (dict, list)):
        daily_schedule = payload.schedule_data

    # Get Clerk user info
    clerk_user = getattr(request.state, "clerk_user", {})
    if not isinstance(clerk_user, dict):
        clerk_user = {}
    name = f"{clerk_user.get('first_name', '')} {clerk_user.get('last_name', '')}".strip()

    try:
        # Use upsert to eliminate TOCTOU race conditions
        record = {
            "name": name or "",
            "exam_type": payload.exam_type,
            "exam_date": payload.exam_date,
            "weak_subjects": weak_array,
            "mode": payload.mode,
            "guardian_contact": payload.guardian_contact,
            "preferred_platforms": preferred_platforms,
            "whatsapp_number": whatsapp_number,
            "discord_user_id": discord_user_id,
            "telegram_chat_id": telegram_chat_id,
            "schedule_locked": payload.schedule_locked if payload.schedule_locked is not None else False,
            "daily_schedule": daily_schedule,
            "setup_complete": payload.setup_complete if payload.setup_complete is not None else True,
        }
        if payload.country:
            record["country"] = payload.country
            record["country_code"] = payload.country_code or payload.country
            record["isd_code"] = payload.isd_code or "+91"

        # Add optional fields only if provided
        if payload.parent_email:
            record["guardian_email"] = payload.parent_email
        if payload.student_email:
            record["student_email"] = payload.student_email

        # Check if student exists to track edits
        existing = await sb_select("students", {"clerk_user_id": clerk_id})
        is_edit = len(existing) > 0
        edit_count = 0
        awarded_first_setup = False

        if is_edit:
            old_data = existing[0]
            # ... existing edit limit logic ...
            try:
                edit_count = int(old_data.get("setup_edit_count") or 0)
            except (ValueError, TypeError):
                edit_count = 0

            last_edit = str(old_data.get("last_edit_date") or "")
            from datetime import date as dt_date
            if last_edit != str(dt_date.today()):
                edit_count = 0

            if edit_count >= 100:
                raise HTTPException(status_code=429, detail="Edit limit reached (100/day). Try again tomorrow.")

            record["setup_edit_count"] = edit_count + 1
            record["last_edit_date"] = str(dt_date.today())
        else:
            # NEW USER: Award first-time setup reward
            record["setup_reward_claimed"] = True
            record["xp_bonus"] = 100 # 100 XP for completing setup
            awarded_first_setup = True

        # Save ...
        if existing:
            await sb_update("students", record, {"clerk_user_id": clerk_id})
            # ... existing clearing stale tasks logic ...
        else:
            await sb_insert("students", {"clerk_user_id": clerk_id, **record})

        # ... existing notifications logic ...
        
        return {
            "success": True, 
            "message": "Profile saved.",
            "first_setup": awarded_first_setup,
            "xp_earned": 100 if awarded_first_setup else 0
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Setup failed for {clerk_id}: {e}")
        raise HTTPException(status_code=500, detail="Setup failed. Please try again.")
