"""Yozma ishni (esse) Milliy sertifikat mezoni bo'yicha tekshirish.

Asos: Bilim va malakalarni baholash agentligining «Ona tili va adabiyot fanidan
yozma ishni baholashga qo'yiladigan talablar» hujjati (uzbmb.uz). Esseda 12 ta
band bor, har biri 0 dan 2 ballgacha — jami 24 ball. Hujjatdagi qat'iy qoidalar
ham hisobga olinadi:

* mavzuga mos bo'lmagan ish — 2 ball;
* 100 so'zdan kam ish — 2 ball;
* boshqa manbadan ko'chirilgan ish — 2 ball;
* faqat kirish qismi yozilgani — 0 ball.

Ish lotin yoki kirill alifbosida yozilgan bo'lishi mumkin: alifbo tanlovi
kamchilik emas, imlo va tinish shu alifbo qoidalari bo'yicha baholanadi.

Foydalanuvchi DOCX/TXT fayl, rasm yoki matn yuboradi; rasm Gemini vision orqali
o'qiladi. Hisobotda har bir band bo'yicha ball, aniq xatolar va taqriz qaytadi.
"""
import asyncio
import base64
import hashlib
import io
import json
import re
import threading
import time

import aiohttp

import ai_pool

MAX_CHARS = 15000          # bir marta tekshiriladigan matn hajmi
MAX_ERRORS = 30            # imlo to'liq ko'rib chiqilsin: har bir xato alohida
MAX_IMAGE_SIDE = 2600      # qo'lyozma ingichka: kichik rasmda harflar yo'qoladi
MIN_IMAGE_SIDE = 1700      # bundan kichik suratni kattalashtiramiz (ingichka harflar)
MAX_PER_BAND = 2
MAX_TOTAL = 24
MIN_WORDS = 100
MIN_OCR_WORDS = 25         # bundan kam o'qilgan rasm — to'liq o'qilmagan bo'lishi mumkin
# Bir vaqtda 6-7 foydalanuvchi albom yuborsa, o'nlab so'rov birdaniga ketib
# bepul limitlarni «portlatadi». Navbat bilan yuborilsa, ko'proq so'rov muvaffaqiyatli
# o'tadi va hech kim xato ko'rmaydi.
OCR_CONCURRENCY = 3
ANALYZE_CONCURRENCY = 4
OCR_ENOUGH_WORDS = 100     # shu hajmdan keyin boshqa modelni sinash shart emas
VISION_MAX_TOKENS = 8192
SCALE_MAX = 75             # rasmiy: 24 ballik natija 75 ballik shkalaga o'tkaziladi

# Rasmiy mezon: 12 band, har biri 0..2. Kalit — hisobot va JSON uchun.
CRITERIA = (
    ("uslub", "Publitsistik (ilmiy-ommabop) uslubda yozilganlik"),
    ("qarashlar", "Vaziyat yuzasidan ikkala qarash va shaxsiy qarash yoritilgani"),
    ("dalillar", "Qarashlarning dalillar bilan asoslangani"),
    ("qismlar", "Matn uch qismdan iboratligi: kirish, asosiy qism, xulosa"),
    ("mantiq", "Mantiqiy qurilish: gap bo'laklari, sintaktik birliklar, xatboshilar"),
    ("izchillik", "Mazmuniy-mantiqiy izchillik, fikr takrorlanmasligi"),
    ("imlo", "Imlo qoidalariga rioya (ishning o'z alifbosida)"),
    ("tinish", "Tinish belgilarining to'g'ri qo'llanishi"),
    ("qoshimchalar", "So'z va shakl yasovchi qo'shimchalarning o'rinli qo'llanishi"),
    ("soz", "So'z qo'llash: leksik birliklarning o'rinli tanlanishi"),
    ("paremiya", "Paremiologizmlar va vaziyatga mos atamalardan o'rinli foydalanish"),
    ("adabiy", "Adabiy til me'yorlari: sheva, vulgarizm, varvarizm yo'qligi"),
)

CRITERIA_KEYS = tuple(key for key, _ in CRITERIA)

# Tekshirilgan, tez javob beradigan vision modellari (tartib muhim).
VISION_MODELS = ("gemini-2.5-flash", "gemini-flash-lite-latest",
                 "gemini-3-flash-preview", "gemini-3.5-flash-lite",
                 "gemini-2.0-flash")

_LABELS = {
    "uz": {
        "title": "📝 Esse tekshiruvi — Milliy sertifikat mezoni",
        "total": "Jami",
        "words": "So'zlar",
        "required": "talab: kamida 100 so'z",
        "criteria": "12 band bo'yicha",
        "errors": "Xatolar",
        "no_errors": "✅ Imlo, tinish va so'z qo'llashda xato topilmadi.",
        "strengths": "Kuchli tomonlar",
        "advice": "Maslahatlar",
        "review": "Taqriz",
        "band": "band",
        "scale": "75 ballik shkala",
        "structure": "Tuzilma",
        "sections": {"kirish": "Kirish", "asosiy": "Asosiy qism", "xulosa": "Xulosa"},
        "plan_written": "Matnda reja yozilgan — rasmiy talabda reja yozilmaydi.",
        "epigraph_written": "Matnda epigraf yozilgan — rasmiy talabda epigraf yozilmaydi.",
        "flags": {
            "blank": "Varaq bo'sh — ish yozilmagan, 0 ball.",
            "ocr_short": "Rasmdan matn to'liq o'qilmadi shekilli — jami 100 so'zdan kam chiqdi. Yorug'roq, to'liq sahifa rasmini yuboring yoki matnni yozib yuboring (hozirgi ballar to'liq matnga mos kelmasligi mumkin).",
            "short": "Ish hajmi 100 so'zdan kam — rasmiy qoidaga ko'ra 2 ball qo'yiladi.",
            "offtopic": "Ish mavzuga mos emas — rasmiy qoidaga ko'ra 2 ball qo'yiladi.",
            "copied": "Ish boshqa manbadan ko'chirilgan deb baholandi — 2 ball.",
            "notask": "Faqat kirish qismi yozilgan — topshiriq bajarilmagan, 0 ball.",
            "estimated": "AI to'liq baholay olmadi; ballar matn tahlili asosida taxminiy qo'yildi. Qayta tekshirib ko'ring.",
            "not_graded": "Hozircha AI baholab bo'lmadi — bepul limitlar vaqtincha band. Ballar o'ylab topilmaydi: bir daqiqadan so'ng «Qayta tekshirish»ni bosing.",
        },
        "not_graded_title": "Baholab bo'lmadi",
        "not_graded_retry": "Matn saqlandi — pastdagi «Qayta tekshirish» tugmasini bir daqiqadan so'ng bosing.",
        "crit": {
            "uslub": "Publitsistik uslub",
            "qarashlar": "Ikkala qarash + shaxsiy fikr",
            "dalillar": "Dalillanganlik",
            "qismlar": "Kirish–asosiy–xulosa",
            "mantiq": "Mantiqiy qurilish va xatboshilar",
            "izchillik": "Mazmuniy izchillik",
            "imlo": "Imlo",
            "tinish": "Tinish belgilari",
            "qoshimchalar": "Qo'shimchalar uslubiyati",
            "soz": "So'z qo'llash",
            "paremiya": "Tasviriy ifoda va atamalar",
            "adabiy": "Adabiy til me'yorlari",
        },
    },
    "ru": {
        "title": "📝 Проверка эссе — критерии Milliy sertifikat",
        "total": "Итого",
        "words": "Слов",
        "required": "требование: не менее 100 слов",
        "criteria": "По 12 критериям",
        "errors": "Ошибки",
        "no_errors": "✅ Орфографических, пунктуационных и лексических ошибок не найдено.",
        "strengths": "Сильные стороны",
        "advice": "Рекомендации",
        "review": "Рецензия",
        "band": "критерий",
        "scale": "Шкала 75 баллов",
        "structure": "Структура",
        "sections": {"kirish": "Вступление", "asosiy": "Основная часть", "xulosa": "Заключение"},
        "plan_written": "В работе есть план — по официальным требованиям план не пишется.",
        "epigraph_written": "В работе есть эпиграф — по официальным требованиям эпиграф не пишется.",
        "flags": {
            "blank": "Лист пуст — работа не написана, 0 баллов.",
            "ocr_short": "Текст с фото прочитан не полностью — вышло меньше 100 слов. Отправьте более чёткое фото всей страницы или пришлите текст (текущие баллы могут не соответствовать полному тексту).",
            "short": "Объём меньше 100 слов — по официальному правилу ставится 2 балла.",
            "offtopic": "Работа не соответствует теме — по официальному правилу 2 балла.",
            "copied": "Работа оценена как списанная — 2 балла.",
            "notask": "Написано только вступление — задание не выполнено, 0 баллов.",
            "estimated": "AI не смог полностью оценить работу; баллы выставлены приблизительно. Проверьте ещё раз.",
            "not_graded": "Сейчас AI не смог оценить работу — бесплатные лимиты временно заняты. Баллы не выдумываются: нажмите «Проверить ещё раз» через минуту.",
        },
        "not_graded_title": "Оценить не удалось",
        "not_graded_retry": "Текст сохранён — нажмите «Проверить ещё раз» через минуту.",
        "crit": {
            "uslub": "Публицистический стиль",
            "qarashlar": "Две точки зрения + своё мнение",
            "dalillar": "Аргументация",
            "qismlar": "Вступление–основная–заключение",
            "mantiq": "Логика и абзацы",
            "izchillik": "Смысловая связность",
            "imlo": "Орфография",
            "tinish": "Пунктуация",
            "qoshimchalar": "Употребление аффиксов",
            "soz": "Словоупотребление",
            "paremiya": "Образные средства и термины",
            "adabiy": "Нормы литературного языка",
        },
    },
    "en": {
        "title": "📝 Essay review — Milliy sertifikat criteria",
        "total": "Total",
        "words": "Words",
        "required": "requirement: at least 100 words",
        "criteria": "Across 12 criteria",
        "errors": "Errors",
        "no_errors": "✅ No spelling, punctuation or vocabulary issues found.",
        "strengths": "Strengths",
        "advice": "Recommendations",
        "review": "Reviewer note",
        "band": "criterion",
        "scale": "75-point scale",
        "structure": "Structure",
        "sections": {"kirish": "Introduction", "asosiy": "Body", "xulosa": "Conclusion"},
        "plan_written": "The work contains an outline — the official rules do not allow one.",
        "epigraph_written": "The work contains an epigraph — the official rules do not allow one.",
        "flags": {
            "blank": "The page is blank — nothing was written, 0 points.",
            "ocr_short": "The photo was probably not read in full — fewer than 100 words came through. Send a sharper photo of the whole page or paste the text (these scores may not match the full essay).",
            "short": "Fewer than 100 words — the official rule gives 2 points.",
            "offtopic": "The work is off topic — the official rule gives 2 points.",
            "copied": "The work was judged copied — 2 points.",
            "notask": "Only the introduction is written — task not done, 0 points.",
            "estimated": "The AI could not grade the whole work; the scores are approximate. Please check it again.",
            "not_graded": "The AI could not grade the work right now — free limits are temporarily used up. No scores are invented: press “Check again” in a minute.",
        },
        "not_graded_title": "Could not grade",
        "not_graded_retry": "The text is kept — press “Check again” in a minute.",
        "crit": {
            "uslub": "Publicistic style",
            "qarashlar": "Both views + own opinion",
            "dalillar": "Argumentation",
            "qismlar": "Intro–body–conclusion",
            "mantiq": "Logic and paragraphs",
            "izchillik": "Coherence",
            "imlo": "Spelling",
            "tinish": "Punctuation",
            "qoshimchalar": "Affix usage",
            "soz": "Word usage",
            "paremiya": "Figurative language and terms",
            "adabiy": "Literary language norms",
        },
    },
}


def labels(lang="uz"):
    return _LABELS.get(str(lang or "uz").lower(), _LABELS["en"])


# ===== Matn ajratish =====
def extract_docx_text(data):
    """DOCX fayldan matn: paragraflar va jadvallar."""
    from docx import Document
    document = Document(io.BytesIO(data))
    parts = [p.text for p in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                parts.append(cell.text)
    return "\n".join(part for part in parts if part and part.strip())


def decode_text(data):
    """TXT faylni kodlashni taxmin qilib o'qish (UTF-8, keyin cp1251)."""
    if not data:
        return ""
    for encoding in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", "ignore")


# Apostrof bilan yozilgan o'zbek so'zlari (to'rt, bo'lib) bitta so'z sanaladi.
_WORD_RE = re.compile(r"[^\W\d_]+(?:['\u2018\u2019\u02bb\u02bc][^\W\d_]+)*", re.UNICODE)
_CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")
_LATIN_RE = re.compile(r"[A-Za-z\u00C0-\u024F]")


def word_count(text):
    return len(_WORD_RE.findall(str(text or "")))


# Qo'lyozmada so'z qator oxirida bo'g'inlarga bo'linadi: OCR buni «dar-\nggoh»
# ko'rinishida qaytaradi. AI buni imlo xatosi deb sanab, butun bandni 0 qilardi.
_OCR_LINE_BREAK_RE = re.compile(r"(?<=[^\W\d_])-\s*\n\s*(?=[^\W\d_])", re.UNICODE)


def clean_ocr_text(text):
    """OCR natijasidagi qator oxiri chiziqchalarini birlashtiradi.

    «maʼlumot-\nga» → «maʼlumotga». Faqat harf-harf orasidagi chiziqcha
    olib tashlanadi, shuning uchun «2020-2021» kabi yozuvlar tegilmaydi.
    """
    value = str(text or "")
    for _ in range(3):
        updated = _OCR_LINE_BREAK_RE.sub("", value)
        if updated == value:
            break
        value = updated
    return value


# AI «sections» ni ko'p hollarda false qilib qo'yardi: yaxshi yozilgan esse
# «Kirish ❌ · Asosiy ❌ · Xulosa ❌» bo'lib, «qismlar» bandi 0 olardi. Tuzilma
# matnning o'zidan aniqlanadi — bu bepul va model xatosiga bog'liq emas.
_PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_XULOSA_MARKERS = re.compile(
    r"(xulosa|shunday\s+qilib|shu\s+asosda|umuman\s+aytganda|yakunlab|yakunida|"
    r"demak|shu\s+bois|bu\s+fikrlarga\s+asoslanib)", re.IGNORECASE)


# Matn Telegram yoki Word'dan ko'chirilganda xatboshilar bo'sh qator bilan
# ajratilmaydi — har bir xatbosh faqat chekinish (bo'sh joy) bilan boshlanadi.
# Shunda butun esse bitta xatbosh bo'lib ko'rinib, «asosiy qism yo'q» deb
# baholanardi.
_INDENT_RE = re.compile(r"^[ \t\u00a0]")


def _indented_blocks(raw):
    """Chekinish bilan boshlangan qatorlarni xatbosh deb ajratadi."""
    lines = [line.rstrip() for line in str(raw or "").split("\n")]
    starts = [line for line in lines
              if _INDENT_RE.match(line) and word_count(line) >= 4]
    if len(starts) < 2:
        return []
    blocks, current = [], []
    for line in lines:
        if _INDENT_RE.match(line) and current:
            blocks.append(" ".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        blocks.append(" ".join(current))
    blocks = [re.sub(r"\s+", " ", part).strip() for part in blocks]
    return [part for part in blocks if word_count(part) >= 4]


def paragraphs_of(text, loose=False):
    """Matn xatboshilari.

    ``loose`` — qo'lyozma (OCR) matni uchun: OCR ba'zan bo'sh qatorlarni
    tushirib qoldiradi, shunda xatboshilar gaplar bo'yicha ajratiladi.
    """
    raw = str(text or "")
    blocks = [re.sub(r"[ \t]+", " ", part).strip()
              for part in _PARAGRAPH_SPLIT_RE.split(raw)]
    blocks = [part for part in blocks if word_count(part) >= 4]
    if len(blocks) <= 1:
        # Bo'sh qator yo'q, lekin xatboshilar chekinish bilan boshlangan.
        blocks = _indented_blocks(raw) or blocks
    if loose and len(blocks) <= 1 and word_count(raw) >= 90:
        sentences = [s for s in _SENTENCE_SPLIT_RE.split(re.sub(r"\s+", " ", raw).strip()) if s]
        blocks, chunk = [], []
        for sentence in sentences:
            chunk.append(sentence)
            if word_count(" ".join(chunk)) >= 40:
                blocks.append(" ".join(chunk))
                chunk = []
        if chunk:
            blocks.append(" ".join(chunk))
    return blocks


def detect_sections(text, loose=False):
    """Kirish / asosiy qism / xulosa borligini matndan aniqlaydi.

    Qaytaradi: ({'kirish': bool, 'asosiy': bool, 'xulosa': bool}, xatboshilar soni).
    """
    blocks = paragraphs_of(text, loose=loose)
    count = len(blocks)
    if count == 0:
        return {"kirish": False, "asosiy": False, "xulosa": False}, 0
    words = re.sub(r"\s+", " ", str(text or "")).split()
    tail = blocks[-1]
    if words:
        tail += " " + " ".join(words[int(len(words) * 0.75):])
    has_conclusion = bool(_XULOSA_MARKERS.search(tail))
    if count >= 3:
        return {"kirish": True, "asosiy": True, "xulosa": True}, count
    if count == 2:
        return {"kirish": True, "asosiy": True, "xulosa": has_conclusion}, count
    # Bitta xatbosh — asosiy qism alohida ajratilmagan; xulosa belgisi bo'lsa, bor.
    return {"kirish": True, "asosiy": False, "xulosa": has_conclusion}, count


# AI keltirgan «xato» matnda umuman bo'lmasligi mumkin (OCR xatosi yoki
# to'qib chiqarilgan so'z). Bunday yozuv ballni asossiz tushirardi.
_QUOTE_STRIP_RE = re.compile(r"[^0-9a-z\u00c0-\u024f\u0400-\u04ff]+")
_APOSTROPHE_MAP = str.maketrans({"\u2018": "'", "\u2019": "'", "\u02bb": "'",
                                 "\u02bc": "'", "`": "'", "\u00b4": "'"})


def _flat_text(value):
    return _QUOTE_STRIP_RE.sub("", str(value or "").translate(_APOSTROPHE_MAP).casefold())


def _quote_in_text(quote, text):
    """Keltirilgan parcha haqiqatan matnda bormi (tinish/apostrof farqi bilan)."""
    needle = _flat_text(quote)
    if len(needle) < 3:
        return True
    return needle in _flat_text(text)


# Model xato turini turlicha yozadi: «qo'shimcha», «leksika», «punktuatsiya».
_TYPE_ALIASES = {
    "qoshimcha": "qoshimchalar", "qo'shimcha": "qoshimchalar",
    "qosimcha": "qoshimchalar", "affiks": "qoshimchalar",
    "so'z": "soz", "soz qo'llash": "soz", "leksika": "soz", "leksik": "soz",
    "orfografiya": "imlo", "imlo xatosi": "imlo",
    "punktuatsiya": "tinish", "tinish belgisi": "tinish",
}


# AI ba'zan bandni boshqacha nom bilan qaytaradi: «qo'shimchalar», «punktuatsiya»,
# «so'z qo'llash», «adabiy til». Kalit mos kelmasa, band o'tkazib yuborilgan
# bo'lib, 0 ball olardi — holbuki 0 faqat ish bajarilmagan holat uchun.
_CRITERIA_ALIASES = {
    "uslub": "uslub", "uslubiyat": "uslub", "publitsistikuslub": "uslub",
    "style": "uslub",
    "qarash": "qarashlar", "qarashlar": "qarashlar", "ikkalaqarash": "qarashlar",
    "shaxsiyqarash": "qarashlar", "ikkalaqarashvashaxsiyqarash": "qarashlar",
    "views": "qarashlar",
    "dalil": "dalillar", "dalillar": "dalillar", "argumentatsiya": "dalillar",
    "dalillanganlik": "dalillar", "arguments": "dalillar",
    "qismlar": "qismlar", "tuzilma": "qismlar", "kompozitsiya": "qismlar",
    "matntuzilishi": "qismlar", "structure": "qismlar",
    "mantiq": "mantiq", "mantiqiylik": "mantiq", "mantiqiyqurilish": "mantiq",
    "logic": "mantiq",
    "izchillik": "izchillik", "mazmuniyizchillik": "izchillik",
    "mazmuniymantiqiyizchillik": "izchillik", "izchillikvayaxlitlik": "izchillik",
    "coherence": "izchillik",
    "imlo": "imlo", "orfografiya": "imlo", "imloqoidalari": "imlo",
    "spelling": "imlo",
    "tinish": "tinish", "punktuatsiya": "tinish", "tinishbelgilari": "tinish",
    "punctuation": "tinish",
    "qoshimchalar": "qoshimchalar", "qoshimcha": "qoshimchalar",
    "sozvashaklyasovchiqoshimchalar": "qoshimchalar", "affixes": "qoshimchalar",
    "soz": "soz", "sozqollash": "soz", "soztanlash": "soz",
    "leksika": "soz", "leksikbirliklar": "soz", "vocabulary": "soz",
    "paremiya": "paremiya", "paremiologizmlar": "paremiya",
    "tasviriyifoda": "paremiya", "atamalar": "paremiya",
    "adabiy": "adabiy", "adabiytil": "adabiy", "adabiytilmeyorlari": "adabiy",
    "adabiytilmeyori": "adabiy", "literarynorms": "adabiy",
}


def _criterion_key(raw):
    """AI qaytargan band nomini rasmiy kalitga aylantiradi (topilmasa None)."""
    key = _QUOTE_STRIP_RE.sub("", str(raw or "").translate(_APOSTROPHE_MAP).casefold())
    key = re.sub(r"^\d+", "", key)
    if key in CRITERIA_KEYS:
        return key
    alias = _CRITERIA_ALIASES.get(key)
    if alias:
        return alias
    # «mazmuniy-mantiqiy izchillik» kabi to'liq nomlar: avval izchillik.
    if "izchillik" in key:
        return "izchillik"
    for name in CRITERIA_KEYS:
        if name in key:
            return name
    return None


def detect_script(text):
    """Matn qaysi alifboda yozilgan: «cyrillic» yoki «latin».

    Ikkala alifbo ham qabul qilinadi — imlo va tinish shu alifbo qoidalari
    bo'yicha tekshiriladi, alifbo tanlovi uchun ball tushirilmaydi.
    """
    return "cyrillic" if cyrillic_ratio(text) >= 0.6 else "latin"


def cyrillic_ratio(text):
    """Matndagi harflarning qancha qismi kirill ekani (0..1)."""
    cyrillic = len(_CYRILLIC_RE.findall(str(text or "")))
    latin = len(_LATIN_RE.findall(str(text or "")))
    total = cyrillic + latin
    return (cyrillic / float(total)) if total else 0.0


# Navbat chegaralari har hodisa tsikli (event loop) uchun alohida: bot bitta
# tsiklda, Mini App esa har so'rovda o'z tsiklida ishlaydi.
_GATES = threading.local()


def _gate(name, limit):
    loop_id = id(asyncio.get_running_loop())
    state = getattr(_GATES, "state", None)
    if state is None or state["loop"] != loop_id:
        state = {"loop": loop_id, "sems": {}}
        _GATES.state = state
    sem = state["sems"].get(name)
    if sem is None:
        sem = asyncio.Semaphore(limit)
        state["sems"][name] = sem
    return sem


# ===== Rasmdan matn (OCR) — Gemini vision =====
OCR_PROMPT = (
    "Bu rasmda qo'lyozma yoki bosma matn (o'quvchi daftari yoki varaq) bor. "
    "Sahifadagi BARCHA matnni to'liq va tartib bilan yozib bering.\n"
    "- Matn o'zbek lotin yoki kirill alifbosida qo'lda yozilgan bo'lishi mumkin. "
    "Qaysi alifboda yozilgan bo'lsa, o'sha alifbodagi harflarni aniq saqlang: lotinda "
    "o', g', sh, ch, ng harflari va apostroflar (o', g'), kirillda ў, қ, ғ, ҳ, "
    "ш, ч, нг harflari. Hech bir harfni tushirib qoldirmang va alifboni almashtirmang.\n"
    "- Daftar chizig'iga yozilgan mayda harflarni ham o'qing; qator chetidagi, "
    "sarlavha va sana kabi yozuvlarni ham qo'shing.\n"
    "- So'z chizilgan yoki ustidan tuzatilgan bo'lsa, oxirgi (tuzatilgan) variantni yozing.\n"
    "- Har bir so'zni qator kontekstida tekshiring: o'qilgan so'z o'zbek tilida "
    "mantiqiy bo'lmasa, uni qayta o'qing (masalan «bormoqda» ni «mogda» deb "
    "yozmang). o', g', sh, ch, ng birikmalari va nuqtali harflarni aniq ajrating.\n"
    "- Hech narsani qisqartirmang va tashlab ketmang; qatorlar va xatboshilarni saqlang.\n"
    "- Imlo va tinish belgilaridagi xatolarni TUZATMANG: so'z qanday yozilgan bo'lsa, "
    "aynan shunday yozing — tekshiruv uchun bu muhim.\n"
    "- So'z o'ylab topmang, izoh, sarlavha yoki tarjima qo'shmang.\n"
    "- Faqat matnning o'zini qaytaring. Rasmda matn bo'lmasa, bo'sh javob bering."
)

_CONTINUE_PROMPT = (
    "Sahifadagi matn to'liq yozilmadi. Quyida hozir yozilgan matnning oxiri berilgan. "
    "SHU JOYDAN davom etib, qolgan barcha matnni yozib bering. Faqat davomini "
    "yozing, avval yozilganini takrorlamang va izoh qo'shmang."
)


def prepare_image(data):
    """Rasmni o'qish uchun tayyorlaydi: kattalashtirish, kontrast, JPEG.

    Qo'lyozma uchun o'lcham muhim: juda kichik rasmda ingichka harflar yo'qoladi va
    model sahifaning faqat bir qismini o'qib qo'yadi. Shu sababli kichik suratni
    kattalashtiramiz, xira suratning kontrastini esa yengil ko'taramiz.
    """
    try:
        from PIL import Image, ImageOps
        with Image.open(io.BytesIO(data)) as source:
            source.load()
            image = source.convert("RGB")
            longest = max(image.size)
            if longest > MAX_IMAGE_SIDE:
                ratio = MAX_IMAGE_SIDE / float(longest)
                size = (max(1, int(image.width * ratio)), max(1, int(image.height * ratio)))
                image = image.resize(size, Image.LANCZOS)
            elif longest < MIN_IMAGE_SIDE:
                ratio = MIN_IMAGE_SIDE / float(longest)
                size = (max(1, int(image.width * ratio)), max(1, int(image.height * ratio)))
                image = image.resize(size, Image.LANCZOS)
            try:
                # Daftar sahifasidagi kulrang fon va xira qalamni ajratish uchun.
                image = ImageOps.autocontrast(image, cutoff=1)
            except Exception:
                pass
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=92, optimize=True)
        return buffer.getvalue(), "image/jpeg"
    except Exception as exc:
        print(f"[check] rasm tayyorlanmadi: {type(exc).__name__}: {exc}", flush=True)
        return data, "image/jpeg"


def _vision_config(model, max_tokens):
    """So'rov sozlamalari.

    Gemini 2.5+ «o'ylash» byudjetini aynan shu javob tokenlaridan oladi: yoqilgan
    bo'lsa OCR matni yarmida uzilib qoladi (foydalanuvchi 300 so'zli qo'lyozma
    uchun «57 so'z» ko'rgan holat). Shuning uchun o'ylashni o'chiramiz.
    """
    config = {"temperature": 0, "maxOutputTokens": max_tokens}
    name = str(model or "").lower()
    if "2.0" not in name and "gemma" not in name:
        config["thinkingConfig"] = {"thinkingBudget": 0}
    return config


def _vision_text(raw):
    """Javobdan matn va «tugallanmagan» belgisini ajratadi."""
    try:
        data = json.loads(raw)
    except Exception:
        return "", False
    candidate = (data.get("candidates") or [{}])[0]
    parts = ((candidate.get("content") or {}).get("parts") or [])
    text = "".join(str(part.get("text") or "") for part in parts).strip()
    reason = candidate.get("finishReason")
    truncated = str(reason).upper() == "MAX_TOKENS" or reason == 2
    return text, truncated


# Bepul kvota tugagan modelni har bir sahifada qayta sinash 5-6 varaqli
# qo'lyozmada o'nlab bekorga so'rov degani. Xato bergan model vaqtincha
# chetlatiladi, shunda ishlaydigan modelga tezroq yetib boramiz.
_VISION_SKIP = {}


def _vision_key(row, model):
    return f"{str(row.get('name') or '')}|{str(model or '')}"


def _vision_skipped(row, model):
    entry = _VISION_SKIP.get(_vision_key(row, model))
    if not entry:
        return False
    if time.time() >= entry[0]:
        _VISION_SKIP.pop(_vision_key(row, model), None)
        return False
    return True


def _vision_fail(row, model, status, body):
    low = str(body or "").lower()
    if status == 429:
        minute = ("perminute" in low or "per minute" in low or "per_minute" in low)
        seconds = 90 if minute else (1800 if ("quota" in low or "billing" in low) else 90)
        reason = "bepul kvota tugagan" if seconds > 100 else "so'rov limiti"
    elif status in (404, 410) or "no longer available" in low:
        seconds, reason = 6 * 3600, "model mavjud emas"
    elif status in (400, 401, 403):
        seconds, reason = 900, "model yoki kalit javob bermadi"
    elif status in (500, 502, 503, 504, 529):
        seconds, reason = 120, "model vaqtincha band"
    else:
        return
    _VISION_SKIP[_vision_key(row, model)] = (time.time() + seconds, reason)
    print(f"[check] ⏭ {row.get('name')} / {model}: {reason}", flush=True)


async def _vision_post(url, payload, total=90):
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=total)) as session:
        async with session.post(url, json=payload) as resp:
            return resp.status, await resp.text()


async def _vision_call(row, model, image_data, mime, prompt, total=90):
    """Bitta modeldan matnni o'qiydi. (matn, tugallanmaganmi) qaytaradi."""
    base = str(row.get("base_url") or ai_pool.PROVIDER_BASE.get("google", "")).rstrip("/")
    key = str(row.get("api_key") or "")
    if not base or not key:
        return "", False
    url = f"{base}/models/{model}:generateContent?key={key}"
    parts = [
        {"text": prompt},
        {"inlineData": {"mimeType": mime,
                        "data": base64.b64encode(image_data).decode("ascii")}},
    ]
    for attempt in range(2):
        config = _vision_config(model, VISION_MAX_TOKENS)
        if attempt:
            # Eski modellar thinkingConfig'ni bilmaydi — usiz qayta urinamiz.
            config.pop("thinkingConfig", None)
        payload = {"contents": [{"role": "user", "parts": parts}],
                   "generationConfig": config}
        try:
            status, body = await _vision_post(url, payload, total)
        except Exception as exc:
            print(f"[check] vision xatosi: {type(exc).__name__}: {exc}", flush=True)
            # Javob kelmasa (timeout) modelni qayta-qayta kutib o'tirmaymiz.
            _vision_fail(row, model, 504, f"{type(exc).__name__}: {exc}")
            return "", False
        if status == 200:
            return _vision_text(body)
        # 400 har doim thinkingConfig aybi bo'lmasa ham, sozlamasiz qayta
        # so'rash arzon va ko'p holatda aynan shu sabab bo'ladi.
        if attempt == 0 and status == 400:
            continue
        # 5xx — provayder vaqtincha band, bir marta qayta so'raymiz.
        if attempt == 0 and status in (500, 502, 503, 504, 529):
            await asyncio.sleep(0.6)
            continue
        print(f"[check] vision {model}: HTTP {status}: {str(body)[:180]}", flush=True)
        _vision_fail(row, model, status, body)
        return "", False
    return "", False


def _join_continuation(head, tail):
    """Davomiy javobni bosh matnga qo'shadi, takrorlangan joyni kesib tashlaydi."""
    head = str(head or "").rstrip()
    tail = str(tail or "").strip()
    if not head:
        return tail
    if not tail:
        return head
    overlap = 0
    for size in range(min(len(tail), 240), 0, -1):
        if head.endswith(tail[:size]):
            overlap = size
            break
    if overlap:
        tail = tail[overlap:]
        return (head + tail).strip() if tail.strip() else head
    return (head + "\n" + tail).strip()


async def _read_full_page(row, model, data, mime, prompt):
    """Sahifani to'liq o'qiydi; javob uzilsa davomini so'raydi."""
    text, truncated = await _vision_call(row, model, data, mime, prompt)
    rounds = 0
    while truncated and text and rounds < 3:
        rounds += 1
        tail_prompt = (f"{OCR_PROMPT}\n\n{_CONTINUE_PROMPT}\n\n"
                       f"HOZIR YOZILGAN MATNNING OXIRI:\n{text[-1200:]}")
        extra, truncated = await _vision_call(row, model, data, mime, tail_prompt)
        if not extra:
            break
        joined = _join_continuation(text, extra)
        if word_count(joined) <= word_count(text):
            break
        text = joined
    return text


def _vision_candidates(models):
    """Sinash tartibi: sinalgan tez modellar birinchi, keyin kalitdagi qolganlar."""
    ordered = [model for model in VISION_MODELS if not models or model in models]
    ordered += [model for model in models if model not in ordered]
    return ordered


# Oxirgi marta ishlagan model eslab qolinadi: keyingi sahifalarda birinchi
# navbatda o'sha sinaladi. Bu bepul kvotani behuda sarflashni kamaytiradi.
_VISION_LAST = {}
# Bir xil sahifa qayta yuborilsa (albomni qayta yig'ish, foydalanuvchi qayta
# urinishi) OCR takrorlanmaydi.
_OCR_CACHE = {}
_OCR_CACHE_TTL = 900
_OCR_CACHE_MAX = 40


def _ocr_cache_get(key):
    entry = _OCR_CACHE.get(key)
    if not entry:
        return ""
    if time.time() - entry[1] > _OCR_CACHE_TTL:
        _OCR_CACHE.pop(key, None)
        return ""
    return entry[0]


def _ocr_cache_put(key, text):
    if not text:
        return
    if len(_OCR_CACHE) >= _OCR_CACHE_MAX:
        oldest = min(_OCR_CACHE, key=lambda name: _OCR_CACHE[name][1])
        _OCR_CACHE.pop(oldest, None)
    _OCR_CACHE[key] = (text, time.time())


def _prefer_last_model(rows):
    """Oxirgi ishlagan kalitni ro'yxat boshiga suradi."""
    name = str(_VISION_LAST.get("key") or "")
    if not name:
        return rows
    return sorted(rows, key=lambda row: 0 if str(row.get("name") or "") == name else 1)


def _order_models(row, models):
    """Oxirgi ishlagan modelni birinchi qilib qaytaradi."""
    ordered = _vision_candidates(models)
    name = str(_VISION_LAST.get("key") or "")
    model = str(_VISION_LAST.get("model") or "")
    if name and model and str(row.get("name") or "") == name and model in ordered:
        ordered.remove(model)
        ordered.insert(0, model)
    return ordered


async def ocr_image(image_data, lang="uz"):
    """Rasmdagi matnni to'liq o'qib beradi; Google kaliti bo'lmasa bo'sh satr.

    Bir nechta model sinaladi va eng to'liq (eng ko'p so'zli) natija olinadi:
    qo'lyozmani bitta model faqat qisman o'qib qo'yishi mumkin, o'shanda butun
    tekshiruv «matn juda qisqa» degan noto'g'ri xulosaga keladi.
    """
    if not image_data:
        return ""
    cache_key = hashlib.sha1(image_data).hexdigest()
    cached = _ocr_cache_get(cache_key)
    if cached:
        print(f"[check] OCR keshdan: {word_count(cached)} so'z", flush=True)
        return cached
    rows = []
    try:
        for item in ai_pool.keys(active_only=True):
            if str(item["provider"] or "") == "google" or \
                    "generativelanguage" in str(item["base_url"] or ""):
                rows.append(item)
    except Exception as exc:
        print(f"[check] AI kalitlari olinmadi: {exc}", flush=True)
        return ""
    if not rows:
        return ""
    rows = _prefer_last_model(rows)
    data, mime = prepare_image(image_data)
    best = ""
    # Har bir kalitdagi barcha Google kalitlarini sinaymiz, lekin jami urinish
    # byudjeti cheklangan: bitta sahifa uchun 5-6 ta so'rovdan ko'proq ketmaydi.
    budget = 6
    for row in rows[:3]:
        models = [m.strip() for m in str(row["models"] or "").split(",") if m.strip()]
        for model in _order_models(row, models):
            if budget <= 0:
                break
            if _vision_skipped(row, model):
                continue
            budget -= 1
            async with _gate("ocr", OCR_CONCURRENCY):
                text = await _read_full_page(row, model, data, mime, OCR_PROMPT)
            text = clean_ocr_text(text)
            if word_count(text) > word_count(best):
                best = text
                if word_count(best) >= MIN_OCR_WORDS:
                    _VISION_LAST["key"] = str(row.get("name") or "")
                    _VISION_LAST["model"] = model
            if word_count(best) >= OCR_ENOUGH_WORDS:
                _ocr_cache_put(cache_key, best)
                return best
        if budget <= 0 or word_count(best) >= OCR_ENOUGH_WORDS:
            break
    _ocr_cache_put(cache_key, best)
    return best


# ===== AI tahlili =====
def _json_closers(text):
    """Ochiq qolgan qavslar/satr uchun yopuvchi belgilar."""
    stack, in_string, escaped = [], False, False
    for char in str(text or ""):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            stack.append("}")
        elif char == "[":
            stack.append("]")
        elif char in "}]" and stack:
            stack.pop()
    if in_string:
        stack.insert(0, '"')
    return "".join(stack)


def _repair_json(text):
    """Tokeni tugab uzilgan JSON javobini yopib ko'radi.

    Model javobni yarmida to'xtatsa, avvalgi kod butun hisobotni yo'qotardi va
    foydalanuvchi «xatolik» ko'rardi. Endi oxirgi to'liq bo'lmagan bo'lak
    kesiladi va qolgan qism yopiladi.
    """
    raw = str(text or "")
    start = raw.find("{")
    if start == -1:
        return None
    raw = raw[start:]
    for _ in range(8):
        if not raw.strip():
            return None
        head = raw.rstrip().rstrip(",")
        closers = _json_closers(head)
        if closers:
            try:
                data = json.loads(head + closers)
                if isinstance(data, dict) and "scores" in data:
                    return data
            except Exception:
                pass
        cut = max(head.rfind(","), head.rfind(":"))
        if cut <= 0:
            return None
        raw = head[:cut]
    return None


def _parse_json_object(text):
    raw = str(text or "").strip()
    if not raw:
        return None
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, flags=re.DOTALL)
    if fenced:
        raw = fenced.group(1)
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end > start:
        try:
            data = json.loads(raw[start:end + 1])
            if isinstance(data, dict) and data:
                return data
        except Exception:
            pass
    return _repair_json(raw)


def _clean_list(values, limit=5, size=180):
    out = []
    for value in values or []:
        if isinstance(value, dict):
            value = value.get("text") or value.get("comment") or ""
        text = str(value or "").strip()
        if text:
            out.append(re.sub(r"\s+", " ", text)[:size])
        if len(out) >= limit:
            break
    return out


# AI ba'zan to'g'ri so'zni «xato» deb ko'rsatib, tuzatish o'rniga o'sha so'zni
# qaytaradi («Insho» → «Insho»). Bunday yozuvlar hisobotga chiqmasligi kerak.
_PLACEHOLDER_FIXES = ("to'g'ri yozilishi kerak", "to‘g‘ri yozilishi kerak",
                      "to'g'ri varianti", "to‘g‘ri varianti", "to'g'ri variant",
                      "xato yo'q", "o'zgartirish shart emas")


def _plain_cell(value):
    text = str(value or "").casefold()
    # «xato → tuzatish» ko'rinishida kelgan bo'lsa, faqat tuzatish qismi olinadi.
    for arrow in ("→", "->", "=>"):
        if arrow in text:
            text = text.split(arrow)[-1]
    text = re.sub(r"[«»\"'‘’ʻʼ`.,;:!?()\[\]—–-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _is_fake_error(quote, fix):
    """Xato deb ko'rsatilgan, lekin aslida tuzatish bermagan yozuv."""
    raw = str(fix or "").casefold()
    if not raw.strip():
        return True
    if any(marker in raw for marker in _PLACEHOLDER_FIXES):
        return True
    return bool(quote) and _plain_cell(fix) == _plain_cell(quote)


# O'zbek lotin alifbosida bu harflar yo'q. Model ularni qo'shib «tuzatish»
# bergan bo'lsa (masalan «enagalar» → «enağalar»), demak u to'g'ri yozilgan
# so'zni xato deb ko'rsatgan — bunday yozuv hisobotga ham, ballga ham
# ta'sir qilmasligi kerak.
_FOREIGN_LETTER_RE = re.compile(r"[ğəıöüşçâêîôûñ]")


def _bad_correction(quote, fix):
    """Tuzatish so'zni o'zgartirmasa, alifboni almashtirsa yoki begona harf qo'shsa."""
    fix_text = str(fix or "")
    quote_text = str(quote or "")
    if quote_text and _plain_cell(fix_text) == _plain_cell(quote_text):
        return True
    # «мактаб» → «maktab» — bu imlo xatosi emas, alifbo almashtirish.
    quote_cyr = bool(_CYRILLIC_RE.search(quote_text))
    fix_cyr = bool(_CYRILLIC_RE.search(fix_text))
    if quote_cyr != fix_cyr:
        other = fix_text if quote_cyr else quote_text
        swapped = quote_text if quote_cyr else fix_text
        if _LATIN_RE.search(other) and not _CYRILLIC_RE.search(other):
            return True
        if _CYRILLIC_RE.search(swapped) and not _LATIN_RE.search(swapped):
            return True
    foreign = _FOREIGN_LETTER_RE.search(fix_text)
    return bool(foreign) and not _FOREIGN_LETTER_RE.search(quote_text)


# Qo'lyozmada so'z qator oxirida bo'linadi va OCR uni «standart--larga» yoki
# «standart¬larga» qilib qaytaradi. Bu imlo ham, tinish ham xatosi emas.
_BROKEN_HYPHEN_RE = re.compile(r"-{1,2}|\u00ac|\u00ad")


def _broken_word_break(quote, fix):
    """Parcha tuzatishdan faqat bo'g'in ko'chirish chiziqchasi bilan farq qilsa."""
    raw = str(quote or "")
    if not raw or not _BROKEN_HYPHEN_RE.search(raw):
        return False
    return _plain_cell(_BROKEN_HYPHEN_RE.sub("", raw)) == _plain_cell(fix)


# Promptda aytilgan: paremiya uchun maqol shart emas, dalil uchun statistika
# shart emas. Model esa shu sabab bilan bandni 1 ga tushiradi — bunday
# tushirish asossiz, shuning uchun qabul qilinmaydi.
_EVIDENCE_BANDS = ("uslub", "dalillar", "mantiq", "izchillik", "paremiya", "adabiy")
_INVALID_LOWERING = {
    "paremiya": (re.compile(r"(maqol|topishmoq|paremiya)[^.;!?]*"
                            r"(yo'q|emas|keltirilmagan|ishlatilmagan)", re.IGNORECASE),
                 # «Maqol bor, lekin to'liq ifodalanmagan» — baribir asossiz tushirish.
                 re.compile(r"(maqol|topishmoq|paremiya|tasviriy\s+ifoda|ibora)[^.;!?]*"
                            r"(to'liq|aniq)[^.;!?]*(emas|ifodalanmagan|kuchsiz)",
                            re.IGNORECASE)),
    "dalillar": re.compile(r"(statistik|raqam|manba|adabiyot)[^.;!?]*"
                           r"(yetarli emas|keltirilmagan|ko'rsatilmagan|berilmagan|yo'q)",
                           re.IGNORECASE),
    "qarashlar": re.compile(r"(shaxsiy|muallif)[^.;!?]*(fikr|munosabat)[^.;!?]*"
                            r"(aniq ajratil|ifodalanmagan|ko'rsatilmagan|emas|yo'q)",
                            re.IGNORECASE),
}


# Matnda muallifning o'z munosabati borligi (qarashlar bandi uchun).
_PERSONAL_VIEW_RE = re.compile(
    r"(mening\s+fikrimcha|menimcha|mening\s+nazarimda|mening\s+fikrim|bu\s+fikrga\s+qo'shilaman|"
    r"men\s+shunday\s+o'ylayman|men\s+[^.;!?]{0,60}deb\s+(hisoblayman|o'ylayman)|o'z\s+fikrim)",
    re.IGNORECASE)


def _has_personal_view(text):
    """Matnda «menimcha/mening fikrimcha» kabi shaxsiy munosabat bormi."""
    value = str(text or "").translate(_APOSTROPHE_MAP).casefold()
    return bool(_PERSONAL_VIEW_RE.search(value))


def _invalid_lowering(key, note):
    """Izohdagi tushirish sababi rasmiy qoidaga zidmi."""
    patterns = _INVALID_LOWERING.get(key)
    if not patterns:
        return False
    if hasattr(patterns, "search"):
        patterns = (patterns,)
    return any(pattern.search(str(note or "")) for pattern in patterns)


_REPEAT_CLAIM_RE = re.compile(r"(takrorlan|qaytaril)", re.IGNORECASE)


def _repeat_claim_unsupported(note, text):
    """«Takrorlanadi» degan izoh, keltirilgan parcha matnda bir marta bo'lsa."""
    note = re.sub(r"\s+", " ", str(note or ""))
    if not _REPEAT_CLAIM_RE.search(note):
        return False
    flat = _flat_text(text)
    fragments = re.findall(r"[«\"“„]([^«»\"“”„]{4,})[»\"“”]", note)
    if not fragments:
        words = re.findall(r"[\w'’ʻ]+", note)
        fragments = [" ".join(words[i:i + 4]) for i in range(len(words) - 3)]
    present = [_flat_text(fragment) for fragment in fragments
               if _flat_text(fragment) and _flat_text(fragment) in flat]
    if not present:
        return False
    return all(flat.count(needle) < 2 for needle in present)


def _clean_note_claims(note):
    """Izohdagi o'z-o'zini inkor etuvchi «tuzatish»larni olib tashlaydi.

    Model «azosi» o'rniga «azosi» yoki «intellektual» o'rniga «intellektual»
    (to'g'ri) deb yozadi — bu xato emas, shunchaki shovqin.
    """
    markers = r"o'rniga|o\u2018rniga|o\u02bbrniga|\u2192"
    pattern = re.compile(r"[«\"‘“]([^«»\"“”‘’]{2,40})[»\"”’]\s*(?:" + markers +
                         r")\s*[«\"‘“]([^«»\"“”‘’]{2,40})[»\"”’]")

    def _drop_equal(match):
        if _plain_cell(match.group(1)) == _plain_cell(match.group(2)):
            return ""
        return match.group(0)

    cleaned = pattern.sub(_drop_equal, str(note or ""))
    cleaned = re.sub(r"\(\s*to'g'ri\s*\)", "", cleaned, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", cleaned).strip(" ,;").strip()


def _note_evidence(note, text):
    """Izohda matndan olingan parcha bormi (qo'shtirnoqli yoki so'zma-so'z)."""
    note = re.sub(r"\s+", " ", str(note or "")).strip()
    if not note:
        return False
    for fragment in re.findall(r"[«\"“„'‘]([^«»\"“”„'‘’]{12,})[»\"“”'’]", note):
        if _quote_in_text(fragment, text):
            return True
    words = re.findall(r"[\w'’ʻ]+", note)
    for index in range(len(words) - 3):
        if _quote_in_text(" ".join(words[index:index + 4]), text):
            return True
    return False

def _score_value(value):
    """AI 2, "2", "2/2" yoki "2 ball" qaytarishi mumkin — hammasidan raqam oladi."""
    if isinstance(value, bool) or value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(round(float(value)))
    match = re.search(r"-?\d+(?:[.,]\d+)?", str(value))
    if not match:
        return 0
    try:
        return int(round(float(match.group(0).replace(",", "."))))
    except ValueError:
        return 0


def _map_scores(raw_scores):
    """AI qaytargan ballarni kanonik band kalitlariga bog'laydi."""
    mapped = {}
    if not isinstance(raw_scores, dict):
        return mapped
    for raw_key, value in raw_scores.items():
        key = _criterion_key(raw_key)
        if not key or key in mapped:
            continue
        # null yoki bo'sh qiymat — «baholanmagan», 0 emas.
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        mapped[key] = max(0, min(MAX_PER_BAND, _score_value(value)))
    return mapped


def missing_criteria(raw_scores):
    """AI javobida umuman baholanmagan bandlar."""
    mapped = _map_scores(raw_scores)
    return [key for key in CRITERIA_KEYS if key not in mapped]


def band_scores(raw_scores, fallback=1):
    """Har bir bandni 0..2 oralig'iga keltiradi.

    ``fallback`` — javobda umuman ko'rsatilmagan band uchun ball. Rasmiy
    qoidaga ko'ra 0 faqat ish bajarilmagan holat uchun, shuning uchun
    o'tkazib yuborilgan band 0 emas, 1 (o'rtacha) oladi.
    """
    mapped = _map_scores(raw_scores)
    return {key: mapped.get(key, fallback) for key in CRITERIA_KEYS}


def to_scale_75(total):
    """Rasmiy qoida: 24 ballik natija 75 ballik shkalaga o'tkaziladi."""
    try:
        value = float(total or 0)
    except (TypeError, ValueError):
        value = 0.0
    value = max(0.0, min(float(MAX_TOTAL), value))
    return int(round(value * SCALE_MAX / float(MAX_TOTAL)))


def baseline_scores(text):
    """AI baholay olmagan holat uchun ehtiyot bahosi.

    Rasmiy qoidada yaroqli ish 0 ball olmaydi (0 — bo'sh varaq yoki faqat
    kirish qismi uchun). Shuning uchun matn mavjud bo'lsa
    har bir bandga pastki (1) baho qo'yiladi, «qismlar» esa xatboshilar soniga
    qarab aniqlanadi. Hisobotda bu taxminiy ekani ogohlantiriladi.
    """
    paragraphs = [part for part in re.split(r"\n+", str(text or ""))
                  if word_count(part) >= 5]
    scores = {key: 1 for key in CRITERIA_KEYS}
    scores["qismlar"] = 2 if len(paragraphs) >= 3 else 1
    return scores


def normalize_report(data, text, lang="uz", topic="", from_image=False):
    """AI javobini rasmiy qoidalar bilan tekshirilgan hisobotga aylantiradi.

    ``from_image`` — matn rasm (qo'lyozma) dan o'qilgani. Bunday matn to'liq
    o'qilmagan bo'lishi mumkin, shuning uchun hajm bo'yicha «2 ball» qoidasi
    o'rniga foydalanuvchiga qayta yuborish taklif qilinadi.
    """
    missing = missing_criteria(data.get("scores"))
    scores = band_scores(data.get("scores"))
    notes = {}
    raw_notes = data.get("notes") if isinstance(data.get("notes"), dict) else {}
    mapped_notes = {}
    for raw_key, raw_note in raw_notes.items():
        key = _criterion_key(raw_key)
        if key and key not in mapped_notes:
            mapped_notes[key] = raw_note
    for key in CRITERIA_KEYS:
        note = str(mapped_notes.get(key) or "").strip()
        notes[key] = _clean_note_claims(re.sub(r"\s+", " ", note))[:200]

    errors = []
    # Model aslida qaysi turdagi xatoni ko'rsatgan. Parcha OCR matnidan
    # tasdiqlanmasa ham, band «xato yo'q» deb 2 ga ko'tarilmasligi kerak.
    faulted = set()
    for item in (data.get("errors") or [])[:MAX_ERRORS]:
        if isinstance(item, dict):
            # To'g'ri so'zni «xato» deb ko'rsatgan yozuv bandni tushirmasin.
            if _bad_correction(item.get("quote"), item.get("fix")):
                continue
            raw_kind = _flat_text(item.get("type") or "imlo")[:24] or "imlo"
            faulted.add(_TYPE_ALIASES.get(raw_kind, raw_kind))
    for item in (data.get("errors") or [])[:MAX_ERRORS]:
        if not isinstance(item, dict):
            continue
        quote = str(item.get("quote") or "").strip()[:160]
        fix = str(item.get("fix") or "").strip()[:160]
        if not quote and not fix:
            continue
        if (_is_fake_error(quote, fix) or _bad_correction(quote, fix)
                or _broken_word_break(quote, fix)):
            continue
        # Matnda bo'lmagan parcha — OCR xatosi yoki to'qib chiqarilgan so'z.
        if quote and not _quote_in_text(quote, text):
            continue
        kind = _flat_text(item.get("type") or "imlo")[:24] or "imlo"
        kind = _TYPE_ALIASES.get(kind, kind)
        errors.append({
            "quote": quote,
            "fix": fix,
            "type": kind,
            "rule": str(item.get("rule") or "").strip()[:180],
        })

    words = word_count(text)
    raw_sections = data.get("sections") if isinstance(data.get("sections"), dict) else {}
    detected, para_count = detect_sections(text, loose=from_image)
    # Tuzilma matndan aniqlanadi; AI faqat qo'shimcha tasdiq bera oladi.
    sections = {key: bool(detected.get(key)) or raw_sections.get(key) is True
                for key in ("kirish", "asosiy", "xulosa")}
    # «Faqat kirish yozilgan» degan 0-ball qoidasi AI xulosasiga tayanadi:
    # xatboshilar soni bu yerda dalil emas.
    # «Reja yo'q» / «epigraf yo'q» — rasmiy talabda kamchilik emas, izohdan olib
    # tashlanadi (model buni baribir qismlar izohiga qo'shib qo'yardi).
    for key, note in list(notes.items()):
        cleaned = re.sub(r"[^.;!?]*\b(reja|epigraf)\b[^.;!?]*(yo'q|emas|yozilmagan)[^.;!?]*[.;!?]?",
                         " ", note, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
        if cleaned != note:
            notes[key] = cleaned
    flags = []
    total = sum(scores.values())
    estimated = data.get("estimated") is True

    # 0 ball: varaq bo'sh yoki faqat kirish yozilgan. Alifbo (lotin/kirill)
    # tanlovi kamchilik emas — imlo shu alifbo qoidalari bo'yicha baholanadi.
    if words == 0:
        flags.append("blank")
    elif raw_sections.get("kirish") is True and not (
            raw_sections.get("asosiy") is True or raw_sections.get("xulosa") is True):
        flags.append("notask")
    # 2 ball: hajm, mavzu, ko'chirma.
    elif words < MIN_WORDS:
        # Rasm to'liq o'qilmagan bo'lsa, «2 ball» o'rniga qayta yuborish so'raladi.
        if from_image and words >= MIN_OCR_WORDS:
            flags.append("ocr_short")
        else:
            flags.append("short")
    elif topic and data.get("topic_match") is False:
        flags.append("offtopic")
    elif data.get("plagiarism_suspected") is True:
        flags.append("copied")

    if flags and flags[0] in ("blank", "notask"):
        total = 0
    elif flags and flags[0] != "ocr_short":
        total = 2
    # AI ba'zan xato ro'yxatida ko'rsatmasdan turib imlo/tinishga 0 qo'yadi
    # (asosan qo'lyozma OCR chiziqchalari sabab). Xato ko'rsatilmagan band 0
    # bo'lib qolmasin — bu bahoni asossiz tushirardi.
    # Faqat qo'lyozma (OCR) yo'lida: matn faylida AI 0 qo'ysa, bu haqiqiy
    # baho bo'lishi mumkin. Barcha bandlar 0 bo'lsa ham tegilmaydi (sxema
    # nusxasi) — u holat `_unscored` orqali qayta baholanadi.
    if from_image and not flags and words >= MIN_WORDS and sum(scores.values()) > 0:
        for key in ("imlo", "tinish", "qoshimchalar", "soz", "paremiya", "adabiy"):
            if scores[key] == 0 and key not in faulted:
                scores[key] = 1
        total = sum(scores.values())
    # Ko'rsatilgan xato bo'lmasa, til bandi «o'rtacha» deb 1 ga tushirilmaydi:
    # qo'lyozmada OCR xatosi ko'p, shuning uchun faqat aniqlangan xatoga ball
    # tushiriladi. «Qismlar» esa matnda uch qism haqiqatan bo'lsa 2 oladi —
    # buning uchun AI'ning «bo'limlar yo'q» degan xulosasi asos bo'lmaydi.
    if not flags and sum(scores.values()) > 0:
        if words >= MIN_WORDS and all(sections.values()) and scores["qismlar"] < 2:
            scores["qismlar"] = 2
            notes["qismlar"] = ""
        if from_image and words >= MIN_WORDS:
            for key in ("imlo", "tinish", "qoshimchalar", "soz"):
                if key not in faulted and scores[key] < 2:
                    scores[key] = 2
                    notes[key] = ""
        # «Shaxsiy fikr aniq ajratilmagan» degan izoh matnda «Mening
        # fikrimcha» bo'lsa asossiz: ikkala qarash ham, o'z munosabati ham bor.
        if (scores["qarashlar"] < 2 and _has_personal_view(text)
                and _invalid_lowering("qarashlar", notes["qarashlar"])):
            scores["qarashlar"] = 2
            notes["qarashlar"] = ""
        # Prompt talab qiladi: 1 yoki 0 faqat matndan keltirilgan parcha bilan
        # tasdiqlangan kamchilik uchun. Model esa «ba'zi joylarda...»,
        # «takrorlanadi» kabi umumiy gaplar bilan bandni tushiradi. Dalil
        # bo'lmasa band 2 bo'ladi — asossiz past ball chiqmasin.
        for key in _EVIDENCE_BANDS:
            if scores[key] >= 2:
                continue
            if (_invalid_lowering(key, notes[key])
                    or _repeat_claim_unsupported(notes[key], text)
                    or not _note_evidence(notes[key], text)):
                scores[key] = 2
                notes[key] = ""
        total = sum(scores.values())
    # Ba'zi bandlar AI javobida umuman yo'q bo'lsa, ular 1 ball bilan
    # to'ldirildi — bu taxminiy, foydalanuvchi buni bilishi kerak.
    if missing and not flags:
        estimated = True
    if estimated:
        # Taxminiy ballar hisobotda alohida ogohlantirish bilan ko'rsatiladi.
        flags.append("estimated")

    return {
        "scores": scores,
        "notes": notes,
        "script": detect_script(text),
        "total": total,
        "max_total": MAX_TOTAL,
        "scale_75": to_scale_75(total),
        "sections": sections,
        "missing_criteria": missing,
        "estimated": estimated,
        "plan_written": data.get("has_plan") is True,
        "epigraph_written": data.get("has_epigraph") is True,
        "flags": flags,
        "word_count": words,
        "min_words": MIN_WORDS,
        "errors": errors,
        "strengths": _clean_list(data.get("strengths"), 4),
        "advice": _clean_list(data.get("advice"), 4),
        "review": re.sub(r"\s+", " ", str(data.get("review") or data.get("summary") or "")).strip()[:700],
        "topic": str(topic or "").strip()[:300],
        "language": str(data.get("language") or lang)[:16],
    }


def build_prompt(text, topic="", lang="uz", retry=False, from_image=False):
    """Rasmiy mezon asosidagi tekshirish topshirig'i."""
    bands = "\n".join(f"- {key} ({band}): {name}" for band, (key, name) in
                      enumerate(CRITERIA, 1))
    retry_block = (
        "QAYTA BAHOLASH: oldingi javobda barcha bandlarga 0 qo'yilgan, bu rasmiy "
        "qoidaga zid. Matnni qayta o'qib, har bir bandga 0, 1 yoki 2 dan mos "
        "qiymat qo'ying.\n\n" if retry else ""
    )
    topic_block = (f"ESSE MAVZUSI / TOPSHIRIQ:\n\"\"\"\n{topic}\n\"\"\"\n\n"
                   if topic else
                   "ESSE MAVZUSI: berilmagan — mavzuga moslikni matnning o'zidan baholang.\n\n")
    script = detect_script(text)
    ocr_block = (
        "MATN QO'LYOZMADAN O'QILGAN (OCR): qator oxiridagi bo'g'in ko'chirish "
        "chiziqchalari, harf uzilishlari va ʼ/’/ʻ ko'rinishidagi apostrof "
        "belgilari imlo xatosi emas. Faqat yozuvchining haqiqiy imlo "
        "xatolarini ko'rsating.\n\n" if from_image else ""
    )
    script_block = (
        "ALIFBO: esse eski o'zbek (kirill) alifbosida yozilgan. Imlo va tinish "
        "belgilarini kirill alifbosidagi o'zbek tili qoidalari bo'yicha baholang; "
        "so'zlarni lotin harflariga o'girmang va alifbo tanlovini kamchilik deb "
        "hisoblamang (buning uchun ball tushirmang).\n\n" if script == "cyrillic"
        else "ALIFBO: esse lotin yozuvidagi o'zbek alifbosida yozilgan. Imlo va "
             "tinish belgilarini shu alifbo qoidalari bo'yicha baholang.\n\n"
    )
    detected, para_count = detect_sections(text, loose=from_image)
    structure_block = (
        "MATN TUZILISHI (avtomatik aniqlandi — shu ma'lumotga tayaning):\n"
        f"- xatboshilar soni: {para_count}\n"
        f"- kirish: {'bor' if detected['kirish'] else 'yoq'}\n"
        f"- asosiy qism: {'bor' if detected['asosiy'] else 'yoq'}\n"
        f"- xulosa: {'bor' if detected['xulosa'] else 'yoq'}\n"
        f"- so'zlar soni: {word_count(text)}\n\n"
    )
    return (
        "Siz O'zbekiston Bilim va malakalarni baholash agentligining ona tili va "
        "adabiyot fanidan yozma ish (esse) bo'yicha ekspertisiz. Quyidagi esseni "
        "rasmiy mezon bo'yicha tekshiring.\n\n"
        "ISH TARTIBI: avval butun matnni boshidan oxirigacha o'qib chiqing — "
        "har bir xatboshini, kirish va xulosani alohida belgilang; shundan keyingina "
        "12 ta bandni birma-bir baholang.\n\n"
        f"{structure_block}"
        "RASMIY MEZON — 12 ta band, HAR BIRIGA FAQAT 0, 1 yoki 2 ball:\n"
        f"{bands}\n\n"
        "Ball qo'yish tartibi:\n"
        "- 2 — talab to'liq bajarilgan;\n"
        "- 1 — qisman bajarilgan (ayrim kamchiliklar bor);\n"
        "- 0 — bajarilmagan.\n\n"
        "Muhim: quyidagi JSON sxemasidagi 0 lar — shunchaki namuna, ularni nusxa "
        "ko'chirmang. Har bir bandni matnga qarab baholang. Matn mavjud bo'lsa, "
        "barcha bandlarga birdan 0 qo'yish mumkin emas.\n\n"
        "12 ta bandning HAMMASI baholanadi: \"scores\" obyektida yuqoridagi 12 ta "
        "kalitning barchasi (uslub, qarashlar, dalillar, qismlar, mantiq, izchillik, "
        "imlo, tinish, qoshimchalar, soz, paremiya, adabiy) bo'lishi shart. "
        "Bittasini ham tashlab ketmang va kalit nomlarini o'zgartirmang; "
        "\"notes\" da ham shu 12 band uchun izoh yozing.\n\n"
        "Adolatli baholang: 0 faqat band umuman bajarilmagan bo'lsa qo'yiladi. "
        "Imlo bo'yicha xato ko'rsatmagan bo'lsangiz, imlo 0 bo'lmaydi; tinish "
        "belgilari to'g'ri qo'llangan bo'lsa, tinish 0 bo'lmaydi; matnda atama "
        "yoki tasviriy ifoda bo'lsa, paremiya 0 bo'lmaydi. O'rtacha, lekin "
        "yaroqli ish odatda 1 ball oladi.\n\n"
        "BALLARNI ADOLATLI QO'YING: yaxshi yozilgan esse (aniq kirish, mantiqiy "
        "asosiy qism, xulosa, dalillar va shaxsiy fikr) odatda har bir bandda 2 ball "
        "oladi. 1 ball — faqat izohda aniq aytilgan va matndan parcha bilan "
        "tasdiqlangan kamchilik bo'lsa. Xato ro'yxatida ko'rsatilmagan band uchun "
        "ballni tushirmang: imlo/tinish/qo'shimcha/so'z bo'yicha xato keltirmagan "
        "bo'lsangiz, o'sha bandga 2 qo'ying. 1 yoki 0 qo'ysangiz, izohda matndan "
        "aniq parcha keltiring; parcha keltira olmasangiz — 2 qo'ying. "
        "Tuzilma va so'zlar soni yuqorida "
        "berilgan; ularga zid xulosa yozmang (masalan «kirish yo'q», «reja yo'q»).\n\n"
        f"{retry_block}"
        f"{ocr_block}"
        f"{script_block}"
        "IMLO TEKSHIRUVI: imlo bandini to'liq ko'rib chiqing — matndagi har bir "
        "so'zning yozilishini tekshiring: harf almashinuvi, tushib qolgan yoki "
        "ortiqcha harf, qo'shimchaning noto'g'ri yozilishi, so'zning qo'shilib "
        "ketishi yoki ajralib ketishi. Har bir topilgan xatoni alohida yozing "
        "(bir xil xato bir necha joyda bo'lsa — bitta). Faqat haqiqiy xatoni "
        "ko'rsating: to'g'ri yozilgan so'zni «xato» deb yozmang.\n\n"
        "Qat'iy qoidalar: matnda yo'q xatoni o'ylab topmang; bir xil xato bir necha "
        f"joyda takrorlansa — bitta xato; quote — matndagi aniq parcha; eng ko'pi "
        f"bilan {MAX_ERRORS} ta aniq xato ko'rsatiladi.\n\n"
        "Rasmiy talablar (buzilishi ballni tushiradi):\n"
        "- esse o'zbek tilida yoziladi; lotin yoki kirill alifbosi — ikkalasi ham "
        "qabul qilinadi, alifbo tanlovi kamchilik emas;\n"
        "- uslub publitsistik (argumentli, munozarali) bo'ladi;\n"
        "- kirish, asosiy qism va xulosa bo'ladi;\n"
        "- reja va epigraf yozilmaydi — matnda bo'lsa, has_plan/has_epigraph ni true "
        "qiling va bu kamchilikni «qismlar» bandida hisobga oling.\n"
        "- matnda reja yoki epigraf YO'Q bo'lsa, bu kamchilik emas: buning uchun "
        "ballni tushirmang va izohda «reja yo'q» deb yozmang.\n\n"
        "Ba'zi bandlarni baholashda ko'p uchraydigan xato:\n"
        "- dalillar: matnda misol, fakt, raqam yoki hayotiy holat keltirilgan bo'lsa — 2; "
        "adabiyot/manba ko'rsatilishi shart emas.\n"
        "- paremiya: maqol yoki topishmoq bo'lishi shart emas; vaziyatga mos atama, "
        "ilmiy-ommabop ibora yoki tasviriy ifoda bo'lsa — 2.\n"
        "- adabiy: sheva, vulgarizm va varvarizm bo'lmasa — 2.\n"
        "- uslub: esse (fikr bildirish, munozara) ohangida yozilgan bo'lsa — 2; "
        "ilmiy maqola darajasidagi isbot talab qilinmaydi.\n"
        "- qarashlar: muqobil fikr va o'z munosabati (masalan «mening fikrimcha») "
        "bo'lsa — 2.\n\n"
        "Istisno qoidalar (o'zingiz qo'llamang, faqat hisobga oling): 100 so'zdan kam — "
        "2 ball, mavzuga mos emas — 2 ball, ko'chirilgan — 2 ball; faqat kirish "
        "yozilgan — 0 ball.\n\n"
        f"{topic_block}"
        "Javob faqat shu JSON sxemasida bo'lsin (boshqa matn yozmang):\n"
        "{\n"
        '  "scores": {"uslub": 0, "qarashlar": 0, "dalillar": 0, "qismlar": 0, '
        '"mantiq": 0, "izchillik": 0, "imlo": 0, "tinish": 0, "qoshimchalar": 0, '
        '"soz": 0, "paremiya": 0, "adabiy": 0},\n'
        '  "notes": {"uslub": "qisqa asos", "qarashlar": "...", "dalillar": "...", '
        '"qismlar": "...", "mantiq": "...", "izchillik": "...", "imlo": "...", '
        '"tinish": "...", "qoshimchalar": "...", "soz": "...", "paremiya": "...", '
        '"adabiy": "..."},\n'
        '  "sections": {"kirish": true, "asosiy": true, "xulosa": true},\n'
        '  "has_plan": false, "has_epigraph": false,\n'
        '  "topic_match": true,\n'
        '  "plagiarism_suspected": false,\n'
        '  "errors": [{"quote": "matndan parcha", "fix": "to\'g\'ri varianti", '
        '"type": "imlo|tinish|soz|qoshimcha|uslub", "rule": "qisqa qoida"}],\n'
        '  "strengths": ["..."],\n'
        '  "advice": ["..."],\n'
        '  "review": "3-5 jumlalik taqriz: umumiy xulosa va eng muhim tavsiya"\n'
        "}\n\n"
        f'ESSE MATNI:\n"""\n{text}\n"""'
    )


async def _request_report(body, topic, lang, retry=False, from_image=False):
    """AI'dan JSON hisobot so'raydi; xato bo'lsa None.

    Javob uzilib qolishi yoki provayder almashishi mumkin, shuning uchun bitta
    muvaffaqiyatsiz urinishdan keyin hisobot yana bir marta so'raladi.
    """
    import ai_api
    system = (
        "Siz ona tili va adabiyot fanidan yozma ishni baholovchi ekspertsiz. "
        "Faqat JSON obyekt qaytarasiz, ballarni 0, 1 yoki 2 dan boshqa qiymatda "
        "bermaysiz."
    )
    prompt = build_prompt(body, topic, lang, retry, from_image=from_image)
    raw = ""
    for attempt in range(2):
        try:
            async with _gate("analyze", ANALYZE_CONCURRENCY):
                raw = await ai_api._chat_complete(
                    prompt, system=system, max_tokens=4000 if attempt else 3000,
                    temperature=0.35 if retry else 0.2,
                    frequency_penalty=0.2, presence_penalty=0.0)
        except Exception as exc:
            print(f"[check] tahlil xatosi: {type(exc).__name__}: {exc}", flush=True)
            continue
        data = _parse_json_object(raw)
        if data:
            return data
        print(f"[check] JSON o'qilmadi (urinish {attempt + 1}, {len(str(raw))} belgi): "
              f"{str(raw)[:200]}", flush=True)
        if attempt == 0 and not str(raw).strip():
            # Provayder butunlay bo'sh javob qaytardi: ikkinchi to'liq so'rov ham
            # behuda ketadi, kvotani tejash uchun qisqa so'rovga o'tamiz.
            print("[check] bo'sh javob — qisqa baholashga o'tildi", flush=True)
            break
        if attempt == 0:
            # Provayder xatosini keyingi urinishda o'tkazib yubormaslik uchun
            # qaysi sabab qaytgani logda ko'rinsin.
            last = getattr(ai_api, "LAST_ERROR", None)
            if last:
                print(f"[check] AI sababi: {last}", flush=True)

    # Zaif model to'liq hisobotni (izohlar, xatolar, taqriz) yozib tugata
    # olmaydi va javob yarmida uziladi. Ballar esa qisqa javobda ham yetib
    # keladi, shuning uchun faqat baholarni so'rab ko'ramiz.
    compact = (
        "Faqat JSON qaytaring, izoh va boshqa matn yozmang."
        " Ballarni 0, 1 yoki 2 qilib bering; 12 ta bandning hammasini yozing.\n"
        '{"scores": {"uslub": 0, "qarashlar": 0, "dalillar": 0, "qismlar": 0, '
        '"mantiq": 0, "izchillik": 0, "imlo": 0, "tinish": 0, "qoshimchalar": 0, '
        '"soz": 0, "paremiya": 0, "adabiy": 0}, '
        '"sections": {"kirish": true, "asosiy": true, "xulosa": true}, '
        '"topic_match": true, "plagiarism_suspected": false, '
        '"has_plan": false, "has_epigraph": false}\n\n'
        f"Mavzu: {topic or 'ko\'rsatilmagan'}\nESSE MATNI:\n" + body[:8000]
    )
    try:
        async with _gate("analyze", ANALYZE_CONCURRENCY):
            raw = await ai_api._chat_complete(compact, system=system, max_tokens=700,
                                              temperature=0.1)
        data = _parse_json_object(raw)
        if data:
            print("[check] qisqa (faqat ballar) javob ishlatildi", flush=True)
            return data
    except Exception as exc:
        print(f"[check] qisqa baholash xatosi: {type(exc).__name__}: {exc}", flush=True)
    return None


def _merge_reports(first, second):
    """Ikkinchi javobdan birinchisida yo'q bandlarni to'ldiradi."""
    scores = _map_scores(first.get("scores"))
    for key, value in _map_scores((second or {}).get("scores")).items():
        scores.setdefault(key, value)
    notes = {}
    for source in (first, second):
        raw = (source or {}).get("notes")
        if not isinstance(raw, dict):
            continue
        for raw_key, note in raw.items():
            key = _criterion_key(raw_key)
            if key and str(note or "").strip() and key not in notes:
                notes[key] = note
    merged = dict(first)
    merged["scores"] = scores
    merged["notes"] = notes
    return merged


def _unscored(report):
    """Matn yaroqli, lekin AI barcha bandlarga 0 qo'ygan — ishonchsiz natija."""
    return (int(report.get("total") or 0) == 0
            and not report.get("flags")
            and int(report.get("word_count") or 0) >= MIN_WORDS)


def not_graded(body, lang="uz", topic="", reason="unavailable"):
    """AI baholay olmagan holat: yolg'on ball o'rniga halol «baholab bo'lmadi».

    Ilgari bu yerda matn tahliliga asoslangan taxminiy ballar qo'yilardi va
    yaroqli esse 12/24 (yoki hajm qoidasi bilan 2/24) bo'lib ko'rinardi — bu
    foydalanuvchini chalg'itardi. Endi ball umuman ko'rsatilmaydi.
    """
    return {
        "not_graded": True,
        "reason": str(reason or "unavailable"),
        "word_count": word_count(body),
        "min_words": MIN_WORDS,
        "topic": str(topic or "").strip()[:300],
        "language": str(lang or "uz")[:16],
    }


async def analyze_essay(text, lang="uz", topic="", from_image=False):
    """Esseni 12 band bo'yicha tekshiradi; AI ishlamasa «baholab bo'lmadi». """
    body = str(text or "").strip()
    if len(body) < 40:
        return None
    body = body[:MAX_CHARS]
    data = await _request_report(body, topic, lang, from_image=from_image)
    if not data:
        print("[check] AI hisobot bermadi — halol «baholab bo'lmadi» qaytadi", flush=True)
        return not_graded(body, lang, topic, "unavailable")
    report = normalize_report(data, body, lang, topic, from_image=from_image)
    # 12 ta mezonning barchasi baholanishi shart. AI ba'zi bandlarni tashlab
    # ketsa (uzilgan JSON, qisqa javob), ular 0 bo'lib qolmasligi uchun faqat
    # o'sha bandlar qayta so'raladi.
    blocking = [flag for flag in report.get("flags") or [] if flag != "estimated"]
    if report.get("missing_criteria") and not blocking:
        print(f"[check] baholanmagan bandlar: {', '.join(report['missing_criteria'])} — "
              "qayta so'raladi", flush=True)
        retry_data = await _request_report(body, topic, lang, retry=True,
                                          from_image=from_image)
        if retry_data:
            merged = normalize_report(_merge_reports(data, retry_data), body, lang, topic,
                                      from_image=from_image)
            if len(merged.get("missing_criteria") or []) < len(report["missing_criteria"]):
                report = merged
    if _unscored(report):
        # 100+ so'zli lotin matniga barcha bandlar 0 — model sxemadagi nollarni
        # ko'chirgan bo'lishi mumkin. Bir marta qayta so'raymiz.
        print("[check] barcha bandlar 0 — qayta baholash so'raladi", flush=True)
        retry_data = await _request_report(body, topic, lang, retry=True,
                                          from_image=from_image)
        if retry_data:
            retry_report = normalize_report(retry_data, body, lang, topic,
                                            from_image=from_image)
            if retry_report["total"] > report["total"]:
                report = retry_report
        if _unscored(report):
            print("[check] AI baholay olmadi — ball qo'yilmaydi", flush=True)
            return not_graded(body, lang, topic, "no_scores")
    return report


# ===== Hisobot matni (Telegram uchun oddiy matn) =====
def not_graded_text(report, lang="uz"):
    """AI baholay olmagan holat uchun halol xabar (ball ko'rsatilmaydi)."""
    info = labels(lang)
    words = int(report.get("word_count") or 0)
    lines = [
        info["title"], "",
        f"⚠️ {info['not_graded_title']}",
        info["flags"]["not_graded"], "",
        f"📄 {info['words']}: {words} ({info['required']})",
    ]
    if report.get("topic"):
        lines.append(f"🎯 Mavzu: {report['topic']}")
    lines.extend(["", f"♻️ {info['not_graded_retry']}"])
    return "\n".join(lines)


def format_report(report, lang="uz"):
    info = labels(lang)
    if report.get("not_graded"):
        return not_graded_text(report, lang)
    percent = int(round(100.0 * report["total"] / MAX_TOTAL))
    lines = [info["title"], ""]
    lines.append(f"📊 {info['total']}: {report['total']}/{MAX_TOTAL} ball ({percent}%)")
    lines.append(f"📐 {info['scale']}: {report.get('scale_75', to_scale_75(report['total']))}/{SCALE_MAX} ball")
    lines.append(f"📄 {info['words']}: {report['word_count']} ({info['required']})")
    if report.get("topic"):
        lines.append(f"🎯 Mavzu: {report['topic']}")
    sections = report.get("sections") or {}
    if sections:
        marks = " · ".join(
            f"{info['sections'][key]} {'✅' if sections.get(key) else '❌'}"
            for key in ("kirish", "asosiy", "xulosa"))
        lines.append(f"🧱 {info['structure']}: {marks}")
    if report.get("plan_written"):
        lines.append(f"⚠️ {info['plan_written']}")
    if report.get("epigraph_written"):
        lines.append(f"⚠️ {info['epigraph_written']}")
    for flag in report.get("flags") or []:
        text = info["flags"].get(flag)
        if text:
            lines.append(f"⚠️ {text}")
    lines.append("")
    lines.append(f"📌 {info['criteria']}:")
    for band, key in enumerate(CRITERIA_KEYS, 1):
        lines.append(f"   {band}. {info['crit'][key]} — {report['scores'][key]}/2")
        note = (report.get("notes") or {}).get(key)
        if note:
            lines.append(f"      {note}")
    lines.append("")
    if report["errors"]:
        counts = {}
        for item in report["errors"]:
            counts[item["type"]] = counts.get(item["type"], 0) + 1
        summary = ", ".join(f"{name} — {count}" for name, count in counts.items())
        lines.append(f"❌ {info['errors']} ({len(report['errors'])}): {summary}")
        for index, item in enumerate(report["errors"], 1):
            head = f"   {index}. «{item['quote']}»" if item["quote"] else f"   {index}."
            if item["fix"]:
                head += f" → «{item['fix']}»"
            lines.append(head)
            detail = " / ".join(x for x in (item["type"], item["rule"]) if x)
            if detail:
                lines.append(f"      {detail}")
    else:
        lines.append(info["no_errors"])
    if report["strengths"]:
        lines.append("")
        lines.append(f"✅ {info['strengths']}:")
        lines.extend(f"   • {item}" for item in report["strengths"])
    if report["advice"]:
        lines.append("")
        lines.append(f"💡 {info['advice']}:")
        lines.extend(f"   • {item}" for item in report["advice"])
    if report["review"]:
        lines.append("")
        lines.append(f"🧾 {info['review']}: {report['review']}")
    return "\n".join(lines)


def criteria_payload(report, lang="uz"):
    """12 band ro'yxati — Mini App va boshqa interfeyslar uchun."""
    info = labels(lang)
    items = []
    for band, key in enumerate(CRITERIA_KEYS, 1):
        items.append({
            "band": band,
            "key": key,
            "name": info["crit"].get(key, key),
            "score": int((report.get("scores") or {}).get(key, 0)),
            "max": MAX_PER_BAND,
            "note": str((report.get("notes") or {}).get(key) or ""),
        })
    return items


def report_payload(report, lang="uz"):
    """Hisobotni Mini App uchun to'liq JSON lug'atiga aylantiradi."""
    info = labels(lang)
    total = int(report.get("total") or 0)
    return {
        "total": total,
        "max_total": MAX_TOTAL,
        "scale_75": int(report.get("scale_75") or to_scale_75(total)),
        "max_scale": SCALE_MAX,
        "percent": int(round(100.0 * total / MAX_TOTAL)),
        "word_count": int(report.get("word_count") or 0),
        "min_words": MIN_WORDS,
        "topic": str(report.get("topic") or ""),
        "flags": [{"key": key, "text": info["flags"].get(key, key)}
                  for key in report.get("flags") or []],
        "sections": {key: bool((report.get("sections") or {}).get(key))
                     for key in ("kirish", "asosiy", "xulosa")},
        "plan_written": bool(report.get("plan_written")),
        "epigraph_written": bool(report.get("epigraph_written")),
        "criteria": criteria_payload(report, lang),
        "missing_criteria": list(report.get("missing_criteria") or []),
        "estimated": bool(report.get("estimated")),
        "errors": list(report.get("errors") or []),
        "strengths": list(report.get("strengths") or []),
        "advice": list(report.get("advice") or []),
        "review": str(report.get("review") or ""),
        "not_graded": bool(report.get("not_graded")),
        "labels": {
            "total": info["total"],
            "scale": info["scale"],
            "words": info["words"],
            "required": info["required"],
            "structure": info["structure"],
            "sections": info["sections"],
            "criteria": info["criteria"],
            "errors": info["errors"],
            "no_errors": info["no_errors"],
            "strengths": info["strengths"],
            "advice": info["advice"],
            "review": info["review"],
            "plan_written": info["plan_written"],
            "epigraph_written": info["epigraph_written"],
            "not_graded": info["not_graded_title"],
            "not_graded_text": info["flags"]["not_graded"],
        },
    }
