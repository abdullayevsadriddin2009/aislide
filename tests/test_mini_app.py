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

    def test_page_is_served(self):
        response = self.client.get("/app")
        self.assertEqual(response.status_code, 200)
        self.assertIn("telegram-web-app.js", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
