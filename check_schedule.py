import os, httpx, asyncio, json
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
headers = {"apikey": key, "Authorization": f"Bearer {key}"}

async def check():
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{url}/rest/v1/students?select=clerk_user_id,daily_schedule&limit=5", headers=headers)
        print(f"Status: {r.status_code}")
        data = r.json()
        for i, s in enumerate(data):
            ds = s.get("daily_schedule")
            print(f"\nStudent {i}: clerk={s.get('clerk_user_id','none')[:30]}...")
            print(f"  daily_schedule type: {type(ds).__name__}")
            if isinstance(ds, list):
                days_list = [d.get("day","?") for d in ds]
                print(f"  Days: {days_list}")
                days = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
                today = days[datetime.now().weekday()]
                print(f"  Today: {today}")
                td = next((d for d in ds if d.get("day") == today), None)
                if td:
                    print(f"  isRest: {td.get('isRest')}")
                    print(f"  blocks count: {len(td.get('blocks',[]))}")
                    if td.get("blocks"):
                        for b in td["blocks"][:2]:
                            print(f"    - {b.get('label')} @ {b.get('startTime')} ({b.get('hours')}h)")
                else:
                    print("  No entry for today")
            elif isinstance(ds, dict):
                print(f"  dict keys: {list(ds.keys())}")
                inner = ds.get("schedule", [])
                if isinstance(inner, list):
                    print(f"  schedule days: {[d.get('day','?') for d in inner]}")
            else:
                print(f"  value: {str(ds)[:100]}")

asyncio.run(check())
