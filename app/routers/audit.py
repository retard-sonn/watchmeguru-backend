"""
Audit Router — for logging user actions and telemetry.
"""
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Any, Optional
from app.core.supabase_client import sb_select, sb_insert
import logging

router = APIRouter(tags=["Audit"])
logger = logging.getLogger(__name__)

class AuditEvent(BaseModel):
    event_type: str
    event_data: Optional[Any] = {}

@router.post("/log")
async def log_audit_event(request: Request, payload: AuditEvent):
    clerk_id = getattr(request.state, "clerk_user_id", None)
    if not clerk_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        # Get internal student_id
        students = await sb_select("students", {"clerk_user_id": clerk_id})
        if not students:
            # Maybe the user is in setup, we log without student_id or skip
            student_id = None
        else:
            student_id = students[0]["id"]

        record = {
            "student_id": student_id,
            "event_type": payload.event_type,
            "event_data": payload.event_data,
        }
        await sb_insert("audit_logs", record)
        return {"success": True}
    except Exception as e:
        logger.error(f"Failed to log audit event: {e}")
        # We don't want to crash the frontend if logging fails
        return {"success": False, "error": str(e)}
