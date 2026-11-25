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
import asyncio
import base64
import io
import json
import re
import time

import aiohttp

import ai_pool

MAX_CHARS = 15000          # bir marta tekshiriladigan matn hajmi
MAX_ERRORS = 20
MAX_IMAGE_SIDE = 2200      # qo'lyozma ingichka: kichik rasmda harflar yo'qoladi
MAX_PER_BAND = 2
MAX_TOTAL = 24
MIN_WORDS = 100
MIN_OCR_WORDS = 25         # bundan kam o'qilgan rasm — to'liq o'qilmagan bo'lishi mumkin
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
    ("imlo", "Imlo qoidalariga rioya (lotin yozuvidagi o'zbek alifbosi)"),
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
            "cyrillic": "Ish to'liq kirill alifbosida — tekshirilmaydi, 0 ball.",
            "estimated": "AI to'liq baholay olmadi; ballar matn tahlili asosida taxminiy qo'yildi. Qayta tekshirib ko'ring.",
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
            "cyrillic": "Работа полностью на кириллице — не проверяется, 0 баллов.",
            "estimated": "AI не смог полностью оценить работу; баллы выставлены приблизительно. Проверьте ещё раз.",
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
            "cyrillic": "The work is fully in Cyrillic — not checked, 0 points.",
            "estimated": "The AI could not grade the whole work; the scores are approximate. Please check it again.",
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
OCR_PROMPT = (
    "Bu rasmda qo'lyozma yoki bosma matn (o'quvchi daftari yoki varaq) bor. "
    "Sahifadagi BARCHA matnni to'liq va tartib bilan yozib bering.\n"
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
    """Rasmni kichraytirib JPEG'ga o'giradi.

    Qo'lyozma uchun o'lcham muhim: juda kichik rasmda ingichka harflar yo'qoladi va
    model sahifaning faqat bir qismini o'qib qo'yadi.
    """
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
            image.save(buffer, format="JPEG", quality=90, optimize=True)
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
        seconds = 1800 if ("quota" in low or "billing" in low) else 90
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


async def ocr_image(image_data, lang="uz"):
    """Rasmdagi matnni to'liq o'qib beradi; Google kaliti bo'lmasa bo'sh satr.

    Bir nechta model sinaladi va eng to'liq (eng ko'p so'zli) natija olinadi:
    qo'lyozmani bitta model faqat qisman o'qib qo'yishi mumkin, o'shanda butun
    tekshiruv «matn juda qisqa» degan noto'g'ri xulosaga keladi.
    """
    if not image_data:
        return ""
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
    data, mime = prepare_image(image_data)
    best = ""
    # Har bir kalitdagi barcha Google kalitlarini sinaymiz, lekin jami urinish
    # byudjeti cheklangan: bitta sahifa uchun 5-6 ta so'rovdan ko'proq ketmaydi.
    budget = 6
    for row in rows[:3]:
        models = [m.strip() for m in str(row["models"] or "").split(",") if m.strip()]
        for model in _vision_candidates(models):
            if budget <= 0:
                break
            if _vision_skipped(row, model):
                continue
            budget -= 1
            text = await _read_full_page(row, model, data, mime, OCR_PROMPT)
            if word_count(text) > word_count(best):
                best = text
            if word_count(best) >= OCR_ENOUGH_WORDS:
                return best
        if budget <= 0 or word_count(best) >= OCR_ENOUGH_WORDS:
            break
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


def band_scores(raw_scores):
    """Har bir bandni 0..2 oralig'iga keltiradi."""
    scores = {}
    for key in CRITERIA_KEYS:
        value = _score_value((raw_scores or {}).get(key, 0))
        scores[key] = max(0, min(MAX_PER_BAND, value))
    return scores


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

    Rasmiy qoidada yaroqli ish 0 ball olmaydi (0 — bo'sh varaq, faqat kirish
    qismi yoki to'liq kirill alifbasi uchun). Shuning uchun matn mavjud bo'lsa
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
        if _is_fake_error(quote, fix):
            continue
        errors.append({
            "quote": quote,
            "fix": fix,
            "type": str(item.get("type") or "imlo").strip().lower()[:24],
            "rule": str(item.get("rule") or "").strip()[:180],
        })

    words = word_count(text)
    raw_sections = data.get("sections") if isinstance(data.get("sections"), dict) else {}
    sections = {key: raw_sections.get(key) is True for key in ("kirish", "asosiy", "xulosa")}
    flags = []
    total = sum(scores.values())
    estimated = data.get("estimated") is True

    # 0 ball: varaq bo'sh, faqat kirish yozilgan yoki to'liq kirill alifbosida.
    if words == 0:
        flags.append("blank")
    elif sections["kirish"] and not (sections["asosiy"] or sections["xulosa"]):
        flags.append("notask")
    elif cyrillic_ratio(text) >= 0.6:
        flags.append("cyrillic")
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

    if flags and flags[0] in ("blank", "notask", "cyrillic"):
        total = 0
    elif flags and flags[0] != "ocr_short":
        total = 2
    if estimated:
        # Taxminiy ballar hisobotda alohida ogohlantirish bilan ko'rsatiladi.
        flags.append("estimated")

    return {
        "scores": scores,
        "notes": notes,
        "total": total,
        "max_total": MAX_TOTAL,
        "scale_75": to_scale_75(total),
        "sections": sections,
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


def build_prompt(text, topic="", lang="uz", retry=False):
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
        "Muhim: quyidagi JSON sxemasidagi 0 lar — shunchaki namuna, ularni nusxa "
        "ko'chirmang. Har bir bandni matnga qarab baholang. Matn mavjud bo'lsa, "
        "barcha bandlarga birdan 0 qo'yish mumkin emas.\n\n"
        f"{retry_block}"
        "Qat'iy qoidalar: matnda yo'q xatoni o'ylab topmang; bir xil xato bir necha "
        "joyda takrorlansa — bitta xato; quote — matndagi aniq parcha; imlo va tinish "
        "bo'yicha o'zbek lotin alifbosi qoidalariga tayaning. Eng ko'pi bilan 20 ta "
        "aniq xato ko'rsatiladi.\n\n"
        "Rasmiy talablar (buzilishi ballni tushiradi):\n"
        "- esse lotin yozuvidagi o'zbek alifbosida yoziladi;\n"
        "- uslub publitsistik (argumentli, munozarali) bo'ladi;\n"
        "- kirish, asosiy qism va xulosa bo'ladi;\n"
        "- reja va epigraf yozilmaydi — matnda bo'lsa, has_plan/has_epigraph ni true "
        "qiling va bu kamchilikni «qismlar» bandida hisobga oling.\n\n"
        "Istisno qoidalar (o'zingiz qo'llamang, faqat hisobga oling): 100 so'zdan kam — "
        "2 ball, mavzuga mos emas — 2 ball, ko'chirilgan — 2 ball; faqat kirish "
        "yozilgan yoki to'liq kirill alifbosida — 0 ball.\n\n"
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


async def _request_report(body, topic, lang, retry=False):
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
    prompt = build_prompt(body, topic, lang, retry)
    raw = ""
    for attempt in range(2):
        try:
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
        " Ballarni 0, 1 yoki 2 qilib bering.\n"
        '{"scores": {"uslub": 0, "qarashlar": 0, "dalillar": 0, "qismlar": 0, '
        '"mantiq": 0, "izchillik": 0, "imlo": 0, "tinish": 0, "qoshimchalar": 0, '
        '"soz": 0, "paremiya": 0, "adabiy": 0}, '
        '"sections": {"kirish": true, "asosiy": true, "xulosa": true}, '
        '"topic_match": true, "plagiarism_suspected": false, '
        '"has_plan": false, "has_epigraph": false}\n\n'
        f"Mavzu: {topic or 'ko\'rsatilmagan'}\nESSE MATNI:\n" + body[:8000]
    )
    try:
        raw = await ai_api._chat_complete(compact, system=system, max_tokens=700,
                                          temperature=0.1)
        data = _parse_json_object(raw)
        if data:
            print("[check] qisqa (faqat ballar) javob ishlatildi", flush=True)
            return data
    except Exception as exc:
        print(f"[check] qisqa baholash xatosi: {type(exc).__name__}: {exc}", flush=True)
    return None


def _unscored(report):
    """Matn yaroqli, lekin AI barcha bandlarga 0 qo'ygan — ishonchsiz natija."""
    return (int(report.get("total") or 0) == 0
            and not report.get("flags")
            and int(report.get("word_count") or 0) >= MIN_WORDS)


async def analyze_essay(text, lang="uz", topic="", from_image=False):
    """Esseni 12 band bo'yicha tekshiradi. AI ishlamasa None qaytaradi."""
    body = str(text or "").strip()
    if len(body) < 40:
        return None
    body = body[:MAX_CHARS]
    data = await _request_report(body, topic, lang)
    if not data:
        # AI provayderlar butunlay javob bermasa ham foydalanuvchi «xatolik»
        # o'rniga hisobot olishi kerak: matn tahliliga asoslangan ehtiyot
        # baholari qo'llanadi va hisobotda bu ochiq ogohlantiriladi.
        print("[check] AI hisobot bermadi — matn tahliliga asoslangan baho", flush=True)
        data = {"scores": baseline_scores(body), "estimated": True}
    report = normalize_report(data, body, lang, topic, from_image=from_image)
    if _unscored(report):
        # 100+ so'zli lotin matniga barcha bandlar 0 — model sxemadagi nollarni
        # ko'chirgan bo'lishi mumkin. Bir marta qayta so'raymiz.
        print("[check] barcha bandlar 0 — qayta baholash so'raladi", flush=True)
        retry_data = await _request_report(body, topic, lang, retry=True)
        if retry_data:
            retry_report = normalize_report(retry_data, body, lang, topic,
                                            from_image=from_image)
            if retry_report["total"] > report["total"]:
                report = retry_report
        if _unscored(report):
            # Ikkinchi urinish ham nol bo'lsa, noto'g'ri 0 o'rniga ehtiyot
            # bahosini beramiz va buni hisobotda ochiq ogohlantiramiz.
            print("[check] AI baholay olmadi — taxminiy ballar qo'llanadi", flush=True)
            fallback = dict(retry_data or data)
            fallback["scores"] = baseline_scores(body)
            fallback["estimated"] = True
            report = normalize_report(fallback, body, lang, topic,
                                      from_image=from_image)
    return report


# ===== Hisobot matni (Telegram uchun oddiy matn) =====
def format_report(report, lang="uz"):
    info = labels(lang)
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
        "errors": list(report.get("errors") or []),
        "strengths": list(report.get("strengths") or []),
        "advice": list(report.get("advice") or []),
        "review": str(report.get("review") or ""),
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
        },
    }
