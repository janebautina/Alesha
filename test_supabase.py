#!/usr/bin/env python3
"""
Test script to verify Supabase connection and table setup
"""

import json
from supabase.client import create_client, Client

# Load config
with open("config.json") as f:
    config = json.load(f)

def test_supabase_connection():
    """Test Supabase connection and table access"""
    try:
        # Initialize Supabase client
        supabase: Client = create_client(config["SUPABASE_URL"], config["SUPABASE_KEY"])
        
        # Test connection by trying to select from messages table
        result = supabase.table("messages").select("*").limit(1).execute()
        
        print("✅ Supabase connection successful!")
        print(f"📊 Found {len(result.data)} messages in database")
        
        # Test inserting a sample message
        test_data = {
            "message_id": "test_123",
            "author": "Test User",
            "content": "This is a test message",
            "language": "en",
            "timestamp": 1234567890.0,
            "platform": "youtube"
        }
        
        insert_result = supabase.table("messages").insert(test_data).execute()
        print("✅ Test message inserted successfully!")
        
        # Clean up test data
        supabase.table("messages").delete().eq("message_id", "test_123").execute()
        print("✅ Test data cleaned up!")
        
        return True
        
    except Exception as e:
        print(f"❌ Supabase connection failed: {e}")
        return False

if __name__ == "__main__":
    print("🔍 Testing Supabase connection...")
    test_supabase_connection() 