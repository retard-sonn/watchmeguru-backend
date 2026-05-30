import os
import asyncio
from dotenv import load_dotenv
import httpx
from twilio.rest import Client

load_dotenv()

async def test_supabase():
    print("Testing Supabase...")
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        print("❌ Supabase credentials missing in .env")
        return False
        
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{supabase_url}/rest/v1/students?select=id&limit=1", headers=headers)
            if r.status_code == 200:
                print(f"✅ Supabase connection SUCCESS. Found {len(r.json())} students.")
                return True
            else:
                print(f"❌ Supabase connection FAILED: {r.status_code} - {r.text}")
                return False
    except Exception as e:
        print(f"❌ Supabase error: {e}")
        return False

def test_twilio():
    print("Testing Twilio...")
    sid = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    from_num = os.getenv("TWILIO_WHATSAPP_NUMBER")
    
    if not sid or not token or not from_num:
        print("❌ Twilio credentials missing in .env")
        return False
        
    try:
        client = Client(sid, token)
        # We won't actually send a message to a random number, just fetch the account info to verify auth
        account = client.api.accounts(sid).fetch()
        print(f"✅ Twilio connection SUCCESS. Account status: {account.status}")
        return True
    except Exception as e:
        print(f"❌ Twilio connection FAILED: {e}")
        return False

async def main():
    s_ok = await test_supabase()
    t_ok = test_twilio()
    
    if s_ok and t_ok:
        print("\nAll APIs verified successfully!")
    else:
        print("\nSome APIs failed to verify.")

if __name__ == "__main__":
    asyncio.run(main())
