"""Secure Supabase client configuration for operational commands."""

from __future__ import annotations

import os
from typing import Any


def load_supabase_settings() -> tuple[str, str]:
    """Load credentials from environment, then the established config fallback."""

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if url and key:
        return url, key

    try:
        from config import SUPABASE_KEY, SUPABASE_URL
    except ImportError as exc:
        raise RuntimeError(
            "Set SUPABASE_URL and SUPABASE_KEY, or provide the repository's "
            "ignored config.py through the established deployment workflow."
        ) from exc
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("Supabase configuration is incomplete.")
    return SUPABASE_URL, SUPABASE_KEY


def create_supabase_client() -> Any:
    from supabase import create_client

    url, key = load_supabase_settings()
    return create_client(url, key)
