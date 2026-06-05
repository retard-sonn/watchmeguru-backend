"""
Verify Router — The Lightning Review Engine
Generates 3 rapid-fire MCQs using Gemini to verify a study session.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
import instructor
from google import genai
from google.genai import types
from app.core.config import get_settings
from typing import List
import logging

router = APIRouter(tags=["Verify"])
settings = get_settings()
logger = logging.getLogger(__name__)

client = genai.Client(api_key=settings.gemini_api_key)

class VerifyRequest(BaseModel):
    subject: str
    topic: str = ""

class Question(BaseModel):
    q: str = Field(description="The question text")
    options: List[str] = Field(description="Exactly 4 distinct options")
    answer: int = Field(description="The index (0-3) of the correct option")

class LightningReview(BaseModel):
    questions: List[Question] = Field(description="Exactly 3 questions")

@router.post("/verify/lightning-quiz", response_model=LightningReview)
async def generate_lightning_quiz(req: VerifyRequest):
    """
    Generates 3 rapid-fire MCQs to verify that the student actually studied the topic.
    """
    prompt = f"The student just finished studying '{req.subject}'"
    if req.topic:
        prompt += f", specifically focusing on '{req.topic}'."
    prompt += " Generate exactly 3 challenging but fair multiple-choice questions to verify their understanding. Ensure there are exactly 4 options per question. Return ONLY raw JSON matching the schema."

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=LightningReview,
            ),
        )
        return response.parsed
    except Exception as e:
        logger.error(f"Gemini generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate review: {e}")
