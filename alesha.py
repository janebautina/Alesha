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
from db import save_message_to_supabase  # shared DB helper

# -------- Config loading --------
with open("config.json") as f:
    config = json.load(f)

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
MAX_TRACKED_MESSAGES = 1000
BOT_COOLDOWN_SECONDS = 30  # global cooldown for all bot messages
LIVE_CHAT_ID = os.getenv("LIVE_CHAT_ID")
LIVE_STREAM_ID = os.getenv("LIVE_STREAM_ID")
connected_clients = set()

MAX_YT_MESSAGE_LEN = 200

# -------- Payment / donations config (edit these for your real data) --------
GRATITUDE_COOLDOWN_SECONDS = 600  # 10 minutes shared cooldown for likes + donations
LIKE_CHECK_INTERVAL = 60  # seconds to poll like count

# How often to show donation info (text-based donations for users without SuperChat)
DONATION_INFO_INTERVAL_SECONDS = 600  # 10 minutes

# TODO: replace these placeholders with your real data
DONATION_CARD_TEXT = "**** **** **** ****"  # your card number / bank details
PAYPAL_LINK = "https://paypal.me/your_link"  # your PayPal.me link
DONATIONALERTS_URL = "https://www.donationalerts.com/r/your_channel"  # your DonationAlerts link

DONATION_INFO_TEXT = (
    "Хочешь поддержать стрим или заказать музыку? 🎵 "
    f"Карта: {DONATION_CARD_TEXT} | PayPal: {PAYPAL_LINK} | DonationAlerts: {DONATIONALERTS_URL}. "
    "Один трек — 250₽."
)

# -------- Globals --------
translator = deepl.Translator(
    config["DEEPL_API_KEY"],
    server_url="https://api-free.deepl.com",
)
client = OpenAI(api_key=config["OPENAI_API_KEY"])

youtube = googleapiclient.discovery.build(
    "youtube",
    "v3",
    credentials=Credentials.from_authorized_user_file(config["TOKEN_FILE"], SCOPES),
)

last_request_time = 0.0
last_bot_post_time = 0.0
processed_message_ids = deque(maxlen=MAX_TRACKED_MESSAGES)
processed_message_ids_set: set[str] = set()
next_page_token = None

# counter for "super-fun" mode
message_counter = 0
next_funny_in = random.randint(3, 5)

# likes and gratitude state
seen_authors = set()
last_like_check_time = 0.0
last_like_count: int | None = None

last_gratitude_time = 0.0  # for likes + donations + donation-info text
last_donation_info_time = 0.0

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

MENTION_KEYWORDS = [
    "алёша",
    "алеша",
    "alesha",
    "Алеша",
    "Aлёша",
    "Alesha",
    "Al",
    "al",
    "@californicationru",
    "@californicationru ",  # YouTube sometimes adds a trailing space after the username
]

def initialize_chat_ids():
    """Initialize LIVE_CHAT_ID and LIVE_STREAM_ID from environment variables."""
    global LIVE_CHAT_ID, LIVE_STREAM_ID
    LIVE_CHAT_ID = os.getenv("LIVE_CHAT_ID")
    LIVE_STREAM_ID = os.getenv("LIVE_STREAM_ID")
    return LIVE_CHAT_ID, LIVE_STREAM_ID


# -------- WebSocket handling --------
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
    """Broadcast a JSON message to all connected WebSocket clients."""
    if connected_clients:
        message = json.dumps(message_dict)
        print(f"📡 Broadcasting to {len(connected_clients)} clients: {message}")
        await asyncio.gather(
            *(client.send(message) for client in connected_clients),
            return_exceptions=True,
        )
    else:
        print("⚠️ No connected clients to broadcast to.")


# -------- Language / translation helpers --------
def detect_language(text: str) -> str:
    """Detect language code using langdetect, fallback to 'unknown'."""
    try:
        return detect(text)
    except Exception:
        return "unknown"


def _extract_deepl_text(result):
    """Extract text from DeepL translation result (handles both single TextResult and list)."""
    if isinstance(result, list):
        return result[0].text if result else ""
    return result.text


def translate_message(message: str, source_language: str):
    """
    Translate message to Russian (for context / UI) and back to original language via Russian.
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


# -------- YouTube chat helpers --------
def build_chat_text(prefix: str, text: str) -> str:
    """
    Build final YouTube chat message with prefix and enforce length limit.
    Ensures the combined string does not exceed MAX_YT_MESSAGE_LEN.
    """
    base = f"{prefix} {text}".strip()
    if len(base) <= MAX_YT_MESSAGE_LEN:
        return base

    keep = MAX_YT_MESSAGE_LEN - 1
    return base[:keep] + "…"


def send_message_to_chat(message: str, prefix: str = "🔴"):
    """Send a message into YouTube live chat with length enforcement and update bot cooldown."""
    global last_bot_post_time

    try:
        if not LIVE_CHAT_ID:
            raise ValueError("LIVE_CHAT_ID is not set.")

        final_text = build_chat_text(prefix, message)

        youtube.liveChatMessages().insert(
            part="snippet",
            body={
                "snippet": {
                    "liveChatId": LIVE_CHAT_ID,
                    "type": "textMessageEvent",
                    "textMessageDetails": {
                        "messageText": final_text
                    },
                }
            },
        ).execute()
        last_bot_post_time = time.time()
        print(f"✅ Sent to YouTube chat: {final_text!r}")
    except Exception as e:
        print(f"⚠ Failed to send to chat: {e}")


def get_current_like_count() -> int | None:
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


def maybe_send_gratitude(text: str, prefix: str = "💖") -> None:
    """
    Send a thank-you / donation-info message using a shared cooldown.
    Likes, SuperChat, and donation-info text share the same 10-minute cooldown,
    and also respect the global BOT_COOLDOWN_SECONDS.
    """
    global last_gratitude_time, last_bot_post_time

    now = time.time()

    # Shared gratitude cooldown
    if now - last_gratitude_time < GRATITUDE_COOLDOWN_SECONDS:
        print("⏱ Skipping gratitude message due to shared 10-min cooldown.")
        return

    # Also respect global bot cooldown, so we do not spam messages too frequently
    if now - last_bot_post_time < BOT_COOLDOWN_SECONDS:
        print("⏱ Skipping gratitude message due to global bot cooldown.")
        return

    send_message_to_chat(text, prefix=prefix)
    last_gratitude_time = now
    # last_bot_post_time is updated inside send_message_to_chat


# -------- AI reply generation --------
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


# -------- Main loop --------
async def fetch_and_process_messages():
    """
    Main loop:
    - periodically checks likes and (if cooldown allows) sends thank-you messages;
    - periodically sends donation-info text (card, PayPal, DonationAlerts);
    - reads new messages from YouTube;
    - stores each user message in Supabase;
    - replies no more often than BOT_COOLDOWN_SECONDS;
    - broadcasts user messages to WebSocket clients;
    - uses a shared 10-min gratitude cooldown for likes, donations, and donation-info.
    """
    global next_page_token, message_counter, next_funny_in
    global last_like_check_time, last_like_count
    global last_donation_info_time

    while True:
        try:
            now = time.time()

            # Periodically check likes and thank viewers for new ones
            if now - last_like_check_time > LIKE_CHECK_INTERVAL:
                like_count = get_current_like_count()
                last_like_check_time = now

                if like_count is not None:
                    if last_like_count is None:
                        # First initialization: just store current like count
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

                        # Send thanks for likes using shared likes+donations cooldown
                        maybe_send_gratitude(text, prefix="💖")

            # Periodically show donation info (card + PayPal + DonationAlerts) using shared cooldown
            if now - last_donation_info_time > DONATION_INFO_INTERVAL_SECONDS:
                maybe_send_gratitude(DONATION_INFO_TEXT, prefix="💸")
                last_donation_info_time = now

            # Read new messages from YouTube Live Chat
            request = youtube.liveChatMessages().list(
                liveChatId=LIVE_CHAT_ID,
                part="snippet,authorDetails",
                pageToken=next_page_token,
            )
            response = request.execute()
            next_page_token = response.get("nextPageToken")
            polling_interval = response.get("pollingIntervalMillis", 2000) / 1000.0

            for item in response.get("items", []):
                msg_id = item["id"]
                if msg_id in processed_message_ids_set:
                    continue

                # Maintain a sliding window of processed message IDs
                if len(processed_message_ids) >= MAX_TRACKED_MESSAGES:
                    old_id = processed_message_ids.popleft()
                    processed_message_ids_set.discard(old_id)

                processed_message_ids.append(msg_id)
                processed_message_ids_set.add(msg_id)

                snippet = item.get("snippet", {})
                message = snippet.get("displayMessage", "[Non-text message]")
                author_details = item.get("authorDetails", {}) or {}

                author = author_details.get("displayName", "Unknown")
                detected_lang = detect_language(message)
                is_owner = bool(author_details.get("isChatOwner"))
                text_lower = message.lower()
                addressed_bot = any(key in text_lower for key in MENTION_KEYWORDS)

                # Detect Super Chat / donation events and thank with shared cooldown
                event_type = snippet.get("type")
                super_chat_details = snippet.get("superChatDetails")

                if event_type == "superChatEvent" and super_chat_details:
                    amount_str = super_chat_details.get("amountDisplayString") or ""
                    donor_name = author

                    if amount_str:
                        donation_text = (
                            f"Thank you for the Super Chat {amount_str}, {donor_name}! "
                            f"You keep this stream alive 💖"
                        )
                    else:
                        donation_text = (
                            f"Thank you so much for your support, {donor_name}! 💖"
                        )

                    maybe_send_gratitude(donation_text, prefix="💖")

                # Save user message to Supabase once
                user_msg_payload = {
                    "id": msg_id,
                    "author": author,
                    "content": message,
                    "language": detected_lang,
                }
                # 🔹 If message is from the channel owner, do NOT trigger AI reply
                # 1) If message is from channel owner,
                #    do NOT save to DB and do NOT trigger AI reply.
                if is_owner:
                    # You *may* still want to broadcast it to frontend, so the dashboard sees your messages
                    await broadcast_message(user_msg_payload)
                    continue  # skip reply + DB for owner
                save_message_to_supabase(user_msg_payload)

                # Respect bot reply cooldown for normal chat replies
                now = time.time()
                if not addressed_bot and (now - last_bot_post_time < BOT_COOLDOWN_SECONDS):
                    # Still broadcast user message to frontend even if bot stays silent
                    await broadcast_message(user_msg_payload)
                    continue

                # Translate to Russian for context / logs / UI
                translated_ru, _ = translate_message(message, detected_lang)

                # Increment counter and decide if this is a "super-fun" turn
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

                # Reset funny counter if we just did a super-funny one
                if is_funny:
                    message_counter = 0
                    next_funny_in = random.randint(3, 5)

                # Broadcast original user message to frontend
                await broadcast_message(user_msg_payload)

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
