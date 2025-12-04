# Unified Alesha with WebSocket Server Integration
import asyncio
import json
import os
import random
import time
from collections import deque

from google.oauth2.credentials import Credentials
import googleapiclient.discovery
import deepl
from langdetect import detect
from openai import OpenAI
import websockets

from persona import get_system_prompt_for_lang
from db import save_message_to_supabase  # 🔹 новый импорт

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
translator = deepl.Translator(
    config["DEEPL_API_KEY"],
    server_url="https://api-free.deepl.com"
)
client = OpenAI(api_key=config["OPENAI_API_KEY"])

youtube = googleapiclient.discovery.build(
    "youtube",
    "v3",
    credentials=Credentials.from_authorized_user_file(config["TOKEN_FILE"], SCOPES),
)

last_request_time = 0
last_bot_post_time = 0
processed_message_ids = deque(maxlen=MAX_TRACKED_MESSAGES)
processed_message_ids_set = set()
next_page_token = None

# counter for "super-fun" mode
message_counter = 0
next_funny_in = random.randint(3, 5)

# like counter
seen_authors = set()
last_like_check_time = 0
last_like_count = None
LIKE_CHECK_INTERVAL = 60  # сек, можно поменять

LANG_NAME_MAP = {
    "en": "English",
    "ru": "Russian",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "nl": "Dutch",
    "pt": "Portuguese",
    "tr": "Turkish",
    "pl": "Polish",
    "uk": "Ukrainian",
    "cs": "Czech",
    "ro": "Romanian",
    "bg": "Bulgarian",
    "hu": "Hungarian",
    "sv": "Swedish",
    "fi": "Finnish",
    "da": "Danish",
}


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
        await asyncio.gather(
            *(client.send(message) for client in connected_clients),
            return_exceptions=True,
        )
    else:
        print("⚠️ No connected clients to broadcast to.")


def detect_language(text):
    try:
        return detect(text)
    except Exception:
        return "unknown"


def _extract_deepl_text(result):
    """Extract text from DeepL translation result (handles both single TextResult and list)."""
    if isinstance(result, list):
        return result[0].text if result else ""
    return result.text


def translate_message(message, source_language):
    """
    Translate message to Russian (for context / UI) and back into original language via RU.
    For Alesha persona we primarily care about the Russian translation as context.
    """
    try:
        result_ru = translator.translate_text(message, target_lang="RU")
        translated_to_russian = _extract_deepl_text(result_ru)
        if source_language == "ru":
            return translated_to_russian, translated_to_russian

        target = {
            "en": "EN-US",
            "fr": "FR",
            "es": "ES",
            "de": "DE",
            "it": "IT",
            "nl": "NL",
            "ru": "RU",
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
                    "textMessageDetails": {
                        "messageText": f"{prefix} {message}"
                    },
                }
            },
        ).execute()
        print(f"✅ Sent to YouTube chat.")
    except Exception as e:
        print(f"⚠ Failed to send to chat: {e}")


"""
The old generate_ai_response is currently commented out.
If you decide to bring it back, it’s better to use db.py as well, 
rather than accessing Supabase directly from here.
"""

def get_current_like_count():
    """Fetch current like count for the active live stream."""
    try:
        if not LIVE_STREAM_ID:
            return None

        response = youtube.videos().list(
            part="statistics",
            id=LIVE_STREAM_ID,
        ).execute()

        items = response.get("items", [])
        if not items:
            return None

        stats = items[0].get("statistics", {})
        like_count = int(stats.get("likeCount", 0))
        return like_count
    except Exception as e:
        print(f"⚠ Failed to fetch like count: {e}")
        return None


def generate_alesha_welcome(author_name: str, source_language: str) -> str:
    """
    Generate a short greeting for a NEW viewer in their language (if known)
    """
    global last_request_time

    try:
        lang_code = (source_language or "unknown").lower()
        lang_name = LANG_NAME_MAP.get(lang_code, "Unknown language")

        user_prompt = f"""
            A new viewer has just written their first message in the livestream chat.
            Nickname: "{author_name}"

            Your task:
            - Greet them warmly in their language (language code: {lang_code}, approx: {lang_name}).
            - 1–2 short sentences max.
            - Make them feel welcome and part of the community.
            - You may address them by nickname.
            - Do NOT say you are a bot or AI.
            - Do NOT use phrases like "how can I help", "how may I help", "how can I be useful".
            If language code is "unknown", reply in a fun mix of simple Russian and English.
            """

        system_prompt = get_system_prompt_for_lang(lang_code)

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            temperature=0.7,
            max_tokens=60,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        content = response.choices[0].message.content
        if not content:
            return f"Добро пожаловать, {author_name}! 💫"

        text = content.strip()
        if len(text) > 160:
            text = text[:157] + "..."

        last_request_time = time.time()
        return text

    except Exception as e:
        print(f"⚠ AI Welcome Error: {e}")
        return f"Рада видеть тебя в чате, {author_name}! ✨"


def generate_alesha_reply(
    original_message: str,
    translated_ru: str,
    source_language: str,
    author_name: str,
    joke_mode: bool = False,
) -> str:
    """
    Generate a short, lively reply from Alesha in the SAME LANGUAGE as the sender.
    Uses SYSTEM_PROMPT_ALESHA persona.
    """
    global last_request_time

    try:
        # simple rate limiting to avoid hammering OpenAI
        if time.time() - last_request_time < 2:
            time.sleep(2)

        lang_code = (source_language or "unknown").lower()
        lang_name = LANG_NAME_MAP.get(lang_code, "Unknown language")

        style_line = (
            "Сделай ответ особенно ярким, игривым, можно чуть более шуточным, но без кринжа. "
            "Сейчас режим супер-весёлого тамады."
            if joke_mode
            else "Сделай ответ дружелюбным, тёплым, без лишнего кринжа. Лёгкий юмор допустим."
        )

        user_prompt = f"""
            Original message (language code: {lang_code}, approx: {lang_name}):
            {original_message}

            Russian translation (for your understanding):
            {translated_ru}

            Author nickname in chat: {author_name}

            Your task:
            - Reply in the SAME LANGUAGE as the original message (language code: {lang_code}, approx: {lang_name}).
            - 1–3 short sentences max.
            - You can briefly reflect the meaning (like a playful paraphrase) and add emotion/banter.
            - Do NOT say you are a bot or AI.
            - Do NOT use phrases like "how can I help", "how may I help", "how can I be useful".
            - {style_line}
            If language code is "unknown", reply in a fun mix of Russian and English.
        """

        system_prompt = get_system_prompt_for_lang(lang_code)

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            temperature=0.9 if joke_mode else 0.6,
            max_tokens=80,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        content = response.choices[0].message.content
        if not content:
            return "Alesha got a little shy, send another message 😉"

        reply = content.strip()
        if len(reply) > 180:
            reply = reply[:177] + "..."

        last_request_time = time.time()
        return reply

    except Exception as e:
        print(f"⚠ AI Tamada Error: {e}")
        return "Alesha glitched for a sec, next message please ✨"


async def fetch_and_process_messages():
    global next_page_token, last_bot_post_time, message_counter, next_funny_in
    global last_like_check_time, last_like_count, seen_authors

    while True:
        try:
            # 🔁 Периодически проверяем лайки и благодарим за новые
            now = time.time()
            if now - last_like_check_time > LIKE_CHECK_INTERVAL:
                like_count = get_current_like_count()
                last_like_check_time = now

                if like_count is not None:
                    if last_like_count is None:
                        # первая инициализация — просто запоминаем
                        last_like_count = like_count
                    elif like_count > last_like_count:
                        diff = like_count - last_like_count
                        last_like_count = like_count

                        if like_count in (10, 25, 50, 100):
                            text = (
                                f"✨ Маленький юбилей — {like_count} лайков! "
                                f"Вы делаете этот стрим живым, люблю вас."
                            )
                        elif diff == 1:
                            text = f"💗 Вижу новый лайк, спасибо вам! Сейчас их уже {like_count}."
                        elif diff < 5:
                            text = f"💗 Спасибо за ваши лайки! Ещё +{diff}, теперь их {like_count}."
                        else:
                            text = (
                                f"✨ Вы засыпали стрим лайками (+{diff})! "
                                f"Уже {like_count}, я в восторге."
                            )

                        send_message_to_chat(text, prefix="💖")

            # 📥 Read new messages from YouTube Live Chat
            request = youtube.liveChatMessages().list(
                liveChatId=LIVE_CHAT_ID,
                part="snippet,authorDetails",
                pageToken=next_page_token,
            )
            response = request.execute()
            next_page_token = response.get("nextPageToken")
            polling_interval = response.get(
                "pollingIntervalMillis", 2000
            ) / 1000.0

            for item in response.get("items", []):
                msg_id = item["id"]
                if msg_id in processed_message_ids_set:
                    continue

                if len(processed_message_ids) >= MAX_TRACKED_MESSAGES:
                    old_id = processed_message_ids.popleft()
                    processed_message_ids_set.discard(old_id)

                processed_message_ids.append(msg_id)
                processed_message_ids_set.add(msg_id)

                message = item["snippet"].get(
                    "displayMessage", "[Non-text message]"
                )
                author = item["authorDetails"]["displayName"]
                detected_lang = detect_language(message)

                # 👋 New person in chat? Welcome them once
                is_new_author = author not in seen_authors
                if is_new_author:
                    seen_authors.add(author)
                    welcome_text = generate_alesha_welcome(
                        author_name=author,
                        source_language=detected_lang,
                    )
                    send_message_to_chat(welcome_text, prefix="🌟")

                now = time.time()
                if now - last_bot_post_time < BOT_COOLDOWN_SECONDS:
                    continue

                # Translate to Russian for context / logs / UI
                translated_ru, _ = translate_message(message, detected_lang)

                # increment counter and decide if this is super-fun turn
                message_counter += 1
                is_funny = message_counter >= next_funny_in

                reply_text = generate_alesha_reply(
                    original_message=message,
                    translated_ru=translated_ru,
                    source_language=detected_lang,
                    author_name=author,
                    joke_mode=is_funny,
                )

                prefix = "🎉" if is_funny else "💬"
                send_message_to_chat(reply_text, prefix=prefix)
                last_bot_post_time = now

                # reset funny counter if we just did a super-funny one
                if is_funny:
                    message_counter = 0
                    next_funny_in = random.randint(3, 5)

                msg_payload = {
                    "id": msg_id,
                     "author": author,
                     "content": message,      # ← сохраняем ОРИГИНАЛЬНОЕ сообщение зрителя
                      "language": detected_lang,
                }

                # 🔹 логируем в Supabase через db.py
                save_message_to_supabase(msg_payload)

                # 🔹 и шлём на фронтенд по WebSocket
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
