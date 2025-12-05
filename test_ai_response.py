import unittest
from unittest.mock import patch, MagicMock
import os

from alesha import (
    initialize_chat_ids,
    translate_message,
    generate_alesha_reply,
)


class TestAleshaAI(unittest.TestCase):
    @patch.dict(os.environ, {
        "LIVE_CHAT_ID": "mock_chat_id",
        "LIVE_STREAM_ID": "mock_stream_id",
    })
    def test_initialize_chat_ids_uses_env(self):
        """initialize_chat_ids should read LIVE_CHAT_ID and LIVE_STREAM_ID from environment."""
        chat_id, stream_id = initialize_chat_ids()
        self.assertEqual(chat_id, "mock_chat_id")
        self.assertEqual(stream_id, "mock_stream_id")

    @patch("alesha.translator.translate_text")
    def test_translate_message_roundtrip_english(self, mock_deepl):
        """translate_message should convert EN -> RU and back using DeepL."""
        def deepl_side_effect(text, target_lang):
            if target_lang == "RU":
                return MagicMock(text="Привет, как дела?")
            if target_lang == "EN-US":
                return MagicMock(text="Hi, how are you?")
            return MagicMock(text=text)

        mock_deepl.side_effect = deepl_side_effect

        ru, back = translate_message("Hi, how are you?", "en")
        self.assertEqual(ru, "Привет, как дела?")
        self.assertEqual(back, "Hi, how are you?")

    @patch("alesha.client.chat.completions.create")
    def test_generate_alesha_reply_success(self, mock_openai):
        """generate_alesha_reply should return a short text on successful OpenAI call."""
        mock_openai.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="Hello there 👋"))]
        )

        reply = generate_alesha_reply(
            original_message="Hi",
            translated_ru="Привет",
            source_language="en",
            author_name="User123",
            joke_mode=False,
        )

        self.assertIsInstance(reply, str)
        self.assertIn("Hello", reply)

    @patch("alesha.client.chat.completions.create", side_effect=Exception("API error"))
    def test_generate_alesha_reply_error_fallback(self, mock_openai):
        """If OpenAI raises an exception, generate_alesha_reply should return fallback text."""
        reply = generate_alesha_reply(
            original_message="Hi",
            translated_ru="Привет",
            source_language="en",
            author_name="User123",
            joke_mode=False,
        )

        self.assertEqual(reply, "Alesha glitched for a sec, next message please ✨")


if __name__ == "__main__":
    unittest.main()
