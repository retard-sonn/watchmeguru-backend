"""
AI Schedule Generation endpoint.
Receives exam + focus subjects + user's natural language preferences
and returns a structured 7-day schedule using Gemini.
"""

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.services.ai_core import generate_schedule_from_prompt
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


class ScheduleRequest(BaseModel):
    exam_type: str
    focus_subjects: Optional[str] = ""
    user_prompt: str


@router.post("/generate-schedule")
async def generate_schedule(request: Request, payload: ScheduleRequest):
    """Generate a personalised weekly schedule using Gemini."""
    try:
        schedule = await generate_schedule_from_prompt(
            exam_type=payload.exam_type,
            focus_subjects=payload.focus_subjects or "",
            user_prompt=payload.user_prompt,
        )
        return {"success": True, "schedule": schedule}
    except Exception as e:
        logger.error(f"Schedule generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
