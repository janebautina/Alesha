#!/usr/bin/env python3
"""
check_messages.py — утилита для просмотра последних сообщений из Supabase

Показывает последние N строк из таблицы public.messages.
"""

from typing import Optional
from db import get_supabase  # ✅ используем общий Supabase-клиент


def show_recent_messages(limit: int = 20) -> None:
    client = get_supabase()
    if client is None:
        print("🚫 Supabase client is not initialized. Check config.json (SUPABASE_URL / SUPABASE_KEY).")
        return

    try:
        response = (
            client
            .table("messages")
            .select("*")
            .order("timestamp", desc=True)
            .limit(limit)
            .execute()
        )

        data = response.data or []
        print(f"\n🗂 Found {len(data)} row(s) in 'messages' table (showing up to {limit}):\n")

        for row in data:
            msg_id = row.get("message_id")
            author = row.get("author")
            lang = row.get("language")
            platform = row.get("platform")
            ts = row.get("timestamp")
            content = (row.get("content") or "")[:80]

            print(
                f"- id={msg_id} | author={author} | lang={lang} | platform={platform} | "
                f"ts={ts} | content={repr(content)}"
            )

    except Exception as e:
        print(f"⚠ Error querying Supabase: {e}")


if __name__ == "__main__":
    show_recent_messages()
