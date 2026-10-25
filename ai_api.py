"""
AI API — to'liq tuzatilgan versiya (v11)
========================================
✓ Slaydlar: 10, 15, 20, 25 shablonlariga qat'iy moslashgan.
✓ Til sofligi: Boshqa til aralashishini oldini olish uchun qat'iy filtrlar.
✓ Kontent sifati: Bo'sh joylar va "Ma'lumot" so'zlari to'liq olib tashlandi.
✓ API va Model almashinuvi: Xatolik yuz berganda avtomatik keyingisiga o'tadi.
"""
import aiohttp
import asyncio
import json
import re
import math
import os
from collections import Counter
from dotenv import load_dotenv
load_dotenv()
from config import AI_API_URL, AI_MODEL, AI_TIMEOUT

LAST_ERROR = "hali sinanmadi"
PIXABAY_KEY  = os.getenv("PIXABAY_KEY", "")
PEXELS_KEY   = os.getenv("PEXELS_KEY", "")
UNSPLASH_KEY = os.getenv("UNSPLASH_KEY", "")
USER_AGENT = "SlaydBot/1.0 (aloqa: @AbduIIayev__7)"

_KEYWORD_CACHE = {}
CHARS_PER_PAGE = 900
MAX_CHUNK_PAGES = 3
LONG_SERVICES = ("diplom", "kurs", "referat", "maqola")

API_LIST = [
    {
        "name": "Groq 1 (asosiy)",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key": os.getenv("GROQ_KEY_1", ""),
        "type": "openai",
        "models": ["qwen/qwen3.8-27b", "openai/gpt-oss-120b", "openai/gpt-oss-20b", "allam-2-7b"]
    },
    {
        "name": "Groq 2",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key": os.getenv("GROQ_KEY_2", ""),
        "type": "openai",
        "models": ["qwen/qwen3.8-27b", "openai/gpt-oss-120b", "openai/gpt-oss-20b", "allam-2-7b"]
    },
    {
        "name": "Cloudflare AI (zaxira)",
        "base_url": "https://api.cloudflare.com/client/v4/accounts/283bb72354435f9cfd19a80c3edc93e0/ai/v1",
        "api_key": os.getenv("CLOUDFLARE_KEY", ""),
        "type": "openai",
        "models": [
            "@cf/meta/llama-3.2-3b-instruct",      # ✅ Hozir ishlayapti — BIRINCHI O'RINDA!
            "@cf/meta/llama-3.1-8b-instruct",
            "@cf/qwen/qwen3.8-27b",
            "@cf/google/gemma-7b-it-lora",
            "@cf/mistral/mistral-7b-instruct-v0.2-lora",
            "@cf/meta/llama-3.2-1b-instruct",
            "@cf/meta-llama/llama-2-7b-chat-hf-lora",
            "@cf/google/gemma-2b-it-lora",
            "@cf/openai/gpt-oss-120b",
            "@cf/deepseek-ai/deepseek-r1-distill-qwen-32b"
        ]
    },
    {
        "name": "Google AI 1",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "api_key": os.getenv("GOOGLE_KEY_1", ""),
        "type": "google",
        "models": [
            "gemini-3.6-flash", "gemini-3.5-flash", "gemini-2.5-flash",
            "gemini-3-flash-preview", "gemini-3.5-flash-lite",
            "gemini-3.1-flash-lite", "gemini-3.1-flash-lite-preview",
            "gemini-flash-lite-latest", "gemma-4-31b-it", "gemma-4-26b-a4b-it"
        ]
    },
    {
        "name": "Google AI 2",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "api_key": os.getenv("GOOGLE_KEY_2", ""),
        "type": "google",
        "models": [
            "gemini-3.6-flash", "gemini-3.5-flash", "gemini-2.5-flash",
            "gemini-3-flash-preview", "gemini-3.5-flash-lite",
            "gemini-3.1-flash-lite", "gemini-3.1-flash-lite-preview",
            "gemini-flash-lite-latest", "gemma-4-31b-it", "gemma-4-26b-a4b-it"
        ]
    }
]

CURRENT_API_INDEX = 0
CURRENT_MODEL_INDEX = 0

def get_current_api(): return API_LIST[CURRENT_API_INDEX]
def get_current_model(): return get_current_api()["models"][CURRENT_MODEL_INDEX % len(get_current_api()["models"])]

def switch_to_next_model() -> bool:
    global CURRENT_MODEL_INDEX
    api = get_current_api()
    CURRENT_MODEL_INDEX += 1
    if CURRENT_MODEL_INDEX >= len(api["models"]):
        CURRENT_MODEL_INDEX = 0
        _log(f"⚠️ {api['name']} modellar tugadi. Keyingi API...")
        return False
    _log(f"🔄 Model: {api['name']} → {get_current_model()}")
    return True

def switch_to_next_api():
    global CURRENT_API_INDEX, CURRENT_MODEL_INDEX
    CURRENT_API_INDEX = (CURRENT_API_INDEX + 1) % len(API_LIST)
    CURRENT_MODEL_INDEX = 0
    _log(f"⚠️ Keyingi API: {get_current_api()['name']} | {get_current_model()}")
    return get_current_api()

def clean_ai_text(text):
    if not text: return ""
    text = re.sub(r'\*+', '', str(text))
    text = re.sub(r'^#{1,6}\s*', '', str(text), flags=re.MULTILINE)
    text = re.sub(r'```.*?```', '', str(text), flags=re.DOTALL)
    text = re.sub(r'\n\s*\n', '\n\n', str(text))
    return text.strip()

def _log(msg): print(f"[AI_API] {msg}", flush=True)
def get_last_error(): return LAST_ERROR

LANG_NAMES = {"uz": "o'zbek", "ru": "rus", "en": "ingliz", "tr": "turk", "de": "nemis", "fr": "fransuz"}
ALL_LANGS = ("uz", "ru", "en", "tr", "de", "fr")
def _lang_name(code): return LANG_NAMES.get(str(code).lower(), "o'zbek")

SYSTEM_PROMPTS = {
    "uz": "Siz akademik matn yozuvchi mutaxassissiz. ABSOLYUT HAMMA NARSANI faqat o'zbek tilida yozing! Boshqa tildan bitta so'z ham aralashmasin.",
    "ru": "Вы академический эксперт. ПИШИТЕ АБСОЛЮТНО ВСЁ только на русском языке! Ни одного слова на другом языке.",
    "en": "You are an academic expert. Write ABSOLUTELY EVERYTHING in English only! No words from any other language.",
    "tr": "Sen akademik uzmansın. MUTLAKA HER ŞEYİ sadece Türkçe yaz! Başka dilden tek kelime bile karışmasın.",
    "de": "Sie sind ein akademischer Experte. Schreiben Sie ABSOLUT ALLES nur auf Deutsch! Kein einziges Wort aus einer anderen Sprache.",
    "fr": "Vous êtes un expert académique. Écrivez ABSOLUMENT TOUT en français uniquement ! Aucun mot d'une autre langue.",
}

def detect_topic_lang(topic):
    t = str(topic or "")
    if len(re.findall(r'[А-Яа-яЁё]', t)) >= 2: return "ru"
    low = t.lower()
    if re.search(r'[ğşıİ]', low): return "tr"
    if re.search(r'[ß]', low): return "de"
    if re.search(r'[àâéèêëîïôùûÿçœæ]', low): return "fr"
    if re.search(r'[äöü]', low): return "de"
    if re.search(r'[ığüşöç]', low): return "tr"
    if re.search(r"o['’]z|g['’]|ʻ|ʼ|‘|’", low): return "uz"
    return "en"

def wiki_langs_for_topic(topic, gen_lang):
    tl = detect_topic_lang(topic)
    gl = str(gen_lang).lower()
    order = [tl, gl]
    for x in ("en", "ru", "uz"):
        if x not in order: order.append(x)
    seen, out = set(), []
    for x in order:
        if x and x not in seen:
            seen.add(x); out.append(x)
    return out[:4]

_EN_STOP = {"the","and","is","of","to","in","for","with","on","that","this","it","as","are","by","an","be",
            "or","which","from","at","not","but","have","has","was","were","will","can","more","their",
            "they","we","our","you","your","also","such","than","into","about","between","these","those",
            "its","his","her","been","being","would","could","should","may","might","must","shall"}

def _english_ratio(text):
    words = re.findall(r'[a-zA-Z]{2,}', str(text).lower())
    if not words: return 0.0
    return sum(1 for w in words if w in _EN_STOP) / len(words)

def _is_lang_mixed(text, lang):
    enr = _english_ratio(text)
    cyr_ratio = len(re.findall(r'[А-Яа-яЁё]', text)) / max(1, len(text))
    if lang != "en" and enr > 0.05: return True
    if lang == "ru" and cyr_ratio < 0.20: return True
    if lang in ("uz","tr","de","fr") and cyr_ratio > 0.10: return True
    return False

def _pure_language_system(lang_code):
    lc = str(lang_code).lower()
    return SYSTEM_PROMPTS.get(lc, SYSTEM_PROMPTS["en"])


async def localize_topic(topic, lang="uz"):
    """Translate a user-entered topic to the requested document language.

    Proper names and standard technical names are preserved. If translation fails,
    return the original topic rather than stopping document generation.
    """
    original = str(topic or "").strip()
    lc = str(lang or "en").lower()
    language_names = {"uz": "Uzbek", "ru": "Russian", "en": "English", "tr": "Turkish", "de": "German", "fr": "French"}
    if not original or lc not in language_names:
        return original
    # Common Arabic subject names should not remain untranslated in an otherwise localized document.
    arabic_subjects = {
        "تاريخ": {"uz": "Tarix", "ru": "История", "en": "History", "tr": "Tarih", "de": "Geschichte", "fr": "Histoire"},
        "رياضيات": {"uz": "Matematika", "ru": "Математика", "en": "Mathematics", "tr": "Matematik", "de": "Mathematik", "fr": "Mathématiques"},
        "جغرافيا": {"uz": "Geografiya", "ru": "География", "en": "Geography", "tr": "Coğrafya", "de": "Geografie", "fr": "Géographie"},
        "فيزياء": {"uz": "Fizika", "ru": "Физика", "en": "Physics", "tr": "Fizik", "de": "Physik", "fr": "Physique"},
        "كيمياء": {"uz": "Kimyo", "ru": "Химия", "en": "Chemistry", "tr": "Kimya", "de": "Chemie", "fr": "Chimie"},
        "أحياء": {"uz": "Biologiya", "ru": "Биология", "en": "Biology", "tr": "Biyoloji", "de": "Biologie", "fr": "Biologie"},
    }
    if original in arabic_subjects:
        return arabic_subjects[original].get(lc, original)
    prompt = (
        f"Translate this academic topic/title into {language_names[lc]}. Preserve people, place, "
        "organization, brand and official product names where appropriate. Do not add commentary, "
        "quotes, labels, or explanations. If it is already in the target language, return it unchanged. "
        f"Return only the translated title:\n{original}"
    )
    try:
        result = await _chat_complete(prompt, system=f"You are a professional translator. Output only {language_names[lc]} text, with no other language unless it is a proper noun.", max_tokens=120)
        result = clean_ai_text(str(result or "")).strip().strip('"“”`')
        if result and not result.startswith("⚠️") and len(result) <= max(250, len(original) * 4):
            return result
    except Exception as exc:
        _log(f"Topic localization failed: {exc}")
    return original

async def wikipedia_fetch(topic, max_chars=4000, full=False, gen_lang="uz"):
    langs = wiki_langs_for_topic(topic, gen_lang)
    _log(f"🔍 Wikipedia qidiruv: {langs} (mavzu: '{topic}')")
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20), headers={"User-Agent": USER_AGENT}) as session:
        for lang in langs:
            try:
                search_url = f"https://{lang}.wikipedia.org/w/api.php?action=query&list=search&srsearch={aiohttp.helpers.quote(topic)}&format=json&srlimit=1"
                async with session.get(search_url) as resp:
                    if resp.status != 200: continue
                    hits = (await resp.json()).get("query", {}).get("search", [])
                    if not hits: continue
                    title = hits[0]["title"]
                exintro = "" if full else "&exintro"
                page_url = f"https://{lang}.wikipedia.org/w/api.php?action=query&prop=extracts|pageimages{exintro}&explaintext&piprop=original&titles={aiohttp.helpers.quote(title)}&format=json&redirects=1"
                async with session.get(page_url) as resp:
                    if resp.status != 200: continue
                    pages = (await resp.json()).get("query", {}).get("pages", {})
                    page = next(iter(pages.values()), {})
                    extract = page.get("extract", "")
                    image = page.get("original", {}).get("source", "")
                    if extract and len(extract) > 100:
                        return {"found": True, "lang": lang, "title": title, "text": extract[:max_chars], "image": image, "url": f"https://{lang}.wikipedia.org/wiki/{title.replace(' ', '_')}"}
            except Exception as e:
                _log(f"[WIKI {lang}] xato: {e}"); continue
    return {"found": False, "text": "", "image": "", "url": "", "title": "", "lang": ""}

def wiki_block(wiki):
    if not wiki.get("found"): return ""
    return f"\n\n=== MANBA (Wikipedia) ===\nSarlavha: {wiki['title']}\nQuyidagi faktlarni asos qilib yoz:\n{wiki['text']}\n"

SERVICE_TEMPLATES = {
    "referat": {"style": "ilmiy-nazariy, rasmiy uslub. HAJMI: 10-15 bet.", "sections": [
        ("TITULLIK BET", "Mavzu, OTM nomi, guruh, muallif, yil — bitta betda, to'liq"),
        ("MUNDARIJA", "Kirish, 2-3 ta reja (bob), Xulosa, Adabiyotlar — sahifa raqamlari bilan"),
        ("KIRISH", "Mavzuning dolzarbligi, maqsadi va vazifalari — TO'LIQ 1 bet"),
        ("ASOSIY QISM — 1-BOB", "Birinchi reja bo'yicha nazariy ma'lumotlar, batafsil, faktlar bilan"),
        ("ASOSIY QISM — 2-BOB", "Ikkinchi reja bo'yicha nazariy ma'lumotlar, batafsil"),
        ("ASOSIY QISM — 3-BOB", "Uchinchi reja bo'yicha tahlil va misollar"),
        ("XULOSA", "Mavzu bo'yicha umumiy xulosalar — TO'LIQ 1 bet"),
        ("FOYDALANILGAN ADABIYOTLAR", "5-10 ta manba, to'liq bibliografik ma'lumot bilan")]},
    "mustaqil": {"style": "akademik, mantiqiy, savol-javob shaklida. HAJMI: 5-10 bet.", "sections": [
        ("TITULLIK BET", "Mavzu, fan, guruh, muallif, yil"), ("REJA", "2-3 ta savol yoki masala ro'yxati"),
        ("KIRISH", "Qisqa kirish — 0.5 bet, mavzuga kirish"), ("1-SAVOLGA JAVOB", "Birinchi savolga batafsil, mantiqiy javob — 2-3 bet"),
        ("2-SAVOLGA JAVOB", "Ikkinchi savolga batafsil javob — 2-3 bet"), ("3-SAVOLGA JAVOB", "Uchinchi savolga batafsil javob — 2-3 bet"),
        ("XULOSA", "Qisqa yakuniy xulosa"), ("ADABIYOTLAR", "5 ta manba, to'liq ma'lumot bilan")]},
    "kurs": {"style": "ilmiy-tadqiqot, rasmiy, statistikalar bilan. HAJMI: 25-35 bet.", "sections": [
        ("TITULLIK BET", "To'liq titullik bet"), ("MUNDARIJA", "Barcha boblar, paragraflar — sahifa raqamlari bilan"),
        ("KIRISH", "Dolzarbligi, obyekti, predmeti, maqsadi — TO'LIQ 2 bet"), ("I-BOB. NAZARIY QISM", "Mavzuning nazariy asoslari — 8-10 bet"),
        ("II-BOB. AMALIY QISM", "Muammo tahlili, statistikalar — 8-10 bet"), ("XULOSA VA TAKLIFLAR", "Umumiy xulosa va takliflar — 2 bet"),
        ("ADABIYOTLAR", "15-20 ta manba"), ("QO'SHIMCHALAR", "Jadvallar, diagrammalar")]},
    "diplom": {"style": "ilmiy-tadqiqot, BMI darajasida. HAJMI: 50-70 bet.", "sections": [
        ("ANNOTATSIYA", "3 tilda qisqa mazmun"), ("MUNDARIJA", "To'liq mundarija"), ("KIRISH", "Dolzarbligi, obyekti, predmeti, maqsadi — 3-4 bet"),
        ("I-BOB. NAZARIY ASOSLAR", "Nazariy asoslar — 12-15 bet"), ("II-BOB. TAHLIL QISMI", "Muammo tahlili, statistika — 12-15 bet"),
        ("III-BOB. TAKLIFLAR", "Takliflar, loyihalar — 10-12 bet"), ("XULOSA", "Umumiy xulosa — 3 bet"),
        ("ADABIYOTLAR", "30+ manba"), ("QO'SHIMCHALAR", "Jadvallar, diagrammalar")]},
    "test": {"style": "qisqa, aniq savollar. A/B/C/D variantlari.", "sections": [("TEST SAVOLLARI", "Savollar va variantlar"), ("JAVOBLAR KALITI", "To'g'ri javoblar ro'yxati")]},
    "maqola": {"style": "ilmiy, IMRAD standarti. HAJMI: 3-7 bet.", "sections": [
        ("SARLAVHA VA MUALlif", "Maqola sarlavhasi, muallif"), ("ANNOTATSIYA", "Annotatsiya va kalit so'zlar"), ("KIRISH", "Muammo, dolzarblik — 1 bet"),
        ("METODOLOGIYA", "Izlanish usullari — 1 bet"), ("NATIJALAR", "Tahlillar, jadvallar — 2-3 bet"), ("XULOSA", "Asosiy xulosalar — 0.5 bet"), ("ADABIYOTLAR", "10-15 manba")]},
    "tezis": {"style": "juda ixcham. HAJMI: 1-3 bet.", "sections": [
        ("SARLAVHA VA MUALlif", "Sarlavha, muallif"), ("QISQA KIRISH", "2-3 jumla"), ("ASOSIY TAHLIL", "Konkret tahlil, raqamlar"), ("XULOSA", "Asosiy natija")]},
}

async def _generate_outline(service, topic, pages, lang, wiki):
    tmpl = SERVICE_TEMPLATES.get(service)
    if not tmpl:
        return [("KIRISH", max(1, pages//6), "kirish"), ("ASOSIY QISM", max(2, pages*2//3), "asosiy"), ("XULOSA", max(1, pages//6), "xulosa")]
    secs = tmpl["sections"]; n = len(secs)
    weights = []
    for title, _ in secs:
        if any(k in title for k in ("TITULLIK", "MUNDARIJA", "ANNOTATSIYA", "KALIT", "QO'SHIM")): weights.append(1)
        elif any(k in title for k in ("KIRISH", "XULOSA")): weights.append(2)
        else: weights.append(5)
    total_w = sum(weights); outline, used = [], 0
    for i, (title, desc) in enumerate(secs):
        p = max(1, pages - used) if i == n - 1 else max(1, round(pages * weights[i] / total_w))
        used += p; outline.append((title, p, desc))
    return outline

async def _generate_section(service, topic, sec_title, sec_pages, sec_desc, lang, wiki, prev_summary):
    chunks_needed = (sec_pages + MAX_CHUNK_PAGES - 1) // MAX_CHUNK_PAGES
    parts, local_prev = [], prev_summary
    for ch in range(chunks_needed):
        chunk_pages = min(MAX_CHUNK_PAGES, sec_pages - ch * MAX_CHUNK_PAGES)
        chunk_target = chunk_pages * CHARS_PER_PAGE
        prompt = (f"Xizmat: {service}\nMavzu: {topic}\nHozirgi bo'lim: {sec_title} ({sec_desc})\n"
                  f"Bu bo'limning {ch+1}-qismi. Kamida {chunk_target} belgi yoz.\n"
                  f"Avvalgi qismlar (TAKRORLAMANG!): {local_prev[:600]}\n{wiki_block(wiki)}\n\n"
                  f"Shartlar: (1) faqat yangi ma'lumot; (2) takrorlama; (3) betlarni to'ldir; (4) faktlar qo'sh.")
        txt = await _chat_complete(prompt, system=_pure_language_system(lang), max_tokens=4096)
        if not txt or "⚠️" in txt:
            loc = _FALLBACK_COPY.get(str(lang).lower(), _FALLBACK_COPY["en"])
            txt = f"{sec_title}. {topic}: {loc['body']} {loc['analysis']}"
        if _is_lang_mixed(txt, lang):
            txt2 = await _chat_complete(prompt + f"\nDIQQAT: FAQAT {_lang_name(lang)} tilida yozing!", system=_pure_language_system(lang), max_tokens=4096)
            if txt2 and "⚠️" not in txt2: txt = txt2
        parts.append(txt); local_prev = txt[:600]
        await asyncio.sleep(0.2)
    return "\n\n".join(parts)

def _fallback_essay_outline(topic, lang="uz"):
    """Return a stable, localized five-point essay plan when AI output is unusable."""
    topic = str(topic or "mavzu").strip()
    plans = {
        "uz": [
            f"Kirish: {topic} mavzusining mazmuni va tarixiy yoki ijtimoiy ahamiyati.",
            "Birinchi asosiy fikr: mavzuning kelib chiqishi va muhim xususiyatlari.",
            "Ikkinchi asosiy fikr: mavzuning hayotga ta’siri va tegishli misollar.",
            "Uchinchi asosiy fikr: turli qarashlarni baholash va shaxsiy munosabat.",
            "Xulosa: asosiy fikrlarni umumlashtirish va yakuniy saboq.",
        ],
        "ru": [
            f"Введение: содержание темы «{topic}» и её историческое или общественное значение.",
            "Первый основной тезис: происхождение темы и её важные особенности.",
            "Второй основной тезис: влияние темы на жизнь и соответствующие примеры.",
            "Третий основной тезис: оценка разных взглядов и личная позиция.",
            "Заключение: обобщение основных мыслей и итоговый вывод.",
        ],
        "en": [
            f"Introduction: the meaning of {topic} and its historical or social significance.",
            "First main point: the topic’s origins and key characteristics.",
            "Second main point: the topic’s impact and relevant examples.",
            "Third main point: weighing different views and stating a personal position.",
            "Conclusion: summarizing the key arguments and final lesson.",
        ],
        "tr": [
            f"Giriş: {topic} konusunun anlamı ve tarihsel ya da toplumsal önemi.",
            "Birinci ana fikir: konunun kökeni ve temel özellikleri.",
            "İkinci ana fikir: konunun yaşama etkisi ve uygun örnekler.",
            "Üçüncü ana fikir: farklı görüşleri değerlendirme ve kişisel tutum.",
            "Sonuç: temel düşünceleri bir araya getirme ve nihai çıkarım.",
        ],
        "de": [
            f"Einleitung: Bedeutung des Themas {topic} für Geschichte oder Gesellschaft.",
            "Erster Hauptgedanke: Ursprung des Themas und seine wichtigsten Merkmale.",
            "Zweiter Hauptgedanke: Auswirkungen des Themas und passende Beispiele.",
            "Dritter Hauptgedanke: verschiedene Ansichten abwägen und die eigene Position begründen.",
            "Schluss: zentrale Argumente zusammenfassen und eine Schlussfolgerung ziehen.",
        ],
        "fr": [
            f"Introduction : sens du sujet {topic} et son importance historique ou sociale.",
            "Première idée principale : les origines du sujet et ses caractéristiques essentielles.",
            "Deuxième idée principale : les effets du sujet et des exemples pertinents.",
            "Troisième idée principale : comparer les points de vue et exposer sa position personnelle.",
            "Conclusion : résumer les arguments essentiels et formuler un bilan.",
        ],
    }
    rows = plans.get(str(lang).lower(), plans["uz"])
    return "\n".join(f"{i}. {row}" for i, row in enumerate(rows, 1))


def _normalize_outline(text, topic, lang):
    """Accept only a clean five-item plan; otherwise use a localized safe plan."""
    raw = clean_ai_text(text or "")
    lines = []
    for line in raw.splitlines():
        line = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line).strip()
        if not line or line.lower().rstrip(":") in {"reja", "outline", "plan", "план", "gliederung", "taslak"}:
            continue
        if len(line) > 240:
            continue
        lines.append(line)
    # A plan must have exactly the requested outline slots, not writing advice or a full essay.
    combined = " ".join(lines)
    if len(lines) != 5 or _is_lang_mixed(combined, lang) or _essay_text_is_suspicious(combined, lang, 30):
        return _fallback_essay_outline(topic, lang)
    norm = [re.sub(r"^\s*(?:I{1,3}[.)]\s*)", "", x).strip() for x in lines]
    if len({re.sub(r"\W+", " ", x.lower()).strip() for x in norm}) != 5:
        return _fallback_essay_outline(topic, lang)
    return "\n".join(f"{i}. {line}" for i, line in enumerate(norm, 1))


def _essay_text_is_suspicious(text, lang, expected_words):
    """Reject malformed, repeated, very short, or clearly mixed-language AI output."""
    cleaned = clean_ai_text(text or "")
    if not cleaned or cleaned.startswith("⚠️") or _is_lang_mixed(cleaned, lang):
        return True
    words = re.findall(r"[^\W_]+(?:[’'’-][^\W_]+)*", cleaned.lower(), flags=re.UNICODE)
    if len(words) < max(8, int(expected_words * 0.48)):
        return True
    if len(words) >= 28:
        language_signals = {
            "uz": {"va", "bu", "bilan", "uchun", "ham", "esa", "ammo", "biroq", "uning", "ular", "bo‘lgan", "bo'lgan", "kerak", "mumkin", "orqali", "shuning", "sababli", "hisoblanadi", "ko‘ra", "kabi", "edi", "qiladi", "etadi", "bo‘lib", "bo'lib", "hamda", "muhim", "tarixda", "davrda", "natijada", "birinchi", "ikkinchi", "xulosa", "inson", "jamiyat", "mavzu"},
            "ru": {"и", "в", "не", "на", "что", "это", "как", "для", "при", "также", "который", "его", "она", "они", "но", "потому", "поэтому", "следует", "важно", "можно", "является", "был", "были", "этот", "тема"},
            "en": {"the", "and", "of", "to", "in", "is", "that", "for", "with", "on", "as", "by", "from", "it", "was", "are", "which", "this", "these", "should", "because", "however"},
            "tr": {"ve", "bir", "bu", "için", "ile", "olarak", "ancak", "ayrıca", "çünkü", "olan", "göre", "gibi", "daha", "çok", "önemli", "gerekir", "konu", "etkisi"},
            "de": {"der", "die", "das", "und", "ist", "für", "mit", "auch", "als", "auf", "im", "den", "ein", "eine", "werden", "deshalb", "wichtig", "weil", "dass", "thema"},
            "fr": {"le", "la", "les", "et", "est", "de", "des", "un", "une", "pour", "avec", "dans", "qui", "que", "mais", "ainsi", "important", "parce", "sujet"},
        }
        expected_signals = language_signals.get(str(lang).lower(), set())
        if expected_signals and len(set(words) & expected_signals) < 3:
            return True
    if len(words) >= 35:
        unique_ratio = len(set(words)) / max(1, len(words))
        if unique_ratio < 0.36:
            return True
        ngrams = Counter(tuple(words[i:i + 7]) for i in range(max(0, len(words) - 6)))
        if any(count >= 3 for count in ngrams.values()):
            return True
    paragraphs = [re.sub(r"\W+", " ", p.lower()).strip() for p in re.split(r"\n\s*\n|\n", cleaned) if p.strip()]
    meaningful = [p for p in paragraphs if len(p.split()) >= 8]
    if len(meaningful) != len(set(meaningful)) and len(meaningful) >= 2:
        return True
    return False


def _fallback_essay_parts(topic, lang="uz"):
    """Coherent localized backup prose; never use a repeated or corrupted model response."""
    tpc = str(topic or "ushbu mavzu").strip()
    lc = str(lang).lower()
    if lc == "uz" and "amir temur" in tpc.lower():
        return (
            "Amir Temur XIV asrda Movarounnahrda kuchli markazlashgan davlat barpo etgan hukmdor va sarkarda sifatida tarixda muhim o‘rin egallaydi. Uning faoliyati davlat boshqaruvi, harbiy strategiya va madaniy hayot bilan bog‘liq. Amir Temur merosini o‘rganish o‘sha davr siyosiy sharoitini hamda davlat taraqqiyotiga ta’sir qilgan omillarni tushunishga yordam beradi.",
            "Avvalo, Amir Temur siyosiy tarqoqlik kuchaygan bir davrda hokimiyatni mustahkamlashga va boshqaruvni markazlashtirishga intildi. Uning harbiy yurishlari davlat hududini kengaytirgan bo‘lsa-da, bu jarayonlar turli xalqlar uchun og‘ir oqibatlar ham keltirgan. Shu sababli uning faoliyatini tarixiy sharoitni hisobga olib, biryoqlama baholamaslik lozim.",
            "Ikkinchidan, Samarqand uning davrida yirik siyosiy va madaniy markazga aylandi. Turli hududlardan ustalar, me’morlar va hunarmandlarning jalb qilinishi me’morchilik hamda amaliy san’at rivojiga ta’sir ko‘rsatdi. Bu jarayonlar keyingi temuriylar davridagi ilm-fan va madaniyat yuksalishi uchun ham muhim zamin yaratdi.",
            "Menimcha, Amir Temur merosini o‘rganishda yutuqlar bilan birga urushlarning oqibatlarini ham tahlil qilish kerak. Tarixiy shaxsga xolis baho berish uning kuchli tomonlarini tan olish va murakkab jihatlarini ham unutmaslikni talab etadi. Ana shunday yondashuv tarixdan to‘g‘ri saboq olishga yordam beradi.",
            "Xulosa qilib aytganda, Amir Temur tarixda davlat qurilishi, harbiy boshqaruv va Samarqand taraqqiyoti bilan iz qoldirgan. Uning faoliyati murakkab tarixiy hodisa bo‘lib, uni dalillar asosida o‘rganish zarur. Tarixiy merosni chuqur bilish bugungi avlodda mas’uliyat, xolis fikrlash va o‘z o‘tmishiga ongli munosabatni shakllantiradi."
        )
    fallback = {
        "uz": (
            f"{tpc} mavzusi turli jihatlarni o‘ylab ko‘rish va uning mazmunini chuqurroq anglash imkonini beradi. Bu masalani faqat umumiy ta’rif bilan cheklamasdan, sabablar, misollar va oqibatlar orqali tahlil qilish muhim. Shunday yondashuv mavzuning ahamiyatini aniqroq ko‘rsatadi.",
            f"Birinchidan, {tpc}ni tushunish uchun uning kelib chiqishi va asosiy xususiyatlariga e’tibor berish kerak. Asosli fikrlar ishonchli ma’lumotlar va aniq misollar bilan mustahkamlanganda, tahlil ishonarli bo‘ladi. Dalillarni tekshirish esa xato xulosalarga kelish ehtimolini kamaytiradi.",
            f"Ikkinchidan, {tpc}ning insonlar va jamiyatga ta’sirini ham hisobga olish lozim. Har bir masalada turli qarashlar uchrashi mumkin, shuning uchun qarama-qarshi fikrlarni tinglash va ularni dalillar bilan solishtirish foydali. Bu mavzuni kengroq nuqtayi nazardan ko‘rishga yordam beradi.",
            f"Menimcha, {tpc}ga munosabat bildirayotganda hissiyotdan ko‘ra dalil va mantiqqa tayanish kerak. Bir nechta jihatni solishtirish orqali asosli pozitsiyani shakllantirish mumkin. Shu bilan birga, har qanday xulosani yangi ma’lumotlar asosida qayta ko‘rib chiqishga tayyor turish muhim.",
            f"Xulosa qilib aytganda, {tpc}ni to‘g‘ri anglash uchun uning asosiy tomonlarini birgalikda baholash kerak. Ishonchli dalillar, mazmunli misollar va xolis yondashuv yaxshi xulosa chiqarishga yordam beradi. Eng muhimi, olingan saboqlarni amalda qo‘llash va masalaga mas’uliyat bilan qarashdir."
        ),
        "ru": (
            f"Тема «{tpc}» позволяет рассмотреть важный вопрос с разных сторон и глубже понять его смысл. Для содержательного анализа недостаточно общего определения: необходимо учитывать причины, примеры и последствия. Такой подход помогает точнее оценить значение темы.",
            f"Во-первых, для понимания темы «{tpc}» важно изучить её происхождение и основные особенности. Когда рассуждения подтверждаются достоверными сведениями и конкретными примерами, анализ становится убедительнее. Проверка фактов также уменьшает риск ошибочных выводов.",
            f"Во-вторых, следует учитывать влияние темы «{tpc}» на людей и общество. По многим вопросам существуют разные позиции, поэтому полезно сопоставлять противоположные мнения и проверять их аргументы. Это позволяет увидеть проблему шире и избежать односторонней оценки.",
            f"На мой взгляд, обсуждая тему «{tpc}», следует опираться прежде всего на логику и доказательства. Сравнение нескольких точек зрения помогает сформировать взвешенную позицию. При этом важно быть готовым пересмотреть выводы при появлении новых достоверных сведений.",
            f"Подводя итог, можно сказать, что для понимания темы «{tpc}» необходимо оценивать её основные стороны в совокупности. Факты, подходящие примеры и объективный подход помогают сделать обоснованный вывод. Важно также применять полученные уроки на практике и ответственно относиться к обсуждаемой проблеме."
        ),
        "en": (
            f"The topic of {tpc} can be examined from several perspectives and understood more deeply by considering its meaning and consequences. A useful discussion should move beyond a general definition and consider causes, examples, and effects. This approach gives a clearer view of the topic’s importance.",
            f"First, understanding {tpc} requires attention to its background and main characteristics. Reasoning becomes more convincing when it is supported by reliable information and concrete examples. Checking evidence also reduces the likelihood of reaching an inaccurate conclusion.",
            f"Second, the effect of {tpc} on people and society should be considered. Different viewpoints often exist, so comparing opposing arguments and evaluating their evidence is useful. This makes it easier to understand the issue broadly rather than relying on a one-sided interpretation.",
            f"In my view, a sound position on {tpc} should be based on evidence and logical reasoning rather than emotion alone. Comparing several perspectives helps form a balanced judgment. It is also important to remain willing to revise a conclusion when trustworthy new information becomes available.",
            f"In conclusion, {tpc} should be evaluated by considering its main dimensions together. Reliable evidence, relevant examples, and an objective approach lead to stronger conclusions. The lessons learned are most valuable when they are applied thoughtfully and with a sense of responsibility."
        ),
        "tr": (
            f"{tpc} konusu, anlamını ve sonuçlarını farklı açılardan değerlendirmeye imkân verir. Nitelikli bir inceleme yalnızca genel bir tanımla yetinmemeli; nedenleri, örnekleri ve etkileri de ele almalıdır. Bu yaklaşım konunun önemini daha açık biçimde gösterir.",
            f"İlk olarak, {tpc} konusunu anlamak için geçmişini ve temel özelliklerini incelemek gerekir. Görüşler güvenilir bilgiler ve somut örneklerle desteklendiğinde değerlendirme daha inandırıcı olur. Bilgileri doğrulamak yanlış sonuçlara ulaşma riskini de azaltır.",
            f"İkinci olarak, {tpc} konusunun insanlar ve toplum üzerindeki etkileri dikkate alınmalıdır. Bir konuda farklı düşünceler bulunabilir; bu nedenle karşıt görüşleri karşılaştırmak ve kanıtlarını değerlendirmek yararlıdır. Böylece mesele tek taraflı değil, daha geniş bir bakışla ele alınır.",
            f"Bana göre, {tpc} hakkında düşünürken yalnızca duygulara değil, mantığa ve kanıtlara da dayanmak gerekir. Farklı bakış açılarını karşılaştırmak dengeli bir görüş oluşturmaya yardım eder. Güvenilir yeni bilgiler ortaya çıktığında düşünceyi yeniden değerlendirmek de önemlidir.",
            f"Sonuç olarak, {tpc} konusunu anlamak için temel yönleri birlikte değerlendirmek gerekir. Güvenilir bilgiler, uygun örnekler ve tarafsız yaklaşım daha sağlam bir sonuca ulaşmayı sağlar. En önemli nokta, çıkarılan dersleri uygulamak ve konuya sorumlulukla yaklaşmaktır."
        ),
        "de": (
            f"Das Thema {tpc} lässt sich aus mehreren Blickwinkeln betrachten, um seine Bedeutung und Folgen besser zu verstehen. Eine überzeugende Erörterung sollte nicht bei einer allgemeinen Definition stehen bleiben, sondern Ursachen, Beispiele und Auswirkungen berücksichtigen. So wird die Bedeutung des Themas klarer.",
            f"Erstens müssen für das Verständnis von {tpc} der Hintergrund und die wichtigsten Merkmale untersucht werden. Argumente wirken überzeugender, wenn sie durch zuverlässige Informationen und konkrete Beispiele gestützt werden. Eine Prüfung der Fakten senkt zudem das Risiko falscher Schlussfolgerungen.",
            f"Zweitens sollten die Auswirkungen von {tpc} auf Menschen und Gesellschaft berücksichtigt werden. Oft gibt es unterschiedliche Sichtweisen; deshalb ist es sinnvoll, Gegenargumente zu vergleichen und ihre Belege zu prüfen. Auf diese Weise lässt sich das Thema umfassender betrachten.",
            f"Meiner Ansicht nach sollte eine fundierte Position zu {tpc} auf Belegen und logischem Denken beruhen. Der Vergleich verschiedener Perspektiven hilft dabei, ein ausgewogenes Urteil zu bilden. Zugleich sollte man bereit sein, Schlussfolgerungen anhand neuer verlässlicher Informationen zu überprüfen.",
            f"Zusammenfassend lässt sich sagen, dass {tpc} nur dann angemessen verstanden wird, wenn seine wesentlichen Aspekte gemeinsam betrachtet werden. Verlässliche Belege, passende Beispiele und eine sachliche Haltung unterstützen eine begründete Schlussfolgerung. Entscheidend ist, daraus praktische Lehren zu ziehen und verantwortungsvoll zu handeln."
        ),
        "fr": (
            f"Le sujet {tpc} peut être étudié sous plusieurs angles afin d’en comprendre le sens et les conséquences. Une réflexion sérieuse ne doit pas se limiter à une définition générale : elle doit aussi examiner les causes, les exemples et les effets. Cette démarche permet de mieux apprécier son importance.",
            f"Tout d’abord, comprendre {tpc} demande d’étudier son contexte et ses caractéristiques principales. Une argumentation devient plus convaincante lorsqu’elle s’appuie sur des informations fiables et des exemples concrets. La vérification des faits réduit également le risque de conclusions erronées.",
            f"Ensuite, il convient d’examiner les effets de {tpc} sur les personnes et la société. Plusieurs points de vue peuvent coexister ; il est donc utile de comparer les arguments opposés et d’évaluer leurs preuves. Cela permet d’aborder le sujet de manière plus complète.",
            f"À mon avis, une position solide sur {tpc} doit s’appuyer sur des preuves et un raisonnement logique, et pas uniquement sur les émotions. Comparer différentes perspectives aide à construire un jugement équilibré. Il faut aussi rester prêt à réviser ses conclusions lorsque de nouvelles informations fiables apparaissent.",
            f"En conclusion, il est nécessaire d’examiner ensemble les principaux aspects de {tpc} pour en saisir la portée. Des preuves fiables, des exemples pertinents et une approche objective permettent de tirer une conclusion justifiée. L’essentiel est de mettre les enseignements en pratique avec responsabilité."
        ),
    }
    return fallback.get(lc, fallback["uz"])


def _normalize_three_paragraphs(text):
    """Ensure the essay body is displayed as three substantive paragraphs."""
    parts = [p.strip() for p in re.split(r"\n\s*\n|\n", clean_ai_text(text or "")) if p.strip()]
    if len(parts) == 3:
        return "\n\n".join(parts)
    if len(parts) > 3:
        groups = [[], [], []]
        for i, part in enumerate(parts):
            groups[min(2, (i * 3) // len(parts))].append(part)
        return "\n\n".join(" ".join(g) for g in groups if g)
    whole = " ".join(parts)
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", whole) if s.strip()]
    if len(sentences) >= 3:
        groups = [[], [], []]
        total = len(sentences)
        for i, sentence in enumerate(sentences):
            groups[min(2, (i * 3) // total)].append(sentence)
        return "\n\n".join(" ".join(g) for g in groups if g)
    return "\n\n".join(parts)


async def generate_outline(service, topic, lang, words=320):
    """Generate exactly five localized outline points: intro, three body points, conclusion."""
    lc = str(lang or "uz").lower()
    ln = _lang_name(lc)
    try:
        wiki = await wikipedia_fetch(topic, max_chars=1800, gen_lang=lc)
    except Exception as exc:
        _log(f"Essay outline reference lookup failed: {exc}")
        wiki = ""
    wb = wiki_block(wiki)
    prompt = f"""Create an outline for an essay on this topic: {topic}.
Write exactly FIVE concise numbered lines, entirely in {ln}, in this precise order:
1. Introduction plan: context, significance, and thesis.
2. Main argument 1: first key point and supporting detail.
3. Main argument 2: second key point, evidence, or a balanced counter-view.
4. Main argument 3: personal evaluation or a third relevant argument.
5. Conclusion plan: synthesize the argument and state a final lesson.
Do not write the essay itself, explanatory instructions, headings beyond the five numbered lines, or any words in another language. Do not invent statistics. Keep each line specific to the topic. If references below use another language, use them only for facts and write the outline solely in {ln}.
Target essay length: {words} words.
Reference notes:
{wb}"""
    try:
        txt = await _chat_complete(prompt, system=_pure_language_system(lc) + f" Output exactly five numbered outline lines only in {ln}.", max_tokens=1000)
        normalized = _normalize_outline(txt, topic, lc)
        return normalized
    except Exception as exc:
        _log(f"Essay outline generation failed: {exc}")
        return _fallback_essay_outline(topic, lc)


# ===== ESSAY GENERATION =====
async def generate(service, topic, options, lang="uz"):
    if service == "insho":
        lc = str(lang or "uz").lower()
        ln = _lang_name(lc)
        try:
            target_words = max(100, min(3000, int(options.get("words", 320) or 320)))
        except (TypeError, ValueError):
            target_words = 320
        target_words = max(100, min(3000, target_words))
        # Keep the user's requested total instead of silently forcing every essay to 320 words.
        intro_words = max(20, round(target_words * 0.20))
        conclusion_words = max(20, round(target_words * 0.20))
        body_words = max(45, target_words - intro_words - conclusion_words)
        para_words = max(15, round(body_words / 3))
        try:
            wiki = await wikipedia_fetch(topic, max_chars=2200, gen_lang=lc)
        except Exception as exc:
            _log(f"Essay reference lookup failed: {exc}")
            wiki = ""
        wb = wiki_block(wiki)
        system = _pure_language_system(lc) + (
            f" You are a skilled essay writer. Write idiomatic, coherent {ln} only. "
            "Do not code-switch or imitate broken language. Never repeat a sentence or paragraph. "
            "Do not invent precise statistics, quotations, or sources. Do not output section headings."
        )

        async def generate_section(label, prompt, expected, max_tokens=1200):
            draft = await _chat_complete(prompt, system=system, max_tokens=max_tokens)
            for attempt in range(2):
                if draft and not str(draft).startswith("⚠️") and not _essay_text_is_suspicious(draft, lc, expected):
                    return clean_ai_text(draft), True
                repair_prompt = f"""The previous answer was unusable because it contained mixed language, repetition, or unnatural text.
Rewrite it from scratch as natural, correct {ln}. Do not translate word by word. Do not include a heading or writing instructions.
Task: {label}
Topic: {topic}
Target length: approximately {expected} words.
Reference notes may contain foreign words; do not copy foreign-language text:
{wb}
Previous draft to fix (use only if it contains a valid fact):
{str(draft or '')[:2500]}"""
                draft = await _chat_complete(repair_prompt, system=system, max_tokens=max_tokens)
            return None, False

        prompt_intro = f"""Write ONLY the opening paragraph of an essay about: {topic}.
Write approximately {intro_words} words in natural {ln}. Establish the topic's relevance, explain it in your own words, and state a clear central idea. Make it topic-specific and factually careful.
Output only the paragraph. No heading, numbering, checklist, meta-advice, or section labels. Do not use any other language. Reference notes:
{wb}"""
        intro, intro_ok = await generate_section("opening paragraph", prompt_intro, intro_words, 1000)

        prompt_body = f"""Write the essay's main argument paragraphs about: {topic}.
Write approximately {body_words} words total in natural {ln}, separated into EXACTLY THREE paragraphs of about {para_words} words each:
Paragraph 1: first important argument with an explanation and relevant example.
Paragraph 2: second aspect or a balanced counter-view with relevant evidence.
Paragraph 3: a third point or a reasoned personal position.
Keep the content specific to the topic. Do not invent exact statistics. Output only those three paragraphs; no headings, numbering, bullet points, checklist, or writing advice. Use only {ln}. Reference notes:
{wb}"""
        body, body_ok = await generate_section("three main argument paragraphs", prompt_body, body_words, 1800)

        prompt_conclusion = f"""Write ONLY the concluding paragraph of an essay about: {topic}.
Use approximately {conclusion_words} words in natural {ln}. Briefly synthesize the arguments, restate the central idea in different words, and finish with a relevant conclusion or recommendation. Do not introduce a new topic or unsupported factual claim.
Output only one paragraph, no heading, list, numbering, checklist, or writing advice. Use only {ln}. Reference notes:
{wb}"""
        conclusion, conclusion_ok = await generate_section("concluding paragraph", prompt_conclusion, conclusion_words, 1000)

        used_fallback = not (intro_ok and body_ok and conclusion_ok)
        fallback_parts = _fallback_essay_parts(topic, lc)
        if not intro_ok:
            intro = fallback_parts[0]
        if not body_ok:
            body = "\n\n".join(fallback_parts[1:4])
        if not conclusion_ok:
            conclusion = fallback_parts[4]
        body = _normalize_three_paragraphs(body)

        result = (
            "[[ESSAY_INTRO]]\n" + clean_ai_text(intro) +
            "\n\n[[ESSAY_BODY]]\n" + clean_ai_text(body) +
            "\n\n[[ESSAY_CONCLUSION]]\n" + clean_ai_text(conclusion)
        )
        return result, not used_fallback

    pages = int(options.get("pages", 10) or 10)
    if service == "test":
        return await _generate_test(service, topic, options, lang)
        
    wiki = await wikipedia_fetch(topic, max_chars=10000 if service in LONG_SERVICES else 4000, full=(service in LONG_SERVICES), gen_lang=lang)
    outline = await _generate_outline(service, topic, pages, lang, wiki)
    full_text_parts, prev_summary, real_count, fail_count = [], "", 0, 0
    
    for sec_title, sec_pages, sec_desc in outline:
        sec_text = await _generate_section(service, topic, sec_title, sec_pages, sec_desc, lang, wiki, prev_summary)
        if "batafsil ma'lumot" in sec_text or sec_text.strip().startswith("⚠️"): fail_count += 1
        else: real_count += 1
        full_text_parts.append(sec_text); prev_summary = sec_text[:800]
        
    result = "\n\n".join(full_text_parts)
    real = real_count > 0 and fail_count <= len(outline) // 2
    if len(result) < pages * CHARS_PER_PAGE * 0.4:
        result += "\n\n" + _fallback_text(service, topic, options, lang, max(3, pages//3))
    return result, real

# ===== TEST GENERATSIYASI =====
async def _generate_test(service, topic, options, lang):
    count = int(options.get("questions", options.get("pages", 20)) or 20)
    wiki = await wikipedia_fetch(topic, max_chars=5000, gen_lang=lang)
    all_questions, chunk_size = [], 5
    for start in range(1, count + 1, chunk_size):
        end = min(count, start + chunk_size - 1)
        num_to_gen = end - start + 1
        prompt = f"Mavzu: {topic}. AYNAN {num_to_gen} ta test savolini yozing. Savollar {start} dan {end} gacha raqamlansin. Variantlar A) B) C) D) bo'lsin. To'g'ri javobni (✓) bilan belgilang. Faqat savollarni yozing. {wiki_block(wiki)}"
        txt = await _chat_complete(prompt, system=_pure_language_system(lang), max_tokens=3000)
        if txt and "⚠️" not in txt: 
            all_questions.append(txt)
        await asyncio.sleep(0.5)
    answer_key = {"uz": "JAVOBLAR KALITI: to‘g‘ri javob ✓ bilan belgilangan.", "ru": "КЛЮЧ ОТВЕТОВ: правильный вариант отмечен символом ✓.", "en": "ANSWER KEY: the correct option is marked with ✓.", "tr": "CEVAP ANAHTARI: doğru seçenek ✓ ile işaretlenmiştir.", "de": "LÖSUNGSSCHLÜSSEL: Die richtige Option ist mit ✓ markiert.", "fr": "CORRIGÉ : la bonne réponse est marquée par ✓."}.get(str(lang).lower(), "ANSWER KEY: the correct option is marked with ✓.")
    result = "\n\n".join(all_questions) + "\n\n" + answer_key
    return result, bool(all_questions)

# ====== SLAYDLAR GENERATSIYASI (Yangi shablonlar uchun QAT'IY struktura) ======
async def generate_slides_structured(topic, subject, lang, count):
    ln = _lang_name(lang)
    wiki = await wikipedia_fetch(topic, max_chars=5000, gen_lang=lang)
    wb = wiki_block(wiki)
    
    system = (_pure_language_system(lang) +
              f" Siz professional taqdimot tuzuvchisiz. Javobni FAQAT {ln} tilida yozing! "
              f"Javobni faqat JSON massiv ko'rinishida qaytaring.")

    prompt = f"""Topic: {topic}. Subject: {subject}.
Create exactly {count} CONTENT slides for a professional presentation. The title/cover slide is created separately by the PowerPoint template, so do not return a cover slide or a table-of-contents slide.

STRICT LANGUAGE RULES:
1. Write every title and every content sentence only in the selected language ({ln}).
2. Translate the topic and section headings into {ln} where appropriate. Keep proper names, official product names, and standard technical terms only when they should not be translated.
3. Do not insert Uzbek, English, Russian, or any other language as decoration or filler when it is not the selected language.
4. All slide titles, labels and sentences must be natural and grammatically correct in {ln}.

CONTENT RULES:
1. Return only a valid JSON array with exactly {count} objects.
2. Each object must contain the keys "title" and "content".
3. The content array must contain 3-5 concise, meaningful sentences suitable for a slide.
4. Cover distinct aspects such as background, concepts, evidence, practical uses, comparison and implications. Do not repeat the same generic text.
5. The final content slide must present a concise conclusion and practical recommendations in {ln}; make its title a natural localized equivalent of “Conclusion”.
6. Do not invent citations or claim a source was consulted unless the source is explicitly supplied.
7. If relevant dates or numbers are known, state them accurately.

Reference material (use only to check facts; do not copy its language if different from {ln}):
{wb}

JSON example (translate the example's sample wording into {ln} in the actual response):
[{{"title":"Section title","content":["Sentence one.","Sentence two.","Sentence three."]}}]"""

    txt = await _chat_complete(prompt, system=system, max_tokens=4500)
    parsed = _extract_json(txt)
    
    all_slides = []
    
    if parsed and isinstance(parsed, list):
        all_text = " ".join([str(s.get("title", "")) + " " + " ".join(s.get("content", [])) for s in parsed if isinstance(s, dict)])
        if _is_lang_mixed(all_text, lang):
            retry_txt = await _chat_complete(prompt + f"\nFINAL LANGUAGE CHECK: rewrite every title and sentence only in {ln}. Remove any phrases in other languages.", system=system, max_tokens=4500)
            retry_parsed = _extract_json(retry_txt)
            retry_text = " ".join([str(item.get("title", "")) + " " + " ".join(item.get("content", [])) for item in retry_parsed if isinstance(item, dict)]) if isinstance(retry_parsed, list) else ""
            if retry_parsed and isinstance(retry_parsed, list) and not _is_lang_mixed(retry_text, lang):
                parsed = retry_parsed
            else:
                parsed = None
            
        if parsed and isinstance(parsed, list):
            for s in parsed:
                if isinstance(s, dict):
                    cl = s.get("content", [])
                    if isinstance(cl, str): cl = [p.strip() for p in cl.split("\n") if p.strip()]
                    all_slides.append({
                        "title": clean_ai_text(str(s.get("title", f"Bo'lim {len(all_slides)+1}"))),
                        "content": [clean_ai_text(str(c)) for c in cl]
                    })
    
    # Keep count exact without inserting text from another language.
    used_fallback = not bool(all_slides)
    if not all_slides:
        all_slides = _fallback_slides(topic, count, lang)
    else:
        if len(all_slides) < count:
            used_fallback = True
        while len(all_slides) < count:
            idx = len(all_slides) + 1
            title_fallback, body_fallback = _localized_slide_fallback(topic, lang, idx)
            all_slides.append({"title": title_fallback, "content": body_fallback})
        all_slides = all_slides[:count]

    out = []
    for i, s in enumerate(all_slides):
        cl = s.get("content", [])
        if isinstance(cl, str): cl = [p.strip() for p in cl.split("\n") if p.strip()]
        while len(cl) < 3:
            _, body_fallback = _localized_slide_fallback(topic, lang, i + 1)
            cl.append(body_fallback[len(cl) % len(body_fallback)])
        
        out.append({
            "slide_number": i+1,
            "title": s.get("title", f"Bo'lim {i+1}"),
            "content": cl[:6],
            "wiki_source": wiki["url"] if wiki["found"] else None
        })
    return out, not used_fallback

SEARCH_MAP = {
    "alisher navoiy": "Alisher Navoi portrait poet", "navoiy": "Alisher Navoi writer poet",
    "amir temur": "Amir Timur Tamerlane conqueror", "temur": "Timur Tamerlane empire",
    "jaloliddin manguberdi": "Jalal ad-Din Manguberdi warrior", "mirzo ulugbek": "Ulugh Beg astronomer",
    "ibn sino": "Avicenna Ibn Sina physician", "samarqand": "Samarkand Registan square",
    "buxoro": "Bukhara old city", "hujayra": "biological cell microscope",
    "fotosintez": "photosynthesis plant leaf", "atom": "atom structure nucleus",
    "dnk": "DNA double helix genetics", "fizika": "physics laboratory",
    "kimyo": "chemistry laboratory flask", "biologiya": "biology science laboratory",
    "matematika": "mathematics formulas numbers", "geografiya": "geography globe map",
    "tarix": "history ancient civilization", "adabiyot": "literature books library",
    "informatika": "computer science coding", "iqtisod": "economy finance chart",
}
STOP_WORDS = {"portrait", "historical", "hero", "leader", "conqueror", "poet", "writer", "scholar", "astronomer", "city", "architecture", "culture", "landmark", "warrior", "prince", "scientist", "figure", "realistic", "photo", "ancient", "epic", "scene", "heritage", "monument", "legacy", "inspirational", "cinematic", "detailed", "photorealistic", "structure", "laboratory", "educational", "illustration", "microscope", "nucleus", "electrons"}

async def topic_to_english_keywords(topic):
    key = topic.lower().strip()
    if key in _KEYWORD_CACHE: return _KEYWORD_CACHE[key]
    for uz, en in SEARCH_MAP.items():
        if uz in key: _KEYWORD_CACHE[key] = en; return en
    try:
        txt = await _chat_complete(f"Rasm uchun inglizcha 3-5 kalit so'z. Faqat so'zlar: {topic}", system="You generate stock-photo keywords in English. Keywords only.", max_tokens=60)
        if txt and 3 < len(txt) < 150:
            kw = re.sub(r'[^a-zA-Z\s,]', '', txt).strip()
            if kw: _KEYWORD_CACHE[key] = kw; return kw
    except Exception: pass
    _KEYWORD_CACHE[key] = topic
    return topic

async def _wiki_image(topic):
    try:
        wiki = await wikipedia_fetch(topic, max_chars=200)
        if wiki.get("image"): return [{"url": wiki["image"], "tags": wiki["title"].lower(), "src": "wikipedia"}]
    except Exception: pass
    return []

async def _pixabay_images(query):
    if not PIXABAY_KEY: return []
    url = f"https://pixabay.com/api/?key={PIXABAY_KEY}&q={aiohttp.helpers.quote(query)}&image_type=photo&orientation=horizontal&per_page=40&safesearch=true&lang=en"
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=12)) as s:
            async with s.get(url) as r:
                if r.status != 200: return []
                data = await r.json()
        return [{"url": h.get("webformatURL"), "tags": (h.get("tags", "") + " " + str(h.get("user", ""))).lower(), "src": "pixabay"} for h in data.get("hits", []) if h.get("webformatURL")]
    except Exception: return []

async def _pexels_images(query):
    if not PEXELS_KEY: return []
    url = f"https://api.pexels.com/v1/search?query={aiohttp.helpers.quote(query)}&per_page=40&orientation=landscape"
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=12), headers={"Authorization": PEXELS_KEY}) as s:
            async with s.get(url) as r:
                if r.status != 200: return []
                data = await r.json()
        return [{"url": p.get("src", {}).get("large"), "tags": (str(p.get("alt", "")) + " " + str(p.get("photographer", ""))).lower(), "src": "pexels"} for p in data.get("photos", []) if p.get("src", {}).get("large")]
    except Exception: return []

async def _unsplash_images(query):
    if not UNSPLASH_KEY: return []
    url = f"https://api.unsplash.com/search/photos?query={aiohttp.helpers.quote(query)}&per_page=30&orientation=landscape"
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=12), headers={"Authorization": f"Client-ID {UNSPLASH_KEY}"}) as s:
            async with s.get(url) as r:
                if r.status != 200: return []
                data = await r.json()
        return [{"url": p.get("urls", {}).get("regular"), "tags": (str(p.get("alt_description", "")) + " " + str(p.get("description", ""))).lower(), "src": "unsplash"} for p in data.get("results", []) if p.get("urls", {}).get("regular")]
    except Exception: return []

async def search_images(query, count=5):
    q = re.sub(r'[^\w\s\']', ' ', str(query)).strip()
    if len(q) < 3: return []
    keywords = await topic_to_english_keywords(q)
    kw_list = [w for w in keywords.lower().split() if len(w) > 2 and w not in STOP_WORDS]
    results = await asyncio.gather(_wiki_image(q), _pixabay_images(keywords), _pexels_images(keywords), _unsplash_images(keywords))
    candidates, seen = [], set()
    for group in results:
        for c in group:
            u = c["url"]
            if not u or u in seen: continue
            seen.add(u)
            mos = sum(1 for kw in kw_list if kw in c["tags"]) if kw_list else 1
            if c["src"] == "wikipedia": mos += 10 # Vikipediya rasmlari ustuvor
            candidates.append((mos, u))
    candidates.sort(key=lambda x: -x[0])
    urls = [u for mos, u in candidates if mos > 0][:count]
    return urls

async def download_image(url, save_path):
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    with open(save_path, "wb") as f: f.write(await resp.read())
                    return True
    except Exception: pass
    return False

async def _try_post(api, model, payload):
    global LAST_ERROR
    if not api["api_key"]:
        LAST_ERROR = f"Kalit yo'q: {api['name']}"; return None, None, LAST_ERROR
    try:
        if api["type"] == "google":
            url = f"{api['base_url']}/models/{model}:generateContent?key={api['api_key']}"
            messages = payload.get("messages", [])
            system_text = "\n".join(
                str(item.get("content", "")) for item in messages
                if item.get("role") == "system" and item.get("content")
            ).strip()
            user_messages = [item for item in messages if item.get("role") != "system"]
            contents = [
                {"role": "user" if item.get("role") != "assistant" else "model",
                 "parts": [{"text": str(item.get("content", ""))}]}
                for item in user_messages if item.get("content")
            ]
            data = {"contents": contents}
            if system_text:
                data["systemInstruction"] = {"parts": [{"text": system_text}]}
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=AI_TIMEOUT)) as session:
                async with session.post(url, json=data, timeout=AI_TIMEOUT) as resp:
                    body = await resp.text()
                    if resp.status == 200:
                        LAST_ERROR = None
                        try: return 200, json.loads(body)["candidates"][0]["content"]["parts"][0]["text"], None
                        except Exception as e: return resp.status, None, str(e)
                    return resp.status, None, f"HTTP {resp.status}"
        else:
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api['api_key']}"}
            url = f"{api['base_url']}/chat/completions"
            p = dict(payload); p["model"] = model
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=AI_TIMEOUT)) as session:
                async with session.post(url, headers=headers, json=p, timeout=AI_TIMEOUT) as resp:
                    body = await resp.text()
                    if resp.status == 200:
                        LAST_ERROR = None
                        try: return 200, json.loads(body)["choices"][0]["message"]["content"], None
                        except Exception as e: return resp.status, None, str(e)
                    return resp.status, None, f"HTTP {resp.status}"
    except Exception as e: return None, None, str(e)

async def _chat_complete(prompt, system=None, max_tokens=2500):
    messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
    payload = {
        "messages": messages, 
        "temperature": 0.5, 
        "max_tokens": max_tokens,
        "frequency_penalty": 0.7,
        "presence_penalty": 0.5
    }
    start = CURRENT_API_INDEX
    while True:
        api = get_current_api(); model = get_current_model()
        if not api["api_key"]:
            switch_to_next_api()
            if CURRENT_API_INDEX == start: break
            continue
        status, text, err = await _try_post(api, model, payload)
        if status == 200 and text:
            return clean_ai_text(text).strip()
        if status == 429: await asyncio.sleep(2.0)
        if not switch_to_next_model() and CURRENT_API_INDEX == start: break
        await asyncio.sleep(0.5)
    return "⚠️ AI serverga ulanib bo'lmadi."

CHAT_AUTO_LANGUAGE_SYSTEM = """You are a helpful multilingual AI assistant.
IMPORTANT LANGUAGE RULE: Determine the language of the user's latest message and answer in that same language, using the same script and a natural level of formality. The bot interface language and these system instructions do not determine the response language.
If the user explicitly asks you to translate something or to answer in a different language, follow that explicit request. Otherwise, do not switch languages and do not default to Uzbek.
Answer the actual question or task. If the user provides a long text, analyze the whole available text instead of treating words inside it as menu commands. Preserve requested structure, examples, and level of detail. Do not claim that you processed parts that were not provided. Use readable formatting and avoid unnecessary repetition."""

async def chat_answer(question, user_lang="uz"):
    q = str(question or "").strip()
    if not q:
        return None
    # Telegram message bodies are normally capped around 4096 characters. Keep a safety limit
    # for other clients without appending a notice in a different language.
    if len(q) > 12000:
        q = q[:12000]
    ans = await _chat_complete(q, system=CHAT_AUTO_LANGUAGE_SYSTEM, max_tokens=4000)
    return ans if ans and not ans.startswith("⚠️") else None

async def test_api():
    lines = []
    for api in API_LIST:
        if not api["api_key"]: lines.append(f"❌ {api['name']}: kalit yo'q"); continue
        for model in api["models"]:
            status, text, err = await _try_post(api, model, {"messages": [{"role": "user", "content": "OK"}], "temperature": 0.1, "max_tokens": 10})
            if status == 200 and text:
                lines.append(f"✅ {api['name']}: ishlaydi → {model}")
                break
        else: lines.append(f"❌ {api['name']}: ishlamadi")
    return "\n".join(lines)

def _extract_json(text):
    if not text: return None
    m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, flags=re.DOTALL)
    if m:
        try: return json.loads(m.group(1))
        except Exception: pass
    start, end = text.find("["), text.rfind("]")
    if start != -1 and end > start:
        try: return json.loads(text[start:end+1])
        except Exception: pass
    return None

# ===== 6 TIL UCHUN ZAXIRA (FALLBACK) =====
FB = {
    "uz": {"sections": ["Kirish", "Tarixiy kelib chiqishi", "Asosiy qism 1", "Asosiy qism 2", "Tahlil", "Xulosa"],
        "slide_sections": ["Kirish", "Tarix", "Tahlil", "Natijalar", "Xulosa"]},
    "ru": {"sections": ["Введение", "История", "Основная часть 1", "Основная часть 2", "Анализ", "Заключение"],
        "slide_sections": ["Введение", "История", "Анализ", "Результаты", "Заключение"]},
    "en": {"sections": ["Introduction", "Background", "Main part 1", "Main part 2", "Analysis", "Conclusion"],
        "slide_sections": ["Introduction", "Background", "Analysis", "Results", "Conclusion"]},
    "tr": {"sections": ["Giriş", "Tarihçe", "Ana Kısım 1", "Ana Kısım 2", "Analiz", "Sonuç"],
        "slide_sections": ["Giriş", "Tarih", "Analiz", "Sonuçlar", "Sonuç"]},
    "de": {"sections": ["Einleitung", "Geschichte", "Hauptteil 1", "Hauptteil 2", "Analyse", "Fazit"],
        "slide_sections": ["Einleitung", "Geschichte", "Analyse", "Ergebnisse", "Fazit"]},
    "fr": {"sections": ["Introduction", "Histoire", "Partie principale 1", "Partie principale 2", "Analyse", "Conclusion"],
        "slide_sections": ["Introduction", "Histoire", "Analyse", "Résultats", "Conclusion"]}
}
def _fb(lang):
    return FB.get(str(lang).lower(), FB["en"])


_FALLBACK_COPY = {
    "uz": {"part": "Qism", "body": "Ushbu bo‘lim mavzuning muhim jihatlarini yoritadi.", "analysis": "Asosiy dalillar va amaliy misollar tahlil qilinadi.", "relevance": "Mavzuning ahamiyati va mumkin bo‘lgan qo‘llanilishi ko‘rib chiqiladi.", "contents": "Mundarija", "conclusion": "Xulosa"},
    "ru": {"part": "Раздел", "body": "В этом разделе раскрываются важные аспекты темы.", "analysis": "Анализируются основные аргументы и практические примеры.", "relevance": "Рассматриваются значение темы и возможные области применения.", "contents": "Содержание", "conclusion": "Заключение"},
    "en": {"part": "Section", "body": "This section explains important aspects of the topic.", "analysis": "Key arguments and practical examples are analyzed.", "relevance": "The topic’s significance and possible applications are discussed.", "contents": "Contents", "conclusion": "Conclusion"},
    "tr": {"part": "Bölüm", "body": "Bu bölüm konunun önemli yönlerini açıklar.", "analysis": "Temel savlar ve uygulamalı örnekler incelenir.", "relevance": "Konunun önemi ve olası kullanım alanları ele alınır.", "contents": "İçindekiler", "conclusion": "Sonuç"},
    "de": {"part": "Abschnitt", "body": "Dieser Abschnitt erläutert wichtige Aspekte des Themas.", "analysis": "Zentrale Argumente und praktische Beispiele werden analysiert.", "relevance": "Die Bedeutung des Themas und mögliche Anwendungen werden erörtert.", "contents": "Inhalt", "conclusion": "Fazit"},
    "fr": {"part": "Section", "body": "Cette section présente les aspects importants du sujet.", "analysis": "Les arguments clés et les exemples pratiques sont analysés.", "relevance": "L’importance du sujet et ses applications possibles sont examinées.", "contents": "Sommaire", "conclusion": "Conclusion"},
}


def _localized_slide_fallback(topic, lang, index=1):
    loc = _FALLBACK_COPY.get(str(lang).lower(), _FALLBACK_COPY["en"])
    if index == 1:
        title = loc["part"] + " 1"
    else:
        title = f"{loc['part']} {index}"
    return title, [f"{topic}: {loc['body']}", loc["analysis"], loc["relevance"]]


def _fallback_text(service, topic, options, lang, bob_count=10):
    fb = _fb(lang)
    loc = _FALLBACK_COPY.get(str(lang).lower(), _FALLBACK_COPY["en"])
    sections = list(fb["sections"])
    while len(sections) < bob_count:
        sections.insert(max(0, len(sections) - 2), loc["part"])
    return f"{topic}\n\n" + "\n\n".join(f"{section}\n{topic}: {loc['body']} {loc['analysis']}" for section in sections[:bob_count])


def _fallback_slides(topic, count, lang):
    fb = _fb(lang)
    loc = _FALLBACK_COPY.get(str(lang).lower(), _FALLBACK_COPY["en"])
    out = []
    for i in range(count):
        if i == 0:
            title = topic
        elif i == 1:
            title = loc["contents"]
        elif i == count - 1:
            title = loc["conclusion"]
        else:
            title = fb["slide_sections"][i % len(fb["slide_sections"])]
        _, content = _localized_slide_fallback(topic, lang, i + 1)
        out.append({"slide_number": i + 1, "title": title, "content": content})
    return out
