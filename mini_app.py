"""Telegram Mini App — backend (Flask blueprint).

Sahifa:      GET  /app
JSON API:    POST /api/mini/init      — initData tekshiruvi, profil + xizmatlar
             POST /api/mini/plan      — insho uchun REJA
             POST /api/mini/generate  — hujjat/slayd yaratishni navbatga qo'yish
             GET  /api/mini/job       — holat
             GET  /api/mini/download  — tayyor fayl
             GET  /api/mini/orders    — oxirgi buyurtmalar
             GET  /api/mini/profile   — balans va sozlamalar

Mini App bot bilan bir Flask jarayonida (Render'dagi bitta port) ishlaydi.
"""
import asyncio
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import threading
import time
import uuid
from urllib.parse import parse_qsl

from flask import Blueprint, Response, jsonify, request, send_file

import config
from services import ALL_LANGS, SERVICES, service_name

mini = Blueprint("mini_app", __name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEBAPP_FILE = os.path.join(BASE_DIR, "webapp", "index.html")
OUTPUT_DIR = os.path.join(config.DATA_DIR, "mini")
# Buyurtma fayllari doimiy saqlanadi: 3 soatlik vaqtinchalik papkadan farqli,
# istalgan vaqtda yuklab olish mumkin.
FILES_DIR = os.path.join(config.DATA_DIR, "files")

JOBS = {}
TOKENS = {}
_LOCK = threading.Lock()
_SEMAPHORE = threading.BoundedSemaphore(max(1, int(os.getenv("MINI_MAX_JOBS", "2"))))
JOB_TTL = 3 * 3600
TOKEN_TTL = 12 * 3600
MAX_ACTIVE_PER_USER = 3

# To'liq titul varaq talab qiladigan xizmatlar (institut, fakultet, kafedra...).
TITLE_SERVICES = ("referat", "mustaqil", "kurs", "diplom")
COMPACT_AUTHOR_SERVICES = ("maqola", "tezis", "insho", "esse")


# =====================  Bazaga yordamchi funksiyalar  =====================
def _db():
    con = sqlite3.connect(config.DB_PATH, timeout=15)
    con.row_factory = sqlite3.Row
    return con


def _setting(key, default=""):
    try:
        with _db() as con:
            row = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default
    except Exception:
        return default


def _price(service):
    default = int(SERVICES.get(service, {}).get("price", 0) or 0)
    try:
        return int(_setting(f"price_{service}", str(default)))
    except (TypeError, ValueError):
        return default


def _ensure_user(tg_id, username=None, first_name=None):
    """Mini App'dan kirgan foydalanuvchini bazaga yozadi (bot bilan bir xil jadval)."""
    tg_id = int(tg_id)
    with _db() as con:
        con.execute(
            "INSERT OR IGNORE INTO users(telegram_id,username,first_name,created_at) VALUES(?,?,?,?)",
            (tg_id, username, first_name, int(time.time())),
        )
        con.commit()
        row = con.execute("SELECT * FROM users WHERE telegram_id=?", (tg_id,)).fetchone()
    return row


def _profile(uid):
    try:
        with _db() as con:
            row = con.execute("SELECT * FROM users WHERE telegram_id=?", (uid,)).fetchone()
            orders = con.execute(
                "SELECT id,service,topic,options,price,status,created_at FROM orders "
                "WHERE user_id=? ORDER BY id DESC LIMIT 30", (uid,)
            ).fetchall()
    except Exception:
        return {"id": uid, "first_name": "", "username": "", "balance": 0,
                "bonus_balance": 0, "premium": 0, "lang": "uz"}, []
    data = {
        "id": uid,
        "first_name": (row["first_name"] if row else "") or "",
        "username": (row["username"] if row else "") or "",
        "balance": int((row["balance"] if row else 0) or 0),
        "bonus_balance": int((row["bonus_balance"] if row else 0) or 0),
        "premium": int((row["premium"] if row else 0) or 0),
        "lang": (row["lang"] if row and row["lang"] in ALL_LANGS else "uz"),
    }
    history = []
    for order in orders:
        try:
            options = json.loads(order["options"] or "{}")
        except Exception:
            options = {}
        history.append({
            "id": order["id"],
            "service": order["service"],
            "service_name": service_name(order["service"], data["lang"]),
            "topic": order["topic"],
            "options": options,
            "price": int(order["price"] or 0),
            "status": order["status"],
            "created_at": int(order["created_at"] or 0),
        })
    return data, history


# =====================  Autentifikatsiya  =====================
_LAST_INIT_ERROR = ""


def verify_init_data(init_data):
    """Telegram WebApp initData imzosini tekshiradi va user dict qaytaradi."""
    global _LAST_INIT_ERROR
    _LAST_INIT_ERROR = ""
    if not init_data:
        _LAST_INIT_ERROR = "no_init_data"
        return None
    if not config.BOT_TOKEN:
        _LAST_INIT_ERROR = "no_bot_token"
        return None
    try:
        parsed = dict(parse_qsl(str(init_data), keep_blank_values=True))
    except Exception:
        _LAST_INIT_ERROR = "bad_init_data"
        return None
    received = str(parsed.pop("hash", "") or "").strip()
    if not received:
        _LAST_INIT_ERROR = "no_hash"
        return None
    # Bot API 7.2+ `signature` maydonini ham yuboradi. Ba'zi mijozlar uni hash
    # hisobiga qo'shadi, ba'zilari qo'shmaydi — ikkala variantni ham tekshiramiz.
    variants = ["\n".join(f"{key}={parsed[key]}" for key in sorted(parsed))]
    if "signature" in parsed:
        without_signature = {key: value for key, value in parsed.items() if key != "signature"}
        variants.append("\n".join(f"{key}={without_signature[key]}" for key in sorted(without_signature)))
    secret = hmac.new(b"WebAppData", config.BOT_TOKEN.encode(), hashlib.sha256).digest()
    if not any(hmac.compare_digest(hmac.new(secret, variant.encode(), hashlib.sha256).hexdigest(), received)
               for variant in variants):
        _LAST_INIT_ERROR = "bad_hash"
        print("[mini] initData imzosi mos kelmadi (BOT_TOKEN yoki maydonlar)", flush=True)
        return None
    try:
        auth_date = int(parsed.get("auth_date") or 0)
    except (TypeError, ValueError):
        auth_date = 0
    if auth_date and time.time() - auth_date > 86400:
        _LAST_INIT_ERROR = "stale"
        return None
    user = {}
    if parsed.get("user"):
        try:
            user = json.loads(parsed["user"])
        except Exception:
            user = {}
    if not isinstance(user, dict) or not user.get("id"):
        _LAST_INIT_ERROR = "no_user"
        return None
    return user


def _issue_token(user_id):
    token = secrets.token_urlsafe(32)
    with _LOCK:
        TOKENS[token] = (int(user_id), time.time() + TOKEN_TTL)
    return token


def _token_user():
    token = (request.headers.get("X-Mini-Token")
             or request.args.get("token")
             or ((request.get_json(silent=True) or {}).get("token") if request.is_json else ""))
    if not token:
        return 0
    with _LOCK:
        entry = TOKENS.get(str(token))
    if not entry:
        return 0
    user_id, expires = entry
    if time.time() > expires:
        TOKENS.pop(str(token), None)
        return 0
    return user_id


def _unauthorized():
    return jsonify({"ok": False, "error": "auth", "message": "Mini App sessiyasi tugagan. Qayta oching."}), 401


# =====================  Xizmatlar ro'yxati  =====================
def _services_payload(lang):
    from designs import DESIGN_KEYS, SUBJECT_KEYS, design_name, subject_name

    items = []
    for code, info in SERVICES.items():
        options = [int(value) for value in (info.get("options") or ())]
        if not options:
            options = [10, 15, 20]
        items.append({
            "code": code,
            "emoji": info.get("emoji", "📄"),
            "name": service_name(code, lang),
            "names": {lc: service_name(code, lc) for lc in ALL_LANGS},
            "option_type": info.get("option_type", "pages"),
            "options": options,
            "price": _price(code),
            "title_fields": code in TITLE_SERVICES,
            "author_only": code in COMPACT_AUTHOR_SERVICES,
            "needs_plan": code == "insho",
        })
    return {
        "services": items,
        "designs": [{"key": key, "name": design_name(key, lang)} for key in DESIGN_KEYS],
        "subjects": [{"key": key, "name": subject_name(key, lang)} for key in SUBJECT_KEYS],
    }


@mini.route("/app")
@mini.route("/app/")
def mini_page():
    """Mini App sahifasi (Telegram WebApp SDK bilan)."""
    if not os.path.isfile(WEBAPP_FILE):
        return "Mini App topilmadi", 404
    with open(WEBAPP_FILE, "r", encoding="utf-8") as handle:
        html = handle.read()
    injected = []
    if os.getenv("MINI_DEV") == "1":
        # Faqat lokal demo: brauzerda Telegram imzosisiz ochish uchun.
        injected.append("window.__MINI_DEV__=true;")
    username = str(getattr(config, "BOT_USERNAME", "") or "").lstrip("@").strip()
    if username:
        # initData kelmasa sahifa shu havola orqali qayta ochishni taklif qiladi.
        injected.append("window.__BOT_LINK__=" + json.dumps(f"https://t.me/{username}") + ";")
    if injected:
        html = html.replace('"use strict";', '"use strict";' + "".join(injected), 1)
    return Response(html, mimetype="text/html")


@mini.route("/design-preview/<key>.png")
def design_preview_png(key):
    """6 ta dizaynning rasm ko'rinishi (botdagidek bir xil render)."""
    from design_preview import render_design_preview
    from designs import normalize_design_key
    lang = str(request.args.get("lang") or "uz").lower()
    image = render_design_preview(normalize_design_key(key), lang)
    response = Response(image, mimetype="image/png")
    response.headers["Cache-Control"] = "public, max-age=86400"
    return response


@mini.route("/api/mini/init", methods=["POST"])
def api_init():
    data = request.get_json(silent=True) or {}
    tg_user = verify_init_data(data.get("initData"))
    if tg_user is None and os.getenv("MINI_DEV") == "1":
        # Faqat lokal sinov uchun: Telegram imzosisiz ham ishlaydi.
        dev_id = int(data.get("dev_user") or 0)
        if dev_id:
            tg_user = {"id": dev_id, "first_name": "Local test", "username": "dev"}
    if not tg_user or not tg_user.get("id"):
        return jsonify({"ok": False, "error": "auth", "code": _LAST_INIT_ERROR or "auth",
                        "message": "Mini App faqat Telegram ichidan ochiladi."}), 401
    uid = int(tg_user["id"])
    row = _ensure_user(uid, tg_user.get("username"), tg_user.get("first_name"))
    profile, history = _profile(uid)
    lang = str(data.get("lang") or profile.get("lang") or "uz").lower()
    if lang not in ALL_LANGS:
        lang = profile.get("lang") if profile.get("lang") in ALL_LANGS else "uz"
    payload = {
        "ok": True,
        "token": _issue_token(uid),
        "user": profile,
        "history": history,
        "languages": list(ALL_LANGS),
        "free_mode": _setting("free_mode", "1") == "1",
        "max_active": MAX_ACTIVE_PER_USER,
    }
    payload.update(_services_payload(lang))
    return jsonify(payload)


@mini.route("/api/mini/profile", methods=["GET"])
def api_profile():
    uid = _token_user()
    if not uid:
        return _unauthorized()
    profile, history = _profile(uid)
    return jsonify({"ok": True, "user": profile, "history": history,
                    "free_mode": _setting("free_mode", "1") == "1"})


@mini.route("/api/mini/orders", methods=["GET"])
def api_orders():
    uid = _token_user()
    if not uid:
        return _unauthorized()
    _profile_data, history = _profile(uid)
    return jsonify({"ok": True, "orders": history})


@mini.route("/api/mini/order", methods=["GET"])
def api_order():
    """Bitta buyurtma tafsiloti (buyurtmalar ro'yxatidan bosilganda)."""
    uid = _token_user()
    if not uid:
        return _unauthorized()
    try:
        order_id = int(request.args.get("id") or 0)
    except (TypeError, ValueError):
        order_id = 0
    if not order_id:
        return jsonify({"ok": False, "error": "id", "message": "Buyurtma topilmadi."}), 404
    try:
        with _db() as con:
            row = con.execute(
                "SELECT id,service,topic,options,price,status,created_at FROM orders "
                "WHERE id=? AND user_id=?", (order_id, int(uid))
            ).fetchone()
    except Exception:
        row = None
    if not row:
        return jsonify({"ok": False, "error": "id", "message": "Buyurtma topilmadi."}), 404
    try:
        options = json.loads(row["options"] or "{}")
    except Exception:
        options = {}
    lang_row = _profile(uid)[0]
    job_id = None
    job = None
    for key, item in JOBS.items():
        if item.get("user_id") == uid and item.get("order_id") == order_id:
            job = item
            job_id = key
            break
    stored_path, stored_name = _order_file(uid, order_id)
    return jsonify({
        "ok": True,
        "download": bool(stored_path),
        "filename": stored_name,
        "order": {
            "id": row["id"],
            "service": row["service"],
            "service_name": service_name(row["service"], lang_row.get("lang", "uz")),
            "topic": row["topic"],
            "options": options,
            "price": int(row["price"] or 0),
            "status": row["status"],
            "created_at": int(row["created_at"] or 0),
        },
        "job": job_id if job and job.get("status") == "done" else None,
        "file": bool(job and job.get("file") and os.path.isfile(job["file"])),
    })


# =====================  AI Chat  =====================
def _chat_history(uid, limit=16):
    try:
        with _db() as con:
            rows = con.execute(
                "SELECT role, content FROM chat_messages WHERE user_id=? ORDER BY id DESC LIMIT ?",
                (int(uid), limit),
            ).fetchall()
    except Exception:
        return []
    return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]


def _chat_save(uid, role, text):
    try:
        with _db() as con:
            con.execute(
                "INSERT INTO chat_messages(user_id,role,content,created_at) VALUES(?,?,?,?)",
                (int(uid), role, str(text)[:8000], int(time.time())),
            )
            con.commit()
    except Exception:
        pass


@mini.route("/api/mini/chat", methods=["GET", "POST"])
def api_chat():
    """Botdagi AI Chat bilan bir xil suhbat (tarix umumiy)."""
    uid = _token_user()
    if not uid:
        return _unauthorized()
    if request.method == "GET":
        return jsonify({"ok": True, "messages": _chat_history(uid, 30)})

    data = request.get_json(silent=True) or {}
    message = re.sub(r"\s+", " ", str(data.get("message") or "")).strip()
    if not message:
        return jsonify({"ok": False, "error": "message", "message": "Savol bo'sh."}), 400
    message = message[:4000]
    lang = str(data.get("lang") or "uz").lower()
    if lang not in ALL_LANGS:
        lang = "uz"

    try:
        import ai_pool
        history_pairs = ai_pool.chat_history_limit() or 8
    except Exception:
        history_pairs = 8
    # "Juft xabar" — savol + javob, shuning uchun ikki barobar qator olinadi.
    history = _chat_history(uid, max(2, history_pairs * 2))
    try:
        from ai_api import chat_answer
        answer = asyncio.run(chat_answer(message, user_lang=lang, history=history))
    except Exception as exc:
        return jsonify({"ok": False, "error": "chat", "message": str(exc)[:200]}), 502
    if not answer or not str(answer).strip():
        try:
            import ai_pool
            custom_error = ai_pool.chat_error()
        except Exception:
            custom_error = ""
        return jsonify({"ok": False, "error": "chat",
                        "message": custom_error or "AI javob bermadi. Birozdan keyin urinib ko'ring."}), 502
    answer = str(answer).strip()[:8000]
    _chat_save(uid, "user", message)
    _chat_save(uid, "assistant", answer)
    return jsonify({"ok": True, "answer": answer})


# =====================  Insho REJA  =====================
@mini.route("/api/mini/plan", methods=["POST"])
def api_plan():
    uid = _token_user()
    if not uid:
        return _unauthorized()
    data = request.get_json(silent=True) or {}
    topic = re.sub(r"\s+", " ", str(data.get("topic") or "")).strip()
    lang = str(data.get("lang") or "uz").lower()
    if len(topic) < 3:
        return jsonify({"ok": False, "error": "topic", "message": "Mavzuni yozing."}), 400
    if lang not in ALL_LANGS:
        lang = "uz"
    try:
        pages = int(data.get("pages") or 3)
    except (TypeError, ValueError):
        pages = 3
    try:
        from ai_api import generate_insho_plan
        plan = asyncio.run(generate_insho_plan(topic, lang, pages))
    except Exception as exc:
        return jsonify({"ok": False, "error": "plan", "message": str(exc)[:200]}), 500
    return jsonify({"ok": True, "plan": plan})


# =====================  Generatsiya navbati  =====================
def _clean_jobs():
    now = time.time()
    with _LOCK:
        stale = [jid for jid, job in JOBS.items() if now - float(job.get("created", now)) > JOB_TTL]
    for jid in stale:
        job = JOBS.pop(jid, None)
        path = job.get("file") if job else None
        if path and os.path.isfile(path):
            try:
                os.remove(path)
            except OSError:
                pass


def _payload_options(service, data):
    info = SERVICES.get(service, {})
    option_type = info.get("option_type", "pages")
    allowed = [int(value) for value in (info.get("options") or (10, 15, 20))]
    options = {}
    raw = data.get("options") or {}
    if not isinstance(raw, dict):
        raw = {}
    if option_type in ("pages", "questions", "words"):
        try:
            value = int(raw.get(option_type) or raw.get("value") or allowed[0])
        except (TypeError, ValueError):
            value = allowed[0]
        if value not in allowed:
            value = min(allowed, key=lambda item: abs(item - value))
        options[option_type] = value
    if option_type == "slides":
        try:
            count = int(raw.get("count") or data.get("slide_count") or allowed[0])
        except (TypeError, ValueError):
            count = allowed[0]
        # Botdagi kabi faqat tayyor variantlar: 10 / 15 / 20.
        options["count"] = min(allowed, key=lambda item: abs(item - count))
    if service == "insho":
        options["plan"] = str(data.get("plan") or "")[:4000]
    return options


def _extra_data(service, data, options):
    return {
        "ref_institution": str(data.get("institution") or "").strip()[:160],
        "ref_faculty": str(data.get("faculty") or "").strip()[:120],
        "ref_dept": str(data.get("dept") or "").strip()[:120],
        "ref_subject": str(data.get("subject") or "").strip()[:120],
        "ref_author": str(data.get("author") or "").strip()[:120],
        "ref_checker": str(data.get("checker") or "").strip()[:120],
        "ref_email": str(data.get("email") or "").strip()[:120],
        "ref_brief": str(data.get("brief") or "").strip()[:400],
        "insho_plan": options.get("plan", ""),
    }


def _safe_name(text, fallback="document"):
    value = "".join(char for char in str(text or "")[:30] if char.isalnum() or char in " _-").strip()
    return (value.replace(" ", "_") or fallback)


def _start_job(user_id, payload):
    _clean_jobs()
    with _LOCK:
        active = sum(1 for job in JOBS.values()
                     if job.get("user_id") == user_id and job.get("status") in ("queued", "running"))
        if active >= MAX_ACTIVE_PER_USER:
            return None
        job_id = uuid.uuid4().hex
        JOBS[job_id] = {
            "id": job_id,
            "user_id": user_id,
            "status": "queued",
            "stage": "queued",
            "created": time.time(),
            "payload": payload,
        }
    threading.Thread(target=_worker, args=(job_id,), daemon=True).start()
    return job_id


def _worker(job_id):
    with _SEMAPHORE:
        try:
            asyncio.run(_generate(job_id))
        except Exception as exc:  # pragma: no cover - himoya qatlami
            job = JOBS.get(job_id)
            if job:
                job["status"] = "error"
                job["error"] = str(exc)[:300]


async def _generate(job_id):
    job = JOBS.get(job_id)
    if not job:
        return
    payload = job["payload"]
    service = payload["service"]
    topic = payload["topic"]
    lang = payload["lang"]
    options = payload["options"]
    fmt = payload.get("format", "docx")
    author = payload.get("author") or ""
    data = payload.get("extra") or {}
    try:
        job["status"] = "running"
        job["stage"] = "writing"

        if service == "slide":
            from pptx_generator import generate_pptx
            from ai_api import generate_slides_structured
            from designs import subject_name

            from services import slide_body_count, slide_image_total

            count = int(options.get("count") or 10)
            subject_key = payload.get("subject_key") or "umumiy"
            subject = subject_name(subject_key, lang)
            # Bot bilan bir xil: mavzu o'zgartirilmaydi (tarjima qilinmaydi).
            generation_topic = topic
            slides_content, real = await generate_slides_structured(
                generation_topic, subject, lang, slide_body_count(count))
            job["stage"] = "images"
            images = []
            if config.SLIDE_IMAGES:
                try:
                    from handlers.creation import _collect_images
                    images = await _collect_images(
                        generation_topic, slides_content,
                        total=slide_image_total(len(slides_content)), lang=lang)
                except Exception:
                    images = []
            job["stage"] = "building"
            buffer = generate_pptx(
                topic=generation_topic, subject=subject, lang=lang,
                design_key=payload.get("design_key") or "modern",
                slide_count=count, slides_content=slides_content,
                images=images, author=author,
            )
            if images:
                try:
                    import shutil
                    from pathlib import Path
                    shutil.rmtree(Path(images[0]).parent, ignore_errors=True)
                except Exception:
                    pass
            content, ext = buffer.read(), "pptx"
        else:
            from ai_api import generate as generate_content
            from docx_generator import generate_docx

            # Botdagi kabi: mavzu o'zgartirilmaydi, matn tanlangan tilda yoziladi.
            generation_topic = topic
            text, real = await generate_content(service, generation_topic, options, lang)
            job["stage"] = "building"
            # Hajm bot bilan bir xil funksiyada hisoblanadi: test — savollar
            # soni, esse — so'z hajmi, qolganlari sahifa.
            from services import document_pages
            pages = document_pages(service, options)
            buffer = generate_docx(
                generation_topic, service_name(service, lang), service, lang, pages, text,
                author=author, extra_data=data,
            )
            content, ext = buffer.read(), "docx"
            if fmt == "pdf":
                job["stage"] = "convert"
                try:
                    from handlers.creation import _to_pdf
                    pdf = _to_pdf(content, topic)
                    if pdf:
                        content, ext = pdf, "pdf"
                except Exception:
                    pass

        filename = f"{_safe_name(service_name(service, lang))}_{_safe_name(topic)}_{job_id[:6]}.{ext}"
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        path = os.path.join(OUTPUT_DIR, f"{job_id}.{ext}")
        with open(path, "wb") as handle:
            handle.write(content)
        note = ""
        if not real:
            try:
                from ai_api import get_last_error
                note = str(get_last_error() or "").strip()[:300]
            except Exception:
                note = ""
        job.update(status="done", stage="done", file=path, filename=filename,
                   size=len(content), real=bool(real), note=note)
        job["order_id"] = _save_order(job["user_id"], service, topic, options)
        if job["order_id"]:
            job["stored"] = _store_file(job["order_id"], content, ext, filename)
    except Exception as exc:
        job["status"] = "error"
        job["stage"] = "error"
        job["error"] = str(exc)[:300] or exc.__class__.__name__


def _store_file(order_id, content, ext, filename):
    """Faylni doimiy papkaga yozib, buyurtmaga bog'laydi."""
    try:
        os.makedirs(FILES_DIR, exist_ok=True)
        path = os.path.join(FILES_DIR, f"{int(order_id)}.{ext}")
        with open(path, "wb") as handle:
            handle.write(content)
        with _db() as con:
            con.execute("UPDATE orders SET file_path=?, file_name=? WHERE id=?",
                        (path, filename, int(order_id)))
            con.commit()
        return path
    except Exception:
        return None


def _order_file(uid, order_id):
    """(path, filename) — buyurtma fayli mavjud bo'lsa."""
    try:
        with _db() as con:
            row = con.execute(
                "SELECT file_path, file_name FROM orders WHERE id=? AND user_id=?",
                (int(order_id), int(uid)),
            ).fetchone()
    except Exception:
        return None, None
    if not row:
        return None, None
    path = row["file_path"] if "file_path" in row.keys() else None
    name = row["file_name"] if "file_name" in row.keys() else None
    if path and os.path.isfile(path):
        return path, name or os.path.basename(path)
    return None, None


def _save_order(user_id, service, topic, options):
    try:
        with _db() as con:
            cur = con.execute(
                "INSERT INTO orders(user_id,service,topic,options,price,status,created_at) "
                "VALUES(?,?,?,?,?,?,?)",
                (int(user_id), service, topic, json.dumps(options, ensure_ascii=False),
                 _price(service), "done", int(time.time())),
            )
            con.commit()
            return cur.lastrowid
    except Exception:
        return None


@mini.route("/api/mini/generate", methods=["POST"])
def api_generate():
    uid = _token_user()
    if not uid:
        return _unauthorized()
    data = request.get_json(silent=True) or {}
    service = str(data.get("service") or "").strip()
    if service not in SERVICES:
        return jsonify({"ok": False, "error": "service", "message": "Xizmat tanlanmadi."}), 400
    topic = re.sub(r"\s+", " ", str(data.get("topic") or "")).strip()
    if len(topic) < 3:
        return jsonify({"ok": False, "error": "topic", "message": "Mavzuni to‘liqroq yozing."}), 400
    if len(topic) > 200:
        topic = topic[:200]
    lang = str(data.get("lang") or "uz").lower()
    if lang not in ALL_LANGS:
        lang = "uz"
    fmt = str(data.get("format") or "docx").lower()
    if fmt not in ("docx", "pdf", "pptx"):
        fmt = "docx"
    if service == "slide":
        fmt = "pptx"
    options = _payload_options(service, data)
    extra = _extra_data(service, data, options)
    subject_key = ""
    # Fan yo'nalishi barcha xizmatlarda tanlanadi; belgilanmasa material
    # mavzuning o'zi bo'yicha yoziladi.
    requested = str(data.get("subject_key") or "").strip()
    try:
        from designs import SUBJECT_KEYS, subject_name as subject_display_name
        if requested in SUBJECT_KEYS:
            subject_key = requested
            if (service != "slide" and requested != "umumiy"
                    and not str(extra.get("ref_subject") or "").strip()):
                # Titul varaqda tanlangan fan ko'rsatiladi.
                extra["ref_subject"] = subject_display_name(requested, lang)
    except Exception:
        subject_key = ""
    if service != "slide":
        # Hujjat mazmuni ham tanlangan fanga mos yoziladi.
        options["subject"] = str(extra.get("ref_subject") or "").strip()
    payload = {
        "service": service,
        "topic": topic,
        "lang": lang,
        "options": options,
        "format": fmt,
        "author": str(data.get("author") or "").strip()[:120],
        "subject_key": subject_key,
        "design_key": str(data.get("design_key") or "").strip()[:40],
        "extra": extra,
    }
    job_id = _start_job(uid, payload)
    if not job_id:
        return jsonify({"ok": False, "error": "limit",
                        "message": "Bir vaqtda ko‘pi bilan 3 ta ish yaratish mumkin."}), 429
    return jsonify({"ok": True, "job": job_id})


@mini.route("/api/mini/job", methods=["GET"])
def api_job():
    uid = _token_user()
    if not uid:
        return _unauthorized()
    job = JOBS.get(str(request.args.get("id") or ""))
    if not job or job.get("user_id") != uid:
        return jsonify({"ok": False, "error": "job", "message": "Ish topilmadi."}), 404
    response = {
        "ok": True,
        "id": job["id"],
        "status": job["status"],
        "stage": job["stage"],
        "filename": job.get("filename"),
        "size": job.get("size"),
        "error": job.get("error"),
        "real": job.get("real"),
        "note": job.get("note"),
        "elapsed": int(time.time() - float(job.get("created") or time.time())),
    }
    return jsonify(response)


@mini.route("/api/mini/download", methods=["GET"])
def api_download():
    uid = _token_user()
    if not uid:
        return _unauthorized()

    # Doimiy saqlangan buyurtma fayli (muddat cheklovisiz).
    order_id = request.args.get("order")
    if order_id:
        try:
            order_id = int(order_id)
        except (TypeError, ValueError):
            order_id = 0
        path, name = _order_file(uid, order_id) if order_id else (None, None)
        if not path and order_id:
            # Doimiy nusxa yo'q bo'lsa, hali xotirada turgan ish faylini beramiz.
            for item in JOBS.values():
                if (item.get("user_id") == uid and item.get("order_id") == order_id
                        and item.get("file") and os.path.isfile(item["file"])):
                    path, name = item["file"], item.get("filename")
                    break
        if path:
            return send_file(path, as_attachment=True, download_name=name)
        return jsonify({"ok": False, "error": "file", "message": "Fayl topilmadi."}), 404

    job = JOBS.get(str(request.args.get("id") or ""))
    if not job or job.get("user_id") != uid or job.get("status") != "done":
        return jsonify({"ok": False, "error": "file", "message": "Fayl tayyor emas."}), 404
    path = job.get("file")
    if not path or not os.path.isfile(path):
        return jsonify({"ok": False, "error": "file", "message": "Fayl o‘chirilgan."}), 404
    return send_file(path, as_attachment=True, download_name=job.get("filename") or os.path.basename(path))


@mini.route("/api/mini/send", methods=["POST"])
def api_send():
    """Tayyor faylni foydalanuvchining Telegram chatiga bot orqali yuboradi."""
    uid = _token_user()
    if not uid:
        return _unauthorized()
    data = request.get_json(silent=True) or {}
    job = JOBS.get(str(data.get("job") or ""))
    filename = None
    if job and job.get("user_id") == uid and job.get("status") == "done":
        path = job.get("file")
        filename = job.get("filename")
    else:
        job = None
        path = None
    if not path or not os.path.isfile(path):
        # Doimiy saqlangan nusxa
        try:
            order_id = int(data.get("order") or 0)
        except (TypeError, ValueError):
            order_id = 0
        path, stored_name = _order_file(uid, order_id) if order_id else (None, None)
        filename = stored_name
    if not path or not os.path.isfile(path):
        return jsonify({"ok": False, "error": "file", "message": "Fayl topilmadi."}), 404
    if not config.BOT_TOKEN:
        return jsonify({"ok": False, "error": "bot", "message": "Bot tokeni sozlanmagan."}), 500

    async def _send():
        from aiogram import Bot
        from aiogram.client.default import DefaultBotProperties
        from aiogram.types import FSInputFile

        bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
        try:
            await bot.send_document(
                chat_id=int(uid),
                document=FSInputFile(path, filename=filename or os.path.basename(path)),
            )
        finally:
            await bot.session.close()

    try:
        asyncio.run(_send())
    except Exception as exc:
        return jsonify({"ok": False, "error": "send", "message": str(exc)[:200]}), 502
    return jsonify({"ok": True})
