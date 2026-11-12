"""Admin boshqaradigan AI kalitlari, modellari va chat sozlamalari.

CdxChatBot.php mantiqi: bir nechta API kalit saqlanadi, xato bergan kalitning
`fails` hisoblagichi oshadi va keyingi urinishda boshqa kalit birinchi sinaladi.
Kalitlar, modellar va chat sozlamalari bot ichidagi admin paneldan boshqariladi.
"""
import os
import sqlite3
import threading
import time

import config

_LOCK = threading.RLock()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ai_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL DEFAULT '',
    provider TEXT NOT NULL DEFAULT 'openai',
    api_key TEXT NOT NULL,
    base_url TEXT NOT NULL DEFAULT '',
    models TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1,
    fails INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS ai_models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    active INTEGER NOT NULL DEFAULT 1,
    is_default INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS ai_settings (
    k TEXT PRIMARY KEY,
    v TEXT NOT NULL DEFAULT ''
);
"""

_PROVIDER_BASE = {
    "groq": "https://api.groq.com/openai/v1",
    "google": "https://generativelanguage.googleapis.com/v1beta",
    "cloudflare": ("https://api.cloudflare.com/client/v4/accounts/"
                   "283bb72354435f9cfd19a80c3edc93e0/ai/v1"),
    "openai": "",
}

_PROVIDER_MODELS = {
    "groq": ("qwen/qwen3.8-27b", "allam-2-7b", "openai/gpt-oss-120b", "openai/gpt-oss-20b"),
    "google": ("gemini-2.5-flash", "gemini-flash-lite-latest", "gemini-3.5-flash",
               "gemini-2.0-flash"),
    "cloudflare": ("@cf/meta/llama-3.2-3b-instruct", "@cf/meta/llama-3.2-1b-instruct",
                   "@cf/openai/gpt-oss-120b", "@cf/qwen/qwen3.8-27b"),
    "openai": (),
}

# CdxChatBot.php dagi settings jadvali bilan bir xil kalitlar.
CHAT_DEFAULTS = {
    "system_prompt": ("Sen foydali AI yordamchisan. Foydalanuvchi qaysi tilda yozsa, "
                      "shu tilda aniq va qisqa javob ber."),
    "welcome_text": "",
    "error_text": "",
    "temperature": "0.7",
    "max_tokens": "2600",
    "history_limit": "16",
    "markdown": "1",
    "draft_stream": "1",
}


def _connect():
    con = sqlite3.connect(config.DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout=5000")
    return con


def _query(sql, args=()):
    con = _connect()
    try:
        return con.execute(sql, args).fetchall()
    finally:
        con.close()


def _exec(sql, args=()):
    con = _connect()
    try:
        con.execute(sql, args)
        con.commit()
    finally:
        con.close()


_SYNCED_PATHS = set()


def ensure():
    """Jadvallarni yaratadi va muhitdagi (Render) kalitlarni bazaga qo'shadi.

    Muhit kalitlari har ishga tushishda tekshiriladi: Renderda yangi kalit
    qo'shilsa, u bazada hali yo'q bo'lsa avtomatik qo'shiladi. Admin panelda
    qo'lda qo'shilgan kalitlar va o'chirilgan kalitlar tegilmaydi.
    """
    with _LOCK:
        con = _connect()
        try:
            con.executescript(_SCHEMA)
            path = os.path.abspath(str(config.DB_PATH))
            if path not in _SYNCED_PATHS:
                existing = {row[0] for row in con.execute("SELECT api_key FROM ai_keys")}
                added = 0
                for row in _env_keys():
                    if row["api_key"] in existing:
                        continue
                    con.execute(
                        "INSERT INTO ai_keys(label,provider,api_key,base_url,models,created_at)"
                        " VALUES(?,?,?,?,?,?)",
                        (row["label"], row["provider"], row["api_key"], row["base_url"],
                         ",".join(row["models"]), time.strftime("%Y-%m-%d %H:%M:%S")),
                    )
                    added += 1
                if added:
                    print(f"[ai_pool] muhitdan {added} ta AI kalit qo'shildi", flush=True)
                _SYNCED_PATHS.add(path)
            for key, value in CHAT_DEFAULTS.items():
                con.execute("INSERT OR IGNORE INTO ai_settings(k,v) VALUES(?,?)", (key, value))
            # PHP dagi kabi boshlang'ich model (admin panelda o'zgartiriladi).
            if con.execute("SELECT COUNT(*) FROM ai_models").fetchone()[0] == 0:
                con.execute("INSERT INTO ai_models(name,active,is_default) VALUES(?,1,1)",
                            ("gemini-2.5-flash",))
            con.commit()
        finally:
            con.close()


def _env_keys():
    """Muhit o'zgaruvchilaridagi mavjud kalitlar (bir marta ko'chiriladi)."""
    rows = []
    try:  # ai_api ni kech import qilamiz: u ham shu modulni ishlatadi.
        import ai_api
        for api in getattr(ai_api, "API_LIST", []):
            key = str(api.get("api_key") or "").strip()
            if not key:
                continue
            base = str(api.get("base_url") or "")
            provider = "google" if "generativelanguage" in base else (
                "groq" if "groq.com" in base else (
                    "cloudflare" if "cloudflare" in base else "openai"))
            rows.append({
                "label": str(api.get("name") or provider)[:60],
                "provider": provider,
                "api_key": key,
                "base_url": base,
                "models": tuple(api.get("models") or _PROVIDER_MODELS.get(provider, ())),
            })
    except Exception:
        pass
    return rows


def keys(active_only=False):
    ensure()
    sql = "SELECT * FROM ai_keys" + (" WHERE active=1" if active_only else "") + \
          " ORDER BY fails ASC, id ASC"
    return [dict(row) for row in _query(sql)]


def add_key(label, api_key, provider="openai", base_url="", models=""):
    api_key = str(api_key or "").strip()
    if not api_key:
        return False
    provider = str(provider or "openai").strip().lower()
    if provider not in _PROVIDER_BASE:
        provider = "openai"
    ensure()
    _exec("INSERT INTO ai_keys(label,provider,api_key,base_url,models,created_at) VALUES(?,?,?,?,?,?)",
          (str(label or "").strip()[:60], provider, api_key, str(base_url or "").strip(),
           str(models or "").strip(), time.strftime("%Y-%m-%d %H:%M:%S")))
    return True


def toggle_key(key_id):
    _exec("UPDATE ai_keys SET active=1-active, fails=0 WHERE id=?", (int(key_id),))


def delete_key(key_id):
    _exec("DELETE FROM ai_keys WHERE id=?", (int(key_id),))


def mark_result(key_id, ok):
    if not key_id:
        return
    try:
        if ok:
            _exec("UPDATE ai_keys SET fails=0 WHERE id=?", (int(key_id),))
        else:
            _exec("UPDATE ai_keys SET fails=fails+1 WHERE id=?", (int(key_id),))
    except Exception:
        pass


def models():
    ensure()
    return [dict(row) for row in
            _query("SELECT * FROM ai_models ORDER BY is_default DESC, id ASC")]


def add_model(name):
    name = str(name or "").strip()
    if not name:
        return False
    ensure()
    _exec("INSERT OR IGNORE INTO ai_models(name) VALUES(?)", (name,))
    return True


def toggle_model(model_id):
    _exec("UPDATE ai_models SET active=1-active WHERE id=?", (int(model_id),))


def set_default_model(model_id):
    _exec("UPDATE ai_models SET is_default=0")
    _exec("UPDATE ai_models SET is_default=1, active=1 WHERE id=?", (int(model_id),))


def delete_model(model_id):
    _exec("DELETE FROM ai_models WHERE id=?", (int(model_id),))


def setting(key, default=""):
    ensure()
    rows = _query("SELECT v FROM ai_settings WHERE k=?", (str(key),))
    return str(rows[0]["v"]) if rows else str(default)


def set_setting(key, value):
    ensure()
    _exec("INSERT INTO ai_settings(k,v) VALUES(?,?) "
          "ON CONFLICT(k) DO UPDATE SET v=excluded.v", (str(key), str(value)))


def note_error(text):
    set_setting("last_error", str(text or "")[:400])


def last_error():
    return setting("last_error", "")


def chat_system_prompt():
    return setting("system_prompt", CHAT_DEFAULTS["system_prompt"]).strip()


def chat_temperature():
    try:
        return max(0.0, min(2.0, float(setting("temperature", "0.7"))))
    except (TypeError, ValueError):
        return 0.7


def chat_max_tokens():
    try:
        return max(64, min(8192, int(setting("max_tokens", "2600"))))
    except (TypeError, ValueError):
        return 2600


def chat_history_limit():
    try:
        return max(0, min(40, int(setting("history_limit", "16"))))
    except (TypeError, ValueError):
        return 16


def chat_markdown():
    return setting("markdown", "1") != "0"


def chat_welcome():
    """`/start` (AI chat) uchun matn; bo'sh bo'lsa bot o'z tarjima matnini ishlatadi."""
    return setting("welcome_text", "").strip()


def chat_error():
    """AI javob bera olmaganda foydalanuvchiga ko'rinadigan matn."""
    return setting("error_text", "").strip()


def chat_draft_stream():
    """Javobni yozilayotgandek ko'rsatish (sendMessageDraft) yoqilganmi."""
    return setting("draft_stream", "1") != "0"


def note_draft_error(text):
    set_setting("draft_error", str(text or "")[:300])


def draft_error():
    return setting("draft_error", "")


def runtime_apis():
    """Faol kalitlar → `ai_api` kutgan provayder ro'yxati (xatolar bo'yicha tartib)."""
    # Admin panelda belgilangan modellar tartibi (asosiy model eng oldinda).
    preferred = [m["name"] for m in models() if m["active"]]
    defaults = [m["name"] for m in models() if m["active"] and m["is_default"]]
    apis = []
    for row in keys(active_only=True):
        provider = str(row["provider"] or "openai")
        names = [name.strip() for name in str(row["models"] or "").split(",") if name.strip()]
        if not names:
            names = list(_PROVIDER_MODELS.get(provider, ()))
        if not names:
            # AI_MODEL=auto bo'lgan OpenAI-mos provayder: model ro'yxati
            # `/models` manzilidan jonli olinadi (`ai_api._models_for_api`).
            if provider == "openai" and (row["base_url"] or ""):
                apis.append({
                    "key_id": row["id"],
                    "name": row["label"] or provider,
                    "base_url": row["base_url"],
                    "api_key": row["api_key"],
                    "type": "openai",
                    "models": [],
                })
            continue
        inside = [name for name in names]
        ordered = [name for name in defaults if name in inside]
        ordered += [name for name in preferred if name in inside and name not in ordered]
        names = ordered + [name for name in inside if name not in ordered]
        apis.append({
            "key_id": row["id"],
            "name": row["label"] or provider,
            "base_url": row["base_url"] or _PROVIDER_BASE.get(provider, ""),
            "api_key": row["api_key"],
            "type": "google" if provider == "google" else "openai",
            "models": names,
        })
    return apis


PROVIDER_BASE = _PROVIDER_BASE
PROVIDER_MODELS = _PROVIDER_MODELS


def provider_choices():
    return ("groq", "google", "cloudflare", "openai")


def mask(value):
    text = str(value or "")
    return text[:6] + "…" + text[-4:] if len(text) > 12 else "•" * min(8, len(text))
