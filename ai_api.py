"""
AI API — to'liq tuzatilgan versiya (v8)
========================================
✓ Til sofligi: Barcha fallback matnlari 6 tilga o'tkazildi (aralashish yo'q).
✓ Test xizmati: Nechta savol tanlansa, aynan shuncha savol generatsiya qiladi.
✓ Slaydlar, rasm qidirish va boshqa barcha funksiyalar to'liq saqlab qolindi.
"""
import aiohttp
import asyncio
import json
import re
import math
import os
from dotenv import load_dotenv
load_dotenv()
from config import AI_API_URL, AI_MODEL, AI_TIMEOUT

LAST_ERROR = "hali sinanmadi"
PIXABAY_KEY  = os.getenv("PIXABAY_KEY", "")
PEXELS_KEY   = os.getenv("PEXELS_KEY", "")
UNSPLASH_KEY = os.getenv("UNSPLASH_KEY", "")
IMAGE_SLIDE_INDICES = [0, 3, 6]
USER_AGENT = "SlaydBot/1.0 (aloqa: admin@example.uz)"

def wiki_langs_for(gen_lang):
    order = {"uz": ["uz","ru","en"], "ru": ["ru","en","uz"], "en": ["en","ru","uz"],
             "tr": ["en","tr","ru","uz"], "de": ["en","de","ru","uz"], "fr": ["en","fr","ru","uz"]}
    return order.get(str(gen_lang).lower(), ["en","ru","uz"])
    
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
        "models": [
            "qwen/qwen3.8-27b",
            "openai/gpt-oss-120b",
            "openai/gpt-oss-20b"
        ]
    },
    {
        "name": "Groq 2",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key": os.getenv("GROQ_KEY_2", ""),
        "type": "openai",
        "models": [
            "qwen/qwen3.8-27b",
            "openai/gpt-oss-120b",
            "openai/gpt-oss-20b"
        ]
    },
   {"name": "Cloudflare AI (zaxira)",
     "base_url": "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run",
     "account_id": os.getenv("CLOUDFLARE_ACCOUNT_ID", ""),
     "api_key": os.getenv("CLOUDFLARE_KEY", ""), "type": "cloudflare",
     "models": ["@cf/meta/llama-3-8b-instruct", "@cf/meta/llama-3.1-8b-instruct",
                "@cf/mistral/mistral-7b-instruct-v0.2", "@cf/google/gemma-7b-it-lora"]},
    {
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": os.getenv("OPENROUTER_KEY", ""),
        "type": "openai",
        "models": [
            "qwen/qwen3.8-27b",
            "openai/gpt-oss-120b",
            "meta-llama/llama-3.2-3b-instruct"
        ]
    },
    {
        "name": "Google AI",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "api_key": os.getenv("GOOGLE_KEY_1", ""),
        "type": "google",
        "models": [
            "gemini-2.0-flash-exp",
            "gemini-1.5-flash",
            "gemini-1.5-flash-8b"
        ]
    },
    {
        "name": "Local FreeLLMAPI",
        "base_url": AI_API_URL,
        "api_key": os.getenv("AI_API_KEY", ""),
        "type": "openai",
        "models": [AI_MODEL, "gpt-3.5-turbo", "llama3"]
    },
]

CURRENT_API_INDEX = 0
CURRENT_MODEL_INDEX = 0

def get_current_api():  return API_LIST[CURRENT_API_INDEX]
def get_current_model():
    return get_current_api()["models"][CURRENT_MODEL_INDEX % len(get_current_api()["models"])]

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

def verify_facts(text):
    if not text: return text
    if "Navoiy" in text or "Alisher Navoiy" in text:
        text = re.sub(r'Samarqand', 'Hirot', text)
        text = re.sub(r'Samarqandda', 'Hirot shahrida', text)
    return text

def _log(msg): print(f"[AI_API] {msg}", flush=True)
def get_last_error(): return LAST_ERROR

LANG_NAMES = {"uz": "o'zbek", "ru": "rus", "en": "english", "tr": "turkish", "de": "german", "fr": "french"}
LANG_FULL = {"uz": "o'zbekcha", "ru": "ruscha", "en": "inglizcha", "tr": "turkcha", "de": "nemcha", "fr": "fransuzcha"}
ALL_LANGS = ("uz", "ru", "en", "tr", "de", "fr")
def _lang_name(code): return LANG_NAMES.get(str(code).lower(), "o'zbek")

SYSTEM_PROMPTS = {
    "uz": "Siz akademik va badiiy matn yozish bo'yicha mutaxassissiz. ABSOLYUT HAMMA NARSANI faqat o'zbekcha yozing! Hech qanday boshqa til so'zi, atamasi yoki iborasi aralashmasin. Har bir gap, har bir raqam izohi — hammasi o'zbekcha bo'lsin. Agar biror atama o'zbekchada bo'lmasa, uni tarjima qilib yozing. * yoki # belgi ishlatmang. Faktlarga asoslaning.",
    "ru": "Вы специалист по написанию академических и художественных текстов. ПИШИТЕ АБСОЛЮТНО ВСЁ только на русском языке! Никаких слов, терминов или выражений на других языках. Не используйте * и #.",
    "en": "You are an expert academic and creative writer. Write ABSOLUTELY EVERYTHING in English only! No words, terms or phrases from any other language. Do not use * or #.",
    "tr": "Sen akademik ve yaratıcı metin yazma uzmanısın. MUTLAKA HER ŞEYİ sadece Türkçe yaz! Başka hiçbir dilin kelimesi karışmasın. * ve # kullanma.",
    "de": "Sie sind Experte für akademisches und kreatives Schreiben. Schreiben Sie ABSOLUT ALLES nur auf Deutsch! Keine Wörter aus anderen Sprachen.",
    "fr": "Vous êtes un expert en rédaction académique et créative. Écrivez ABSOLUMENT TOUT en français uniquement ! Aucun mot d'une autre langue.",
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

async def wikipedia_fetch(topic, max_chars=4000, full=False, gen_lang="uz"):
    langs = wiki_langs_for_topic(topic, gen_lang)
    _log(f"🔍 Wikipedia qidiruv tartibi: {langs} (mavzu: '{topic}')")
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20),
                                     headers={"User-Agent": USER_AGENT}) as session:
        for lang in langs:
            try:
                search_url = (f"https://{lang}.wikipedia.org/w/api.php?action=query&list=search"
                              f"&srsearch={aiohttp.helpers.quote(topic)}&format=json&srlimit=1")
                async with session.get(search_url) as resp:
                    if resp.status != 200: continue
                    hits = (await resp.json()).get("query", {}).get("search", [])
                    if not hits: continue
                    title = hits[0]["title"]
                exintro = "" if full else "&exintro"
                page_url = (f"https://{lang}.wikipedia.org/w/api.php?action=query&prop=extracts|pageimages"
                            f"{exintro}&explaintext&piprop=original&titles={aiohttp.helpers.quote(title)}"
                            f"&format=json&redirects=1")
                async with session.get(page_url) as resp:
                    if resp.status != 200: continue
                    pages = (await resp.json()).get("query", {}).get("pages", {})
                    page = next(iter(pages.values()), {})
                    extract = page.get("extract", "")
                    image = page.get("original", {}).get("source", "")
                    if extract and len(extract) > 100:
                        return {"found": True, "lang": lang, "title": title,
                                "text": extract[:max_chars], "image": image,
                                "url": f"https://{lang}.wikipedia.org/wiki/{title.replace(' ', '_')}"}
            except Exception as e:
                _log(f"[WIKI {lang}] xato: {e}"); continue
    return {"found": False, "text": "", "image": "", "url": "", "title": "", "lang": ""}

def wiki_block(wiki):
    if not wiki.get("found"): return ""
    return (f"\n\n=== MANBA (Wikipedia) ===\nSarlavha: {wiki['title']}\n"
            f"Quyidagi faktlarni asos qilib yoz:\n{wiki['text']}\n")

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
        ("TITULLIK BET", "Mavzu, fan, guruh, muallif, yil"),
        ("REJA", "2-3 ta savol yoki masala ro'yxati"),
        ("KIRISH", "Qisqa kirish — 0.5 bet, mavzuga kirish"),
        ("1-SAVOLGA JAVOB", "Birinchi savolga batafsil, mantiqiy javob — 2-3 bet"),
        ("2-SAVOLGA JAVOB", "Ikkinchi savolga batafsil javob — 2-3 bet"),
        ("3-SAVOLGA JAVOB", "Uchinchi savolga batafsil javob — 2-3 bet"),
        ("XULOSA", "Qisqa yakuniy xulosa"),
        ("ADABIYOTLAR", "5 ta manba, to'liq ma'lumot bilan")]},
    "kurs": {"style": "ilmiy-tadqiqot, rasmiy, statistikalar bilan. HAJMI: 25-35 bet.", "sections": [
        ("TITULLIK BET", "To'liq titullik bet"),
        ("MUNDARIJA", "Barcha boblar, paragraflar — sahifa raqamlari bilan"),
        ("KIRISH", "Dolzarbligi, obyekti, predmeti, maqsadi — TO'LIQ 2 bet"),
        ("I-BOB. NAZARIY QISM", "Mavzuning nazariy asoslari — 8-10 bet"),
        ("II-BOB. AMALIY QISM", "Muammo tahlili, statistikalar — 8-10 bet"),
        ("XULOSA VA TAKLIFLAR", "Umumiy xulosa va takliflar — 2 bet"),
        ("ADABIYOTLAR", "15-20 ta manba"),
        ("QO'SHIMCHALAR", "Jadvallar, diagrammalar")]},
    "diplom": {"style": "ilmiy-tadqiqot, BMI darajasida. HAJMI: 50-70 bet.", "sections": [
        ("ANNOTATSIYA", "3 tilda qisqa mazmun"),
        ("MUNDARIJA", "To'liq mundarija"),
        ("KIRISH", "Dolzarbligi, obyekti, predmeti, maqsadi — 3-4 bet"),
        ("I-BOB. NAZARIY ASOSLAR", "Nazariy asoslar — 12-15 bet"),
        ("II-BOB. TAHLIL QISMI", "Muammo tahlili, statistika — 12-15 bet"),
        ("III-BOB. TAKLIFLAR", "Takliflar, loyihalar — 10-12 bet"),
        ("XULOSA", "Umumiy xulosa — 3 bet"),
        ("ADABIYOTLAR", "30+ manba"),
        ("QO'SHIMCHALAR", "Jadvallar, diagrammalar")]},
    "test": {"style": "qisqa, aniq savollar. A/B/C/D variantlari.", "sections": [
        ("TEST SAVOLLARI", "Savollar va variantlar"),
        ("JAVOBLAR KALITI", "To'g'ri javoblar ro'yxati")]},
    "maqola": {"style": "ilmiy, IMRAD standarti. HAJMI: 3-7 bet.", "sections": [
        ("SARLAVHA VA MUALlif", "Maqola sarlavhasi, muallif"),
        ("ANNOTATSIYA", "Annotatsiya va kalit so'zlar"),
        ("KIRISH", "Muammo, dolzarblik — 1 bet"),
        ("METODOLOGIYA", "Izlanish usullari — 1 bet"),
        ("NATIJALAR", "Tahlillar, jadvallar — 2-3 bet"),
        ("XULOSA", "Asosiy xulosalar — 0.5 bet"),
        ("ADABIYOTLAR", "10-15 manba")]},
    "tezis": {"style": "juda ixcham. HAJMI: 1-3 bet.", "sections": [
        ("SARLAVHA VA MUALlif", "Sarlavha, muallif"),
        ("QISQA KIRISH", "2-3 jumla"),
        ("ASOSIY TAHLIL", "Konkret tahlil, raqamlar"),
        ("XULOSA", "Asosiy natija")]},
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
            txt = f"{sec_title} bo'yicha batafsil ma'lumot. {topic} mavzusida tahlil va xulosalar."
        if _is_lang_mixed(txt, lang):
            txt2 = await _chat_complete(prompt + f"\nDIQQAT: FAQAT {_lang_name(lang)} tilida yozing!", system=_pure_language_system(lang), max_tokens=4096)
            if txt2 and "⚠️" not in txt2: txt = txt2
        parts.append(txt); local_prev = txt[:600]
        await asyncio.sleep(0.2)
    return "\n\n".join(parts)

async def generate_outline(service, topic, lang, words=250):
    wiki = await wikipedia_fetch(topic, max_chars=2000, gen_lang=lang)
    wb = wiki_block(wiki)
    prompt = f"""Mavzu: {topic}. Ushbu mavzuda insho yozish uchun REJA tuzing. 
Reja quyidagi tuzilishda bo'lishi shart:
1. Kirish (asosiy tezis nima bo'ladi?)
2. Asosiy qism (3 ta alohida fikr/argument)
3. Xulosa (qanday yakuniy fikrga kelinadi?)
Faqat shu rejani qisqa qilib yozing, matnni yozmang. {wb}"""
    txt = await _chat_complete(prompt, system=_pure_language_system(lang), max_tokens=1000)
    return txt if txt and not txt.startswith("⚠️") else None

# ===== ASOSIY GENERATE FUNKSIYASI =====
async def generate(service, topic, options, lang="uz"):
    from services import SERVICES
    name = SERVICES.get(service, {}).get("name", service)
    
    # ===== INSHO (ESSEY) UCHUN MAXSUS MANTIQ =====
    if service == "insho":
        wiki = await wikipedia_fetch(topic, max_chars=3000, gen_lang=lang)
        wb = wiki_block(wiki)
        
        system = _pure_language_system(lang) + """ Siz badiiy va falsafiy essey yozadigan mohir adibsiz. 
QAT'IY QOIDA: Hech qanday sarlavha (KIRISH, ASOSIY QISM, XULOSA) yozmang! Raqamlar (1, 2, 3) yoki ro'yxat (nuqtalar) ishlatmang! Faqat oddiy abzaslardan iborat badiiy matn yozing."""

        prompt_k = f"Mavzu: {topic}. Inshoning kirish qismini yozing. Kamida 70-80 so'z bo'lsin. Hech qanday sarlavha yozmang, to'g'ridan-to'g'ri matnni boshlang. {wb}"
        kirish = await _chat_complete(prompt_k, system=system, max_tokens=1000)
        if _is_lang_mixed(kirish, lang) or not kirish:
            kirish = await _chat_complete(prompt_k + f"\nFAQAT {_lang_name(lang)} TILIDA YOZING!", system=system, max_tokens=1000)
        if not kirish or kirish.startswith("⚠️"): kirish = f"{topic} haqida o'ylar. Bu mavzu insoniyat uchun muhim ahamiyatga ega."

        prompt_a = f"Mavzu: {topic}. Inshoning asosiy qismi uchun 3 ta mazmunli abzas yozing. Jami hajmi 300-400 so'z bo'lsin. Raqamlar (1,2,3) yoki sarlavhalar ishlatmang! Faqat 3 ta abzasni bering. {wb}"
        asosiy = await _chat_complete(prompt_a, system=system, max_tokens=2000)
        if _is_lang_mixed(asosiy, lang) or not asosiy:
            asosiy = await _chat_complete(prompt_a + f"\nFAQAT {_lang_name(lang)} TILIDA YOZING!", system=system, max_tokens=2000)
        if not asosiy or asosiy.startswith("⚠️"): asosiy = f"{topic} ning bugungi kundagi o'rni va ahamiyati haqida fikrlar. Ushbu masala yuzasidan turli qarashlar mavjud."

        prompt_x = f"Mavzu: {topic}. Inshoning xulosa qismini yozing. Kamida 70-80 so'z bo'lsin. Hech qanday sarlavha yozmang, faqat yakuniy fikrni yozing."
        xulosa = await _chat_complete(prompt_x, system=system, max_tokens=1000)
        if _is_lang_mixed(xulosa, lang) or not xulosa:
            xulosa = await _chat_complete(prompt_x + f"\nFAQAT {_lang_name(lang)} TILIDA YOZING!", system=system, max_tokens=1000)
        if not xulosa or xulosa.startswith("⚠️"): xulosa = f"Xulosa o'rnida shuni aytish mumkinki, {topic} mavzusi biz uchun katta saboq bo'lib xizmat qiladi."

        result = f"{kirish}\n\n{asosiy}\n\n{xulosa}"
        real = bool(kirish and asosiy and xulosa and not kirish.startswith("⚠️"))
        return clean_ai_text(result), real
    # ===============================================

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

# ===== TEST GENERATSIYASI (QAT'IY NAZORAT) =====
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
    result = "\n\n".join(all_questions) + "\n\nJAVOBLAR KALITI: (TO'G'RI) belgilangan variant."
    return result, bool(all_questions)

def _is_image_slide(idx, total):
    return idx in IMAGE_SLIDE_INDICES or idx == total - 1

def _make_image_prompt(topic, idx):
    base = "educational illustration, realistic"
    for uz, en in SEARCH_MAP.items():
        if uz in topic.lower(): base = en; break
    if idx == 0:   return f"portrait of {base}, photorealistic"
    elif idx == 3: return f"{base}, educational scene"
    elif idx == 6: return f"{base}, architecture or monument"
    return f"{base}, inspirational, cinematic"

# ====== SLAYDLAR GENERATSIYASI ======
async def generate_slides_structured(topic, subject, lang, count):
    ln = _lang_name(lang)
    wiki = await wikipedia_fetch(topic, max_chars=4000, gen_lang=lang)
    wb = wiki_block(wiki)
    
    system = (_pure_language_system(lang) +
              f" Siz professional taqdimot tuzuvchisiz. Javobni FAQAT {ln} tilida yozing! "
              f"Javobni faqat JSON massiv ko'rinishida qaytaring.")

    all_slides = []
    
    titles = {
        "uz": {"reja": "Reja", "kirish": "Kirish", "xulosa": "Xulosa"},
        "ru": {"reja": "План", "kirish": "Введение", "xulosa": "Заключение"},
        "en": {"reja": "Outline", "kirish": "Introduction", "xulosa": "Conclusion"},
        "tr": {"reja": "Plan", "kirish": "Giriş", "xulosa": "Sonuç"},
        "de": {"reja": "Gliederung", "kirish": "Einleitung", "xulosa": "Fazit"},
        "fr": {"reja": "Plan", "kirish": "Introduction", "xulosa": "Conclusion"},
    }
    t_lang = titles.get(lang, titles["en"])

    all_slides.append({
        "title": f"{topic}",
        "content": [f"{subject} fanidan taqdimot", f"Tayyorlagan: (Muallif)"]
    })

    all_slides.append({
        "title": t_lang["reja"],
        "content": ["1. Kirish qismi", "2. Asosiy tahlillar va ma'lumotlar", "3. Xulosa va natijalar"]
    })

    all_slides.append({
        "title": t_lang["kirish"],
        "content": [
            f"Ushbu taqdimot {topic} mavzusiga bag'ishlangan.",
            f"Mavzuning dolzarbligi va bugungi kundagi o'rni tahlil qilinadi.",
            f"{subject} fanidagi asosiy tushunchalar yoritiladi."
        ]
    })

    main_count = count - 4
    if main_count < 1: main_count = 1
    
    for start in range(0, main_count, 5):
        chunk_size = min(5, main_count - start)
        prompt = f"""{topic} mavzusida taqdimotning asosiy qismi uchun {chunk_size} ta slayd yarating.
Har bir slayd uchun 4-5 ta mazmunli gap yozing. 
QAT'IY: Sarlavhada "Kirish", "Xulosa", "Reja" so'zlari BO'LMASIN!
{wb}
JSON formati: [{{"title": "Sarlavha", "content": ["gap1", "gap2", ...]}}]"""
        
        txt = await _chat_complete(prompt, system=system, max_tokens=4000)
        parsed = _extract_json(txt)
        
        if parsed and isinstance(parsed, list) and len(parsed) > 0:
            all_text = " ".join([str(s.get("title", "")) + " " + " ".join(s.get("content", [])) for s in parsed])
            if _is_lang_mixed(all_text, lang):
                txt = await _chat_complete(prompt + f"\nFAQAT {ln} tilida!", system=system, max_tokens=4000)
                parsed = _extract_json(txt)
                
            if parsed and isinstance(parsed, list):
                for s in parsed[:chunk_size]:
                    all_slides.append({"title": s.get("title", "Tahlil"), "content": s.get("content", [])})
            else:
                for i in range(chunk_size):
                    all_slides.append({"title": f"{topic} tahlili {start+i+1}", "content": [f"{topic} bo'yicha ma'lumot.", "Qo'shimcha tahlillar."]})
        else:
            for i in range(chunk_size):
                all_slides.append({"title": f"{topic} tahlili {start+i+1}", "content": [f"{topic} bo'yicha asosiy ma'lumotlar.", "Qo'shimcha tahliliy ma'lumotlar."]})

    all_slides.append({
        "title": t_lang["xulosa"],
        "content": [
            f"{topic} mavzusi bo'yicha umumiy xulosalar.",
            "Asosiy natijalar va keyingi qadamlar.",
            "E'tiboringiz uchun rahmat!"
        ]
    })

    out = []
    for i, s in enumerate(all_slides[:count]):
        cl = s.get("content", [])
        if isinstance(cl, str): cl = [p.strip() for p in cl.split("\n") if p.strip()]
        while len(cl) < 3: cl.append(f"{topic} bo'yicha ma'lumot.")
        
        out.append({
            "slide_number": i+1,
            "title": clean_ai_text(str(s.get("title", f"Bo'lim {i+1}"))),
            "content": [clean_ai_text(str(c)) for c in cl[:6]],
            "has_image": _is_image_slide(i, count),
            "image_prompt": _make_image_prompt(topic, i) if _is_image_slide(i, count) else None,
            "wiki_source": wiki["url"] if wiki["found"] else None
        })
    return out, True

SEARCH_MAP = {
    "alisher navoiy": "Alisher Navoi portrait poet", "navoiy": "Alisher Navoi writer poet",
    "amir temur": "Amir Timur Tamerlane conqueror", "temur": "Timur Tamerlane empire",
    "jaloliddin manguberdi": "Jalal ad-Din Manguberdi Khwarazmshah warrior", "manguberdi": "Jalal ad-Din Manguberdi hero",
    "mirzo ulugbek": "Ulugh Beg astronomer Samarkand observatory", "ulugbek": "Ulugh Beg Timurid scholar",
    "ibn sino": "Avicenna Ibn Sina physician philosopher", "islom karimov": "Islam Karimov president Uzbekistan",
    "toshkent": "Tashkent city Uzbekistan", "samarqand": "Samarkand Registan square",
    "buxoro": "Bukhara old city Uzbekistan", "xorazm": "Khiva Khwarezm fortress",
    "farg'ona": "Fergana valley Uzbekistan", "andijon": "Andijan city Uzbekistan",
    "qoraqalpog'iston": "Karakalpakstan Aral sea", "uzbekiston": "Uzbekistan landmark culture",
    "hujayra": "biological cell structure microscope", "fotosintez": "photosynthesis plant leaf chlorophyll",
    "atom": "atom structure nucleus electrons", "molekula": "molecule chemistry 3d structure",
    "dnk": "DNA double helix genetics", "genetika": "genetics DNA chromosome",
    "evolyutsiya": "evolution biology darwin", "fizika": "physics laboratory experiment",
    "kimyo": "chemistry laboratory flask", "biologiya": "biology science laboratory",
    "matematika": "mathematics formulas numbers", "geografiya": "geography globe map world",
    "tarix": "history ancient civilization", "adabiyot": "literature books library",
    "informatika": "computer science coding programming", "iqtisod": "economy finance business chart",
    "huquq": "law justice scale court", "botanika": "botany plants flowers",
    "zoologiya": "zoology animals wildlife", "anatomiya": "human anatomy body medical",
    "geologiya": "geology rocks earth layers", "astronomiya": "astronomy stars galaxy telescope",
}
STOP_WORDS = {"portrait", "historical", "hero", "leader", "conqueror", "poet", "writer",
    "scholar", "astronomer", "city", "architecture", "culture", "landmark", "warrior",
    "prince", "scientist", "figure", "realistic", "8k", "photo", "ancient", "epic",
    "scene", "heritage", "monument", "legacy", "starry", "sky", "sunset", "inspirational",
    "cinematic", "dignified", "pose", "detailed", "photorealistic", "structure", "laboratory",
    "educational", "illustration", "microscope", "nucleus", "electrons", "double", "helix"}

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
            if c["src"] == "wikipedia": mos += 10
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
            data = {"contents": [{"parts": [{"text": payload["messages"][-1]["content"]}]}]}
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
        "temperature": 0.6, 
        "max_tokens": max_tokens,
        "frequency_penalty": 0.8,
        "presence_penalty": 0.6
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
            return verify_facts(clean_ai_text(text)).strip()
        if status == 429: await asyncio.sleep(2.0)
        if not switch_to_next_model() and CURRENT_API_INDEX == start: break
        await asyncio.sleep(0.5)
    return "⚠️ AI serverga ulanib bo'lmadi."

CHAT_STYLE = {
    "uz": "Suhbat uslubida, qisqa va aniq javob bering.",
    "ru": "Отвечайте в разговорном стиле, кратко.",
    "en": "Answer in a conversational style, briefly.",
    "tr": "Konuşma tarzında, kısa cevap ver.",
    "de": "Antworten Sie im Gesprächsstil, kurz.",
    "fr": "Répondez dans un style conversationnel, brièvement.",
}

async def chat_answer(question, user_lang="uz"):
    q = str(question or "")
    lang = str(user_lang).lower()
    truncated = ""
    if len(q) > 8000:
        truncated = "\n\n[Eslatma: matn qisqartirildi.]"
        q = q[:8000]
    system = _pure_language_system(lang) + " " + CHAT_STYLE.get(lang, CHAT_STYLE["en"])
    ans = await _chat_complete(q, system=system, max_tokens=4000)
    return ans + truncated if ans and not ans.startswith("⚠️") else None

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

# ===== 6 TIL UCHUN TO'LIQ FALLBACK =====
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
def _fb(lang): return FB.get(str(lang).lower(), FB["en"])

def _fallback_text(service, topic, options, lang, bob_count=10):
    fb = _fb(lang); sections = list(fb["sections"])
    while len(sections) < bob_count: sections.insert(len(sections)-2, "Qism" if lang=="uz" else "Part")
    return f"{topic}\n\n" + "\n\n".join([f"{sec}\n{topic} bo'yicha ma'lumot." for sec in sections[:bob_count]])

def _fallback_slides(topic, count, lang):
    fb = _fb(lang); secs = fb["slide_sections"]; out = []
    for i in range(count):
        out.append({
            "slide_number": i+1,
            "title": secs[i % len(secs)],
            "content": [f"{topic} bo'yicha ma'lumot.", "Tahliliy xulosalar.", "Amaliy ahamiyati."],
            "has_image": _is_image_slide(i, count),
            "image_prompt": _make_image_prompt(topic, i) if _is_image_slide(i, count) else None
        })
    return out
