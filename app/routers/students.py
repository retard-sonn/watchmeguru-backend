"""
Students Router
Endpoints for fetching and updating student data.
"""
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone, timedelta
from app.core.supabase_client import sb_select, sb_update, sb_insert
from app.core.config import get_settings
import logging
import secrets
import json

router = APIRouter(tags=["Students"])
logger = logging.getLogger(__name__)

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def get_today_short() -> str:
    return DAYS[datetime.now().weekday()]


@router.get("/me")
async def get_my_profile(request: Request):
    clerk_id = getattr(request.state, "clerk_user_id", None)
    if not clerk_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        students = await sb_select("students", {"clerk_user_id": clerk_id})
        if not students:
            return {"setup_complete": False}
        s = students[0]
        student_id = s["id"]

        # Daily login XP (+10 XP)
        last_active = s.get("last_active_at")
        now = datetime.now(timezone.utc)
        award_login_xp = False
        if not last_active:
            award_login_xp = True
        else:
            try:
                last_active_dt = datetime.fromisoformat(str(last_active).replace("Z", "+00:00"))
                if last_active_dt.date() < now.date():
                    award_login_xp = True
            except Exception:
                award_login_xp = True
        
        if award_login_xp:
            new_xp_bonus = (s.get("xp_bonus") or 0) + 10
            await sb_update("students", {
                "xp_bonus": new_xp_bonus,
                "last_active_at": now.isoformat()
            }, {"id": student_id})
            s["xp_bonus"] = new_xp_bonus
            s["last_active_at"] = now.isoformat()

        # Compute days_to_exam from exam_date
        days_to_exam = None
        raw_exam_date = s.get("exam_date")
        if raw_exam_date:
            try:
                exam_date = datetime.fromisoformat(str(raw_exam_date).replace("Z", "+00:00"))
                tz_aware = exam_date if exam_date.tzinfo else exam_date.replace(tzinfo=timezone.utc)
                delta = tz_aware - datetime.now(timezone.utc)
                days_to_exam = max(0, delta.days)
            except Exception:
                days_to_exam = None

        return {
            "setup_complete": True,
            "id": student_id,
            "name": s.get("name", ""),
            "exam_type": s.get("exam_type", ""),
            "exam_date": s.get("exam_date"),
            "days_to_exam": days_to_exam,
            "mode": s.get("mode"),
            "day_streak": s.get("day_streak", 0),
            "tasks_completed": s.get("tasks_completed", 0),
            "study_hours": float(s.get("study_hours", 0)),
            "xp_bonus": s.get("xp_bonus", 0),
            "quiz_accuracy": float(s.get("quiz_accuracy", 0)),
            "escalation_level": s.get("escalation_level", 0),
            "last_active_at": s.get("last_active_at"),
            "schedule_locked": s.get("schedule_locked", False),
            "daily_schedule": s.get("daily_schedule"),
            "preferred_platforms": s.get("preferred_platforms", []),
            "whatsapp_number": s.get("whatsapp_number"),
            "discord_user_id": s.get("discord_user_id"),
            "telegram_chat_id": s.get("telegram_chat_id"),
            "guardian_contact": s.get("guardian_contact"),
        }
    except Exception as e:
        logger.error(f"Error fetching profile: {e}")
        raise HTTPException(status_code=500, detail="Something went wrong. Please try again.")


@router.get("/me/schedule/today")
async def get_today_schedule(request: Request):
    """Return only today's study blocks from the student's daily_schedule."""
    clerk_id = getattr(request.state, "clerk_user_id", None)
    if not clerk_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        students = await sb_select("students", {"clerk_user_id": clerk_id})
        if not students:
            return {"today": None, "blocks": []}
        s = students[0]
        daily_schedule = s.get("daily_schedule")
        if not daily_schedule:
            return {"today": None, "blocks": [], "message": "No schedule yet. Generate one in Setup."}

        # Defensive: handle JSON strings (if DB returns text instead of jsonb)
        if isinstance(daily_schedule, str):
            import json as _json
            try: daily_schedule = _json.loads(daily_schedule)
            except: return {"today": None, "blocks": [], "message": "Schedule data is corrupted. Please regenerate."}

        schedule = daily_schedule if isinstance(daily_schedule, list) else daily_schedule.get("schedule", [])
        today_short = get_today_short()
        today_day = next((d for d in schedule if d.get("day") == today_short), None)

        if not today_day:
            return {"today": None, "blocks": [], "message": "No schedule for today."}

        return {
            "today": today_day,
            "blocks": today_day.get("blocks", []),
            "is_rest": today_day.get("isRest", False),
            "total_hours": today_day.get("totalHours", 0),
            "full_day": today_day.get("fullDay", ""),
        }
    except Exception as e:
        logger.error(f"Error fetching today's schedule: {e}")
        return {"today": None, "blocks": []}


@router.get("/me/tasks/today")
async def get_today_tasks(request: Request):
    clerk_id = getattr(request.state, "clerk_user_id", None)
    if not clerk_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        students = await sb_select("students", {"clerk_user_id": clerk_id})
        if not students:
            return {"tasks": []}
        student_id = students[0]["id"]
        tasks = await sb_select("tasks", {"student_id": student_id})
        # Filter in-memory to tasks due today (UTC calendar day matches server today)
        today_date = datetime.now(timezone.utc).date()
        formatted = []
        for t in tasks:
            due_str = t.get("due_date")
            is_today = False
            if due_str:
                try:
                    dt = datetime.fromisoformat(str(due_str).replace("Z", "+00:00"))
                    if dt.date() == today_date:
                        is_today = True
                except Exception:
                    is_today = True
            else:
                is_today = True
            
            if is_today:
                formatted.append({
                    "id": t["id"],
                    "title": t.get("title", ""),
                    "subject": t.get("subject", ""),
                    "status": t.get("status", "pending"),
                    "due_date": due_str or "",
                })
        return {"tasks": formatted}
    except Exception as e:
        logger.error(f"Error fetching tasks: {e}")
        return {"tasks": []}


@router.get("/me/interactions")
async def get_interactions(request: Request):
    clerk_id = getattr(request.state, "clerk_user_id", None)
    if not clerk_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        students = await sb_select("students", {"clerk_user_id": clerk_id})
        if not students:
            return {"interactions": []}
        student_id = students[0]["id"]
        rows = await sb_select("interactions", {"student_id": student_id})
        interactions = [{
            "time": r.get("created_at", "")[:16].replace("T", " "),
            "platform": r.get("platform", "dashboard"),
            "msg": r.get("content", ""),
            "type": "outbound" if r.get("direction") == "outbound" else "inbound",
        } for r in rows]
        return {"interactions": interactions}
    except Exception as e:
        return {"interactions": []}


@router.get("/me/activity/week")
async def get_week_activity(request: Request):
    clerk_id = getattr(request.state, "clerk_user_id", None)
    if not clerk_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        students = await sb_select("students", {"clerk_user_id": clerk_id})
        if not students:
            return {"days": []}
        student_id = students[0]["id"]
        activity_rows = await sb_select("daily_activity", {"student_id": student_id})
        # Build a 7-day map (Mon-Sun)
        day_map = {r.get("date", ""): r for r in activity_rows}
        days_output = []
        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        from datetime import date, timedelta
        today = date.today()
        # Last 7 days ending today
        for i in range(6, -1, -1):
            d = today - timedelta(days=i)
            row = day_map.get(d.isoformat(), {})
            days_output.append({
                "day": day_names[d.weekday()],
                "hrs": float(row.get("study_hours", 0)),
                "tasks": int(row.get("tasks_completed", 0)),
            })
        return {"days": days_output}
    except Exception as e:
        return {"days": []}


class IntegrationsPayload(BaseModel):
    whatsapp_number: str                    # Required
    discord_user_id: Optional[str] = None
    telegram_chat_id: Optional[str] = None


@router.post("/me/integrations")
async def update_integrations(request: Request, payload: IntegrationsPayload):
    """Save the student's social media handles to Supabase."""
    clerk_id = getattr(request.state, "clerk_user_id", None)
    if not clerk_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    if not payload.whatsapp_number:
        raise HTTPException(status_code=400, detail="WhatsApp number is required.")

    try:
        students = await sb_select("students", {"clerk_user_id": clerk_id})
        if not students:
            raise HTTPException(status_code=404, detail="Student profile not found. Complete setup first.")

        update_data = {
            "whatsapp_number": payload.whatsapp_number,
            "discord_user_id": payload.discord_user_id,
            "telegram_chat_id": payload.telegram_chat_id,
        }
        await sb_update("students", update_data, {"clerk_user_id": clerk_id})
        logger.info(f"Integrations updated for {clerk_id}")
        return {"success": True, "message": "Integrations saved successfully."}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update integrations: {e}")
        raise HTTPException(status_code=500, detail="Something went wrong. Please try again.")


# ─── Parent OTP Unlock ──────────────────────────────────────────

@router.post("/me/unlock/request")
async def request_unlock(request: Request):
    """Generate OTP, send to parent's WhatsApp, store in DB."""
    clerk_id = getattr(request.state, "clerk_user_id", None)
    if not clerk_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    students = await sb_select("students", {"clerk_user_id": clerk_id})
    if not students:
        raise HTTPException(status_code=404, detail="Student not found")
    student = students[0]

    guardian = student.get("guardian_contact")
    if not guardian:
        raise HTTPException(status_code=400, detail="No guardian contact set. Complete setup first.")

    otp = str(secrets.randbelow(900000) + 100000)

    await sb_update("students", {
        "unlock_otp": otp,
        "unlock_otp_expires": datetime.now(timezone.utc).isoformat(),
    }, {"id": student["id"]})

    try:
        from app.services.twilio_service import get_twilio_client, format_whatsapp_number
        settings = get_settings()
        twilio = get_twilio_client()
        twilio.messages.create(
            body=f"WatchMeGuru — Parent Verification Code: {otp}\n\nYour child is requesting to edit their locked schedule. Share this code with them to approve.\n\nCode expires in 10 minutes.",
            from_=format_whatsapp_number(settings.twilio_whatsapp_number),
            to=format_whatsapp_number(guardian),
        )
        logger.info(f"Unlock OTP sent to parent {guardian}")
        return {"success": True, "message": "OTP sent to parent's WhatsApp"}
    except Exception as e:
        logger.error(f"Failed to send OTP via Twilio: {e}")
        return {"success": True, "message": "OTP generated (dev mode)", "otp": otp}


@router.post("/me/unlock/verify")
async def verify_unlock(request: Request):
    """Verify OTP and unlock schedule for 24h."""
    clerk_id = getattr(request.state, "clerk_user_id", None)
    if not clerk_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    import json
    body = await request.json()
    otp = body.get("otp", "")

    students = await sb_select("students", {"clerk_user_id": clerk_id})
    if not students:
        raise HTTPException(status_code=404, detail="Student not found")
    student = students[0]

    stored_otp = student.get("unlock_otp")
    if not stored_otp or stored_otp != otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")

    expires_str = student.get("unlock_otp_expires")
    if expires_str:
        expires = datetime.fromisoformat(str(expires_str).replace("Z", "+00:00"))
        if (datetime.now(timezone.utc) - expires).total_seconds() > 600:
            raise HTTPException(status_code=400, detail="OTP expired. Request a new one.")

    unlock_until = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()

    await sb_update("students", {
        "schedule_locked": False,
        "unlock_until": unlock_until,
        "unlock_otp": None,
        "unlock_otp_expires": None,
    }, {"id": student["id"]})

    logger.info(f"Schedule unlocked for {clerk_id} until {unlock_until}")
    return {"success": True, "message": "Schedule unlocked for 24 hours", "unlock_until": unlock_until}
