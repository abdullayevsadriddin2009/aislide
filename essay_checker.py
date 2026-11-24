"""Yozma ishni (esse, insho, referat) mezon bo'yicha tekshirish.

Foydalanuvchi DOCX/TXT fayl, rasm yoki oddiy matn yuboradi. Matn ajratib
olinadi (rasm — Gemini vision orqali o'qiladi), AI uni imlo, grammatika,
tinish belgilari, uslub, tuzilma, mazmun va hajm mezonlari bo'yicha tahlil
qiladi; natija ballar, aniq xatolar va maslahatlar bilan qaytadi.
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

# Mezonlar va ularning maksimal ballari (jami 100).
CRITERIA = (
    ("imlo", 25),
    ("grammatika", 20),
    ("tinish", 15),
    ("uslub", 15),
    ("tuzilma", 10),
    ("mazmun", 10),
    ("hajm", 5),
)

VISION_MODELS = ("gemini-2.5-flash", "gemini-flash-lite-latest",
                 "gemini-3.5-flash-lite", "gemini-2.0-flash")

_LABELS = {
    "uz": {
        "title": "📝 Yozma ish tekshiruvi",
        "total": "Umumiy ball",
        "words": "So'zlar",
        "criteria": "Mezonlar",
        "errors": "Topilgan xatolar",
        "no_errors": "✅ Imlo va grammatik xatolar topilmadi.",
        "strengths": "Kuchli tomonlar",
        "advice": "Maslahatlar",
        "summary": "Xulosa",
        "crit": {"imlo": "Imlo", "grammatika": "Grammatika", "tinish": "Tinish belgilari",
                 "uslub": "Uslub va so'z boyligi", "tuzilma": "Tuzilma",
                 "mazmun": "Mazmun va dalillar", "hajm": "Hajm va talab"},
        "grades": {"alo": "a'lo", "yaxshi": "yaxshi", "qoniqarli": "qoniqarli",
                   "qoniqarsiz": "qoniqarsiz"},
    },
    "ru": {
        "title": "📝 Проверка письменной работы",
        "total": "Общий балл",
        "words": "Слов",
        "criteria": "Критерии",
        "errors": "Найденные ошибки",
        "no_errors": "✅ Орфографических и грамматических ошибок не найдено.",
        "strengths": "Сильные стороны",
        "advice": "Рекомендации",
        "summary": "Заключение",
        "crit": {"imlo": "Орфография", "grammatika": "Грамматика", "tinish": "Пунктуация",
                 "uslub": "Стиль и лексика", "tuzilma": "Структура",
                 "mazmun": "Содержание и аргументы", "hajm": "Объём и требования"},
        "grades": {"alo": "отлично", "yaxshi": "хорошо", "qoniqarli": "удовлетворительно",
                   "qoniqarsiz": "неудовлетворительно"},
    },
    "en": {
        "title": "📝 Written work review",
        "total": "Overall score",
        "words": "Words",
        "criteria": "Criteria",
        "errors": "Issues found",
        "no_errors": "✅ No spelling or grammar issues found.",
        "strengths": "Strengths",
        "advice": "Recommendations",
        "summary": "Conclusion",
        "crit": {"imlo": "Spelling", "gramatika": "Grammar", "tinish": "Punctuation",
                 "uslub": "Style and vocabulary", "tuzilma": "Structure",
                 "mazmun": "Content and evidence", "hajm": "Length and requirements"},
        "grades": {"alo": "excellent", "yaxshi": "good", "qoniqarli": "satisfactory",
                   "qoniqarsiz": "unsatisfactory"},
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


def word_count(text):
    return len(_WORD_RE.findall(str(text or "")))


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
    """Rasmdaqi matnni o'qib beradi; Google kaliti bo'lmasa bo'sh satr."""
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
        "hech narsa qo'shmasdan va izohsiz yozib bering. Qatorlarni saqlang. "
        "Agar rasmda matn bo'lmasa, bo'sh javob bering."
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


def _grade(total, lang):
    names = labels(lang)["grades"]
    if total >= 86:
        return names["alo"]
    if total >= 71:
        return names["yaxshi"]
    if total >= 56:
        return names["qoniqarli"]
    return names["qoniqarsiz"]


def _clean_list(values, limit=6, size=200):
    out = []
    for value in values or []:
        if isinstance(value, dict):
            value = value.get("text") or value.get("comment") or ""
        text = str(value or "").strip()
        if text:
            out.append(text[:size])
        if len(out) >= limit:
            break
    return out


def normalize_report(data, text, lang="uz"):
    """AI javobini tekshirilgan, chegaralangan hisobotga aylantiradi."""
    raw_scores = data.get("scores") if isinstance(data.get("scores"), dict) else {}
    scores = {}
    for key, maximum in CRITERIA:
        try:
            value = int(float(raw_scores.get(key, 0)))
        except (TypeError, ValueError):
            value = 0
        scores[key] = max(0, min(maximum, value))
    total = sum(scores.values())
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
            "type": str(item.get("type") or "imlo").strip().lower()[:32],
            "rule": str(item.get("rule") or "").strip()[:180],
        })
    return {
        "scores": scores,
        "total": total,
        "grade": _grade(total, lang),
        "word_count": word_count(text),
        "errors": errors,
        "strengths": _clean_list(data.get("strengths"), 4),
        "advice": _clean_list(data.get("advice"), 4),
        "summary": str(data.get("summary") or "").strip()[:600],
        "language": str(data.get("language") or lang)[:16],
    }


async def analyze_essay(text, lang="uz"):
    """Matnni mezonlar bo'yicha tekshiradi. AI ishlamasa None qaytaradi."""
    import ai_api
    body = str(text or "").strip()
    if len(body) < 40:
        return None
    body = body[:MAX_CHARS]
    info = labels(lang)
    system = (
        "Siz o'zbek tili va adabiyotidan tajribali o'qituvchi, imlo va uslub "
        "bo'yicha ekspertsiz. Yozma ishni faqat JSON obyekt ko'rinishida tahlil "
        "qilasiz va boshqa hech qanday matn yozmaysiz."
    )
    criteria_lines = "\n".join(
        f"- {key}: 0..{maximum} ({info['crit'][key]})" for key, maximum in CRITERIA)
    prompt = (
        "Quyidagi yozma ishni tekshiring.\n\n"
        f"MEZONLAR (har biri uchun ball):\n{criteria_lines}\n\n"
        "Javob faqat shu JSON sxemasida bo'lsin:\n"
        "{\n"
        '  "language": "matn tili (uz/ru/en/...)",\n'
        '  "scores": {"imlo": 0, "grammatika": 0, "tinish": 0, "uslub": 0, '
        '"tuzilma": 0, "mazmun": 0, "hajm": 0},\n'
        '  "errors": [{"quote": "matndan aynan parcha", "fix": "to\'g\'ri varianti", '
        '"type": "imlo|grammatika|tinish|uslub", "rule": "qisqa qoida"}],\n'
        '  "strengths": ["..."],\n'
        '  "advice": ["..."],\n'
        '  "summary": "2-3 jumlalik xulosa"\n'
        "}\n\n"
        "Qoidalar: matnda yo'q xatoni o'ylab topmang; quote — matndagi aniq parcha; "
        "xatolar ko'pi bilan 15 ta; ballarni matnga qarab xolis qo'ying; "
        "imlo xatolarida o'zbek lotin imlo qoidalariga tayaning.\n\n"
        f'MATN:\n"""\n{body}\n"""'
    )
    try:
        raw = await ai_api._chat_complete(
            prompt, system=system, max_tokens=3000, temperature=0.2,
            frequency_penalty=0.2, presence_penalty=0.0)
    except Exception as exc:
        print(f"[check] tahlil xatosi: {type(exc).__name__}: {exc}", flush=True)
        return None
    data = _parse_json_object(raw)
    if not data:
        print(f"[check] JSON o'qilmadi: {str(raw)[:200]}", flush=True)
        return None
    return normalize_report(data, body, lang)


# ===== Hisobot matni (Telegram uchun oddiy matn) =====
def format_report(report, lang="uz"):
    info = labels(lang)
    lines = [info["title"], ""]
    lines.append(f"📊 {info['total']}: {report['total']}/100 — {report['grade']}")
    lines.append(f"📄 {info['words']}: {report['word_count']}")
    lines.append("")
    lines.append(f"📌 {info['criteria']}:")
    for key, maximum in CRITERIA:
        lines.append(f"   • {info['crit'][key]}: {report['scores'][key]}/{maximum}")
    lines.append("")
    if report["errors"]:
        lines.append(f"❌ {info['errors']} ({len(report['errors'])}):")
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
    if report["summary"]:
        lines.append("")
        lines.append(f"📝 {info['summary']}: {report['summary']}")
    return "\n".join(lines)
