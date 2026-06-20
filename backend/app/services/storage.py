"""
Supabase Storage helper for Polis attachments.
"""
import re
import uuid
from functools import lru_cache
from typing import Optional
from uuid import UUID

import httpx

from app.config import settings


class StorageNotConfigured(RuntimeError):
    pass


def _service_key() -> Optional[str]:
    return settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_ANON_KEY


def _clean_base_url() -> str:
    return (settings.SUPABASE_URL or "").rstrip("/")


def _safe_filename(filename: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", filename).strip(".-")
    return cleaned or "attachment"


def _headers(content_type: Optional[str] = None) -> dict:
    key = _service_key()
    if not settings.SUPABASE_URL or not key:
        raise StorageNotConfigured("Supabase Storage is not configured")
    headers = {
        "Authorization": f"Bearer {key}",
        "apikey": key,
    }
    if content_type:
        headers["Content-Type"] = content_type
    return headers


@lru_cache(maxsize=1)
def ensure_bucket() -> None:
    base_url = _clean_base_url()
    bucket = settings.SUPABASE_STORAGE_BUCKET
    headers = _headers("application/json")
    response = httpx.post(
        f"{base_url}/storage/v1/bucket",
        headers=headers,
        json={"id": bucket, "name": bucket, "public": True},
        timeout=15,
    )
    if response.status_code not in (200, 201, 409):
        response.raise_for_status()


def upload_bytes(
    *,
    data: bytes,
    filename: str,
    content_type: str,
    owner_id: UUID,
) -> str:
    ensure_bucket()
    base_url = _clean_base_url()
    bucket = settings.SUPABASE_STORAGE_BUCKET
    path = f"{owner_id}/{uuid.uuid4()}-{_safe_filename(filename)}"

    response = httpx.post(
        f"{base_url}/storage/v1/object/{bucket}/{path}",
        headers={**_headers(content_type), "x-upsert": "false"},
        content=data,
        timeout=30,
    )
    response.raise_for_status()
    return f"{base_url}/storage/v1/object/public/{bucket}/{path}"
