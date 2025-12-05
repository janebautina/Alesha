#!/usr/bin/env python3
"""
Standalone Supabase connection test.

- Loads config.json implicitly via db.get_supabase()
- Verifies connection to Supabase
- Checks that the messages table is accessible
- Inserts a test row into messages and then deletes it
"""

from typing import Optional
from db import get_supabase


def test_standalone_supabase() -> bool:
    client = get_supabase()
    if client is None:
        print("🚫 Supabase client is not initialized. Check config.json (SUPABASE_URL / SUPABASE_KEY).")
        return False

    try:
        print("🔗 Testing connection to Supabase using db.get_supabase()...")

        # 1) Simple SELECT from messages
        result = client.table("messages").select("*").limit(1).execute()
        print(f"✅ 'messages' table is accessible. Sample row count: {len(result.data)}")

        # 2) Insert a test message
        test_message_id = "test_standalone_123"

        # Clean up any previous test row with the same message_id (idempotent)
        try:
            client.table("messages").delete().eq("message_id", test_message_id).execute()
        except Exception:
            # If delete fails, we ignore it here
            pass

        test_data = {
            "message_id": test_message_id,
            "author": "Standalone Test User",
            "content": "This is a standalone test message",
            "language": "en",
            "timestamp": 1234567890.0,
            "platform": "youtube",
        }

        insert_result = client.table("messages").insert(test_data).execute()
        print("✅ Test message inserted successfully!")
        print(f"🆔 Inserted row: {insert_result.data}")

        # 3) Clean up test data
        print("🧹 Cleaning up test data...")
        client.table("messages").delete().eq("message_id", test_message_id).execute()
        print("✅ Test data cleaned up!")

        return True

    except Exception as e:
        print(f"❌ Standalone Supabase test failed: {e}")
        return False


if __name__ == "__main__":
    ok = test_standalone_supabase()
    if ok:
        print("🎉 Standalone Supabase test completed successfully.")
    else:
        print("🚨 Standalone test failed. Check logs above and your database setup.")
