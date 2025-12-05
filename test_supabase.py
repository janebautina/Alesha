#!/usr/bin/env python3
"""
test_supabase.py — Simple diagnostics for Supabase

- Verifies Supabase connection
- Verifies that the `messages` table is accessible (critical)
- Tries to query other tables if they exist (non-critical)
- Inserts a test row into `messages` and then deletes it
"""

from supabase.client import Client
from db import get_supabase


def format_error(e) -> str:
    """
    Nicely format Supabase / PostgREST errors.

    Sometimes e.args[0] is a dict with keys: message, code, etc.
    We turn that into a readable string.
    """
    if hasattr(e, "args") and e.args:
        first = e.args[0]
        if isinstance(first, dict):
            msg = first.get("message", "Unknown error")
            code = first.get("code")
            if code == "PGRST205":
                # "Table not found in schema cache"
                return f"{msg} (table probably does not exist yet)"
            if code:
                return f"{msg} (code={code})"
            return msg
    # Fallback — just convert to string
    return str(e)


def test_table(supabase: Client, table_name: str) -> None:
    """
    Try a simple `select * limit 1` on the given table.

    If it fails, we print a soft info message instead of crashing.
    """
    try:
        result = supabase.table(table_name).select("*").limit(1).execute()
        print(
            f"✅ Table '{table_name}' is accessible "
            f"({len(result.data)} sample row(s))."
        )
    except Exception as e:
        err_text = format_error(e)
        print(f"ℹ️  Table '{table_name}' is not available yet: {err_text}")


def test_supabase_connection() -> bool:
    """
    Main test function:
    - gets a shared Supabase client from db.py
    - checks main and optional tables
    - does a test insert/delete in `messages`
    """
    try:
        supabase = get_supabase()
        if supabase is None:
            print("❌ Could not initialize Supabase client (check config.json).")
            return False

        print("🔗 Checking connection and tables...")

        # 1) messages — main table, should exist
        try:
            test_table(supabase, "messages")
        except Exception as e:
            # If `messages` does not work, this is critical
            print(
                f"❌ Critical: 'messages' table check failed: {format_error(e)}"
            )
            return False

        # 2) Optional tables — do not break if they are missing
        print("\n🔍 Checking optional tables (if they exist):")
        for tbl in ["streamers", "streamer_settings", "subscribers"]:
            test_table(supabase, tbl)

        # --- Test insert into messages ---
        print("\n✏️ Inserting test message into 'messages'...")

        test_message_id = "test_123"

        # Clean up any previous test row if it exists
        try:
            supabase.table("messages").delete().eq(
                "message_id", test_message_id
            ).execute()
        except Exception:
            # If delete fails, it is fine (row may not exist)
            pass

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
        supabase.table("messages").delete().eq(
            "message_id", test_message_id
        ).execute()
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
        print(
            "🚨 Tests failed. Check the error above and your config.json / database schema."
        )
