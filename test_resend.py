"""Test Resend email directly."""
import os, asyncio
from dotenv import load_dotenv
load_dotenv()

async def test():
    import resend
    key = os.getenv("RESEND_API_KEY")
    print(f"Resend key exists: {bool(key)}")
    print(f"Key starts with: {key[:12]}...")

    if not key:
        print("ERROR: RESEND_API_KEY not set!")
        return

    resend.api_key = key

    try:
        r = resend.Emails.send({
            "from": "WatchMeGuru <onboarding@resend.dev>",
            "to": ["abraarssgtoons@gmail.com"],
            "subject": "[Test] WatchMeGuru — Welcome! 🌱",
            "html": "<h1>WatchMeGuru Test</h1><p>Your mentor is ready!</p>",
        })
        print(f"Email sent! ID: {r.get('id', '?')}")
        print(r)
    except Exception as e:
        print(f"Send failed: {e}")

asyncio.run(test())
