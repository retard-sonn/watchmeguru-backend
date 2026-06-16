from fastapi import APIRouter, Depends, HTTPException, Header
import os
from app.core.config import get_settings

router = APIRouter()
settings = get_settings()

def verify_cron_secret(authorization: str = Header(None)):
    expected_secret = os.environ.get("CRON_SECRET", getattr(settings, "CRON_SECRET", ""))
    
    # If a cron secret is configured, require it in the Authorization header
    if expected_secret:
        if authorization != f"Bearer {expected_secret}":
            raise HTTPException(status_code=401, detail="Unauthorized")
    return True

@router.get("/run")
async def run_cron_jobs(authorized: bool = Depends(verify_cron_secret)):
    """Vercel Cron endpoint triggered every 5 minutes."""
    try:
        from app.core.scheduler import send_block_reminders, check_engagement_decay, send_weekly_parent_reports
        
        # Execute the jobs that would normally run every 5 minutes via APScheduler
        await send_block_reminders()
        await check_engagement_decay()
        
        # This function internally checks if it's Sunday, so it's safe to call frequently
        # or we could add logic to only call it once an hour, but Vercel limits us to 2 cron jobs on free tier, 
        # so bundling them into one endpoint is best.
        await send_weekly_parent_reports()
        
        return {"status": "success", "message": "Cron jobs executed successfully"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}
