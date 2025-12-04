#!/usr/bin/env python3
"""
db.py — Supabase helper functions for Alesha

- Ленивая инициализация клиента Supabase
- Безопасное логирование сообщений (не роняет бота при ошибках)
"""

import json
import time
from typing import Optional

from supabase.client import create_client, Client

# Загружаем конфиг (тот же самый, что и в alesha.py)
with open("config.json") as f:
    config = json.load(f)

_supabase: Optional[Client] = None


def get_supabase() -> Optional[Client]:
    """
    Lazy-init Supabase client.
    Возвращает None, если не получилось инициализировать.
    """
    global _supabase
    if _supabase is not None:
        return _supabase

    url = config.get("SUPABASE_URL")
    key = config.get("SUPABASE_KEY")

    if not url or not key:
        print("⚠ Supabase URL or KEY missing in config.json")
        _supabase = None
        return None

    try:
        _supabase = create_client(url, key)
        print("✅ Supabase client initialized (db.py).")
    except Exception as e:
        print(f"⚠ Failed to init Supabase client: {e}")
        _supabase = None

    return _supabase


def save_message_to_supabase(message_data: dict):
    """
    Save message to public.messages table.

    Expects minimum:
        {
            "id": <yt message id>,
            "author": <author name>,
            "content": <text>,
            "language": <lang_code>,
        }

    Optional:
        "timestamp", "platform", "streamer_id", "subscriber_id"
    """
    client = get_supabase()
    if client is None:
        # Supabase is not configured — just silently log the error
        return None

    try:
        data = {
            "message_id": message_data.get("id"),
            "author": message_data.get("author"),
            "content": message_data.get("content"),
            "language": message_data.get("language"),
            "timestamp": message_data.get("timestamp", time.time()),
            "platform": message_data.get("platform", "youtube"),
            "streamer_id": message_data.get("streamer_id"),
            "subscriber_id": message_data.get("subscriber_id"),
        }

        result = client.table("messages").insert(data).execute()
        print(f"✅ Saved message to Supabase: {data['message_id']}")
        return result

    except Exception as e:
        print(f"⚠ Failed to save to Supabase: {e}")
        return None
