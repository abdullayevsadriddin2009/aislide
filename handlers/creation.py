import math  # NAMEERROR XATOSI TUZATILDI
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
import database as db
from texts import t
from states import Creation
from services import SERVICES, service_name, ALL_LANGS
from keyboards import (option_kb_for, confirm_kb, main_kb, option_label,
                       subjects_kb, languages_kb, format_kb, template_kb, slide_count_kb)
from designs import (subject_name, detect_subject_key, lang_full_name, SLIDE_COUNTS, design_name)
from ai_api import generate, generate_slides_structured, get_last_error, search_images, download_image, generate_outline, localize_topic
from pptx_generator import generate_pptx
from docx_generator import generate_docx

router = Router()


def _slide_count_prompt(lang):
    prompts = {
        "uz": "📊 Nechta slaydli taqdimot kerak? Dizaynni keyingi bosqichda tanlaysiz.",
        "ru": "📊 Сколько слайдов должно быть в презентации? Дизайн выберете на следующем шаге.",
        "en": "📊 How many slides should the presentation contain? You will choose the design next.",
        "tr": "📊 Sunum kaç slayt içersin? Tasarımı bir sonraki adımda seçeceksiniz.",
        "de": "📊 Wie viele Folien soll die Präsentation enthalten? Das Design wählen Sie im nächsten Schritt.",
        "fr": "📊 Combien de diapositives doit contenir la présentation ? Vous choisirez le design à l’étape suivante.",
    }
    return prompts.get(lang, prompts["en"])


def _slide_design_prompt(lang):
    prompts = {
        "uz": "🎨 Taqdimot dizaynini tanlang. Uchala variant ham siz tanlagan slayd sonida ishlaydi.",
        "ru": "🎨 Выберите дизайн презентации. Все три варианта поддерживают выбранное количество слайдов.",
        "en": "🎨 Choose a presentation design. All three options support your selected slide count.",
        "tr": "🎨 Sunum tasarımını seçin. Üç tasarım da seçtiğiniz slayt sayısını destekler.",
        "de": "🎨 Wählen Sie ein Präsentationsdesign. Alle drei Varianten unterstützen die gewählte Folienzahl.",
        "fr": "🎨 Choisissez le design de la présentation. Les trois options prennent en charge le nombre de diapositives choisi.",
    }
    return prompts.get(lang, prompts["en"])

async def _collect_images(topic, slides_content, total=5, lang="uz"):
    """Collect topic-specific images concurrently and always supply visual artwork."""
    import tempfile, os, textwrap, asyncio
    from PIL import Image, ImageDraw, ImageFont
    tmpdir = tempfile.mkdtemp(prefix="pptx_imgs_")
    queries = []
    for candidate in [str(topic or "").strip()] + [
        str(item.get("title") or "").strip()
        for item in (slides_content or []) if isinstance(item, dict)
    ]:
        candidate = candidate.strip()
        if len(candidate) >= 3 and candidate.casefold() not in {q.casefold() for q in queries}:
            queries.append(candidate)
        if len(queries) >= 3:
            break

    async def search_one(q):
        try:
            return await search_images(q, count=max(5, total * 2))
        except Exception as exc:
            print(f"[creation] search_images failed for {q!r}: {exc}", flush=True)
            return []

    groups = await asyncio.gather(*(search_one(q) for q in queries)) if queries else []
    urls, seen = [], set()
    for group in groups:
        for url in group or []:
            if url and url not in seen:
                seen.add(url)
                urls.append(url)
    urls = urls[:max(8, total * 2)]

    async def download_one(index, url):
        path = os.path.join(tmpdir, f"img_{index}.jpg")
        try:
            ok = await download_image(url, path)
            if not ok or not os.path.isfile(path) or os.path.getsize(path) < 1000:
                return None
            # HTTP 200 responses can still contain HTML/error pages instead of an
            # image; verify the bytes before passing the file to python-pptx.
            with Image.open(path) as image:
                if image.width < 120 or image.height < 80:
                    return None
                image.verify()
            return path
        except Exception as exc:
            print(f"[creation] image download failed/invalid: {exc}", flush=True)
            return None

    downloads = await asyncio.gather(*(download_one(i, url) for i, url in enumerate(urls))) if urls else []
    paths = [p for p in downloads if p][:total]

    if not paths:
        # The supplied PPTX has no embedded photos. This generated visual is a
        # guaranteed fallback when Commons or optional image APIs cannot be reached.
        try:
            width, height = 1600, 900
            canvas = Image.new("RGB", (width, height), (20, 32, 50))
            draw = ImageDraw.Draw(canvas)
            draw.ellipse((1030, -180, 1770, 560), outline=(201, 162, 39), width=12)
            draw.ellipse((1100, -110, 1690, 480), outline=(104, 125, 151), width=5)
            draw.rounded_rectangle((80, 90, 1520, 810), radius=38, outline=(201, 162, 39), width=4)
            try:
                font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
                title_font = ImageFont.truetype(font_path, 62)
                label_font = ImageFont.truetype(font_path, 28)
            except Exception:
                title_font = label_font = ImageFont.load_default()
            title = str(topic or "Educational presentation").strip()
            lines = textwrap.wrap(title, width=30)[:4]
            y = 285 if len(lines) <= 2 else 220
            for line in lines:
                draw.text((145, y), line, font=title_font, fill=(255, 255, 255), stroke_width=1, stroke_fill=(20, 32, 50))
                y += 83
            labels = {
                "uz": "MAVZUGA OID VIZUAL", "ru": "ВИЗУАЛИЗАЦИЯ ТЕМЫ", "en": "TOPIC VISUAL",
                "tr": "KONU GÖRSELİ", "de": "THEMENVISUALISIERUNG", "fr": "VISUEL DU SUJET",
            }
            draw.text((145, 690), labels.get(str(lang).lower(), labels["en"]), font=label_font, fill=(201, 162, 39))
            path = os.path.join(tmpdir, "topic_visual.jpg")
            canvas.save(path, "JPEG", quality=90)
            paths.append(path)
        except Exception as exc:
            print(f"[creation] fallback image generation failed: {exc}", flush=True)
    return paths

async def _lang(uid):
    u = await db.get_user(uid)
    return u["lang"] if u and u["lang"] in ALL_LANGS else "uz"

def _to_pdf(docx_bytes, topic):
    """Convert DOCX to PDF on Linux/Windows when a supported converter exists."""
    import os
    import shutil
    import subprocess
    import tempfile

    safe = "".join(c for c in str(topic or "")[:40] if c.isalnum() or c in " _-").strip() or "document"
    with tempfile.TemporaryDirectory(prefix="aislide_pdf_") as tmpdir:
        docx_path = os.path.join(tmpdir, f"{safe}.docx")
        pdf_path = os.path.join(tmpdir, f"{safe}.pdf")
        with open(docx_path, "wb") as f:
            f.write(docx_bytes)

        # Render deployment installs LibreOffice; prefer it over docx2pdf (which
        # requires Microsoft Word and is not supported on Linux).
        office = shutil.which("libreoffice") or shutil.which("soffice")
        if office:
            try:
                proc = subprocess.run(
                    [office, "--headless", "--convert-to", "pdf", "--outdir", tmpdir, docx_path],
                    capture_output=True, text=True, timeout=90, check=False,
                )
                if proc.returncode == 0 and os.path.isfile(pdf_path):
                    with open(pdf_path, "rb") as f:
                        return f.read()
                print(f"[creation] LibreOffice PDF conversion failed: {proc.stderr[-400:]}", flush=True)
            except Exception as exc:
                print(f"[creation] LibreOffice PDF conversion error: {exc}", flush=True)

        # Windows local fallback if Microsoft Word is installed.
        try:
            from docx2pdf import convert
            convert(docx_path, pdf_path)
            if os.path.isfile(pdf_path):
                with open(pdf_path, "rb") as f:
                    return f.read()
        except Exception as exc:
            print(f"[creation] docx2pdf conversion unavailable: {exc}", flush=True)
        return None

def _eid(event):
    if isinstance(event, CallbackQuery):
        return event.from_user.id, event.message
    return event.from_user.id, event

# ===== 1. Xizmat tanlash =====
@router.callback_query(Creation.service, F.data.startswith("svc:"))
async def cb_service(call: CallbackQuery, state: FSMContext):
    user_id, msg = _eid(call)
    lang = await _lang(user_id)
    service = call.data.split(":")[1]
    await state.update_data(service=service, options={})
    await state.set_state(Creation.topic)
    if service == "slide":
        await msg.edit_text(t("enter_slide_topic", lang))
    else:
        sname = service_name(service, lang)
        await msg.edit_text(t("enter_topic_generic", lang, service=sname))
    await call.answer()

# ===== 2. Mavzu =====
@router.message(Creation.topic)
async def topic_received(message: Message, state: FSMContext):
    user_id = message.from_user.id
    lang = await _lang(user_id)
    topic = message.text.strip()
    data = await state.get_data()
    service = data.get("service")
    await state.update_data(topic=topic)
    
    if service == "slide":
        detected_key = detect_subject_key(topic)
        await state.update_data(subject=detected_key)
        await state.set_state(Creation.subject)
        subj_name = subject_name(detected_key, lang)
        await message.answer(
            t("subject_question", lang, subject=subj_name),
            reply_markup=subjects_kb(detected_key, lang))
        return
        
    s = SERVICES.get(service, {})
    ot = s.get("option_type", "pages")
    if ot in ("pages", "questions", "words"):
        await state.set_state(Creation.option)
        await message.answer(t("choose_option", lang), reply_markup=option_kb_for(service, lang))
    else:
        await _ask_author(message, state)

# ===== 3. Fan (faqat slayd) =====
@router.callback_query(Creation.subject, F.data.startswith("subj:"))
async def cb_subject(call: CallbackQuery, state: FSMContext):
    user_id, msg = _eid(call)
    lang = await _lang(user_id)
    subject_key = call.data.split(":", 1)[1]
    await state.update_data(subject=subject_key)
    await state.set_state(Creation.language)
    await msg.edit_text(t("choose_language", lang), reply_markup=languages_kb(lang))
    await call.answer()

# ===== 4. Til (slayd + non-slayd) =====
@router.callback_query(Creation.language, F.data.startswith("lng:"))
async def cb_language(call: CallbackQuery, state: FSMContext):
    user_id, msg = _eid(call)
    lang = await _lang(user_id)
    lang_code = call.data.split(":")[1]
    lang_name = lang_full_name(lang_code, lang)
    await state.update_data(language=lang_code, language_name=lang_name)
    data = await state.get_data()
    service = data.get("service")
    
    # Barcha hujjat xizmatlari uchun titul/metadata ma'lumotlarini oldindan yig'amiz.
    # Referat uchun alohida matnlar saqlanadi; qolgan xizmatlar umumiy lokalizatsiyani ishlatadi.
    if service != "slide":
        await state.set_state(Creation.ref_subject)
        ask_key = "ref_ask_subject" if service == "referat" else "academic_ask_subject"
        await msg.edit_text(t(ask_key, lang))
        await call.answer()
        return

    # Slayd soni va dizayni mustaqil tanlanadi.
    await state.set_state(Creation.slide_count)
    await msg.edit_text(_slide_count_prompt(lang), reply_markup=slide_count_kb(lang))
    await call.answer()

# ===== 5. Fayl formati (non-slayd) =====
@router.callback_query(Creation.format, F.data.startswith("fmt:"))
async def cb_format(call: CallbackQuery, state: FSMContext):
    fmt = call.data.split(":")[1]
    await state.update_data(file_format=fmt)
    data = await state.get_data()
    
    # Barcha hujjat xizmatlari uchun muallif va qo'shimcha ma'lumotlar oldindan so'ralgan.
    await _show_confirm(call, state)
    await call.answer()

# ===== 6. Slaydlar soni =====
@router.callback_query(Creation.slide_count, F.data.startswith("scnt:"))
async def cb_slide_count(call: CallbackQuery, state: FSMContext):
    user_id, msg = _eid(call)
    lang = await _lang(user_id)
    try:
        count = int(call.data.split(":", 1)[1])
    except (TypeError, ValueError):
        await call.answer()
        return
    if count not in (10, 15, 20):
        await call.answer()
        return
    base_price = await db.get_price("slide")
    count_price = dict(SLIDE_COUNTS).get(count, 0)
    selected_price = base_price if base_price > 0 else count_price
    await state.update_data(slide_count=count, slide_price=selected_price)
    await state.set_state(Creation.slide_design)
    await msg.edit_text(_slide_design_prompt(lang), reply_markup=template_kb(lang))
    await call.answer()

# ===== 7. Taqdimot dizayni =====
@router.callback_query(Creation.slide_design, F.data.startswith("tmpl:"))
async def cb_template(call: CallbackQuery, state: FSMContext):
    design_key = call.data.split(":", 1)[1]
    if design_key not in ("modern", "nature", "elegant"):
        await call.answer()
        return
    user_id, _ = _eid(call)
    lang = await _lang(user_id)
    await state.update_data(design_key=design_key, template_name=design_name(design_key, lang))
    await _ask_author(call, state)
    await call.answer()

# ===== 7. Parametr (non-slayd: pages/questions) =====
@router.callback_query(Creation.option, F.data.startswith("opt:"))
async def cb_option(call: CallbackQuery, state: FSMContext):
    _, otype, oval = call.data.split(":", 2)
    allowed_values = {"pages": {10, 15, 20}, "questions": {10, 15, 20}, "words": {200, 300, 500}}
    try:
        selected_value = int(oval)
    except (TypeError, ValueError):
        await call.answer("Invalid option", show_alert=True)
        return
    if otype not in allowed_values or selected_value not in allowed_values[otype]:
        await call.answer("Invalid option", show_alert=True)
        return
    data = await state.get_data()
    options = data.get("options", {})
    options[otype] = selected_value
    await state.update_data(options=options)
    service = data.get("service")
    if service != "slide":
        lang = await _lang(call.from_user.id)
        await state.set_state(Creation.language)
        await call.message.edit_text(t("choose_language", lang), reply_markup=languages_kb(lang))
        await call.answer(); return
    await _ask_author(call, state)
    await call.answer()

# ===== 8. Muallif so'rash (Umumiy hujjatlar uchun) =====
async def _ask_author(event, state):
    user_id, msg = _eid(event)
    lang = await _lang(user_id)
    await state.set_state(Creation.author)
    text = t("enter_author", lang)
    if isinstance(event, CallbackQuery):
        await msg.edit_text(text)
    else:
        await msg.answer(text)

@router.message(Creation.author)
async def author_received(message: Message, state: FSMContext):
    author = (message.text or "").strip()
    skip_words = ["-", "—", "yo'q", "yoq", "none", "skip", "o'tkazib yubor", "нет", "пропустить"]
    if author.lower() in skip_words:
        author = ""
    await state.update_data(author=author)
    await _show_confirm(message, state)

# ===== 8.1 TITUL VARAQ MA'LUMOTLARI: REFERAT / KURS / DIPLOM =====
def _academic_key(service, ref_key, generic_key):
    return ref_key if service == "referat" else generic_key


FULL_TITLE_SERVICES = {"referat", "mustaqil", "kurs", "diplom"}

@router.message(Creation.ref_subject)
async def ref_subject(message: Message, state: FSMContext):
    lang = await _lang(message.from_user.id)
    data = await state.get_data()
    service = data.get("service")
    value = (message.text or "").strip()
    if not value:
        ask_key = "ref_ask_subject" if service == "referat" else "academic_ask_subject"
        await message.answer(t(ask_key, lang)); return
    await state.update_data(ref_subject=value)
    if service in FULL_TITLE_SERVICES:
        await state.set_state(Creation.ref_institution)
        await message.answer(t(_academic_key(service, "ref_ask_institution", "academic_ask_institution"), lang))
    else:
        # Essay, test, article and thesis use a compact header: subject + author is sufficient.
        await state.set_state(Creation.ref_author)
        await message.answer(t(_academic_key(service, "ref_ask_author", "academic_ask_author"), lang))

@router.message(Creation.ref_institution)
async def ref_institution(message: Message, state: FSMContext):
    lang = await _lang(message.from_user.id)
    data = await state.get_data()
    service = data.get("service")
    value = (message.text or "").strip()
    if not value:
        await message.answer(t(_academic_key(service, "ref_ask_institution", "academic_ask_institution"), lang)); return
    await state.update_data(ref_institution=value)
    await state.set_state(Creation.ref_faculty)
    await message.answer(t(_academic_key(service, "ref_ask_faculty", "academic_ask_faculty"), lang))

@router.message(Creation.ref_faculty)
async def ref_faculty(message: Message, state: FSMContext):
    lang = await _lang(message.from_user.id)
    data = await state.get_data()
    service = data.get("service")
    value = (message.text or "").strip()
    if not value:
        await message.answer(t(_academic_key(service, "ref_ask_faculty", "academic_ask_faculty"), lang)); return
    await state.update_data(ref_faculty=value)
    await state.set_state(Creation.ref_dept)
    await message.answer(t(_academic_key(service, "ref_ask_dept", "academic_ask_dept"), lang))

@router.message(Creation.ref_dept)
async def ref_dept(message: Message, state: FSMContext):
    lang = await _lang(message.from_user.id)
    data = await state.get_data()
    service = data.get("service")
    value = (message.text or "").strip()
    if not value:
        await message.answer(t(_academic_key(service, "ref_ask_dept", "academic_ask_dept"), lang)); return
    await state.update_data(ref_dept=value)
    await state.set_state(Creation.ref_author)
    await message.answer(t(_academic_key(service, "ref_ask_author", "academic_ask_author"), lang))

@router.message(Creation.ref_author)
async def ref_author(message: Message, state: FSMContext):
    lang = await _lang(message.from_user.id)
    data = await state.get_data()
    service = data.get("service")
    author = (message.text or "").strip()
    if not author:
        await message.answer(t(_academic_key(service, "ref_ask_author", "academic_ask_author"), lang)); return
    await state.update_data(ref_author=author, author=author)
    if service in FULL_TITLE_SERVICES:
        await state.set_state(Creation.ref_checker)
        await message.answer(t(_academic_key(service, "ref_ask_checker", "academic_ask_checker"), lang))
    else:
        await state.set_state(Creation.format)
        await message.answer(t("file_format_question", lang), reply_markup=format_kb(lang))

@router.message(Creation.ref_checker)
async def ref_checker(message: Message, state: FSMContext):
    lang = await _lang(message.from_user.id)
    data = await state.get_data()
    service = data.get("service")
    value = (message.text or "").strip()
    if not value:
        await message.answer(t(_academic_key(service, "ref_ask_checker", "academic_ask_checker"), lang)); return
    await state.update_data(ref_checker=value)
    await state.set_state(Creation.format)
    await message.answer(t("file_format_question", lang), reply_markup=format_kb(lang))

# ===== 9. Tasdiqlash =====
async def _show_confirm(event, state):
    user_id, msg = _eid(event)
    is_cb = isinstance(event, CallbackQuery)
    lang = await _lang(user_id)
    data = await state.get_data()
    service = data.get("service")
    topic = data.get("topic", "")
    options = data.get("options", {})
    
    # Referat bo'lsa ref_author, bo'lmasa oddiy author
    author = data.get("ref_author") or data.get("author", "") or "—"
    
    s = SERVICES.get(service, {})
    price = await db.get_price(service)
    
    if service == "slide":
        subject_key = data.get("subject", "tarix")
        language_code = data.get("language", lang)
        language_name = data.get("language_name", lang_full_name(language_code, lang))
        slide_count = data.get("slide_count", 10)
        template_name = data.get("template_name", "Modern blue")
        subj_name = subject_name(subject_key, language_code)
        param = f"{subj_name} • {language_name} • {template_name} • {t('slides_label', lang, n=slide_count)}"
        price = data.get("slide_price", await db.get_price(service))
    else:
        u = await db.get_user(user_id)
        if u and "pages" not in options and s.get("option_type") == "pages":
            try:
                default_pages = int(u.get("default_pages", 10))
            except (TypeError, ValueError):
                default_pages = 10
            options["pages"] = default_pages if default_pages in (10, 15, 20) else 10
        await state.update_data(options=options)
        lang_name = data.get("language_name", lang_full_name("uz", lang))
        fmt = data.get("file_format", "docx")
        fmt_label = t("word_format", lang) if fmt == "docx" else t("pdf_format", lang)
        param = f"{option_label(service, options, lang)} • {lang_name} • {fmt_label}"
        if service in FULL_TITLE_SERVICES:
            # Titul varaq uchun yig‘ilgan ma’lumotlar ham tasdiqlashdan oldin ko‘rsatiladi.
            academic_fields = [
                data.get("ref_subject", ""), data.get("ref_institution", ""),
                data.get("ref_faculty", ""), data.get("ref_dept", ""),
                data.get("ref_author", ""), data.get("ref_checker", ""),
            ]
            shown_fields = [str(v).strip() for v in academic_fields if str(v or "").strip()]
            if shown_fields:
                param += " • " + " / ".join(shown_fields)
        
    free_mode = (await db.get_setting("free_mode", "1")) == "1" or price == 0
    await state.set_state(Creation.confirm)
    text = t("confirm_order", lang, service=service_name(service, lang), topic=topic,
             author=author, param=param, price=price,
             free_note=t("free_label", lang) if free_mode else f"💳 {price} so'm")
             
    if is_cb:
        await msg.edit_text(text, reply_markup=confirm_kb(lang))
    else:
        await msg.answer(text, reply_markup=confirm_kb(lang))

# ===== 10. Yaratish =====
@router.callback_query(Creation.confirm, F.data == "confirm:yes")
async def cb_confirm(call: CallbackQuery, state: FSMContext):
    user_id, msg = _eid(call)
    lang = await _lang(user_id)
    data = await state.get_data()
    service = data.get("service")
    topic = data.get("topic", "")
    options = data.get("options", {})
    author = data.get("ref_author") or data.get("author", "")
    price = data.get("slide_price", await db.get_price(service)) if service == "slide" else await db.get_price(service)
    free_mode = (await db.get_setting("free_mode", "1")) == "1" or price == 0
    
    u = await db.get_user(user_id)
    if not free_mode and u:
        total = u["balance"] + u["bonus_balance"]
        if total < price:
            await msg.answer(t("insufficient_balance", lang), reply_markup=main_kb(lang))
            await state.clear(); await call.answer(); return
        pay_bonus = min(u["bonus_balance"], price)
        if pay_bonus: await db.add_bonus_balance(user_id, -pay_bonus)
        if price - pay_bonus: await db.add_balance(user_id, -(price - pay_bonus))
        
    await msg.edit_text(t("generating", lang))
    await call.answer()
    language_code = data.get("language", lang)
    generation_topic = await localize_topic(topic, language_code)
    await state.update_data(generation_topic=generation_topic)
    data["generation_topic"] = generation_topic
    
    # ===== INSHO UCHUN MAXSUS =====
    if service == "insho":
        language_code = data.get("language", lang)
        words = int(options.get("words", 200) or 200)
        words = words if words in (200, 300, 500) else min((200, 300, 500), key=lambda n: abs(n - words))
        options["words"] = words
        await state.update_data(options=options)
        outline = await generate_outline(service, generation_topic, language_code, words)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t("btn_write_essay", lang), callback_data="essay:go")],
            [InlineKeyboardButton(text=t("btn_cancel", lang), callback_data="cancel")],
        ])
        if outline:
            await state.update_data(essay_outline=outline)
            await msg.edit_text(t("essay_outline", lang, outline=outline[:3000]), reply_markup=kb)
        else:
            fallback_outline = {
                "uz": f"1. Kirish: {generation_topic} mavzusining mazmuni va ahamiyati\n2. Asosiy fikr: asosiy tarixiy yoki nazariy xususiyatlar\n3. Asosiy fikr: mavzuning jamiyatga ta’siri\n4. Shaxsiy munosabat: dalillarni baholash\n5. Xulosa: fikrlarni umumlashtirish",
                "ru": f"1. Введение: значение темы «{generation_topic}»\n2. Основная мысль: ключевые особенности\n3. Основная мысль: влияние темы на общество\n4. Личная позиция: оценка аргументов\n5. Заключение: обобщение выводов",
                "en": f"1. Introduction: meaning and importance of {generation_topic}\n2. Main point: key features\n3. Main point: impact on society\n4. Personal view: evaluate the arguments\n5. Conclusion: summarize the findings",
                "tr": f"1. Giriş: {generation_topic} konusunun önemi\n2. Ana fikir: temel özellikler\n3. Ana fikir: toplum üzerindeki etkisi\n4. Kişisel görüş: savları değerlendirme\n5. Sonuç: bulguları özetleme",
                "de": f"1. Einleitung: Bedeutung von {generation_topic}\n2. Hauptgedanke: zentrale Merkmale\n3. Hauptgedanke: gesellschaftliche Wirkung\n4. Eigene Position: Argumente bewerten\n5. Schluss: Ergebnisse zusammenfassen",
                "fr": f"1. Introduction : importance de {generation_topic}\n2. Idée principale : caractéristiques essentielles\n3. Idée principale : effets sur la société\n4. Point de vue personnel : évaluer les arguments\n5. Conclusion : résumer les résultats",
            }.get(language_code, f"1. Introduction: {generation_topic}\n2. Main point\n3. Main point\n4. Personal view\n5. Conclusion")
            await state.update_data(essay_outline=fallback_outline)
            await msg.edit_text(t("essay_outline", lang, outline=fallback_outline), reply_markup=kb)
        await state.set_state(Creation.essay_outline)
        return
        
    safe_topic = "".join(c for c in topic[:25] if c.isalnum() or c in " _-").strip() or "document"
    
    if service == "slide":
        subject_key = data.get("subject", "tarix")
        language_code = data.get("language", "uz")
        slide_count = data.get("slide_count", 10)
        subj_display = subject_name(subject_key, language_code)
        
        slides_content, real = await generate_slides_structured(generation_topic, subj_display, language_code, max(2, slide_count - 3))
        
        try:
            img_paths = await _collect_images(generation_topic, slides_content, total=5, lang=language_code)
        except Exception as e:
            print(f"[creation] Image download error: {e}", flush=True)
            img_paths = []
            
        buf = generate_pptx(
            topic=generation_topic,
            subject=subj_display,
            lang=language_code,
            design_key=data.get("design_key", "modern"),
            slide_count=slide_count,
            slides_content=slides_content,
            images=img_paths,
            author=author
        )
        # python-pptx embeds image bytes in the presentation; the temporary files
        # can now be safely removed.
        if img_paths:
            try:
                import shutil
                shutil.rmtree(__import__("pathlib").Path(img_paths[0]).parent, ignore_errors=True)
            except Exception:
                pass

        prefix = t("fname_slide", language_code)
        fname = f"{prefix}_{safe_topic}.pptx".replace(" ", "_")
        doc = BufferedInputFile(buf.read(), filename=fname)
        
        if real:
            caption = t("gen_done", lang)
        else:
            err = get_last_error() or "n/a"
            caption = t("gen_failed", lang) + f"\n\n🔍 {err}"
            
        await msg.answer_document(doc, caption=caption, reply_markup=main_kb(lang))
        
    else:
        language_code = data.get("language", lang)
        text_content, real = await generate(service, generation_topic, options, language_code)
        
        if service == "insho" and options.get("words"):
            words = int(options["words"])
            pages = max(2, math.ceil(words / 220))
            options["pages"] = pages
            options["target_words"] = words
        elif service == "test":
            pages = int(options.get("questions", 20) or 20)
        else:
            pages = int(options.get("pages", 10) or 10)
            
        # Foydalanuvchi kiritgan titul ma'lumotlarini saqlaymiz; faqat fan nomi
        # tanlangan hujjat tiliga tarjima qilinadi. Ism va muassasa nomlari o'z holicha qoladi.
        document_data = dict(data)
        for field in ("ref_subject", "ref_faculty", "ref_dept"):
            if document_data.get(field):
                document_data[field] = await localize_topic(document_data[field], language_code)
        buf = generate_docx(
            topic=generation_topic,
            service_name=service_name(service, language_code),
            service_code=service,
            lang=language_code,
            pages=pages,
            content_text=text_content,
            author=author,
            extra_data=document_data
        )
        docx_bytes = buf.read()
        fmt = data.get("file_format", "docx")
        prefix = t(f"fname_{service}", language_code)
        
        if fmt == "pdf":
            pdf_bytes = _to_pdf(docx_bytes, topic)
            if pdf_bytes:
                fname = f"{prefix}_{safe_topic}.pdf".replace(" ", "_")
                doc = BufferedInputFile(pdf_bytes, filename=fname)
            else:
                fname = f"{prefix}_{safe_topic}.docx".replace(" ", "_")
                doc = BufferedInputFile(docx_bytes, filename=fname)
        else:
            fname = f"{prefix}_{safe_topic}.docx".replace(" ", "_")
            doc = BufferedInputFile(docx_bytes, filename=fname)
            
        caption = t("gen_done", lang) if real else t("gen_failed", lang)
        await msg.answer_document(doc, caption=caption, reply_markup=main_kb(lang))
        
    await db.add_order(user_id, service, topic, options, 0 if free_mode else price, topic[:100])
    await state.clear()

# ===== 11. Essay: reja tasdiqlandi, to'liq matn yoziladi =====
@router.callback_query(Creation.essay_outline, F.data == "essay:go")
async def cb_essay_go(call: CallbackQuery, state: FSMContext):
    user_id, msg = _eid(call)
    lang = await _lang(user_id)
    data = await state.get_data()
    service = data.get("service")
    topic = data.get("topic", "")
    generation_topic = data.get("generation_topic", topic)
    options = data.get("options", {})
    author = data.get("author", "")
    price = await db.get_price(service)
    free_mode = (await db.get_setting("free_mode", "1")) == "1" or price == 0
    await msg.edit_text(t("generating", lang))
    await call.answer()
    safe_topic = "".join(c for c in topic[:25] if c.isalnum() or c in " _-").strip() or "document"
    language_code = data.get("language", lang)
    text_content, real = await generate(service, generation_topic, options, language_code)
    words = int(options.get("words", 200) or 200)
    words = words if words in (200, 300, 500) else min((200, 300, 500), key=lambda n: abs(n - words))
    pages = max(2, math.ceil(words / 220))
    options["pages"] = pages
    options["target_words"] = words
    document_data = dict(data)
    document_data["essay_target_words"] = words
    document_data["essay_outline"] = data.get("essay_outline", "")
    for field in ("ref_subject", "ref_faculty", "ref_dept"):
        if document_data.get(field):
            document_data[field] = await localize_topic(document_data[field], language_code)
    buf = generate_docx(generation_topic, service_name(service, language_code), service, language_code, pages, text_content, author=author, extra_data=document_data)
    docx_bytes = buf.read()
    fmt = data.get("file_format", "docx")
    prefix = t(f"fname_{service}", language_code)
    if fmt == "pdf":
        pdf_bytes = _to_pdf(docx_bytes, topic)
        if pdf_bytes:
            fname = f"{prefix}_{safe_topic}.pdf".replace(" ", "_")
            doc = BufferedInputFile(pdf_bytes, filename=fname)
        else:
            fname = f"{prefix}_{safe_topic}.docx".replace(" ", "_")
            doc = BufferedInputFile(docx_bytes, filename=fname)
    else:
        fname = f"{prefix}_{safe_topic}.docx".replace(" ", "_")
        doc = BufferedInputFile(docx_bytes, filename=fname)
    caption = t("gen_done", lang) if real else t("gen_failed", lang)
    await msg.answer_document(doc, caption=caption, reply_markup=main_kb(lang))
    await db.add_order(user_id, service, topic, options, 0 if free_mode else price, topic[:100])
    await state.clear()
