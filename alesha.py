from google.oauth2.credentials import Credentials
import googleapiclient.discovery
import time
from langdetect import detect
import deepl
import os
import openai
import json

# Load config
with open("config.json") as f:
    config = json.load(f)

# Initialize API Clients
translator = deepl.Translator(config["DEEPL_API_KEY"])

# Initialize OpenAI Client (New format)
openai_client =  os.environ.get("OPENAI_API_KEY")
last_request_time = 0  # Prevents OpenAI 429 rate limits

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]

LIVE_CHAT_ID = None
LIVE_STREAM_ID = None

def initialize_chat_ids():
    """Sets LIVE_CHAT_ID and LIVE_STREAM_ID only when the script runs, not when imported."""
    global LIVE_CHAT_ID, LIVE_STREAM_ID
    LIVE_CHAT_ID = os.getenv("LIVE_CHAT_ID")
    LIVE_STREAM_ID = os.getenv("LIVE_STREAM_ID")

    if not LIVE_CHAT_ID:
        raise ValueError("❌ ERROR: LIVE_CHAT_ID is not set. Make sure `get_live_chat_id.py` is fetching it correctly.")

    if not LIVE_STREAM_ID:
        raise ValueError("❌ ERROR: LIVE_STREAM_ID is not set. Make sure `get_live_chat_id.py` is fetching it correctly.")


def get_authenticated_service():
    """Authenticate and return the YouTube API service."""
    creds = Credentials.from_authorized_user_file(config["TOKEN_FILE"], SCOPES)
    youtube = googleapiclient.discovery.build("youtube", "v3", credentials=creds)
    return youtube

# Initialize YouTube API client
youtube = get_authenticated_service()

def detect_language(text):
    """Detect the language of a given text."""
    try:
        return detect(text)
    except:
        return "unknown"

def get_live_chat_messages():
    """Fetch live chat messages from YouTube and process only non-Russian messages."""
    request = youtube.liveChatMessages().list(
        liveChatId=LIVE_CHAT_ID,
        part="snippet,authorDetails"
    )
    response = request.execute()
    messages = []

    for item in response.get("items", []):
        message = item["snippet"].get("displayMessage", "[Non-text message]")
        author = item["authorDetails"]["displayName"]
        
        # Detect language
        detected_lang = detect_language(message)

        # Only process messages that are NOT in Russian
        if detected_lang != "ru":
            # Translate message
            translated_msg, _ = translate_message(message, detected_lang)

            # Generate AI Response
            ai_response_original, ai_response_ru = generate_ai_response(message, detected_lang)

            # Send messages back to chat
            send_message_to_chat(f"📝 {author}: {translated_msg}")
            send_message_to_chat(f"💬 AI Reply: {ai_response_original} | {ai_response_ru}")

            # Add to processed messages list
            messages.append((author, message, translated_msg, ai_response_original, ai_response_ru, detected_lang))

    return messages  # Returns only processed (non-Russian) messages

def translate_message(message, source_language):
    """Translate a message to Russian and back to the original language if needed."""

    # Mapping common languages to DeepL's required format
    language_mapping = {
        "en": "EN-US",  # English (US)
        "fr": "FR",      # French
        "es": "ES",      # Spanish
        "de": "DE",      # German
        "it": "IT",      # Italian
        "nl": "NL",      # Dutch
        "ru": "RU"       # Russian
    }

    # Convert detected language to DeepL's format
    target_lang = language_mapping.get(source_language, "EN-US")  # Default to English US

    try:
        # Translate to Russian first
        translated_to_russian = translator.translate_text(message, target_lang="RU").text

        # If the message is already in Russian, no need to translate back
        if source_language == "ru":
            return translated_to_russian, translated_to_russian

        # Translate AI-generated response back to the original language
        translated_response = translator.translate_text(translated_to_russian, target_lang=target_lang).text

        return translated_to_russian, translated_response

    except Exception as e:
        print(f"⚠ Translation Error: {e}")
        return message, message  # Return original message if translation fails


def send_message_to_chat(message):
    """Send a message back to the YouTube live chat."""
    request = youtube.liveChatMessages().insert(
        part="snippet",
        body={
            "snippet": {
                "liveChatId": LIVE_CHAT_ID,
                "type": "textMessageEvent",
                "textMessageDetails": {
                    "messageText": message
                }
            }
        }
    )
    request.execute()

def generate_ai_response(message, language):
    """Generate an AI-based response in both the original language and Russian."""
    
    global last_request_time

    try:
        # Enforce a small delay to avoid OpenAI rate limits
        time_since_last_request = time.time() - last_request_time
        if time_since_last_request < 2:  # Ensures at least 2 seconds between requests
            time.sleep(2 - time_since_last_request)

        # Construct AI prompt
        messages = [
            {"role": "system", "content": "You are a helpful AI assisting users in YouTube live chat."},
            {"role": "user", "content": f"User said: {message}. Generate a relevant and concise response."}
        ]

        # Corrected OpenAI API Call (Version 0.28.0)
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=messages
        )

        ai_response = response["choices"][0]["message"]["content"].strip()

        # Update last request time to avoid API spam
        last_request_time = time.time()

        # Translate AI response to Russian
        ai_response_ru = translator.translate_text(ai_response, target_lang="RU").text

        # Translate AI response back to the original language (if needed)
        if language != "ru":
            ai_response_original = translator.translate_text(ai_response, target_lang=language.upper()).text
        else:
            ai_response_original = ai_response  # No need to translate if it's already Russian

        return ai_response_original, ai_response_ru

    except Exception as e:
        print(f"⚠ AI Response Error: {e}")
        return "Ошибка AI", "AI Error"

def main():
    """Main function to fetch, translate, and respond to live chat messages with AI (Only Non-Russian)."""
    print("🚀 YouTube Live Chat Translator Bot is running...")
    initialize_chat_ids()
    processed_messages = set()

    while True:
        messages = get_live_chat_messages()

        for author, original_msg, translated_msg, ai_response_original, ai_response_ru, detected_lang in messages:
            if original_msg not in processed_messages:
                # Send AI-generated responses back to the chat
                send_message_to_chat(f"💬 AI Reply: {ai_response_original} | {ai_response_ru}")
                
                processed_messages.add(original_msg)
        
        time.sleep(5)  # Prevents excessive API calls

if __name__ == "__main__":
    main()
