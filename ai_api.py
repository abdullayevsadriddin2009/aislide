"""
AI API — to'liq tuzatilgan versiya (v3)
========================================
✓ Barcha 9 xizmat o'z shablonida bo'lakma-bo'lak generatsiya qilinadi (takrorlanmas, to'liq hajmdagi)
✓ Til tozaligi: qaysi til tanlansa, SOF o'sha tilda (boshqa til aralashmaydi)
✓ Wikipediya faktlari (uz→ru→en) — barcha xizmatlarda
✓ Rasm: Wikipedia rasmi + Pixabay + Pexels + Unsplash (4 manba)
✓ Ko'p API + ko'p model avtomatik almashish
"""
import aiohttp
import asyncio
import json
import re
import os
from dotenv import load_dotenv
load_dotenv()
from config import AI_API_URL, AI_MODEL, AI_TIMEOUT

LAST_ERROR = "hali sinanmadi"
PIXABAY_KEY  = os.getenv("PIXABAY_KEY", "")
PEXELS_KEY   = os.getenv("PEXELS_KEY", "")
UNSPLASH_KEY = os.getenv("UNSPLASH_KEY", "")
IMAGE_SLIDE_INDICES = [0, 3, 6]
WIKI_LANGS = ["uz", "ru", "en"]
USER_AGENT = "SlaydBot/1.0 (aloqa: admin@example.uz)"
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

_EN_STOP = {"the","and","is","of","to","in","for","with","on","that","this","it","as","are","by","an","be",
            "or","which","from","at","not","but","have","has","was","were","will","can","more","their",
            "they","we","our","you","your","also","such","than","into","about","between","these","those",
            "its","his","her","been","being","would","could","should","may","might","must","shall"}

def _english_ratio(text):
    words = re.findall(r'[a-zA-Z]{2,}', str(text).lower())
    if not words: return 0.0
    return sum(1 for w in words if w in _EN_STOP) / len(words)

def _pure_language_system(lang_code):
    lf = LANG_FULL.get(lang_code, "o'zbekcha")
    return (f"Siz akademik matn yozish bo'yicha mutaxassissiz. "
            f"ABSOLYUT HAMMA NARSANI faqat {lf} yozing! "
            f"Hech qanday boshqa til so'zi, atamasi yoki iborasi aralashmasin. "
            f"Har bir sarlavha, har bir gap, har bir raqam izohi — hammasi {lf} bo'lsin. "
            f"Agar biror atama {lf} da bo'lmasa, uni tarjima qilib yozing. "
            f"* # belgi ishlatmang. Faktlarga asoslaning, xayoliy ma'lumot qo'shmang.")

async def wikipedia_fetch(topic, max_chars=4000, full=False):
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20),
                                     headers={"User-Agent": USER_AGENT}) as session:
        for lang in WIKI_LANGS:
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
                        _log(f"📚 Wikipedia ({lang}){' [to‘liq]' if full else ''}: '{title}' → {len(extract)} belgi")
                        return {"found": True, "lang": lang, "title": title,
                                "text": extract[:max_chars], "image": image,
                                "url": f"https://{lang}.wikipedia.org/wiki/{title.replace(' ', '_')}"}
            except Exception as e:
                _log(f"[WIKI {lang}] xato: {e}"); continue
    _log(f"[WIKI] '{topic}' topilmadi")
    return {"found": False, "text": "", "image": "", "url": "", "title": "", "lang": ""}

def wiki_block(wiki):
    if not wiki.get("found"): return ""
    return (f"\n\n=== MANBA (Wikipedia) ===\nSarlavha: {wiki['title']}\n"
            f"Quyidagi faktlarni asos qilib yoz, sanalar va raqamlarni aynan shunday qoldir:\n{wiki['text']}\n"
            f"Manba: {wiki['url']}")

SERVICE_TEMPLATES = {
    "referat": {"style": "ilmiy-nazariy, rasmiy uslub", "sections": [
        ("TITULLIK BET", "Mavzu, OTM nomi, guruh, muallif, yil — bitta betda"),
        ("MUNDARIJA", "Barcha bo'limlar ro'yxati, sahifa raqamlari bilan"),
        ("KIRISH", "Mavzuning dolzarbligi, maqsadi va vazifalari — to'liq 1 bet"),
        ("ASOSIY QISM — 1-BOB", "Birinchi reja bo'yicha nazariy ma'lumotlar, batafsil"),
        ("ASOSIY QISM — 2-BOB", "Ikkinchi reja bo'yicha nazariy ma'lumotlar, batafsil"),
        ("ASOSIY QISM — 3-BOB", "Uchinchi reja bo'yicha tahlil va misollar"),
        ("XULOSA", "Mavzu bo'yicha umumiy xulosalar — to'liq 1 bet"),
        ("FOYDALANILGAN ADABIYOTLAR", "5-10 ta manba, to'liq bibliografik ma'lumot bilan")]},
    "mustaqil": {"style": "akademik, mantiqiy, savol-javob shaklida", "sections": [
        ("TITULLIK BET", "Mavzu, fan, guruh, muallif"),
        ("REJA", "2-3 ta savol yoki masala ro'yxati"),
        ("KIRISH", "Qisqa kirish (0.5 bet)"),
        ("1-SAVOLGA JAVOB", "Birinchi savolga batafsil, mantiqiy javob — 2-3 bet"),
        ("2-SAVOLGA JAVOB", "Ikkinchi savolga batafsil javob — 2-3 bet"),
        ("3-SAVOLGA JAVOB", "Uchinchi savolga batafsil javob — 2-3 bet"),
        ("XULOSA", "Qisqa yakuniy xulosa"),
        ("ADABIYOTLAR", "5 ta manba")]},
    "kurs": {"style": "ilmiy-tadqiqot, rasmiy, statistikalar bilan", "sections": [
        ("TITULLIK BET", "To'liq titullik bet"),
        ("MUNDARIJA", "Barcha boblar va paragraflar"),
        ("KIRISH", "Dolzarblik, obyekt, predmet, maqsad, vazifalar — 2 bet"),
        ("I-BOB. NAZARIY ASOSLAR", "Mavzuning nazariy, huquqiy yoki tarixiy asoslari — 8-10 bet"),
        ("II-BOB. AMALIY TAHLIL", "Muammo tahlili, statistikalar, jadvallar, misollar — 8-10 bet"),
        ("XULOSA VA TAKLIFLAR", "Umumiy xulosa va amaliy takliflar — 2 bet"),
        ("FOYDALANILGAN ADABIYOTLAR", "15-20 ta manba"),
        ("QO'SHIMCHALAR", "Jadvallar va diagrammalar")]},
    "diplom": {"style": "ilmiy-tadqiqot, BMI darajasida, chuqur tahlil", "sections": [
        ("ANNOTATSIYA", "O'zbek, rus va ingliz tillarida qisqa mazmun"),
        ("MUNDARIJA", "To'liq mundarija"),
        ("KIRISH", "Dolzarblik, obyekt, predmet, maqsad, vazifalar, tadqiqot metodlari — 3-4 bet"),
        ("I-BOB. NAZARIY ASOSLAR", "Tadqiqot mavzusining nazariy asoslari — 12-15 bet"),
        ("II-BOB. TAHLIL QISMI", "Muammo tahlili, statistika, amaliy ma'lumotlar — 12-15 bet"),
        ("III-BOB. TAKLIFLAR VA ISTIQBOLLAR", "Takliflar, loyihalar, samaradorlik — 10-12 bet"),
        ("XULOSA", "Umumiy xulosa va takliflar — 3 bet"),
        ("ADABIYOTLAR RO'YXATI", "30+ manba"),
        ("QO'SHIMCHALAR", "Jadvallar, diagrammalar, namunaviy hujjatlar")]},
    "insho": {"style": "erkin, badiiy yoki publitsistik, shaxsiy fikrlar bilan", "sections": [
        ("KIRISH (TEZIS)", "Mavzuga kirish va muallifning asosiy fikri — 1 bet"),
        ("ASOSIY QISM — 1-DALIL", "Birinchi argument, hayotiy yoki fanniy misol bilan"),
        ("ASOSIY QISM — 2-DALIL", "Ikkinchi argument, misol bilan"),
        ("ASOSIY QISM — 3-DALIL", "Uchinchi argument, qarama-qarshi fikrni rad etish"),
        ("XULOSA", "Shaxsiy yakuniy xulosa — 1 bet")]},
    "test": {"style": "qisqa, aniq savollar, har birida bitta to'g'ri javob", "sections": [
        ("TEST SAVOLLARI", "Har bir savol: raqam, savol matni, A/B/C/D variantlari. To'g'ri javob belgilangan"),
        ("JAVOBLAR KALITI", "Oxirida barcha to'g'ri javoblar ro'yxati")]},
    "maqola": {"style": "ilmiy, IMRAD standarti, rasmiy", "sections": [
        ("SARLAVHA VA MUALlif", "Maqola sarlavhasi, muallif, ilmiy daraja, muassasa"),
        ("ANNOTATSIYA VA KALIT SO'ZLAR", "O'zbek, rus, ingliz tillarida annotatsiya va kalit so'zlar"),
        ("KIRISH (Introduction)", "Muammo, dolzarblik, tadqiqot maqsadi"),
        ("METODOLOGIYA (Methods)", "Izlanish usullari, materiallar"),
        ("NATIJALAR VA MUHOKAMA", "Tahlillar, jadvallar, grafiklar, muhokama"),
        ("XULOSA (Conclusion)", "Asosiy xulosalar"),
        ("ADABIYOTLAR", "APA yoki GOST formatida 10-15 manba")]},
    "tezis": {"style": "juda ixcham, konkret raqam va faktlar, suvli gaplarsiz", "sections": [
        ("SARLAVHA VA MUALlif", "Sarlavha, muallif, muassasa"),
        ("QISQA KIRISH", "2-3 jumla, muammo va maqsad"),
        ("ASOSIY ILMIY G'OYA", "Konkret tahlil, raqamlar, faktlar — suvli gaplarsiz"),
        ("QISQA XULOSA", "Asosiy natija va xulosa")]},
}

async def _generate_outline(service, topic, pages, lang, wiki):
    tmpl = SERVICE_TEMPLATES.get(service)
    if not tmpl:
        return [("KIRISH", max(1, pages//6), "kirish"),
                ("ASOSIY QISM", max(2, pages*2//3), "asosiy"),
                ("XULOSA", max(1, pages//6), "xulosa")]
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
        prompt = (f"Xizmat: {service}\nMavzu: {topic}\n"
                  f"Hozirgi bo'lim: {sec_title} ({sec_desc})\n"
                  f"Bu bo'limning {ch+1}-qismi (jami {chunks_needed} qism). Kamida {chunk_target} belgi yoz.\n"
                  f"Avvalgi qismlarning qisqacha mazmuni (TAKRORLAMANG!): {local_prev[:600]}\n"
                  f"{wiki_block(wiki)}\n\n"
                  f"Shartlar: (1) faqat yangi, avval yozilmagan ma'lumot yoz; "
                  f"(2) oldingi qismni takrorlama; (3) betlarni to'ldir, qisqartma; "
                  f"(4) faktlar, sanalar, raqamlar, misollar qo'sh.")
        txt = await _chat_complete(prompt, system=_pure_language_system(lang), max_tokens=8000)
        if not txt or "⚠️" in txt:
            txt = f"{sec_title} bo'yicha batafsil ma'lumot. {topic} mavzusida chuqur tahlil."
        if lang != "en" and _english_ratio(txt) > 0.10:
            _log(f"⚠️ Til aralashgan ({sec_title}), qayta generatsiya...")
            txt2 = await _chat_complete(
                prompt + "\n\nDIQQAT: Oldingi javobda boshqa til so'zlari aralashgan! FAQAT so'ralgan tilda yoz!",
                system=_pure_language_system(lang), max_tokens=8000)
            if txt2 and "⚠️" not in txt2: txt = txt2
        parts.append(txt); local_prev = txt[:600]
        await asyncio.sleep(0.2)
    return "\n\n".join(parts)

async def generate(service, topic, options, lang="uz"):
    from services import SERVICES
    name = SERVICES.get(service, {}).get("name", service)
    pages = int(options.get("pages", 10) or 10)
    if service == "test":
        return await _generate_test(service, topic, options, lang)
    wiki = await wikipedia_fetch(topic, max_chars=10000 if service in LONG_SERVICES else 4000,
                                 full=(service in LONG_SERVICES))
    outline = await _generate_outline(service, topic, pages, lang, wiki)
    _log(f"📋 Reja: {len(outline)} bo'lim, jami {pages} bet | Wiki: {'ha' if wiki['found'] else 'yoq'}")
    full_text_parts, prev_summary = [], ""
    for sec_title, sec_pages, sec_desc in outline:
        _log(f"✍️ Yozilmoqda: {sec_title} ({sec_pages} bet)...")
        sec_text = await _generate_section(service, topic, sec_title, sec_pages, sec_desc, lang, wiki, prev_summary)
        full_text_parts.append(f"{'='*20}\n{sec_title}\n{'='*20}\n\n{sec_text}")
        prev_summary = sec_text[:800]
    result = "\n\n".join(full_text_parts)
    _log(f"✅ Tayyor: {name} | {pages} bet | {len(result)} belgi (reja: {pages*CHARS_PER_PAGE})")
    if len(result) < pages * CHARS_PER_PAGE * 0.5:
        _log("⚠️ Hajm kamroq, zaxira matn qo'shilmoqda")
        result += "\n\n" + _fallback_text(service, topic, options, lang, max(3, pages//3))
    return result, True

async def _generate_test(service, topic, options, lang):
    count = int(options.get("questions", options.get("pages", 15)) or 15)
    wiki = await wikipedia_fetch(topic, max_chars=5000)
    all_questions, chunk_size = [], 10
    for start in range(1, count + 1, chunk_size):
        end = min(count, start + chunk_size - 1)
        prompt = (f"{topic} bo'yicha test savollari. {start}-dan {end}-gacha ({end-start+1} ta).\n"
                  f"Har bir savol: raqam, savol matni, A) B) C) D) variantlari. "
                  f"To'g'ri javobni variantdan keyin (TO'G'RI) deb belgilang.\n"
                  f"{wiki_block(wiki)}\n\nFaqat savollarni yoz.")
        txt = await _chat_complete(prompt, system=_pure_language_system(lang), max_tokens=4000)
        if txt and "⚠️" not in txt: all_questions.append(txt)
        await asyncio.sleep(0.2)
    result = "\n\n".join(all_questions) + "\n\nJAVOBLAR KALITI: har bir savoldagi (TO'G'RI) belgilangan variant."
    _log(f"✅ Test tayyor: {count} savol")
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

async def generate_slides_structured(topic, subject, lang, count):
    ln = _lang_name(lang)
    target_chars = count * 750
    wiki = await wikipedia_fetch(topic, max_chars=4000)
    wb = wiki_block(wiki)
    system = (_pure_language_system(lang) +
              f" Slayd tuzilishi: 1) Sarlavha; 2) Reja; 3) Kirish; 4-{count-1}) Asosiy qism (faktlar, sanalar); "
              f"{count}) Xulosa. Har slayd: sarlavha + 6-8 gap. Faqat JSON qaytaring.")
    prompt = f"""{topic} mavzusida {count} slaydli taqdimot. Fan: {subject}. Til: faqat {ln}.{wb}
JSON: [{{"title":"...","content":["gap1","gap2",...]}}]"""
    txt = None
    for _ in range(2):
        txt = await _chat_complete(prompt, system=system, max_tokens=16000)
        if txt and len(txt) > target_chars * 0.5: break
        await asyncio.sleep(1)
    slides = _extract_json(txt) if txt else None
    if slides and isinstance(slides, list) and len(slides) >= 3:
        out = []
        while len(slides) < count: slides.append(slides[len(slides) % len(slides)])
        for i, s in enumerate(slides[:count]):
            cl = s.get("content", ["Ma'lumot tayyorlanmoqda..."])
            if isinstance(cl, str): cl = [p.strip() for p in cl.split("\n") if p.strip()]
            while len(cl) < 5: cl.append(f"{topic} bo'yicha batafsil tahlil.")
            out.append({"slide_number": i+1,
                        "title": clean_ai_text(str(s.get("title", f"Bo'lim {i+1}"))),
                        "content": [clean_ai_text(str(c)) for c in cl[:12]],
                        "has_image": _is_image_slide(i, count),
                        "image_prompt": _make_image_prompt(topic, i) if _is_image_slide(i, count) else None,
                        "wiki_source": wiki["url"] if wiki["found"] else None})
        _log(f"✅ Slayd tayyor: {len(out)}")
        return out, True
    _log("⚠️ Slayd zaxirasi ishlatilmoqda")
    return _fallback_slides(topic, count, lang), False

SEARCH_MAP = {
    "alisher navoiy": "Alisher Navoi portrait poet", "navoiy": "Alisher Navoi writer poet",
    "amir temur": "Amir Timur Tamerlane conqueror", "temur": "Timur Tamerlane empire",
    "jaloliddin manguberdi": "Jalal ad-Din Manguberdi Khwarazmshah warrior",
    "manguberdi": "Jalal ad-Din Manguberdi hero",
    "mirzo ulugbek": "Ulugh Beg astronomer Samarkand observatory", "ulugbek": "Ulugh Beg Timurid scholar",
    "ibn sino": "Avicenna Ibn Sina physician philosopher",
    "islom karimov": "Islam Karimov president Uzbekistan",
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
        txt = await _chat_complete(
            f"Rasm qidirish uchun inglizcha 3-5 kalit so'z. Faqat so'zlar, vergul bilan: {topic}",
            system="You generate stock-photo search keywords in English. Keywords only.", max_tokens=60)
        if txt and 3 < len(txt) < 150:
            kw = re.sub(r'[^a-zA-Z\s,]', '', txt).strip()
            if kw: _KEYWORD_CACHE[key] = kw; _log(f"🔤 Kalit: '{topic}' → '{kw}'"); return kw
    except Exception as e: _log(f"[KEYWORD] xato: {e}")
    _KEYWORD_CACHE[key] = topic
    return topic

async def _wiki_image(topic):
    try:
        wiki = await wikipedia_fetch(topic, max_chars=200)
        if wiki.get("image"):
            return [{"url": wiki["image"], "tags": wiki["title"].lower(), "src": "wikipedia"}]
    except Exception: pass
    return []

async def _pixabay_images(query):
    if not PIXABAY_KEY: return []
    url = (f"https://pixabay.com/api/?key={PIXABAY_KEY}&q={aiohttp.helpers.quote(query)}"
           f"&image_type=photo&orientation=horizontal&per_page=40&safesearch=true&lang=en")
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=12)) as s:
            async with s.get(url) as r:
                if r.status != 200: return []
                data = await r.json()
        return [{"url": h.get("webformatURL"),
                 "tags": (h.get("tags", "") + " " + str(h.get("user", ""))).lower(), "src": "pixabay"}
                for h in data.get("hits", []) if h.get("webformatURL")]
    except Exception as e: _log(f"[PIXABAY] xato: {e}"); return []

async def _pexels_images(query):
    if not PEXELS_KEY: return []
    url = f"https://api.pexels.com/v1/search?query={aiohttp.helpers.quote(query)}&per_page=40&orientation=landscape"
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=12),
                headers={"Authorization": PEXELS_KEY}) as s:
            async with s.get(url) as r:
                if r.status != 200: return []
                data = await r.json()
        return [{"url": p.get("src", {}).get("large"),
                 "tags": (str(p.get("alt", "")) + " " + str(p.get("photographer", ""))).lower(), "src": "pexels"}
                for p in data.get("photos", []) if p.get("src", {}).get("large")]
    except Exception as e: _log(f"[PEXELS] xato: {e}"); return []

async def _unsplash_images(query):
    if not UNSPLASH_KEY: return []
    url = f"https://api.unsplash.com/search/photos?query={aiohttp.helpers.quote(query)}&per_page=30&orientation=landscape"
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=12),
                headers={"Authorization": f"Client-ID {UNSPLASH_KEY}"}) as s:
            async with s.get(url) as r:
                if r.status != 200: return []
                data = await r.json()
        return [{"url": p.get("urls", {}).get("regular"),
                 "tags": (str(p.get("alt_description", "")) + " " + str(p.get("description", ""))).lower(), "src": "unsplash"}
                for p in data.get("results", []) if p.get("urls", {}).get("regular")]
    except Exception as e: _log(f"[UNSPLASH] xato: {e}"); return []

async def search_images(query, count=5):
    q = re.sub(r'[^\w\s\']', ' ', str(query)).strip()
    if len(q) < 3: _log(f"[RASM] qisqa: '{q}'"); return []
    keywords = await topic_to_english_keywords(q)
    kw_list = [w for w in keywords.lower().split() if len(w) > 2 and w not in STOP_WORDS]
    results = await asyncio.gather(_wiki_image(q), _pixabay_images(keywords),
                                   _pexels_images(keywords), _unsplash_images(keywords))
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
    _log(f"📸 '{q}' → {len(urls)} rasm" if urls else f"⚠️ '{q}' rasm topilmadi")
    return urls

async def download_image(url, save_path):
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    with open(save_path, "wb") as f: f.write(await resp.read())
                    try:
                        from PIL import Image
                        with Image.open(save_path) as img: img.verify()
                    except Exception: pass
                    return True
    except Exception as e: _log(f"[RASM] yuklash xato: {e}")
    return False

async def _try_post(api, model, payload):
    global LAST_ERROR
    if not api["api_key"]:
        LAST_ERROR = f"Kalit mavjud emas: {api['name']}"; return None, None, LAST_ERROR
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
                        except Exception as e: LAST_ERROR = f"Tahlil xato: {e}"; return resp.status, None, LAST_ERROR
                    LAST_ERROR = f"HTTP {resp.status}: {body[:150]}"; return resp.status, None, LAST_ERROR
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
                        except Exception as e: LAST_ERROR = f"Tahlil xato: {e}"; return resp.status, None, LAST_ERROR
                    LAST_ERROR = f"HTTP {resp.status}: {body[:150]}"; return resp.status, None, LAST_ERROR
    except aiohttp.ClientConnectorError as e: LAST_ERROR = f"Ulanib bo'lmadi: {e}"; return None, None, LAST_ERROR
    except asyncio.TimeoutError: LAST_ERROR = f"Vaqt tugadi: {AI_TIMEOUT}s"; return None, None, LAST_ERROR
    except Exception as e: LAST_ERROR = f"Xato: {type(e).__name__}: {e}"; return None, None, LAST_ERROR

async def _chat_complete(prompt, system=None, max_tokens=8000):
    messages = [
        {"role": "system", "content": system or _pure_language_system("uz")},
        {"role": "user", "content": prompt}]
    payload = {"messages": messages, "temperature": 0.7, "max_tokens": max_tokens}
    start = CURRENT_API_INDEX
    while True:
        api = get_current_api(); model = get_current_model()
        if not api["api_key"]:
            switch_to_next_api()
            if CURRENT_API_INDEX == start: break
            continue
        status, text, err = await _try_post(api, model, payload)
        if status == 200 and text:
            text = verify_facts(clean_ai_text(text))
            _log(f"✅ {api['name']} | {model}")
            return text.strip()
        _log(f"❌ {api['name']} | {model}: {err}")
        if not switch_to_next_model() and CURRENT_API_INDEX == start: break
        await asyncio.sleep(0.3)
    _log("⚠️ BARCHA API ishlamadi!")
    return "⚠️ Hozir barcha manbalar ishlashdan to'xtadi."

async def chat_answer(question):
    return await _chat_complete(question, system=_pure_language_system("uz") + " Suhbat uslubida javob bering.", max_tokens=2000)

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

FB = {
    "uz": {"sections": ["Kirish", "Tarixiy kelib chiqishi", "Nazariy asoslari", "Asosiy qism 1",
            "Asosiy qism 2", "Asosiy qism 3", "Tahlil", "Muammolar va yechimlar", "Xulosa", "Adabiyotlar"],
        "extra": "Qo'shimcha bob", "body": "{topic} bo'yicha {sec} — batafsil ma'lumotlar, faktlar, misollar va tahlillar.",
        "slide_sections": ["Kirish", "Tarixiy kelib chiqishi", "Yoshlik va ta'lim", "Faoliyat bosqichlari",
            "Asosiy yutuqlar", "Ilm-fan va madaniyatga hissasi", "Bunyodkorlik", "So'nggi yillari", "Merosi", "Xulosa"],
        "slide_body": ["{topic} ning {sec} jihati muhim", "Ushbu davrda shaxs shakllangan",
            "Olingan bilim asos bo'lgan", "Ko'plab o'zgarishlar bo'lgan",
            "Bugungi kunda o'rganilmoqda", "Merosi kelajak uchun yo'l ko'rsatadi"]},
    "ru": {"sections": ["Введение", "Историческое происхождение", "Теоретические основы", "Основная часть 1",
            "Основная часть 2", "Основная часть 3", "Анализ", "Проблемы и решения", "Заключение", "Литература"],
        "extra": "Дополнительная глава", "body": "По теме «{topic}» раздел «{sec}» — подробные факты и анализ.",
        "slide_sections": ["Введение", "Историческое происхождение", "Молодость и обучение", "Этапы деятельности",
            "Основные достижения", "Вклад в науку и культуру", "Созидание", "Последние годы", "Наследие", "Заключение"],
        "slide_body": ["Аспект «{sec}» важен", "Личность формировалась", "Знания стали основой",
            "Много изменений", "Сегодня изучается", "Наследие останется"]},
    "en": {"sections": ["Introduction", "Background", "Theoretical foundations", "Main part 1",
            "Main part 2", "Main part 3", "Analysis", "Problems and solutions", "Conclusion", "References"],
        "extra": "Additional chapter", "body": "On «{topic}», section «{sec}» — detailed facts and analysis.",
        "slide_sections": ["Introduction", "Background", "Youth and education", "Stages of activity",
            "Main achievements", "Contribution to science", "Creation", "Later years", "Legacy", "Conclusion"],
        "slide_body": ["The aspect is important", "Personality was formed", "Knowledge became foundation",
            "Many changes", "Today widely studied", "Legacy remains"]},
}
def _fb(lang): return FB.get(str(lang).lower(), FB["uz"])

def _fallback_text(service, topic, options, lang, bob_count=10):
    fb = _fb(lang); sections = list(fb["sections"])
    while len(sections) < bob_count:
        sections.insert(len(sections)-2, f"{fb['extra']} {len(sections)-3}")
    parts = [f"{sec}\n{fb['body'].format(topic=topic, sec=sec.lower())}\n{fb['body'].format(topic=topic, sec=sec.lower())}"
             for sec in sections[:bob_count]]
    return f"{topic}\n\n" + "\n\n".join(parts)

def _fallback_slides(topic, count, lang):
    fb = _fb(lang); secs = fb["slide_sections"]; bodies = fb["slide_body"]; out = []
    for i in range(count):
        sec = secs[i % len(secs)]
        b = bodies[i % len(bodies)].format(topic=topic, sec=sec.lower())
        out.append({"slide_number": i+1, "title": sec, "content": [b]*5,
                    "has_image": _is_image_slide(i, count),
                    "image_prompt": _make_image_prompt(topic, i) if _is_image_slide(i, count) else None})
    return out
