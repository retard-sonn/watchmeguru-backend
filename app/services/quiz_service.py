"""
Quiz Service — AI-generated quizzes from study content.
Generates 10-question quizzes based on subject/topic.
"""
import json
import logging
from google import genai
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

WORKING_MODEL = "gemini-2.5-flash"

_client = None

def _get_client():
    global _client
    if _client is None:
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY not set")
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


async def generate_quiz(subject: str, topic: str = "", image_context: str = "") -> list[dict]:
    """
    Generate a 10-question quiz from a subject/topic.
    Optionally use image_context (OCR'd from student's proof photo) to tailor questions.
    Returns: [{question, options: [A,B,C,D], correct: "A", explanation: ""}, ...]
    """
    client = _get_client()
    context = f"\n\nContext from student's study notes: {image_context}" if image_context else ""

    prompt = f"""You are an exam preparation AI. Generate a 10-question multiple-choice quiz for the subject "{subject}".
Topic focus: {topic or "general concepts"}.{context}

Rules:
- 10 questions, each with exactly 4 options (A, B, C, D)
- Difficulty: 3 easy, 4 medium, 3 hard
- Include the correct answer and a 1-2 sentence explanation per question
- Questions must test understanding, not just memorization
- Format as valid JSON array

Return ONLY a JSON array, no markdown, no codeblocks:
[
  {{
    "question": "What is...?",
    "options": ["A) option1", "B) option2", "C) option3", "D) option4"],
    "correct": "A",
    "explanation": "Because...",
    "difficulty": "easy"
  }},
  ...
]"""

    try:
        response = client.models.generate_content(model=WORKING_MODEL, contents=prompt)
        text = response.text.strip()
        # Strip markdown if present
        if "```" in text:
            parts = text.split("```")
            for part in parts:
                if "[" in part:
                    text = part.lstrip("json").strip()
                    break
        quiz = json.loads(text)
        logger.info(f"Generated {len(quiz)} questions for {subject}")
        return quiz
    except Exception as e:
        logger.error(f"Quiz generation failed for {subject}: {e}")
        # Return fallback quiz
        return _fallback_quiz(subject)


def _fallback_quiz(subject: str) -> list[dict]:
    """Fallback quiz if AI generation fails."""
    return [
        {
            "question": f"What is the primary focus of {subject}?",
            "options": ["A) Theory", "B) Practice", "C) Both theory and practice", "D) Neither"],
            "correct": "C",
            "explanation": f"{subject} requires both theoretical understanding and practical application.",
            "difficulty": "easy"
        },
        {
            "question": f"Which study method is most effective for {subject}?",
            "options": ["A) Passive reading", "B) Active recall", "C) Highlighting", "D) Rereading"],
            "correct": "B",
            "explanation": "Active recall is proven to be the most effective study technique across subjects.",
            "difficulty": "easy"
        },
        {
            "question": f"How often should you review {subject} concepts?",
            "options": ["A) Once before exam", "B) Daily spaced repetition", "C) Weekly only", "D) Monthly"],
            "correct": "B",
            "explanation": "Daily spaced repetition helps move information from short-term to long-term memory.",
            "difficulty": "easy"
        },
    ]


def grade_quiz(quiz: list[dict], answers: dict[str, str]) -> dict:
    """
    Grade a quiz submission.
    answers: {"0": "A", "1": "B", ...}
    Returns: {score, total, percentage, results: [{correct, given, explanation}], passed}
    """
    total = len(quiz)
    correct_count = 0
    results = []

    for i, q in enumerate(quiz):
        given = answers.get(str(i), "")
        is_correct = given.upper() == q.get("correct", "").upper()
        if is_correct:
            correct_count += 1
        results.append({
            "question": q.get("question", ""),
            "given": given,
            "correct_answer": q.get("correct", ""),
            "explanation": q.get("explanation", ""),
            "is_correct": is_correct,
        })

    percentage = round((correct_count / total) * 100) if total > 0 else 0
    return {
        "score": correct_count,
        "total": total,
        "percentage": percentage,
        "passed": percentage >= 60,
        "results": results,
    }
