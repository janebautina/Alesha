# Unified Alesha with WebSocket Server Integration
import asyncio
import json
import os
import time
from collections import deque

from google.oauth2.credentials import Credentials
import googleapiclient.discovery
import deepl
from langdetect import detect
from openai import OpenAI
from supabase.client import create_client, Client
import websockets

# Config loading
with open("config.json") as f:
    config = json.load(f)

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
MAX_TRACKED_MESSAGES = 1000
BOT_COOLDOWN_SECONDS = 30
LIVE_CHAT_ID = os.getenv("LIVE_CHAT_ID")
LIVE_STREAM_ID = os.getenv("LIVE_STREAM_ID")
connected_clients = set()

# Globals
translator = deepl.Translator(config["DEEPL_API_KEY"], server_url="https://api-free.deepl.com")
client = OpenAI(api_key=config["OPENAI_API_KEY"])
supabase: Client = create_client(config["SUPABASE_URL"], config["SUPABASE_KEY"])
youtube = googleapiclient.discovery.build("youtube", "v3", credentials=Credentials.from_authorized_user_file(config["TOKEN_FILE"], SCOPES))

last_request_time = 0
last_bot_post_time = 0
processed_message_ids = deque(maxlen=MAX_TRACKED_MESSAGES)
processed_message_ids_set = set()
next_page_token = None

def initialize_chat_ids():
    """Initialize LIVE_CHAT_ID and LIVE_STREAM_ID from environment variables."""
    global LIVE_CHAT_ID, LIVE_STREAM_ID
    LIVE_CHAT_ID = os.getenv("LIVE_CHAT_ID")
    LIVE_STREAM_ID = os.getenv("LIVE_STREAM_ID")
    return LIVE_CHAT_ID, LIVE_STREAM_ID

# WebSocket handler
async def handler(websocket):
    print("🔌 New client connected")
    connected_clients.add(websocket)
    try:
        while True:
            await asyncio.sleep(10)
    except websockets.exceptions.ConnectionClosed:
        print("❌ Client disconnected")
    finally:
        connected_clients.remove(websocket)

async def broadcast_message(message_dict):
    if connected_clients:
        message = json.dumps(message_dict)
        print(f"📡 Broadcasting to {len(connected_clients)} clients: {message}")
        await asyncio.gather(*(client.send(message) for client in connected_clients), return_exceptions=True)
    else:
        print("⚠️ No connected clients to broadcast to.")

def detect_language(text):
    try:
        return detect(text)
    except:
        return "unknown"

def _extract_deepl_text(result):
    """Extract text from DeepL translation result (handles both single TextResult and list)."""
    if isinstance(result, list):
        return result[0].text if result else ""
    return result.text

def translate_message(message, source_language):
    try:
        result_ru = translator.translate_text(message, target_lang="RU")
        translated_to_russian = _extract_deepl_text(result_ru)
        if source_language == "ru":
            return translated_to_russian, translated_to_russian

        target = {
            "en": "EN-US", "fr": "FR", "es": "ES", "de": "DE",
            "it": "IT", "nl": "NL", "ru": "RU"
        }.get(source_language, "EN-US")

        result_back = translator.translate_text(translated_to_russian, target_lang=target)
        translated_back = _extract_deepl_text(result_back)
        return translated_to_russian, translated_back
    except Exception as e:
        print(f"⚠ Translation Error: {e}")
        return message, message

def send_message_to_chat(message, prefix="🔴"):
    try:
        if not LIVE_CHAT_ID:
            raise ValueError("LIVE_CHAT_ID is not set.")
        if len(message) > 200:
            message = message[:197] + "..."

        youtube.liveChatMessages().insert(
            part="snippet",
            body={
                "snippet": {
                    "liveChatId": LIVE_CHAT_ID,
                    "type": "textMessageEvent",
                    "textMessageDetails": {"messageText": f"{prefix} {message}"}
                }
            }
        ).execute()
        print(f"✅ Sent to YouTube chat.")
    except Exception as e:
        print(f"⚠ Failed to send to chat: {e}")

def save_message_to_supabase(message_data):
    try:
        data = {
            "message_id": message_data["id"],
            "author": message_data["author"],
            "content": message_data["content"],
            "language": message_data["language"],
            "timestamp": time.time(),
            "platform": "youtube"
        }
        result = supabase.table("messages").insert(data).execute()
        print(f"✅ Saved message to Supabase: {message_data['id']}")
        return result
    except Exception as e:
        print(f"⚠ Failed to save to Supabase: {e}")
        return None

def generate_ai_response(message, language):
    global last_request_time
    try:
        if time.time() - last_request_time < 2:
            time.sleep(2)

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are Alesha — a beautiful, sexy, and brilliant woman with deep knowledge of psychology. "
                        "You're confident, charming, and irresistible. "
                        "Reply briefly, clearly, and helpfully in the same language the user spoke. "
                        "Keep replies under 100 characters. Never repeat the user's message."
                    )
                },
                {"role": "user", "content": message}
            ]
        )

        content = response.choices[0].message.content
        if content is None:
            return "AI error", "Ошибка AI"
        
        ai_response = content.strip()
        if len(ai_response) > 100:
            ai_response = ai_response[:97] + "..."

        last_request_time = time.time()

        result_ru = translator.translate_text(ai_response, target_lang="RU")
        ai_response_ru = _extract_deepl_text(result_ru)

        if language.lower() != "ru":
            deepl_lang = {
                "en": "EN-US", "fr": "FR", "es": "ES", "de": "DE",
                "it": "IT", "nl": "NL", "ru": "RU"
            }.get(language.lower(), "EN-US")
            result_orig = translator.translate_text(ai_response, target_lang=deepl_lang)
            ai_response_original = _extract_deepl_text(result_orig)
        else:
            ai_response_original = ai_response

        return ai_response_original, ai_response_ru

    except Exception as e:
        print(f"⚠ AI Response Error: {e}")
        return "AI error", "Ошибка AI"

async def fetch_and_process_messages():
    global next_page_token, last_bot_post_time
    while True:
        try:
            request = youtube.liveChatMessages().list(
                liveChatId=LIVE_CHAT_ID,
                part="snippet,authorDetails",
                pageToken=next_page_token
            )
            response = request.execute()
            next_page_token = response.get("nextPageToken")
            polling_interval = response.get("pollingIntervalMillis", 2000) / 1000.0

            for item in response.get("items", []):
                msg_id = item["id"]
                if msg_id in processed_message_ids_set:
                    continue

                if len(processed_message_ids) >= MAX_TRACKED_MESSAGES:
                    old_id = processed_message_ids.popleft()
                    processed_message_ids_set.discard(old_id)

                processed_message_ids.append(msg_id)
                processed_message_ids_set.add(msg_id)

                message = item["snippet"].get("displayMessage", "[Non-text message]")
                author = item["authorDetails"]["displayName"]
                detected_lang = detect_language(message)

                if detected_lang == "ru":
                    continue

                now = time.time()
                if now - last_bot_post_time < BOT_COOLDOWN_SECONDS:
                    continue

                translated_msg, _ = translate_message(message, detected_lang)
                ai_response_original, ai_response_ru = generate_ai_response(message, detected_lang)

                send_message_to_chat(f"💬 AI Reply: {ai_response_original} | {ai_response_ru}")
                last_bot_post_time = now

                msg_payload = {
                    "id": msg_id,
                    "author": author,
                    "content": ai_response_original,
                    "language": detected_lang
                }

                save_message_to_supabase(msg_payload)
                await broadcast_message(msg_payload)

            await asyncio.sleep(polling_interval)

        except Exception as e:
            print(f"⚠ API Error: {e}")
            await asyncio.sleep(5)

async def main():
    print("🚀 Alesha is running with integrated WebSocket server")
    async with websockets.serve(handler, "localhost", 8765):
        await fetch_and_process_messages()

if __name__ == "__main__":
    asyncio.run(main())
