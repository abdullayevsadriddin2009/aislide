"""AI kalitlari bazasi, model tartibi va chat formatlash testlari."""
import os
import tempfile
import unittest
from unittest import mock

import chat_format
import config


class AiPoolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = mock.patch.object(config, "DB_PATH", os.path.join(self.tmp.name, "pool.db"))
        patcher.start()
        self.addCleanup(patcher.stop)
        import ai_pool
        self.pool = ai_pool
        ai_pool.ensure()

    def test_key_is_used_with_provider_defaults(self):
        self.pool.add_key("Gemini asosiy", "test-key-123456789", "google")
        apis = self.pool.runtime_apis()
        self.assertEqual(len(apis), 1)
        api = apis[0]
        self.assertEqual(api["type"], "google")
        self.assertEqual(api["api_key"], "test-key-123456789")
        self.assertTrue(api["base_url"].startswith("https://generativelanguage"))
        self.assertIn("gemini-2.5-flash", api["models"])

    def test_failing_key_moves_behind_healthy_one(self):
        self.pool.add_key("birinchi", "key-one-aaaaaaaa", "groq")
        self.pool.add_key("ikkinchi", "key-two-bbbbbbbb", "groq")
        first = self.pool.keys()[0]
        self.pool.mark_result(first["id"], False)
        ordered = [api["name"] for api in self.pool.runtime_apis()]
        self.assertEqual(ordered[0], "ikkinchi", ordered)
        self.pool.mark_result(first["id"], True)
        self.assertEqual(self.pool.runtime_apis()[0]["name"], "birinchi")

    def test_disabled_key_is_skipped(self):
        self.pool.add_key("o'chiriladi", "key-three-cccccc", "groq")
        key = self.pool.keys()[0]
        self.pool.toggle_key(key["id"])
        self.assertEqual(self.pool.runtime_apis(), [])

    def test_default_model_goes_first(self):
        self.pool.add_key("groq", "key-four-dddddddd", "groq",
                          models="openai/gpt-oss-20b, qwen/qwen3.8-27b")
        self.pool.add_model("openai/gpt-oss-20b")
        model = self.pool.models()[0]
        self.pool.set_default_model(model["id"])
        self.assertEqual(self.pool.runtime_apis()[0]["models"][0], "openai/gpt-oss-20b")

    def test_render_environment_keys_are_imported_once(self):
        import ai_api
        fake = [{"name": "Google env", "type": "google",
                 "base_url": "https://generativelanguage.googleapis.com/v1beta",
                 "api_key": "env-key-999999", "models": ["gemini-2.5-flash"]}]
        with mock.patch.object(ai_api, "API_LIST", fake):
            self.pool._SYNCED_PATHS.clear()
            self.pool.ensure()
        keys = [key["api_key"] for key in self.pool.keys()]
        self.assertIn("env-key-999999", keys)
        env_key = [key for key in self.pool.keys() if key["api_key"] == "env-key-999999"][0]
        self.pool.toggle_key(env_key["id"])  # admin o'chirgan kalit qayta yoqilmasin
        with mock.patch.object(ai_api, "API_LIST", fake):
            self.pool._SYNCED_PATHS.clear()
            self.pool.ensure()
        again = [key for key in self.pool.keys() if key["api_key"] == "env-key-999999"]
        self.assertEqual(len(again), 1)
        self.assertEqual(again[0]["active"], 0)

    def test_chat_settings_are_clamped(self):
        self.pool.set_setting("temperature", "9")
        self.pool.set_setting("history_limit", "500")
        self.pool.set_setting("markdown", "0")
        self.assertEqual(self.pool.chat_temperature(), 2.0)
        self.assertEqual(self.pool.chat_history_limit(), 40)
        self.assertFalse(self.pool.chat_markdown())
        self.assertTrue(self.pool.chat_system_prompt())


class ChatFormatTests(unittest.TestCase):
    def test_markdown_is_converted_to_telegram_html(self):
        html = chat_format.md_to_tg_html(
            "# Sarlavha\n**qalin** va *kursiv*\n\n- birinchi\n- ikkinchi\n\n`kod` va [havola](https://example.com)")
        self.assertIn("<b>Sarlavha</b>", html)
        self.assertIn("<b>qalin</b>", html)
        self.assertIn("<i>kursiv</i>", html)
        self.assertIn("• birinchi", html)
        self.assertIn("<code>kod</code>", html)
        self.assertIn('<a href="https://example.com">havola</a>', html)

    def test_html_in_answer_is_escaped(self):
        self.assertIn("&lt;script&gt;", chat_format.md_to_tg_html("<script>alert(1)</script>"))

    def test_long_answer_is_split(self):
        parts = chat_format.split_text("qator\n" * 900, 3500)
        self.assertGreater(len(parts), 1)
        self.assertTrue(all(len(part) <= 3500 for part in parts))
        self.assertEqual("".join(part.replace("\n", "") for part in parts).count("qator"), 900)

    def test_fenced_code_is_preserved(self):
        html = chat_format.md_to_tg_html("```python\nprint('<hi>')\n```")
        self.assertIn("<pre><code", html)
        self.assertIn("&lt;hi&gt;", html)


if __name__ == "__main__":
    unittest.main()
