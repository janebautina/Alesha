#!/usr/bin/env python3
"""
Test script to verify Supabase connection and table setup

- Проверяет подключение к Supabase
- Проверяет доступность таблицы messages
- Пытается прочитать другие таблицы (если они есть), но не падает, если их нет
- Вставляет тестовое сообщение в messages и удаляет его
"""

import json
from supabase.client import create_client, Client

# Load config
with open("config.json") as f:
    config = json.load(f)


def format_error(e) -> str:
    """Красиво отформатировать ошибку Supabase/PostgREST."""
    # Иногда e.args[0] — это dict с ключами message/code/...
    if hasattr(e, "args") and e.args:
        first = e.args[0]
        if isinstance(first, dict):
            msg = first.get("message", "Unknown error")
            code = first.get("code")
            if code == "PGRST205":
                # Специально для 'table not found in schema cache'
                return f"{msg} (table probably does not exist yet)"
            if code:
                return f"{msg} (code={code})"
            return msg
    # Фоллбек — обычная строка
    return str(e)


def test_table(supabase: Client, table_name: str) -> None:
    """Проверить, что таблица доступна (простой select limit 1)."""
    try:
        result = supabase.table(table_name).select("*").limit(1).execute()
        print(f"✅ Table '{table_name}' is accessible ({len(result.data)} sample row(s)).")
    except Exception as e:
        err_text = format_error(e)
        # Для опциональных таблиц сообщение будет мягким
        print(f"ℹ️  Table '{table_name}' is not available yet: {err_text}")


def test_supabase_connection() -> bool:
    """Test Supabase connection and basic CRUD on messages."""
    try:
        # Initialize Supabase client
        supabase: Client = create_client(config["SUPABASE_URL"], config["SUPABASE_KEY"])

        print("🔗 Checking connection and tables...")

        # 1) messages — основная таблица, она ДОЛЖНА существовать
        try:
            test_table(supabase, "messages")
        except Exception as e:
            # Если messages реально нет — это критичная ошибка
            print(f"❌ Critical: 'messages' table check failed: {format_error(e)}")
            return False

        # 2) Другие таблицы — опционально, не ломаемся если их нет
        print("\n🔍 Checking optional tables (if they exist):")
        for tbl in ["streamers", "streamer_settings", "subscribers"]:
            test_table(supabase, tbl)

        # --- Test insert into messages ---
        print("\n✏️ Inserting test message into 'messages'...")

        test_message_id = "test_123"

        # На всякий случай удалим старый тест, если он остался
        try:
            supabase.table("messages").delete().eq("message_id", test_message_id).execute()
        except Exception:
            # Если удаление упало, не страшно — значит, строки может и не быть
            pass

        # ВАЖНО: здесь только те поля, которые реально есть в твоей messages
        test_data = {
            "message_id": test_message_id,
            "author": "Test User",
            "content": "This is a test message",
            "language": "en",
            "timestamp": 1234567890.0,
            "platform": "youtube",
        }

        insert_result = supabase.table("messages").insert(test_data).execute()
        print("✅ Test message inserted successfully!")
        print(f"🆔 Inserted row: {insert_result.data}")

        # Clean up test data
        print("🧹 Cleaning up test data...")
        supabase.table("messages").delete().eq("message_id", test_message_id).execute()
        print("✅ Test data cleaned up!")

        return True

    except Exception as e:
        print(f"❌ Supabase connection or test failed: {format_error(e)}")
        return False


if __name__ == "__main__":
    print("🔍 Testing Supabase connection...")
    ok = test_supabase_connection()
    if ok:
        print("🎉 All tests completed successfully.")
    else:
        print("🚨 Tests failed. Check the error above and your config.json / database schema.")
