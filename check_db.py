"""Check Supabase database for missing columns and data integrity."""
import os, httpx, asyncio
from dotenv import load_dotenv
load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
headers = {"apikey": key, "Authorization": f"Bearer {key}"}

async def check():
    async with httpx.AsyncClient() as c:
        # Get students with all columns
        r = await c.get(f"{url}/rest/v1/students?select=*&limit=2", headers=headers)
        print(f"Students: HTTP {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            for s in data[:1]:
                cols = list(s.keys())
                print(f"  Columns ({len(cols)}): {cols}")
                missing = []
                needed = ["country", "country_code", "isd_code", "setup_complete", "daily_schedule",
                          "student_email", "guardian_email", "setup_edit_count", "last_edit_date",
                          "mode", "day_streak", "tasks_completed", "study_hours", "quiz_accuracy"]
                for col in needed:
                    if col not in s:
                        missing.append(col)
                if missing:
                    print(f"  MISSING COLUMNS: {missing}")
                else:
                    print("  All needed columns exist")
                print(f"  setup_complete: {s.get('setup_complete')}")
                print(f"  has schedule: {bool(s.get('daily_schedule'))}")
                print(f"  mode: {s.get('mode')}")
        else:
            print(f"Error: {r.text[:300]}")

        # Check quizzes table
        r2 = await c.get(f"{url}/rest/v1/quizzes?select=id,subject,status&limit=2", headers=headers)
        print(f"\nQuizzes: HTTP {r2.status_code}")

        # Check tasks table
        r3 = await c.get(f"{url}/rest/v1/tasks?select=id,status,subject&limit=2", headers=headers)
        print(f"Tasks: HTTP {r3.status_code}")

        # Check daily_activity table
        r4 = await c.get(f"{url}/rest/v1/daily_activity?select=*&limit=2", headers=headers)
        print(f"Daily Activity: HTTP {r4.status_code}")

asyncio.run(check())
