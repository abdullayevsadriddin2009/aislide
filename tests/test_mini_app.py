"""Mini App backend testlari: initData imzosi va asosiy endpointlar."""
import hashlib
import hmac
import json
import os
import sqlite3
import tempfile
import time
import unittest
from urllib.parse import urlencode

import asyncio

import config
import mini_app
from admin_web import app


def make_init_data(user, token, auth_date=None):
    fields = {
        "auth_date": str(int(auth_date if auth_date is not None else time.time())),
        "query_id": "AAH-test",
        "user": json.dumps(user, separators=(",", ":")),
    }
    check_string = "\n".join(f"{key}={fields[key]}" for key in sorted(fields))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


class MiniAppTests(unittest.TestCase):
    def setUp(self):
        self._token = config.BOT_TOKEN
        self._db_path = config.DB_PATH
        config.BOT_TOKEN = "123456:TEST-TOKEN"
        self.tmpdir = tempfile.TemporaryDirectory()
        config.DB_PATH = os.path.join(self.tmpdir.name, "mini.db")
        con = sqlite3.connect(config.DB_PATH)
        con.executescript("""
        CREATE TABLE users (telegram_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
            lang TEXT DEFAULT 'uz', balance INTEGER DEFAULT 0, bonus_balance INTEGER DEFAULT 0,
            referred_by INTEGER, default_pages INTEGER DEFAULT 10, premium INTEGER DEFAULT 0,
            bonus_awarded INTEGER DEFAULT 0, created_at INTEGER, lang_set INTEGER DEFAULT 0);
        CREATE TABLE orders (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, service TEXT,
            topic TEXT, options TEXT, price INTEGER DEFAULT 0, status TEXT DEFAULT 'done',
            result TEXT, created_at INTEGER);
        CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE chat_messages (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            role TEXT, content TEXT, created_at INTEGER);
        """)
        con.commit()
        con.close()
        mini_app.TOKENS.clear()
        self.client = app.test_client()

    def tearDown(self):
        config.BOT_TOKEN = self._token
        config.DB_PATH = self._db_path
        self.tmpdir.cleanup()

    def test_valid_signature_is_accepted(self):
        data = make_init_data({"id": 777, "first_name": "Test"}, config.BOT_TOKEN)
        user = mini_app.verify_init_data(data)
        self.assertIsNotNone(user)
        self.assertEqual(user["id"], 777)

    def test_tampered_signature_is_rejected(self):
        data = make_init_data({"id": 777}, config.BOT_TOKEN).replace("777", "888")
        self.assertIsNone(mini_app.verify_init_data(data))

    def test_expired_init_data_is_rejected(self):
        data = make_init_data({"id": 777}, config.BOT_TOKEN, auth_date=time.time() - 90000)
        self.assertIsNone(mini_app.verify_init_data(data))

    def test_init_endpoint_returns_services_and_token(self):
        data = make_init_data({"id": 555, "first_name": "Ali", "username": "ali"}, config.BOT_TOKEN)
        response = self.client.post("/api/mini/init", json={"initData": data, "lang": "uz"})
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["token"])
        codes = [item["code"] for item in payload["services"]]
        self.assertIn("referat", codes)
        self.assertIn("slide", codes)
        self.assertEqual(payload["user"]["id"], 555)

    def test_init_endpoint_rejects_missing_init_data(self):
        response = self.client.post("/api/mini/init", json={})
        self.assertEqual(response.status_code, 401)

    def test_generate_requires_token(self):
        response = self.client.post("/api/mini/generate", json={"service": "referat", "topic": "Test"})
        self.assertEqual(response.status_code, 401)

    def test_generate_validates_topic(self):
        data = make_init_data({"id": 556}, config.BOT_TOKEN)
        token = self.client.post("/api/mini/init", json={"initData": data}).get_json()["token"]
        response = self.client.post("/api/mini/generate",
                                    json={"token": token, "service": "referat", "topic": "ab"})
        self.assertEqual(response.status_code, 400)

    def _token_for(self, user_id):
        data = make_init_data({"id": user_id}, config.BOT_TOKEN)
        return self.client.post("/api/mini/init", json={"initData": data}).get_json()["token"]

    def test_slide_count_is_limited_to_bot_options(self):
        self.assertEqual(mini_app._payload_options("slide", {"options": {"count": 16}}), {"count": 15})
        self.assertEqual(mini_app._payload_options("slide", {"options": {"count": 4}}), {"count": 10})
        self.assertEqual(mini_app._payload_options("slide", {"options": {"count": 20}}), {"count": 20})

    def test_slide_subject_is_detected_from_topic(self):
        from designs import detect_subject_key

        token = self._token_for(560)
        captured = {}
        original = mini_app._start_job
        def fake_start(uid, payload):
            captured.update(payload)
            return "job-test"

        mini_app._start_job = fake_start
        try:
            response = self.client.post("/api/mini/generate", json={
                "token": token, "service": "slide", "topic": "Biologiya hujayra tuzilishi",
                "options": {"count": 10}, "subject_key": "tarix",
            })
        finally:
            mini_app._start_job = original
        self.assertEqual(response.status_code, 200)
        self.assertEqual(captured["subject_key"], detect_subject_key("Biologiya hujayra tuzilishi"))

    def test_order_detail_is_private(self):
        con = sqlite3.connect(config.DB_PATH)
        con.execute("INSERT INTO orders(user_id,service,topic,options,price,status,created_at) "
                    "VALUES(555,'referat','Test mavzu',?,0,'done',?)",
                    ('{"pages": 7}', int(time.time())))
        con.commit()
        order_id = con.execute("SELECT id FROM orders").fetchone()[0]
        con.close()
        token = self._token_for(555)
        response = self.client.get(f"/api/mini/order?id={order_id}&token={token}")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["order"]["topic"], "Test mavzu")
        self.assertEqual(payload["order"]["options"], {"pages": 7})
        self.assertIsNone(payload["job"])
        other_token = self._token_for(556)
        self.assertEqual(self.client.get(f"/api/mini/order?id={order_id}&token={other_token}").status_code, 404)

    def test_chat_returns_answer_and_stores_history(self):
        token = self._token_for(570)

        async def fake_answer(question, user_lang="uz", history=None):
            return "Javob: " + question

        import ai_api
        original = ai_api.chat_answer
        ai_api.chat_answer = fake_answer
        try:
            response = self.client.post("/api/mini/chat", json={
                "token": token, "message": "Referat nima?", "lang": "uz"})
            self.assertEqual(response.status_code, 200)
            self.assertIn("Referat nima?", response.get_json()["answer"])
            history = self.client.get(f"/api/mini/chat?token={token}").get_json()["messages"]
        finally:
            ai_api.chat_answer = original
        self.assertEqual([m["role"] for m in history], ["user", "assistant"])

    def test_chat_rejects_empty_message(self):
        token = self._token_for(571)
        self.assertEqual(self.client.post("/api/mini/chat", json={"token": token, "message": "  "}).status_code, 400)
        self.assertEqual(self.client.get("/api/mini/chat").status_code, 401)

    def test_page_is_served(self):
        response = self.client.get("/app")
        self.assertEqual(response.status_code, 200)
        self.assertIn("telegram-web-app.js", response.get_data(as_text=True))


class WebAppUrlTests(unittest.TestCase):
    def setUp(self):
        self._url = config.WEBAPP_URL
        config.WEBAPP_URL = ""

    def tearDown(self):
        config.WEBAPP_URL = self._url

    def test_webhook_origin_is_used_when_nothing_is_configured(self):
        import run

        class Info:
            url = "https://bot.example.com/hook/abc"

        class FakeBot:
            async def get_webhook_info(self):
                return Info()

        resolved = asyncio.run(run._resolve_webapp_url(FakeBot()))
        self.assertEqual(resolved, "https://bot.example.com")

    def test_http_webhook_is_ignored(self):
        import run

        class Info:
            url = "http://192.168.1.5:8080/hook"

        class FakeBot:
            async def get_webhook_info(self):
                return Info()

        self.assertEqual(asyncio.run(run._resolve_webapp_url(FakeBot())), "")
        self.assertEqual(config.WEBAPP_URL, "")

    def test_explicit_url_wins(self):
        import run
        config.WEBAPP_URL = "https://my.domain"
        self.assertEqual(asyncio.run(run._resolve_webapp_url(None)), "https://my.domain")


if __name__ == "__main__":
    unittest.main()


class GenerateTimeoutTests(unittest.TestCase):
    def test_slow_generation_raises_timeout(self):
        import asyncio as _asyncio

        import ai_api

        async def slow(*args, **kwargs):
            await _asyncio.sleep(30)
            return "never", True

        original_impl = ai_api._generate_impl
        original_timeout = ai_api.GEN_TIMEOUT
        ai_api._generate_impl = slow
        ai_api.GEN_TIMEOUT = 1
        try:
            with self.assertRaises(TimeoutError):
                _asyncio.run(ai_api.generate("referat", "Mavzu", {"pages": 7}, "uz"))
        finally:
            ai_api._generate_impl = original_impl
            ai_api.GEN_TIMEOUT = original_timeout
