from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.middleware.clerk_auth import ClerkAuthMiddleware
from contextlib import asynccontextmanager

settings = get_settings()

from app.core.scheduler import start_scheduler, shutdown_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Application Startup")
    start_scheduler()
    yield
    from app.core.supabase_client import close_client
    await close_client()
    shutdown_scheduler()
    print("Application Shutdown")

app = FastAPI(
    title="WatchMeGuru.io API",
    description="Backend API for WatchMeGuru.io — proactive mentorship across WhatsApp, Telegram & Discord",
    version="1.0.0",
    lifespan=lifespan
)

# CORS — allow frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://watchmeguru.io"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Clerk Auth Middleware — verifies JWT & syncs user on every request
app.add_middleware(ClerkAuthMiddleware)

@app.get("/health")
def health_check():
    return {"status": "healthy", "environment": settings.environment}

from app.routers import webhook, webhooks, students, onboarding, ai, kickstart, quiz, dashboard, leaderboard

# Include routers
app.include_router(webhook.router, prefix="/api/v1/webhooks", tags=["Webhooks (Legacy)"])
app.include_router(webhooks.router, prefix="/api/v1/omnichannel", tags=["Omni-Channel Webhooks"])
app.include_router(students.router, prefix="/api/v1/students", tags=["Students"])
app.include_router(onboarding.router, prefix="/api/v1/onboarding", tags=["Onboarding"])
app.include_router(ai.router, prefix="/api/v1/ai", tags=["AI"])
app.include_router(dashboard.router, prefix="/api/v1/students", tags=["Dashboard"])
app.include_router(leaderboard.router, prefix="/api/v1/leaderboard", tags=["Leaderboard"])
app.include_router(kickstart.router, prefix="/api/v1", tags=["Kickstart"])
app.include_router(quiz.router, prefix="/api/v1/quiz", tags=["Quiz"])
