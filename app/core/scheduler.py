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

        # Only fetch students who have a schedule set (efficiency: avoid full table scan of unsetup users)
        students = await sb_select("students", raw_filters={"daily_schedule": "not.is.null"})
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

        students = await sb_select("students", raw_filters={"daily_schedule": "not.is.null"})
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

# ─── Weekly Parent Report for Strict Mode ─────────────────
async def send_weekly_parent_reports():
    """Every Sunday evening, send study report to parents of strict-mode students."""
    print("Running send_weekly_parent_reports APScheduler job...")
    try:
        from app.core.supabase_client import sb_select
        from app.services.twilio_service import send_whatsapp

        students = await sb_select("students", raw_filters={"mode": "eq.strict"})
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

        # Only run on Sundays
        if datetime.now().weekday() != 6:
            print("Not Sunday — skipping weekly parent reports")
            return

        for student in students:
            mode = student.get("mode", "own_pace")
            if mode != "strict":
                continue

            guardian = student.get("guardian_contact")
            if not guardian:
                continue

            student_name = student.get("name") or "Student"
            day_streak = student.get("day_streak") or 0
            tasks_completed = student.get("tasks_completed") or 0
            study_hours = float(student.get("study_hours") or 0)
            escalation_level = student.get("escalation_level") or 0
            exam_type = student.get("exam_type") or "exam"

            # Build report
            streak_emoji = "🔥" if day_streak >= 7 else ("✨" if day_streak >= 3 else "")
            alert_line = ""
            if escalation_level >= 2:
                alert_line = f"\n⚠️ *Alert:* {student_name} has missed multiple sessions this week. Please check in.\n"

            report = (
                f"📊 *Weekly Study Report — WatchMeGuru*\n\n"
                f"Student: *{student_name}*\n"
                f"Exam: {exam_type}\n\n"
                f"📈 *This Week's Stats:*\n"
                f"• Streak: {day_streak} days {streak_emoji}\n"
                f"• Tasks Completed: {tasks_completed}\n"
                f"• Study Hours: {study_hours}h\n"
                f"• Accountability Mode: Strict\n"
                f"{alert_line}"
                f"👨‍👩‍👦 *What you can do:*\n"
                f"• Ask {student_name} about their toughest subject this week\n"
                f"• Celebrate the small wins — encouragement boosts consistency\n"
                f"• Check if the study environment is set up properly\n\n"
                f"— WatchMeGuru AI Mentor"
            )

            try:
                await send_whatsapp(guardian, report)
                print(f"Weekly report sent to guardian of {student_name} at {guardian}")
            except Exception as e:
                print(f"Failed to send WhatsApp report for {student_name}: {e}")

            # Also send email report to parent if email is set
            parent_email = student.get("guardian_email") or student.get("parent_email")
            if parent_email:
                try:
                    from app.services.email_service import send_email, build_parent_weekly_report
                    html = build_parent_weekly_report(
                        student_name, exam_type, day_streak,
                        tasks_completed, study_hours, mode, escalation_level)
                    await send_email(parent_email,
                        f"Weekly Study Report — {student_name} | WatchMeGuru",
                        html, from_label="WatchMeGuru")
                    print(f"Weekly email report sent to {parent_email}")
                except Exception as e:
                    print(f"Failed to send email report to {parent_email}: {e}")

            # Send student weekly summary if student_email is set
            student_email = student.get("student_email")
            if student_email:
                try:
                    from app.services.email_service import send_email
                    student_html = f"""<div style="font-family:sans-serif;max-width:560px;margin:0 auto;background:#FDF9F0;border-radius:24px;padding:40px">
<h1 style="color:#5B4636">Your Weekly Summary, {student_name}! 🌱</h1>
<p style="color:#6B5D52;font-size:15px">Here's how your week went:</p>
<div style="background:#F4EEDB;border-radius:16px;padding:20px;margin:16px 0">
<p style="color:#5B4636;font-size:16px;margin:4px 0">🔥 Streak: <strong>{day_streak} days</strong></p>
<p style="color:#5B4636;font-size:16px;margin:4px 0">✅ Tasks: <strong>{tasks_completed} completed</strong></p>
<p style="color:#5B4636;font-size:16px;margin:4px 0">⏱️ Hours: <strong>{study_hours:.1f}h</strong></p>
</div>
<p style="color:#6B5D52;font-size:14px">Keep up the momentum. Every session grows your learning tree. 🌳</p>
<a href="https://watchmeguru.io/dashboard" style="display:inline-block;background:#58CC02;color:#fff;padding:14px 32px;border-radius:14px;text-decoration:none;font-weight:700">Open Dashboard →</a>
</div>"""
                    await send_email(student_email,
                        f"Your Weekly Summary, {student_name}! | WatchMeGuru",
                        student_html, from_label="WatchMeGuru")
                    print(f"Weekly student summary sent to {student_email}")
                except Exception as e:
                    print(f"Failed to send student email to {student_email}: {e}")

    except Exception as ex:
        print(f"Error in send_weekly_parent_reports: {ex}")

# Add jobs to run every 5 minutes
scheduler.add_job(send_block_reminders, 'interval', minutes=5)
scheduler.add_job(check_engagement_decay, 'interval', minutes=5)
scheduler.add_job(send_weekly_parent_reports, 'interval', minutes=60)  # Check hourly, only sends on Sunday
