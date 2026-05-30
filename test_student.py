import asyncio
import sys
sys.path.insert(0, '.')

async def test():
    from app.core.supabase_client import sb_select
    students = await sb_select('students', {'clerk_user_id': 'user_3EBRgiJYvS6yihMtAu0LtDedyot'})
    if students:
        s = students[0]
        print('Student found!')
        print(f'  Name: "{s.get("name")}"')
        print(f'  WhatsApp: {s.get("whatsapp_number")}')
        print(f'  Exam: {s.get("exam_type")}')
        print(f'  Schedule exists: {s.get("daily_schedule") is not None}')
        print(f'  Mode: {s.get("mode")}')
        print(f'  Platforms: {s.get("preferred_platforms")}')
    else:
        print('No student found')

asyncio.run(test())
