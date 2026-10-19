"""
AI API — to'liq versiya
========================
✓ Barcha xizmatlar avval Wikipediyadan (uz→ru→en) fakt oladi
✓ Rasm: Wikipedia rasmi + Pixabay + Pexels + Unsplash (4 manba)
✓ Kalit so'zlarni AI avtomatik inglizchaga tarjima qiladi
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

# ===================== SOZLAMALAR =====================
LAST_ERROR = "hali sinanmadi"
PIXABAY_KEY  = os.getenv("PIXABAY_KEY", "")
PEXELS_KEY   = os.getenv("PEXELS_KEY", "")      # pexels.com/api — bepul
UNSPLASH_KEY = os.getenv("UNSPLASH_KEY", "")    # unsplash.com/developers — bepul
IMAGE_SLIDE_INDICES = [0, 3, 6]
WIKI_LANGS = ["uz", "ru", "en"]                 # qidiruv tartibi
USER_AGENT = "SlaydBot/1.0 (aloqa: admin@example.uz)"  # Wikipediya talab qiladi
_KEYWORD_CACHE = {}                             # takror tarjima qilmaslik

# ===================== API RO'YXATI =====================
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
        _log(f"⚠️ {api['name']} da barcha modellar sinab ko'rildi. Keyingi API ga o'tilmoqda...")
        return False
    _log(f"🔄 Model almashtirildi: {api['name']} → {get_current_model()}")
    return True

def switch_to_next_api():
    global CURRENT_API_INDEX, CURRENT_MODEL_INDEX
    CURRENT_API_INDEX = (CURRENT_API_INDEX + 1) % len(API_LIST)
    CURRENT_MODEL_INDEX = 0
    _log(f"⚠️ Keyingi API: {get_current_api()['name']} | Model: {get_current_model()}")
    return get_current_api()

# ===================== YORDAMCHI =====================
def clean_ai_text(text):
    if not text: return ""
    text = re.sub(r'\*+', '', str(text))
    text = re.sub(r'^#{1,3}\s*', '', str(text), flags=re.MULTILINE)
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

LANG_NAMES = {"uz": "o'zbek", "ru": "rus", "en": "english", "tr": "turkish",
              "de": "german", "fr": "french"}
ALL_LANGS = ("uz", "ru", "en", "tr", "de", "fr")
def _lang_name(code): return LANG_NAMES.get(str(code).lower(), "o'zbek")

# ===================== 1. WIKIPEDIYA =====================
async def wikipedia_fetch(topic, max_chars=3500, full=False):
    """Wikipediyadan fakt oladi: uz→ru→en. full=True → butun maqola (diplom/kurs uchun)."""
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
    """Wiki natijasidan prompt uchun blok yasaydi (barcha xizmatlarda ishlatiladi)."""
    if not wiki.get("found"): return ""
    return (f"\n\n=== WIKIPEDIYA MANBASI ({wiki['lang'].upper()}) ===\n"
            f"Sarlavha: {wiki['title']}\n"
            f"Quyidagi faktlarni asos qilib yoz, xayoliy ma'lumot qo'shma, "
            f"sanalar va raqamlarni aynan shunday qoldir:\n{wiki['text']}\n"
            f"Manba: {wiki['url']}")

# ===================== 2. RASM QIDIRUV =====================
SEARCH_MAP = {
    # shaxslar
    "alisher navoiy": "Alisher Navoi portrait poet", "navoiy": "Alisher Navoi writer poet",
    "amir temur": "Amir Timur Tamerlane conqueror", "temur": "Timur Tamerlane empire",
    "jaloliddin manguberdi": "Jalal ad-Din Manguberdi Khwarazmshah warrior",
    "manguberdi": "Jalal ad-Din Manguberdi hero",
    "mirzo ulugbek": "Ulugh Beg astronomer Samarkand observatory", "ulugbek": "Ulugh Beg Timurid scholar",
    "ibn sino": "Avicenna Ibn Sina physician philosopher",
    "islom karimov": "Islam Karimov president Uzbekistan",
    # shaharlar
    "toshkent": "Tashkent city Uzbekistan", "samarqand": "Samarkand Registan square",
    "buxoro": "Bukhara old city Uzbekistan", "xorazm": "Khiva Khwarezm fortress",
    "farg'ona": "Fergana valley Uzbekistan", "andijon": "Andijan city Uzbekistan",
    "qoraqalpog'iston": "Karakalpakstan Aral sea", "uzbekiston": "Uzbekistan landmark culture",
    # fanlar
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
    """Rasm qidirish uchun inglizcha kalit so'z: SEARCH_MAP → AI → to'g'ridan-to'g'ri."""
    key = topic.lower().strip()
    if key in _KEYWORD_CACHE: return _KEYWORD_CACHE[key]
    for uz, en in SEARCH_MAP.items():
        if uz in key:
            _KEYWORD_CACHE[key] = en; return en
    try:
        txt = await _chat_complete(
            f"Rasm qidirish (stock photo) uchun inglizcha 3-5 kalit so'z yoz. Faqat so'zlar, vergul bilan: {topic}",
            system="You generate stock-photo search keywords in English. Keywords only.", max_tokens=60)
        if txt and 3 < len(txt) < 150:
            kw = re.sub(r'[^a-zA-Z\s,]', '', txt).strip()
            if kw:
                _KEYWORD_CACHE[key] = kw
                _log(f"🔤 AI kalit so'z: '{topic}' → '{kw}'")
                return kw
    except Exception as e:
        _log(f"[KEYWORD] xato: {e}")
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
    except Exception as e:
        _log(f"[PIXABAY] xato: {e}"); return []

async def _pexels_images(query):
    if not PEXELS_KEY: return []
    url = (f"https://api.pexels.com/v1/search?query={aiohttp.helpers.quote(query)}"
           f"&per_page=40&orientation=landscape")
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=12),
                headers={"Authorization": PEXELS_KEY}) as s:
            async with s.get(url) as r:
                if r.status != 200: return []
                data = await r.json()
        return [{"url": p.get("src", {}).get("large"),
                 "tags": (str(p.get("alt", "")) + " " + str(p.get("photographer", ""))).lower(), "src": "pexels"}
                for p in data.get("photos", []) if p.get("src", {}).get("large")]
    except Exception as e:
        _log(f"[PEXELS] xato: {e}"); return []

async def _unsplash_images(query):
    if not UNSPLASH_KEY: return []
    url = (f"https://api.unsplash.com/search/photos?query={aiohttp.helpers.quote(query)}"
           f"&per_page=30&orientation=landscape")
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=12),
                headers={"Authorization": f"Client-ID {UNSPLASH_KEY}"}) as s:
            async with s.get(url) as r:
                if r.status != 200: return []
                data = await r.json()
        return [{"url": p.get("urls", {}).get("regular"),
                 "tags": (str(p.get("alt_description", "")) + " " + str(p.get("description", ""))).lower(), "src": "unsplash"}
                for p in data.get("results", []) if p.get("urls", {}).get("regular")]
    except Exception as e:
        _log(f"[UNSPLASH] xato: {e}"); return []

async def search_images(query, count=5):
    """4 manbadan rasm: Wikipedia(eng aniq) + Pixabay + Pexels + Unsplash. Relevans bo'yicha saralash."""
    q = re.sub(r'[^\w\s\']', ' ', str(query)).strip()
    if len(q) < 3:
        _log(f"[RASM] so'z qisqa: '{q}'"); return []
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
            if c["src"] == "wikipedia": mos += 10  # eng aniq manba — birinchi
            candidates.append((mos, u))
    candidates.sort(key=lambda x: -x[0])
    urls = [u for mos, u in candidates if mos > 0][:count]
    _log(f"📸 '{q}' → {len(urls)} rasm (kalit: '{keywords}')" if urls else f"⚠️ '{q}' rasm topilmadi")
    return urls

async def download_image(url, save_path):
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    with open(save_path, "wb") as f:
                        f.write(await resp.read())
                    try:
                        from PIL import Image
                        with Image.open(save_path) as img: img.verify()
                    except Exception: pass
                    return True
    except Exception as e:
        _log(f"[RASM] yuklash xato: {e}")
    return False

# ===================== 3. AI SO'ROV =====================
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
                        try:
                            return 200, json.loads(body)["candidates"][0]["content"]["parts"][0]["text"], None
                        except Exception as e:
                            LAST_ERROR = f"Javob tahlil xato: {e}"; return resp.status, None, LAST_ERROR
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
                        try:
                            return 200, json.loads(body)["choices"][0]["message"]["content"], None
                        except Exception as e:
                            LAST_ERROR = f"Javob tahlil xato: {e}"; return resp.status, None, LAST_ERROR
                    LAST_ERROR = f"HTTP {resp.status}: {body[:150]}"; return resp.status, None, LAST_ERROR
    except aiohttp.ClientConnectorError as e:
        LAST_ERROR = f"Ulanib bo'lmadi: {e}"; return None, None, LAST_ERROR
    except asyncio.TimeoutError:
        LAST_ERROR = f"Vaqt tugadi: {AI_TIMEOUT}s"; return None, None, LAST_ERROR
    except Exception as e:
        LAST_ERROR = f"Xato: {type(e).__name__}: {e}"; return None, None, LAST_ERROR

async def _chat_complete(prompt, system=None, max_tokens=16000):
    messages = [
        {"role": "system", "content": system or "Siz mutaxassis yordamchisiz. Javoblar faktlarga asoslangan bo'lsin. Hech qanday * # belgi ishlatmang."},
        {"role": "user", "content": prompt}]
    payload = {"messages": messages, "temperature": 0.7, "max_tokens": max_tokens}
    start = CURRENT_API_INDEX
    while True:
        api = get_current_api(); model = get_current_model()
        if not api["api_key"]:
            switch_to_next_api()
            if CURRENT_API_INDEX == start: break
            continue
        _log(f"Sinab ko'rilmoqda: {api['name']} | Model: {model}")
        status, text, err = await _try_post(api, model, payload)
        if status == 200 and text:
            text = verify_facts(clean_ai_text(text))
            _log(f"✅ {api['name']} | {model}")
            return text.strip()
        _log(f"❌ {api['name']} | {model}: {err}")
        if not switch_to_next_model() and CURRENT_API_INDEX == start: break
        await asyncio.sleep(0.3)
    _log("⚠️ BARCHA API ishlamadi!")
    return "⚠️ Hozir barcha manbalar ishlashdan to'xtadi. Iltimos, keyinroq urinib ko'ring."

async def chat_answer(question):
    return await _chat_complete(question, system="Siz do'stona, bilimdon AI yordamchisiz. To'liq javob bering. * # belgi ishlatmang.")

# ===================== 4. SLAYD (Taqdimot) =====================
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
    char_map = {5: 4000, 7: 5000, 10: 7000, 12: 8500, 15: 10000,
                18: 11500, 20: 13000, 25: 18000, 30: 22000}
    target_chars = char_map.get(count, count * 750)

    wiki = await wikipedia_fetch(topic, max_chars=4000)
    wb = wiki_block(wiki)
    if wiki["found"]: _log(f"📚 [Taqdimot] Wiki ulandi: {wiki['title']}")

    system = f"""Siz akademik kontent mutaxassissiz. Hammasi faqat {ln} tilida! 
Har slayd: sarlavha + 8-10 gap, faktlar bilan. Belgilar: kamida {target_chars}. 
* # belgi ishlatmang. Faqat JSON qaytaring. Manba berilgan bo'lsa, faktlarni o'shandan ol."""
    prompt = f"""{topic} mavzusida {count} slaydli taqdimot. Til: faqat {ln}.{wb}
JSON: [{{"title":"...","content":["gap1","gap2"]}}]"""

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
        _log(f"✅ Tayyor: {len(out)} slayd")
        return out, True
    _log("⚠️ Zaxira slayd ishlatilmoqda")
    return _fallback_slides(topic, count, lang), False

# ===================== 5. HUJJAT XIZMATLARI (Referat, Kurs, Diplom, Maqola, Tezis, Insho, Mustaqil ish) =====================
LONG_SERVICES = ("diplom", "diplom_ishi", "kurs", "kurs_ishi", "referat", "maqola", "tezis")

async def generate(service, topic, options, lang="uz"):
    from services import SERVICES
    s = SERVICES.get(service, {})
    name = s.get("name", service)
    pages = int(options.get("pages", 10) or 10)
    ln = _lang_name(lang)
    bob_count = max(8, pages)
    doc_chars = pages * 900

    # Wikipediya — uzun hujjatga to'liq maqola
    long_doc = service in LONG_SERVICES or pages >= 15
    wiki = await wikipedia_fetch(topic, max_chars=10000 if long_doc else 4000, full=long_doc)
    wb = wiki_block(wiki)
    if wiki["found"]:
        _log(f"📚 [{name}] Wiki ulandi: {wiki['title']} ({len(wiki['text'])} belgi)")
    else:
        _log(f"📚 [{name}] Wiki topilmadi")

    prompt = (f"Topic: {topic}\nService: {name}\nLength: {pages} sahifa (kamida {doc_chars} belgi)\n\n"
              f"Faqat {ln} tilida yoz! Boshqa til aralashmasin.{wb}\n\n"
              f"Kamida {bob_count} bo'lim: Kirish → Asosiy qism → Tahlil → Xulosa. "
              f"Har bo'limda faktlar, sanalar, raqamlar, misollar bo'lsin.")
    result = await _chat_complete(prompt)
    if result and "⚠️" not in result:
        return result, True
    await asyncio.sleep(1)
    return _fallback_text(service, topic, options, lang, bob_count), False

# ===================== 6. QUIZ / TEST =====================
async def generate_quiz(topic, count=10, lang="uz"):
    """Quiz/Test — Wikipediya faktlariga asoslangan savollar."""
    ln = _lang_name(lang)
    wiki = await wikipedia_fetch(topic, max_chars=5000)
    wb = wiki_block(wiki)
    if wiki["found"]: _log(f"📚 [Quiz] Wiki ulandi: {wiki['title']}")

    system = (f"Siz test savollari yaratuvchi mutaxassissiz. Hammasi faqat {ln} tilida! "
              f"Har bir savolda 4 ta javob variantidan bittasi to'g'ri. JSON qaytaring. * # belgi ishlatmang.")
    prompt = f"""{topic} bo'yicha {count} ta test savoli yasang. Til: faqat {ln}.{wb}
JSON format: [{{"question":"...","options":["a","b","c","d"],"correct":0}}]
correct — to'g'ri javob indeksi (0-3). Savollar faktlarga asoslangan bo'lsin."""

    txt = await _chat_complete(prompt, system=system, max_tokens=4000)
    questions = _extract_json(txt) if txt else None
    if questions and isinstance(questions, list) and len(questions) >= 3:
        _log(f"✅ Quiz tayyor: {len(questions)} savol")
        return questions, True
    _log("⚠️ Quiz zaxirasi ishlatilmoqda")
    return _fallback_quiz(topic, count, lang), False

def _fallback_quiz(topic, count, lang):
    out = []
    for i in range(count):
        out.append({"question": f"{topic} bo'yicha {i+1}-savol: umumiy bilim?",
                    "options": ["Variant A", "Variant B", "Variant C", "Variant D"],
                    "correct": 0})
    return out

# ===================== YORDAMCHI: JSON ajratish =====================
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

# ===================== ZAXIRA MATN TIZIMI =====================
FB = {
    "uz": {"sections": ["Kirish", "Tarixiy kelib chiqishi", "Nazariy asoslari", "Asosiy qism 1",
            "Asosiy qism 2", "Asosiy qism 3", "Tahlil", "Muammolar va yechimlar", "Xulosa", "Foydalanilgan adabiyotlar"],
        "extra": "Qo'shimcha bob",
        "body": "{topic} bo'yicha {sec} — batafsil ma'lumotlar, faktlar, misollar va tahlillar. Har bir gap to'liq, mazmunli va batafsil yozilgan.",
        "slide_sections": ["Kirish va dolzarblik", "Tarixiy kelib chiqishi", "Yoshlik va ta'lim", "Faoliyat bosqichlari",
            "Asosiy yutuqlar", "Ilm-fan va madaniyatga hissasi", "Bunyodkorlik va xayriya", "So'nggi yillari",
            "Merosi va zamonaviy ahamiyati", "Xulosa"],
        "slide_body": ["{topic} ning {sec} jihati eng muhim qismlardan biridir",
            "Ushbu davrda shaxs va dunyoqarasi shakllangan",
            "Olingan bilim va tajriba keyingi ishlariga asos bo'lgan",
            "Faoliyati davrida ko'plab o'zgarishlar amalga oshirilgan",
            "Bugungi kunda bu mavzu keng o'rganilmoqda",
            "Uning merosi kelajak avlodlar uchun yo'l ko'rsatadi"]},
    "ru": {"sections": ["Введение", "Историческое происхождение", "Теоретические основы", "Основная часть 1",
            "Основная часть 2", "Основная часть 3", "Анализ", "Проблемы и решения", "Заключение", "Список литературы"],
        "extra": "Дополнительная глава",
        "body": "По теме «{topic}» раздел «{sec}» — подробные сведения, факты, примеры и анализ.",
        "slide_sections": ["Введение и актуальность", "Историческое происхождение", "Молодость и обучение", "Этапы деятельности",
            "Основные достижения", "Вклад в науку и культуру", "Созидание и благотворительность", "Последние годы",
            "Наследие и современное значение", "Заключение"],
        "slide_body": ["Аспект «{sec}» темы «{topic}» важен", "В этот период формировалась личность",
            "Знания стали основой последующих работ", "Произошло множество изменений",
            "Сегодня тема широко изучается", "Наследие останется в истории"]},
    "en": {"sections": ["Introduction", "Historical background", "Theoretical foundations", "Main part 1",
            "Main part 2", "Main part 3", "Analysis", "Problems and solutions", "Conclusion", "References"],
        "extra": "Additional chapter",
        "body": "On «{topic}», section «{sec}» provides detailed facts, examples and analysis.",
        "slide_sections": ["Introduction and relevance", "Historical background", "Youth and education", "Stages of activity",
            "Main achievements", "Contribution to science and culture", "Creation and charity", "Later years",
            "Legacy and modern significance", "Conclusion"],
        "slide_body": ["The «{sec}» aspect of «{topic}» is important", "Personality was formed in this period",
            "Knowledge became the foundation", "Many changes took place",
            "Today this topic is widely studied", "The legacy will remain"]},
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
