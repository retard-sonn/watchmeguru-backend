from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.middleware.clerk_auth import ClerkAuthMiddleware
from contextlib import asynccontextmanager
import os

settings = get_settings()

# APScheduler only works in long-running servers, NOT on Vercel serverless.
# Guard it so Vercel cold-starts don't crash.
IS_VERCEL = os.environ.get("VERCEL") == "1"

if not IS_VERCEL:
    from app.core.scheduler import start_scheduler, shutdown_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Application Startup")
    if not IS_VERCEL:
        start_scheduler()
    yield
    if not IS_VERCEL:
        try:
            from app.core.supabase_client import close_client
            await close_client()
        except Exception:
            pass
        shutdown_scheduler()
    print("Application Shutdown")


app = FastAPI(
    title="WatchMeGuru.io API",
    description="Backend API for WatchMeGuru.io — proactive mentorship across WhatsApp, Telegram & Discord",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow all our frontends (localhost dev + Vercel preview + production)
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "https://watchmeguru.io",
    "https://www.watchmeguru.io",
    "https://watchmeguru-frontend.vercel.app",
    # Allow all Vercel preview deploy URLs for this project
    "https://watchmeguru-frontend-*.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"https://watchmeguru-frontend.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Clerk Auth Middleware — verifies JWT & syncs user on every request
app.add_middleware(ClerkAuthMiddleware)


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "environment": settings.environment,
        "serverless": IS_VERCEL,
    }


@app.get("/")
def root():
    return {"service": "WatchMeGuru API", "version": "1.0.0", "docs": "/docs"}


from app.routers import webhook, webhooks, students, onboarding, ai, kickstart

# Core routers — always included
app.include_router(webhook.router, prefix="/api/v1/webhooks", tags=["Webhooks (Legacy)"])
app.include_router(webhooks.router, prefix="/api/v1/omnichannel", tags=["Omni-Channel Webhooks"])
app.include_router(students.router, prefix="/api/v1/students", tags=["Students"])
app.include_router(onboarding.router, prefix="/api/v1/onboarding", tags=["Onboarding"])
app.include_router(ai.router, prefix="/api/v1/ai", tags=["AI"])
app.include_router(kickstart.router, prefix="/api/v1", tags=["Kickstart"])

# Optional routers — import defensively so missing deps don't crash Vercel
try:
    from app.routers import quiz
    app.include_router(quiz.router, prefix="/api/v1/quiz", tags=["Quiz"])
except Exception as e:
    print(f"Quiz router not loaded: {e}")

try:
    from app.routers import dashboard
    app.include_router(dashboard.router, prefix="/api/v1/students", tags=["Dashboard"])
except Exception as e:
    print(f"Dashboard router not loaded: {e}")

try:
    from app.routers import audit
    app.include_router(audit.router, prefix="/api/v1/audit", tags=["Audit"])
except Exception as e:
    print(f"Audit router not loaded: {e}")

try:
    from app.routers import verify
    app.include_router(verify.router, prefix="/api/v1", tags=["Verify"])
except Exception as e:
    print(f"Verify router not loaded: {e}")

try:
    from app.routers import leaderboard
    app.include_router(leaderboard.router, prefix="/api/v1/leaderboard", tags=["Leaderboard"])
except Exception as e:
    print(f"Leaderboard router not loaded: {e}")
