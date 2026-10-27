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
import io
from collections import Counter
from dotenv import load_dotenv
load_dotenv()
from config import AI_API_URL, AI_MODEL, AI_TIMEOUT

LAST_ERROR = "hali sinanmadi"
PIXABAY_KEY  = os.getenv("PIXABAY_KEY", "")
PEXELS_KEY   = os.getenv("PEXELS_KEY", "")
UNSPLASH_KEY = os.getenv("UNSPLASH_KEY", "")
USER_AGENT = "TalabaAISlideBot/1.0 (educational presentation image retrieval)"

_KEYWORD_CACHE = {}
CHARS_PER_PAGE = 1400
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


async def _generate_section(service, topic, sec_title, sec_pages, sec_desc, lang, wiki, prev_summary):
    """Generate a section in the chosen language and reject language leaks/LLM loops."""
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
        chunk_target = chunk_pages * CHARS_PER_PAGE
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

    try:
        requested_pages = int(options.get("pages", 10) or 10)
    except (TypeError, ValueError):
        requested_pages = 10
    pages = requested_pages if requested_pages in (10, 15, 20) else min((10, 15, 20), key=lambda n: abs(n - requested_pages))
    if service == "test":
        # The test service's selected quantity is a question count, not page count.
        return await _generate_test(service, topic, options, lang)

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
    global LAST_ERROR
    ln = _lang_name(lang)
    wiki = await wikipedia_fetch(topic, max_chars=5000, gen_lang=lang)
    wb = wiki_block(wiki, lang)
    
    system = (_pure_language_system(lang) +
              f" You are a professional presentation writer. Write ONLY in {ln}. "
              "Return only a valid JSON array, with no explanation outside the JSON.")

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
        if _is_lang_mixed(all_text, lang) or _document_text_is_repetitive(all_text):
            retry_txt = await _chat_complete(prompt + f"\nFINAL LANGUAGE CHECK: rewrite every title and sentence only in {ln}. Remove any phrases in other languages.", system=system, max_tokens=4500)
            retry_parsed = _extract_json(retry_txt)
            retry_text = " ".join([str(item.get("title", "")) + " " + " ".join(item.get("content", [])) for item in retry_parsed if isinstance(item, dict)]) if isinstance(retry_parsed, list) else ""
            if (retry_parsed and isinstance(retry_parsed, list)
                    and not _is_lang_mixed(retry_text, lang)
                    and not _document_text_is_repetitive(retry_text)):
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
    
    if not parsed and not str(txt or "").strip().startswith("⚠️") and not LAST_ERROR:
        LAST_ERROR = "AI javobi yaroqli JSON/til tekshiruvidan o'tmadi; taqdimot zaxira mazmun bilan tuzildi."

    # Keep count exact without inserting text from another language.
    used_fallback = not bool(all_slides)
    if not all_slides:
        if not LAST_ERROR:
            LAST_ERROR = "AI mazmuni yaroqsiz yoki bo'sh; taqdimot uchun zaxira slaydlar ishlatildi."
        used_fallback = True
        all_slides = _fallback_slides(topic, count, lang)
    else:
        if len(all_slides) < count:
            used_fallback = True
            if not LAST_ERROR:
                LAST_ERROR = f"AI faqat {len(all_slides)} ta slayd qaytardi; qolgan slaydlar zaxiradan to'ldirildi."
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

async def _commons_images(query, count=12):
    """Search Wikimedia Commons without requiring a third-party API key."""
    query = str(query or "").strip()
    if len(query) < 3:
        return []
    api_url = "https://commons.wikimedia.org/w/api.php"
    params = {
        "action": "query", "generator": "search",
        "gsrsearch": query, "gsrnamespace": 6, "gsrlimit": max(5, min(20, int(count))),
        "prop": "imageinfo", "iiprop": "url|mime|size", "iiurlwidth": 1600,
        "format": "json",
    }
    try:
        headers = {"User-Agent": USER_AGENT}
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=12), headers=headers) as session:
            async with session.get(api_url, params=params) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json(content_type=None)
        pages = data.get("query", {}).get("pages", {})
        results = []
        for page in pages.values():
            title = str(page.get("title", ""))
            for info in page.get("imageinfo", [])[:1]:
                mime = str(info.get("mime", ""))
                url = info.get("thumburl") or info.get("url")
                width = int(info.get("thumbwidth", info.get("width", 0)) or 0)
                height = int(info.get("thumbheight", info.get("height", 0)) or 0)
                if not url or not mime.startswith("image/"):
                    continue
                if width and height and (width < 400 or height < 240):
                    continue
                results.append({"url": url, "tags": title.lower(), "src": "commons"})
        return results
    except Exception as exc:
        _log(f"Wikimedia Commons image search failed: {exc}")
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
    results = await asyncio.gather(
        _wiki_image(q), _commons_images(keywords, count=max(8, count * 3)),
        _pixabay_images(keywords), _pexels_images(keywords), _unsplash_images(keywords),
        return_exceptions=True,
    )
    candidates, seen = [], set()
    for group in results:
        if isinstance(group, Exception) or not group:
            continue
        for c in group:
            u = c.get("url")
            if not u or u in seen: continue
            seen.add(u)
            mos = sum(1 for kw in kw_list if kw in c["tags"]) if kw_list else 1
            if c.get("src") == "wikipedia": mos += 10
            elif c.get("src") == "commons": mos += 6
            candidates.append((mos, u))
    candidates.sort(key=lambda x: -x[0])
    urls = [u for mos, u in candidates if mos > 0][:count]
    return urls

async def download_image(url, save_path):
    """Download and validate an image; re-encode it to a safe JPEG for PPTX."""
    try:
        from PIL import Image, ImageOps
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=20),
            headers={"User-Agent": USER_AGENT},
        ) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return False
                content_type = str(resp.headers.get("Content-Type", "")).lower()
                raw = await resp.read()
                if not raw or len(raw) > 20 * 1024 * 1024:
                    return False
                if content_type and not content_type.startswith("image/"):
                    return False
        with Image.open(io.BytesIO(raw)) as source:
            source.load()
            image = ImageOps.exif_transpose(source).convert("RGB")
            if image.width < 240 or image.height < 160:
                return False
            image.save(save_path, format="JPEG", quality=88, optimize=True)
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
                        try: return 200, json.loads(body)["choices"][0]["message"]["content"], None
                        except Exception as e: return resp.status, None, str(e)
                    return resp.status, None, _error_detail(resp.status, body)
    except Exception as e: return None, None, str(e)

async def _chat_complete(prompt, system=None, max_tokens=2500, temperature=0.5,
                         frequency_penalty=0.7, presence_penalty=0.5):
    """Try every configured model across every provider before returning fallback text.

    Previous implementation stopped as soon as the first provider's models ran out,
    so configured backups were never reached. Keep a local ordered attempt list to
    make each request complete its own failover cycle.
    """
    global CURRENT_API_INDEX, CURRENT_MODEL_INDEX, LAST_ERROR
    messages = []
    if system:
        messages.append({"role": "system", "content": str(system)})
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
        models = list(api.get("models", []))
        if not models:
            errors.append(f"{api.get('name', 'API')}: model ro'yxati bo'sh")
            continue
        # On the current provider, start from the last successful model position;
        # for the other providers, try all models in their configured order.
        if api_index == start_api:
            model_start = CURRENT_MODEL_INDEX % len(models)
            models = models[model_start:] + models[:model_start]
        # A 429 can mean "this model's limit is gone" or "this whole key is
        # rate-limited". Give the provider's next model one chance before treating
        # it as key-level and moving on to the next configured provider.
        consecutive_rate_limits = 0
        for model_index, model in enumerate(models):
            attempts += 1
            status, answer, error = await _try_post(api, model, payload)
            if status == 200 and answer and answer.strip():
                CURRENT_API_INDEX = api_index
                try:
                    CURRENT_MODEL_INDEX = api.get("models", []).index(model)
                except ValueError:
                    CURRENT_MODEL_INDEX = 0
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
    "uz": {"salom", "assalomu", "alaykum", "haqida", "nima", "qanday", "qayerda", "qachon", "nega", "uchun", "bilan", "kerak", "mumkin", "men", "siz", "menga", "tushuntir", "yozib", "yozing", "iltimos", "rahmat", "bo'ladi", "emas", "qaysi", "o'zbek", "o‘zbek", "qilib", "qil", "ber", "ayt"},
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
    if re.search(r"[ʻʼ‘’]", raw) or any(w in tokens for w in {"haqida", "qanday", "qayerda", "uchun", "mumkin", "kerak", "salom", "rahmat", "iltimos", "o'zbek"}):
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


async def chat_answer(question, user_lang="uz"):
    q = str(question or "").strip()
    if not q:
        return None
    if len(q) > 12000:
        q = q[:12000]

    # Directly handle common one-word greetings so a model cannot randomly answer in Arabic.
    compact = re.sub(r"\s+", " ", q.casefold().strip(" .,!?:;\"'`()[]{}"))
    if compact in _CHAT_GREETINGS:
        return _CHAT_GREETINGS[compact][1]

    lang = _detect_chat_language(q, fallback=user_lang)
    system = _chat_language_system(lang)
    ans = await _chat_complete(
        q, system=system, max_tokens=2200, temperature=0.2,
        frequency_penalty=0.35, presence_penalty=0.1
    )
    if not ans or ans.startswith("⚠️"):
        return None
    ans = ans.strip()
    bad = (_chat_answer_is_repetitive(ans) or _chat_answer_wrong_script(ans, lang)
           or (lang in ALL_LANGS and _is_lang_mixed(ans, lang)))
    if bad:
        retry_prompt = (
            "Write a fresh answer to the ORIGINAL user question below. Do not reuse the previous draft. "
            "Keep the answer accurate and useful, with no repeated phrases.\n\n"
            f"Original user question:\n{q}"
        )
        ans = await _chat_complete(
            retry_prompt, system=system, max_tokens=2200, temperature=0.15,
            frequency_penalty=0.25, presence_penalty=0.0
        )
        if not ans or ans.startswith("⚠️"):
            return _chat_failure_message(lang)
        ans = ans.strip()
        if (_chat_answer_is_repetitive(ans) or _chat_answer_wrong_script(ans, lang)
                or (lang in ALL_LANGS and _is_lang_mixed(ans, lang))):
            return _chat_failure_message(lang)
    return ans

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
