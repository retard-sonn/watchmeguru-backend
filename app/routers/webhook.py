from fastapi import APIRouter, Request, HTTPException, Query, BackgroundTasks
from fastapi.responses import PlainTextResponse
from app.core.config import get_settings
from app.services.db_service import get_student_by_clerk_id, log_interaction
from app.services.ai_core import generate_conversational_reply
import logging

router = APIRouter(tags=["Webhooks"])
settings = get_settings()
logger = logging.getLogger(__name__)


@router.get("/whatsapp")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
):
    if hub_mode == "subscribe" and hub_verify_token == settings.whatsapp_verify_token:
        return PlainTextResponse(content=hub_challenge)
    raise HTTPException(status_code=403, detail="Verification token mismatch")


async def process_whatsapp_message(phone_number: str, text: str):
    # TODO: Look up by whatsapp_number when that field is populated
    logger.info(f"WhatsApp message from {phone_number}: {text}")
    # Placeholder: reply with AI
    try:
        reply = generate_conversational_reply("Student", "your exam", text)
        # TODO: send reply via Twilio
    except Exception as e:
        logger.error(f"Failed to generate reply: {e}")


@router.post("/whatsapp")
async def receive_whatsapp(request: Request, background_tasks: BackgroundTasks):
    body = await request.json()
    if body.get("object") == "whatsapp_business_account":
        for entry in body.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                for message in value.get("messages", []):
                    if message.get("type") == "text":
                        background_tasks.add_task(
                            process_whatsapp_message,
                            message.get("from"),
                            message["text"]["body"],
                        )
        return {"status": "ok"}
    raise HTTPException(status_code=404, detail="Not a WhatsApp event")
