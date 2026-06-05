"""Test Twilio WhatsApp send directly."""
import os, asyncio
from dotenv import load_dotenv
load_dotenv()

async def test():
    from twilio.rest import Client
    sid = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    from_num = os.getenv("TWILIO_WHATSAPP_NUMBER")

    print(f"SID: {sid[:10]}...")
    print(f"Token exists: {bool(token)}")
    print(f"From number: {from_num}")

    if not all([sid, token, from_num]):
        print("ERROR: Missing Twilio credentials!")
        return

    client = Client(sid, token)

    # Check account info
    try:
        account = client.api.accounts(sid).fetch()
        print(f"Account status: {account.status}")
        print(f"Account friendly_name: {account.friendly_name}")
    except Exception as e:
        print(f"Account check failed: {e}")
        return

    # Try sending a test WhatsApp message
    # Note: Twilio sandbox requires the recipient to join first
    # Production numbers need Twilio approval
    to_num = os.getenv("TEST_WHATSAPP_NUMBER", "")

    if to_num:
        try:
            msg = client.messages.create(
                body="[Test] WatchMeGuru — your mentor is here! 🌱",
                from_=from_num,
                to=f"whatsapp:{to_num}",
            )
            print(f"Message sent! SID: {msg.sid}, Status: {msg.status}")
        except Exception as e:
            print(f"Send failed: {e}")
            print("\nNote: Twilio WhatsApp sandbox requires the recipient to send a join code first.")
            print("For production WhatsApp, the number must be approved by Meta.")
    else:
        print("No test number provided. Set TEST_WHATSAPP_NUMBER in .env to test.")

asyncio.run(test())
