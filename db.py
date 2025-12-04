#!/usr/bin/env python3
"""
db.py — single place for working with Supabase:
- initialization of client
- management of streamers
- management of subscribers
- saving messages
"""

import json
import time
from typing import Any, Dict, Optional

from supabase.client import create_client, Client

# ---------- Supabase init ----------

_supabase: Optional[Client] = None


def get_supabase() -> Optional[Client]:
    """
    Возвращает общий Supabase-клиент.
    Если не удалось инициализировать — вернёт None.
    """
    global _supabase
    if _supabase is not None:
        return _supabase

    try:
        with open("config.json") as f:
            config = json.load(f)

        url = config["SUPABASE_URL"]
        key = config["SUPABASE_KEY"]

        _supabase = create_client(url, key)
        print("✅ Supabase client initialized in db.py")
        return _supabase
    except Exception as e:
        print(f"⚠ Failed to initialize Supabase client in db.py: {e}")
        return None


# ---------- Streamers ----------

def get_or_create_streamer(
    external_id: str,
    platform: str = "youtube",
    display_name: Optional[str] = None,
    email: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Find or create streamer.

    external_id — external ID of the streamer (can use something simple for now:
    'default_youtube_streamer', later — Google / Telegram / YouTube id).
    """
    client = get_supabase()
    if client is None:
        print("🚫 Supabase not initialized in get_or_create_streamer")
        return None

    try:
        resp = (
            client.table("streamers")
            .select("*")
            .eq("external_id", external_id)
            .eq("platform", platform)
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        if rows:
            return rows[0]

        insert_data: Dict[str, Any] = {
            "external_id": external_id,
            "platform": platform,
        }
        if display_name is not None:
            insert_data["display_name"] = display_name
        if email is not None:
            insert_data["email"] = email

        resp = client.table("streamers").insert(insert_data).execute()
        rows = resp.data or []
        if rows:
            print(f"✅ Created new streamer in DB: {rows[0].get('id')}")
        return rows[0] if rows else None

    except Exception as e:
        print(f"⚠ get_or_create_streamer error: {e}")
        return None


# ---------- Subscribers ----------

def get_or_create_subscriber(
    streamer_id: str,
    external_user_id: str,
    platform: str = "youtube",
    display_name: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Find or create subscriber for a specific streamer.

    streamer_id      — id streamer (FK on streamers table)
    external_user_id — external ID of the user (e.g. YouTube channelId)
    """
    client = get_supabase()
    if client is None:
        print("🚫 Supabase not initialized in get_or_create_subscriber")
        return None

    try:
        resp = (
            client.table("subscribers")
            .select("*")
            .eq("streamer_id", streamer_id)
            .eq("external_user_id", external_user_id)
            .eq("platform", platform)
            .limit(1)
            .execute()
        )
        rows = resp.data or []
        if rows:
            return rows[0]

        insert_data: Dict[str, Any] = {
            "streamer_id": streamer_id,
            "external_user_id": external_user_id,
            "platform": platform,
        }
        if display_name is not None:
            insert_data["display_name"] = display_name

        resp = client.table("subscribers").insert(insert_data).execute()
        rows = resp.data or []
        if rows:
            print(
                f"✅ Created new subscriber in DB: {rows[0].get('id')} "
                f"(streamer_id={streamer_id})"
            )
        return rows[0] if rows else None

    except Exception as e:
        print(f"⚠ get_or_create_subscriber error: {e}")
        return None


# ---------- Messages ----------

def save_message_to_supabase(message_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Save message to public.messages table.

    Expected fields in input dict (some can be not passed):
        - id / message_id  (any one, we will convert to message_id)
        - author           (str)
        - content          (str)
        - language         (str)
        - timestamp        (float) — if not, set time.time()
        - platform         (str)   — if not, 'youtube'
        - streamer_id      (uuid|None) — optional
        - subscriber_id    (uuid|None) — optional
    """
    client = get_supabase()
    if client is None:
        print("🚫 Supabase not initialized in save_message_to_supabase")
        return None

    try:
        message_id = message_data.get("message_id") or message_data.get("id")
        author = message_data.get("author")
        content = message_data.get("content")
        language = message_data.get("language")
        ts = message_data.get("timestamp") or time.time()
        platform = message_data.get("platform") or "youtube"
        streamer_id = message_data.get("streamer_id")
        subscriber_id = message_data.get("subscriber_id")

        row: Dict[str, Any] = {
            "message_id": str(message_id) if message_id is not None else None,
            "author": author,
            "content": content,
            "language": language,
            "timestamp": float(ts),
            "platform": platform,
            "streamer_id": streamer_id,
            "subscriber_id": subscriber_id,
        }

        # убираем None, чтобы не было проблем, если какие-то поля не нужны
        insert_row = {k: v for k, v in row.items() if v is not None}

        resp = client.table("messages").insert(insert_row).execute()
        data = (resp.data or [None])[0]
        print(f"💾 Saved message to Supabase: message_id={message_id}")
        return data

    except Exception as e:
        print(f"⚠ Failed to save message to Supabase: {e}")
        return None
