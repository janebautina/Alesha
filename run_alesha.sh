#!/bin/bash

echo "🚀 Starting YouTube Live Chat Translator Bot Setup..."

# Activate Virtual Environment
echo "🔹 Activating Python virtual environment..."
source yt_env/bin/activate

# Remove old token.json (Optional - Forces re-authentication)
if [ -f "token.json" ]; then
    echo "🔹 Removing old token.json..."
    rm token.json
fi

# Authenticate with YouTube API
echo "🔹 Running authentication process..."
python3 auth.py

# Fetch the Live Stream ID and Live Chat ID
echo "🔹 Fetching current Live Stream ID and Live Chat ID..."
LIVE_STREAM_ID=$(python3 get_live_chat_id.py | grep "✅ Live Stream ID" | awk '{print $5}')
LIVE_CHAT_ID=$(python3 get_live_chat_id.py | grep "✅ Live Chat ID" | awk '{print $5}')

# Check if a valid Live Stream ID and Live Chat ID were found
if [[ -z "$LIVE_STREAM_ID" || -z "$LIVE_CHAT_ID" ]]; then
    echo "❌ No active live streams found. Please start a new YouTube live stream."
    exit 1
fi

echo "✅ Found Live Stream ID: $LIVE_STREAM_ID"
echo "✅ Found Live Chat ID: $LIVE_CHAT_ID"

# Update alesha.py with the new Live Stream ID and Live Chat ID
echo "🔹 Updating LIVE_CHAT_ID and LIVE_STREAM_ID in alesha.py..."
sed -i '' "s/LIVE_CHAT_ID = .*/LIVE_CHAT_ID = \"$LIVE_CHAT_ID\"/" alesha.py
sed -i '' "s/LIVE_STREAM_ID = .*/LIVE_STREAM_ID = \"$LIVE_STREAM_ID\"/" alesha.py

# Start the bot
echo "🚀 Starting YouTube Live Chat Translator Bot..."
python3 alesha.py
