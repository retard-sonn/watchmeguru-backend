"""
Twilio WhatsApp Service
Sends WhatsApp messages via the Twilio sandbox / production number.
"""
import logging
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def get_twilio_client():
    from twilio.rest import Client
    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        raise RuntimeError("Twilio credentials not configured in .env")
    return Client(settings.twilio_account_sid, settings.twilio_auth_token)


def format_whatsapp_number(number: str) -> str:
    """Ensure number is in whatsapp:+1234567890 format."""
    if not number:
        return ""
    number = number.strip().replace(" ", "").replace("-", "")
    if not number.startswith("+"):
        number = "+" + number
    if number.startswith("whatsapp:"):
        return number
    return f"whatsapp:{number}"


async def send_whatsapp(to: str, body: str) -> dict:
    """
    Send a WhatsApp message via Twilio.
    'to' should be the student's phone number e.g. '+919876543210'
    """
    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        logger.warning(f"[MOCK WhatsApp] → {to}: {body}")
        return {"status": "mocked", "to": to}

    try:
        client = get_twilio_client()
        from_number = format_whatsapp_number(settings.twilio_whatsapp_number)
        to_number = format_whatsapp_number(to)

        message = client.messages.create(
            body=body,
            from_=from_number,
            to=to_number,
        )
        logger.info(f"WhatsApp sent to {to}: SID={message.sid}")
        return {"status": "sent", "sid": message.sid, "to": to}
    except Exception as e:
        logger.error(f"Twilio send failed to {to}: {e}")
        raise


async def send_kickstart_message(student_name: str, to: str, block_label: str, block_hours: float) -> dict:
    """Send the Beast Prompt kickstart message to start a study session."""
    body = (
        f"⏱️ *{block_label} session starting now.*\n\n"
        f"You have *{block_hours}h* locked in. I'm watching, {student_name or 'student'}.\n\n"
        f"When you're done — send me a *photo of your notes or solved problems*. "
        f"No photo = session not counted. Let's go. 🎯"
    )
    return await send_whatsapp(to, body)
