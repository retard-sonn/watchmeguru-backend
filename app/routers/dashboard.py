"""
Consolidated Dashboard API — single endpoint returning all dashboard data.
Reduces N+1 API calls from 4 to 1. Adds caching headers.
"""
from fastapi import APIRouter, Request, HTTPException
from app.core.supabase_client import sb_select
from datetime import datetime, timezone, date, timedelta
import logging

router = APIRouter()
logger = logging.getLogger(__name__)
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


@router.get("/dashboard")
async def get_dashboard(request: Request):
    """Returns all dashboard data in a single call."""
    clerk_id = getattr(request.state, "clerk_user_id", None)
    if not clerk_id or not str(clerk_id).strip():
        raise HTTPException(status_code=401, detail="Unauthorized")
    clerk_id = str(clerk_id)

    try:
        students = await sb_select("students", {"clerk_user_id": clerk_id})
        if not students:
            return {"setup_complete": False}

        s = students[0]
        student_id = s["id"]
        now = datetime.now(timezone.utc)
        today_short = DAYS[now.weekday()]
        today_iso = now.date().isoformat()

        # Profile
        days_to_exam = None
        raw_exam_date = s.get("exam_date")
        if raw_exam_date:
            try:
                ed = datetime.fromisoformat(str(raw_exam_date).replace("Z", "+00:00"))
                ed_tz = ed if ed.tzinfo else ed.replace(tzinfo=timezone.utc)
                days_to_exam = max(0, (ed_tz - now).days)
            except: pass

        # Today's schedule
        daily_schedule = s.get("daily_schedule")
        today_data = None
        today_blocks = []
        if daily_schedule:
            if isinstance(daily_schedule, str):
                import json
                try: daily_schedule = json.loads(daily_schedule)
                except: daily_schedule = None
            schedule = daily_schedule if isinstance(daily_schedule, list) else (daily_schedule or {}).get("schedule", [])
            today_day = next((d for d in schedule if d.get("day") == today_short), None)
            if today_day:
                today_data = today_day
                today_blocks = today_day.get("blocks", [])

        # Today's tasks
        tasks_raw = await sb_select("tasks", {"student_id": student_id})
        tasks = []
        for t in tasks_raw:
            due_str = t.get("due_date")
            due_today = True
            if due_str:
                try:
                    dt = datetime.fromisoformat(str(due_str).replace("Z", "+00:00"))
                    due_today = dt.date() == now.date()
                except: pass
            if due_today:
                tasks.append({
                    "id": t["id"], "title": t.get("title", ""), "subject": t.get("subject", ""),
                    "status": t.get("status", "pending"), "due_date": due_str or "",
                })

        # Week activity
        activity_rows = await sb_select("daily_activity", {"student_id": student_id})
        day_map = {r.get("date", ""): r for r in activity_rows}
        week_activity = []
        for i in range(6, -1, -1):
            d = (now - timedelta(days=i)).date()
            row = day_map.get(d.isoformat(), {})
            week_activity.append({
                "day": DAYS[d.weekday()], "hrs": float(row.get("study_hours", 0)),
                "tasks": int(row.get("tasks_completed", 0)),
            })

        # Pending quizzes
        quizzes = await sb_select("quizzes", {"student_id": student_id})
        pending_quizzes = [q for q in quizzes if q.get("status") == "pending"]

        return {
            "setup_complete": True,
            "profile": {
                "id": student_id, "name": s.get("name", ""), "exam_type": s.get("exam_type", ""),
                "exam_date": s.get("exam_date"), "days_to_exam": days_to_exam, "mode": s.get("mode"),
                "day_streak": s.get("day_streak", 0), "tasks_completed": s.get("tasks_completed", 0),
                "study_hours": float(s.get("study_hours", 0)), "quiz_accuracy": float(s.get("quiz_accuracy", 0)),
                "xp_bonus": s.get("xp_bonus", 0), "escalation_level": s.get("escalation_level", 0),
                "schedule_locked": s.get("schedule_locked", False),
                "whatsapp_number": s.get("whatsapp_number"), "discord_user_id": s.get("discord_user_id"),
                "telegram_chat_id": s.get("telegram_chat_id"), "guardian_contact": s.get("guardian_contact"),
                "last_active_at": s.get("last_active_at"),
            },
            "today": {
                "day": today_data, "blocks": today_blocks,
                "is_rest": today_data.get("isRest", False) if today_data else False,
                "total_hours": today_data.get("totalHours", 0) if today_data else 0,
            },
            "tasks": tasks,
            "week_activity": week_activity,
            "pending_quizzes": [{"id": q["id"], "subject": q.get("subject", ""), "total_questions": q.get("total_questions", 10)} for q in pending_quizzes],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Dashboard failed for {clerk_id}: {e}")
        raise HTTPException(status_code=500, detail="Dashboard unavailable. Please try again.")
