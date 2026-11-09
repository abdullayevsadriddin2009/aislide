import aiosqlite
import json
import time
import db_firebase
from config import DB_PATH, FREE_MODE, DEFAULT_PAYMENT_INFO
from services import DEFAULT_REFERRAL_BONUS

_db = None
_FB_RESTORED = False

async def get_db():
    global _db
    if _db is None:
        _db = await aiosqlite.connect(DB_PATH)
        await _db.execute("PRAGMA journal_mode=WAL;")
        _db.row_factory = aiosqlite.Row
        await _init()
    return _db

async def _init():
    db = await get_db()
    await db.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        telegram_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        lang TEXT DEFAULT 'uz',
        balance INTEGER DEFAULT 0,
        bonus_balance INTEGER DEFAULT 0,
        referred_by INTEGER,
        default_pages INTEGER DEFAULT 10,
        premium INTEGER DEFAULT 0,
        bonus_awarded INTEGER DEFAULT 0,
        created_at INTEGER
    );
    CREATE TABLE IF NOT EXISTS referrals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        referrer_id INTEGER,
        referred_id INTEGER,
        earned INTEGER DEFAULT 0,
        created_at INTEGER,
        UNIQUE(referred_id)
    );
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, service TEXT, topic TEXT, options TEXT,
        price INTEGER DEFAULT 0, status TEXT DEFAULT 'done',
        result TEXT, created_at INTEGER
    );
    CREATE TABLE IF NOT EXISTS checks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, amount INTEGER, photo_file_id TEXT,
        status TEXT DEFAULT 'pending', created_at INTEGER, reviewed_by INTEGER
    );
    CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
    CREATE TABLE IF NOT EXISTS chat_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        role TEXT,
        content TEXT,
        created_at INTEGER
    );
    CREATE INDEX IF NOT EXISTS idx_chat_user ON chat_messages(user_id, id);
    """)
    await db.commit()
    # Migratsiya — eski bazaga yangi ustunlarni qo'shish
    for col, typ in [("bonus_awarded", "INTEGER DEFAULT 0"), ("default_pages", "INTEGER DEFAULT 10"),
                     ("premium", "INTEGER DEFAULT 0"), ("bonus_balance", "INTEGER DEFAULT 0"),
                     ("lang_set", "INTEGER DEFAULT 0")]:
        try:
            await db.execute(f"ALTER TABLE users ADD COLUMN {col} {typ}")
            await db.commit()
        except Exception:
            pass
    # Mini App yaratgan fayllar buyurtmaga bog'lanadi (istalgan vaqtda yuklab olish uchun).
    for col, typ in [("file_path", "TEXT"), ("file_name", "TEXT")]:
        try:
            await db.execute(f"ALTER TABLE orders ADD COLUMN {col} {typ}")
            await db.commit()
        except Exception:
            pass
    await _restore_from_firebase()
    await set_setting("payment_info", DEFAULT_PAYMENT_INFO, if_not_exists=True)
    await set_setting("free_mode", "1" if FREE_MODE else "0", if_not_exists=True)
    await set_setting("referral_bonus", str(DEFAULT_REFERRAL_BONUS), if_not_exists=True)


# ---------- Firebase'dan tiklash (kod yangilanganda ma'lumot yo'qolmasin) ----------
async def _restore_from_firebase():
    """Firestore'dagi foydalanuvchi, buyurtma va sozlamalarni SQLite'ga qaytaradi.

    Hostingda fayl tizimi yangilanishda tozalansa ham ma'lumot tiklanadi.
    Mavjud lokal yozuvlar ustidan yozilmaydi (INSERT OR IGNORE).
    """
    global _FB_RESTORED
    if _FB_RESTORED:
        return
    _FB_RESTORED = True
    if not db_firebase.is_enabled():
        return
    db = await get_db()
    users_restored = 0
    try:
        for data in await db_firebase.fb_load_users():
            try:
                uid = int(data.get("telegram_id") or 0)
            except (TypeError, ValueError):
                continue
            if not uid:
                continue
            cur = await db.execute(
                "INSERT OR IGNORE INTO users(telegram_id,username,first_name,lang,balance,bonus_balance,"
                "referred_by,premium,created_at,lang_set) VALUES(?,?,?,?,?,?,?,?,?,1)",
                (uid, data.get("username"), data.get("first_name"),
                 data.get("lang") if data.get("lang") in ("uz", "ru", "en", "tr", "de", "fr") else "uz",
                 int(data.get("balance") or 0), int(data.get("bonus_balance") or 0),
                 data.get("referred_by"), int(data.get("premium") or 0),
                 int(data.get("created_at") or time.time())))
            users_restored += 1 if cur.rowcount > 0 else 0
        await db.commit()
    except Exception as exc:
        print(f"[FB] foydalanuvchilarni tiklashda xato: {exc}", flush=True)

    orders_restored = 0
    try:
        if await order_count() == 0:
            for order in await db_firebase.fb_load_orders():
                await db.execute(
                    "INSERT INTO orders(user_id,service,topic,options,price,status,result,created_at) "
                    "VALUES(?,?,?,?,?,?,?,?)",
                    (int(order.get("telegram_id") or order.get("user_id") or 0),
                     order.get("service"), order.get("topic"), order.get("options"),
                     int(order.get("price") or 0), order.get("status") or "done",
                     None, int(order.get("created_at") or 0)))
                orders_restored += 1
            await db.commit()
    except Exception as exc:
        print(f"[FB] buyurtmalarni tiklashda xato: {exc}", flush=True)

    settings_restored = 0
    try:
        # Admin o'zgartirgan sozlamalar (narxlar, to'lov, kanal) ustuvor bo'ladi.
        for key, value in (await db_firebase.fb_load_settings()).items():
            await db.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (key, str(value)))
            settings_restored += 1
        await db.commit()
    except Exception as exc:
        print(f"[FB] sozlamalarni tiklashda xato: {exc}", flush=True)

    if users_restored or orders_restored or settings_restored:
        print(f"[FB] tiklandi: {users_restored} user, {orders_restored} buyurtma, "
              f"{settings_restored} sozlama", flush=True)


async def _mirror_user(telegram_id):
    """Foydalanuvchining joriy holatini Firestore'ga yozish."""
    if not db_firebase.is_enabled():
        return
    try:
        u = await get_user(telegram_id)
        if not u:
            return
        await db_firebase.fb_save_user(
            telegram_id, username=u["username"], first_name=u["first_name"],
            lang=u["lang"], balance=u["balance"], bonus_balance=u["bonus_balance"],
            premium=u["premium"], referred_by=u["referred_by"], created_at=u["created_at"])
    except Exception as exc:
        print(f"[FB] user mirror xato: {exc}", flush=True)

# ---------- settings ----------
async def get_setting(key, default=None):
    db = await get_db()
    cur = await db.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = await cur.fetchone()
    return row["value"] if row else default

async def set_setting(key, value, if_not_exists=False):
    db = await get_db()
    if if_not_exists:
        cur = await db.execute("SELECT 1 FROM settings WHERE key=?", (key,))
        if await cur.fetchone():
            return
    await db.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (key, value))
    await db.commit()
    if db_firebase.is_enabled():
        await db_firebase.fb_save_setting(key, value)

# ---------- users ----------
async def get_user(telegram_id):
    db = await get_db()
    cur = await db.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,))
    return await cur.fetchone()

async def ensure_user(telegram_id, username=None, first_name=None, referred_by=None):
    db = await get_db()
    u = await get_user(telegram_id)
    if u is None:
        try:
            await db.execute(
                "INSERT OR IGNORE INTO users(telegram_id,username,first_name,referred_by,created_at) VALUES(?,?,?,?,?)",
                (telegram_id, username, first_name, referred_by, int(time.time())))
            await db.commit()
        except Exception:
            pass
        if referred_by and referred_by != telegram_id:
            try:
                await db.execute(
                    "INSERT OR IGNORE INTO referrals(referrer_id,referred_id,created_at) VALUES(?,?,?)",
                    (referred_by, telegram_id, int(time.time())))
                await db.commit()
            except Exception:
                pass
        await _mirror_user(telegram_id)
        return await get_user(telegram_id)
    return u

async def update_user(telegram_id, **fields):
    db = await get_db()
    for k, v in fields.items():
        await db.execute(f"UPDATE users SET {k}=? WHERE telegram_id=?", (v, telegram_id))
    await db.commit()
    await _mirror_user(telegram_id)

async def add_balance(telegram_id, amount):
    db = await get_db()
    await db.execute("UPDATE users SET balance=balance+? WHERE telegram_id=?", (amount, telegram_id))
    await db.commit()
    await _mirror_user(telegram_id)

async def add_bonus_balance(telegram_id, amount):
    db = await get_db()
    await db.execute("UPDATE users SET bonus_balance=bonus_balance+? WHERE telegram_id=?", (amount, telegram_id))
    await db.commit()
    await _mirror_user(telegram_id)

async def all_users():
    db = await get_db()
    cur = await db.execute("SELECT * FROM users")
    return await cur.fetchall()

async def user_count():
    db = await get_db()
    cur = await db.execute("SELECT COUNT(*) c FROM users")
    return (await cur.fetchone())["c"]

async def total_balance():
    db = await get_db()
    cur = await db.execute("SELECT COALESCE(SUM(balance),0) s FROM users")
    return (await cur.fetchone())["s"]

# ---------- referrals ----------
async def referral_stats(telegram_id):
    db = await get_db()
    cur = await db.execute("SELECT COUNT(*) c, COALESCE(SUM(earned),0) e FROM referrals WHERE referrer_id=?", (telegram_id,))
    row = await cur.fetchone()
    return row["c"], row["e"]

async def get_referrer(telegram_id):
    u = await get_user(telegram_id)
    return u["referred_by"] if u else None

async def add_referral_earned(referrer_id, amount):
    db = await get_db()
    await db.execute("UPDATE referrals SET earned=earned+? WHERE referrer_id=?", (amount, referrer_id))
    await db.commit()

# ---------- orders ----------
async def add_order(user_id, service, topic, options, price, result):
    db = await get_db()
    created = int(time.time())
    cur = await db.execute(
        "INSERT INTO orders(user_id,service,topic,options,price,result,created_at) VALUES(?,?,?,?,?,?,?)",
        (user_id, service, topic, json.dumps(options, ensure_ascii=False), price, result, created))
    await db.commit()
    if db_firebase.is_enabled():
        await db_firebase.fb_save_order(user_id, service, topic=topic, options=options,
                                       price=price, created_at=created)
    return cur.lastrowid

async def order_count(user_id=None):
    db = await get_db()
    if user_id:
        cur = await db.execute("SELECT COUNT(*) c FROM orders WHERE user_id=?", (user_id,))
    else:
        cur = await db.execute("SELECT COUNT(*) c FROM orders")
    return (await cur.fetchone())["c"]

# ---------- checks ----------
async def add_check(user_id, amount, photo_file_id):
    db = await get_db()
    cur = await db.execute(
        "INSERT INTO checks(user_id,amount,photo_file_id,created_at) VALUES(?,?,?,?)",
        (user_id, amount, photo_file_id, int(time.time())))
    await db.commit()
    return cur.lastrowid

async def pending_checks():
    db = await get_db()
    cur = await db.execute("SELECT * FROM checks WHERE status='pending' ORDER BY id")
    return await cur.fetchall()

async def get_check(check_id):
    db = await get_db()
    cur = await db.execute("SELECT * FROM checks WHERE id=?", (check_id,))
    return await cur.fetchone()

async def review_check(check_id, status, reviewed_by):
    db = await get_db()
    await db.execute("UPDATE checks SET status=?, reviewed_by=? WHERE id=?", (status, reviewed_by, check_id))
    await db.commit()

async def pending_check_count():
    db = await get_db()
    cur = await db.execute("SELECT COUNT(*) c FROM checks WHERE status='pending'")
    return (await cur.fetchone())["c"]

async def total_deposited(user_id):
    db = await get_db()
    cur = await db.execute("SELECT COALESCE(SUM(amount),0) s FROM checks WHERE user_id=? AND status='approved'", (user_id,))
    return (await cur.fetchone())["s"]

# ---------- prices ----------
async def get_price(service_code):
    from services import SERVICES
    default = SERVICES.get(service_code, {}).get("price", 0)
    val = await get_setting(f"price_{service_code}", str(default))
    try:
        return int(val)
    except Exception:
        return default

async def set_price(service_code, amount):
    await set_setting(f"price_{service_code}", str(amount))

async def get_all_prices():
    from services import SERVICES
    prices = {}
    for code in SERVICES:
        prices[code] = await get_price(code)
    return prices

# ---------- referral bonus ----------
async def get_referral_bonus():
    val = await get_setting("referral_bonus", str(DEFAULT_REFERRAL_BONUS))
    try:
        return int(val)
    except Exception:
        return DEFAULT_REFERRAL_BONUS

async def set_referral_bonus(amount):
    await set_setting("referral_bonus", str(amount))


# ---------- AI Chat tarixi ----------
async def add_chat_message(user_id, role, content, keep=40):
    """Suhbat xabarini saqlash va eskilarini qisqartirish."""
    role = "assistant" if str(role).lower() in ("assistant", "ai", "bot") else "user"
    text = str(content or "").strip()
    if not text:
        return
    db = await get_db()
    await db.execute(
        "INSERT INTO chat_messages(user_id,role,content,created_at) VALUES(?,?,?,?)",
        (user_id, role, text[:8000], int(time.time())))
    await db.execute(
        "DELETE FROM chat_messages WHERE user_id=? AND id NOT IN "
        "(SELECT id FROM chat_messages WHERE user_id=? ORDER BY id DESC LIMIT ?)",
        (user_id, user_id, keep))
    await db.commit()
    if db_firebase.is_enabled():
        await db_firebase.fb_save_chat(user_id, await get_chat_history(user_id, keep))


async def get_chat_history(user_id, limit=12):
    """Oxirgi xabarlar (eng eskidan yangiga) — AI konteksti uchun."""
    db = await get_db()
    cur = await db.execute(
        "SELECT role, content FROM chat_messages WHERE user_id=? ORDER BY id DESC LIMIT ?",
        (user_id, limit))
    rows = await cur.fetchall()
    if not rows and db_firebase.is_enabled():
        # Lokal fayl yo'qolgan bo'lsa, suhbatni Firestore'dan tiklaymiz.
        remote = await db_firebase.fb_load_chat(user_id)
        for msg in remote[-limit:]:
            if isinstance(msg, dict) and str(msg.get("content") or "").strip():
                await db.execute(
                    "INSERT INTO chat_messages(user_id,role,content,created_at) VALUES(?,?,?,?)",
                    (user_id, "assistant" if msg.get("role") == "assistant" else "user",
                     str(msg.get("content"))[:8000], int(time.time())))
        if remote:
            await db.commit()
            cur = await db.execute(
                "SELECT role, content FROM chat_messages WHERE user_id=? ORDER BY id DESC LIMIT ?",
                (user_id, limit))
            rows = await cur.fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(list(rows))]


async def chat_message_count(user_id):
    db = await get_db()
    cur = await db.execute("SELECT COUNT(*) c FROM chat_messages WHERE user_id=?", (user_id,))
    return (await cur.fetchone())["c"]


async def clear_chat_history(user_id):
    """Suhbatni o'chirib, yangi mavzu boshlash imkonini beradi."""
    db = await get_db()
    await db.execute("DELETE FROM chat_messages WHERE user_id=?", (user_id,))
    await db.commit()
    if db_firebase.is_enabled():
        await db_firebase.fb_delete_chat(user_id)

