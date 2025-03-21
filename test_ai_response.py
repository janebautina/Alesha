import unittest
from unittest.mock import patch, MagicMock
import os
from alesha import generate_ai_response, initialize_chat_ids

class TestAIResponseRealOpenAI(unittest.TestCase):

    @patch.dict(os.environ, {
        "LIVE_CHAT_ID": "mock_chat_id",
        "LIVE_STREAM_ID": "mock_stream_id"
    })
    @patch("alesha.translator.translate_text")
    def test_generate_ai_response_english(self, mock_deepl):
        """Test AI response for an English message (real OpenAI API)"""
        initialize_chat_ids()

        # Mock DeepL translations
        def deepl_mock(text, target_lang):
            if target_lang == "RU":
                return MagicMock(text="Здравствуйте! Чем я могу помочь?")
            return MagicMock(text=text)
        mock_deepl.side_effect = deepl_mock

        original, translated = generate_ai_response("How are you?", "en")
        print(f"\n🔹 AI Response (English): {original}")
        print(f"🔹 AI Response (Russian): {translated}")

        self.assertIsInstance(original, str)
        self.assertIsInstance(translated, str)
        self.assertNotIn("Ошибка AI", original)

    @patch.dict(os.environ, {
        "LIVE_CHAT_ID": "mock_chat_id",
        "LIVE_STREAM_ID": "mock_stream_id"
    })
    @patch("alesha.translator.translate_text")
    def test_generate_ai_response_spanish(self, mock_deepl):
        """Test AI response for a Spanish message (real OpenAI API)"""
        initialize_chat_ids()

        def deepl_mock(text, target_lang):
            if target_lang == "RU":
                return MagicMock(text="Здравствуйте, чем я могу вам помочь?")
            return MagicMock(text=text)
        mock_deepl.side_effect = deepl_mock

        original, translated = generate_ai_response("Hola", "es")
        print(f"\n🔹 AI Response (Spanish): {original}")
        print(f"🔹 AI Response (Russian): {translated}")

        self.assertIsInstance(original, str)
        self.assertIsInstance(translated, str)
        self.assertNotIn("Ошибка AI", original)

    @patch.dict(os.environ, {
        "LIVE_CHAT_ID": "mock_chat_id",
        "LIVE_STREAM_ID": "mock_stream_id"
    })
    @patch("alesha.translator.translate_text", return_value=MagicMock(text="AI Error"))
    @patch("alesha.client.chat.completions.create", side_effect=Exception("API error"))
    def test_generate_ai_response_api_error(self, mock_openai, mock_deepl):
        """Test fallback when OpenAI API fails"""
        initialize_chat_ids()

        original, translated = generate_ai_response("This should cause an API error.", "en")
        print(f"\n⚠ AI Response Error (Expected): {original} | {translated}")
        self.assertEqual(original, "Ошибка AI")
        self.assertEqual(translated, "AI Error")

if __name__ == "__main__":
    unittest.main()
