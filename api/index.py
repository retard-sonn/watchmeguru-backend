"""
Vercel serverless entrypoint for FastAPI.
This file is required at /api/index.py for Vercel's Python runtime.
"""
from app.main import app  # noqa: F401
