"""
Gamification Router — persist XP, levels, achievements, streaks to Supabase.
"""
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from app.core.supabase_client import sb_select, sb_update, sb_upsert
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


class AchievementUpdate(BaseModel):
    achievement_ids: List[str]  # list of achieved milestone keys


@router.get("/stats")
async def get_gamification_stats(request: Request):
    """Return consolidated gamification stats for the student."""
    clerk_id = getattr(request.state, "clerk_user_id", None)
    if not clerk_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    students = await sb_select("students", {"clerk_user_id": clerk_id})
    if not students:
        return {"setup_complete": False}

    s = students[0]
    day_streak = s.get("day_streak") or 0
    tasks_completed = s.get("tasks_completed") or 0
    study_hours = float(s.get("study_hours") or 0)
    quiz_accuracy = float(s.get("quiz_accuracy") or 0)
    xp = tasks_completed * 50 + int(study_hours * 30) + day_streak * 10
    level = max(1, (xp // 500) + 1)

    # Fetch achievements from dedicated table if exists, else fallback
    achievements = []
    try:
        ach_rows = await sb_select("achievements", {"student_id": s["id"]})
        achievements = [a.get("achievement_id") for a in ach_rows] if ach_rows else []
    except Exception:
        achievements = []

    return {
        "xp": xp,
        "level": level,
        "day_streak": day_streak,
        "tasks_completed": tasks_completed,
        "study_hours": study_hours,
        "quiz_accuracy": quiz_accuracy,
        "achievements": achievements,
    }


@router.post("/achievements/sync")
async def sync_achievements(request: Request, payload: AchievementUpdate):
    """Save unlocked achievements to Supabase."""
    clerk_id = getattr(request.state, "clerk_user_id", None)
    if not clerk_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    students = await sb_select("students", {"clerk_user_id": clerk_id})
    if not students:
        raise HTTPException(status_code=404, detail="Student not found")
    student = students[0]

    saved = 0
    for ach_id in payload.achievement_ids:
        try:
            await sb_upsert("achievements", {
                "student_id": student["id"],
                "achievement_id": ach_id,
                "unlocked_at": "now()",
            })
            saved += 1
        except Exception as e:
            logger.warning(f"Failed to save achievement {ach_id}: {e}")

    return {"success": True, "saved": saved}
