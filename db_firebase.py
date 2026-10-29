import firebase_admin
from firebase_admin import credentials, firestore
import os

# Renderda /etc/secrets/ da, kompyuterda papka ichida bo'ladi
KEY_PATHS = ["/etc/secrets/firebase_key.json", "firebase_key.json"]

_key_file = None
for _p in KEY_PATHS:
    if os.path.exists(_p):
        _key_file = _p
        break

db = None
if _key_file:
    try:
        _cred = credentials.Certificate(_key_file)
        if not firebase_admin._apps:
            firebase_admin.initialize_app(_cred)
        db = firestore.client()
        print(f"✅ Firebase ga ulandi! Kalit: {_key_file}", flush=True)
    except Exception as e:
        print(f"⚠️ Firebase ulanish xatosi: {e}", flush=True)
else:
    print("⚠️ firebase_key.json topilmadi — Firebase o'chirilgan.", flush=True)


async def fb_add_user(telegram_id, username=None, first_name=None, last_name=None, lang='uz'):
    """Foydalanuvchini Firebase-ga saqlash (mavjud bo'lsa yangilaydi)"""
    if not db: return
    try:
        doc = db.collection("users").document(str(telegram_id))
        doc.set({
            "telegram_id": telegram_id,
            "username": username,
            "first_name": first_name,
            "last_name": last_name,
            "lang": lang,
            "last_seen": firestore.SERVER_TIMESTAMP,
        }, merge=True)
        # Foydalanish sonini 1 ga oshirish
        doc.update({"total_uses": firestore.Increment(1)})
    except Exception as e:
        print(f"[FB] add_user xato: {e}", flush=True)


async def fb_log_action(telegram_id, action_type, topic=None, service_type=None):
    """Harakatni saqlash"""
    if not db: return
    try:
        db.collection("user_actions").add({
            "telegram_id": telegram_id,
            "action_type": action_type,
            "topic": topic,
            "service_type": service_type,
            "created_at": firestore.SERVER_TIMESTAMP,
        })
    except Exception as e:
        print(f"[FB] log_action xato: {e}", flush=True)
