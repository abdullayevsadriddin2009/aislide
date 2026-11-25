"""Esse tekshirish bo'limi — Milliy sertifikat mezoni bo'yicha tahlil.

Oqim: mavzu/topshiriq → ish (DOCX/TXT fayl, qo'lyozma rasmi yoki matn) → 12 band
bo'yicha 24 ballik hisobot va taqriz.

Bir necha varaq bitta albom bo'lib kelsa, ular alohida-alohida tekshirilmaydi:
albom tugashini kutib, barcha sahifalar matni birlashtirilib, bitta ish sifatida
tahlil qilinadi.
"""
import asyncio

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
                           Message)

import database as db
import essay_checker
from chat_format import split_text
from states import Check
from texts import t

router = Router()

_DOCX = (".docx",)
_TXT = (".txt", ".md", ".rtf")
_IMAGES = (".jpg", ".jpeg", ".png", ".webp")
_PDF = (".pdf",)
LANGS = ("uz", "ru", "en", "tr", "de", "fr")

# Telegram albomni bir necha alohida xabar qilib yuboradi. Har birini darhol
# tekshirish o'rniga qisqa vaqt kutamiz va sahifalarni birlashtiramiz.
_ALBUM_WAIT = 2.0
_ALBUM_MAX = 10
_ALBUMS = {}


async def _lang(user_id):
    u = await db.get_user(user_id)
    return u["lang"] if u and u["lang"] in LANGS else "uz"


def _retry_kb(lang):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("check_again", lang), callback_data="check:start")],
    ])


def _topic_kb(lang):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("check_topic_skip", lang), callback_data="check:no_topic")],
    ])


async def _redirect_menu(message, state):
    """Asosiy menyu tugmasi kelsa tekshiruvni to'xtatib, o'sha bo'limni ochadi.

    Tekshiruv holatida «🚀 Yaratishni boshlash» yuborilsa, u mavzu yoki esse
    matni sifatida qabul qilinmasligi kerak.
    """
    try:
        from handlers import user as user_handlers
        return await user_handlers.handle_menu_action(message, state)
    except Exception as exc:
        print(f"[check] menyu tugmasi xatosi: {type(exc).__name__}: {exc}", flush=True)
        return False


async def start_check(message: Message, state: FSMContext):
    """Asosiy menyudagi tugma uchun: tekshiruvni mavzu qadamidan boshlaydi."""
    lang = await _lang(message.from_user.id)
    await state.clear()
    await state.set_state(Check.topic)
    await state.update_data(check_topic="")
    await message.answer(t("check_prompt", lang), reply_markup=_topic_kb(lang))


@router.callback_query(F.data == "check:start")
async def cb_check_start(call: CallbackQuery, state: FSMContext):
    """«Yaratishni boshlash» ichidagi tekshirish bo'limi — 1-qadam: mavzu."""
    lang = await _lang(call.from_user.id)
    await state.clear()
    await state.set_state(Check.topic)
    await state.update_data(check_topic="")
    try:
        await call.message.edit_text(t("check_prompt", lang), reply_markup=_topic_kb(lang))
    except Exception:
        await call.message.answer(t("check_prompt", lang), reply_markup=_topic_kb(lang))
    await call.answer()


@router.callback_query(F.data == "check:no_topic")
async def cb_check_no_topic(call: CallbackQuery, state: FSMContext):
    """Mavzusiz tekshirish: 2-qadamga o'tadi."""
    lang = await _lang(call.from_user.id)
    await state.set_state(Check.essay)
    await state.update_data(check_topic="")
    try:
        await call.message.edit_text(t("check_essay_prompt", lang))
    except Exception:
        await call.message.answer(t("check_essay_prompt", lang))
    await call.answer()


async def _download(message: Message):
    """Telegram faylini xotiraga yuklaydi."""
    buffer = await message.bot.download(message.document or message.photo[-1])
    try:
        return buffer.read()
    finally:
        try:
            buffer.close()
        except Exception:
            pass


def _is_image(message: Message):
    if message.photo:
        return True
    name = (message.document.file_name or "").lower() if message.document else ""
    return bool(name.endswith(_IMAGES))


async def _read_work(message: Message, lang):
    """Xabardan matn ajratadi. (matn, xatolik_kaliti) qaytaradi."""
    if message.document:
        name = (message.document.file_name or "").lower()
        if name.endswith(_PDF):
            return "", "check_pdf"
        if not name.endswith(_DOCX + _TXT + _IMAGES):
            return "", "check_unsupported"
        data = await _download(message)
        if name.endswith(_DOCX):
            return await asyncio.to_thread(essay_checker.extract_docx_text, data), ""
        if name.endswith(_IMAGES):
            return await essay_checker.ocr_image(data, lang), "check_image_unreadable"
        return essay_checker.decode_text(data), ""
    if message.photo:
        data = await _download(message)
        return await essay_checker.ocr_image(data, lang), "check_image_unreadable"
    if (message.text or "").strip():
        return message.text.strip(), ""
    return "", "check_prompt"


# ===== Ko'p varaqli qo'lyozma (albom) =====
def _album_bucket(message, state, lang):
    key = message.chat.id
    bucket = _ALBUMS.get(key)
    if bucket is None:
        bucket = {"images": [], "task": None, "token": 0}
        _ALBUMS[key] = bucket
    bucket["state"] = state
    bucket["lang"] = lang
    bucket["message"] = message
    return bucket


async def _collect_album(message, state, lang):
    """Albomning bitta sahifasini yig'adi; oxirgi sahifadan keyin hammasini tekshiradi."""
    bucket = _album_bucket(message, state, lang)
    data = await _download(message)
    if len(bucket["images"]) < _ALBUM_MAX:
        bucket["images"].append(data)
    bucket["token"] += 1
    token = bucket["token"]
    if bucket["task"] and not bucket["task"].done():
        bucket["task"].cancel()
    bucket["task"] = asyncio.create_task(_flush_album(message.chat.id, token))


async def _flush_album(chat_id, token):
    try:
        await asyncio.sleep(_ALBUM_WAIT)
    except asyncio.CancelledError:
        return
    bucket = _ALBUMS.get(chat_id)
    if not bucket or bucket.get("token") != token:
        return
    _ALBUMS.pop(chat_id, None)
    message, state, lang = bucket["message"], bucket["state"], bucket["lang"]
    images = list(bucket["images"])
    if not images:
        return
    waiting = await message.answer(t("check_waiting", lang))
    semaphore = asyncio.Semaphore(2)

    async def read_page(data):
        async with semaphore:
            try:
                return await essay_checker.ocr_image(data, lang)
            except Exception as exc:
                print(f"[check] sahifa o'qilmadi: {type(exc).__name__}: {exc}", flush=True)
                return ""

    pages = await asyncio.gather(*(read_page(data) for data in images))
    text = "\n\n".join(page.strip() for page in pages if page and page.strip())
    print(f"[check] albom: {len(images)} sahifa, {essay_checker.word_count(text)} so'z", flush=True)
    if not text.strip():
        try:
            await waiting.edit_text(t("check_image_unreadable", lang))
        except Exception:
            await message.answer(t("check_image_unreadable", lang))
        return
    await _analyze_and_send(message, state, lang, text, from_image=True, waiting=waiting)


@router.message(Check.topic)
async def topic_received(message: Message, state: FSMContext):
    """Mavzuni qabul qiladi; fayl/rasm kelsa — mavzusiz tekshirishga o'tadi."""
    lang = await _lang(message.from_user.id)
    if await _redirect_menu(message, state):
        return
    if message.document or message.photo:
        await state.update_data(check_topic="")
        await state.set_state(Check.essay)
        if message.media_group_id and _is_image(message):
            await _collect_album(message, state, lang)
            return
        await _run_check(message, state, lang)
        return
    topic = (message.text or "").strip()
    # Mavzu o'rniga ishning o'zi yuborilgan bo'lsa (uzun matn), uni yo'qotmaymiz.
    if len(topic) >= 400:
        await state.update_data(check_topic="")
        await state.set_state(Check.essay)
        await _run_check(message, state, lang)
        return
    if len(topic) < 3:
        await message.answer(t("check_prompt", lang), reply_markup=_topic_kb(lang))
        return
    await state.update_data(check_topic=topic[:300])
    await state.set_state(Check.essay)
    await message.answer(t("check_essay_prompt", lang))


@router.message(Check.essay)
async def check_received(message: Message, state: FSMContext):
    if await _redirect_menu(message, state):
        return
    lang = await _lang(message.from_user.id)
    # 5-6 varaq bitta albomda kelsa, faqat birinchi sahifa tekshirilib qolmasin.
    if message.media_group_id and _is_image(message):
        await _collect_album(message, state, lang)
        return
    await _run_check(message, state, lang)


async def _run_check(message: Message, state: FSMContext, lang):
    from_image = _is_image(message)
    try:
        text, error_key = await _read_work(message, lang)
    except Exception as exc:
        print(f"[check] faylni o'qish xatosi: {type(exc).__name__}: {exc}", flush=True)
        await message.answer(t("check_error", lang), reply_markup=_retry_kb(lang))
        return
    if error_key and not text.strip():
        await message.answer(t(error_key, lang))
        return
    if not text.strip():
        await message.answer(t("check_image_unreadable"), reply_markup=_retry_kb(lang))
        return
    if len(text.strip()) < 60:
        await message.answer(t("check_empty", lang))
        return
    await _analyze_and_send(message, state, lang, text, from_image=from_image)


async def _analyze_and_send(message: Message, state: FSMContext, lang, text,
                            from_image=False, waiting=None):
    data = await state.get_data()
    topic = str(data.get("check_topic") or "")
    if waiting is None:
        waiting = await message.answer(t("check_waiting", lang))
    print(f"[check] matn: {essay_checker.word_count(text)} so'z (rasm={from_image})", flush=True)
    try:
        report = await essay_checker.analyze_essay(text, lang, topic, from_image=from_image)
    except Exception as exc:
        # Kutilmagan xato ham foydalanuvchini javobsiz qoldirmasligi kerak.
        import traceback
        print(f"[check] tahlil kutilmagan xatosi: {type(exc).__name__}: {exc}", flush=True)
        traceback.print_exc()
        report = None
    if not report:
        import ai_api
        reason = getattr(ai_api, "LAST_ERROR", "") or ""
        print(f"[check] hisobot olinmadi: {reason}", flush=True)
        try:
            await waiting.edit_text(t("check_ai", lang), reply_markup=_retry_kb(lang))
        except Exception:
            await message.answer(t("check_ai", lang), reply_markup=_retry_kb(lang))
        return

    body = essay_checker.format_report(report, lang)
    parts = split_text(body, 3500) or [body]
    kb = _retry_kb(lang)
    for index, part in enumerate(parts):
        markup = kb if index == len(parts) - 1 else None
        if index == 0:
            try:
                await waiting.edit_text(part, parse_mode=None, reply_markup=markup)
                continue
            except Exception:
                pass
        await message.answer(part, parse_mode=None, reply_markup=markup)
    await state.clear()
