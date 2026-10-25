import math  # NAMEERROR XATOSI TUZATILDI
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
import database as db
from texts import t
from states import Creation
from services import SERVICES, service_name, ALL_LANGS
from keyboards import (option_kb_for, confirm_kb, main_kb, option_label,
                       subjects_kb, languages_kb, format_kb, template_kb)
from designs import (subject_name, detect_subject_key, lang_full_name)
from ai_api import generate, generate_slides_structured, get_last_error, search_images, download_image, generate_outline
from pptx_generator import generate_pptx
from docx_generator import generate_docx

router = Router()

async def _collect_images(topic, slides_content, total=5):
    import tempfile, os
    tmpdir = tempfile.mkdtemp(prefix="pptx_imgs_")
    queries = [topic]
    paths = []
    seen = set()
    for q in queries:
        if len(paths) >= total: break
        try:
            urls = await search_images(q, count=8)
        except Exception:
            urls = []
        for u in urls:
            if u in seen or len(paths) >= total: continue
            seen.add(u)
            p = os.path.join(tmpdir, f"img_{len(paths)}.jpg")
            try:
                if await download_image(u, p):
                    paths.append(p)
            except Exception:
                pass
    return paths

async def _lang(uid):
    u = await db.get_user(uid)
    return u["lang"] if u and u["lang"] in ALL_LANGS else "uz"

def _to_pdf(docx_bytes, topic):
    try:
        import tempfile, os
        from docx2pdf import convert
        tmpdir = tempfile.mkdtemp()
        safe = "".join(c for c in topic[:20] if c.isalnum() or c in " _-").strip() or "document"
        docx_path = os.path.join(tmpdir, f"{safe}.docx")
        pdf_path = os.path.join(tmpdir, f"{safe}.pdf")
        with open(docx_path, "wb") as f:
            f.write(docx_bytes)
        convert(docx_path, pdf_path)
        with open(pdf_path, "rb") as f:
            return f.read()
    except Exception as e:
        print(f"[creation] PDF convert error (continue with docx): {e}", flush=True)
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
    if ot in ("pages", "questions"):
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
    
    # REFERAT UCHUN MAXSUS SAVOLLAR BOSHLANADI
    if service == "referat":
        await state.set_state(Creation.ref_subject)
        await msg.edit_text(t("ref_ask_subject", lang))
        await call.answer()
        return

    if service != "slide":
        await state.set_state(Creation.format)
        await msg.edit_text(t("file_format_question", lang), reply_markup=format_kb(lang))
        await call.answer(); return
        
    # Slayd bo'lsa - yangi shablonlarni tanlashga o'tamiz
    await state.set_state(Creation.slide_count)
    await msg.edit_text("🎨 Taqdimot shablonini tanlang:\n\n<i>Har bir shablon o'zining ranglar palitrasi va tuzilishiga ega.</i>", reply_markup=template_kb(lang))
    await call.answer()

# ===== 5. Fayl formati (non-slayd) =====
@router.callback_query(Creation.format, F.data.startswith("fmt:"))
async def cb_format(call: CallbackQuery, state: FSMContext):
    fmt = call.data.split(":")[1]
    await state.update_data(file_format=fmt)
    data = await state.get_data()
    
    # Referat bo'lsa, muallifni qayta so'ramaymiz, to'g'ridan-to'g'ri tasdiqlashga o'tamiz
    if data.get("service") == "referat":
        await _show_confirm(call, state)
    else:
        await _ask_author(call, state)
    await call.answer()

# ===== 6. Yangi Shablon tanlash (slayd) =====
@router.callback_query(Creation.slide_count, F.data.startswith("tmpl:"))
async def cb_template(call: CallbackQuery, state: FSMContext):
    count = int(call.data.split(":")[1])
    t_names = {10: "Gold", 15: "Green", 20: "Wine", 25: "Teal"}
    template_name = t_names.get(count, "Gold")
    
    await state.update_data(slide_count=count, template_name=template_name)
    await _ask_author(call, state)
    await call.answer()

# ===== 7. Parametr (non-slayd: pages/questions) =====
@router.callback_query(Creation.option, F.data.startswith("opt:"))
async def cb_option(call: CallbackQuery, state: FSMContext):
    _, otype, oval = call.data.split(":", 2)
    data = await state.get_data()
    options = data.get("options", {})
    options[otype] = oval
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

# ===== 8.1 REFERAT UCHUN MAXSUS SAVOL-JAVOBLAR =====
@router.message(Creation.ref_subject)
async def ref_subject(message: Message, state: FSMContext):
    lang = await _lang(message.from_user.id)
    await state.update_data(ref_subject=message.text.strip())
    await state.set_state(Creation.ref_institution)
    await message.answer(t("ref_ask_institution", lang))

@router.message(Creation.ref_institution)
async def ref_institution(message: Message, state: FSMContext):
    lang = await _lang(message.from_user.id)
    await state.update_data(ref_institution=message.text.strip())
    await state.set_state(Creation.ref_faculty)
    await message.answer(t("ref_ask_faculty", lang))

@router.message(Creation.ref_faculty)
async def ref_faculty(message: Message, state: FSMContext):
    lang = await _lang(message.from_user.id)
    await state.update_data(ref_faculty=message.text.strip())
    await state.set_state(Creation.ref_dept)
    await message.answer(t("ref_ask_dept", lang))

@router.message(Creation.ref_dept)
async def ref_dept(message: Message, state: FSMContext):
    lang = await _lang(message.from_user.id)
    await state.update_data(ref_dept=message.text.strip())
    await state.set_state(Creation.ref_author)
    await message.answer(t("ref_ask_author", lang))

@router.message(Creation.ref_author)
async def ref_author(message: Message, state: FSMContext):
    lang = await _lang(message.from_user.id)
    await state.update_data(ref_author=message.text.strip())
    await state.set_state(Creation.ref_checker)
    await message.answer(t("ref_ask_checker", lang))

@router.message(Creation.ref_checker)
async def ref_checker(message: Message, state: FSMContext):
    lang = await _lang(message.from_user.id)
    await state.update_data(ref_checker=message.text.strip())
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
        language_name = data.get("language_name", lang_full_name("uz", lang))
        slide_count = data.get("slide_count", 10)
        template_name = data.get("template_name", "Gold")
        subj_name = subject_name(subject_key, lang)
        param = f"{subj_name} • {language_name} • {template_name} shablon • {t('slides_label', lang, n=slide_count)}"
        price = data.get("price", 0)
    else:
        u = await db.get_user(user_id)
        if u and "pages" not in options and s.get("option_type") == "pages":
            options["pages"] = u["default_pages"]
        await state.update_data(options=options)
        lang_name = data.get("language_name", lang_full_name("uz", lang))
        fmt = data.get("file_format", "docx")
        fmt_label = t("word_format", lang) if fmt == "docx" else t("pdf_format", lang)
        param = f"{option_label(service, options, lang)} • {lang_name} • {fmt_label}"
        
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
    price = data.get("price") if service == "slide" else await db.get_price(service)
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
    
    # ===== INSHO UCHUN MAXSUS =====
    if service == "insho":
        language_code = data.get("language", lang)
        words = int(options.get("words", 250))
        outline = await generate_outline(service, topic, language_code, words)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t("btn_write_essay", lang), callback_data="essay:go")],
            [InlineKeyboardButton(text=t("btn_cancel", lang), callback_data="cancel")],
        ])
        if outline:
            await msg.edit_text(t("essay_outline", lang, outline=outline[:3000]), reply_markup=kb)
        else:
            await msg.edit_text(t("essay_outline", lang, outline="(Reja avtomatik tuziladi)"), reply_markup=kb)
        await state.set_state(Creation.essay_outline)
        return
        
    safe_topic = "".join(c for c in topic[:25] if c.isalnum() or c in " _-").strip() or "document"
    
    if service == "slide":
        subject_key = data.get("subject", "tarix")
        language_code = data.get("language", "uz")
        slide_count = data.get("slide_count", 10)
        template_type = str(slide_count)
        subj_display = subject_name(subject_key, language_code)
        
        slides_content, real = await generate_slides_structured(topic, subj_display, language_code, slide_count)
        
        try:
            img_paths = await _collect_images(topic, slides_content, total=5)
        except Exception as e:
            print(f"[creation] Image download error: {e}", flush=True)
            img_paths = []
            
        buf = generate_pptx(
            topic=topic, 
            subject=subj_display, 
            lang=language_code, 
            design_key=template_type,
            slide_count=slide_count, 
            slides_content=slides_content, 
            images=img_paths, 
            author=author
        )
        
        prefix = t("fname_slide", lang)
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
        text_content, real = await generate(service, topic, options, language_code)
        
        if service == "insho" and options.get("words"):
            words = int(options["words"])
            pages = max(2, math.ceil(words / 220))
            options["pages"] = pages
            options["target_words"] = words
        else:
            pages = int(options.get("pages", 10) or 10)
            
        # extra_data=data qo'shildi, bu docx_generator ichidagi titul varaq uchun kerak
        buf = generate_docx(
            topic=topic, 
            service_name=service_name(service, lang), 
            service_code=service, 
            lang=language_code, 
            pages=pages, 
            content_text=text_content, 
            author=author,
            extra_data=data
        )
        docx_bytes = buf.read()
        fmt = data.get("file_format", "docx")
        prefix = t(f"fname_{service}", lang)
        
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
    options = data.get("options", {})
    author = data.get("author", "")
    price = await db.get_price(service)
    free_mode = (await db.get_setting("free_mode", "1")) == "1" or price == 0
    await msg.edit_text(t("generating", lang))
    await call.answer()
    safe_topic = "".join(c for c in topic[:25] if c.isalnum() or c in " _-").strip() or "document"
    language_code = data.get("language", lang)
    text_content, real = await generate(service, topic, options, language_code)
    words = int(options.get("words", 250))
    pages = max(2, math.ceil(words / 220))
    options["pages"] = pages
    options["target_words"] = words
    buf = generate_docx(topic, service_name(service, lang), service, language_code, pages, text_content, author=author, extra_data=data)
    docx_bytes = buf.read()
    fmt = data.get("file_format", "docx")
    prefix = t(f"fname_{service}", lang)
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
