"""Debug why onboarding upsert fails."""
import os, httpx, asyncio
from dotenv import load_dotenv
load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
headers = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}

async def check():
    clerk = "user_3EBRgiJYvS6yihMtAu0LtDedyot"
    async with httpx.AsyncClient() as c:
        # 1. Check if student exists
        r = await c.get(f"{url}/rest/v1/students?clerk_user_id=eq.{clerk}&select=id,clerk_user_id,name", headers=headers)
        print(f"Select: {r.status_code}")
        data = r.json()
        if data:
            s = data[0]
            print(f"  Found: {s.get('name')} (id: {s.get('id','?')[:8]}...)")
        else:
            print("  No student found")

        # 2. Try basic update (no new columns)
        basic = {"name": "Abraar Test", "exam_type": "School", "mode": "strict"}
        r2 = await c.patch(f"{url}/rest/v1/students?clerk_user_id=eq.{clerk}", headers=headers, json=basic)
        print(f"\nPatch (basic): {r2.status_code}")
        if r2.status_code >= 400:
            print(f"  Error: {r2.text[:200]}")

        # 3. Try update with guardian_email
        with_email = {**basic, "guardian_email": "test@test.com"}
        r3 = await c.patch(f"{url}/rest/v1/students?clerk_user_id=eq.{clerk}", headers=headers, json=with_email)
        print(f"\nPatch (with email): {r3.status_code}")
        if r3.status_code >= 400:
            print(f"  Error: {r3.text[:200]}")

        # 4. Try update with setup_edit_count
        with_edit = {**basic, "setup_edit_count": 1}
        r4 = await c.patch(f"{url}/rest/v1/students?clerk_user_id=eq.{clerk}", headers=headers, json=with_edit)
        print(f"\nPatch (with edit count): {r4.status_code}")
        if r4.status_code >= 400:
            print(f"  Error: {r4.text[:200]}")

        # 5. Try upsert
        upsert_headers = {**headers, "Prefer": "resolution=merge-duplicates,return=representation"}
        r5 = await c.post(f"{url}/rest/v1/students?on_conflict=clerk_user_id", headers=upsert_headers, json=basic)
        print(f"\nUpsert: {r5.status_code}")
        if r5.status_code >= 400:
            print(f"  Error: {r5.text[:200]}")
        else:
            print(f"  OK: {r5.json()[0].get('name','?')}")

asyncio.run(check())
