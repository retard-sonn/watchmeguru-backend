"""
Supabase REST client using plain httpx with connection pooling.
No C++ build tools required — avoids the pyiceberg dependency chain.
"""
import httpx
from app.core.config import get_settings
from contextlib import asynccontextmanager

settings = get_settings()

SUPABASE_URL = settings.supabase_url
SUPABASE_KEY = settings.supabase_key
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

# Shared client with connection pooling — created once, reused across all requests
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    """Get or create the shared httpx client with connection pooling."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=50),
        )
    return _client


async def close_client():
    """Gracefully close the shared client (call on app shutdown)."""
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None


def _url(table: str) -> str:
    return f"{SUPABASE_URL}/rest/v1/{table}"


async def sb_select(table: str, filters: dict = None, raw_filters: dict = None) -> list:
    """SELECT rows.
    filters: {"column": "value"} — uses eq. operator
    raw_filters: {"column": "not.is.null"} — passes value directly as URL param
    """
    params = {"select": "*"}
    if filters:
        for k, v in filters.items():
            params[k] = f"eq.{v}"
    if raw_filters:
        for k, v in raw_filters.items():
            params[k] = v  # e.g., "not.is.null", "gt.100", etc.
    client = _get_client()
    r = await client.get(_url(table), headers=HEADERS, params=params)
    r.raise_for_status()
    return r.json()


async def sb_upsert(table: str, record: dict, on_conflict: str = "id") -> list:
    """UPSERT a single record."""
    headers = {**HEADERS, "Prefer": "resolution=merge-duplicates,return=representation"}
    params = {"on_conflict": on_conflict}
    client = _get_client()
    r = await client.post(_url(table), headers=headers, params=params, json=record)
    r.raise_for_status()
    return r.json()


async def sb_update(table: str, record: dict, filters: dict) -> list:
    """UPDATE rows matching filters."""
    params = {}
    for k, v in filters.items():
        params[k] = f"eq.{v}"
    client = _get_client()
    r = await client.patch(_url(table), headers=HEADERS, params=params, json=record)
    r.raise_for_status()
    return r.json()


async def sb_insert(table: str, record: dict) -> list:
    """INSERT a single record."""
    client = _get_client()
    r = await client.post(_url(table), headers=HEADERS, json=record)
    r.raise_for_status()
    return r.json()
