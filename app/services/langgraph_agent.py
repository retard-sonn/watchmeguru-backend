"""
LangGraph Mentor Agent
State machine: Vision (Gemini) → Mentor (Groq Llama-3.3) → Tool Execution (DB mutation)
"""
import logging
import json
from typing import List, Any, Optional
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import StateGraph, START, END
from google import genai as google_genai
from app.core.config import get_settings
from app.core.supabase_client import sb_update

logger = logging.getLogger(__name__)
settings = get_settings()

# ─── LLM Clients ────────────────────────────────────────────
_llm = None
_gemini_client = None


def get_llm():
    global _llm
    if _llm is None:
        if not settings.groq_api_key:
            raise RuntimeError("GROQ_API_KEY not set")
        _llm = ChatGroq(model="llama-3.3-70b-versatile", api_key=settings.groq_api_key, temperature=0.15)
    return _llm


def get_gemini():
    global _gemini_client
    if _gemini_client is None:
        if not settings.gemini_api_key:
            return None
        _gemini_client = google_genai.Client(api_key=settings.gemini_api_key)
    return _gemini_client


# ─── Tool Definition ─────────────────────────────────────────
class MarkBlockCompletedParams(BaseModel):
    block_id: str = Field(description="The task ID of the study block to mark as completed in the database.")
    score: int = Field(description="The micro-quiz score out of 10 the student achieved.")
    feedback: str = Field(description="A one-sentence encouraging feedback message for the student.")


def mark_block_completed_tool(block_id: str, score: int, feedback: str) -> str:
    """Marks a task as completed in Supabase. Called when student passes the micro-quiz."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, sb_update("tasks", {"status": "completed"}, {"id": block_id}))
                future.result(timeout=5)
        else:
            loop.run_until_complete(sb_update("tasks", {"status": "completed"}, {"id": block_id}))
        logger.info(f"DB MUTATION: Task {block_id} → COMPLETED (score: {score}/10)")
        return f"Task {block_id} marked COMPLETED. Score: {score}/10. {feedback}"
    except Exception as e:
        logger.error(f"mark_block_completed failed: {e}")
        return f"Recorded score {score}/10. {feedback} (DB sync pending)"


# ─── State Schema ────────────────────────────────────────────
class AgentState(BaseModel):
    student_id: str
    student_name: str
    current_block: str
    platform: str
    messages: List[Any]
    image_url: Optional[str] = None
    vision_context: Optional[str] = None


# ─── Vision Node (Gemini Flash OCR) ──────────────────────────
def vision_node(state: AgentState) -> AgentState:
    """If an image_url is present, run Gemini Vision to extract academic concepts."""
    if not state.image_url:
        return state

    gemini = get_gemini()
    if not gemini:
        state.vision_context = "[Vision unavailable — Gemini key not set]"
        return state

    try:
        logger.info(f"Running Gemini Vision OCR on: {state.image_url}")
        prompt = (
            "You are an academic OCR and analysis engine. "
            "Analyze this image of a student's study notes or solved problems. "
            "Extract: (1) The key academic concepts, formulas, or topics visible. "
            "(2) The subject area. "
            "(3) Any specific equations, diagrams, or problem-solving steps visible. "
            "Be precise and concise. Return structured text, not markdown."
        )
        # Use URL-based image loading
        response = gemini.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                {"role": "user", "parts": [
                    {"text": prompt},
                    {"image_url": {"url": state.image_url}},
                ]}
            ]
        )
        state.vision_context = response.text.strip()
        logger.info(f"Vision extracted: {state.vision_context[:200]}")
    except Exception as e:
        logger.error(f"Gemini Vision error: {e}")
        state.vision_context = f"[Vision error: could not analyze image — {str(e)[:100]}]"

    return state


# ─── Mentor Node (Groq Llama-3.3) ────────────────────────────
def mentor_node(state: AgentState) -> AgentState:
    """Core conversational AI node with Beast Prompt and tool calling."""
    llm = get_llm()
    llm_with_tools = llm.bind_tools([mark_block_completed_tool])

    system_prompt = f"""You are "Guru" — an elite, stateful Academic Mentor AI for WatchMeGuru. You are NOT a standard chatbot. You are an execution engine monitoring, testing, and logging a student's daily study sessions.

DYNAMIC CONTEXT:
- Student Name: {state.student_name}
- Current Scheduled Block: {state.current_block}
- Platform: {state.platform}
- Vision Analysis of Uploaded Image: {state.vision_context if state.vision_context else "No image uploaded yet."}

CORE DIRECTIVES:

1. THE ACCOUNTABILITY LOOP
If the student is chatting casually during a scheduled block, abruptly redirect them back to their work. Be clinical and urgent, but deeply invested in their long-term success.

2. THE VERIFICATION LOOP (STRICT — DO NOT BYPASS)
You are FORBIDDEN from accepting "I'm done", "Finished", or "Did it" at face value. ALWAYS demand Proof of Work — a photo of their handwritten notes, a screenshot of solved problems, or a photograph of a worked equation. No exceptions. No shortcuts.

3. THE VISION-ASSESSMENT LOOP
When vision context is present (image was uploaded):
- Generate exactly 1-2 targeted micro-quiz questions derived STRICTLY from the concepts visible in the image.
- Wait for the student's answer. Evaluate it critically.
- If CORRECT → praise them genuinely AND call the `mark_block_completed_tool` to update the database.
- If INCORRECT → explain the gap specifically, refuse to mark complete, ask them to try again.

4. TOOL USE (MANDATORY)
When a student successfully passes the quiz, you MUST call `mark_block_completed_tool` with the task ID, score (out of 10), and feedback. The conversation is meaningless if you don't update the system.

COMMUNICATION RULES (Mobile Messaging App — Keep It Short):
- Maximum 3-4 sentences per message.
- Use **bold** for key terms and emphasis.
- Use bullet points for lists.
- Max 2 emojis per message.
- Tone: Clinical precision mixed with genuine care for their future.
- If the student fails to provide proof 3+ times: Shift to "Strict Accountability" mode — stop all pleasantries, cite mathematical reality of missing exam targets."""

    messages = [SystemMessage(content=system_prompt)] + state.messages
    response = llm_with_tools.invoke(messages)

    # Handle tool calls
    if hasattr(response, "tool_calls") and response.tool_calls:
        state.messages.append(response)
        for tool_call in response.tool_calls:
            if tool_call["name"] == "mark_block_completed_tool":
                args = tool_call["args"]
                result_str = mark_block_completed_tool(
                    block_id=args.get("block_id", ""),
                    score=args.get("score", 7),
                    feedback=args.get("feedback", "Well done."),
                )
                state.messages.append(ToolMessage(content=result_str, tool_call_id=tool_call["id"]))

        # Get final response after tool execution
        final = llm_with_tools.invoke([SystemMessage(content=system_prompt)] + state.messages)
        state.messages.append(final)
    else:
        state.messages.append(response)

    return state


# ─── Graph Construction ───────────────────────────────────────
_graph = None


def get_graph():
    global _graph
    if _graph is None:
        workflow = StateGraph(AgentState)
        workflow.add_node("vision", vision_node)
        workflow.add_node("mentor", mentor_node)
        workflow.add_edge(START, "vision")
        workflow.add_edge("vision", "mentor")
        workflow.add_edge("mentor", END)
        _graph = workflow.compile()
    return _graph


# ─── Entry Point ──────────────────────────────────────────────
async def process_omnichannel_message(
    student_id: str,
    student_name: str,
    message: str,
    platform: str,
    image_url: Optional[str] = None,
    current_block: str = "your scheduled study block",
) -> str:
    """Entry point called by Webhook handlers."""
    import asyncio
    initial_state = AgentState(
        student_id=student_id,
        student_name=student_name,
        current_block=current_block,
        platform=platform,
        messages=[HumanMessage(content=message)],
        image_url=image_url,
    )
    graph = get_graph()
    # LangGraph invoke is synchronous — run in thread pool to not block async loop
    loop = asyncio.get_event_loop()
    result_state = await loop.run_in_executor(None, graph.invoke, initial_state)

    last_message = result_state["messages"][-1]
    content = getattr(last_message, "content", str(last_message))
    return content if isinstance(content, str) else json.dumps(content)
