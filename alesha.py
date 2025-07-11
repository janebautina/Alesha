from google.oauth2.credentials import Credentials
import googleapiclient.discovery
import time
from langdetect import detect
import deepl
import os
import json
from openai import OpenAI
from openai import OpenAIError
from collections import deque
import asyncio
import websockets
import threading
from ws_server import broadcast_message

# Load config
with open("config.json") as f:
    config = json.load(f)

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
MAX_TRACKED_MESSAGES = 1000
BOT_COOLDOWN_SECONDS = 30  # ⏳ Delay between replies to avoid spam

# Initialize API Clients
translator = deepl.Translator(config["DEEPL_API_KEY"], server_url="https://api-free.deepl.com")
client = OpenAI(api_key=config["OPENAI_API_KEY"])

# Global state
last_request_time = 0
last_bot_post_time = 0
processed_message_ids = deque(maxlen=MAX_TRACKED_MESSAGES)
processed_message_ids_set = set()
next_page_token = None
LIVE_CHAT_ID = None
LIVE_STREAM_ID = None
connected_clients = set()

# WebSocket broadcasting
async def broadcast_to_clients(message):
    if not connected_clients:
        return
    msg_json = json.dumps(message)
    await asyncio.gather(*(ws.send(msg_json) for ws in connected_clients))

async def websocket_handler(websocket, path):
    connected_clients.add(websocket)
    try:
        async for _ in websocket:
            pass
    finally:
        connected_clients.remove(websocket)

def start_websocket_server():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    start_server = websockets.serve(websocket_handler, "localhost", 8765)
    loop.run_until_complete(start_server)
    print("🌐 WebSocket server started on ws://localhost:8765")
    loop.run_forever()

def start_background_services():
    threading.Thread(target=start_websocket_server, daemon=True).start()

def initialize_chat_ids():
    global LIVE_CHAT_ID, LIVE_STREAM_ID
    LIVE_CHAT_ID = os.getenv("LIVE_CHAT_ID")
    LIVE_STREAM_ID = os.getenv("LIVE_STREAM_ID")

    if not LIVE_CHAT_ID:
        raise ValueError("❌ ERROR: LIVE_CHAT_ID is not set.")
    if not LIVE_STREAM_ID:
        raise ValueError("❌ ERROR: LIVE_STREAM_ID is not set.")

def get_authenticated_service():
    creds = Credentials.from_authorized_user_file(config["TOKEN_FILE"], SCOPES)
    return googleapiclient.discovery.build("youtube", "v3", credentials=creds)

youtube = get_authenticated_service()

def detect_language(text):
    try:
        return detect(text)
    except:
        return "unknown"

def get_live_chat_messages():
    global next_page_token, processed_message_ids, processed_message_ids_set
    global last_bot_post_time

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
                print(f"⏭️ Skipped Russian message from {author}: '{message}'")
                continue

            try:
                now = time.time()
                if now - last_bot_post_time < BOT_COOLDOWN_SECONDS:
                    print("⏳ Cooldown active. Skipping reply to avoid spamming.")
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
                #asyncio.run(broadcast_to_clients(msg_payload))
                asyncio.create_task(broadcast_message(msg_payload))

            except Exception as e:
                print(f"⚠ Error handling message from {author}: {e}")

        time.sleep(polling_interval)

    except Exception as e:
        print(f"⚠ API Error while fetching messages: {e}")
        time.sleep(5)

def translate_message(message, source_language):
    language_mapping = {
        "en": "EN-US", "fr": "FR", "es": "ES", "de": "DE",
        "it": "IT", "nl": "NL", "ru": "RU"
    }
    target_lang = language_mapping.get(source_language, "EN-US")

    try:
        translated_to_russian = translator.translate_text(message, target_lang="RU").text
        if source_language == "ru":
            return translated_to_russian, translated_to_russian
        translated_back = translator.translate_text(translated_to_russian, target_lang=target_lang).text
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

        full_message = f"{prefix} {message}"
        print(f"💬 Sending to chat: {full_message}")

        request_body = {
            "snippet": {
                "liveChatId": LIVE_CHAT_ID,
                "type": "textMessageEvent",
                "textMessageDetails": {
                    "messageText": full_message
                }
            }
        }

        youtube.liveChatMessages().insert(
            part="snippet",
            body=request_body
        ).execute()

        print(f"✅ Sent message: {full_message}")

    except Exception as e:
        print(f"⚠ Failed to send message to chat: {e}")
        print(f"⚠ Request Body: {json.dumps(request_body, indent=2)}")

def generate_ai_response(message, language):
    global last_request_time

    try:
        time_since_last_request = time.time() - last_request_time
        if time_since_last_request < 2:
            time.sleep(2 - time_since_last_request)

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": ( "You are Alesha — a beautiful, sexy, and brilliant woman with deep knowledge of psychology. "
                                "You're confident, charming, and irresistible. "
                                "Reply briefly, clearly, and helpfully in the same language the user spoke. "
                                "Keep replies under 100 characters. Never repeat the user's message.")
                },
                {
                    "role": "user",
                    "content": message
                }
            ]
        )

        ai_response = response.choices[0].message.content.strip()
        if len(ai_response) > 200:
            ai_response = ai_response[:197] + "..."

        last_request_time = time.time()

        ai_response_ru = translator.translate_text(ai_response, target_lang="RU").text

        language_mapping = {
            "en": "EN-US", "fr": "FR", "es": "ES", "de": "DE",
            "it": "IT", "nl": "NL", "ru": "RU"
        }
        deepl_lang = language_mapping.get(language.lower(), "EN-US")

        if language.lower() != "ru":
            ai_response_original = translator.translate_text(ai_response, target_lang=deepl_lang).text
        else:
            ai_response_original = ai_response

        return ai_response_original, ai_response_ru

    except Exception as e:
        print(f"⚠ AI Response Error: {e}")
        return "Ошибка AI", "AI Error"

def main():
    print("🚀 YouTube Live Chat Translator Bot is running...")
    initialize_chat_ids()
    start_background_services()
    while True:
        get_live_chat_messages()

if __name__ == "__main__":
    main()
