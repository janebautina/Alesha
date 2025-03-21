import unittest
from unittest.mock import patch
import os
import openai
from openai import OpenAIError
from alesha import generate_ai_response, initialize_chat_ids  # Ensure correct script filename

class TestAIResponseMock(unittest.TestCase):

    @patch.dict(os.environ, {"LIVE_CHAT_ID": "mock_chat_id", "LIVE_STREAM_ID": "mock_stream_id"})
    @patch("openai.ChatCompletion.create")  # Mock OpenAI API call
    def test_generate_ai_response_english(self, mock_openai):
        """Test AI response for an English message without a real YouTube stream"""
        
        initialize_chat_ids()  # Initialize after mock

        # Simulate OpenAI API returning a response
        mock_openai.return_value = {
            "choices": [{"message": {"content": "Hello! How can I help?"}}]
        }

        message = "How are you?"
        language = "EN-US"

        ai_response_original, ai_response_ru = generate_ai_response(message, language)

        print("\n🔹 AI Response (English):", ai_response_original)
        print("🔹 AI Response (Russian):", ai_response_ru)
        print("\nExpected:", "Hello! How can I help?")
        print("Received:", ai_response_original)
        self.assertEqual(ai_response_original.strip(), "Hello! How can I help?")
        self.assertIsInstance(ai_response_ru, str)

    @patch.dict(os.environ, {"LIVE_CHAT_ID": "mock_chat_id", "LIVE_STREAM_ID": "mock_stream_id"})
    @patch("openai.ChatCompletion.create")
    def test_generate_ai_response_spanish(self, mock_openai):
        """Test AI response for a Spanish message"""
        
        initialize_chat_ids()  # Initialize after mock

        mock_openai.return_value = {
            "choices": [{"message": {"content": "Hola, ¿cómo puedo ayudarte?"}}]
        }

        message = "Hola"
        language = "es"

        ai_response_original, ai_response_ru = generate_ai_response(message, language)

        print("\n🔹 AI Response (Spanish):", ai_response_original)
        print("🔹 AI Response (Russian):", ai_response_ru)

        self.assertEqual(ai_response_original, "Hola, ¿cómo puedo ayudarte?")
        self.assertIsInstance(ai_response_ru, str)

    @patch.dict(os.environ, {"LIVE_CHAT_ID": "mock_chat_id", "LIVE_STREAM_ID": "mock_stream_id"})
    @patch("openai.ChatCompletion.create")
    def test_generate_ai_response_api_error(self, mock_openai):
        """Test AI response when OpenAI API fails"""
        
        initialize_chat_ids()  # Initialize after mock

        mock_openai.side_effect = OpenAIError("API error")

        message = "This should cause an API error."
        language = "en"

        ai_response_original, ai_response_ru = generate_ai_response(message, language)

        print("\n⚠ AI Response Error (Expected due to API failure):", ai_response_original, "|", ai_response_ru)

        self.assertEqual(ai_response_original, "Ошибка AI")
        self.assertEqual(ai_response_ru, "AI Error")

if __name__ == "__main__":
    unittest.main()
