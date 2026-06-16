"""
Clerk JWT Auth Middleware for FastAPI.

On every authenticated request:
1. Extract Bearer token from Authorization header
2. Verify JWT using Clerk's JWKS endpoint
3. Extract user data (clerk_user_id, email, name, photo)
4. Upsert user to the 'users' table in Supabase
5. Attach user data to request.state.clerk_user
"""

import jwt
import httpx
from jwt import PyJWKClient
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.config import get_settings
from app.services.user_sync import sync_clerk_user_to_db
import logging

logger = logging.getLogger(__name__)

# Public routes that don't require auth
PUBLIC_PATHS = [
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/api/v1/webhooks",
    "/api/v1/cron",
]


def _cors_response(status_code: int, detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"detail": detail},
        headers={
            "Access-Control-Allow-Origin": "http://localhost:3000",
            "Access-Control-Allow-Credentials": "true",
        },
    )

class ClerkAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        settings = get_settings()
        self._jwks_client = None
        self._clerk_issuer = None

        # Extract the Clerk frontend API domain from the publishable key
        # pk_test_<base64-encoded-domain>
        if settings.clerk_publishable_key:
            import base64
            try:
                key_part = settings.clerk_publishable_key.split("_")[-1]
                # Add padding
                padding = 4 - len(key_part) % 4
                if padding != 4:
                    key_part += "=" * padding
                domain = base64.b64decode(key_part).decode("utf-8").rstrip("$")
                self._clerk_issuer = f"https://{domain}"
                self._jwks_url = f"https://{domain}/.well-known/jwks.json"
                self._jwks_client = PyJWKClient(self._jwks_url, cache_keys=True)
                logger.info(f"Clerk JWKS configured for issuer: {self._clerk_issuer}")
            except Exception as e:
                logger.warning(f"Failed to parse Clerk publishable key: {e}")

    def _is_public_path(self, path: str) -> bool:
        for public_path in PUBLIC_PATHS:
            if path.startswith(public_path):
                return True
        return False

    async def dispatch(self, request: Request, call_next):
        # Skip auth for OPTIONS (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)

        # Skip auth for public paths
        if self._is_public_path(request.url.path):
            return await call_next(request)

        # Extract token
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return _cors_response(401, "Missing or invalid Authorization header")

        token = auth_header.split(" ", 1)[1]

        if not self._jwks_client:
            return _cors_response(500, "Clerk auth not configured. Set CLERK_PUBLISHABLE_KEY in .env")

        try:
            # Get signing key from JWKS
            signing_key = self._jwks_client.get_signing_key_from_jwt(token)

            # Decode and verify JWT with 10 minutes leeway for clock skew
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                issuer=self._clerk_issuer,
                options={"verify_aud": False},  # Clerk doesn't always set aud
                leeway=600,  # 10 minutes leeway to tolerate client-server clock drift
            )

            # Extract user data from claims
            clerk_user_id = payload.get("sub", "")
            user_data = {
                "clerk_user_id": clerk_user_id,
                "email": payload.get("email", payload.get("primary_email", "")),
                "first_name": payload.get("first_name", ""),
                "last_name": payload.get("last_name", ""),
                "profile_image_url": payload.get("image_url", payload.get("profile_image_url", "")),
            }

            # Upsert user to database (sync on every request)
            try:
                await sync_clerk_user_to_db(user_data)
            except Exception as e:
                logger.error(f"Failed to sync Clerk user to DB: {e}")
                # Don't block the request if sync fails

            # Attach to request state
            request.state.clerk_user = user_data
            request.state.clerk_user_id = clerk_user_id

        except jwt.ExpiredSignatureError:
            return _cors_response(401, "Token expired")
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid Clerk token: {e}")
            return _cors_response(401, f"Invalid token: {str(e)}")
        except Exception as e:
            logger.error(f"Auth error: {e}")
            return _cors_response(401, "Authentication failed")

        return await call_next(request)
