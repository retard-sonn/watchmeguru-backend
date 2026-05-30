"""
Omni-Channel Webhook Router
Handles inbound messages from Twilio (WhatsApp), Discord, and Telegram.
Returns HTTP 200 immediately and processes via BackgroundTasks to avoid timeout.
"""
from fastapi import APIRouter, Request, BackgroundTasks, Form, HTTPException
from fastapi.responses import PlainTextResponse
import logging

from app.core.supabase_client import sb_select
from app.services.langgraph_agent import process_omnichannel_message
from app.services.twilio_service import send_whatsapp
from app.services.db_service import log_interaction

router = APIRouter()
logger = logging.getLogger(__name__)


async def get_student_by_phone(phone: str) -> dict:
    """Look up a student by their WhatsApp number."""
    # Normalize the number — strip 'whatsapp:' prefix
    normalized = phone.replace("whatsapp:", "").strip()
    students = await sb_select("students", {"whatsapp_number": normalized})
    if not students:
        # Try with + prefix variations
        alt = normalized.lstrip("+")
        students = await sb_select("students", {"whatsapp_number": f"+{alt}"})
    return students[0] if students else {}


async def get_student_by_discord(discord_id: str) -> dict:
    students = await sb_select("students", {"discord_user_id": discord_id})
    return students[0] if students else {}


async def get_student_by_telegram(telegram_id: str) -> dict:
    students = await sb_select("students", {"telegram_chat_id": telegram_id})
    return students[0] if students else {}


async def get_current_block(student: dict) -> str:
    """Get the current scheduled study block label for the student."""
    from datetime import datetime
    daily_schedule = student.get("daily_schedule")
    if not daily_schedule:
        return "your study session"

    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    today_short = days[datetime.now().weekday()]
    schedule = daily_schedule if isinstance(daily_schedule, list) else daily_schedule.get("schedule", [])
    today_day = next((d for d in schedule if d.get("day") == today_short), None)

    if not today_day or today_day.get("isRest"):
        return "your rest day (take it easy!)"

    blocks = today_day.get("blocks", [])
    if not blocks:
        return "your study session"

    # Find the first non-completed block (simplified — no status tracking here)
    block = blocks[0]
    return f"{block.get('label', 'Study')} ({block.get('hours', 1)}h, starts {block.get('startTime', '')})"


async def handle_inbound_message(
    student: dict,
    message: str,
    platform: str,
    image_url: str | None = None,
    reply_to: str | None = None,
):
    """Core handler — runs in background to avoid webhook timeout."""
    try:
        student_id = student.get("id", "")
        student_name = student.get("name") or "Student"
        current_block = await get_current_block(student)

        # Log inbound
        if student_id:
            await log_interaction(
                student_id=student_id,
                direction="inbound",
                message_type="text",
                content=message,
                platform=platform,
            )

        # Run LangGraph agent
        reply = await process_omnichannel_message(
            student_id=student_id,
            student_name=student_name,
            message=message,
            platform=platform,
            image_url=image_url,
            current_block=current_block,
        )

        # Send reply back
        if platform == "whatsapp" and reply_to:
            await send_whatsapp(reply_to, reply)
        elif platform == "telegram" and reply_to:
            await _send_telegram_reply(reply_to, reply)
        elif platform == "discord" and reply_to:
            # Discord replies are handled by the interaction endpoint
            pass

        # Log outbound
        if student_id:
            await log_interaction(
                student_id=student_id,
                direction="outbound",
                message_type="text",
                content=reply,
                platform=platform,
            )

    except Exception as e:
        logger.error(f"handle_inbound_message error ({platform}): {e}")


async def _send_telegram_reply(chat_id: str, text: str):
    """Send a Telegram message."""
    from app.core.config import get_settings
    import httpx
    settings = get_settings()
    if not settings.telegram_bot_token:
        logger.warning(f"[MOCK Telegram] → {chat_id}: {text}")
        return
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    async with httpx.AsyncClient() as client:
        await client.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})


# ═══════════════════════════════════════════════════════════
# TWILIO WHATSAPP WEBHOOK
# ═══════════════════════════════════════════════════════════
@router.post("/twilio", response_class=PlainTextResponse)
async def twilio_webhook(
    background_tasks: BackgroundTasks,
    From: str = Form(...),
    Body: str = Form(""),
    MediaUrl0: str = Form(None),
    NumMedia: str = Form("0"),
):
    """Twilio WhatsApp inbound message webhook."""
    logger.info(f"Twilio inbound from {From}: {Body[:80]}")

    # Acknowledge immediately (Twilio requires fast response)
    try:
        student = await get_student_by_phone(From)
        if not student:
            logger.warning(f"No student found for WhatsApp number: {From}")
            # Still respond so Twilio doesn't retry
            return ""

        image_url = MediaUrl0 if int(NumMedia) > 0 else None
        background_tasks.add_task(
            handle_inbound_message,
            student=student,
            message=Body or "[image]",
            platform="whatsapp",
            image_url=image_url,
            reply_to=From.replace("whatsapp:", ""),
        )
    except Exception as e:
        logger.error(f"Twilio webhook error: {e}")

    return ""  # Empty TwiML response — we reply via Twilio API directly


# ═══════════════════════════════════════════════════════════
# TELEGRAM WEBHOOK
# ═══════════════════════════════════════════════════════════
@router.post("/telegram")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    """Telegram bot webhook."""
    try:
        data = await request.json()
        message = data.get("message") or data.get("edited_message", {})
        if not message:
            return {"ok": True}

        chat_id = str(message.get("chat", {}).get("id", ""))
        text = message.get("text", "")
        photo = message.get("photo")
        image_url = None

        if photo:
            # Get the largest photo file_id
            image_url = photo[-1].get("file_id") if photo else None
            text = message.get("caption", "") or "[image]"

        logger.info(f"Telegram inbound from {chat_id}: {text[:80]}")

        student = await get_student_by_telegram(chat_id)
        if not student:
            logger.warning(f"No student found for Telegram chat_id: {chat_id}")
            return {"ok": True}

        background_tasks.add_task(
            handle_inbound_message,
            student=student,
            message=text,
            platform="telegram",
            image_url=image_url,
            reply_to=chat_id,
        )
        return {"ok": True}
    except Exception as e:
        logger.error(f"Telegram webhook error: {e}")
        return {"ok": True}


# ═══════════════════════════════════════════════════════════
# DISCORD WEBHOOK (Interactions Endpoint)
# ═══════════════════════════════════════════════════════════
@router.post("/discord")
async def discord_webhook(request: Request, background_tasks: BackgroundTasks):
    """Discord interactions endpoint."""
    try:
        data = await request.json()
        interaction_type = data.get("type", 0)

        # Type 1 = PING — Discord sends this to verify the endpoint
        if interaction_type == 1:
            return {"type": 1}

        # Type 2 = APPLICATION_COMMAND or DM message
        user = data.get("member", {}).get("user") or data.get("user", {})
        discord_id = user.get("id", "")
        message_content = data.get("data", {}).get("options", [{}])[0].get("value", "") or \
                          data.get("content", "")

        logger.info(f"Discord inbound from {discord_id}: {message_content[:80]}")

        student = await get_student_by_discord(discord_id)
        if not student:
            return {"type": 4, "data": {"content": "I don't recognize you. Link your Discord in your WatchMeGuru dashboard first!"}}

        # Process in background, return ACK immediately
        background_tasks.add_task(
            handle_inbound_message,
            student=student,
            message=message_content,
            platform="discord",
            image_url=None,
            reply_to=discord_id,
        )

        return {
            "type": 4,
            "data": {"content": "⏳ Your mentor is thinking... reply coming shortly."}
        }
    except Exception as e:
        logger.error(f"Discord webhook error: {e}")
        return {"type": 1}
