"""
Quiz Router — AI-generated quiz from study sessions.
"""
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from app.core.supabase_client import sb_select, sb_insert, sb_update
from app.services.quiz_service import generate_quiz, grade_quiz
from app.services.twilio_service import send_whatsapp
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


class GenerateQuizRequest(BaseModel):
    subject: str
    topic: Optional[str] = ""
    image_context: Optional[str] = ""


class SubmitQuizRequest(BaseModel):
    quiz_id: str
    answers: dict  # {"0": "A", "1": "B", ...}


@router.post("/generate")
async def generate_study_quiz(request: Request, payload: GenerateQuizRequest):
    """Generate a 10-question quiz based on subject and optional image context."""
    clerk_id = getattr(request.state, "clerk_user_id", None)
    if not clerk_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        students = await sb_select("students", {"clerk_user_id": clerk_id})
        if not students:
            raise HTTPException(status_code=404, detail="Student not found")
        student = students[0]

        quiz = await generate_quiz(payload.subject, payload.topic or "", payload.image_context or "")

        # Save quiz to database
        saved = await sb_insert("quizzes", {
            "student_id": student["id"],
            "subject": payload.subject,
            "topic": payload.topic or "",
            "questions": quiz,
            "status": "pending",
            "total_questions": len(quiz),
        })

        quiz_id = saved[0]["id"] if saved else None
        return {"success": True, "quiz_id": quiz_id, "questions": quiz, "total": len(quiz)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Quiz generation failed: {e}")
        raise HTTPException(status_code=500, detail="Something went wrong. Please try again.")


@router.post("/submit")
async def submit_quiz(request: Request, payload: SubmitQuizRequest):
    """Submit answers and get graded results."""
    clerk_id = getattr(request.state, "clerk_user_id", None)
    if not clerk_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        # Get the quiz
        quizzes = await sb_select("quizzes", {"id": payload.quiz_id})
        if not quizzes:
            raise HTTPException(status_code=404, detail="Quiz not found")
        quiz = quizzes[0]

        questions = quiz.get("questions", [])
        if isinstance(questions, str):
            import json
            questions = json.loads(questions)

        result = grade_quiz(questions, payload.answers)
        passed = result["passed"]

        # Update quiz record
        await sb_update("quizzes", {
            "student_answers": payload.answers,
            "score": result["score"],
            "total_questions": result["total"],
            "percentage": result["percentage"],
            "passed": passed,
            "status": "completed",
            "answered_at": "now()",
        }, {"id": payload.quiz_id})

        # Update student's quiz accuracy
        students = await sb_select("students", {"clerk_user_id": clerk_id})
        if students:
            student = students[0]
            old_accuracy = float(student.get("quiz_accuracy") or 0)
            old_completed = int(student.get("quizzes_completed") or 0)
            new_accuracy = round(((old_accuracy * old_completed) + result["percentage"]) / (old_completed + 1), 1)
            await sb_update("students", {
                "quiz_accuracy": new_accuracy,
                "quizzes_completed": old_completed + 1,
            }, {"id": student["id"]})

        return {
            "success": True,
            "passed": passed,
            "score": result["score"],
            "total": result["total"],
            "percentage": result["percentage"],
            "results": result["results"],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Quiz submission failed: {e}")
        raise HTTPException(status_code=500, detail="Something went wrong. Please try again.")


@router.get("/pending")
async def get_pending_quiz(request: Request):
    """Check if student has a pending (unanswered) quiz."""
    clerk_id = getattr(request.state, "clerk_user_id", None)
    if not clerk_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        students = await sb_select("students", {"clerk_user_id": clerk_id})
        if not students:
            return {"has_pending": False}

        quizzes = await sb_select("quizzes", {"student_id": students[0]["id"]})
        pending = [q for q in quizzes if q.get("status") == "pending"]

        return {
            "has_pending": len(pending) > 0,
            "pending_quizzes": [{
                "id": q["id"],
                "subject": q.get("subject", ""),
                "topic": q.get("topic", ""),
                "total_questions": q.get("total_questions", 10),
                "created_at": str(q.get("created_at", "")),
            } for q in pending],
        }
    except Exception as e:
        logger.error(f"Pending quiz check failed: {e}")
        return {"has_pending": False, "pending_quizzes": []}
