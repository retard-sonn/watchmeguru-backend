"""
Resend Email Service
Sends transactional emails: welcome, weekly parent reports, alerts.
"""
import logging
import resend
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Initialize Resend client
_client = None

def _get_client() -> resend.Resend:
    global _client
    if _client is None:
        if not settings.resend_api_key:
            logger.warning("RESEND_API_KEY not set — emails will be mocked")
            return None
        resend.api_key = settings.resend_api_key
        _client = resend
    return _client


async def send_email(to: str, subject: str, html: str, from_label: str = "WatchMeGuru") -> dict:
    """
    Send an email via Resend.
    Returns {"status": "sent", "id": "..."} or {"status": "mocked"} if not configured.
    """
    client = _get_client()
    if client is None:
        logger.info(f"[MOCK Email] → {to}: {subject}")
        return {"status": "mocked", "to": to, "subject": subject}

    try:
        response = client.Emails.send({
            "from": f"{from_label} <onboarding@resend.dev>",
            "to": [to],
            "subject": subject,
            "html": html,
        })
        logger.info(f"Email sent to {to}: id={response.get('id','?')}")
        return {"status": "sent", "id": response.get("id", ""), "to": to}
    except Exception as e:
        logger.error(f"Resend send failed to {to}: {e}")
        return {"status": "failed", "to": to, "error": str(e)}


def build_welcome_email(student_name: str, exam_type: str, mode: str) -> str:
    """HTML template for student welcome email."""
    mode_desc = {"strict": "Strict — daily check-ins, parent alerts on missed days.",
                 "moderate": "Moderate — firm accountability, weekly parent reports.",
                 "own_pace": "Own Pace — supportive mentor, no parent alerts."}
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:#F4EEDB;padding:40px 20px;margin:0">
<div style="max-width:560px;margin:0 auto;background:#FDF9F0;border-radius:24px;padding:40px;border:1px solid rgba(91,70,54,0.1)">
  <h1 style="color:#5B4636;font-size:28px;margin:0 0 8px">Welcome to WatchMeGuru, {student_name}! 🌱</h1>
  <p style="color:#6B5D52;font-size:15px;line-height:1.6">
    Your AI mentor is ready. We've locked in your study plan for <strong>{exam_type}</strong>.
  </p>
  <div style="background:#F4EEDB;border-radius:16px;padding:20px;margin:24px 0">
    <h3 style="color:#5B4636;margin:0 0 12px">Your Setup</h3>
    <p style="color:#6B5D52;font-size:14px;margin:0 0 8px">📚 Exam: <strong>{exam_type}</strong></p>
    <p style="color:#6B5D52;font-size:14px;margin:0 0 8px">🛡️ Mode: <strong>{mode_desc.get(mode, mode)}</strong></p>
    <p style="color:#6B5D52;font-size:14px;margin:0">💬 Mentor available on <strong>WhatsApp</strong></p>
  </div>
  <p style="color:#6B5D52;font-size:14px;line-height:1.6">
    Your mentor will message you on WhatsApp every day. After each study block, send a photo of your work as proof.
    No photo = session not counted.
  </p>
  <p style="color:#6B5D52;font-size:14px;line-height:1.6">
    <strong>Your dashboard is live:</strong> track streaks, earn XP, grow your learning tree, and unlock achievements.
  </p>
  <a href="https://watchmeguru.io/dashboard" style="display:inline-block;background:linear-gradient(135deg,#58CC02,#46A302);color:#fff;text-decoration:none;padding:14px 32px;border-radius:14px;font-weight:700;font-size:15px;margin-top:16px">
    Open Dashboard →
  </a>
  <p style="color:#9B8E84;font-size:12px;margin:32px 0 0">
    — The WatchMeGuru Team<br>
    <span style="color:#7BA65B">Stay accountable. Build discipline. Level up daily.</span>
  </p>
</div>
</body></html>"""


def build_parent_weekly_report(student_name: str, exam_type: str, day_streak: int,
                                tasks_completed: int, study_hours: float,
                                mode: str, escalation_level: int = 0) -> str:
    """HTML template for parent weekly report."""
    streak_emoji = "🔥" if day_streak >= 7 else ("✨" if day_streak >= 3 else "—")
    alert_html = ""
    if escalation_level >= 2:
        alert_html = f"""<div style="background:rgba(255,75,75,0.08);border:1px solid rgba(255,75,75,0.2);border-radius:12px;padding:16px;margin:16px 0">
          <strong style="color:#FF4B4B">⚠️ Alert:</strong> {student_name} has missed multiple sessions. Please check in with them.
        </div>"""

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:#F4EEDB;padding:40px 20px;margin:0">
<div style="max-width:560px;margin:0 auto;background:#FDF9F0;border-radius:24px;padding:40px;border:1px solid rgba(91,70,54,0.1)">
  <h1 style="color:#5B4636;font-size:24px;margin:0 0 4px">Weekly Study Report</h1>
  <p style="color:#9B8E84;font-size:14px;margin:0 0 24px">WatchMeGuru · {student_name}</p>
  {alert_html}
  <div style="background:#F4EEDB;border-radius:16px;padding:24px;margin:16px 0">
    <h3 style="color:#5B4636;margin:0 0 16px">📊 This Week's Stats</h3>
    <table style="width:100%;border-collapse:collapse">
      <tr><td style="padding:10px 0;color:#6B5D52;font-size:14px">📅 Streak</td><td style="text-align:right;font-weight:700;color:#5B4636;font-size:16px">{day_streak} days {streak_emoji}</td></tr>
      <tr><td style="padding:10px 0;color:#6B5D52;font-size:14px">✅ Tasks Completed</td><td style="text-align:right;font-weight:700;color:#5B4636;font-size:16px">{tasks_completed}</td></tr>
      <tr><td style="padding:10px 0;color:#6B5D52;font-size:14px">⏱️ Study Hours</td><td style="text-align:right;font-weight:700;color:#5B4636;font-size:16px">{study_hours:.1f}h</td></tr>
      <tr><td style="padding:10px 0;color:#6B5D52;font-size:14px">🎯 Exam</td><td style="text-align:right;font-weight:700;color:#5B4636;font-size:16px">{exam_type}</td></tr>
      <tr><td style="padding:10px 0;color:#6B5D52;font-size:14px">🛡️ Mode</td><td style="text-align:right;font-weight:700;color:#5B4636;font-size:16px">{mode.capitalize()}</td></tr>
    </table>
  </div>
  <div style="background:rgba(123,166,91,0.06);border-radius:12px;padding:16px;margin:16px 0">
    <h3 style="color:#5B4636;margin:0 0 8px">💡 Tips for Parents</h3>
    <ul style="color:#6B5D52;font-size:13px;line-height:1.8;margin:0;padding-left:20px">
      <li>Ask about their <strong>toughest subject</strong> this week</li>
      <li>Celebrate small wins — encouragement boosts consistency</li>
      <li>Check the study environment is set up properly</li>
    </ul>
  </div>
  <p style="color:#9B8E84;font-size:12px;margin:32px 0 0">
    — WatchMeGuru AI Mentor<br>
    <span style="color:#7BA65B">Stay accountable. Build discipline. Level up daily.</span>
  </p>
</div>
</body></html>"""
