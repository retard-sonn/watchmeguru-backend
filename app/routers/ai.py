"""
AI endpoints:
  POST /generate-schedule  — generate weekly study schedule
  POST /verify-proof       — Gemini Vision proof-of-work check
"""

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.services.ai_core import generate_schedule_from_prompt
import logging
import base64
import json
import re
from google import genai
from google.genai import types
from app.core.config import get_settings

router = APIRouter()
logger = logging.getLogger(__name__)
settings = get_settings()

_vision_client = None

def _get_vision_client() -> genai.Client:
    global _vision_client
    if _vision_client is None:
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        _vision_client = genai.Client(api_key=settings.gemini_api_key)
    return _vision_client


class ScheduleRequest(BaseModel):
    exam_type: str
    focus_subjects: Optional[str] = ""
    user_prompt: str


class ProofVerifyRequest(BaseModel):
    image_data_url: str          # e.g. "data:image/jpeg;base64,/9j/..."
    task_title: str = ""
    subject: str = ""


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
        raise HTTPException(status_code=500, detail="Schedule generation failed. Please try again.")


@router.post("/verify-proof")
async def verify_proof(request: Request, payload: ProofVerifyRequest):
    """
    Use Gemini Vision to verify the student uploaded a genuine study proof.
    Returns:
      verdict: 'verified' | 'partial' | 'unrelated'
      feedback: short mentor sentence
      xp_awarded: int (50 if verified, 20 if partial, 0 if unrelated)
    """
    try:
        # Parse the data URL — extract mime type and raw bytes
        match = re.match(r"data:([^;]+);base64,(.+)", payload.image_data_url, re.DOTALL)
        if not match:
            raise HTTPException(status_code=400, detail="Invalid image_data_url format. Expected data:<mime>;base64,<data>")

        mime_type = match.group(1)
        raw_b64 = match.group(2).strip()

        # Validate it's actually decodable
        try:
            image_bytes = base64.b64decode(raw_b64)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid base64 image data.")

        task_context = ""
        if payload.subject:
            task_context += f"Subject: {payload.subject}. "
        if payload.task_title:
            task_context += f"Task: {payload.task_title}."

        prompt = f"""You are a strict but fair academic mentor verifying study proof submitted by a student.

Task context: {task_context or 'General study session'}

Examine the image carefully. Determine if it genuinely shows the student actively studying.

Accepted evidence includes:
- Handwritten notes, solved problems, or diagrams
- A textbook or study material open and actively being read
- A filled notebook page with subject-relevant content
- A whiteboard or digital notes with study content
- A screen showing educational content (lecture, Khan Academy, notes)

NOT accepted:
- Blank or empty paper/screen
- A photo of food, surroundings, or random objects
- A screenshot of Instagram, YouTube entertainment, games
- Completely unreadable or blurry image with no academic content

RESPOND ONLY with a JSON object — no markdown, no extra text:
{{
  "verdict": "verified" | "partial" | "unrelated",
  "feedback": "<one sentence, direct mentor tone, max 20 words>",
  "confidence": <0.0 to 1.0>
}}

Examples:
- "verdict": "verified", "feedback": "Clear handwritten notes on thermodynamics — solid deep work.", "confidence": 0.92
- "verdict": "partial", "feedback": "Study material visible but hard to confirm active engagement.", "confidence": 0.55
- "verdict": "unrelated", "feedback": "This is not study proof. Don't try to cheat the system.", "confidence": 0.97"""

        client = _get_vision_client()

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                types.Part.from_text(text=prompt),
            ]
        )

        raw = response.text.strip()

        # Strip markdown fences if model wraps
        if "```" in raw:
            parts = raw.split("```")
            for p in parts:
                if "{" in p:
                    raw = p.lstrip("json").strip()
                    break

        result = json.loads(raw)

        verdict = result.get("verdict", "unrelated")
        feedback = result.get("feedback", "Could not verify your proof. Try again.")
        confidence = float(result.get("confidence", 0.5))

        xp_map = {"verified": 50, "partial": 20, "unrelated": 0}
        xp_awarded = xp_map.get(verdict, 0)

        logger.info(f"Proof verify — verdict={verdict} confidence={confidence:.2f} task='{payload.task_title}'")

        return {
            "success": True,
            "verdict": verdict,
            "feedback": feedback,
            "confidence": confidence,
            "xp_awarded": xp_awarded,
        }

    except HTTPException:
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Gemini Vision returned non-JSON: {e}")
        raise HTTPException(status_code=500, detail="AI verification failed to parse. Please try again.")
    except Exception as e:
        logger.error(f"Proof verification failed: {e}")
        raise HTTPException(status_code=500, detail="Proof verification failed. Please try again.")

