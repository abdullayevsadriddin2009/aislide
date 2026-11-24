"""Esse tekshirish bo'limi — fayl, rasm yoki matnni mezon bo'yicha tahlil qiladi."""
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


async def _lang(user_id):
    u = await db.get_user(user_id)
    return u["lang"] if u and u["lang"] in LANGS else "uz"


def _retry_kb(lang):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("check_again", lang), callback_data="check:start")],
    ])


@router.callback_query(F.data == "check:start")
async def cb_check_start(call: CallbackQuery, state: FSMContext):
    """«Yaratishni boshlash» ichidagi tekshirish bo'limi."""
    lang = await _lang(call.from_user.id)
    await state.clear()
    await state.set_state(Check.essay)
    try:
        await call.message.edit_text(t("check_prompt", lang))
    except Exception:
        await call.message.answer(t("check_prompt", lang))
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


@router.message(Check.essay)
async def check_received(message: Message, state: FSMContext):
    lang = await _lang(message.from_user.id)
    text = ""
    try:
        if message.document:
            name = (message.document.file_name or "").lower()
            if name.endswith(_PDF):
                await message.answer(t("check_pdf", lang))
                return
            if not name.endswith(_DOCX + _TXT + _IMAGES):
                await message.answer(t("check_unsupported", lang))
                return
            data = await _download(message)
            if name.endswith(_DOCX):
                text = await asyncio.to_thread(essay_checker.extract_docx_text, data)
            elif name.endswith(_IMAGES):
                text = await essay_checker.ocr_image(data, lang)
            else:
                text = essay_checker.decode_text(data)
        elif message.photo:
            data = await _download(message)
            text = await essay_checker.ocr_image(data, lang)
        elif (message.text or "").strip():
            text = message.text.strip()
        else:
            await message.answer(t("check_prompt", lang))
            return
    except Exception as exc:
        print(f"[check] faylni o'qish xatosi: {type(exc).__name__}: {exc}", flush=True)
        await message.answer(t("check_error", lang))
        return

    if not text.strip():
        await message.answer(t("check_image_unreadable", lang))
        return
    if len(text.strip()) < 60:
        await message.answer(t("check_empty", lang))
        return

    thinking = await message.answer(t("check_waiting", lang))
    report = await essay_checker.analyze_essay(text, lang)
    if not report:
        try:
            await thinking.edit_text(t("check_error", lang))
        except Exception:
            await message.answer(t("check_error", lang))
        return

    body = essay_checker.format_report(report, lang)
    parts = split_text(body, 3500) or [body]
    kb = _retry_kb(lang)
    for index, part in enumerate(parts):
        markup = kb if index == len(parts) - 1 else None
        if index == 0:
            try:
                await thinking.edit_text(part, parse_mode=None, reply_markup=markup)
                continue
            except Exception:
                pass
        await message.answer(part, parse_mode=None, reply_markup=markup)
    await state.clear()
