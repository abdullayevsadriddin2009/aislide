import math  # NAMEERROR XATOSI TUZATILDI
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
import config
import database as db
from texts import t
from states import Creation
from services import SERVICES, service_name, ALL_LANGS
from keyboards import (option_kb_for, confirm_kb, main_kb, option_label,
                       languages_kb, format_kb, template_kb, slide_count_kb)
from designs import (subject_name, detect_subject_key, lang_full_name, SLIDE_COUNTS,
                     design_name, DESIGNS, DESIGN_KEYS)
from ai_api import (generate, generate_slides_structured, get_last_error, search_images, download_image,
                    generate_insho_plan, image_grade, related_keywords)
from pptx_generator import generate_pptx
from docx_generator import generate_docx

router = Router()


def _persist_file(order_id, content, filename):
    """Hujjatni DATA_DIR/files ga saqlaydi — Mini App'da istalgan vaqtda yuklab olinadi."""
    try:
        import os
        folder = os.path.join(config.DATA_DIR, "files")
        os.makedirs(folder, exist_ok=True)
        ext = os.path.splitext(str(filename))[1] or ".docx"
        path = os.path.join(folder, f"{int(order_id)}{ext}")
        with open(path, "wb") as handle:
            handle.write(content)
        return path
    except Exception as exc:
        print(f"[creation] faylni saqlab bo'lmadi: {exc}", flush=True)
        return None



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
    total = len(DESIGN_KEYS)
    prompts = {
        "uz": f"🎨 Taqdimot shablonini tanlang ({total} ta variant). Har bir shablon siz tanlagan slayd sonida ishlaydi.",
        "ru": f"🎨 Выберите шаблон презентации (вариантов: {total}). Каждый шаблон работает с выбранным количеством слайдов.",
        "en": f"🎨 Choose a presentation template ({total} options). Every template supports your selected slide count.",
        "tr": f"🎨 Sunum şablonunu seçin ({total} seçenek). Her şablon seçtiğiniz slayt sayısını destekler.",
        "de": f"🎨 Wählen Sie eine Präsentationsvorlage ({total} Varianten). Jede Vorlage unterstützt die gewählte Folienzahl.",
        "fr": f"🎨 Choisissez un modèle de présentation ({total} options). Chaque modèle prend en charge le nombre de diapositives choisi.",
    }
    return prompts.get(lang, prompts["en"])

async def _collect_images(topic, slides_content, total=5, lang="uz"):
    """Download one distinct topic-matched photo per slide, cover included.

    Each slide title is searched on its own and the topic is searched as a wider
    pool, so a deck of six slides gets six different photos instead of the same two
    repeated. The returned list starts with the cover photo, then one photo per
    body slide in slide order; ``generate_pptx`` maps it by position.
    """
    import tempfile, os, textwrap, asyncio, re
    from PIL import Image, ImageDraw, ImageFont
    from urllib.parse import unquote

    tmpdir = tempfile.mkdtemp(prefix="pptx_imgs_")
    topic_text = str(topic or "").strip()
    titles = [str(item.get("title") or "").strip()
              for item in (slides_content or []) if isinstance(item, dict)]
    titles = [title for title in titles if len(title) >= 3]
    # Section headings carry no subject of their own: "Xulosa" or "Tahlil" is where
    # a search engine returns logic diagrams and stock charts, which is how
    # unrelated pictures used to reach a slide.
    headings = {
        "xulosa", "kirish", "mundarija", "reja", "tahlil", "natijalar", "adabiyotlar",
        "mavzu", "asosiy qism", "savol", "savollar", "test", "amaliyot", "zhulosa",
        "conclusion", "introduction", "contents", "summary", "analysis", "results",
        "введение", "заключение", "содержание", "анализ", "выводы", "итоги",
        "giriş", "sonuç", "içindekiler", "einleitung", "fazit", "inhalt",
        "sommaire", "conclusion", "résumé",
    }
    titles = [title for title in titles
              if title.casefold().strip(" .,:;!?") not in headings]
    slide_slots = max(1, len(titles))

    queries = [query for query in ([topic_text] + titles) if len(query) >= 3][:12]
    if not queries:
        queries = [topic_text or str(lang)]

    # Every photo is searched with exactly the words the user gave us: the topic and
    # the slide titles as they are written, never a translation or an AI paraphrase.
    keywords = list(queries)

    # Same-language words for the subject itself: the phrase's own words plus the
    # article titles this Wikipedia suggests for them. They are the second wave,
    # used only where the topic as written has no pictures.
    topic_terms = [topic_text or str(lang)]
    try:
        for extra in await related_keywords(topic_text, lang):
            if extra and extra.casefold() not in {term.casefold() for term in topic_terms}:
                topic_terms.append(extra)
    except Exception as exc:
        print(f"[creation] keyword expansion failed: {exc}", flush=True)

    async def search(query, keyword, count, use_wiki=False):
        try:
            return await search_images(query, count=count, keywords=keyword,
                                       use_wiki=use_wiki, lang=lang) or []
        except Exception as exc:
            print(f"[creation] search_images failed for {query!r}: {exc}", flush=True)
            return []

    def grade_rank(url):
        grade = image_grade(url)
        return 0 if grade == "A" else (1 if grade == "B" else 2)

    # The subject first: the article's own lead image and a pool of its pictures,
    # then one group of pictures per slide title.
    cover_urls, *pool_groups = await asyncio.gather(
        search(topic_text, keywords[0], 5, use_wiki=True),
        *(search(term, term, 10) for term in topic_terms[:4]),
    )
    topic_pool = sorted(dict.fromkeys(url for group in pool_groups for url in (group or [])),
                        key=grade_rank)
    groups = await asyncio.gather(
        *(search(queries[index], keywords[index], 6) for index in range(1, len(queries))))

    used, slot_urls = set(), []

    def take(candidates, grades=("A", "B")):
        for url in candidates or []:
            if url and url not in used and image_grade(url) in grades:
                used.add(url)
                return url
        return None

    # A photo confirmed to show the subject gets the cover; one that carries the
    # topic in its file name is the second choice, themed artwork the last.
    cover_url = (take(cover_urls, ("A",)) or take(topic_pool, ("A",))
                 or take(cover_urls) or take(topic_pool))
    for group in groups:
        # The deck's own subject first: a picture found through a heading such as
        # "Tahlil va natijalar" is what put unrelated photos into slides. A
        # heading's picture is used when it is verified for that subject ("A"),
        # otherwise the topic pool supplies the photo.
        slot_urls.append(take(topic_pool) or take(group, ("A",)) or take(group))

    # Slides that found nothing borrow a different photo from the topic pool or
    # from the leftovers of the other slides, so photos repeat only when the topic
    # really has fewer pictures than the deck has slides.
    leftovers = []
    for group in list(groups) + [topic_pool, cover_urls]:
        leftovers.extend(url for url in (group or []) if url)
    # Confirmed photos come first, topic-named ones after them: requiring a
    # Wikidata "depicts" statement for every slide left whole decks without any
    # photo, which is worse than a looser but still on-topic picture.
    leftovers = sorted(dict.fromkeys(leftovers),
                       key=lambda url: 0 if image_grade(url) == "A" else 1)
    if cover_url and image_grade(cover_url) not in ("A", "B"):
        cover_url = take(leftovers)
    for index, url in enumerate(slot_urls):
        if url and image_grade(url) not in ("A", "B"):
            slot_urls[index] = None
    for index in range(len(slot_urls)):
        if not slot_urls[index]:
            slot_urls[index] = take(leftovers)

    distinct = len({url for url in ([cover_url] + slot_urls) if url})
    if distinct < min(5, 1 + slide_slots):
        # The topic as written does not have enough pictures: search its
        # same-language keywords and synonyms before any slide goes without a
        # photo. The words are the user's own or the ones Wikipedia itself offers,
        # never a translation.
        topic_words = [word for word in re.findall(r"[^\W\d_]{4,}", topic_text.casefold())]

        def on_subject(url):
            """A related-title photo must still name the deck's own subject.

            A suggestion such as "Vatan urushi ordeni" is a real subject in the
            same language, but its medal is not a picture of "vatan"; the word in
            the file name is the cheap proof that the photo belongs to the deck.
            """
            name = unquote(str(url)).casefold()
            return not topic_words or any(word in name for word in topic_words)

        for term in topic_terms[1:6]:
            leftovers.extend(url for url in await search(term, term, 10)
                             if image_grade(url) in ("A", "B") and on_subject(url))
        if not leftovers:
            for term in topic_terms[:4]:
                leftovers.extend(url for url in await search(term, term, 12)
                                 if on_subject(url))
        leftovers = sorted(dict.fromkeys(leftovers), key=grade_rank)
        for index in range(len(slot_urls)):
            if not slot_urls[index]:
                slot_urls[index] = take(leftovers)
        if not cover_url:
            cover_url = take(leftovers)

    ordered_urls = []
    for url in [cover_url] + slot_urls:
        if url:
            ordered_urls.append(url)

    gate = asyncio.Semaphore(4)

    async def download_one(index, url):
        path = os.path.join(tmpdir, f"img_{index}.jpg")
        try:
            async with gate:
                ok = await download_image(url, path)
            if not ok or not os.path.isfile(path) or os.path.getsize(path) < 1000:
                return None
            # HTTP 200 responses can still contain HTML/error pages instead of an
            # image; verify the bytes before passing the file to python-pptx.
            with Image.open(path) as image:
                if image.width < 640 or image.height < 360:
                    return None
                image.verify()
            return path
        except Exception as exc:
            print(f"[creation] image download failed/invalid: {exc}", flush=True)
            return None

    downloads = await asyncio.gather(*(download_one(i, u) for i, u in enumerate(ordered_urls)))
    downloaded = {index: path for index, path in enumerate(downloads) if path}

    # A photo that failed to download (rate limit, broken file) is replaced by the
    # next unused photo of the topic instead of turning that slide into artwork.
    spare = []
    for url in leftovers:
        if url and url not in ordered_urls and url not in spare:
            spare.append(url)
    for index in range(len(ordered_urls)):
        if index in downloaded:
            continue
        while spare:
            path = await download_one(index, spare.pop(0))
            if path:
                downloaded[index] = path
                break
    fallback_path = None

    def fallback_visual():
        """Themed abstract artwork: better than an unrelated photo."""
        nonlocal fallback_path
        if fallback_path:
            return fallback_path
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
            title = topic_text or "Educational presentation"
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
            fallback_path = path
        except Exception as exc:
            print(f"[creation] fallback image generation failed: {exc}", flush=True)
        return fallback_path

    # Cover first, then one entry per body slide so each layout gets its own photo.
    paths = []
    for index in range(1 + slide_slots):
        path = downloaded.get(index) or fallback_visual()
        if path:
            paths.append(path)
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
        # The subject is detected from the topic itself; asking the user for it was
        # an unnecessary extra step and often got the wrong answer.
        detected_key = detect_subject_key(topic)
        await state.update_data(subject=detected_key)
        await state.set_state(Creation.language)
        await message.answer(t("choose_language", lang), reply_markup=languages_kb(lang))
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
    if design_key not in DESIGNS:
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
    try:
        selected_value = int(oval)
    except (TypeError, ValueError):
        await call.answer("Invalid option", show_alert=True)
        return
    data = await state.get_data()
    service = data.get("service")
    allowed_values = {"pages": {10, 15, 20}, "questions": {10, 15, 20}, "words": {200, 300, 500}}
    s = SERVICES.get(service, {})
    allowed = set(s.get("options") or allowed_values.get(s.get("option_type", "pages"), set()))
    if selected_value not in allowed:
        await call.answer("Invalid option", show_alert=True)
        return
    options = data.get("options", {})
    options[otype] = selected_value
    await state.update_data(options=options)
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
        template_name = data.get("template_name", design_name(data.get("design_key", DESIGN_KEYS[0]), lang))
        subj_name = subject_name(subject_key, language_code)
        param = f"{subj_name} • {language_name} • {template_name} • {t('slides_label', lang, n=slide_count)}"
        price = data.get("slide_price", await db.get_price(service))
    else:
        u = await db.get_user(user_id)
        if u and "pages" not in options and s.get("option_type") == "pages":
            allowed_pages = tuple(s.get("options") or (10, 15, 20))
            try:
                default_pages = int(u.get("default_pages", allowed_pages[0]))
            except (TypeError, ValueError):
                default_pages = allowed_pages[0]
            options["pages"] = default_pages if default_pages in allowed_pages else allowed_pages[0]
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
    # Foydalanuvchi yozgan mavzu o'zgartirilmaydi: tarjima qilinmaydi, matn,
    # titul va rasm qidiruvi aynan shu mavzu bo'yicha bajariladi.
    generation_topic = topic
    await state.update_data(generation_topic=generation_topic)
    data["generation_topic"] = generation_topic
    
    # ===== INSHO UCHUN MAXSUS: REJA =====
    # Inshoda reja majburiy va u hujjat boshida (mavzudan keyin) yoziladi.
    if service == "insho":
        language_code = data.get("language", lang)
        try:
            pages = int(options.get("pages", 3) or 3)
        except (TypeError, ValueError):
            pages = 3
        pages = pages if pages in (3, 4, 5) else min((3, 4, 5), key=lambda n: abs(n - pages))
        options["pages"] = pages
        await state.update_data(options=options)
        plan = await generate_insho_plan(generation_topic, language_code, pages)
        await state.update_data(essay_outline=plan)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t("btn_write_essay", lang), callback_data="essay:go")],
            [InlineKeyboardButton(text=t("btn_cancel", lang), callback_data="cancel")],
        ])
        await msg.edit_text(t("essay_outline", lang, outline=plan[:3000]), reply_markup=kb)
        await state.set_state(Creation.essay_outline)
        return
        
    safe_topic = "".join(c for c in topic[:25] if c.isalnum() or c in " _-").strip() or "document"
    
    if service == "slide":
        subject_key = data.get("subject", "tarix")
        language_code = data.get("language", "uz")
        slide_count = data.get("slide_count", 10)
        subj_display = subject_name(subject_key, language_code)
        
        slides_content, real = await generate_slides_structured(generation_topic, subj_display, language_code, max(2, slide_count - 3))
        
        img_paths = []
        if config.SLIDE_IMAGES:
            try:
                # One photo per body slide keeps every layout on-topic; the download
                # budget is still capped so generation stays fast.
                image_total = min(12, max(5, len(slides_content)))
                img_paths = await _collect_images(generation_topic, slides_content, total=image_total, lang=language_code)
            except Exception as e:
                print(f"[creation] Image download error: {e}", flush=True)
                img_paths = []
            
        buf = generate_pptx(
            topic=generation_topic,
            subject=subj_display,
            lang=language_code,
            design_key=data.get("design_key", DESIGN_KEYS[0]),
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
        
        if service == "esse":
            try:
                words = int(options.get("words", 250) or 250)
            except (TypeError, ValueError):
                words = 250
            words = words if words in (150, 250, 350) else min((150, 250, 350), key=lambda n: abs(n - words))
            options["words"] = words
            options["target_words"] = words
            pages = max(2, math.ceil(words / 300))
        elif service == "insho":
            pages = int(options.get("pages", 3) or 3)
        elif service == "test":
            pages = int(options.get("questions", 20) or 20)
        else:
            pages = int(options.get("pages", 10) or 10)
            
        # Foydalanuvchi kiritgan titul ma'lumotlarini saqlaymiz; faqat fan nomi
        # tanlangan hujjat tiliga tarjima qilinadi. Ism va muassasa nomlari o'z holicha qoladi.
        document_data = dict(data)
        # Titul maydonlari ham foydalanuvchi yozganidek qoladi (tarjima qilinmaydi).
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
            
        if real:
            caption = t("gen_done", lang)
        else:
            caption = t("gen_failed", lang)
            detail = get_last_error()
            if detail:
                caption += f"\n\n🔍 {str(detail)[:350]}"
        await msg.answer_document(doc, caption=caption, reply_markup=main_kb(lang))
        
    order_id = await db.add_order(user_id, service, topic, options, 0 if free_mode else price, topic[:100])
    if order_id:
        saved = _persist_file(order_id, doc.data, doc.filename)
        if saved:
            await db.set_order_file(order_id, saved, doc.filename)
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
    author = data.get("ref_author") or data.get("author", "")
    price = await db.get_price(service)
    free_mode = (await db.get_setting("free_mode", "1")) == "1" or price == 0
    await msg.edit_text(t("generating", lang))
    await call.answer()
    safe_topic = "".join(c for c in topic[:25] if c.isalnum() or c in " _-").strip() or "document"
    language_code = data.get("language", lang)
    plan = data.get("essay_outline", "")
    options["plan"] = plan
    text_content, real = await generate(service, generation_topic, options, language_code)
    pages = int(options.get("pages", 3) or 3)
    document_data = dict(data)
    document_data["insho_plan"] = plan
    # Titul maydonlari foydalanuvchi yozganidek qoladi.
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
    if real:
        caption = t("gen_done", lang)
    else:
        caption = t("gen_failed", lang)
        detail = get_last_error()
        if detail:
            caption += f"\n\n🔍 {str(detail)[:350]}"
    await msg.answer_document(doc, caption=caption, reply_markup=main_kb(lang))
    order_id = await db.add_order(user_id, service, topic, options, 0 if free_mode else price, topic[:100])
    if order_id:
        saved = _persist_file(order_id, doc.data, doc.filename)
        if saved:
            await db.set_order_file(order_id, saved, doc.filename)
    await state.clear()
