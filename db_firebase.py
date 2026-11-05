# -*- coding: utf-8 -*-
"""Firebase (Firestore) — botning doimiy saqlash qatlami.

Nima uchun kerak: hosting (Render/Railway) fayl tizimi kod yangilanganda
tozalanadi, shuning uchun SQLite fayli yo'qoladi. Bu modul foydalanuvchilar,
buyurtmalar va AI Chat tarixini Firestore'da saqlaydi; `database.py` ishga
tushishda ularni SQLite'ga qaytaradi va har bir yozuvda Firestore'ga nusxa
ko'chiradi.

Kalit faylni topish tartibi:
  1) FIREBASE_CREDENTIALS_JSON / FIREBASE_KEY_JSON muhit o'zgaruvchisi (JSON matn)
  2) /etc/secrets/firebase_key.json (Render Secret File)
  3) loyiha papkasidagi firebase_key.json / serviceAccountKey.json

Hech qanday xato botni to'xtatmaydi: Firebase bo'lmasa bot SQLite bilan ishlaydi.
"""
from __future__ import annotations

import asyncio
import json
import os

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    HAS_FIREBASE_SDK = True
except Exception:  # firebase-admin o'rnatilmagan muhitlar
    firebase_admin = None
    credentials = None
    firestore = None
    HAS_FIREBASE_SDK = False

KEY_PATHS = [
    "/etc/secrets/firebase_key.json",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "firebase_key.json"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "serviceAccountKey.json"),
]
ENV_KEY_VARS = ("FIREBASE_CREDENTIALS_JSON", "FIREBASE_KEY_JSON", "FIREBASE_SERVICE_ACCOUNT")

STARTUP_ERROR = ""


def _build_client():
    """Return a Firestore client or None (never raises)."""
    global STARTUP_ERROR
    if not HAS_FIREBASE_SDK:
        STARTUP_ERROR = "firebase-admin paketi o'rnatilmagan"
        return None

    cred = None
    source = ""
    for var in ENV_KEY_VARS:
        raw = os.getenv(var, "").strip()
        if not raw:
            continue
        try:
            cred = credentials.Certificate(json.loads(raw))
            source = f"env:{var}"
            break
        except Exception as exc:
            STARTUP_ERROR = f"{var} JSON xato: {exc}"
    if cred is None:
        for path in KEY_PATHS:
            if os.path.isfile(path):
                try:
                    cred = credentials.Certificate(path)
                    source = path
                    break
                except Exception as exc:
                    STARTUP_ERROR = f"{path}: {exc}"
    if cred is None:
        STARTUP_ERROR = STARTUP_ERROR or "firebase_key.json topilmadi"
        return None

    try:
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        client = firestore.client()
        print(f"✅ Firebase ulandi! Kalit: {source}", flush=True)
        return client
    except Exception as exc:
        STARTUP_ERROR = f"ulanish xatosi: {exc}"
        return None


db = _build_client()
if db is None:
    print(f"⚠️ Firebase o'chirilgan — sabab: {STARTUP_ERROR}", flush=True)

_USERS = "users"
_ORDERS = "orders"
_CHATS = "chats"
_ACTIONS = "user_actions"
_SETTINGS = "settings"


def is_enabled() -> bool:
    return db is not None


async def _run(func, default=None):
    """Run a blocking Firestore call in a worker thread; never raise."""
    if db is None:
        return default
    try:
        return await asyncio.to_thread(func)
    except Exception as exc:
        print(f"[FB] xato: {exc}", flush=True)
        return default


def _clean(data: dict) -> dict:
    return {k: v for k, v in data.items() if v is not None}


# ============================ FOYDALANUVCHILAR ============================
async def fb_save_user(telegram_id, username=None, first_name=None, last_name=None,
                       lang=None, balance=None, bonus_balance=None, premium=None,
                       referred_by=None, created_at=None, count_use=False):
    """Foydalanuvchini saqlash/yangilash (merge — mavjud maydonlar yo'qolmaydi)."""
    if db is None:
        return
    uid = str(telegram_id)

    def op():
        doc = db.collection(_USERS).document(uid)
        payload = _clean({
            "telegram_id": int(telegram_id),
            "username": username,
            "first_name": first_name,
            "last_name": last_name,
            "lang": lang,
            "balance": balance,
            "bonus_balance": bonus_balance,
            "premium": premium,
            "referred_by": referred_by,
            "created_at": created_at,
            "last_seen": firestore.SERVER_TIMESTAMP,
        })
        doc.set(payload, merge=True)
        if count_use:
            # set() hujjatni yaratadi, keyin Increment ishlaydi.
            doc.update({"total_uses": firestore.Increment(1)})

    await _run(op)


async def fb_load_users(limit=5000):
    """Barcha saqlangan foydalanuvchilarni qaytaradi (SQLite'ni tiklash uchun)."""
    if db is None:
        return []

    def op():
        rows = []
        for snap in db.collection(_USERS).limit(limit).stream():
            data = snap.to_dict() or {}
            data["telegram_id"] = data.get("telegram_id") or int(snap.id)
            rows.append(data)
        return rows

    return await _run(op, []) or []


# ============================== BUYURTMALAR ==============================
async def fb_save_order(telegram_id, service, topic=None, options=None, price=0,
                        status="done", created_at=None):
    """Buyurtmani saqlash — statistika kod yangilangandan keyin ham qoladi."""
    if db is None:
        return

    def op():
        db.collection(_ORDERS).add(_clean({
            "telegram_id": int(telegram_id),
            "user_id": int(telegram_id),
            "service": service,
            "topic": topic,
            "options": json.dumps(options, ensure_ascii=False) if isinstance(options, (dict, list)) else options,
            "price": price,
            "status": status,
            "created_at": created_at,
            "saved_at": firestore.SERVER_TIMESTAMP,
        }))

    await _run(op)


async def fb_load_orders(limit=5000):
    if db is None:
        return []

    def op():
        rows = []
        query = db.collection(_ORDERS).order_by("created_at").limit(limit)
        for snap in query.stream():
            data = snap.to_dict() or {}
            data["fb_id"] = snap.id
            rows.append(data)
        return rows

    return await _run(op, []) or []


async def fb_order_count():
    if db is None:
        return 0

    def op():
        return len(list(db.collection(_ORDERS).limit(5000).stream()))

    return await _run(op, 0) or 0


# ============================ AI CHAT TARIXI ============================
async def fb_save_chat(telegram_id, messages):
    """Suhbatning oxirgi xabarlarini bitta hujjatda saqlash."""
    if db is None:
        return

    def op():
        db.collection(_CHATS).document(str(telegram_id)).set({
            "telegram_id": int(telegram_id),
            "messages": messages[-40:],
            "updated_at": firestore.SERVER_TIMESTAMP,
        }, merge=True)

    await _run(op)


async def fb_load_chat(telegram_id):
    if db is None:
        return []

    def op():
        snap = db.collection(_CHATS).document(str(telegram_id)).get()
        if not snap.exists:
            return []
        return (snap.to_dict() or {}).get("messages", [])

    return await _run(op, []) or []


async def fb_delete_chat(telegram_id):
    if db is None:
        return

    def op():
        db.collection(_CHATS).document(str(telegram_id)).delete()

    await _run(op)


# ============================== HARAKATLAR ==============================
async def fb_save_setting(key, value):
    """Admin o'zgartirgan sozlama (narx, to'lov rekviziti, kanal) saqlanadi."""
    if db is None:
        return

    def op():
        db.collection(_SETTINGS).document(str(key)).set({
            "key": str(key), "value": str(value),
            "updated_at": firestore.SERVER_TIMESTAMP,
        }, merge=True)

    await _run(op)


async def fb_load_settings():
    if db is None:
        return {}

    def op():
        data = {}
        for snap in db.collection(_SETTINGS).stream():
            row = snap.to_dict() or {}
            data[str(row.get("key") or snap.id)] = row.get("value")
        return data

    return await _run(op, {}) or {}


async def fb_log_action(telegram_id, action_type, topic=None, service_type=None):
    if db is None:
        return

    def op():
        db.collection(_ACTIONS).add({
            "telegram_id": int(telegram_id),
            "action_type": action_type,
            "topic": topic,
            "service_type": service_type,
            "created_at": firestore.SERVER_TIMESTAMP,
        })

    await _run(op)


# Eski kod bilan moslik uchun nom saqlanadi.
async def fb_add_user(telegram_id, username=None, first_name=None, last_name=None,
                      lang="uz", count_use=True, **kwargs):
    await fb_save_user(telegram_id, username=username, first_name=first_name,
                       last_name=last_name, lang=lang, count_use=count_use, **kwargs)
