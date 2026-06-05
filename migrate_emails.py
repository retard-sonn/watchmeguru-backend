"""
Run this script once to add email columns to the students table.
You can also paste these SQL commands in Supabase SQL Editor:
  ALTER TABLE students ADD COLUMN IF NOT EXISTS guardian_email TEXT;
  ALTER TABLE students ADD COLUMN IF NOT EXISTS student_email TEXT;
"""
import os, httpx, asyncio
from dotenv import load_dotenv
load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

# Note: Supabase REST API doesn't support DDL directly.
# Use the Supabase SQL Editor at https://supabase.com/dashboard
# and run these commands:
SQL_COMMANDS = """
ALTER TABLE students ADD COLUMN IF NOT EXISTS guardian_email TEXT;
ALTER TABLE students ADD COLUMN IF NOT EXISTS student_email TEXT;
"""

async def verify_columns():
    """Check if email columns exist in the students table."""
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{url}/rest/v1/students?select=guardian_email,student_email&limit=1", headers=headers)
        if r.status_code == 200:
            print("[OK] Email columns exist or were auto-created by Supabase!")
            return True
        else:
            print(f"[FAIL] Columns may not exist. HTTP {r.status_code}: {r.text[:200]}")
            print("\nPlease run these SQL commands in Supabase SQL Editor:")
            print(SQL_COMMANDS)
            return False

asyncio.run(verify_columns())
