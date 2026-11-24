"""Yozma ishni (esse) Milliy sertifikat mezoni bo'yicha tekshirish.

Asos: Bilim va malakalarni baholash agentligining «Ona tili va adabiyot fanidan
yozma ishni baholashga qo'yiladigan talablar» hujjati (uzbmb.uz). Esseda 12 ta
band bor, har biri 0 dan 2 ballgacha — jami 24 ball. Hujjatdagi qat'iy qoidalar
ham hisobga olinadi:

* mavzuga mos bo'lmagan ish — 2 ball;
* 100 so'zdan kam ish — 2 ball;
* boshqa manbadan ko'chirilgan ish — 2 ball;
* faqat kirish qismi yozilgani yoki to'liq kirill alifbosida yozilgani — 0 ball.

Foydalanuvchi DOCX/TXT fayl, rasm yoki matn yuboradi; rasm Gemini vision orqali
o'qiladi. Hisobotda har bir band bo'yicha ball, aniq xatolar va taqriz qaytadi.
"""
import base64
import io
import json
import re

import aiohttp

import ai_pool

MAX_CHARS = 15000          # bir marta tekshiriladigan matn hajmi
MAX_ERRORS = 12
MAX_IMAGE_SIDE = 1600
MAX_PER_BAND = 2
MAX_TOTAL = 24
MIN_WORDS = 100

# Rasmiy mezon: 12 band, har biri 0..2. Kalit — hisobot va JSON uchun.
CRITERIA = (
    ("uslub", "Publitsistik (ilmiy-ommabop) uslubda yozilganlik"),
    ("qarashlar", "Vaziyat yuzasidan ikkala qarash va shaxsiy qarash yoritilgani"),
    ("dalillar", "Qarashlarning dalillar bilan asoslangani"),
    ("qismlar", "Matn uch qismdan iboratligi: kirish, asosiy qism, xulosa"),
    ("mantiq", "Mantiqiy qurilish: gap bo'laklari, sintaktik birliklar, xatboshilar"),
    ("izchillik", "Mazmuniy-mantiqiy izchillik, fikr takrorlanmasligi"),
    ("imlo", "Imlo qoidalariga rioya (lotin yozuvidagi o'zbek alifbosi)"),
    ("tinish", "Tinish belgilarining to'g'ri qo'llanishi"),
    ("qoshimchalar", "So'z va shakl yasovchi qo'shimchalarning o'rinli qo'llanishi"),
    ("soz", "So'z qo'llash: leksik birliklarning o'rinli tanlanishi"),
    ("paremiya", "Paremiologizmlar va vaziyatga mos atamalardan o'rinli foydalanish"),
    ("adabiy", "Adabiy til me'yorlari: sheva, vulgarizm, varvarizm yo'qligi"),
)

CRITERIA_KEYS = tuple(key for key, _ in CRITERIA)

VISION_MODELS = ("gemini-2.5-flash", "gemini-flash-lite-latest",
                 "gemini-3.5-flash-lite", "gemini-2.0-flash")

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
        "flags": {
            "short": "Ish hajmi 100 so'zdan kam — rasmiy qoidaga ko'ra 2 ball qo'yiladi.",
            "offtopic": "Ish mavzuga mos emas — rasmiy qoidaga ko'ra 2 ball qo'yiladi.",
            "copied": "Ish boshqa manbadan ko'chirilgan deb baholandi — 2 ball.",
            "notask": "Faqat kirish qismi yozilgan — topshiriq bajarilmagan, 0 ball.",
            "cyrillic": "Ish to'liq kirill alifbosida — tekshirilmaydi, 0 ball.",
        },
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
        "flags": {
            "short": "Объём меньше 100 слов — по официальному правилу ставится 2 балла.",
            "offtopic": "Работа не соответствует теме — по официальному правилу 2 балла.",
            "copied": "Работа оценена как списанная — 2 балла.",
            "notask": "Написано только вступление — задание не выполнено, 0 баллов.",
            "cyrillic": "Работа полностью на кириллице — не проверяется, 0 баллов.",
        },
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
        "flags": {
            "short": "Fewer than 100 words — the official rule gives 2 points.",
            "offtopic": "The work is off topic — the official rule gives 2 points.",
            "copied": "The work was judged copied — 2 points.",
            "notask": "Only the introduction is written — task not done, 0 points.",
            "cyrillic": "The work is fully in Cyrillic — not checked, 0 points.",
        },
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


def cyrillic_ratio(text):
    """Matndagi harflarning qancha qismi kirill ekani (0..1)."""
    cyrillic = len(_CYRILLIC_RE.findall(str(text or "")))
    latin = len(_LATIN_RE.findall(str(text or "")))
    total = cyrillic + latin
    return (cyrillic / float(total)) if total else 0.0


# ===== Rasmdan matn (OCR) — Gemini vision =====
def prepare_image(data):
    """Rasmni kichraytirib JPEG'ga o'giradi (yuklash tez bo'lsin)."""
    try:
        from PIL import Image
        with Image.open(io.BytesIO(data)) as source:
            source.load()
            image = source.convert("RGB")
            if max(image.size) > MAX_IMAGE_SIDE:
                ratio = MAX_IMAGE_SIDE / float(max(image.size))
                size = (max(1, int(image.width * ratio)), max(1, int(image.height * ratio)))
                image = image.resize(size, Image.LANCZOS)
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=88, optimize=True)
        return buffer.getvalue(), "image/jpeg"
    except Exception as exc:
        print(f"[check] rasm tayyorlanmadi: {type(exc).__name__}: {exc}", flush=True)
        return data, "image/jpeg"


async def _vision_call(row, model, image_data, mime, prompt):
    base = str(row["base_url"] or ai_pool.PROVIDER_BASE.get("google", "")).rstrip("/")
    key = str(row["api_key"] or "")
    if not base or not key:
        return ""
    url = f"{base}/models/{model}:generateContent?key={key}"
    payload = {
        "contents": [{"role": "user", "parts": [
            {"text": prompt},
            {"inlineData": {"mimeType": mime,
                            "data": base64.b64encode(image_data).decode("ascii")}},
        ]}],
        "generationConfig": {"temperature": 0, "maxOutputTokens": 4096},
    }
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120)) as session:
            async with session.post(url, json=payload) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    print(f"[check] vision {model}: HTTP {resp.status}: {str(body)[:180]}", flush=True)
                    return ""
                data = await resp.json(content_type=None)
        parts = (((data.get("candidates") or [{}])[0].get("content") or {}).get("parts") or [])
        return "".join(str(part.get("text") or "") for part in parts).strip()
    except Exception as exc:
        print(f"[check] vision xatosi: {type(exc).__name__}: {exc}", flush=True)
        return ""


async def ocr_image(image_data, lang="uz"):
    """Rasmdagi matnni o'qib beradi; Google kaliti bo'lmasa bo'sh satr."""
    if not image_data:
        return ""
    row = None
    try:
        for item in ai_pool.keys(active_only=True):
            if str(item["provider"] or "") == "google" or \
                    "generativelanguage" in str(item["base_url"] or ""):
                row = item
                break
    except Exception as exc:
        print(f"[check] AI kalitlari olinmadi: {exc}", flush=True)
        return ""
    if row is None:
        return ""
    models = [m.strip() for m in str(row["models"] or "").split(",") if m.strip()]
    if not models:
        models = list(VISION_MODELS)
    data, mime = prepare_image(image_data)
    prompt = (
        "Bu rasmda qo'lyozma yoki bosma matn bor. Rasmdagi matnni to'liq, "
        "hech narsa qo'shmasdan va izohsiz yozib bering. Qatorlarni va "
        "xatboshilarni saqlang. Agar rasmda matn bo'lmasa, bo'sh javob bering."
    )
    for model in models[:4]:
        text = await _vision_call(row, model, data, mime, prompt)
        if text:
            return text
    return ""


# ===== AI tahlili =====
def _parse_json_object(text):
    raw = str(text or "").strip()
    if not raw:
        return None
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, flags=re.DOTALL)
    if fenced:
        raw = fenced.group(1)
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(raw[start:end + 1])
    except Exception:
        return None
    return data if isinstance(data, dict) else None


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


def band_scores(raw_scores):
    """Har bir bandni 0..2 oralig'iga keltiradi."""
    scores = {}
    for key in CRITERIA_KEYS:
        try:
            value = int(round(float((raw_scores or {}).get(key, 0))))
        except (TypeError, ValueError):
            value = 0
        scores[key] = max(0, min(MAX_PER_BAND, value))
    return scores


def normalize_report(data, text, lang="uz", topic=""):
    """AI javobini rasmiy qoidalar bilan tekshirilgan hisobotga aylantiradi."""
    scores = band_scores(data.get("scores"))
    notes = {}
    raw_notes = data.get("notes") if isinstance(data.get("notes"), dict) else {}
    for key in CRITERIA_KEYS:
        note = str(raw_notes.get(key) or "").strip()
        notes[key] = re.sub(r"\s+", " ", note)[:200]

    errors = []
    for item in (data.get("errors") or [])[:MAX_ERRORS]:
        if not isinstance(item, dict):
            continue
        quote = str(item.get("quote") or "").strip()[:160]
        fix = str(item.get("fix") or "").strip()[:160]
        if not quote and not fix:
            continue
        errors.append({
            "quote": quote,
            "fix": fix,
            "type": str(item.get("type") or "imlo").strip().lower()[:24],
            "rule": str(item.get("rule") or "").strip()[:180],
        })

    words = word_count(text)
    sections = data.get("sections") if isinstance(data.get("sections"), dict) else {}
    flags = []
    total = sum(scores.values())

    # 0 ball: topshiriq bajarilmagan yoki to'liq kirill alifbosida.
    if sections and not (sections.get("asosiy") or sections.get("xulosa")):
        flags.append("notask")
    elif cyrillic_ratio(text) >= 0.6:
        flags.append("cyrillic")
    # 2 ball: hajm, mavzu, ko'chirma.
    elif words < MIN_WORDS:
        flags.append("short")
    elif topic and data.get("topic_match") is False:
        flags.append("offtopic")
    elif data.get("plagiarism_suspected") is True:
        flags.append("copied")

    if "notask" in flags or "cyrillic" in flags:
        total = 0
    elif flags:
        total = 2

    return {
        "scores": scores,
        "notes": notes,
        "total": total,
        "max_total": MAX_TOTAL,
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


def build_prompt(text, topic="", lang="uz"):
    """Rasmiy mezon asosidagi tekshirish topshirig'i."""
    bands = "\n".join(f"- {key} ({band}): {name}" for band, (key, name) in
                      enumerate(CRITERIA, 1))
    topic_block = (f"ESSE MAVZUSI / TOPSHIRIQ:\n\"\"\"\n{topic}\n\"\"\"\n\n"
                   if topic else
                   "ESSE MAVZUSI: berilmagan — mavzuga moslikni matnning o'zidan baholang.\n\n")
    return (
        "Siz O'zbekiston Bilim va malakalarni baholash agentligining ona tili va "
        "adabiyot fanidan yozma ish (esse) bo'yicha ekspertisiz. Quyidagi esseni "
        "rasmiy mezon bo'yicha tekshiring.\n\n"
        "RASMIY MEZON — 12 ta band, HAR BIRIGA FAQAT 0, 1 yoki 2 ball:\n"
        f"{bands}\n\n"
        "Ball qo'yish tartibi:\n"
        "- 2 — talab to'liq bajarilgan;\n"
        "- 1 — qisman bajarilgan (ayrim kamchiliklar bor);\n"
        "- 0 — bajarilmagan.\n\n"
        "Qat'iy qoidalar: matnda yo'q xatoni o'ylab topmang; bir xil xato bir necha "
        "joyda takrorlansa — bitta xato; quote — matndagi aniq parcha; imlo va tinish "
        "bo'yicha o'zbek lotin alifbosi qoidalariga tayaning.\n\n"
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


async def analyze_essay(text, lang="uz", topic=""):
    """Esseни 12 band bo'yicha tekshiradi. AI ishlamasa None qaytaradi."""
    import ai_api
    body = str(text or "").strip()
    if len(body) < 40:
        return None
    body = body[:MAX_CHARS]
    system = (
        "Siz ona tili va adabiyot fanidan yozma ishni baholovchi ekspertsiz. "
        "Faqat JSON obyekt qaytarasiz, ballarni 0, 1 yoki 2 dan boshqa qiymatda "
        "bermaysiz."
    )
    try:
        raw = await ai_api._chat_complete(
            build_prompt(body, topic, lang), system=system, max_tokens=3000,
            temperature=0.2, frequency_penalty=0.2, presence_penalty=0.0)
    except Exception as exc:
        print(f"[check] tahlil xatosi: {type(exc).__name__}: {exc}", flush=True)
        return None
    data = _parse_json_object(raw)
    if not data:
        print(f"[check] JSON o'qilmadi: {str(raw)[:200]}", flush=True)
        return None
    return normalize_report(data, body, lang, topic)


# ===== Hisobot matni (Telegram uchun oddiy matn) =====
def format_report(report, lang="uz"):
    info = labels(lang)
    percent = int(round(100.0 * report["total"] / MAX_TOTAL))
    lines = [info["title"], ""]
    lines.append(f"📊 {info['total']}: {report['total']}/{MAX_TOTAL} ball ({percent}%)")
    lines.append(f"📄 {info['words']}: {report['word_count']} ({info['required']})")
    if report.get("topic"):
        lines.append(f"🎯 Mavzu: {report['topic']}")
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
