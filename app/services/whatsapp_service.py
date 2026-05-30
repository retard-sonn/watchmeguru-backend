import httpx
from app.core.config import get_settings

settings = get_settings()

async def send_whatsapp_message(to: str, message: str):
    """
    Send a plain text message via Meta WhatsApp Cloud API.
    """
    if not settings.whatsapp_token or not settings.whatsapp_phone_number_id:
        print(f"MOCK WhatsApp to {to}: {message}")
        return {"status": "mocked"}

    url = f"https://graph.facebook.com/v17.0/{settings.whatsapp_phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {settings.whatsapp_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": message}
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
