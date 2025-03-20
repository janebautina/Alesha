import googleapiclient.discovery
from google.oauth2.credentials import Credentials
import json

# Load config
with open("config.json") as f:
    config = json.load(f)

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]

def get_authenticated_service():
    """Authenticate and return the YouTube API service."""
    creds = Credentials.from_authorized_user_file(config["TOKEN_FILE"], SCOPES)
    youtube = googleapiclient.discovery.build("youtube", "v3", credentials=creds)
    return youtube

def get_live_stream_info():
    """Fetch the Live Chat ID and Stream ID for the current live broadcast."""
    youtube = get_authenticated_service()

    request = youtube.liveBroadcasts().list(
        part="id,snippet",
        broadcastStatus="active"
    )
    response = request.execute()

    if "items" in response and len(response["items"]) > 0:
        live_chat_id = response["items"][0]["snippet"]["liveChatId"]
        live_stream_id = response["items"][0]["id"]
        stream_title = response["items"][0]["snippet"]["title"]

        print(f"✅ Live Stream Title: {stream_title}")
        print(f"✅ Live Stream ID: {live_stream_id}")
        print(f"✅ Live Chat ID: {live_chat_id}")

        return live_stream_id, live_chat_id
    else:
        print("❌ No active live streams found.")
        return None, None

if __name__ == "__main__":
    stream_id, chat_id = get_live_stream_info()
    if stream_id and chat_id:
        print(f"🔹 Use these IDs in your bot:")
        print(f"   🆔 Live Stream ID: {stream_id}")
        print(f"   💬 Live Chat ID: {chat_id}")