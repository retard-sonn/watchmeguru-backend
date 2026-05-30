from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timezone
import re

# Initialize the scheduler
scheduler = AsyncIOScheduler()

def start_scheduler():
    if not scheduler.running:
        scheduler.start()
        print("APScheduler started")

def shutdown_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        print("APScheduler shutdown")

def minutes_until_block(start_time_str: str) -> int:
    """Calculate minutes from now until the block's start time."""
    try:
        match = re.match(r"(\d+):(\d+)\s*(AM|PM)", start_time_str, re.IGNORECASE)
        if not match:
            return -9999
        h, m, meridiem = match.groups()
        hour = int(h)
        minute = int(m)
        if meridiem.upper() == "PM" and hour != 12:
            hour += 12
        elif meridiem.upper() == "AM" and hour == 12:
            hour = 0
            
        now = datetime.now() # local server time
        block_time_mins = hour * 60 + minute
        now_mins = now.hour * 60 + now.minute
        
        diff = block_time_mins - now_mins
        return diff
    except Exception:
        return -9999

# Block reminder job
async def send_block_reminders():
    print("Running send_block_reminders APScheduler job...")
    try:
        from app.core.supabase_client import sb_select
        from app.services.twilio_service import send_whatsapp
        from app.services.telegram_service import send_telegram_message
        from app.services.discord_service import send_discord_message

        students = await sb_select("students")
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        today_short = days[datetime.now().weekday()]

        for student in students:
            daily_schedule = student.get("daily_schedule")
            if not daily_schedule:
                continue

            schedule = daily_schedule if isinstance(daily_schedule, list) else daily_schedule.get("schedule", [])
            today_day = next((d for d in schedule if d.get("day") == today_short), None)
            if not today_day or today_day.get("isRest"):
                continue

            blocks = today_day.get("blocks", [])
            for block in blocks:
                start_time_str = block.get("startTime") or block.get("start")
                if not start_time_str:
                    continue

                diff = minutes_until_block(start_time_str)
                # If block starts in 10-15 minutes, send alert
                if 10 <= diff <= 15:
                    label = block.get("label", "Study Session")
                    hours = block.get("hours", 1.5)
                    student_name = student.get("name") or "Student"
                    
                    msg = (
                        f"⏰ *Upcoming Study Session Reminder*\n\n"
                        f"Hey {student_name}, your session for *{label}* ({hours}h) is scheduled to start in *{diff} minutes* (at {start_time_str}).\n\n"
                        f"Get your desk ready, set up your books, and prepare to kickstart when the time comes! 🎯"
                    )

                    # Send to whatsapp
                    if student.get("whatsapp_number"):
                        try:
                            await send_whatsapp(student["whatsapp_number"], msg)
                        except Exception as e:
                            print(f"Failed to send whatsapp reminder: {e}")

                    # Send to Telegram
                    if student.get("telegram_chat_id"):
                        try:
                            await send_telegram_message(student["telegram_chat_id"], msg)
                        except Exception as e:
                            print(f"Failed to send telegram reminder: {e}")

                    # Send to Discord
                    if student.get("discord_user_id"):
                        try:
                            await send_discord_message(student["discord_user_id"], msg)
                        except Exception as e:
                            print(f"Failed to send discord reminder: {e}")

    except Exception as ex:
        print(f"Error in send_block_reminders: {ex}")

# Engagement decay and escalation job
async def check_engagement_decay():
    print("Running check_engagement_decay APScheduler job...")
    try:
        from app.core.supabase_client import sb_select, sb_update
        from app.services.twilio_service import send_whatsapp

        students = await sb_select("students")
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        today_short = days[datetime.now().weekday()]

        for student in students:
            # Only track if accountability mode is moderate or strict
            mode = student.get("mode", "own_pace")
            if mode == "own_pace":
                continue

            daily_schedule = student.get("daily_schedule")
            if not daily_schedule:
                continue

            schedule = daily_schedule if isinstance(daily_schedule, list) else daily_schedule.get("schedule", [])
            today_day = next((d for d in schedule if d.get("day") == today_short), None)
            if not today_day or today_day.get("isRest"):
                continue

            student_id = student["id"]
            student_name = student.get("name") or "Student"
            whatsapp_number = student.get("whatsapp_number")
            guardian = student.get("guardian_contact")

            # Get all tasks created today for this student
            tasks = await sb_select("tasks", {"student_id": student_id})
            today_tasks = []
            today_date = datetime.now().date()
            for t in tasks:
                due_str = t.get("due_date")
                if due_str:
                    try:
                        dt = datetime.fromisoformat(str(due_str).replace("Z", "+00:00"))
                        if dt.date() == today_date:
                            today_tasks.append(t)
                    except Exception:
                        pass

            blocks = today_day.get("blocks", [])
            for block_index, block in enumerate(blocks):
                start_time_str = block.get("startTime") or block.get("start")
                if not start_time_str:
                    continue

                diff = minutes_until_block(start_time_str)
                # If the block start time has passed by more than 30 minutes (diff <= -30)
                # And they have not kickstarted it (no task exists for this block subject today)
                if diff <= -30:
                    subject = block.get("label", "")
                    has_started = any(t.get("subject", "").lower() == subject.lower() for t in today_tasks)
                    
                    if not has_started:
                        # Escalation logic
                        esc_level = student.get("escalation_level") or 0
                        new_esc_level = esc_level + 1
                        
                        await sb_update("students", {"escalation_level": new_esc_level}, {"id": student_id})
                        student["escalation_level"] = new_esc_level
                        
                        if new_esc_level == 1:
                            warning_msg = (
                                f"⚠️ *Study Block Missed Warning*\n\n"
                                f"Hey {student_name}, you missed your scheduled start for *{subject}* (scheduled at {start_time_str}).\n\n"
                                f"Please get back to your study desk as soon as possible. Consistency is key!"
                            )
                            if whatsapp_number:
                                await send_whatsapp(whatsapp_number, warning_msg)

                        elif new_esc_level == 2:
                            stern_msg = (
                                f"🚨 *STERN WARNING: Missed Study Session*\n\n"
                                f"{student_name}, you have missed your study session for *{subject}* by more than 30 minutes.\n\n"
                                f"If you do not complete your upcoming blocks, I will escalate this to your guardian. Do not break your commitment."
                            )
                            if whatsapp_number:
                                await send_whatsapp(whatsapp_number, stern_msg)

                        elif new_esc_level >= 3:
                            if mode in ["strict", "moderate"] and guardian:
                                guardian_msg = (
                                    f"👨‍👩‍👦 *WatchMeGuru — Guardian Alert*\n\n"
                                    f"Dear Parent/Guardian, this is to inform you that {student_name} has missed their scheduled study sessions for *{subject}* today despite warnings.\n\n"
                                    f"Accountability Mode: {mode.capitalize()}\n"
                                    f"Please check in on their progress."
                                )
                                try:
                                    await send_whatsapp(guardian, guardian_msg)
                                    print(f"Guardian alert sent to {guardian}")
                                except Exception as ge:
                                    print(f"Failed to send guardian alert: {ge}")
                                    
                            # Reset level after alerting parent
                            await sb_update("students", {"escalation_level": 0}, {"id": student_id})

    except Exception as ex:
        print(f"Error in check_engagement_decay: {ex}")

# Add jobs to run every 5 minutes
scheduler.add_job(send_block_reminders, 'interval', minutes=5)
scheduler.add_job(check_engagement_decay, 'interval', minutes=5)
