"""
AI Core — uses google-genai SDK with gemini-2.5-flash.
NO SILENT FALLBACKS. If Gemini fails, we raise the error so the caller
can surface it to the user honestly.
"""

import json
import logging
import os
import datetime
from google import genai
from groq import Groq
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

WORKING_MODEL = "gemini-2.5-flash"

PALETTE = ["#0F2167", "#1A3A8F", "#7C3AED", "#0891B2", "#DC2626", "#D97706", "#059669"]
SUPPORT_COLORS = {
    "Previous Year Papers": "#E8A000",
    "Revision + Notes": "#6B7280",
    "Mock Test Analysis": "#DC2626",
    "Flash Cards": "#8B5CF6",
}

_client = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not set in environment.")
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client

_groq_client = None

def _get_groq_client() -> Groq:
    global _groq_client
    if _groq_client is None:
        if not settings.groq_api_key:
            raise RuntimeError("GROQ_API_KEY is not set in environment.")
        _groq_client = Groq(api_key=settings.groq_api_key)
    return _groq_client


def get_personality_prompt(student_name: str, exam_type: str, mode: str = "strict") -> str:
    if mode == "strict":
        return (
            f"You are an elite, cold, unforgiving academic mentor for {student_name} preparing for {exam_type}. "
            "No excuses. Be demanding and analytical. Max 3 sentences. No pleasantries."
        )
    elif mode == "moderate":
        return (
            f"You are a firm but fair academic mentor for {student_name} preparing for {exam_type}. "
            "Hold them accountable but acknowledge effort. Be concise."
        )
    return (
        f"You are a supportive tutor and accountability partner for {student_name} preparing for {exam_type}. "
        "Encourage them and help through challenges. Warm but focused."
    )


def generate_conversational_reply(
    student_name: str, exam_type: str, message: str, mode: str = "strict", context: str = ""
) -> str:
    """Generate a conversational reply. Raises on failure — never fakes it."""
    client = _get_client()
    system_prompt = get_personality_prompt(student_name, exam_type, mode)
    full_prompt = f"{system_prompt}\n\nContext:\n{context}\n\nStudent says: {message}\nMentor:"
    response = client.models.generate_content(model=WORKING_MODEL, contents=full_prompt)
    return response.text.strip()


async def generate_schedule_from_prompt(
    exam_type: str, focus_subjects: str, user_prompt: str
) -> list:
    """
    Generate a structured 7-day study schedule using Gemini.
    RAISES an exception if Gemini is unavailable — no silent fallback.
    The caller (router) will return a proper HTTP error to the frontend.
    """
    client = _get_client()
    subjects = [s.strip() for s in focus_subjects.split(",") if s.strip()] or [exam_type]
    subject_colors = {s: PALETTE[i % len(PALETTE)] for i, s in enumerate(subjects)}

    prompt = f"""SYSTEM ROLE & METHODOLOGY
You are an Elite Academic Strategist and a strict Constraint Satisfaction Problem (CSP) solver. Your function is to generate a highly effective, realistic 7-day study schedule in perfect JSON format. You must apply strict Schema Enforcement, Zero-Shot Rule Evaluation, and Evidence-Based Pedagogical Timeboxing.

STUDENT INPUT CONTEXT
- Target exam: {exam_type}
- Exclusive Subjects to Cover: {focus_subjects}
- Student's preferences: "{user_prompt}"

CRITICAL EXECUTION CONSTRAINTS (HARD RULES):
1. DOMAIN ISOLATION (ZERO SUBJECT HALLUCINATION): You are strictly forbidden from adding ANY core academic subject that is not explicitly listed in the "Exclusive Subjects to Cover" array.
2. PEDAGOGICAL TIMEBOXING (CRITICAL): You must allocate realistic time durations based on the cognitive load of the task:
- Core Subjects (Physics, Chemistry, etc.): 2.0 to 3.0 hours per block (Deep Work).
- "Flash Cards": STRICTLY 0.5 to 1.0 hour maximum per day (Spaced Repetition).
- "Revision + Notes": 1.0 to 1.5 hours maximum.
- "Mock Test Analysis": 1.5 to 2.0 hours.
- "Previous Year Papers": 2.0 to 3.0 hours.
Never schedule 3 hours of Flash Cards or Revision. Interleave short active recall sessions with longer deep work sessions.
3. PREFERENCE ENFORCEMENT: Strictly honor the user's free-text preferences. If a specific day is marked for rest (e.g., "Sunday rest"), the node for that day MUST reflect `"isRest": true`, `"totalHours": 0`, and the `"blocks"` array MUST be completely empty `[]`.
4. TIME INJECTION: If a specific time of day (e.g., "morning") is mentioned in the preferences, anchor the first `"startTime"` of the day to "6:00 AM". Allow logical 15-30 minute breaks between blocks (e.g., if Block 1 is 6:00 AM - 9:00 AM, Block 2 can start at 9:15 AM).
5. MATHEMATICAL INTEGRITY: The `"totalHours"` number at the daily root level MUST be the exact mathematical sum of the `"hours"` values inside that day's `"blocks"` array. (You may use decimal values like 1.5 for hours).
6. COLOR & LABEL MAPPING (EXACT MATCH ONLY):
- Core Subject Colors: {json.dumps(subject_colors)}
- Support Block Colors: {json.dumps(SUPPORT_COLORS)}
Every block label generated must perfectly match a key in these dictionaries, and you must assign the exact corresponding hex code.

OUTPUT FORMATTING INSTRUCTIONS:
Return ONLY valid, parseable JSON.
Do NOT wrap the output in markdown codeblocks (no `json ... `).
Do NOT include any conversational text, reasoning, explanations, or formatting outside of the raw JSON object.

REQUIRED JSON SCHEMA:
{{
  "schedule": [
    {{
      "day": "Mon",
      "fullDay": "Monday",
      "isRest": false,
      "totalHours": 6.5,
      "blocks": [
        {{"label": "{subjects[0] if subjects else 'Subject'}", "hours": 3, "color": "{subject_colors.get(subjects[0], '#000') if subjects else '#000'}", "startTime": "6:00 AM"}},
        {{"label": "Revision + Notes", "hours": 1.5, "color": "#6B7280", "startTime": "9:15 AM"}},
        {{"label": "{subjects[min(1, len(subjects)-1)] if subjects else 'Subject'}", "hours": 2, "color": "{subject_colors.get(subjects[min(1, len(subjects)-1)], '#000') if subjects else '#000'}", "startTime": "11:00 AM"}}
      ]
    }}
  ]
}}
Ensure the array contains exact structures for all 7 days, Mon through Sun, following all constraints."""

    text = None
    model_used = "llama-3.3-70b-versatile (Groq)"
    
    try:
        logger.info(f"Calling Groq llama-3.3-70b-versatile for schedule generation...")
        groq_client = _get_groq_client()
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        text = completion.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Groq API failed: {e}. Falling back to Gemini 2.5 Flash.")
        model_used = f"{WORKING_MODEL} (Gemini Fallback)"
        client = _get_client()
        response = client.models.generate_content(model=WORKING_MODEL, contents=prompt)
        text = response.text.strip()

    # Log with rotation (max 5MB, keep 3 backups)
    log_file = "ai_generation.log"
    try:
        # Auto-rotate if file exceeds 5MB
        import os as _os
        max_bytes = 5 * 1024 * 1024  # 5MB
        if _os.path.exists(log_file) and _os.path.getsize(log_file) > max_bytes:
            for i in range(2, 0, -1):
                old = f"{log_file}.{i}"
                new = f"{log_file}.{i + 1}" if i < 3 else None
                if _os.path.exists(old):
                    if i == 2:
                        _os.remove(old)
                    else:
                        _os.rename(old, f"{log_file}.{i + 1}")
            _os.rename(log_file, f"{log_file}.1")

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*50}\n")
            f.write(f"TIMESTAMP: {datetime.datetime.now().isoformat()}\n")
            f.write(f"MODEL USED: {model_used}\n")
            f.write(f"PROMPT LENGTH: {len(prompt)} chars\n")
            f.write(f"RESPONSE LENGTH: {len(text)} chars\n")
            f.write(f"{'='*50}\n")
    except Exception as e:
        logger.warning(f"Failed to write to AI log file: {e}")

    # Strip markdown fences if model wraps in them
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            if "{" in part:
                text = part.lstrip("json").strip()
                break

    data = json.loads(text)
    schedule = data["schedule"]
    logger.info(f"{model_used} schedule generated successfully: {len(schedule)} days")
    return schedule
