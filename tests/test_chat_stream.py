"""AI chat oqimi (CdxChatBot.php mantiqi) testlari."""
import asyncio
import unittest
from unittest import mock

import ai_chat_stream


class _DummySession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class BuildContentsTests(unittest.TestCase):
    def test_history_starts_with_user_and_maps_assistant_to_model(self):
        history = [
            {"role": "assistant", "content": "salom"},
            {"role": "user", "content": "savol"},
            {"role": "assistant", "content": "javob"},
        ]
        contents = ai_chat_stream.build_contents(history, "yangi savol")
        self.assertEqual([item["role"] for item in contents], ["user", "model", "user"])
        self.assertEqual(contents[-1]["parts"][0]["text"], "yangi savol")

    def test_empty_history_only_has_the_question(self):
        contents = ai_chat_stream.build_contents(None, "savol")
        self.assertEqual(len(contents), 1)
        self.assertEqual(contents[0]["role"], "user")


class AttemptOrderTests(unittest.TestCase):
    def test_default_model_goes_first_and_keys_follow_fails_order(self):
        keys = [{"id": 2, "label": "b", "provider": "google", "models": "m1,m2"},
                {"id": 1, "label": "a", "provider": "google", "models": "m1"}]
        models = [{"name": "m1", "active": 1, "is_default": 1},
                  {"name": "m2", "active": 1, "is_default": 0}]
        with mock.patch.object(ai_chat_stream.ai_pool, "keys", return_value=keys), \
                mock.patch.object(ai_chat_stream.ai_pool, "models", return_value=models):
            plan = ai_chat_stream.attempts()
        self.assertEqual([(key["id"], model) for key, model in plan],
                         [(2, "m1"), (1, "m1"), (2, "m2")])


class StreamReplyTests(unittest.IsolatedAsyncioTestCase):
    async def test_streams_text_and_resets_fails(self):
        keys = [{"id": 1, "label": "google", "provider": "google",
                 "api_key": "k", "base_url": "https://example", "models": "m1"}]
        models = [{"name": "m1", "active": 1, "is_default": 1}]
        seen = []

        async def fake_google(session, key, model, body, on_text):
            on_text("Salom")
            on_text("Salom dunyo")
            return 200, "Salom dunyo", None

        with mock.patch.object(ai_chat_stream.ai_pool, "keys", return_value=keys), \
                mock.patch.object(ai_chat_stream.ai_pool, "models", return_value=models), \
                mock.patch.object(ai_chat_stream.ai_pool, "mark_result") as mark, \
                mock.patch.object(ai_chat_stream.ai_pool, "note_error") as note, \
                mock.patch.object(ai_chat_stream, "_stream_google", fake_google), \
                mock.patch.object(ai_chat_stream.aiohttp, "ClientSession", return_value=_DummySession()):
            answer = await ai_chat_stream.stream_reply("sys", "savol", on_text=seen.append)

        self.assertEqual(answer, "Salom dunyo")
        self.assertEqual(seen[-1], "Salom dunyo")
        mark.assert_called_with(1, True)
        note.assert_called_with("")

    async def test_bad_key_moves_to_the_next_one(self):
        keys = [{"id": 1, "label": "a", "provider": "google", "api_key": "k",
                 "base_url": "https://example", "models": "m1"},
                {"id": 2, "label": "b", "provider": "google", "api_key": "k2",
                 "base_url": "https://example", "models": "m1"}]
        models = [{"name": "m1", "active": 1, "is_default": 1}]
        calls = []

        async def fake_google(session, key, model, body, on_text):
            calls.append(key["id"])
            if key["id"] == 1:
                return 401, None, "HTTP 401: API key not valid"
            return 200, "javob", None

        with mock.patch.object(ai_chat_stream.ai_pool, "keys", return_value=keys), \
                mock.patch.object(ai_chat_stream.ai_pool, "models", return_value=models), \
                mock.patch.object(ai_chat_stream.ai_pool, "mark_result") as mark, \
                mock.patch.object(ai_chat_stream.ai_pool, "note_error"), \
                mock.patch.object(ai_chat_stream, "_stream_google", fake_google), \
                mock.patch.object(ai_chat_stream.aiohttp, "ClientSession", return_value=_DummySession()):
            answer = await ai_chat_stream.stream_reply("sys", "savol")

        self.assertEqual(answer, "javob")
        self.assertEqual(calls, [1, 2])
        mark.assert_any_call(1, False)
        mark.assert_any_call(2, True)

    async def test_all_failures_return_none_and_store_error(self):
        keys = [{"id": 1, "label": "a", "provider": "google", "api_key": "k",
                 "base_url": "https://example", "models": "m1"}]
        models = [{"name": "m1", "active": 1, "is_default": 1}]

        async def fake_google(session, key, model, body, on_text):
            return 500, None, "HTTP 500"

        with mock.patch.object(ai_chat_stream.ai_pool, "keys", return_value=keys), \
                mock.patch.object(ai_chat_stream.ai_pool, "models", return_value=models), \
                mock.patch.object(ai_chat_stream.ai_pool, "mark_result"), \
                mock.patch.object(ai_chat_stream.ai_pool, "note_error") as note, \
                mock.patch.object(ai_chat_stream, "_stream_google", fake_google), \
                mock.patch.object(ai_chat_stream.aiohttp, "ClientSession", return_value=_DummySession()):
            answer = await ai_chat_stream.stream_reply("sys", "savol")

        self.assertIsNone(answer)
        self.assertIn("muvaffaqiyatsiz", note.call_args[0][0])

    async def test_no_keys_reports_clearly(self):
        with mock.patch.object(ai_chat_stream.ai_pool, "keys", return_value=[]), \
                mock.patch.object(ai_chat_stream.ai_pool, "models", return_value=[]), \
                mock.patch.object(ai_chat_stream.ai_pool, "note_error") as note:
            answer = await ai_chat_stream.stream_reply("sys", "savol")
        self.assertIsNone(answer)
        self.assertIn("kalit", note.call_args[0][0].lower())


if __name__ == "__main__":
    unittest.main()
