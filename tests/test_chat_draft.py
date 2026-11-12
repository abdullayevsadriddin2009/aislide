"""Botdagi sendMessageDraft (oqim) callback testlari."""
import unittest
from unittest import mock

import handlers.user as user_handlers


class _FakeChat:
    id = 4242


class _FakeMessage:
    chat = _FakeChat()


class DraftCallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_throttles_updates_to_once_per_interval(self):
        sent = []

        async def fake_send(chat_id, draft_id, text):
            sent.append(text)
            return True, ""

        with mock.patch.object(user_handlers, "_send_message_draft", fake_send), \
                mock.patch("ai_pool.chat_draft_stream", return_value=True), \
                mock.patch("ai_pool.note_draft_error"):
            on_text = user_handlers._draft_callback(_FakeMessage())
            await on_text("birinchi")
            await on_text("ikkinchi")  # 0.8s ichida — yuborilmaydi

        self.assertEqual(sent, ["birinchi"])

    async def test_turns_off_when_telegram_rejects_the_method(self):
        calls = []

        async def fake_send(chat_id, draft_id, text):
            calls.append(text)
            return False, "Telegram server says: method not found"

        with mock.patch.object(user_handlers, "_send_message_draft", fake_send), \
                mock.patch("ai_pool.chat_draft_stream", return_value=True), \
                mock.patch("ai_pool.note_draft_error") as note:
            on_text = user_handlers._draft_callback(_FakeMessage())
            await on_text("birinchi")
            await on_text("ikkinchi")  # o'chirilgandan keyin umuman yuborilmaydi

        self.assertEqual(calls, ["birinchi"])
        note.assert_any_call("Telegram server says: method not found")

    async def test_disabled_in_admin_sends_nothing(self):
        async def fake_send(chat_id, draft_id, text):  # pragma: no cover
            raise AssertionError("draft yuborilmasligi kerak edi")

        with mock.patch.object(user_handlers, "_send_message_draft", fake_send), \
                mock.patch("ai_pool.chat_draft_stream", return_value=False):
            on_text = user_handlers._draft_callback(_FakeMessage())
            await on_text("matn")


if __name__ == "__main__":
    unittest.main()
