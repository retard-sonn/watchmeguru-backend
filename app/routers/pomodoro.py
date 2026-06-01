"""
Pomodoro Session Router
Handles start/complete notifications via WhatsApp.
After completion, triggers quiz generation and tracks results.
"""
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging
from datetime import datetime, timezone

from app.core.supabase_client import sb_select, sb_insert, sb_update
from app.services.twilio_service import send_whatsapp

router = APIRouter()
logger = logging.getLogger(__name__)


class PomodoroStartRequest(BaseModel):
    subject: str
    block_label: str
    start_time: str  # e.g. "6:00 PM"
    duration_hours: float = 1.0


class PomodoroCompleteRequest(BaseModel):
    subject: str
    block_label: str
    duration_minutes: int = 25


class QuizAnswerRequest(BaseModel):
    quiz_id: str
    answers: list[str]  # Student's answers in order


@router.post("/pomodoro/start")
async def pomodoro_start(request: Request, payload: PomodoroStartRequest):
    """Notify student via WhatsApp that a study session has started."""
    clerk_id = getattr(request.state, "clerk_user_id", None)
    if not clerk_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    students = await sb_select("students", {"clerk_user_id": clerk_id})
    if not students:
        raise HTTPException(status_code=404, detail="Student not found")

    student = students[0]
    whatsapp = student.get("whatsapp_number")
    student_name = student.get("name") or "Student"

    if whatsapp:
        msg = (
            f"⏱️ *Session Started!*\n\n"
            f"📚 *{payload.block_label}* — {payload.subject}\n"
            f"🕐 Started at: {payload.start_time}\n"
            f"⏳ Duration: {payload.duration_hours}h\n\n"
            f"Stay focused, {student_name}! I'll check in when you're done. 💪\n\n"
            f"*Tip:* Keep your phone away and focus on your books."
        )
        try:
            await send_whatsapp(whatsapp, msg)
            logger.info(f"Pomodoro start notification sent to {student_name}")
        except Exception as e:
            logger.error(f"Failed to send pomodoro start WhatsApp: {e}")

    return {"success": True, "message": "Session started — notification sent"}


@router.post("/pomodoro/complete")
async def pomodoro_complete(request: Request, payload: PomodoroCompleteRequest):
    """Notify student via WhatsApp that session is complete and ask for proof photo."""
    clerk_id = getattr(request.state, "clerk_user_id", None)
    if not clerk_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    students = await sb_select("students", {"clerk_user_id": clerk_id})
    if not students:
        raise HTTPException(status_code=404, detail="Student not found")

    student = students[0]
    student_id = student["id"]
    whatsapp = student.get("whatsapp_number")
    student_name = student.get("name") or "Student"

    # Record the session in daily_activity
    today = datetime.now(timezone.utc).date().isoformat()
    try:
        existing = await sb_select("daily_activity", {"student_id": student_id, "date": today})
        if existing:
            await sb_update("daily_activity", {
                "tasks_completed": (existing[0].get("tasks_completed") or 0) + 1,
                "study_hours": float(existing[0].get("study_hours") or 0) + payload.duration_minutes / 60.0,
            }, {"student_id": student_id, "date": today})
        else:
            await sb_insert("daily_activity", {
                "student_id": student_id,
                "date": today,
                "study_hours": payload.duration_minutes / 60.0,
                "tasks_completed": 1,
                "tasks_total": 1,
            })
    except Exception as e:
        logger.warning(f"Failed to record daily activity: {e}")

    # Generate a quiz for this session
    quiz_id = None
    try:
        quiz_result = await sb_insert("quizzes", {
            "student_id": student_id,
            "question": f"Quiz for {payload.subject} — {payload.block_label}",
            "expected_answer": "",
        })
        if quiz_result:
            quiz_id = quiz_result[0]["id"]
    except Exception as e:
        logger.warning(f"Failed to create quiz: {e}")

    if whatsapp:
        msg = (
            f"✅ *Session Complete!*\n\n"
            f"📚 *{payload.block_label}* — {payload.subject}\n"
            f"⏱️ Duration: {payload.duration_minutes}min\n"
            f"🎯 Great work, {student_name}!\n\n"
            f"📸 *Next Step:* Send me a *photo of your notes/work* from this session. "
            f"I'll verify your effort and generate a quick quiz based on what you studied.\n\n"
            f"No photo = session not counted. 📋"
        )
        try:
            await send_whatsapp(whatsapp, msg)
            logger.info(f"Pomodoro complete notification sent to {student_name}")
        except Exception as e:
            logger.error(f"Failed to send pomodoro complete WhatsApp: {e}")

    return {
        "success": True,
        "message": "Session complete — proof photo requested",
        "quiz_id": quiz_id,
    }
