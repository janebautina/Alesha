from google.oauth2.credentials import Credentials
import googleapiclient.discovery
import time
import googleapiclient.discovery
from langdetect import detect
import deepl
import openai
import json

# Load config
with open("config.json") as f:
    config = json.load(f)

# Initialize API Clients
translator = deepl.Translator(config["DEEPL_API_KEY"])
openai.api_key = config["OPENAI_API_KEY"]

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]

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
    """Fetch live chat messages from YouTube."""
    request = youtube.liveChatMessages().list(
        liveChatId = LIVE_CHAT_ID,
        part="snippet,authorDetails"
    )
    response = request.execute()
    messages = []
    for item in response.get("items", []):
        message = item["snippet"].get("displayMessage", "[Non-text message]")
        author = item["authorDetails"]["displayName"]
        # Detect language
        detected_lang = detect_language(message)
        
        # Translate message if needed
        translated_msg, _ = translate_message(message, detected_lang)

        # Generate AI Response
        ai_response_ru, ai_response_original = generate_ai_response(message, detected_lang)
        print(f"📝 **Original ({author} - {detected_lang}):** {message}")
        print(f"🇷🇺 **Translated to Russian:** {translated_msg}")
        print(f"💬 **AI Response in {detected_lang} & Russian:** {ai_response_original} | {ai_response_ru}")

        messages.append((author, message, translated_msg, ai_response_original, ai_response_ru, detected_lang))
    return messages

def translate_message(message, source_language):
    """Translate a message based on its source language."""
    
    if source_language == "ru":
        return message, message  # No need to translate

    translated_to_russian = translator.translate_text(message, target_lang="RU").text

    translated_response = translator.translate_text(
        f"Спасибо за ваше сообщение! ({translated_to_russian})", 
        target_lang=source_language.upper()
    ).text

    return translated_to_russian, translated_response


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
    
    try:
        # Create a prompt for AI to generate a response
        prompt = f"You are a helpful AI responding to a YouTube live chat message: {message}"

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "system", "content": prompt}]
        )

        ai_response = response["choices"][0]["message"]["content"].strip()

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
    """Main function to fetch, translate, and respond to live chat messages with AI."""
    print("🚀 YouTube Live Chat Translator Bot is running...")
    
    processed_messages = set()

    while True:
        messages = get_live_chat_messages()
        
        for author, original_msg, translated_msg, ai_response_original, ai_response_ru, detected_lang in messages:
            if original_msg not in processed_messages:
                # Send the translated message and AI responses back to the chat
                send_message_to_chat(f"📝 {author}: {translated_msg}")
                send_message_to_chat(f"💬 AI Reply: {ai_response_original} | {ai_response_ru}")

                processed_messages.add(original_msg)
        
        time.sleep(5)

if __name__ == "__main__":
    main()
