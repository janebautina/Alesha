from google.oauth2.credentials import Credentials
import googleapiclient.discovery
import time
from langdetect import detect
import deepl
import os
import json
from openai import OpenAI
from collections import deque
import asyncio
from ws_server import broadcast_message  # ✅ import broadcast only
from supabase.client import create_client, Client

# Load config
with open("config.json") as f:
    config = json.load(f)

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
MAX_TRACKED_MESSAGES = 1000
BOT_COOLDOWN_SECONDS = 30
LIVE_CHAT_ID = None
LIVE_STREAM_ID = None
def initialize_chat_ids():
    global LIVE_CHAT_ID, LIVE_STREAM_ID
    LIVE_CHAT_ID = os.getenv("LIVE_CHAT_ID")
    LIVE_STREAM_ID = os.getenv("LIVE_STREAM_ID")

    if not LIVE_CHAT_ID:
        raise ValueError("❌ LIVE_CHAT_ID not set.")
    if not LIVE_STREAM_ID:
        raise ValueError("❌ LIVE_STREAM_ID not set.")

translator = deepl.Translator(config["DEEPL_API_KEY"], server_url="https://api-free.deepl.com")
client = OpenAI(api_key=config["OPENAI_API_KEY"])

# Initialize Supabase client
try:
    supabase: Client = create_client(config["SUPABASE_URL"], config["SUPABASE_KEY"])
except Exception as e:
    print(f"❌ Failed to initialize Supabase client: {e}")
    raise

last_request_time = 0
last_bot_post_time = 0
processed_message_ids = deque(maxlen=MAX_TRACKED_MESSAGES)
processed_message_ids_set = set()
next_page_token = None


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
                    print("⏳ Cooldown active. Skipping.")
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

                # Save message to Supabase
                save_message_to_supabase(msg_payload)

                print(f"📤 Broadcasting message to frontend: {msg_payload}")
                asyncio.run(broadcast_message(msg_payload))  # ✅ Run broadcast outside any loop

            except Exception as e:
                print(f"⚠ Error handling message from {author}: {e}")

        time.sleep(polling_interval)

    except Exception as e:
        print(f"⚠ API Error: {e}")
        time.sleep(5)

def translate_message(message, source_language):
    try:
        translated_to_russian = translator.translate_text(message, target_lang="RU").text
        if source_language == "ru":
            return translated_to_russian, translated_to_russian

        target = {
            "en": "EN-US", "fr": "FR", "es": "ES", "de": "DE",
            "it": "IT", "nl": "NL", "ru": "RU"
        }.get(source_language, "EN-US")

        translated_back = translator.translate_text(translated_to_russian, target_lang=target).text
        return translated_to_russian, translated_back
    except Exception as e:
        print(f"⚠ Translation Error: {e}")
        return message, message

def save_message_to_supabase(message_data):
    """Save message data to Supabase database"""
    try:
        data = {
            "message_id": message_data["id"],
            "author": message_data["author"],
            "content": message_data["content"],
            "language": message_data["language"],
            "timestamp": time.time(),
            "platform": "youtube"
        }
        print("📝 Inserting into Supabase:", data)
        result = supabase.table("messages").insert(data).execute()
        print(f"✅ Saved message to Supabase: {message_data['id']}")
        return result
    except Exception as e:
        print(f"⚠ Failed to save to Supabase: {e}")
        return None

def send_message_to_chat(message, prefix="🔴"):
    try:
        if not LIVE_CHAT_ID:
            raise ValueError("LIVE_CHAT_ID is not set.")

        if len(message) > 200:
            message = message[:197] + "..."

        print(f"💬 Sending to chat: {prefix} {message}")

        youtube.liveChatMessages().insert(
            part="snippet",
            body={
                "snippet": {
                    "liveChatId": LIVE_CHAT_ID,
                    "type": "textMessageEvent",
                    "textMessageDetails": {
                        "messageText": f"{prefix} {message}"
                    }
                }
            }
        ).execute()

        print(f"✅ Sent to YouTube chat.")

    except Exception as e:
        print(f"⚠ Failed to send to chat: {e}")

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

        ai_response = response.choices[0].message.content.strip()
        if len(ai_response) > 100:
            ai_response = ai_response[:97] + "..."

        last_request_time = time.time()

        ai_response_ru = translator.translate_text(ai_response, target_lang="RU").text

        if language.lower() != "ru":
            deepl_lang = {
                "en": "EN-US", "fr": "FR", "es": "ES", "de": "DE",
                "it": "IT", "nl": "NL", "ru": "RU"
            }.get(language.lower(), "EN-US")
            ai_response_original = translator.translate_text(ai_response, target_lang=deepl_lang).text
        else:
            ai_response_original = ai_response

        return ai_response_original, ai_response_ru

    except Exception as e:
        print(f"⚠ AI Response Error: {e}")
        return "AI error", "Ошибка AI"

def main():
    print("🚀 Alesha is running...")
    initialize_chat_ids()
    while True:
        get_live_chat_messages()

if __name__ == "__main__":
    main()
