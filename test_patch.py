"""Test Supabase PATCH with new columns."""
import os, httpx, asyncio
from dotenv import load_dotenv
load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
headers = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json", "Prefer": "return=representation"}

async def test():
    test_data = {"name": "Abraar", "exam_type": "School Exam", "mode": "strict"}
    async with httpx.AsyncClient() as c:
        r = await c.patch(f"{url}/rest/v1/students?clerk_user_id=eq.user_3EBRgiJYvS6yihMtAu0LtDedyot", headers=headers, json=test_data)
        print(f"Status: {r.status_code}")
        if r.status_code >= 400:
            print(f"Error: {r.text[:300]}")
        else:
            data = r.json()
            if data:
                s = data[0]
                print(f"OK! Name: {s.get('name')}, Edit count: {s.get('setup_edit_count', 'N/A')}")

asyncio.run(test())
