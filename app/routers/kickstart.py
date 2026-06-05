"""
Kickstart Router
POST /api/v1/kickstart/{block_index}
Triggers a study session for a specific block in today's schedule.
Creates a task row, sends WhatsApp message, logs interaction.
"""
from fastapi import APIRouter, Request, HTTPException, Query
from datetime import datetime, timezone
import logging

from app.core.supabase_client import sb_select, sb_insert, sb_update
from app.core.config import get_settings
from app.services.twilio_service import send_kickstart_message
from app.services.discord_service import send_discord_message
from app.services.telegram_service import send_telegram_message
from app.services.db_service import log_interaction

router = APIRouter()
logger = logging.getLogger(__name__)

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def get_today_short() -> str:
    return DAYS[datetime.now().weekday()]


@router.post("/kickstart/{block_index}")
async def kickstart_block(request: Request, block_index: int, platform: str = Query(default="whatsapp")):
    """
    Kicks off a specific study block for today.
    1. Looks up student and their daily_schedule
    2. Finds today's block at block_index
    3. Creates/updates a task row in 'tasks' table
    4. Sends kickstart message via selected platform
    5. Logs the interaction
    """
    clerk_id = getattr(request.state, "clerk_user_id", None)
    if not clerk_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    students = await sb_select("students", {"clerk_user_id": clerk_id})
    if not students:
        raise HTTPException(status_code=404, detail="Student profile not found. Complete setup first.")
    student = students[0]
    student_id = student["id"]
    student_name = student.get("name") or "Student"

    # Determine target handle based on platform
    whatsapp_number = student.get("whatsapp_number")
    discord_user_id = student.get("discord_user_id")
    telegram_chat_id = student.get("telegram_chat_id")

    daily_schedule = student.get("daily_schedule")
    if not daily_schedule:
        raise HTTPException(status_code=400, detail="No schedule found. Generate your AI schedule first.")

    schedule = daily_schedule if isinstance(daily_schedule, list) else daily_schedule.get("schedule", [])
    today_short = get_today_short()
    today_day = next((d for d in schedule if d.get("day") == today_short), None)

    if not today_day or today_day.get("isRest"):
        raise HTTPException(status_code=400, detail="Today is a rest day. No blocks to kickstart.")

    blocks = today_day.get("blocks", [])
    if block_index >= len(blocks):
        raise HTTPException(status_code=404, detail=f"Block index {block_index} not found for today.")

    block = blocks[block_index]
    block_label = block.get("label", "Study Session")
    block_hours = block.get("hours", 1)
    block_start = block.get("startTime", "")

    # Create task row
    task_data = {
        "student_id": student_id,
        "title": f"{block_label} — {today_day.get('fullDay', today_short)}",
        "subject": block_label,
        "status": "in_progress",
        "due_date": datetime.now(timezone.utc).isoformat(),
        "description": f"Block {block_index + 1}: {block_hours}h starting {block_start}",
    }
    try:
        task_result = await sb_insert("tasks", task_data)
        task_id = task_result[0]["id"] if task_result else None
    except Exception as e:
        logger.error(f"Failed to create task: {e}")
        task_id = None

    # Calculate and update streak and last_active_at on kickstart
    try:
        current_streak = student.get("day_streak") or 0
        last_active = student.get("last_active_at")
        now = datetime.now(timezone.utc)
        
        new_streak = current_streak
        if not last_active:
            new_streak = 1
        else:
            try:
                last_active_dt = datetime.fromisoformat(str(last_active).replace("Z", "+00:00"))
                delta = now.date() - last_active_dt.date()
                if delta.days == 1:
                    new_streak = current_streak + 1
                elif delta.days > 1:
                    new_streak = 1
                # if delta.days == 0, streak stays the same
            except Exception as pe:
                logger.error(f"Failed to parse last_active_at: {pe}")
                new_streak = max(1, current_streak)
                
        await sb_update("students", {
            "day_streak": new_streak,
            "last_active_at": now.isoformat()
        }, {"id": student_id})
        logger.info(f"Updated student {student_id} streak to {new_streak}")
    except Exception as se:
        logger.error(f"Failed to update student streak: {se}")

    # Send message via selected platform
    msg_sent = False
    kickstart_msg = f"🚀 Your study session for *{block_label}* has started!\n\n⏱ Duration: {block_hours}h\n📅 Time: {block_start}\n\nStay focused, {student_name} — your mentor is watching."

    if platform == "whatsapp" and whatsapp_number:
        try:
            await send_kickstart_message(student_name, whatsapp_number, block_label, block_hours)
            msg_sent = True
        except Exception as e:
            logger.error(f"Kickstart WhatsApp failed: {e}")

    elif platform == "discord" and discord_user_id:
        try:
            msg_sent = await send_discord_message(discord_user_id, kickstart_msg)
        except Exception as e:
            logger.error(f"Kickstart Discord failed: {e}")

    elif platform == "telegram" and telegram_chat_id:
        try:
            msg_sent = await send_telegram_message(telegram_chat_id, kickstart_msg)
        except Exception as e:
            logger.error(f"Kickstart Telegram failed: {e}")

    # Log interaction
    try:
        await log_interaction(
            student_id=student_id,
            direction="outbound",
            message_type="kickstart",
            content=f"Kickstarted: {block_label} ({block_hours}h)",
            platform=platform if msg_sent else "dashboard",
        )
        # Audit Log
        await sb_insert("audit_logs", {
            "student_id": student_id,
            "event_type": "SESSION_STARTED",
            "event_data": {"block": block_label, "hours": block_hours, "platform": platform}
        })
    except Exception as e:
        logger.error(f"Failed to log interaction/audit: {e}")

    platform_emoji = {"whatsapp": "💬", "discord": "🎮", "telegram": "✈️"}
    return {
        "success": True,
        "block": block_label,
        "hours": block_hours,
        "task_id": task_id,
        "message_sent": msg_sent,
        "platform": platform,
        "message": f"'{block_label}' session started. {'Sent via ' + platform_emoji.get(platform, platform) if msg_sent else 'Platform not connected — session in dashboard only.'}",
    }


from pydantic import BaseModel

class CompleteTaskRequest(BaseModel):
    success: bool = True
    hours: float = 0.0

@router.post("/students/me/tasks/{task_id}/complete")
async def complete_task(request: Request, task_id: str, payload: CompleteTaskRequest):
    """Mark a task as completed. Only awards stats if success=True (verified)."""
    clerk_id = getattr(request.state, "clerk_user_id", None)
    if not clerk_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    students = await sb_select("students", {"clerk_user_id": clerk_id})
    if not students:
        raise HTTPException(status_code=404, detail="Student not found")
    student = students[0]
    student_id = student["id"]

    try:
        tasks = await sb_select("tasks", {"id": task_id, "student_id": student_id})
        if not tasks:
            raise HTTPException(status_code=404, detail="Task not found")
        task = tasks[0]

        if task.get("status") == "completed":
            return {"success": True, "message": "Task already completed"}

        # Mark as completed regardless, but stats depend on success
        new_status = "completed" if payload.success else "unverified"
        await sb_update("tasks", {"status": new_status}, {"id": task_id, "student_id": student_id})
        
        hours = payload.hours
        subject = task.get("subject") or task.get("title", "Study")

        if payload.success and hours > 0:
            today = datetime.now(timezone.utc).date().isoformat()
            existing_activity = await sb_select("daily_activity", {"student_id": student_id, "date": today})
            
            # 1. Update daily activity
            if existing_activity:
                new_count = (existing_activity[0].get("tasks_completed") or 0) + 1
                new_hours = float(existing_activity[0].get("study_hours") or 0) + hours
                await sb_update("daily_activity", {
                    "tasks_completed": new_count,
                    "study_hours": new_hours
                }, {"student_id": student_id, "date": today})
            else:
                await sb_insert("daily_activity", {
                    "student_id": student_id, "date": today,
                    "study_hours": hours, "tasks_completed": 1, "tasks_total": 1
                })
            
            # 2. Update Student Stats & Progression
            # XP = Hours * 50
            earned_xp = int(hours * 50)
            old_study_hours = float(student.get("study_hours") or 0)
            new_study_hours = old_study_hours + hours
            
            # Logic for Level Up (Syncing with frontend lib/levelSystem.ts logic)
            def get_level(h):
                total_xp = int(h * 50)
                # Matches lib/levelSystem.ts thresholds
                if total_xp >= 18000: return 10
                if total_xp >= 13500: return 9
                if total_xp >= 10000: return 8
                if total_xp >= 7300: return 7
                if total_xp >= 5200: return 6
                if total_xp >= 3500: return 5
                if total_xp >= 2200: return 4
                if total_xp >= 1200: return 3
                if total_xp >= 500: return 2
                return 1

            old_level = get_level(old_study_hours)
            new_level = get_level(new_study_hours)
            did_level_up = new_level > old_level

            update_fields = {
                "tasks_completed": (student.get("tasks_completed") or 0) + 1,
                "study_hours": new_study_hours,
                "last_active_at": datetime.now(timezone.utc).isoformat(),
            }
            
            # Note: These columns might not exist yet, we catch errors silently
            # in a real app we'd have run migrations.
            try: update_fields["level"] = new_level
            except: pass
            
            await sb_update("students", update_fields, {"id": student_id})

            return {
                "success": True, 
                "task_id": task_id, 
                "verified": True, 
                "xp_earned": earned_xp,
                "new_level": new_level,
                "did_level_up": did_level_up
            }

        return {"success": True, "task_id": task_id, "verified": payload.success}
    except Exception as e:
        logger.error(f"Failed to complete task {task_id}: {e}")
        raise HTTPException(status_code=500, detail="Something went wrong. Please try again.")
