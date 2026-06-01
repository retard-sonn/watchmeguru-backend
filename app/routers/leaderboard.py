"""
Leaderboard Router — global and country-specific rankings.
XP is verified server-side from Supabase to prevent cheating.
"""
from fastapi import APIRouter, Request, HTTPException, Query
from app.core.supabase_client import sb_select
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/global")
async def get_global_leaderboard(request: Request, limit: int = Query(default=50, ge=1, le=100)):
    """Global leaderboard — top students by XP (server-verified)."""
    try:
        students = await sb_select("students", raw_filters={
            "order": "tasks_completed.desc",
            "limit": str(limit),
        })

        rankings = []
        for i, s in enumerate(students):
            tasks = int(s.get("tasks_completed") or 0)
            hours = float(s.get("study_hours") or 0)
            streak = int(s.get("day_streak") or 0)
            xp = tasks * 50 + hours * 30 + streak * 10

            rankings.append({
                "rank": i + 1,
                "name": s.get("name", "Student"),
                "level": min(30, xp // 500 + 1),
                "xp": xp,
                "streak": streak,
                "country": s.get("country") or s.get("country_code") or "IN",
                "exam": s.get("exam_type", ""),
            })

        return {"leaderboard": rankings}

    except Exception as e:
        logger.exception(f"Leaderboard failed: {e}")
        raise HTTPException(status_code=500, detail="Leaderboard unavailable")


@router.get("/country/{country_code}")
async def get_country_leaderboard(country_code: str, limit: int = Query(default=50, ge=1, le=100)):
    """Country-specific leaderboard."""
    try:
        students = await sb_select("students", filters={"country_code": country_code}, raw_filters={
            "order": "tasks_completed.desc",
            "limit": str(limit),
        })

        # Also try country field
        if not students:
            students = await sb_select("students", filters={"country": country_code}, raw_filters={
                "order": "tasks_completed.desc",
                "limit": str(limit),
            })

        rankings = []
        for i, s in enumerate(students):
            tasks = int(s.get("tasks_completed") or 0)
            hours = float(s.get("study_hours") or 0)
            streak = int(s.get("day_streak") or 0)
            xp = tasks * 50 + hours * 30 + streak * 10

            rankings.append({
                "rank": i + 1,
                "name": s.get("name", "Student"),
                "level": min(30, xp // 500 + 1),
                "xp": xp,
                "streak": streak,
                "country": s.get("country") or country_code,
                "exam": s.get("exam_type", ""),
            })

        return {"leaderboard": rankings, "country": country_code}

    except Exception as e:
        logger.exception(f"Country leaderboard failed: {e}")
        raise HTTPException(status_code=500, detail="Leaderboard unavailable")
