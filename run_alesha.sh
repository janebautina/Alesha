#!/bin/bash

echo "🚀 Starting YouTube Live Chat Translator Bot Setup..."

# Activate Virtual Environment
echo "🔹 Activating Python virtual environment..."
source yt_env/bin/activate || {
  echo "❌ Failed to activate virtual environment."
  exit 1
}

# Remove old token.json (forces re-authentication if needed)
if [[ -f "token.json" ]]; then
  echo "🔹 Removing old token.json..."
  rm token.json
fi

# Authenticate with YouTube API
echo "🔹 Running authentication process..."
python3 auth.py || {
  echo "❌ Authentication failed. Check your credentials."
  exit 1
}

# Fetch Live Stream ID and Live Chat ID (single execution)
echo "🔹 Fetching current Live Stream ID and Live Chat ID..."
LIVE_INFO=$(python3 get_live_chat_id.py)

LIVE_STREAM_ID=$(echo "$LIVE_INFO" | grep "✅ Live Stream ID" | awk '{print $5}')
LIVE_CHAT_ID=$(echo "$LIVE_INFO" | grep "✅ Live Chat ID" | awk '{print $5}')

# Check if IDs were fetched
if [[ -z "$LIVE_STREAM_ID" || -z "$LIVE_CHAT_ID" ]]; then
  echo "❌ No active live streams found. Please start a new YouTube live stream."
  exit 1
fi

echo "✅ Found Live Stream ID: $LIVE_STREAM_ID"
echo "✅ Found Live Chat ID: $LIVE_CHAT_ID"

# Pass Live Chat ID and Stream ID as environment variables
echo "💬 Starting YouTube Live Chat Translator Bot..."
LIVE_CHAT_ID="$LIVE_CHAT_ID" LIVE_STREAM_ID="$LIVE_STREAM_ID" python3 alesha.py