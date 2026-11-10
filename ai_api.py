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
import time

import academic
import os
import io
from collections import Counter
from dotenv import load_dotenv
load_dotenv()
from config import AI_API_URL, AI_API_KEY, AI_MODEL, AI_TIMEOUT, GEN_TIMEOUT, DATA_DIR

LAST_ERROR = "hali sinanmadi"
PIXABAY_KEY  = os.getenv("PIXABAY_KEY", "")
PEXELS_KEY   = os.getenv("PEXELS_KEY", "")
UNSPLASH_KEY = os.getenv("UNSPLASH_KEY", "")
USER_AGENT = ("TalabaAISlideBot/1.0 (educational presentation image retrieval; "
               "https://github.com/abdullayevsadriddin2009/aislide)")

_KEYWORD_CACHE = {}
CHARS_PER_PAGE = 1650
MAX_CHUNK_PAGES = 3
LONG_SERVICES = ("diplom", "kurs", "referat", "maqola")

API_LIST = [
    {
        "name": "Groq 1 (asosiy)",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key": os.getenv("GROQ_KEY_1", ""),
        "type": "openai",
        "models": ["qwen/qwen3.8-27b", "allam-2-7b", "openai/gpt-oss-120b", "openai/gpt-oss-20b"]
    },
    {
        "name": "Groq 2",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key": os.getenv("GROQ_KEY_2", ""),
        "type": "openai",
        "models": ["qwen/qwen3.8-27b", "allam-2-7b", "openai/gpt-oss-120b", "openai/gpt-oss-20b"]
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

def _primary_api():
    """The provider the admin configured with AI_BASE_URL / AI_API_KEY / AI_MODEL.

    Those three variables were documented in render.yaml and .env.example but were
    never part of the failover list, so a bot with only them configured answered
    "AI serverga ulanib bo'lmadi" even though its key was valid.
    """
    base = str(AI_API_URL or "").strip()
    if not AI_API_KEY or not base:
        return None
    model = str(AI_MODEL or "").strip()
    return {
        "name": "Asosiy AI (AI_BASE_URL)",
        "base_url": base.rstrip("/"),
        "api_key": AI_API_KEY,
        "type": "openai",
        "models": [model] if model and model.lower() != "auto" else [],
    }


_primary_api_config = _primary_api()
if _primary_api_config:
    API_LIST.insert(0, _primary_api_config)

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

_LANGUAGE_MARKERS = {
    "uz": {"va", "bu", "bilan", "uchun", "ham", "esa", "ammo", "biroq", "uning", "ular", "kerak", "mumkin", "orqali", "shuning", "sababli", "hisoblanadi", "kabi", "edi", "qiladi", "etadi", "bo'lib", "hamda", "muhim", "tarixda", "davrda", "natijada", "birinchi", "ikkinchi", "xulosa", "inson", "jamiyat", "mavzu", "rivojlanish"},
    "en": _EN_STOP,
    "tr": {"ve", "bir", "bu", "için", "ile", "olarak", "ancak", "ayrıca", "çünkü", "olan", "göre", "gibi", "daha", "çok", "önemli", "gerekir", "konu", "etkisi", "nedeniyle", "sonuç", "üzerinde"},
    "de": {"der", "die", "das", "und", "ist", "für", "mit", "auch", "als", "auf", "im", "den", "ein", "eine", "werden", "deshalb", "wichtig", "weil", "dass", "thema", "sowie", "durch"},
    "fr": {"le", "la", "les", "et", "est", "de", "des", "un", "une", "pour", "avec", "dans", "qui", "que", "mais", "ainsi", "important", "parce", "sujet", "également", "donc"},
}


def _is_lang_mixed(text, lang):
    """Detect obvious language leakage and likely wrong-language Latin output.

    Short proper names are tolerated, while normal paragraph-length text is
    checked using script proportions and stop-word markers for the six supported
    languages. The detector is intentionally conservative for very short text.
    """
    raw = str(text or "").strip()
    lc = str(lang or "uz").lower()
    if not raw:
        return True
    if lc not in ALL_LANGS:
        lc = "en"

    letters = max(1, sum(ch.isalpha() for ch in raw))
    cyr_ratio = sum(bool(re.match(r"[А-Яа-яЁё]", ch)) for ch in raw) / letters
    arabic_ratio = sum("\u0600" <= ch <= "\u06ff" for ch in raw) / letters
    if lc == "ru" and cyr_ratio < 0.20:
        return True
    if lc != "ru" and cyr_ratio > 0.10:
        return True
    if arabic_ratio > 0.03:
        return True

    # A substantial English stop-word ratio reliably catches English text sent
    # to a non-English locale, while tolerating isolated technical terms/names.
    enr = _english_ratio(raw)
    if lc != "en" and enr >= 0.08:
        return True

    tokens = re.findall(r"[^\W_]+(?:[’'-][^\W_]+)*", raw.casefold(), flags=re.UNICODE)
    if len(tokens) >= 12 and lc in _LANGUAGE_MARKERS:
        scores = {code: sum(1 for token in tokens if token in markers)
                  for code, markers in _LANGUAGE_MARKERS.items()}
        target_score = scores.get(lc, 0)
        alternatives = [(code, score) for code, score in scores.items() if code != lc]
        other_code, other_score = max(alternatives, key=lambda pair: pair[1], default=(None, 0))
        # If another language has several clear function/content words and the
        # target language has almost none, reject and let the repair prompt run.
        if other_score >= 3 and other_score >= target_score + 2 and target_score < 4:
            return True
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
        meta_reply = bool(re.search(
            r"(?:no text (?:was )?provided|please provide (?:the )?(?:text|title)|nothing to translate|"
            r"matn (?:yoki sarlavha )?taqdim etilmagan|переводить нечего|текст не предоставлен|"
            r"kein text angegeben|aucun texte fourni)", result, flags=re.I
        ))
        if (result and not result.startswith("⚠️") and not meta_reply
                and len(result) <= max(250, len(original) * 4)
                and not _is_lang_mixed(result, lc)):
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

def wiki_block(wiki, lang="uz"):
    """Localized source wrapper; the source text itself is used only for facts."""
    if not isinstance(wiki, dict) or not wiki.get("found"):
        return ""
    labels = {
        "uz": ("MA'LUMOT MANBASI", "Sarlavha", "Faqat tekshirish mumkin bo‘lgan faktlardan foydalaning; manba tilini ko‘chirmang"),
        "ru": ("СПРАВОЧНЫЕ СВЕДЕНИЯ", "Заголовок", "Используйте только проверяемые факты; не копируйте язык источника"),
        "en": ("REFERENCE NOTES", "Title", "Use only verifiable facts; do not copy the source language"),
        "tr": ("KAYNAK NOTLARI", "Başlık", "Yalnızca doğrulanabilir bilgileri kullanın; kaynak dilini kopyalamayın"),
        "de": ("QUELLENHINWEISE", "Titel", "Verwenden Sie nur überprüfbare Fakten; übernehmen Sie nicht die Quellensprache"),
        "fr": ("NOTES DE RÉFÉRENCE", "Titre", "N’utilisez que des faits vérifiables et ne copiez pas la langue de la source"),
    }
    title, heading, instruction = labels.get(str(lang).lower(), labels["en"])
    return f"\n\n=== {title} ===\n{heading}: {wiki.get('title', '')}\n{instruction}:\n{wiki.get('text', '')}\n"

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

_BODY_SECTION_MAP = {
    "referat": [
        {"uz":"Asosiy tushunchalar va tarixiy sharoit", "ru":"Основные понятия и исторический контекст", "en":"Core concepts and historical context", "tr":"Temel kavramlar ve tarihsel bağlam", "de":"Grundbegriffe und historischer Kontext", "fr":"Notions essentielles et contexte historique"},
        {"uz":"Nazariy asoslar va dalillar", "ru":"Теоретические основы и доказательства", "en":"Theoretical foundations and evidence", "tr":"Kuramsal temeller ve kanıtlar", "de":"Theoretische Grundlagen und Belege", "fr":"Fondements théoriques et éléments de preuve"},
        {"uz":"Tahlil, misollar va amaliy ahamiyat", "ru":"Анализ, примеры и практическое значение", "en":"Analysis, examples, and practical relevance", "tr":"Analiz, örnekler ve pratik önem", "de":"Analyse, Beispiele und praktische Bedeutung", "fr":"Analyse, exemples et portée pratique"},
    ],
    "mustaqil": [
        {"uz":"Mavzuning mazmuni va asosiy masalalar", "ru":"Содержание темы и основные вопросы", "en":"Topic overview and main questions", "tr":"Konunun kapsamı ve temel sorular", "de":"Themenüberblick und zentrale Fragen", "fr":"Présentation du sujet et questions principales"},
        {"uz":"Muammolar va tahliliy yondashuv", "ru":"Проблемы и аналитический подход", "en":"Problems and analytical approach", "tr":"Sorunlar ve analitik yaklaşım", "de":"Probleme und analytischer Ansatz", "fr":"Problèmes et approche analytique"},
        {"uz":"Misollar va amaliy yechimlar", "ru":"Примеры и практические решения", "en":"Examples and practical solutions", "tr":"Örnekler ve pratik çözümler", "de":"Beispiele und praktische Lösungen", "fr":"Exemples et solutions pratiques"},
    ],
    "kurs": [
        {"uz":"Nazariy asoslar va ilmiy qarashlar", "ru":"Теоретические основы и научные подходы", "en":"Theoretical foundations and scholarly approaches", "tr":"Kuramsal temeller ve bilimsel yaklaşımlar", "de":"Theoretische Grundlagen und wissenschaftliche Ansätze", "fr":"Fondements théoriques et approches scientifiques"},
        {"uz":"Amaliy holat va muammoning tahlili", "ru":"Практическая ситуация и анализ проблемы", "en":"Practical context and problem analysis", "tr":"Uygulama durumu ve sorun analizi", "de":"Praxisbezug und Problemanalyse", "fr":"Contexte pratique et analyse du problème"},
        {"uz":"Natijalar, takliflar va samaradorlik", "ru":"Результаты, предложения и эффективность", "en":"Findings, recommendations, and effectiveness", "tr":"Bulgular, öneriler ve etkililik", "de":"Ergebnisse, Empfehlungen und Wirksamkeit", "fr":"Résultats, recommandations et efficacité"},
    ],
    "diplom": [
        {"uz":"Tadqiqotning nazariy va metodologik asoslari", "ru":"Теоретические и методологические основы исследования", "en":"Theoretical and methodological foundations", "tr":"Araştırmanın kuramsal ve yöntemsel temelleri", "de":"Theoretische und methodische Grundlagen", "fr":"Fondements théoriques et méthodologiques"},
        {"uz":"Muammo, dalillar va natijalar tahlili", "ru":"Анализ проблемы, доказательств и результатов", "en":"Analysis of the problem, evidence, and findings", "tr":"Sorun, kanıt ve bulguların analizi", "de":"Analyse des Problems, der Belege und Ergebnisse", "fr":"Analyse du problème, des preuves et des résultats"},
        {"uz":"Amaliy yechimlar va tavsiyalar", "ru":"Практические решения и рекомендации", "en":"Practical solutions and recommendations", "tr":"Pratik çözümler ve öneriler", "de":"Praktische Lösungen und Empfehlungen", "fr":"Solutions pratiques et recommandations"},
    ],
    "maqola": [
        {"uz":"Mavzuning ilmiy asoslari", "ru":"Научные основы темы", "en":"Scientific background of the topic", "tr":"Konunun bilimsel temelleri", "de":"Wissenschaftliche Grundlagen des Themas", "fr":"Fondements scientifiques du sujet"},
        {"uz":"Tahlil va asosiy natijalar", "ru":"Анализ и основные результаты", "en":"Analysis and key findings", "tr":"Analiz ve temel bulgular", "de":"Analyse und zentrale Ergebnisse", "fr":"Analyse et principaux résultats"},
        {"uz":"Muhokama va amaliy ahamiyat", "ru":"Обсуждение и практическое значение", "en":"Discussion and practical implications", "tr":"Tartışma ve pratik sonuçlar", "de":"Diskussion und praktische Auswirkungen", "fr":"Discussion et implications pratiques"},
    ],
    "tezis": [
        {"uz":"Asosiy g‘oyalar va dalillar", "ru":"Основные идеи и доказательства", "en":"Main ideas and evidence", "tr":"Temel fikirler ve kanıtlar", "de":"Kernaussagen und Belege", "fr":"Idées principales et éléments de preuve"},
        {"uz":"Tahlil va yakuniy natijalar", "ru":"Анализ и итоговые результаты", "en":"Analysis and key outcomes", "tr":"Analiz ve temel sonuçlar", "de":"Analyse und zentrale Ergebnisse", "fr":"Analyse et résultats essentiels"},
    ],
}

_BODY_SECTION_DESC = {
    "uz": "Mazmunni mavzuga xos aniq izohlar, tekshiriladigan faktlar va mos misollar bilan batafsil yoritish; boshqa bo‘limlarni takrorlamaslik.",
    "ru": "Подробно раскрыть содержание с конкретными пояснениями, проверяемыми фактами и уместными примерами; не повторять другие разделы.",
    "en": "Explain the topic in detail with specific reasoning, verifiable facts, and relevant examples; do not repeat other sections.",
    "tr": "Konuyu somut açıklamalar, doğrulanabilir bilgiler ve uygun örneklerle ayrıntılı ele alın; diğer bölümleri tekrarlamayın.",
    "de": "Behandeln Sie das Thema ausführlich mit konkreten Erläuterungen, überprüfbaren Fakten und passenden Beispielen; wiederholen Sie keine anderen Abschnitte.",
    "fr": "Développez le sujet à l’aide d’explications précises, de faits vérifiables et d’exemples pertinents, sans répéter les autres sections.",
}

async def _generate_outline(service, topic, pages, lang, wiki):
    """Outline only substantive body sections; cover, contents, intro, conclusion and references are generated separately in DOCX."""
    lc = str(lang or "uz").lower()
    sections = _BODY_SECTION_MAP.get(service, _BODY_SECTION_MAP["referat"])
    names = [item.get(lc, item["en"]) for item in sections]
    total_pages = max(len(names), int(pages or len(names)))
    base, extra = divmod(total_pages, len(names))
    desc = _BODY_SECTION_DESC.get(lc, _BODY_SECTION_DESC["en"])
    outline = []
    for i, name in enumerate(names):
        allocated = base + (1 if i < extra else 0)
        outline.append((name, max(1, allocated), desc))
    return outline

def _document_text_is_repetitive(text):
    """Reject common LLM looping output before it is saved into a document."""
    raw = clean_ai_text(str(text or ""))
    words = re.findall(r"[^\W_]+(?:[’'-][^\W_]+)*", raw.casefold(), flags=re.UNICODE)
    if len(words) >= 45 and len(set(words)) / max(1, len(words)) < 0.42:
        return True
    if len(words) >= 36:
        grams = Counter(tuple(words[i:i + 7]) for i in range(len(words) - 6))
        if grams and max(grams.values()) >= 3:
            return True
    sentences = [re.sub(r"\W+", " ", x.casefold()).strip()
                 for x in re.split(r"(?<=[.!?؟])\s+|\n+", raw) if len(x.split()) >= 7]
    counts = Counter(sentences)
    if counts and max(counts.values()) >= 3:
        return True
    return False


async def _generate_section(service, topic, sec_title, sec_pages, sec_desc, lang, wiki, prev_summary, chars_per_page=None):
    """Generate a section in the chosen language and reject language leaks/LLM loops."""
    capacity = int(chars_per_page or CHARS_PER_PAGE)
    sec_pages = max(1, int(math.ceil(float(sec_pages or 1))))
    chunks_needed = (sec_pages + MAX_CHUNK_PAGES - 1) // MAX_CHUNK_PAGES
    parts, local_prev = [], prev_summary
    lc = str(lang or "uz").lower()
    prompt_labels = {
        "uz": ("Xizmat", "Mavzu", "Bo‘lim", "Qism", "Oldingi matn", "Faqat tanlangan tilda yangi, tabiiy va takrorlanmaydigan mazmun yozing."),
        "ru": ("Услуга", "Тема", "Раздел", "Часть", "Предыдущий текст", "Пишите только на выбранном языке, естественно, содержательно и без повторов."),
        "en": ("Service", "Topic", "Section", "Part", "Previous text", "Write only in the selected language, naturally, with specific information and no repetition."),
        "tr": ("Hizmet", "Konu", "Bölüm", "Kısım", "Önceki metin", "Yalnızca seçilen dilde doğal, özgün ve tekrarsız içerik yazın."),
        "de": ("Dienst", "Thema", "Abschnitt", "Teil", "Vorheriger Text", "Schreiben Sie nur in der gewählten Sprache, natürlich, konkret und ohne Wiederholungen."),
        "fr": ("Service", "Sujet", "Section", "Partie", "Texte précédent", "Rédigez uniquement dans la langue choisie, de façon naturelle, précise et sans répétitions."),
    }
    service_label, topic_label, section_label, part_label, prev_label, instruction = prompt_labels.get(lc, prompt_labels["en"])
    for ch in range(chunks_needed):
        chunk_pages = min(MAX_CHUNK_PAGES, sec_pages - ch * MAX_CHUNK_PAGES)
        chunk_target = int(chunk_pages * capacity * 0.96)
        part_instructions = {
            "uz": f"{part_label} {ch+1}. Taxminan {chunk_target} belgi hajmida yozing; keraksiz takror va umumiy gaplarni ko‘paytirmang.",
            "ru": f"{part_label} {ch+1}. Напишите примерно {chunk_target} символов; не заполняйте объём повторами и общими фразами.",
            "en": f"{part_label} {ch+1}. Write about {chunk_target} characters; do not inflate length with repeated or generic sentences.",
            "tr": f"{part_label} {ch+1}. Yaklaşık {chunk_target} karakter yazın; uzunluğu tekrarlarla doldurmayın.",
            "de": f"{part_label} {ch+1}. Schreiben Sie etwa {chunk_target} Zeichen; füllen Sie den Umfang nicht mit Wiederholungen.",
            "fr": f"{part_label} {ch+1}. Rédigez environ {chunk_target} caractères; n’allongez pas le texte par des répétitions.",
        }
        prompt = (
            f"{topic_label}: {topic}\n{section_label}: {sec_title} ({sec_desc})\n"
            f"{part_instructions.get(lc, part_instructions['en'])}\n"
            f"{prev_label} (avoid repeating): {local_prev[:600]}\n"
            f"{wiki_block(wiki, lc)}\n\n{instruction}\n"
            "Fill the requested volume completely with specific, topic-related content and do not stop early "
            "or leave the text unfinished. Every paragraph must add new information; never pad with repetition, "
            "generic filler or questions.\n"
            f"Do not output a title page, table of contents, source notes, instructions, or explanations about the task."
        )
        txt = await _chat_complete(prompt, system=_pure_language_system(lc), max_tokens=4096)
        invalid = (not txt or str(txt).startswith("⚠️") or _is_lang_mixed(txt, lc) or _document_text_is_repetitive(txt))
        if invalid:
            repair_instructions = {
                "uz": "Matnni boshidan faqat tabiiy o‘zbek tilida qayta yozing. Takrorlangan jumlalarni, tarjima izohlarini va boshqa til parchalarini olib tashlang.",
                "ru": "Перепишите с нуля только на естественном русском языке. Удалите повторы, пояснения к переводу и фрагменты других языков.",
                "en": "Rewrite from scratch in natural English only. Remove repeated sentences, translation commentary, and other-language fragments.",
                "tr": "Metni baştan yalnızca doğal Türkçe ile yazın. Tekrarları, çeviri açıklamalarını ve diğer dillerdeki parçaları kaldırın.",
                "de": "Schreiben Sie den Text neu und ausschließlich auf natürlichem Deutsch. Entfernen Sie Wiederholungen, Übersetzungskommentare und fremdsprachige Passagen.",
                "fr": "Réécrivez le texte en français naturel uniquement. Supprimez les répétitions, les commentaires de traduction et les passages dans d’autres langues.",
            }
            txt2 = await _chat_complete(
                prompt + "\n" + repair_instructions.get(lc, repair_instructions["en"]),
                system=_pure_language_system(lc), max_tokens=4096, temperature=0.2,
                frequency_penalty=0.8, presence_penalty=0.6,
            )
            if txt2 and not str(txt2).startswith("⚠️") and not _is_lang_mixed(txt2, lc) and not _document_text_is_repetitive(txt2):
                txt = txt2
            else:
                loc = _FALLBACK_COPY.get(lc, _FALLBACK_COPY["en"])
                # Short localized fallback rather than exposing corrupted AI text.
                txt = f"{sec_title}. {topic}. {loc['body']} {loc['analysis']} {loc['relevance']}"
        parts.append(clean_ai_text(txt))
        local_prev = clean_ai_text(txt)[:600]
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


def _normalize_two_paragraphs(text):
    """Esse asosiy qismini ikkita mazmunli abzasga keltiradi."""
    parts = [p.strip() for p in re.split(r"\n\s*\n|\n", clean_ai_text(text or "")) if p.strip()]
    if len(parts) == 2:
        return "\n\n".join(parts)
    if len(parts) > 2:
        half = (len(parts) + 1) // 2
        return "\n\n".join((" ".join(parts[:half]), " ".join(parts[half:])))
    whole = " ".join(parts)
    sentences = [x.strip() for x in re.split(r"(?<=[.!?])\s+", whole) if x.strip()]
    if len(sentences) >= 2:
        half = (len(sentences) + 1) // 2
        return "\n\n".join((" ".join(sentences[:half]), " ".join(sentences[half:])))
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
    wb = wiki_block(wiki, lc)
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
# ===== MUSTAQIL ISH: to'liq strukturaviy mazmun (yangi shablon) =====
# Hujjat tuzilishi: Titul → Mundarija → Kirish (dolzarblik/maqsad/vazifalar) →
# I bob (1.1, 1.2) → II bob (2.1, 2.2) → Xulosa → Adabiyotlar.
_MQ_PLAN = {
    "uz": [
        ("KIRISH", "Kirish", "Mavzuning dolzarbligi, ishning maqsadi va vazifalari. Uchta alohida xatboshi yozilsin va ular aynan «Mavzuning dolzarbligi:», «Ishning maqsadi:», «Ishning vazifalari:» so‘zlari bilan boshlansin."),
        ("1.1", "I bob, 1.1-band: mavzuning mohiyati va ilmiy tushunchalari", "Mavzuning mohiyati, asosiy tushunchalar, ta’riflar va ilmiy qarashlar batafsil yoritilsin."),
        ("1.2", "I bob, 1.2-band: xorijiy tajribalar va adabiyotlar tahlili", "Xorijiy davlatlar tajribasi va ilmiy adabiyotlar tahlili keltirilsin."),
        ("2.1", "II bob, 2.1-band: bugungi kundagi holat va statistik tahlillar", "Bugungi kundagi holat aniq yillar, raqamlar va statistik ko‘rsatkichlar bilan tahlil qilinsin."),
        ("2.2", "II bob, 2.2-band: sohani rivojlantirishdagi muammolar va yechimlar", "Mavjud muammolar va ularni bartaraf etish bo‘yicha aniq amaliy takliflar bayon etilsin."),
        ("XULOSA", "Xulosa", "«Mavzuni o‘rganib chiqib, quyidagi xulosalarga keldim:» jumlasi bilan boshlanib, 5-6 ta raqamlangan xulosa yozilsin."),
    ],
    "ru": [
        ("KIRISH", "Введение", "Актуальность темы, цель и задачи работы. Три отдельных абзаца, начинающихся словами «Актуальность темы:», «Цель работы:», «Задачи исследования:»."),
        ("1.1", "Глава I, пункт 1.1: сущность темы и основные научные понятия", "Подробно раскрыть сущность темы, основные понятия, определения и научные подходы."),
        ("1.2", "Глава I, пункт 1.2: зарубежный опыт и анализ литературы", "Привести опыт зарубежных стран и анализ научной литературы."),
        ("2.1", "Глава II, пункт 2.1: современное состояние и статистический анализ", "Проанализировать текущее состояние с конкретными годами, цифрами и статистическими показателями."),
        ("2.2", "Глава II, пункт 2.2: проблемы развития сферы и пути их решения", "Изложить существующие проблемы и конкретные практические предложения по их решению."),
        ("XULOSA", "Заключение", "Начать словами «Изучив тему, я пришёл к следующим выводам:» и привести 5-6 пронумерованных выводов."),
    ],
    "en": [
        ("KIRISH", "Introduction", "Relevance of the topic, the goal of the work and its tasks. Three separate paragraphs beginning exactly with “Relevance of the topic:”, “Goal of the work:”, “Tasks completed:”."),
        ("1.1", "Chapter I, section 1.1: the essence of the topic and key scientific concepts", "Explain the essence of the topic, core concepts, definitions and scholarly approaches in detail."),
        ("1.2", "Chapter I, section 1.2: international experience and literature review", "Present the experience of other countries and an analysis of the scientific literature."),
        ("2.1", "Chapter II, section 2.1: current situation and statistical analysis", "Analyse the current situation with specific years, figures and statistical indicators."),
        ("2.2", "Chapter II, section 2.2: development problems and their solutions", "State the existing problems and concrete practical recommendations for solving them."),
        ("XULOSA", "Conclusion", "Begin with “Having studied the topic, I have come to the following conclusions:” and give 5-6 numbered conclusions."),
    ],
    "tr": [
        ("KIRISH", "Giriş", "Konunun güncelliği, çalışmanın amacı ve görevleri. Üç ayrı paragraf «Konu güncelliği:», «Çalışmanın amacı:», «Yapılan görevler:» ifadeleriyle başlasın."),
        ("1.1", "I. bölüm, 1.1: konunun özü ve temel bilimsel kavramlar", "Konunun özü, temel kavramlar, tanımlar ve bilimsel yaklaşımlar ayrıntılı açıklansın."),
        ("1.2", "I. bölüm, 1.2: uluslararası deneyim ve literatür incelemesi", "Yabancı ülke deneyimleri ve bilimsel literatür analizi sunulsun."),
        ("2.1", "II. bölüm, 2.1: güncel durum ve istatistiksel analiz", "Güncel durum belirli yıllar, sayılar ve istatistiksel göstergelerle analiz edilsin."),
        ("2.2", "II. bölüm, 2.2: alanın gelişme sorunları ve çözüm yolları", "Mevcut sorunlar ve bunların çözümüne yönelik somut pratik öneriler belirtilsin."),
        ("XULOSA", "Sonuç", "«Konuyu inceledikten sonra aşağıdaki sonuçlara vardım:» ifadesiyle başlayıp 5-6 numaralı sonuç yazılsın."),
    ],
    "de": [
        ("KIRISH", "Einleitung", "Aktualität des Themas, Ziel und Aufgaben der Arbeit. Drei Absätze, die genau mit „Aktualität des Themas:“, „Ziel der Arbeit:“, „Aufgaben:“ beginnen."),
        ("1.1", "Kapitel I, Abschnitt 1.1: Wesen des Themas und zentrale wissenschaftliche Begriffe", "Wesen des Themas, Grundbegriffe, Definitionen und wissenschaftliche Ansätze ausführlich darlegen."),
        ("1.2", "Kapitel I, Abschnitt 1.2: internationale Erfahrungen und Literaturanalyse", "Erfahrungen anderer Länder und eine Analyse der wissenschaftlichen Literatur vorstellen."),
        ("2.1", "Kapitel II, Abschnitt 2.1: aktuelle Lage und statistische Analyse", "Die aktuelle Lage mit konkreten Jahren, Zahlen und statistischen Indikatoren analysieren."),
        ("2.2", "Kapitel II, Abschnitt 2.2: Entwicklungsprobleme und ihre Lösungen", "Bestehende Probleme und konkrete praktische Empfehlungen zu ihrer Lösung darlegen."),
        ("XULOSA", "Fazit", "Mit „Nach der Untersuchung des Themas bin ich zu folgenden Schlussfolgerungen gekommen:“ beginnen und 5-6 nummerierte Schlussfolgerungen anführen."),
    ],
    "fr": [
        ("KIRISH", "Introduction", "Pertinence du sujet, objectif et tâches du travail. Trois paragraphes commençant exactement par « Pertinence du sujet : », « Objectif du travail : », « Tâches effectuées : »."),
        ("1.1", "Chapitre I, section 1.1 : essence du sujet et principaux concepts scientifiques", "Développer l’essence du sujet, les concepts clés, les définitions et les approches scientifiques."),
        ("1.2", "Chapitre I, section 1.2 : expérience internationale et analyse de la littérature", "Présenter l’expérience des pays étrangers et une analyse de la littérature scientifique."),
        ("2.1", "Chapitre II, section 2.1 : situation actuelle et analyse statistique", "Analyser la situation actuelle avec des années, des chiffres et des indicateurs statistiques précis."),
        ("2.2", "Chapitre II, section 2.2 : problèmes de développement et solutions", "Exposer les problèmes existants et des recommandations pratiques concrètes pour les résoudre."),
        ("XULOSA", "Conclusion", "Commencer par « Après avoir étudié le sujet, je suis parvenu aux conclusions suivantes : » et donner 5-6 conclusions numérotées."),
    ],
}

_MQ_SOURCE_LABELS = {
    "uz": ("Mavzu", "Vazifa", "Quyida 7 ta manbani faqat ro‘yxat ko‘rinishida yozing: 1) O‘zbekiston Respublikasi qonunlari va Prezident farmonlari (2 ta); 2) darslik va ilmiy qo‘llanmalar — Muallif. Kitob nomi. — Shahar: Nashriyot, yil. — bet (3 ta); 3) rasmiy statistika va ishonchli internet manbalari to‘liq havola (URL) bilan (2 ta). Har bir manba yangi qatorda «1.» ko‘rinishida raqamlansin. Sarlavha, izoh yoki boshqa matn yozmang."),
    "ru": ("Тема", "Задание", "Напишите ровно 7 источников только в виде списка: 1) законы Республики Узбекистан и указы Президента (2); 2) учебники и научные пособия — Автор. Название. — Город: Издательство, год. — страницы (3); 3) официальная статистика и надёжные интернет-источники с полной ссылкой (URL) (2). Каждый источник — с новой строки с номером «1.». Не пишите заголовок, пояснения или другой текст."),
    "en": ("Topic", "Task", "Write exactly 7 sources as a plain list only: 1) laws of the Republic of Uzbekistan and Presidential decrees (2); 2) textbooks and scholarly manuals — Author. Title. — City: Publisher, year. — pages (3); 3) official statistics and reliable Internet sources with full URLs (2). Put each source on a new line numbered “1.”. Do not write a heading, explanations or any other text."),
    "tr": ("Konu", "Görev", "Tam olarak 7 kaynağı yalnızca liste hâlinde yazın: 1) Özbekistan Cumhuriyeti kanunları ve Cumhurbaşkanlığı kararnameleri (2); 2) ders kitapları ve bilimsel el kitapları — Yazar. Kitap adı. — Şehir: Yayınevi, yıl. — sayfa (3); 3) resmî istatistikler ve güvenilir internet kaynakları, tam bağlantı (URL) ile (2). Her kaynak yeni satırda «1.» şeklinde numaralansın. Başlık, açıklama veya başka metin yazmayın."),
    "de": ("Thema", "Aufgabe", "Schreiben Sie genau 7 Quellen ausschließlich als Liste: 1) Gesetze der Republik Usbekistan und Präsidialerlasse (2); 2) Lehrbücher und wissenschaftliche Handbücher — Autor. Titel. — Stadt: Verlag, Jahr. — Seiten (3); 3) amtliche Statistik und verlässliche Internetquellen mit vollständiger URL (2). Jede Quelle in einer neuen Zeile mit „1.“ nummeriert. Keine Überschrift, keine Erklärungen, kein anderer Text."),
    "fr": ("Sujet", "Tâche", "Rédigez exactement 7 sources sous forme de liste uniquement : 1) lois de la République d’Ouzbékistan et décrets présidentiels (2) ; 2) manuels et ouvrages scientifiques — Auteur. Titre. — Ville : Éditeur, année. — pages (3) ; 3) statistiques officielles et sources Internet fiables avec URL complète (2). Chaque source sur une nouvelle ligne numérotée « 1. ». N’écrivez ni titre, ni explication, ni autre texte."),
}

_MQ_REAL_SOURCES = {
    "uz": [
        "O‘zbekiston Respublikasi qonun hujjatlari milliy bazasi. — https://lex.uz",
        "O‘zbekiston Respublikasi Prezidentining rasmiy veb-sayti. — https://president.uz",
        "O‘zbekiston Respublikasi Davlat statistika qo‘mitasi rasmiy portali. — https://stat.uz",
        "O‘zbekiston Respublikasi Oliy ta’lim, fan va innovatsiyalar vazirligi. — https://gov.uz/oz/edu",
        "Jahon banki ma’lumotlar bazasi. — https://data.worldbank.org",
        "Birlashgan Millatlar Tashkiloti rasmiy portali. — https://www.un.org",
    ],
    "ru": [
        "Национальная база законодательства Республики Узбекистан. — https://lex.uz",
        "Официальный сайт Президента Республики Узбекистан. — https://president.uz",
        "Государственный комитет Республики Узбекистан по статистике. — https://stat.uz",
        "Министерство высшего образования, науки и инноваций Республики Узбекистан. — https://gov.uz/oz/edu",
        "База данных Всемирного банка. — https://data.worldbank.org",
        "Официальный портал Организации Объединённых Наций. — https://www.un.org",
    ],
    "en": [
        "National database of legislation of the Republic of Uzbekistan. — https://lex.uz",
        "Official website of the President of the Republic of Uzbekistan. — https://president.uz",
        "State Committee of the Republic of Uzbekistan on Statistics. — https://stat.uz",
        "Ministry of Higher Education, Science and Innovations of the Republic of Uzbekistan. — https://gov.uz/oz/edu",
        "World Bank open data. — https://data.worldbank.org",
        "United Nations official portal. — https://www.un.org",
    ],
    "tr": [
        "Özbekistan Cumhuriyeti mevzuatının ulusal veri tabanı. — https://lex.uz",
        "Özbekistan Cumhuriyeti Cumhurbaşkanlığı resmî web sitesi. — https://president.uz",
        "Özbekistan Cumhuriyeti Devlet İstatistik Komitesi. — https://stat.uz",
        "Özbekistan Cumhuriyeti Yükseköğretim, Bilim ve İnovasyon Bakanlığı. — https://gov.uz/oz/edu",
        "Dünya Bankası açık veri portalı. — https://data.worldbank.org",
        "Birleşmiş Milletler resmî portalı. — https://www.un.org",
    ],
    "de": [
        "Nationale Datenbank der Rechtsvorschriften der Republik Usbekistan. — https://lex.uz",
        "Offizielle Website des Präsidenten der Republik Usbekistan. — https://president.uz",
        "Staatliches Statistikamt der Republik Usbekistan. — https://stat.uz",
        "Ministerium für Hochschulwesen, Wissenschaft und Innovation der Republik Usbekistan. — https://gov.uz/oz/edu",
        "Open-Data-Portal der Weltbank. — https://data.worldbank.org",
        "Offizielles Portal der Vereinten Nationen. — https://www.un.org",
    ],
    "fr": [
        "Base nationale de la législation de la République d’Ouzbékistan. — https://lex.uz",
        "Site officiel du Président de la République d’Ouzbékistan. — https://president.uz",
        "Comité d’État des statistiques de la République d’Ouzbékistan. — https://stat.uz",
        "Ministère de l’Enseignement supérieur, des Sciences et de l’Innovation de la République d’Ouzbékistan. — https://gov.uz/oz/edu",
        "Portail open data de la Banque mondiale. — https://data.worldbank.org",
        "Portail officiel des Nations Unies. — https://www.un.org",
    ],
}


def _mustaqil_page_split(pages):
    """Asosiy qism sahifalarini 4 ta kichik bo'limga taqsimlaydi."""
    body_pages = max(4, int(pages or 10) - 6)
    base, extra = divmod(body_pages, 4)
    return [base + (1 if index < extra else 0) for index in range(4)], body_pages


def _reference_entries(text):
    """AI ro'yxatidan haqiqiy manba qatorlarini ajratib oladi."""
    entries = []
    for raw in str(text or "").splitlines():
        line = re.sub(r"^\s*(?:[•▪●\-–—*]|\(?\d{1,2}[\.\)])\s*", "", raw).strip()
        line = re.sub(r"\s+", " ", line)
        if len(line) < 15 or line.startswith("⚠️"):
            continue
        low = line.casefold().rstrip(":")
        if low in ("manbalar", "adabiyotlar", "источники", "литература", "sources", "references",
                   "kaynaklar", "quellen", "sources utilisées"):
            continue
        entries.append(line)
    return entries


async def _generate_mustaqil_sources(topic, lang, wiki):
    """Adabiyotlar ro'yxati: AI manbalari + tekshirilishi mumkin bo'lgan rasmiy havolalar."""
    lc = str(lang or "uz").lower()
    topic_label, task_label, rule = _MQ_SOURCE_LABELS.get(lc, _MQ_SOURCE_LABELS["en"])
    prompt = (
        f"{topic_label}: {topic}\n{task_label}: {rule}\n{wiki_block(wiki, lc)}\n"
        f"Do not output a title, notes or explanations; only the numbered source list."
    )
    raw = await _chat_complete(prompt, system=_pure_language_system(lc), max_tokens=900, temperature=0.4)
    entries, seen = [], set()

    def add(value):
        item = re.sub(r"\s+", " ", str(value or "")).strip()
        if len(item) < 12 or item.startswith("⚠️"):
            return
        key = re.sub(r"\W+", "", item.casefold())[:60]
        if not key or key in seen:
            return
        seen.add(key)
        entries.append(item)

    for item in _reference_entries(raw):
        add(item)
        if len(entries) >= 7:
            break
    if isinstance(wiki, dict) and wiki.get("found") and wiki.get("url"):
        add(f'Wikipedia. {wiki.get("title", topic)}. — {wiki.get("url")}')
    for item in _MQ_REAL_SOURCES.get(lc, _MQ_REAL_SOURCES["en"]):
        if len(entries) >= 8:
            break
        add(item)
    return "\n".join(f"{index}. {item}" for index, item in enumerate(entries[:10], 1))


async def _generate_mustaqil(topic, pages, lang):
    """Mustaqil ish: to'liq tuzilma (kirish, 4 kichik bo'lim, xulosa, adabiyotlar)."""
    lc = str(lang or "uz").lower()
    plan = _MQ_PLAN.get(lc, _MQ_PLAN["en"])
    wiki = await wikipedia_fetch(topic, max_chars=10000, full=True, gen_lang=lc)
    split, _body_pages = _mustaqil_page_split(pages)
    section_pages = {"1.1": split[0], "1.2": split[1], "2.1": split[2], "2.2": split[3],
                     "KIRISH": 2, "XULOSA": 1}
    parts, previous, solid = [], "", 0
    for marker, title, desc in plan:
        text = await _generate_section("mustaqil", topic, title, section_pages.get(marker, 1),
                                       desc, lc, wiki, previous)
        text = str(text or "").strip()
        if len(text) >= 400:
            solid += 1
        parts.append(f"[[{marker}]]\n{text}")
        previous = text[:800]
    references = await _generate_mustaqil_sources(topic, lc, wiki)
    parts.append("[[ADABIYOTLAR]]\n" + references)
    return "\n\n".join(parts), solid >= 4


# ===== INSHO: REJA + adabiy matn (alohida xizmat) =====
_INSHO_PLAN_PROMPT = {
    "uz": ("Mavzu", "Vazifa", "Aynan besh qator yozing:\n1. Kirish. <mavzuga kirish mazmuni>\n2. Asosiy qism:\n   a) <birinchi band>\n   b) <ikkinchi band>\n3. Xulosa. <yakuniy fikr>\nFaqat shu reja qatorlarini yozing; sarlavha, izoh yoki boshqa matn yozmang."),
    "ru": ("Тема", "Задание", "Напишите ровно пять строк:\n1. Введение. <содержание введения>\n2. Основная часть:\n   а) <первый пункт>\n   б) <второй пункт>\n3. Заключение. <итоговый вывод>\nПишите только строки плана, без заголовка, пояснений и другого текста."),
    "en": ("Topic", "Task", "Write exactly five lines:\n1. Introduction. <introduction content>\n2. Main part:\n   a) <first point>\n   b) <second point>\n3. Conclusion. <final idea>\nWrite only these plan lines; no heading, notes or other text."),
    "tr": ("Konu", "Görev", "Tam olarak beş satır yazın:\n1. Giriş. <giriş içeriği>\n2. Ana bölüm:\n   a) <birinci nokta>\n   b) <ikinci nokta>\n3. Sonuç. <kapanış fikri>\nYalnızca bu plan satırlarını yazın; başlık, açıklama veya başka metin yazmayın."),
    "de": ("Thema", "Aufgabe", "Schreiben Sie genau fünf Zeilen:\n1. Einleitung. <Inhalt der Einleitung>\n2. Hauptteil:\n   a) <erster Punkt>\n   b) <zweiter Punkt>\n3. Schluss. <abschließender Gedanke>\nSchreiben Sie nur diese Gliederungszeilen, keine Überschrift, keine Erläuterungen, keinen anderen Text."),
    "fr": ("Sujet", "Tâche", "Rédigez exactement cinq lignes :\n1. Introduction. <contenu de l’introduction>\n2. Partie principale :\n   a) <premier point>\n   b) <deuxième point>\n3. Conclusion. <idée finale>\nN’écrivez que ces lignes du plan, sans titre, sans explication et sans autre texte."),
}

_INSHO_PLAN_FALLBACK = {
    "uz": ["Kirish. {t} mavzusining mazmuni va bugungi kundagi ahamiyati.",
           "Asosiy qism:", "a) {t} bo‘yicha asosiy tushunchalar va ilmiy qarashlar.",
           "b) Hayotiy misollar, badiiy tahlil va dalillar.", "Xulosa. Asosiy fikrlarning umumlashmasi va ma’naviy xulosasi."],
    "ru": ["Введение. Содержание темы «{t}» и её значение сегодня.",
           "Основная часть:", "а) Основные понятия и научные взгляды по теме «{t}».",
           "б) Жизненные примеры, литературный анализ и аргументы.", "Заключение. Обобщение основных мыслей и духовный вывод."],
    "en": ["Introduction. The meaning of {t} and its significance today.",
           "Main part:", "a) Key concepts and scholarly views on {t}.",
           "b) Real-life examples, literary analysis and evidence.", "Conclusion. A summary of the main ideas and the final moral lesson."],
    "tr": ["Giriş. {t} konusunun anlamı ve bugünkü önemi.",
           "Ana bölüm:", "a) {t} ile ilgili temel kavramlar ve bilimsel görüşler.",
           "b) Hayattan örnekler, edebî tahlil ve kanıtlar.", "Sonuç. Ana fikirlerin özeti ve manevi sonuç."],
    "de": ["Einleitung. Inhalt des Themas {t} und seine heutige Bedeutung.",
           "Hauptteil:", "a) Grundbegriffe und wissenschaftliche Ansichten zu {t}.",
           "b) Beispiele aus dem Leben, literarische Analyse und Belege.", "Schluss. Zusammenfassung der Hauptgedanken und moralisches Fazit."],
    "fr": ["Introduction. Le sens du sujet {t} et son importance aujourd’hui.",
           "Partie principale :", "a) Concepts clés et points de vue scientifiques sur {t}.",
           "b) Exemples de la vie, analyse littéraire et arguments.", "Conclusion. Synthèse des idées principales et portée morale."],
}

_INSHO_WORDS = {
    "uz": ("Kirish", "Asosiy qism", "Xulosa",
           "Adabiy, jonli va ta’sirchan uslubda, birinchi shaxs nomidan yozilsin. She’riy parchalar, iqtiboslar va badiiy tahlildan foydalanilsin; sun’iy statistika o‘ylab topilmasin.",
           "Mavzuga badiiy kirish: davr, shaxs yoki muammo haqida umumiy tasavvur berilsin, o‘quvchini qiziqtiradigan jonli jumlalar bilan boshlansin.",
           "Reja bandi to‘liq ochib berilsin: fikr, badiiy tahlil, iqtibos yoki hayotiy misol va shaxsiy munosabat.",
           "Yozilgan fikrlardan kelib chiqib yakunlansin, mavzuning ma’naviy qiymati va bugungi yoshlar uchun saboqlari ko‘rsatilsin."),
    "ru": ("Введение", "Основная часть", "Заключение",
           "Пишите литературным, живым и выразительным языком от первого лица. Используйте цитаты, поэтические фрагменты и литературный анализ; не выдумывайте статистику.",
           "Художественное вступление: дайте общее представление о теме, эпохе или личности и начните с ярких, вовлекающих фраз.",
           "Полностью раскройте пункт плана: мысль, литературный анализ, цитата или жизненный пример и личное отношение.",
           "Подведите итог на основе написанного, покажите духовную ценность темы и урок для современной молодёжи."),
    "en": ("Introduction", "Main part", "Conclusion",
           "Write in a literary, vivid and expressive first-person style. Use quotations, poetic fragments and literary analysis; never invent statistics.",
           "Give an artistic introduction to the topic, period or person and open with vivid sentences that engage the reader.",
           "Fully develop the plan point: the idea, literary analysis, a quotation or real-life example, and a personal attitude.",
           "Conclude from what has been written, showing the moral value of the topic and the lesson it holds for young people today."),
    "tr": ("Giriş", "Ana bölüm", "Sonuç",
           "Edebî, canlı ve etkileyici bir üslupla birinci şahıs ağzından yazın. Alıntılar, şiirsel parçalar ve edebî tahlil kullanın; istatistik uydurmayın.",
           "Konuya edebî bir giriş yapın: dönem, kişi veya sorun hakkında genel bir izlenim verin ve okuru çeken canlı cümlelerle başlayın.",
           "Plan maddesini tam olarak açın: fikir, edebî tahlil, alıntı ya da hayattan bir örnek ve kişisel tutum.",
           "Yazılanlardan yola çıkarak bitirin; konunun manevi değerini ve bugünkü gençler için dersini gösterin."),
    "de": ("Einleitung", "Hauptteil", "Schluss",
           "Schreiben Sie in einem literarischen, lebendigen und ausdrucksstarken Stil in der Ich-Form. Verwenden Sie Zitate, poetische Passagen und literarische Analyse; erfinden Sie keine Statistiken.",
           "Künstlerischer Einstieg: Geben Sie einen allgemeinen Eindruck von Thema, Epoche oder Person und beginnen Sie mit lebendigen, fesselnden Sätzen.",
           "Entwickeln Sie den Gliederungspunkt vollständig: Gedanke, literarische Analyse, Zitat oder Beispiel aus dem Leben und persönliche Haltung.",
           "Fassen Sie das Geschriebene zusammen und zeigen Sie den geistigen Wert des Themas und seine Lehre für junge Menschen heute."),
    "fr": ("Introduction", "Partie principale", "Conclusion",
           "Écrivez dans un style littéraire, vivant et expressif, à la première personne. Utilisez citations, passages poétiques et analyse littéraire ; n’inventez pas de statistiques.",
           "Introduction artistique : donnez une impression générale du sujet, de l’époque ou de la personne et commencez par des phrases vivantes qui captivent le lecteur.",
           "Développez pleinement le point du plan : idée, analyse littéraire, citation ou exemple de la vie et position personnelle.",
           "Concluez à partir de ce qui a été écrit en montrant la valeur morale du sujet et la leçon pour les jeunes d’aujourd’hui."),
}


def _insho_plan_lines(plan, topic, lang):
    """REJA matnini 5 qatorga keltiradi (kirish, «asosiy qism:», a), b), xulosa)."""
    lc = str(lang or "uz").lower()
    lines = []
    for raw in str(plan or "").splitlines():
        line = raw.strip().rstrip()
        if not line:
            continue
        if line.casefold().rstrip(":") in ("reja", "план", "plan", "outline", "gliederung"):
            continue
        lines.append(line)
    if len(lines) < 5:
        template = _INSHO_PLAN_FALLBACK.get(lc, _INSHO_PLAN_FALLBACK["en"])
        lines = []
        for index, item in enumerate(template):
            value = item.format(t=str(topic)[:80])
            prefix = ("1. ", "2. ", "   a) ", "   b) ", "3. ")[index]
            lines.append(prefix + value)
    return lines[:5]


async def generate_insho_plan(topic, lang, pages=3):
    """Insho uchun REJA: kirish, asosiy qism (a, b), xulosa."""
    lc = str(lang or "uz").lower()
    topic_label, task_label, rule = _INSHO_PLAN_PROMPT.get(lc, _INSHO_PLAN_PROMPT["en"])
    try:
        wiki = await wikipedia_fetch(topic, max_chars=1500, gen_lang=lc)
    except Exception as exc:
        _log(f"Insho plan reference lookup failed: {exc}")
        wiki = ""
    prompt = (
        f"{topic_label}: {topic}\n{task_label}: {rule}\n{wiki_block(wiki, lc)}\n"
        f"Do not output any other text."
    )
    raw = ""
    try:
        raw = await _chat_complete(prompt, system=_pure_language_system(lc), max_tokens=700, temperature=0.4)
    except Exception as exc:
        _log(f"Insho plan generation failed: {exc}")
    lines = _insho_plan_lines(raw, topic, lc)
    return "\n".join(lines)


async def _generate_insho(topic, pages, lang, plan=""):
    """Insho matni: kirish → asosiy qism (a, b) → xulosa (adabiy uslub, reja asosida)."""
    lc = str(lang or "uz").lower()
    intro_word, body_word, concl_word, style_desc, intro_desc, body_desc, concl_desc = _INSHO_WORDS.get(lc, _INSHO_WORDS["en"])
    try:
        pages = int(pages or 3)
    except (TypeError, ValueError):
        pages = 3
    pages = min(5, max(3, pages))
    lines = _insho_plan_lines(plan, topic, lc)
    plan_intro = re.sub(r"^\s*1[.)]\s*", "", lines[0]).strip()
    plan_a = re.sub(r"^\s*a[)]\s*", "", lines[2]).strip() if len(lines) > 2 else ""
    plan_b = re.sub(r"^\s*b[)]\s*", "", lines[3]).strip() if len(lines) > 3 else ""
    plan_concl = re.sub(r"^\s*3[.)]\s*", "", lines[4]).strip() if len(lines) > 4 else ""

    try:
        wiki = await wikipedia_fetch(topic, max_chars=6000, full=True, gen_lang=lc)
    except Exception as exc:
        _log(f"Insho reference lookup failed: {exc}")
        wiki = ""

    body_pages = max(2, pages - 2)
    base, extra = divmod(body_pages, 2)
    first_pages = base + (1 if extra else 0)
    second_pages = base
    parts = []
    previous = ""
    solid = 0
    for marker, title, section_pages, desc in (
        ("INSHO_INTRO", f"{intro_word}: {plan_intro}", 1, f"{intro_desc} {style_desc}"),
        ("INSHO_BODY_A", f"{body_word}, a): {plan_a}", first_pages, f"{body_desc} {style_desc}"),
        ("INSHO_BODY_B", f"{body_word}, b): {plan_b}", second_pages, f"{body_desc} {style_desc}"),
        ("INSHO_CONCLUSION", f"{concl_word}: {plan_concl}", 1, f"{concl_desc} {style_desc}"),
    ):
        text = await _generate_section("insho", topic, title, section_pages, desc, lc, wiki, previous)
        text = str(text or "").strip()
        if len(text) >= 400:
            solid += 1
        parts.append(f"[[{marker}]]\n{text}")
        previous = text[:600]
    return "\n\n".join(parts), solid >= 3



# ===== STANDART AKADEMIK XIZMATLAR (referat, kurs, diplom, maqola, tezis) =====
# Har bir bo'lim tanlangan sahifa hajmiga to'liq to'ldiriladi: matn yetarli
# bo'lmasa, o'sha bo'lim uchun yangi mazmun bilan davom ettiriladi.
def _dedupe_blocks(text):
    seen, out = set(), []
    for raw in re.split(r"\n\s*\n", str(text or "")):
        block = re.sub(r"\s+", " ", raw).strip()
        if len(block) < 2:
            continue
        key = re.sub(r"\W+", "", block.casefold())[:80]
        if key in seen:
            continue
        seen.add(key)
        out.append(block)
    return out


async def _fill_section(service, topic, sec_title, sec_pages, sec_desc, lang, wiki, previous,
                        chars_per_page, budget_scale=1.0):
    """Bo'limni ajratilgan sahifalarga to'liq to'ldiradi (kerak bo'lsa davomi yoziladi)."""
    pages_float = float(sec_pages or 1)
    budget_scale = max(0.5, min(1.0, float(budget_scale or 1.0)))
    target = max(300, int(round(pages_float * int(chars_per_page) * 0.95 * budget_scale)))
    if pages_float < 1:
        # Kasr sahifa (maqola/tezis): bitta chaqiriq, lekin hajm shu ulushga mos.
        gen_pages = 1
        section_capacity = max(250, int(round(pages_float * int(chars_per_page) * budget_scale)))
    else:
        gen_pages = int(math.ceil(pages_float))
        section_capacity = max(300, int(round(int(chars_per_page) * budget_scale)))
    text = await _generate_section(service, topic, sec_title, gen_pages, sec_desc, lang,
                                   wiki, previous, chars_per_page=section_capacity)
    text = str(text or "").strip()
    if len(text) >= target * 0.92:
        return text
    missing = target - len(text)
    extra_pages = max(1, min(3, math.ceil(missing / max(1, int(chars_per_page)))))
    continuation = (
        "Continue the same section with NEW material only. Do not repeat or paraphrase "
        "anything already written. Add concrete details, examples, mechanisms, comparisons "
        "and analysis that develop the section further, and finish with a complete paragraph."
    )
    extra = await _generate_section(
        service, topic, sec_title, extra_pages,
        f"{sec_desc} {continuation}", lang, wiki, text[-800:],
        chars_per_page=section_capacity,
    )
    extra = str(extra or "").strip()
    if extra and len(extra) >= 250:
        blocks = _dedupe_blocks(text) + _dedupe_blocks(extra)
        text = "\n\n".join(blocks)
    return text


def _plan_lines(service, lang, plan, found=None):
    """Referat uchun REJA: bo'lim nomi va uning mazmunini qisqa izohi bilan."""
    found = found or {}
    lines = []
    for number, (marker, title_text, _desc, pages) in enumerate(plan, 1):
        hint = ""
        body = str(found.get(marker, "") or "").strip()
        if body:
            first = re.split(r"(?<=[.!?])\s+", body)[0]
            first = re.sub(r"\s+", " ", first).strip()
            if len(first) > 120:
                first = first[:117].rsplit(" ", 1)[0] + "…"
            hint = f" — {first}"
        lines.append(f"{number}. {title_text}{hint}")
    return "\n".join(lines)


_ANNOT_TEMPLATE = {
    "uz": "Ushbu bitiruv malakaviy ishi «{t}» mavzusiga bag‘ishlangan. Ishda mavzuning nazariy asoslari, amaliy holati, mavjud muammolar va ularni bartaraf etish bo‘yicha takliflar tahlil qilingan.",
    "ru": "Данная выпускная квалификационная работа посвящена теме «{t}». В работе проанализированы теоретические основы темы, её практическое состояние, существующие проблемы и предложения по их устранению.",
    "en": "This graduation thesis is devoted to the topic “{t}”. It analyses the theoretical foundations of the topic, its practical state, the existing problems and the proposals for solving them.",
}


async def _generate_annotation(topic, lang, doc_lang):
    """Diplom uchun qisqa annotatsiya: o'zbek, rus va ingliz tillarida."""
    texts = {}
    for code in ("uz", "ru", "en"):
        ln = _lang_name(code)
        prompt = (
            f"Write one annotation paragraph (60-80 words) for a graduation thesis about: {topic}. "
            f"Language: {ln}. Mention the aim, the methods, the main results and the practical value. "
            "Output only the paragraph, no heading, no lists, no other languages."
        )
        try:
            raw = await _chat_complete(prompt, system=_pure_language_system(code), max_tokens=500, temperature=0.4)
        except Exception as exc:
            _log(f"Annotation generation failed ({code}): {exc}")
            raw = ""
        raw = str(raw or "").strip()
        if len(raw) < 80 or _is_lang_mixed(raw, code) or _document_text_is_repetitive(raw):
            raw = _ANNOT_TEMPLATE[code].format(t=str(topic)[:120])
        texts[code] = raw
    return "\n\n".join(f"[[{code.upper()}]]\n{value}" for code, value in texts.items())


async def _generate_sources(topic, lang, wiki, count):
    """Adabiyotlar ro'yxati: kerakli songacha AI manbalari + tekshiriladigan rasmiy havolalar."""
    lc = str(lang or "uz").lower()
    count = max(3, int(count or 5))
    topic_label, task_label, _rule = _MQ_SOURCE_LABELS.get(lc, _MQ_SOURCE_LABELS["en"])
    entries, seen = [], set()

    def add(value):
        item = re.sub(r"\s+", " ", str(value or "")).strip()
        if len(item) < 15 or item.startswith("⚠️"):
            return
        key = re.sub(r"\W+", "", item.casefold())[:60]
        if not key or key in seen:
            return
        seen.add(key)
        entries.append(item)

    per_batch = 12
    for _ in range(3):
        if len(entries) >= count:
            break
        need = min(per_batch, count - len(entries) + 4)
        rule = (
            f"Write exactly {need} sources as a plain numbered list, one per line, in the given language. "
            "Include laws and presidential decrees first, then textbooks and scholarly manuals "
            "in the form Author. Title. — City: Publisher, year. — pages, then official statistics "
            "and reliable Internet sources with full URLs. No heading, no notes, no other text."
        )
        prompt = f"{topic_label}: {topic}\n{task_label}: {rule}\n{wiki_block(wiki, lc)}\n"
        try:
            raw = await _chat_complete(prompt, system=_pure_language_system(lc), max_tokens=1400, temperature=0.5)
        except Exception as exc:
            _log(f"Source generation failed: {exc}")
            break
        before = len(entries)
        for item in _reference_entries(raw):
            add(item)
            if len(entries) >= count + 2:
                break
        if len(entries) == before:
            break

    if isinstance(wiki, dict) and wiki.get("found") and wiki.get("url"):
        add(f'Wikipedia. {wiki.get("title", topic)}. — {wiki.get("url")}')
    for item in _MQ_REAL_SOURCES.get(lc, _MQ_REAL_SOURCES["en"]):
        if len(entries) >= count:
            break
        add(item)
    return "\n".join(f"{index}. {item}" for index, item in enumerate(entries[:count], 1))


_TABLE_FALLBACK = {
    "uz": [
        ("Tashkiliy shakl", "An’anaviy usullar", "Raqamli vositalar", "Samaradorlik oshadi"),
        ("Ma’lumot manbasi", "Qog‘oz hisobotlar", "Elektron tizimlar", "Tezkorlik va aniqlik"),
        ("Nazorat tizimi", "Davriy tekshiruv", "Doimiy monitoring", "Nazorat kuchayadi"),
        ("Kutilayotgan natija", "Barqarorlik", "Rivojlanish", "Uzoq muddatli samara"),
    ],
    "ru": [
        ("Организационная форма", "Традиционные методы", "Цифровые инструменты", "Рост эффективности"),
        ("Источник данных", "Бумажные отчёты", "Электронные системы", "Оперативность и точность"),
        ("Система контроля", "Периодические проверки", "Постоянный мониторинг", "Усиление контроля"),
        ("Ожидаемый результат", "Стабильность", "Развитие", "Долгосрочный эффект"),
    ],
    "en": [
        ("Organisational form", "Traditional methods", "Digital tools", "Higher efficiency"),
        ("Data source", "Paper reports", "Electronic systems", "Speed and accuracy"),
        ("Control system", "Periodic inspection", "Continuous monitoring", "Stronger control"),
        ("Expected result", "Stability", "Development", "Long-term effect"),
    ],
    "tr": [
        ("Örgütsel biçim", "Geleneksel yöntemler", "Dijital araçlar", "Verimlilik artar"),
        ("Veri kaynağı", "Kâğıt raporlar", "Elektronik sistemler", "Hız ve doğruluk"),
        ("Kontrol sistemi", "Dönemsel denetim", "Sürekli izleme", "Denetim güçlenir"),
        ("Beklenen sonuç", "İstikrar", "Gelişme", "Uzun vadeli etki"),
    ],
    "de": [
        ("Organisationsform", "Traditionelle Methoden", "Digitale Werkzeuge", "Höhere Effizienz"),
        ("Datenquelle", "Papierberichte", "Elektronische Systeme", "Schnelligkeit und Genauigkeit"),
        ("Kontrollsystem", "Periodische Prüfung", "Kontinuierliches Monitoring", "Stärkere Kontrolle"),
        ("Erwartetes Ergebnis", "Stabilität", "Entwicklung", "Langfristige Wirkung"),
    ],
    "fr": [
        ("Forme organisationnelle", "Méthodes traditionnelles", "Outils numériques", "Efficacité accrue"),
        ("Source des données", "Rapports papier", "Systèmes électroniques", "Rapidité et précision"),
        ("Système de contrôle", "Contrôle périodique", "Suivi continu", "Contrôle renforcé"),
        ("Résultat attendu", "Stabilité", "Développement", "Effet à long terme"),
    ],
}


async def _generate_table_rows(topic, lang, kind):
    """Jadval qatorlari: 4 qator, har biri 3 ta katak (AI ishlamasa lokalizatsiya qilingan zaxira)."""
    lc = str(lang or "uz").lower()
    headers = {
        "compare": academic.title("col_criteria", lc) + " | " + academic.title("col_old", lc) + " | "
                   + academic.title("col_new", lc) + " | " + academic.title("row_result", lc),
        "problems": academic.title("col_problem", lc) + " | " + academic.title("col_cause", lc) + " | "
                    + academic.title("col_solution", lc) + " | " + academic.title("row_result", lc),
    }
    columns = 4 if kind == "compare" else 4
    prompt = (
        f"Topic: {topic}\nWrite exactly 6 rows for an analytical table ({kind}) in {_lang_name(lc)}. "
        f"Each row must have {columns} short cells separated by ' | '. "
        "Keep every cell under 8 words, specific to the topic, no numbers invented, "
        "no header row, no numbering, no other text."
    )
    try:
        raw = await _chat_complete(prompt, system=_pure_language_system(lc), max_tokens=700, temperature=0.35)
    except Exception as exc:
        _log(f"Table generation failed: {exc}")
        raw = ""
    rows = []
    for line in str(raw or "").splitlines():
        line = re.sub(r"^\s*(?:\d+[.)]|[-•*])\s*", "", line).strip()
        if "|" not in line:
            continue
        cells = [re.sub(r"\s+", " ", cell).strip() for cell in line.split("|")][:columns]
        if len(cells) < columns or any(len(cell) < 2 for cell in cells):
            continue
        rows.append(tuple(cells))
        if len(rows) == 6:
            break
    if len(rows) < 6:
        rows = _TABLE_FALLBACK.get(lc, _TABLE_FALLBACK["en"])
    return headers[kind], rows


async def _generate_standard(service, topic, pages, lang):
    """Referat, kurs, diplom, maqola va tezis: to'liq, sahifalab to'ldirilgan mazmun."""
    lc = str(lang or "uz").lower()
    plan = academic.plan(service, pages, lc)
    cpp = academic.chars_per_page(service)
    wiki = await wikipedia_fetch(topic, max_chars=10000 if service in LONG_SERVICES else 5000,
                                 full=True, gen_lang=lc)
    parts, previous, solid = [], "", 0
    found_parts = {}
    for marker, title_text, desc, sec_pages in plan:
        # Kurs ishida 2.1 va 2.3 bo'limlaridan keyin jadval tushadi: o'sha
        # sahifada jadvalga joy qoldirish uchun matn 18% kam yoziladi.
        scale = 0.82 if (service == "kurs" and marker in ("2.1", "2.3")) else 1.0
        text = await _fill_section(service, topic, title_text, sec_pages, desc, lc, wiki,
                                   previous, cpp, budget_scale=scale)
        text = str(text or "").strip()
        found_parts[marker] = text
        if len(text) >= 400:
            solid += 1
        parts.append(f"[[{marker}]]\n{text}")
        previous = text[:700]

    if service in academic.ACADEMIC_SERVICES:
        refs_min, _refs_max = academic.STRUCTURES[service]["refs_range"]
        count = refs_min
        if service == "diplom":
            count = max(refs_min, 36)
        references = await _generate_sources(topic, lc, wiki, count)
        parts.append("[[ADABIYOTLAR]]\n" + references)
        if service == "referat":
            parts.append("[[REJA]]\n" + _plan_lines(service, lc, plan, found=dict(found_parts)))
        if service == "diplom":
            parts.append("[[ANNOTATSIYA]]\n" + await _generate_annotation(topic, lc, lc))
        if service in ("kurs", "diplom"):
            head1, rows1 = await _generate_table_rows(topic, lc, "compare")
            head2, rows2 = await _generate_table_rows(topic, lc, "problems")
            parts.append("[[JADVAL1]]\n" + head1 + "\n" + "\n".join(" | ".join(row) for row in rows1))
            parts.append("[[JADVAL2]]\n" + head2 + "\n" + "\n".join(" | ".join(row) for row in rows2))

    if service == "maqola":
        abstract_prompt = (
            f"Write the abstract of a scientific article about: {topic}. "
            f"Language: {_lang_name(lc)}. 100-150 words, one paragraph: purpose, methods, main results, conclusion. "
            "Output only the paragraph."
        )
        try:
            abstract = await _chat_complete(abstract_prompt, system=_pure_language_system(lc),
                                            max_tokens=600, temperature=0.4)
        except Exception as exc:
            _log(f"Abstract generation failed: {exc}")
            abstract = ""
        abstract = str(abstract or "").strip()
        if len(abstract) < 120 or _is_lang_mixed(abstract, lc):
            abstract = " ".join(_dedupe_blocks(" ".join(parts))[0:2])[:900]
        parts.append("[[ABSTRACT]]\n" + abstract)
        keywords_prompt = (
            f"Write 6 keywords for a scientific article about: {topic}. Language: {_lang_name(lc)}. "
            "Separate them with commas, lowercase, no numbering, no other text."
        )
        try:
            keywords = await _chat_complete(keywords_prompt, system=_pure_language_system(lc),
                                            max_tokens=120, temperature=0.3)
        except Exception as exc:
            _log(f"Keywords generation failed: {exc}")
            keywords = ""
        keywords = re.sub(r"\s+", " ", str(keywords or "")).strip(" .;")
        if "," not in keywords or _is_lang_mixed(keywords, lc):
            keywords = ", ".join(re.sub(r"\W+", " ", str(topic)).lower().split()[:6])
        parts.append("[[KEYWORDS]]\n" + keywords)

    real = solid >= max(2, len(plan) // 2)
    return "\n\n".join(parts), real


async def generate(service, topic, options, lang="uz"):
    """Umumiy vaqt chegarasi bilan generatsiya (jim qotib qolmasligi uchun)."""
    try:
        return await asyncio.wait_for(
            _generate_impl(service, topic, options, lang),
            timeout=max(1, int(GEN_TIMEOUT)),
        )
    except asyncio.TimeoutError:
        raise TimeoutError(
            f"AI {GEN_TIMEOUT}s ichida javob bermadi. Keyinroq qayta urinib ko'ring."
        )


async def _generate_impl(service, topic, options, lang="uz"):
    if service == "esse":
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
        wb = wiki_block(wiki, lc)
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

        prompt_body = f"""Write the essay's two body paragraphs about: {topic}.
Write approximately {body_words} words total in natural {ln}, separated into EXACTLY TWO paragraphs of about {para_words} words each:
Paragraph 1: the first strong reason supporting the thesis, with a clear explanation and one concrete example.
Paragraph 2: a second strong reason (or a considered counter-view) with an explanation and one concrete example.
Keep the content specific to the topic. Do not invent exact statistics. Output only those two paragraphs; no headings, numbering, bullet points, checklist, or writing advice. Use only {ln}. Reference notes:
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
        body = _normalize_two_paragraphs(body)

        result = (
            "[[ESSAY_INTRO]]\n" + clean_ai_text(intro) +
            "\n\n[[ESSAY_BODY]]\n" + clean_ai_text(body) +
            "\n\n[[ESSAY_CONCLUSION]]\n" + clean_ai_text(conclusion)
        )
        return result, not used_fallback

    try:
        requested_pages = int(options.get("pages", 10) or 10)
    except (TypeError, ValueError):
        requested_pages = 10
    from services import SERVICES as _SERVICES
    _opts = _SERVICES.get(service, {}).get("options")
    if _opts:
        pages = requested_pages if requested_pages in tuple(_opts) else min(tuple(_opts), key=lambda n: abs(n - requested_pages))
    else:
        pages = requested_pages if requested_pages in (10, 15, 20) else min((10, 15, 20), key=lambda n: abs(n - requested_pages))
    if service == "test":
        # The test service's selected quantity is a question count, not page count.
        return await _generate_test(service, topic, options, lang)
    if service == "mustaqil":
        # Mustaqil ish uchun alohida to'liq tuzilma: kirish, 2 bob (4 band),
        # raqamlangan xulosa va real havolali adabiyotlar ro'yxati.
        return await _generate_mustaqil(topic, pages, lang)
    if service == "insho":
        # Insho — adabiy ish: REJA (reja alohida yoziladi) va 3-5 betlik matn.
        return await _generate_insho(topic, pages, lang, (options or {}).get("plan", ""))

    if service in academic.ACADEMIC_SERVICES or service in academic.COMPACT_SERVICES:
        # Referat, kurs, diplom, maqola va tezis: bo'limma-bo'lim to'liq mazmun.
        return await _generate_standard(service, topic, pages, lang)

    page_overhead = 2 if service in ("maqola", "tezis") else 5
    content_pages = max(2, pages - page_overhead)
    wiki = await wikipedia_fetch(topic, max_chars=10000 if service in LONG_SERVICES else 4000, full=(service in LONG_SERVICES), gen_lang=lang)
    outline = await _generate_outline(service, topic, content_pages, lang, wiki)
    full_text_parts, prev_summary, real_count, fail_count = [], "", 0, 0
    
    for sec_title, sec_pages, sec_desc in outline:
        sec_text = await _generate_section(service, topic, sec_title, sec_pages, sec_desc, lang, wiki, prev_summary)
        if "batafsil ma'lumot" in sec_text or sec_text.strip().startswith("⚠️"): fail_count += 1
        else: real_count += 1
        full_text_parts.append(sec_text); prev_summary = sec_text[:800]
        
    result = "\n\n".join(full_text_parts)
    real = real_count > 0 and fail_count <= len(outline) // 2
    # Do not append pages of repetitive filler when the model returns little text.
    # The DOCX layout supplies short, localized page-specific fallback text where needed.
    if len(result.strip()) < 120:
        result = _fallback_text(service, topic, options, lang, min(3, max(1, content_pages)))
    return result, real

# ===== TEST GENERATSIYASI =====
def _fallback_test_questions(topic, start, end, lang):
    """Localized quiz fallback used only if AI produces broken language/content."""
    bank = {
        "uz": (["asosiy tushuncha", "tarixiy sharoit", "kelib chiqish sababi", "muhim xususiyat", "amaliy qo‘llanish", "ta’sir va oqibat", "asosiy muammo", "yechim yo‘li", "dalillar", "umumiy xulosa"], "{topic} mavzusida {focus}ni aniqlash uchun qaysi yondashuv eng asosli?", ["Ishonchli manba va dalillarni solishtirish", "Dalilsiz taxminni qabul qilish", "Faqat bitta fikrga tayanish", "Mavzuga aloqasiz ma’lumotni tanlash"]),
        "ru": (["основное понятие", "исторический контекст", "причина возникновения", "важная особенность", "практическое применение", "влияние и последствия", "главная проблема", "способ решения", "доказательства", "общий вывод"], "Какой подход лучше всего помогает определить аспект «{focus}» в теме «{topic}»?", ["Сопоставить надёжные источники и доказательства", "Принять предположение без доказательств", "Опира́ться только на одно мнение", "Выбрать сведения, не связанные с темой"]),
        "en": (["core concept", "historical context", "underlying cause", "key feature", "practical use", "impact and consequences", "main problem", "possible solution", "supporting evidence", "overall conclusion"], "Which approach best helps identify the {focus} related to {topic}?", ["Compare reliable sources and evidence", "Accept an unsupported guess", "Rely on only one opinion", "Choose information unrelated to the topic"]),
        "tr": (["temel kavram", "tarihsel bağlam", "ortaya çıkış nedeni", "önemli özellik", "uygulama alanı", "etki ve sonuçlar", "temel sorun", "çözüm yolu", "kanıtlar", "genel sonuç"], "{topic} konusunda {focus} unsurunu belirlemek için hangi yaklaşım en sağlamdır?", ["Güvenilir kaynakları ve kanıtları karşılaştırmak", "Kanıtsız bir varsayımı kabul etmek", "Yalnızca tek bir görüşe dayanmak", "Konuyla ilgisiz bilgiyi seçmek"]),
        "de": (["Grundbegriff", "historischer Kontext", "Ursache", "wichtiges Merkmal", "praktische Anwendung", "Auswirkungen und Folgen", "Hauptproblem", "Lösungsweg", "Belege", "Gesamtfazit"], "Welcher Ansatz hilft am besten, den Aspekt „{focus}“ zum Thema {topic} zu bestimmen?", ["Zuverlässige Quellen und Belege vergleichen", "Eine unbelegte Vermutung akzeptieren", "Nur eine Meinung berücksichtigen", "Themenfremde Informationen auswählen"]),
        "fr": (["concept clé", "contexte historique", "cause principale", "caractéristique importante", "application pratique", "effets et conséquences", "problème central", "solution possible", "éléments de preuve", "conclusion générale"], "Quelle approche permet le mieux d’identifier l’aspect « {focus} » du sujet {topic} ?", ["Comparer des sources fiables et des preuves", "Accepter une supposition sans preuve", "S’appuyer sur un seul point de vue", "Choisir des informations sans rapport avec le sujet"]),
    }
    focuses, question, options = bank.get(str(lang).lower(), bank["en"])
    lines = []
    for number in range(start, end + 1):
        focus = focuses[(number - 1) % len(focuses)]
        lines.extend([
            f"{number}. {question.format(topic=topic, focus=focus)}",
            f"A) {options[0]} (✓)", f"B) {options[1]}",
            f"C) {options[2]}", f"D) {options[3]}", "",
        ])
    return "\n".join(lines).strip()


def _numbered_question_count(text):
    cleaned = clean_ai_text(text or "")
    return sum(bool(re.match(r"^\s*(?:(?:question|вопрос|soru|frage)\s*)?\d{1,2}[.)]\s+", line, flags=re.I))
               for line in cleaned.splitlines())


async def _generate_test(service, topic, options, lang):
    """Generate exactly 10/15/20 questions, and never leak an invalid language response."""
    global LAST_ERROR
    lc = str(lang or "uz").lower()
    if lc not in ALL_LANGS:
        lc = "uz"
    try:
        requested = int(options.get("questions", options.get("pages", 20)) or 20)
    except (TypeError, ValueError):
        requested = 20
    count = requested if requested in (10, 15, 20) else min((10, 15, 20), key=lambda n: abs(n - requested))
    wiki = await wikipedia_fetch(topic, max_chars=5000, gen_lang=lc)
    ln = _lang_name(lc)
    all_questions, used_fallback = [], False
    chunk_size = 5
    for start in range(1, count + 1, chunk_size):
        end = min(count, start + chunk_size - 1)
        required = end - start + 1
        prompt = (
            f"Topic: {topic}. Write exactly {required} multiple-choice questions in {ln}, numbered {start} through {end}. "
            "Each question has four options A), B), C), D), with exactly one correct option marked (✓). "
            f"Output only the questions and options, entirely in {ln}. Do not add an answer-key section. "
            f"Use the following reference only for facts and translate its meaning into {ln}:\n{wiki_block(wiki, lc)}"
        )
        txt = await _chat_complete(prompt, system=_pure_language_system(lc), max_tokens=3000)

        def valid_chunk(value):
            cleaned = clean_ai_text(value or "")
            return bool(cleaned and not cleaned.startswith("⚠️")
                        and not _is_lang_mixed(cleaned, lc)
                        and not _document_text_is_repetitive(cleaned)
                        and _numbered_question_count(cleaned) == required)

        if not valid_chunk(txt):
            retry_prompt = prompt + f"\nRewrite from scratch in {ln} only. Return exactly {required} numbered questions, no explanations, no repeated wording."
            retried = await _chat_complete(
                retry_prompt, system=_pure_language_system(lc), max_tokens=3000,
                temperature=0.2, frequency_penalty=0.8, presence_penalty=0.6,
            )
            if valid_chunk(retried):
                txt = retried
            else:
                if not LAST_ERROR:
                    LAST_ERROR = (
                        f"AI javobi {start}-{end}-savollar uchun format/til tekshiruvidan o'tmadi; "
                        "shu qismga zaxira savollar qo'shildi."
                    )
                txt = _fallback_test_questions(topic, start, end, lc)
                used_fallback = True
        all_questions.append(clean_ai_text(txt))
        await asyncio.sleep(0.25)

    result = "\n\n".join(all_questions)
    return result, not used_fallback

# ====== SLAYDLAR GENERATSIYASI (Yangi shablonlar uchun QAT'IY struktura) ======
async def generate_slides_structured(topic, subject, lang, count):
    """Create exactly ``count`` body slides, all in the requested language.

    Each slide is language-checked on its own, so a foreign-language paragraph is
    replaced with localized text instead of leaking into the finished deck. The
    reference material is used for facts only; every sentence is re-written in the
    selected language.
    """
    global LAST_ERROR
    lc = str(lang or "uz").lower()
    if lc not in ALL_LANGS:
        lc = "uz"
    ln = _lang_name(lc)
    try:
        count = int(count)
    except (TypeError, ValueError):
        count = 7
    count = max(1, min(60, count))

    wiki = await wikipedia_fetch(topic, max_chars=7000, full=True, gen_lang=lc)
    wb = wiki_block(wiki, lc)
    source_line = ""
    if wiki.get("found"):
        source_line = (f"\nVerified source: {wiki.get('title')} ({wiki.get('url')}). "
                       "Copy its dates, names and figures exactly and never contradict it.")

    system = (_pure_language_system(lc) +
              f" You are a professional presentation writer. Write ONLY in {ln}. "
              "Return only a valid JSON array, with no explanation outside the JSON.")

    def build_prompt(n, skip_titles=()):
        skip_line = ""
        if skip_titles:
            skip_line = ("\nThese slide titles are already written and must NOT be repeated: "
                         + "; ".join(str(x) for x in list(skip_titles)[:20]) + ".\n")
        return f"""Topic: {topic}. Subject: {subject}.
Create exactly {n} CONTENT slides for a professional presentation. The cover and the agenda slide are added by the PowerPoint template, so do not return a cover slide or a table-of-contents slide.{skip_line}
STRICT LANGUAGE RULES:
1. Write every title and every content sentence only in the selected language ({ln}).
2. Translate headings into {ln}; keep proper names, official product names and standard technical terms that should not be translated.
3. Never insert Uzbek, English, Russian or any other language as decoration, filler or a repeated label.
4. Titles must be short, specific and natural in {ln}.

ACCURACY RULES:
1. Use verifiable facts from the reference below: dates, numbers, names, places, definitions and their meaning.
2. Never invent statistics, quotations, sources or dates. If a fact is unknown, describe it generally instead of inventing a figure.
3. Every slide must carry a different, topic-specific point; no generic filler and no repeated wording.

STRUCTURE RULES:
1. Return only a valid JSON array with exactly {n} objects.
2. Each object has "title" and "content". "title" is a specific heading of 3-9 words. "content" is an array of 6-7 COMPLETE sentences of 12-22 words each, enough real information to fill the whole slide: a definition, a date or figure, a cause, an example and a result.
3. Every sentence must add a fact, a date, a name, a figure, an example, a cause or a clear explanation. Never write empty filler such as "this is very important", "many aspects are studied" or "it plays a big role" without saying exactly what.
4. Never repeat a sentence, a title or a point anywhere in the deck. Do not write one-word bullets or placeholders.
5. Cover background, key concepts, evidence, comparison, practical application and implications across the deck.
6. The last slide must be a conclusion with practical recommendations, titled with the natural {ln} equivalent of "Conclusion".

Reference material (facts only; translate its meaning into {ln} and never copy its language):
{wb}{source_line}

JSON example (translate the sample wording into {ln} in the actual response):
[{{"title":"Section title","content":["Sentence one with a concrete fact.","Sentence two with a date or figure.","Sentence three explaining the cause.","Sentence four giving an example.","Sentence five stating the result."}}]"""

    async def request(extra="", n=None, skip_titles=()):
        wanted = count if n is None else max(1, min(60, int(n)))
        txt = await _chat_complete(build_prompt(wanted, skip_titles) + extra, system=system,
                                   max_tokens=min(7500, 4200 + 160 * wanted))
        return _extract_json(txt)

    def clean_entries(parsed):
        entries = []
        for item in parsed if isinstance(parsed, list) else []:
            if not isinstance(item, dict):
                continue
            title = clean_ai_text(str(item.get("title") or "")).strip()
            content = item.get("content", [])
            if isinstance(content, str):
                content = [part.strip(" •-\t") for part in content.splitlines() if part.strip()]
            content = [clean_ai_text(str(value)).strip() for value in content if str(value).strip()]
            if not title or not content:
                continue
            if _is_lang_mixed(" ".join(content), lc):
                continue  # foreign-language slide: replaced by localized text below
            if _is_lang_mixed(title, lc):
                # Keep the accurate body but never leave a title in another language.
                title, _ = _localized_slide_fallback(topic, lc, len(entries) + 1)
            entries.append({"title": title, "content": content})
        return entries

    all_slides = clean_entries(await request())
    combined = " ".join(f"{item['title']} {' '.join(item['content'])}" for item in all_slides)
    if len(all_slides) < count or _document_text_is_repetitive(combined):
        repaired = clean_entries(await request(
            f"\nFINAL CHECK: return exactly {count} slides. Every title and sentence must be in {ln} only, "
            "with no repeated wording and no phrases from any other language."
        ))
        if len(repaired) >= len(all_slides):
            all_slides = repaired

    used_fallback = False
    if not all_slides:
        LAST_ERROR = ("AI javobi yaroqli JSON/til tekshiruvidan o'tmadi; "
                      "taqdimot zaxira mazmun bilan tuzildi.")
        used_fallback = True

    # Keep the requested count exactly. Before using filler text, ask once for the
    # missing slides so a real deck is not padded with generic localized phrases.
    if len(all_slides) < count:
        if all_slides and not LAST_ERROR:
            LAST_ERROR = (f"AI faqat {len(all_slides)} ta yaroqli slayd qaytardi; "
                          "qolgan slaydlar zaxira mazmun bilan to'ldirildi.")
        used_fallback = True
    if all_slides and len(all_slides) < count:
        missing = count - len(all_slides)
        existing_titles = [item["title"] for item in all_slides]
        extra_slides = clean_entries(await request(
            f"\nFINAL CHECK: the deck still needs {missing} more slides about other real "
            f"aspects of the topic. Return exactly {missing} new slides written in {ln} only, "
            "and do not repeat any title listed above.",
            n=missing, skip_titles=existing_titles))
        all_slides.extend(extra_slides[:missing])
    while len(all_slides) < count:
        index = len(all_slides) + 1
        title_fallback, body_fallback = _localized_slide_fallback(topic, lc, index)
        all_slides.append({"title": title_fallback, "content": list(body_fallback)})
    all_slides = all_slides[:count]

    out = []
    for i, item in enumerate(all_slides):
        content = list(item["content"])
        while len(content) < 5:
            _, body_fallback = _localized_slide_fallback(topic, lc, i + 1)
            content.append(body_fallback[len(content) % len(body_fallback)])
        out.append({
            "slide_number": i + 1,
            "title": item["title"],
            "content": content[:6],
            "wiki_source": wiki["url"] if wiki.get("found") else None,
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

_GENERIC_IMAGE_WORDS = {
    "presentation", "slide", "slides", "topic", "concept", "concepts", "overview",
    "introduction", "education", "educational", "school", "study", "studies",
    "information", "knowledge", "general", "main", "important", "analysis", "example",
    "examples", "aspect", "aspects", "role", "significance", "development", "process",
    "result", "results", "conclusion",
}

_IMAGE_BLOCKED_TITLE_WORDS = (
    "logo", "icon", "flag", "coat of arms", "emblem", "seal of", "signature", "userbox",
    "wikimedia", "commons-logo", "disambig", "stub", "screenshot", "chart", "diagram",
    "graph", "poster", "book cover", "album cover", "stamp", "banknote", "coin",
    "plaque", "letterhead", "formula", "equation", "banner", ".svg", ".pdf",
    " map", "map of", "montage", "collage", "clipart", "sketch", "scan of",
    "wikidata", "wikisource", "template", "category:",
)


def _image_title_usable(title):
    """Reject file titles that are never a useful presentation photo."""
    low = str(title or "").casefold()
    return not any(word in low for word in _IMAGE_BLOCKED_TITLE_WORDS)


def _keyword_words(value):
    # \w keeps Cyrillic and Turkish letters, so a Russian topic is not silently
    # reduced to an empty keyword list.
    return [w for w in re.findall(r"[^\W\d_]{4,}", str(value or "").casefold())
            if w not in STOP_WORDS and w not in _GENERIC_IMAGE_WORDS]


_EN_PHRASE_CACHE = {}


async def english_phrase(text):
    """English name of a topic given in any language, via Wikipedia interlanguage links.

    Photo search must still find real pictures when every AI provider is down, so
    the English term comes from Wikipedia instead of a translation request.
    """
    raw = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(raw) < 3:
        return ""
    cache_key = raw.casefold()
    if cache_key in _EN_PHRASE_CACHE:
        return _EN_PHRASE_CACHE[cache_key]
    phrase = ""
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=12),
                                         headers={"User-Agent": USER_AGENT}) as session:
            for lang in wiki_langs_for_topic(raw, "uz"):
                try:
                    search_url = f"https://{lang}.wikipedia.org/w/api.php"
                    params = {"action": "query", "list": "search", "srsearch": raw,
                              "format": "json", "srlimit": 1}
                    async with session.get(search_url, params=params) as resp:
                        if resp.status != 200:
                            continue
                        hits = (await resp.json(content_type=None)).get("query", {}).get("search", [])
                    if not hits:
                        continue
                    title = str(hits[0].get("title") or "")
                    if not title:
                        continue
                    if lang == "en":
                        phrase = title
                        break
                    params = {"action": "query", "titles": title, "prop": "langlinks",
                              "lllang": "en", "format": "json", "redirects": 1}
                    async with session.get(search_url, params=params) as resp:
                        if resp.status != 200:
                            continue
                        pages = (await resp.json(content_type=None)).get("query", {}).get("pages", {})
                    page = next(iter(pages.values()), {}) if isinstance(pages, dict) else {}
                    links = page.get("langlinks") or []
                    if links and str(links[0].get("*") or "").strip():
                        phrase = str(links[0]["*"]).strip()
                        break
                except Exception as exc:
                    _log(f"English phrase lookup failed ({lang}): {type(exc).__name__}")
                    continue
    except Exception as exc:
        _log(f"English phrase session failed: {type(exc).__name__}: {exc}")
    match = re.search(r"\(([^)]*)\)", phrase)
    if match:
        # "Cell (biology)" -> "Cell biology": the disambiguator is the word that
        # makes the search specific, so it becomes part of the phrase.
        extra = re.sub(r"[^A-Za-z\s-]", " ", match.group(1))
        base = re.sub(r"\([^)]*\)", " ", phrase)
        phrase = re.sub(r"\s+", " ", f"{base} {extra}").strip()
    _EN_PHRASE_CACHE[cache_key] = phrase
    return phrase


async def topic_to_english_keywords(topic):
    global LAST_ERROR
    saved_error = LAST_ERROR
    key = str(topic or "").lower().strip()
    if not key:
        return ""
    if key in _KEYWORD_CACHE:
        return _KEYWORD_CACHE[key]
    for uz, en in SEARCH_MAP.items():
        if uz in key:
            _KEYWORD_CACHE[key] = en
            return en
    prompt = (
        "Write one English stock-photo search phrase of 2-4 CONCRETE nouns that finds a real "
        "photo illustrating exactly this school presentation topic. Do not use generic words "
        "such as presentation, education, concept, overview, information, or history/science "
        "alone. Use the exact English name of the person, place, object, organism, device or "
        "process.\nTopic: " + str(topic)
    )
    try:
        txt = await _chat_complete(
            prompt, system="You generate precise English image search phrases. Output the phrase only, no quotes, no explanation.",
            max_tokens=60, temperature=0.2)
        # A failed request answers with the warning line, and stripping it into a
        # "keyword" used to send every photo search after nonsense words.
        if not txt or str(txt).lstrip().startswith("⚠️"):
            raise ValueError("AI javob bermadi")
        kw = re.sub(r"[^A-Za-z\s-]", " ", str(txt or "")).strip()
        kw = re.sub(r"\s+", " ", kw)
        if 3 < len(kw) <= 80 and _keyword_words(kw):
            _KEYWORD_CACHE[key] = kw
            return kw
    except Exception:
        pass
    finally:
        # A helper request must never erase why the real generation failed.
        LAST_ERROR = saved_error
    en = await english_phrase(topic)
    _KEYWORD_CACHE[key] = en or str(topic)
    return en or str(topic)


async def image_keywords_batch(topic, titles, max_items=12):
    """One precise English image-search phrase per slide, generated in a single request."""
    items = [str(topic or "").strip()]
    items += [str(title or "").strip() for title in (titles or [])]
    items = [item for item in items if item][:max(1, int(max_items))]
    if not items:
        return []
    prompt = (
        "For each numbered item below write ONE English stock-photo search phrase of 2-4 "
        "concrete nouns that would find a real photo illustrating exactly that item. Never use "
        "generic words such as presentation, education, concept, overview, information, history "
        "alone or science alone. For a person or place use its English name plus what it is. "
        f"Return ONLY a JSON array of strings with exactly {len(items)} entries in the same "
        "order, and nothing else.\n" + "\n".join(f"{i + 1}. {item}" for i, item in enumerate(items))
    )
    global LAST_ERROR
    saved_error = LAST_ERROR
    try:
        txt = await _chat_complete(
            prompt, system="You generate precise, concrete English image search phrases. Output only a JSON array of strings.",
            max_tokens=500, temperature=0.2)
        parsed = _extract_json(txt)
        if isinstance(parsed, list):
            cleaned = []
            for value in parsed:
                phrase = re.sub(r"[^A-Za-z\s-]", " ", str(value or "")).strip()
                phrase = re.sub(r"\s+", " ", phrase)
                cleaned.append(phrase if phrase and _keyword_words(phrase) else "")
            if any(cleaned):
                while len(cleaned) < len(items):
                    cleaned.append("")
                return cleaned[:len(items)]
    except Exception as exc:
        _log(f"image keyword batch failed: {exc}")
    finally:
        LAST_ERROR = saved_error
    return []


async def _wiki_image(topic):
    try:
        wiki = await wikipedia_fetch(topic, max_chars=200)
        if wiki.get("image") and _image_title_usable(str(wiki.get("image"))):
            return [{"url": wiki["image"], "tags": str(wiki.get("title", "")).lower(), "src": "wikipedia"}]
    except Exception:
        pass
    return []


COMMONS_API = "https://commons.wikimedia.org/w/api.php"

# Credit line per chosen Commons photo, filled while scoring and read when the
# file is saved, so the deck can attribute the photographer and the licence.
_IMAGE_CREDITS: dict[str, str] = {}
# True only for photos whose subject is confirmed (article lead image, Wikidata
# "depicts", or the topic's curated Commons category). Free-text search hits stay
# False, so a slide never shows an unverified picture.
_IMAGE_VERIFIED: dict[str, bool] = {}


def image_credit(url):
    """Attribution for a Commons image URL ("Artist / Wikimedia Commons (CC BY-SA 4.0)")."""
    return _IMAGE_CREDITS.get(str(url or ""), "")


def _image_key(url):
    """Identity of an image file, ignoring thumbnail width and query string."""
    tail = str(url or "").split("?")[0].rsplit("/", 1)[-1]
    tail = re.sub(r"^\d+px-", "", tail).casefold()
    return tail or str(url or "")


def image_verified(url):
    """Whether this photo was confirmed to show the requested subject."""
    return bool(_IMAGE_VERIFIED.get(str(url or "")))


def _commons_search_tags(page, info):
    """Title, description and categories of a Commons file, lowercased."""
    title = re.sub(r"^file:", "", str(page.get("title", "")).casefold())
    title = re.sub(r"\.(jpe?g|png|webp|gif|tiff?|bmp)$", "", title)
    parts = [title]
    meta = info.get("extmetadata") or {}
    for key in ("ImageDescription", "Categories", "ObjectName", "Artist"):
        entry = meta.get(key)
        value = entry.get("value") if isinstance(entry, dict) else None
        if value:
            parts.append(re.sub(r"<[^>]+>", " ", str(value)))
    return re.sub(r"\s+", " ", " ".join(parts)).strip().casefold()


def _commons_credit(info):
    """Short attribution line for one Commons file: author and licence."""
    meta = info.get("extmetadata") or {}

    def field(key):
        entry = meta.get(key)
        value = entry.get("value") if isinstance(entry, dict) else None
        if not value:
            return ""
        text = re.sub(r"<[^>]+>", " ", str(value)).replace("&amp;", "&")
        return re.sub(r"\s+", " ", text).strip()

    artist, licence = field("Artist"), field("LicenseShortName")
    if not licence:
        return ""
    credit = f"{artist} / Wikimedia Commons ({licence})" if artist else f"Wikimedia Commons ({licence})"
    return credit[:160]


async def _commons_images(query, count=20):
    """Search Wikimedia Commons (free, no API key) for a real photo of the subject.

    Returns file titles, descriptions and categories so the caller can score how
    well a photo actually matches the slide instead of trusting the search order.
    """
    query = re.sub(r"\s+", " ", str(query or "")).strip()
    if len(query) < 3:
        return []
    params = {
        "action": "query", "generator": "search",
        # filetype:bitmap keeps SVG icons, logos and PDF documents out of the pool.
        "gsrsearch": f"{query} filetype:bitmap", "gsrnamespace": 6,
        "gsrlimit": max(20, min(40, int(count) * 2)),
        "prop": "imageinfo",
        "iiprop": "url|mime|size|extmetadata",
        "iiurlwidth": 1600,
        "format": "json", "formatversion": 2,
    }
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15),
                                         headers={"User-Agent": USER_AGENT}) as session:
            async with session.get(COMMONS_API, params=params) as resp:
                if resp.status != 200:
                    _log(f"Commons search HTTP {resp.status}")
                    return []
                data = await resp.json(content_type=None)
        return _commons_results(data)
    except Exception as exc:
        _log(f"Wikimedia Commons image search failed: {exc}")
        return []


def _commons_results(data):
    """Turn a Commons API response into usable photo candidates."""
    pages = data.get("query", {}).get("pages", [])
    if isinstance(pages, dict):
        pages = list(pages.values())
    results = []
    for page in pages:
        title = str(page.get("title", ""))
        if not _image_title_usable(title):
            continue
        for info in (page.get("imageinfo") or [])[:1]:
            mime = str(info.get("mime", ""))
            url = info.get("thumburl") or info.get("url")
            width = int(info.get("thumbwidth", info.get("width", 0)) or 0)
            height = int(info.get("thumbheight", info.get("height", 0)) or 0)
            if not url or mime not in ("image/jpeg", "image/png", "image/webp"):
                continue
            if width and height and (width < 800 or height < 450):
                continue
            results.append({
                "url": url,
                "tags": _commons_search_tags(page, info),
                "title": title,
                "width": width,
                "height": height,
                "credit": _commons_credit(info),
                "src": "commons",
            })
    return results


_ENTITY_CACHE: dict[str, tuple[str, str]] = {}


async def _wikidata_entity(name):
    """(Wikidata item, curated Commons category) for a Wikipedia article title.

    Wikimedia names an article in one spelling ("Ali-Shir Nava'i") and the user
    types another ("Alisher Navoiy"); the item id is the bridge that lets a photo
    be verified against the real subject instead of against a spelling.
    """
    key = re.sub(r"\s+", " ", str(name or "")).strip().casefold()
    if len(key) < 3:
        return "", ""
    if key in _ENTITY_CACHE:
        return _ENTITY_CACHE[key]
    qid, category = "", ""
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=12),
                                         headers={"User-Agent": USER_AGENT}) as session:
            params = {"action": "query", "titles": name, "prop": "pageprops",
                      "ppprop": "wikibase_item", "format": "json", "redirects": 1}
            async with session.get("https://en.wikipedia.org/w/api.php", params=params) as resp:
                if resp.status == 200:
                    pages = (await resp.json(content_type=None)).get("query", {}).get("pages", {})
                    page = next(iter(pages.values()), {}) if isinstance(pages, dict) else {}
                    qid = str((page.get("pageprops") or {}).get("wikibase_item") or "")
            if qid:
                params = {"action": "wbgetclaims", "entity": qid,
                          "property": "P373", "format": "json"}
                async with session.get("https://www.wikidata.org/w/api.php", params=params) as resp:
                    if resp.status == 200:
                        claims = ((await resp.json(content_type=None)).get("claims", {})
                                  .get("P373") or [])
                        for claim in claims:
                            value = (claim.get("mainsnak", {}).get("datavalue") or {}).get("value")
                            if value:
                                category = str(value).strip()
                                break
    except Exception as exc:
        _log(f"Wikidata entity lookup failed for {name!r}: {type(exc).__name__}")
    _ENTITY_CACHE[key] = (qid, category)
    return qid, category


async def _commons_category_name(name):
    """The Commons category Wikidata files a topic's pictures under."""
    return (await _wikidata_entity(name))[1]


async def _commons_depicts_images(qid, count=20):
    """Commons files whose structured data says they depict this exact item.

    Wikimedia volunteers tag portraits and monuments with "depicts" (P180), which
    is a human verification that the picture really shows the subject.
    """
    qid = str(qid or "").strip()
    if not qid.startswith("Q"):
        return []
    params = {
        "action": "query", "generator": "search",
        "gsrsearch": f"haswbstatement:P180={qid} filetype:bitmap",
        "gsrnamespace": 6, "gsrlimit": max(10, min(30, int(count))),
        "prop": "imageinfo", "iiprop": "url|mime|size|extmetadata",
        "iiurlwidth": 1600, "format": "json", "formatversion": 2,
    }
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15),
                                         headers={"User-Agent": USER_AGENT}) as session:
            async with session.get(COMMONS_API, params=params) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json(content_type=None)
        return [dict(item, src="commons_depicts") for item in _commons_results(data)]
    except Exception as exc:
        _log(f"Commons depicts lookup failed ({qid}): {type(exc).__name__}")
        return []


OPENVERSE_API = "https://api.openverse.org/v1/images/"


async def _openverse_images(query, count=20):
    """Openverse: one free API over Flickr, museums and other CC archives."""
    query = re.sub(r"\s+", " ", str(query or "")).strip()
    if len(query) < 3:
        return []
    params = {"q": query, "page_size": max(10, min(20, int(count))),
              "license_type": "all", "mature": "false"}
    try:
        data = {}
        for attempt in range(2):
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15),
                                             headers={"User-Agent": USER_AGENT}) as session:
                async with session.get(OPENVERSE_API, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json(content_type=None)
                        break
                    if resp.status in (429, 500, 502, 503, 504) and attempt == 0:
                        await asyncio.sleep(1.5)
                        continue
                    _log(f"Openverse HTTP {resp.status}")
                    return []
        results = []
        for item in data.get("results") or []:
            url = item.get("url")
            if not url:
                continue
            results.append({
                "url": url,
                "tags": (str(item.get("title") or "") + " " + str(item.get("tags") or "")
                         + " " + str(item.get("creator") or "")).casefold(),
                "title": str(item.get("title") or ""),
                "width": int(item.get("width") or 0),
                "height": int(item.get("height") or 0),
                "credit": (str(item.get("creator") or "").strip()
                           + " / " + str(item.get("source") or "Openverse")
                           + " (" + str(item.get("license") or "?").upper() + ")").strip(),
                "src": "openverse",
            })
        return results
    except Exception as exc:
        _log(f"Openverse search failed: {type(exc).__name__}")
        return []


async def _commons_category_images(name, count=15):
    """Photos filed under the topic's curated Commons category.

    Wikimedia volunteers keep these folders by subject, so "Timur" leads to the
    conqueror's portraits instead of every place whose name means "east". The
    category name comes from Wikidata (P373), which is the authoritative link
    between a Wikipedia article and its Commons folder.
    """
    raw = re.sub(r"\s+", " ", str(name or "")).strip()
    if len(raw) < 3:
        return []
    category = await _commons_category_name(raw) or raw
    params = {
        "action": "query", "generator": "search",
        # incategory keeps the search inside the curated folder, filetype keeps
        # PDFs and audio out of the result set.
        "gsrsearch": f'incategory:"{category}" filetype:bitmap',
        "gsrnamespace": 6, "gsrlimit": max(10, min(30, int(count))),
        "prop": "imageinfo", "iiprop": "url|mime|size|extmetadata",
        "iiurlwidth": 1600, "format": "json", "formatversion": 2,
    }
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15),
                                         headers={"User-Agent": USER_AGENT}) as session:
            async with session.get(COMMONS_API, params=params) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json(content_type=None)
        return [dict(item, src="commons_category") for item in _commons_results(data)]
    except Exception as exc:
        _log(f"Commons category lookup failed ({category}): {type(exc).__name__}")
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


async def search_images(query, count=5, keywords=None, use_wiki=True):
    """Return only images whose own tags really match the requested subject.

    A weak one-word tag hit used to be enough, which is why unrelated photos ended
    up in the deck. Now the main keyword must appear, Commons titles are checked,
    and the article's own Wikipedia image is preferred.
    """
    q = re.sub(r"[^\w\s']", " ", str(query or "")).strip()
    if len(q) < 3:
        return []
    kw_source = keywords if keywords is not None else await topic_to_english_keywords(q)
    kw_list = _keyword_words(kw_source)
    if not kw_list:
        return []
    primary = kw_list[0]
    # Resolve the subject once: its Wikidata item proves which files really show it.
    qid, _category = await _wikidata_entity(str(kw_source))
    tasks = [
        _commons_depicts_images(qid, count=20),
        _commons_category_images(str(kw_source), count=20),
        _commons_images(str(kw_source), count=20),
        _openverse_images(str(kw_source), count=20),
        _pixabay_images(str(kw_source)),
        _pexels_images(str(kw_source)),
        _unsplash_images(str(kw_source)),
    ]
    if use_wiki:
        tasks.insert(0, _wiki_image(q))
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Photos filed under the topic's own Commons category are curated by subject,
    # so when that folder alone can fill the request, loose full-text hits are
    # skipped: they are what put unrelated pictures into the deck.
    def _describe(candidate):
        tags = str(candidate.get("tags") or "").casefold()
        title = str(candidate.get("title") or "").casefold()
        title = re.sub(r"^file:", "", title)
        title = re.sub(r"\.(jpe?g|png|webp|gif|tiff?|bmp)$", "", title)
        title_words = set(re.findall(r"[^\W\d_]{3,}", title))
        matches = sum(1 for word in kw_list
                      if word in set(re.findall(r"[^\W_]+", tags)) or word in tags)
        return tags, title, title_words, matches

    VERIFIED_SOURCES = ("wikipedia", "commons_depicts", "commons_category")
    # When the verified sources can fill the deck, unverified free-text hits are
    # left out entirely: they are what produced basketball hoops and dolphins on a
    # slide about a poet.
    verified_pool = 0
    for group in results:
        if isinstance(group, list):
            verified_pool += sum(1 for item in group if isinstance(item, dict)
                                 and item.get("src") in VERIFIED_SOURCES)
    verified_only = verified_pool >= max(1, int(count))

    candidates, seen = [], set()
    for group in results:
        if isinstance(group, Exception) or not group:
            continue
        for candidate in group:
            if not isinstance(candidate, dict):
                continue
            url = candidate.get("url")
            key = _image_key(url)
            if not url or key in seen:
                continue
            src = candidate.get("src")
            verified = src in VERIFIED_SOURCES
            if verified_only and not verified:
                continue
            tags, title, title_words, matches = _describe(candidate)
            width = int(candidate.get("width") or 0)
            height = int(candidate.get("height") or 0)
            if src == "wikipedia":
                # The article's own lead image is the most reliable topical match.
                score = 110
            elif src == "commons_depicts":
                # Wikidata says the file depicts this exact item.
                score = 100
            elif src == "commons_category":
                # Curated folder of the subject; no wording gate, because the
                # category name is often a different spelling/transliteration.
                score = 85
            elif src == "openverse":
                if not matches or primary not in title_words:
                    continue
                score = 35
                verified = False
            elif src == "commons":
                # Tags are the file title, description and categories, so the photo
                # has to mention the slide's own words, not just one of them.
                if not matches:
                    continue
                if len(kw_list) >= 2 and matches < 2 and primary not in tags:
                    continue
                if len(kw_list) == 1 and primary not in title_words:
                    # "cell" alone also appears in "grape cells" and "prison cell".
                    continue
                score = 20 + matches * 6 + (10 if primary in tags else 0)
                # A file named almost exactly like the slide beats one that only
                # mentions the subject in passing, and a street, school or venue
                # named after the subject is not the subject itself.
                extra = max(0, len([w for w in title_words if w not in STOP_WORDS]) - matches)
                score += max(0, 8 - extra)
                if any(word in title for word in (
                        "street", "ko'chasi", "kochesi", "avenue", "prospekt",
                        "school", "maktab", "district", "tuman", "village", "qishloq",
                        "binosi", "building", "metre", "station")):
                    score -= 8
            else:
                if matches < 1:
                    continue
                score = 10 + matches * 3
                verified = False
            if str(kw_source).casefold().strip() and title.startswith(str(kw_source).casefold().strip()):
                score += 12
            if verified:
                # Among verified photos, prefer the one whose file name is closest to
                # the subject ("Cell structure") over a tangentially related file
                # ("Cryptomonas curvata anterior view").
                extra = max(0, len([w for w in title_words if w not in STOP_WORDS]) - matches)
                score += max(0, 6 - extra)
            if width and height and width >= height:
                # Landscape photos fill the slide photo slot without cropping.
                score += 3
            seen.add(key)
            _IMAGE_VERIFIED[url] = bool(verified)
            if candidate.get("credit"):
                _IMAGE_CREDITS[url] = str(candidate["credit"])
            candidates.append((score, url))
    candidates.sort(key=lambda pair: -pair[0])
    return [url for _, url in candidates][:max(1, int(count))]


async def download_image(url, save_path):
    """Download and validate an image; re-encode it to a safe JPEG for PPTX."""
    try:
        from PIL import Image, ImageOps
        raw, content_type = b"", ""
        # Wikimedia's thumbnail servers answer 429 when a deck requests ten photos
        # at once; one short pause turns that into a successful download.
        for attempt in range(3):
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=20),
                headers={"User-Agent": USER_AGENT},
            ) as session:
                async with session.get(url) as resp:
                    if resp.status in (429, 500, 502, 503, 504):
                        await asyncio.sleep(0.8 * (attempt + 1))
                        continue
                    if resp.status != 200:
                        return False
                    content_type = str(resp.headers.get("Content-Type", "")).lower()
                    raw = await resp.read()
                    break
        if not raw:
            return False
        if len(raw) > 20 * 1024 * 1024:
            return False
        if content_type and not content_type.startswith("image/"):
            return False
        with Image.open(io.BytesIO(raw)) as source:
            source.load()
            image = ImageOps.exif_transpose(source).convert("RGB")
            if image.width < 240 or image.height < 160:
                return False
            image.save(save_path, format="JPEG", quality=88, optimize=True)
        # Keep the attribution next to the file so the deck can print it.
        credit = image_credit(url)
        if credit:
            try:
                with open(str(save_path) + ".credit", "w", encoding="utf-8") as handle:
                    handle.write(credit)
            except OSError:
                pass
        return True
    except Exception as exc:
        _log(f"Image download/validation failed: {type(exc).__name__}: {exc}")
        return False

def _error_detail(status, body):
    """Keep the provider's own reason (rate limit, quota, bad key, unknown model).

    The body is what tells a model-level limit apart from a key-level one, and it is
    what the user finally sees under the generated file, so never drop it to a bare
    ``HTTP 429``.
    """
    text = re.sub(r"<[^>]{1,120}>", " ", str(body or ""))
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return f"HTTP {status}"
    return f"HTTP {status}: {text[:200]}"

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
                    return resp.status, None, _error_detail(resp.status, body)
        else:
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api['api_key']}"}
            url = f"{api['base_url']}/chat/completions"
            p = dict(payload); p["model"] = model
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=AI_TIMEOUT)) as session:
                async with session.post(url, headers=headers, json=p, timeout=AI_TIMEOUT) as resp:
                    body = await resp.text()
                    if resp.status == 200:
                        LAST_ERROR = None
                        try:
                            message = json.loads(body)["choices"][0]["message"]
                        except Exception as e:
                            return resp.status, None, str(e)
                        content = message.get("content")
                        if content and str(content).strip():
                            return 200, content, None
                        if message.get("reasoning") or message.get("reasoning_content"):
                            return resp.status, None, "faqat reasoning qaytardi (content bo'sh)"
                        return resp.status, None, "bo'sh javob (HTTP 200)"
                    return resp.status, None, _error_detail(resp.status, body)
    except Exception as e: return None, None, str(e)

# Provider-side hard limits: `allam-2-7b` rejects max_tokens above 4096 with
# HTTP 400, which used to burn an attempt on every single generation.
MODEL_MAX_TOKENS = {"allam-2-7b": 4096}


def _model_payload(payload, model):
    """Adjust a request for the quirks of one concrete model."""
    p = dict(payload)
    cap = MODEL_MAX_TOKENS.get(str(model).lower())
    if cap and int(p.get("max_tokens") or 0) > cap:
        p["max_tokens"] = cap
    if "gpt-oss" in str(model).lower():
        # Without a low reasoning effort these models spend the whole token
        # budget on hidden reasoning and answer with empty content (HTTP 200).
        p["reasoning_effort"] = "low"
    return p


_MODEL_CACHE = {}
_MODEL_CACHE_TTL = 1800
_BAD_MODEL_WORDS = ("embed", "whisper", "tts", "moderation", "rerank", "ocr", "dall",
                    "image", "audio", "video", "sora", "guard", "deprecated", "codex-mini")
_GOOD_MODEL_FILE = os.path.join(DATA_DIR, "ai_good_models.json")
_GOOD_MODELS = None


def _load_good_models():
    global _GOOD_MODELS
    if _GOOD_MODELS is None:
        try:
            with open(_GOOD_MODEL_FILE, encoding="utf-8") as handle:
                loaded = json.load(handle)
            _GOOD_MODELS = loaded if isinstance(loaded, dict) else {}
        except Exception:
            _GOOD_MODELS = {}
    return _GOOD_MODELS


def _good_model(api):
    """The model that last answered for this provider, tried first after a restart."""
    return _load_good_models().get(str(api.get("name") or ""))


def _save_good_model(api, model):
    name = str(api.get("name") or "")
    state = _load_good_models()
    if not name or state.get(name) == model:
        return
    state[name] = model
    try:
        with open(_GOOD_MODEL_FILE, "w", encoding="utf-8") as handle:
            json.dump(state, handle)
    except Exception:
        pass


def _clean_model_id(api, value):
    model = str(value or "").strip()
    if api.get("type") == "google" and model.startswith("models/"):
        model = model[len("models/"):]
    return model


async def _discover_models(api):
    """Ask the provider which models it actually serves right now.

    Hardcoded names rot: once a provider retires a model every request answers 404
    and the bot falls back to sample content although the key is fine. The live
    catalogue is cached for half an hour so this costs one request per provider.
    """
    base = str(api.get("base_url") or "").rstrip("/")
    key = str(api.get("api_key") or "")
    if not base or not key:
        return []
    cache_key = f"{base}|{key[-6:]}"
    cached = _MODEL_CACHE.get(cache_key)
    if cached and time.time() - cached[0] < _MODEL_CACHE_TTL:
        return list(cached[1])
    ids = []
    try:
        headers = {"Authorization": f"Bearer {key}"}
        url = f"{base}/models?key={key}" if api.get("type") == "google" else f"{base}/models"
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=12),
                                         headers=headers) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    _log(f"Model ro'yxati olinmadi ({api.get('name')}): HTTP {resp.status}")
                    return []
                data = await resp.json(content_type=None)
        for item in (data.get("data") or data.get("models") or []):
            if isinstance(item, str):
                model_id = item
            else:
                methods = item.get("supportedGenerationMethods") or []
                if methods and "generateContent" not in methods:
                    continue
                model_id = item.get("id") or item.get("name") or ""
            model_id = _clean_model_id(api, model_id)
            if not model_id or any(word in model_id.lower() for word in _BAD_MODEL_WORDS):
                continue
            ids.append(model_id)
    except Exception as exc:
        _log(f"Model discovery failed ({api.get('name')}): {type(exc).__name__}: {exc}")
        return []
    # OpenRouter lists paid and free twins of the same model: without credit the
    # paid ones answer 402, so the free ones go first.
    free = [model for model in ids if model.endswith(":free")]
    if free:
        ids = free + [model for model in ids if not model.endswith(":free")]
    ids = ids[:8]
    _MODEL_CACHE[cache_key] = (time.time(), ids)
    return ids


async def _models_for_api(api):
    """Last good model, the provider's live catalogue, then the configured names."""
    models = []
    for model in [_good_model(api)] + await _discover_models(api) + list(api.get("models") or []):
        model = _clean_model_id(api, model)
        if model and model not in models:
            models.append(model)
    return models[:12]


async def _chat_complete(prompt, system=None, max_tokens=2500, temperature=0.5,
                         frequency_penalty=0.7, presence_penalty=0.5, history=None):
    """Try every configured model across every provider before returning fallback text.

    Previous implementation stopped as soon as the first provider's models ran out,
    so configured backups were never reached. Keep a local ordered attempt list to
    make each request complete its own failover cycle.

    ``history`` carries previous chat turns (``[{"role": ..., "content": ...}]``)
    so follow-up questions keep their context instead of starting from scratch.
    """
    global CURRENT_API_INDEX, CURRENT_MODEL_INDEX, LAST_ERROR
    messages = []
    if system:
        messages.append({"role": "system", "content": str(system)})
    for item in history or []:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip().lower()
        content = str(item.get("content") or "").strip()
        if role not in ("user", "assistant") or not content:
            continue
        messages.append({"role": role, "content": content[:4000]})
    messages.append({"role": "user", "content": str(prompt)})
    payload = {
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "frequency_penalty": frequency_penalty,
        "presence_penalty": presence_penalty,
    }

    if not API_LIST:
        LAST_ERROR = "API_LIST bo'sh — hech qanday AI provayder sozlanmagan"
        return "⚠️ AI serverga ulanib bo'lmadi."

    start_api = CURRENT_API_INDEX % len(API_LIST)
    errors = []
    attempts = 0
    for api_offset in range(len(API_LIST)):
        api_index = (start_api + api_offset) % len(API_LIST)
        api = API_LIST[api_index]
        if not api.get("api_key"):
            errors.append(f"{api.get('name', 'API')}: kalit sozlanmagan")
            continue
        models = await _models_for_api(api)
        if not models:
            errors.append(f"{api.get('name', 'API')}: model topilmadi "
                          "(kalit noto'g'ri yoki /models javob bermadi)")
            continue
        # A 429 can mean "this model's limit is gone" or "this whole key is
        # rate-limited". Give the provider's next model one chance before treating
        # it as key-level and moving on to the next configured provider.
        consecutive_rate_limits = 0
        for model_index, model in enumerate(models):
            attempts += 1
            status, answer, error = await _try_post(api, model, _model_payload(payload, model))
            if status == 200 and answer and answer.strip():
                CURRENT_API_INDEX = api_index
                CURRENT_MODEL_INDEX = 0
                _save_good_model(api, model)
                LAST_ERROR = None
                _log(f"✅ Ishladi: {api.get('name', 'API')} → {model}")
                return clean_ai_text(answer).strip()
            reason = error or f"bo'sh javob (HTTP {status})"
            detail = f"{api.get('name', 'API')} / {model}: {reason}"
            errors.append(detail)
            _log(f"❌ {detail}")
            # Rejected credentials or an unpaid provider are key-level problems:
            # every other model on the same key would fail the same way.
            if status in (401, 402, 403):
                break
            if status == 429:
                consecutive_rate_limits += 1
                await asyncio.sleep(0.25)
                if consecutive_rate_limits >= 2:
                    break
                continue
            consecutive_rate_limits = 0
        # brief pause between providers to avoid immediate rate-limit bursts
        if api_offset < len(API_LIST) - 1:
            await asyncio.sleep(0.15)

    LAST_ERROR = f"Barcha AI urinishlari muvaffaqiyatsiz ({attempts} model). " + " | ".join(errors[-4:])
    _log("⚠️ Barcha sozlangan AI provayderlari sinab ko'rildi; natija olinmadi.")
    return "⚠️ AI serverga ulanib bo'lmadi."

CHAT_LANGUAGE_NAMES = {
    "uz": "Uzbek, using the Latin alphabet",
    "ru": "Russian, using Cyrillic",
    "en": "English",
    "tr": "Turkish",
    "de": "German",
    "fr": "French",
    "ar": "Arabic, using Arabic script",
    "es": "Spanish",
    "pt": "Portuguese",
    "it": "Italian",
    "zh": "Chinese",
    "hi": "Hindi",
}

_CHAT_WORDS = {
    "uz": {"salom", "assalomu", "alaykum", "haqida", "nima", "nma", "qanday", "qanaqa", "qayerda", "qayer", "qachon", "nega", "ne", "uchun", "bilan", "kerak", "mumkin", "men", "siz", "menga", "sen", "senga", "u", "unga", "bu", "shu", "ana", "ham", "va", "lekin", "ammo", "faqat", "chunki", "yoki", "keyin", "hozir", "endi", "kim", "narsa", "kishi", "qiladi", "qilaman", "qildi", "beradi", "beraman", "aytadi", "aytaman", "yozadi", "yozaman", "o'qiydi", "biladi", "bilaman", "tushuntir", "yozib", "yozing", "iltimos", "rahmat", "bo'ladi", "bo'ldi", "emas", "emasmi", "mi", "mu", "qaysi", "o'zbek", "o‘zbek", "qilib", "qil", "ber", "ayt", "keldi", "ketdi", "bor", "yo'q", "yaxshi", "katta", "kichik", "ko'p", "oz"},
    "en": {"hello", "hi", "hey", "what", "how", "why", "where", "when", "about", "please", "tell", "explain", "help", "thanks", "thank", "you", "your", "can", "could", "would", "is", "are", "the", "and", "for", "with", "from", "does", "do", "make", "write", "answer"},
    "ru": {"привет", "здравствуйте", "добрый", "день", "вечер", "как", "что", "почему", "где", "когда", "расскажи", "объясни", "пожалуйста", "спасибо", "напиши", "ответь", "это", "для", "про", "меня"},
    "tr": {"merhaba", "selam", "nasıl", "neden", "hakkında", "için", "lütfen", "teşekkürler", "anlat", "açıkla", "yaz", "nedir", "hangi"},
    "de": {"hallo", "guten", "morgen", "abend", "wie", "warum", "wo", "wann", "über", "bitte", "danke", "erkläre", "schreibe", "was", "ist", "und", "der", "die", "das"},
    "fr": {"bonjour", "salut", "bonsoir", "comment", "pourquoi", "où", "quand", "sur", "à propos", "merci", "veuillez", "explique", "écris", "quoi", "avec", "pour"},
    "es": {"hola", "buenos", "buenas", "cómo", "qué", "por", "para", "gracias", "explícame", "escribe", "sobre", "dónde"},
    "pt": {"olá", "ola", "bom", "dia", "como", "porque", "obrigado", "obrigada", "por favor", "explique", "escreva"},
    "it": {"ciao", "buongiorno", "buonasera", "come", "perché", "dove", "quando", "grazie", "spiega", "scrivi"},
}

_CHAT_GREETINGS = {
    "salom": ("uz", "Salom! Qanday yordam bera olaman?"),
    "assalomu alaykum": ("uz", "Va alaykum assalom! Qanday yordam bera olaman?"),
    "assalomu alaykum!": ("uz", "Va alaykum assalom! Qanday yordam bera olaman?"),
    "hello": ("en", "Hello! How can I help you?"),
    "hi": ("en", "Hi! What can I help you with?"),
    "hey": ("en", "Hey! How can I help you?"),
    "привет": ("ru", "Привет! Чем могу помочь?"),
    "здравствуйте": ("ru", "Здравствуйте! Чем могу помочь?"),
    "merhaba": ("tr", "Merhaba! Size nasıl yardımcı olabilirim?"),
    "selam": ("tr", "Selam! Nasıl yardımcı olabilirim?"),
    "hallo": ("de", "Hallo! Wie kann ich dir helfen?"),
    "guten tag": ("de", "Guten Tag! Wie kann ich Ihnen helfen?"),
    "bonjour": ("fr", "Bonjour ! Comment puis-je vous aider ?"),
    "salut": ("fr", "Salut ! Comment puis-je vous aider ?"),
    "hola": ("es", "¡Hola! ¿En qué puedo ayudarte?"),
    "ciao": ("it", "Ciao! Come posso aiutarti?"),
    "olá": ("pt", "Olá! Como posso ajudar?"),
    "مرحبا": ("ar", "مرحبًا! كيف يمكنني مساعدتك؟"),
}


def _chat_tokens(text):
    return re.findall(r"[^\W\d_]+(?:['’][^\W\d_]+)?", str(text or "").casefold(), flags=re.UNICODE)


_TRANSLATION_CUES = (r"tarjima", r"o['’]gir", r"перевед", r"перевод", r"переклад",
                     r"\btranslate\b", r"\btranslation\b", r"übersetz", r"traduc",
                     r"traduz", r"переведи")

_TARGET_LANGUAGE_WORDS = (
    ("uz", ("o'zbek", "o‘zbek", "узбек", "uzbek")),
    ("ru", ("rus tili", "ruscha", "rus tiliga", "русск", "russian")),
    ("en", ("ingliz", "английск", "english")),
    ("tr", ("turk tili", "turkcha", "türkçe", "турецк", "turkish")),
    ("de", ("nemis", "немецк", "german", "deutsch")),
    ("fr", ("fransuz", "француз", "french", "français", "francais")),
    ("ar", ("arab tili", "arabcha", "арабск", "arabic")),
    ("es", ("ispan", "испанск", "spanish", "español")),
    ("zh", ("xitoy", "китайск", "chinese", "中文")),
)


def _wants_translation(text):
    """True when the message asks for a translation rather than a plain answer."""
    t = str(text or "").casefold().replace("’", "'")
    return any(re.search(pattern, t) for pattern in _TRANSLATION_CUES)


def _requested_chat_language(text):
    """Respect an explicit instruction to answer or translate into another language."""
    t = str(text or "").casefold().replace("’", "'")
    patterns = [
        ("uz", (r"o'zbek(cha)? (tilida|javob)", r"uzbek(cha)? (yoz|javob)", r"translate into uzbek", r"in uzbek")),
        ("ru", (r"rus(cha)? (tilida|javob|yoz)", r"на русском", r"переведи на русский", r"in russian", r"translate into russian")),
        ("en", (r"ingliz(cha)? (tilida|javob|yoz)", r"на английском", r"in english", r"answer in english", r"translate into english")),
        ("tr", (r"turk(cha)? (tilida|javob|yoz)", r"in turkish", r"translate into turkish", r"türkçe")),
        ("de", (r"nemis(cha)? (tilida|javob|yoz)", r"in german", r"auf deutsch", r"translate into german")),
        ("fr", (r"fransuz(cha)? (tilida|javob|yoz)", r"in french", r"en français", r"translate into french")),
        ("ar", (r"arab(cha)? (tilida|javob|yoz)", r"in arabic", r"بالعربية")),
        ("es", (r"in spanish", r"español", r"en español", r"ispan(cha)? (tilida|javob)")),
        ("zh", (r"in chinese", r"中文", r"xitoy(cha)? (tilida|javob)")),
    ]
    for lang, regexes in patterns:
        if any(re.search(p, t) for p in regexes):
            return lang
    # Requests such as "ingliz tiliga tarjima qil" or "переведи на немецкий" name
    # the target language instead of saying "in English".
    if _wants_translation(t):
        for lang, words in _TARGET_LANGUAGE_WORDS:
            if any(word in t for word in words):
                return lang
    return None


def _detect_chat_language(text, fallback="uz"):
    """Detect the language of the actual message; don't blindly use the bot UI language."""
    raw = str(text or "").strip()
    if not raw:
        return fallback if fallback in CHAT_LANGUAGE_NAMES else "uz"
    t = raw.casefold().strip(" .,!?:;\"'`()[]{}")
    requested = _requested_chat_language(raw)
    if requested:
        return requested
    if any("\u0600" <= ch <= "\u06ff" for ch in raw):
        return "ar"
    cyrillic = len(re.findall(r"[А-Яа-яЁё]", raw))
    letters = len(re.findall(r"[A-Za-zА-Яа-яЁё]", raw))
    if cyrillic >= 2 and cyrillic / max(1, letters) >= 0.25:
        return "ru"

    # Exact common greetings must not be handed to an LLM for language guessing.
    compact = re.sub(r"\s+", " ", t)
    compact = re.sub(r"[.!?]+$", "", compact).strip()
    if compact in _CHAT_GREETINGS:
        return _CHAT_GREETINGS[compact][0]

    tokens = set(_chat_tokens(raw))
    # Uzbek-specific characters and frequent words provide a strong signal.
    # "nma" (nima qisqartmasi), "kim", "nega" kabi so'zlar ham qo'shildi.
    uz_early = {"haqida", "qanday", "qanaqa", "qayerda", "qayer", "qachon", "nega", "ne",
                "uchun", "mumkin", "kerak", "salom", "rahmat", "iltimos", "o'zbek",
                "nima", "nma", "kim", "chunki", "lekin", "ammo", "faqat", "tushuntir",
                "qiladi", "qilaman", "beradi", "aytadi", "yozadi", "bilaman", "emasmi",
                "narsa", "kishi", "keyin", "hozir", "endi", "yaxshi", "bor", "yo'q",
                "ko'p", "o'zi", "o'qima", "ayt", "ber", "qil", "yoz"}
    if re.search(r"[ʻʼ‘’]", raw) or any(w in tokens for w in uz_early):
        return "uz"
    if any(ch in raw for ch in "ğışİı") or any(w in tokens for w in {"merhaba", "nasıl", "hakkında", "teşekkürler"}):
        return "tr"
    if any(ch in raw for ch in "äöüß") or any(w in tokens for w in {"hallo", "danke", "bitte", "warum", "erkläre"}):
        return "de"
    if any(ch in raw for ch in "àâçéèêëîïôùûüÿœ") or any(w in tokens for w in {"bonjour", "salut", "merci", "pourquoi", "comment"}):
        return "fr"
    if any(w in tokens for w in {"hola", "cómo", "gracias", "español"}):
        return "es"
    if any(w in tokens for w in {"olá", "obrigado", "obrigada"}):
        return "pt"
    if any(w in tokens for w in {"ciao", "grazie", "perché"}):
        return "it"

    scores = {lang: len(tokens & words) for lang, words in _CHAT_WORDS.items()}
    best = max(scores, key=scores.get)
    if scores[best] > 0 and scores[best] >= scores.get("uz", 0):
        return best
    # Ambiguous short text falls back to the user's selected interface language,
    # but a clear English greeting such as "hello" was already handled above.
    return fallback if fallback in CHAT_LANGUAGE_NAMES else "uz"

def _chat_answer_is_repetitive(text):
    words = _chat_tokens(text)
    if len(words) < 35:
        return False
    if len(set(words)) / max(1, len(words)) < 0.28:
        return True
    # Reject copied loop fragments such as a phrase repeated dozens of times.
    for n, threshold in ((5, 4), (4, 6), (3, 9)):
        grams = Counter(tuple(words[i:i+n]) for i in range(len(words) - n + 1))
        if grams and max(grams.values()) >= threshold:
            return True
    sentences = [re.sub(r"\W+", " ", s.casefold()).strip() for s in re.split(r"[.!?\n]+", str(text or "")) if len(s.split()) >= 6]
    sent_counts = Counter(sentences)
    if sent_counts and max(sent_counts.values()) >= 3:
        return True
    return False


def _chat_answer_wrong_script(text, lang):
    raw = str(text or "")
    letters = len(re.findall(r"[A-Za-zА-Яа-яЁё\u0600-\u06ff]", raw))
    if not letters:
        return True
    arabic = len(re.findall(r"[\u0600-\u06ff]", raw))
    cyr = len(re.findall(r"[А-Яа-яЁё]", raw))
    if lang != "ar" and arabic / letters > 0.08:
        return True
    if lang not in ("ru",) and cyr / letters > 0.22:
        return True
    if lang == "ru" and cyr / letters < 0.18 and len(raw) > 80:
        return True
    # Detect obvious Uzbek/English swaps for Latin-script responses without over-filtering names.
    tokens = set(_chat_tokens(raw))
    if lang == "uz":
        uz_markers = len(tokens & {"haqida", "uchun", "bilan", "kerak", "mumkin", "qanday", "bu", "ham", "emas", "hisoblanadi", "bo'ladi", "shuningdek"})
        en_markers = len(tokens & {"the", "and", "is", "are", "with", "this", "that", "you", "your", "about", "can", "for", "from", "which"})
        if en_markers >= 4 and uz_markers == 0:
            return True
    if lang == "en":
        uz_markers = len(tokens & {"haqida", "uchun", "bilan", "kerak", "mumkin", "qanday", "shuningdek", "hisoblanadi"})
        en_markers = len(tokens & {"the", "and", "is", "are", "with", "this", "that", "you", "your", "about", "can", "for", "from", "which"})
        if uz_markers >= 2 and en_markers == 0:
            return True
    return False


def _chat_language_system(lang):
    language = CHAT_LANGUAGE_NAMES.get(lang, CHAT_LANGUAGE_NAMES.get("uz"))
    return (
        "You are a reliable multilingual assistant. Answer the user's actual question. "
        f"MANDATORY OUTPUT LANGUAGE: {language}. This was determined from the user's message, "
        "not from the interface language. Write the entire answer only in that language and its normal script. "
        "Do not answer in Arabic unless the user's message is Arabic or the user explicitly requests Arabic. "
        "For a simple greeting, give one short, natural greeting in the same language. "
        "Never fabricate words, repeat phrases, pad the answer, or switch languages mid-answer. "
        "For technical names and brands, preserve their official spelling but explain them in the required language. "
        "Use concise, readable formatting. If the user asks for a detailed answer, give relevant substance rather than filler."
    )


def _chat_failure_message(lang):
    messages = {
        "uz": "Kechirasiz, hozir ishonchli javob tayyorlay olmadim. Savolni boshqacha yoki qisqaroq yozib ko‘ring.",
        "ru": "Извините, сейчас не удалось подготовить надёжный ответ. Попробуйте задать вопрос иначе или короче.",
        "en": "Sorry, I couldn't prepare a reliable answer right now. Please rephrase the question or make it shorter.",
        "tr": "Üzgünüm, şu anda güvenilir bir yanıt hazırlayamadım. Soruyu farklı veya daha kısa biçimde yazmayı deneyin.",
        "de": "Entschuldigung, ich konnte gerade keine verlässliche Antwort erstellen. Formulieren Sie die Frage bitte anders oder kürzer.",
        "fr": "Désolé, je n’ai pas pu préparer une réponse fiable. Reformulez la question ou raccourcissez-la.",
        "ar": "عذرًا، لم أتمكن من إعداد إجابة موثوقة الآن. يرجى إعادة صياغة السؤال أو اختصاره.",
        "es": "Lo siento, no pude preparar una respuesta fiable. Intenta reformular la pregunta o hacerla más breve.",
        "pt": "Desculpe, não consegui preparar uma resposta confiável. Tente reformular a pergunta ou encurtá-la.",
        "it": "Mi dispiace, non sono riuscito a preparare una risposta affidabile. Prova a riformulare o accorciare la domanda.",
        "zh": "抱歉，我暂时无法生成可靠的回答。请尝试换一种方式提问或缩短问题。",
        "hi": "क्षमा करें, मैं अभी विश्वसनीय उत्तर तैयार नहीं कर सका। कृपया प्रश्न को दूसरे तरीके से या थोड़ा छोटा लिखें।",
    }
    return messages.get(lang, messages["uz"])


async def chat_answer(question, user_lang="uz", history=None):
    """Javobni savol tilida qaytaradi va oldingi suhbat kontekstini hisobga oladi.

    Filtrlardan o'tmasa ham eng yaxshi AI javobini ko'rsatadi.
    """
    q = str(question or "").strip()
    if not q:
        return None
    if len(q) > 12000:
        q = q[:12000]

    # Oldingi xabarlar kontekst sifatida beriladi ("davomi", "yana tushuntir").
    dialogue = []
    for item in history or []:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip().lower()
        content = str(item.get("content") or "").strip()
        if role in ("user", "assistant") and content and not content.startswith("⚠️"):
            dialogue.append({"role": role, "content": content[:1500]})
    dialogue = dialogue[-16:]

    def last_turn(role):
        for item in reversed(dialogue):
            if item["role"] == role and item["content"].strip():
                return item["content"].strip()
        return ""

    last_user_text = last_turn("user")
    last_bot_text = last_turn("assistant")

    # Short follow-ups ("davomi", "buni tushuntir", "bu so'zni tarjima qil") only
    # make sense together with the earlier turns. Weak models ignore a bare
    # message list, so the recent conversation is quoted explicitly as well.
    context_note = ""
    if dialogue:
        recent = "\n".join(
            f"{'User' if item['role'] == 'user' else 'Assistant'}: {item['content'][:700]}"
            for item in dialogue[-8:]
        )
        context_note = (
            "\n\nCONVERSATION SO FAR (context only — never repeat it back):\n"
            f"{recent}\n"
            "The current message continues this conversation. If it refers to "
            "something said earlier (\"this\", \"that word\", \"continue\", "
            "\"explain more\"), use the conversation above and answer as a natural "
            "continuation instead of starting a new topic."
        )

    # Directly handle common one-word greetings so a model cannot randomly answer in Arabic.
    compact = re.sub(r"\s+", " ", q.casefold().strip(" .,!?:;\"'`()[]{}"))
    if compact in _CHAT_GREETINGS:
        return _CHAT_GREETINGS[compact][1]

    explicit_lang = _requested_chat_language(q)
    wants_translation = _wants_translation(q)
    if explicit_lang:
        lang = explicit_lang
    else:
        lang = _detect_chat_language(q, fallback=user_lang)
        if wants_translation and lang != user_lang and user_lang in CHAT_LANGUAGE_NAMES:
            # "tarjima qil" without a named language: translate into the interface
            # language instead of echoing the source language back unchanged.
            lang = user_lang
    language = CHAT_LANGUAGE_NAMES.get(lang, CHAT_LANGUAGE_NAMES.get("uz"))
    translation_note = (
        " The user asks for a translation: translate the provided text fully and naturally "
        f"into {language}, keeping names, numbers and formatting intact. Do not summarize or add "
        "commentary unless the user asked for it. If no text to translate is present, ask the "
        "user to send it — never invent text."
        if wants_translation else ""
    )

    # "bu so'zni tarjima qil" (translate this word) has no text of its own: the
    # word is in the previous turn. Pick that text explicitly so even a small
    # model translates the right thing instead of inventing an answer.
    translation_source = ""
    if wants_translation:
        low = q.casefold().replace("’", "'")
        word_ref = any(w in low for w in ("so'z", "soz", "word", "слово", "сўз", "ifoda"))
        quoted = re.search(r"[\"'«“]([^\"'»”]{2,})[\"'»”]", q)
        if quoted:
            translation_source = quoted.group(1).strip()
        elif len(_chat_tokens(q)) <= 8:
            source = last_user_text if word_ref else (last_bot_text or last_user_text)
            if source and len(source) <= 1500:
                translation_source = source

    if translation_source:
        question_prompt = (
            f"TEXT TO TRANSLATE:\n{translation_source}\n\n"
            f"The user's request: {q}\n"
            f"Translate the whole text above into {language} and return only the translation."
        )
    else:
        question_prompt = q

    best_answer = None  # AI qaytargan birinchi yaroqli (bo'sh emas) javob

    # 3 ta urinish: har birida til talabi kuchayadi.
    for attempt in range(3):
        if attempt == 0:
            system = _chat_language_system(lang) + translation_note + context_note
            prompt = question_prompt
            temp = 0.2
        elif attempt == 1:
            system = (
                f"CRITICAL: You MUST write the ENTIRE answer ONLY in {language}. "
                f"The previous answer was in the wrong language and was rejected. "
                f"Now answer exclusively in {language} with its normal script. "
                "Use simple, short, correct sentences. English words are allowed ONLY for "
                "proper names, brand names and scientific formulas — never for the text itself."
                + translation_note + context_note
            )
            prompt = (
                f"User's question (must be answered in {language}): {question_prompt}\n\n"
                f"Answer ONLY in {language}. Do not use English."
            )
            temp = 0.3
        else:
            system = (
                f"FINAL ATTEMPT. Answer the question below ONLY in {language}. "
                "If you cannot answer in that language, give the shortest possible correct "
                f"answer in {language} anyway. Never switch to English."
                + translation_note + context_note
            )
            prompt = question_prompt
            temp = 0.4

        ans = await _chat_complete(
            prompt, system=system, max_tokens=2600, temperature=temp,
            frequency_penalty=0.35, presence_penalty=0.1, history=dialogue
        )
        if not ans or ans.startswith("⚠️"):
            # All providers already failed inside one call; repeating the same
            # expensive failover only leaves the user waiting on "O'ylayapman...".
            if best_answer is None:
                break
            continue
        ans = ans.strip()
        if best_answer is None:
            best_answer = ans

        bad = (_chat_answer_is_repetitive(ans) or _chat_answer_wrong_script(ans, lang)
               or (lang in ALL_LANGS and _is_lang_mixed(ans, lang)))
        if not bad:
            return ans  # toza javob topildi → darhol qaytaramiz

    # Barcha urinishlar filtirdan o'tmadi, lekin AI javob qaytargan bo'lsa —
    # uni ko'rsatamiz (notukkam javob, umuman javob yo'qdan yaxshiroq).
    if best_answer:
        return best_answer

    # FAQAT barcha AI provayderlari ishlamagan holatda failure message.
    return _chat_failure_message(lang)

async def test_api(timeout=7, concurrency=6):
    """Probe every configured provider/model quickly and report each result.

    The old version called the models one after another with the full
    AI_TIMEOUT (120s by default), so one dead provider could block /testapi for
    many minutes and the admin never received a report at all. Probes now run
    concurrently with a short per-request timeout, every model gets its own
    line, and the shared LAST_ERROR of real generation is restored afterwards.
    """
    import asyncio

    global LAST_ERROR
    saved_error = LAST_ERROR

    no_key, jobs = [], []
    for api in API_LIST:
        if not api.get("api_key"):
            no_key.append(api["name"])
            continue
        for model in api.get("models") or []:
            jobs.append((api, model))

    semaphore = asyncio.Semaphore(max(1, int(concurrency)))
    payload = {"messages": [{"role": "user", "content": "OK"}],
               "temperature": 0.1, "max_tokens": 10}

    async def probe(api, model):
        async with semaphore:
            try:
                status, text, err = await asyncio.wait_for(
                    _try_post(api, model, dict(payload)), timeout=timeout)
            except asyncio.TimeoutError:
                return api["name"], model, False, f"{int(timeout)}s ichida javob yo'q"
            except Exception as exc:
                return api["name"], model, False, type(exc).__name__
            if status == 200 and text:
                return api["name"], model, True, ""
            return api["name"], model, False, str(err or (f"HTTP {status}" if status else "javob yo'q"))

    results = await asyncio.gather(*(probe(api, model) for api, model in jobs)) if jobs else []
    LAST_ERROR = saved_error

    by_api = {}
    for name, model, ok, detail in results:
        by_api.setdefault(name, []).append((model, ok, detail))

    if not API_LIST:
        return "AI provayderlar sozlanmagan."

    lines = []
    for api in API_LIST:
        name = api["name"]
        if name in no_key:
            lines.append(f"❌ {name}: API kaliti yo'q")
            continue
        rows = by_api.get(name) or []
        if any(ok for _, ok, _ in rows):
            lines.append(f"✅ {name}: ishlaydi")
        elif rows:
            lines.append(f"❌ {name}: ishlamadi")
        else:
            lines.append(f"⚠️ {name}: model ro'yxati bo'sh")
        for model, ok, detail in rows:
            if ok:
                lines.append(f"   ✅ {model}")
            else:
                lines.append(f"   ❌ {model} — {detail}" if detail else f"   ❌ {model}")
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
    if start != -1:
        # A truncated response still contains complete slide objects; keep them
        # instead of discarding the whole deck and falling back to filler text.
        close = text.rfind("}")
        if close > start:
            try: return json.loads(text[start:close + 1] + "]")
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
