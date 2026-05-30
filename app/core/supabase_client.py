"""
Supabase REST client using plain httpx.
No C++ build tools required — avoids the pyiceberg dependency chain.
"""

import httpx
from app.core.config import get_settings
from functools import lru_cache

settings = get_settings()

SUPABASE_URL = settings.supabase_url
SUPABASE_KEY = settings.supabase_key
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}


def _url(table: str) -> str:
    return f"{SUPABASE_URL}/rest/v1/{table}"


async def sb_select(table: str, filters: dict = None) -> list:
    """SELECT rows. filters: {"column": "value"}"""
    params = {"select": "*"}
    if filters:
        for k, v in filters.items():
            params[k] = f"eq.{v}"
    async with httpx.AsyncClient() as client:
        r = await client.get(_url(table), headers=HEADERS, params=params)
        r.raise_for_status()
        return r.json()


async def sb_upsert(table: str, record: dict, on_conflict: str = "id") -> list:
    """UPSERT a single record."""
    headers = {**HEADERS, "Prefer": f"resolution=merge-duplicates,return=representation"}
    params = {"on_conflict": on_conflict}
    async with httpx.AsyncClient() as client:
        r = await client.post(_url(table), headers=headers, params=params, json=record)
        r.raise_for_status()
        return r.json()


async def sb_update(table: str, record: dict, filters: dict) -> list:
    """UPDATE rows matching filters."""
    params = {}
    for k, v in filters.items():
        params[k] = f"eq.{v}"
    async with httpx.AsyncClient() as client:
        r = await client.patch(_url(table), headers=HEADERS, params=params, json=record)
        r.raise_for_status()
        return r.json()


async def sb_insert(table: str, record: dict) -> list:
    """INSERT a single record."""
    async with httpx.AsyncClient() as client:
        r = await client.post(_url(table), headers=HEADERS, json=record)
        r.raise_for_status()
        return r.json()
