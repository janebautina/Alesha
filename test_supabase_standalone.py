#!/usr/bin/env python3
"""
Standalone Supabase connection test
"""

import json
from supabase.client import create_client

# Load config
with open("config.json") as f:
    config = json.load(f)

url = config["SUPABASE_URL"]
key = config["SUPABASE_KEY"]

print(f"🔗 Testing connection to: {url}")
print(f"🔑 Using key: {key[:10]}...")

supabase = create_client(url, key)

# Test fetching or inserting
try:
    result = supabase.table("messages").select("*").limit(1).execute()
    print("✅ Supabase connected. Sample data:", result.data)
    
    # Test inserting a sample message
    test_data = {
        "message_id": "test_standalone_123",
        "author": "Test User",
        "content": "This is a standalone test message",
        "language": "en",
        "timestamp": 1234567890.0,
        "platform": "youtube"
    }
    
    insert_result = supabase.table("messages").insert(test_data).execute()
    print("✅ Test message inserted successfully!")
    
    # Clean up test data
    supabase.table("messages").delete().eq("message_id", "test_standalone_123").execute()
    print("✅ Test data cleaned up!")
    
except Exception as e:
    print("❌ Test Supabase call failed:", e) 