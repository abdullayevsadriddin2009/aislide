"""AI API — ko'p manbali + ko'p modelli avtomatik almashish tizimi.
Har bir API ichida bir nechta model, bittasi ishlamasa o'sha API ichidagi keyingisiga o'tadi.
Hammasi ishlamasa keyingi API ga o'tadi.
"""
import aiohttp
import asyncio
import json
import re
import os
from dotenv import load_dotenv
load_dotenv()
from config import AI_API_URL, AI_MODEL, AI_TIMEOUT

# === Holat ===
LAST_ERROR = "hali sinanmadi"
PIXABAY_KEY = os.getenv("PIXABAY_KEY", "")
IMAGE_SLIDE_INDICES = [0, 3, 6]

# === Har bir API uchun bir nechta model ===
API_LIST = [
    {
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key": os.getenv("OPENROUTER_KEY", ""),
        "type": "openai",
        "models": [
            "openai/gpt-3.5-turbo",
            "openai/gpt-4o-mini",
            "openai/gpt-4o",
            "anthropic/claude-3.5-sonnet",
            "meta-llama/llama-3.1-8b-instruct",
            "meta-llama/llama-3.1-70b-instruct"
        ]
    },
    {
        "name": "Groq 1",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key": os.getenv("GROQ_KEY_1", ""),
        "type": "openai",
        "models": [
            "llama-3-8b-8192",
            "llama-3-70b-8192",
            "llama-3.1-8b-instruct",
            "llama-3.1-70b-instruct",
            "mixtral-8x7b-32768",
            "gemma2-9b-it"
        ]
    },
    {
        "name": "Groq 2",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key": os.getenv("GROQ_KEY_2", ""),
        "type": "openai",
        "models": [
            "llama-3-8b-8192",
            "llama-3-70b-8192",
            "llama-3.1-8b-instruct",
            "llama-3.1-70b-instruct",
            "mixtral-8x7b-32768",
            "gemma2-9b-it"
        ]
    },
    {
        "name": "Google AI 1",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "api_key": os.getenv("GOOGLE_KEY_1", ""),
        "type": "google",
        "models": [
            "gemini-1.5-flash",
            "gemini-1.5-flash-8b",
            "gemini-1.5-pro",
            "gemini-2.0-flash-exp"
        ]
    },
    {
        "name": "Google AI 2",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "api_key": os.getenv("GOOGLE_KEY_2", ""),
        "type": "google",
        "models": [
            "gemini-1.5-flash",
            "gemini-1.5-flash-8b",
            "gemini-1.5-pro",
            "gemini-2.0-flash-exp"
        ]
    },
    {
        "name": "Open Code",
        "base_url": "https://api.openai.com/v1",
        "api_key": os.getenv("OPENCODE_KEY", ""),
        "type": "openai",
        "models": [
            "gpt-3.5-turbo",
            "gpt-4o-mini",
            "gpt-4o"
        ]
    },
    {
        "name": "Local FreeLLMAPI",
        "base_url": os.getenv("AI_BASE_URL", ""),
        "api_key": os.getenv("AI_API_KEY", ""),
        "type": "openai",
        "models": [
            os.getenv("AI_MODEL", "auto"),
            "gpt-3.5-turbo",
            "llama3"
        ]
    }
]

CURRENT_API_INDEX = 0
CURRENT_MODEL_INDEX = 0

def get_current_api():
    return API_LIST[CURRENT_API_INDEX]

def get_current_model():
    api = get_current_api()
    return api["models"][CURRENT_MODEL_INDEX % len(api["models"])]

def switch_to_next_model() -> bool:
    """O'sha API ichidagi keyingi modelga o'tadi. Oxirgi bo'lsa False qaytaradi."""
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
    """Keyingi API ga o'tadi, model indeksini 0 ga qaytaradi."""
    global CURRENT_API_INDEX, CURRENT_MODEL_INDEX
    CURRENT_API_INDEX = (CURRENT_API_INDEX + 1) % len(API_LIST)
    CURRENT_MODEL_INDEX = 0
    api = get_current_api()
    _log(f"⚠️ Avvalgi API ishlamadi! Keyingisiga o'tildi: {api['name']} | Model: {get_current_model()}")
    return api

# === Yordamchi funksiyalar ===
def clean_ai_text(text):
    if not text:
        return ""
    text = re.sub(r'\*+', '', str(text))
    text = re.sub(r'^#{1,3}\s*', '', str(text), flags=re.MULTILINE)
    text = re.sub(r'```.*?```', '', str(text), flags=re.DOTALL)
    text = re.sub(r'\n\s*\n', '\n\n', str(text))
    return text.strip()

def verify_facts(text):
    if not text:
        return text
    if "Navoiy" in text or "Alisher Navoiy" in text:
        text = re.sub(r'Samarqand', 'Hirot', text)
        text = re.sub(r'Samarqandda', 'Hirot shahrida', text)
    return text

def _log(msg):
    print(f"[AI_API] {msg}", flush=True)

def get_last_error():
    return LAST_ERROR

LANG_NAMES = {
    "uz": "o'zbek", "ru": "rus", "en": "english",
    "tr": "turkish", "de": "german", "fr": "french",
}
ALL_LANGS = ("uz", "ru", "en", "tr", "de", "fr")
def _lang_name(code):
    return LANG_NAMES.get(str(code).lower(), "o'zbek")

# === Rasm qidiruv lug'ati ===
SEARCH_MAP = {
    "alisher navoiy": "Alisher Navoi portrait historical poet",
    "navoiy": "Alisher Navoi writer historical",
    "amir temur": "Amir Temur historical leader conqueror",
    "temur": "Amir Temur Timurid empire",
    "jaloliddin manguberdi": "Jaloliddin Manguberdi Khwarazmshah warrior hero",
    "manguberdi": "Jaloliddin Manguberdi medieval hero",
    "mirzo ulugbek": "Mirzo Ulugh Beg astronomer observatory Samarkand",
    "ulugbek": "Ulugh Beg Timurid scholar scientist",
    "ibn sino": "Avicenna Ibn Sina philosopher physician",
    "toshkent": "Tashkent city Uzbekistan architecture",
    "samarqand": "Samarkand Registan historical",
    "buxoro": "Bukhara historical Uzbekistan",
    "uzbekiston": "Uzbekistan culture landmark",
}

# === So'rov yuborish — model ham o'zgaradi ===
async def _try_post(api, model, payload):
    global LAST_ERROR
    if not api["api_key"]:
        LAST_ERROR = f"Kalit mavjud emas: {api['name']}"
        return None, None, LAST_ERROR
        
    try:
        headers = {"Content-Type": "application/json"}
        if api["type"] == "google":
            url = f"{api['base_url']}/models/{model}:generateContent?key={api['api_key']}"
            data = {"contents": [{"parts": [{"text": payload["messages"][-1]["content"]}]}]}
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=AI_TIMEOUT)) as session:
                async with session.post(url, json=data, timeout=AI_TIMEOUT) as resp:
                    body = await resp.text()
                    if resp.status == 200:
                        LAST_ERROR = None
                        try:
                            data = json.loads(body)
                            text = data["candidates"][0]["content"]["parts"][0]["text"]
                            return 200, text, None
                        except Exception as e:
                            LAST_ERROR = f"Javobni tahlil qilib bo'lmadi: {e}"
                            return resp.status, None, LAST_ERROR
                    LAST_ERROR = f"HTTP {resp.status}: {body[:150]}"
                    return resp.status, None, LAST_ERROR
        else:
            headers["Authorization"] = f"Bearer {api['api_key']}"
            url = f"{api['base_url']}/chat/completions"
            payload_with_model = dict(payload)
            payload_with_model["model"] = model
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=AI_TIMEOUT)) as session:
                async with session.post(url, headers=headers, json=payload_with_model, timeout=AI_TIMEOUT) as resp:
                    body = await resp.text()
                    if resp.status == 200:
                        LAST_ERROR = None
                        try:
                            data = json.loads(body)
                            text = data["choices"][0]["message"]["content"]
                            return 200, text, None
                        except Exception as e:
                            LAST_ERROR = f"Javobni tahlil qilib bo'lmadi: {e}"
                            return resp.status, None, LAST_ERROR
                    LAST_ERROR = f"HTTP {resp.status}: {body[:150]}"
                    return resp.status, None, LAST_ERROR
    except aiohttp.ClientConnectorError as e:
        LAST_ERROR = f"Ulanib bo'lmadi: {e}"
        return None, None, LAST_ERROR
    except asyncio.TimeoutError:
        LAST_ERROR = f"Vaqt tugadi: {AI_TIMEOUT}s"
        return None, None, LAST_ERROR
    except Exception as e:
        LAST_ERROR = f"Xato: {type(e).__name__}: {e}"
        return None, None, LAST_ERROR

async def _chat_complete(prompt, system=None, max_tokens=16000):
    """Asosiy tizim: avval model almashadi, keyin API almashadi"""
    messages = [
        {"role": "system", "content": system or "Siz mutaxassis yordamchisiz. Barcha javoblar to'liq, batafsil, faktlarga asoslangan bo'lsin. Hech qanday * # belgi ishlatmang."},
        {"role": "user", "content": prompt}
    ]
    payload = {"messages": messages, "temperature": 0.7, "max_tokens": max_tokens}
    
    start_api_index = CURRENT_API_INDEX
    while True:
        api = get_current_api()
        model = get_current_model()
        
        if not api["api_key"]:
            _log(f"O'tkazib yuborilmoqda: {api['name']} — kalit kiritilmagan")
            switch_to_next_api()
            if CURRENT_API_INDEX == start_api_index:
                break
            continue
            
        _log(f"Sinab ko'rilmoqda: {api['name']} | Model: {model}")
        status, text, err = await _try_post(api, model, payload)
        
        if status == 200 and text:
            text = clean_ai_text(text)
            text = verify_facts(text)
            _log(f"✅ {api['name']} | {model} orqali javob olindi")
            return text.strip()
        
        _log(f"❌ {api['name']} | {model} ishlamadi: {err}")
        has_next = switch_to_next_model()
        if not has_next:
            if CURRENT_API_INDEX == start_api_index:
                break  # barchasi sinab ko'rildi
            await asyncio.sleep(0.3)
            continue
        await asyncio.sleep(0.3)
    
    _log("⚠️ BARCHA API va modellar ishlashdan to'xtadi yoki kalitlar kiritilmagan!")
    return "⚠️ Hozir barcha manbalar ishlashdan to'xtadi. Iltimos, kalitlarni tekshiring va keyinroq urinib ko'ring."

async def chat_answer(question):
    return await _chat_complete(question, system="Siz do'stona, bilimdon AI yordamchisiz. Foydalanuvchi savollariga to'liq, batafsil javob bering. Hech qanday * # belgi ishlatmang.")

async def generate(service, topic, options, lang="uz"):
    from services import SERVICES
    s = SERVICES.get(service, {})
    name = s.get("name", service)
    pages = int(options.get("pages", 10) or 10)
    ln = _lang_name(lang)
    bob_count = max(8, pages)
    doc_chars = pages * 900
    
    prompt = (
        f"Topic: {topic}\nService: {name}\nLength: {pages} sahifa (kamida {doc_chars} belgi)\n\n"
        f"Faqat {ln} tilida yozing! Boshqa til aralashmasin.\n\n"
        f"Kamida {bob_count} bo'limdan iborat bo'lsin: Kirish → Asosiy qism → Tahlil → Xulosa.\n"
        f"Har bir bo'limda faktlar, sanalar, raqamlar va misollar bo'lsin."
    )
    
    result = await _chat_complete(prompt)
    if result and "⚠️" not in result:
        return result, True
    await asyncio.sleep(1)
    return _fallback_text(service, topic, options, lang, bob_count), False

def _is_image_slide(idx, total):
    return idx in IMAGE_SLIDE_INDICES or idx == total - 1

async def generate_slides_structured(topic, subject, lang, count):
    ln = _lang_name(lang)
    char_map = {5: 4000, 7: 5000, 10: 7000, 12: 8500, 15: 10000,
                18: 11500, 20: 13000, 25: 18000, 30: 22000}
    target_chars = char_map.get(count, count * 750)
    
    system = f"""Siz akademik kontent yozish bo'yicha mutaxassissiz. 
Hamma narsa faqat {ln} tilida yozilsin! Har bir slayd aniq sarlavha va 8-10 gapdan iborat bo'lsin.
Belgi soni kamida {target_chars} ta bo'lsin. * # belgi ishlatmang. Faqat JSON qaytaring."""
    
    prompt = f"""{topic} mavzusida {count} ta slaydli taqdimot tayyorlang.
Til: faqat {ln}.
Har slayd: sarlavha + 8-10 gap, batafsil, faktlar bilan.
JSON formatida qaytaring: [{{"title":"...","content":["gap1","gap2"]}}]"""
    
    txt = None
    for attempt in range(2):
        txt = await _chat_complete(prompt, system=system, max_tokens=16000)
        if txt and len(txt) > target_chars * 0.5:
            break
        await asyncio.sleep(1)
    
    slides = _extract_json(txt) if txt else None
    if slides and isinstance(slides, list) and len(slides) >= 3:
        out = []
        while len(slides) < count:
            slides.append(slides[len(slides) % len(slides)])
        for i, s in enumerate(slides[:count]):
            content_list = s.get("content", ["Ma'lumot tayyorlanmoqda..."])
            if isinstance(content_list, str):
                content_list = [p.strip() for p in content_list.split("\n") if p.strip()]
            while len(content_list) < 5:
                content_list.append(f"{topic} bo'yicha batafsil tahlil.")
            out.append({
                "slide_number": i + 1,
                "title": clean_ai_text(str(s.get("title", f"Bo'lim {i+1}"))),
                "content": [clean_ai_text(str(c)) for c in content_list[:12]],
                "has_image": _is_image_slide(i, count),
                "image_prompt": _make_image_prompt(topic, i) if _is_image_slide(i, count) else None
            })
        _log(f"✅ Tayyor: {len(out)} slayd")
        return out, True
    
    _log("⚠️ API javobi yaroqsiz, zaxira versiya ishlatilmoqda")
    return _fallback_slides(topic, count, lang), False

def _extract_json(text):
    if not text:
        return None
    m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end+1])
        except Exception:
            pass
    return None

def _make_image_prompt(topic, idx):
    t = topic.lower()
    base = "historical figure, realistic, 8k"
    for uz, en in SEARCH_MAP.items():
        if uz in t:
            base = en
            break
    if idx == 0:
        return f"portrait of {base}, dignified pose, detailed, photorealistic, 8k"
    elif idx == 3:
        return f"{base} epic historical scene, cultural heritage, 8k"
    elif idx == 6:
        return f"{base} ancient architecture, monument, 8k"
    else:
        return f"{base} legacy, starry sky or sunset, inspirational, cinematic, 8k"

def _is_image_slide(idx, total):
    return idx in IMAGE_SLIDE_INDICES or idx == total - 1

async def search_images(query, count=5):
    q = re.sub(r'[^\w\s\']', ' ', str(query)).strip()
    if len(q) < 3:
        _log(f"[RASM] So'z juda qisqa: '{q}'")
        return []
    q_en = q
    for uz, en in SEARCH_MAP.items():
        if uz in q.lower():
            q_en = en
            _log(f"[RASM] Avtomatik: '{q}' → '{q_en}'")
            break
    keywords = [w for w in q_en.lower().split() if len(w) > 2 and w not in {
        "portrait", "historical", "hero", "leader", "conqueror", "poet", "writer",
        "scholar", "astronomer", "city", "architecture", "culture", "landmark",
        "warrior", "prince", "scientist", "figure", "realistic", "8k", "photo"
    }]
    urls = []
    for search_q in [q_en, q, f"{q_en} portrait", f"{q_en} historical"]:
        if len(urls) >= count:
            break
        url = (
            f"https://pixabay.com/api/?key={PIXABAY_KEY}"
            f"&q={search_q.replace(' ', '+')}"
            f"&image_type=photo&orientation=horizontal&per_page=50&safesearch=true"
        )
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        continue
                    data = await resp.json()
        except Exception as e:
            _log(f"[RASM] Xato: {e}")
            continue
        for hit in data.get("hits", []):
            u = hit.get("webformatURL")
            if not u or u in urls:
                continue
            tags = (hit.get("tags", "") + " " + hit.get("title", "")).lower()
            mos = sum(1 for kw in keywords if kw in tags)
            if mos == 0 and keywords:
                continue
            urls.append(u)
            if len(urls) >= count:
                break
    urls = list(dict.fromkeys(urls))[:count]
    if not urls:
        _log(f"⚠️ '{q}' uchun mos rasm topilmadi")
    else:
        _log(f"📸 '{q}' → {len(urls)} ta rasm topildi")
    return urls

async def download_image(url, save_path):
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    with open(save_path, "wb") as f:
                        f.write(data)
                    try:
                        from PIL import Image
                        with Image.open(save_path) as img:
                            img.verify()
                    except Exception:
                        pass
                    return True
    except Exception as e:
        _log(f"[RASM] Yuklash xatosi: {e}")
    return False

def _extract_json(text):
    if not text:
        return None
    m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end+1])
        except Exception:
            pass
    return None

# ===== Zaxira matn tizimi =====
FB = {
    "uz": {
        "sections": ["Kirish", "Tarixiy kelib chiqishi", "Nazariy asoslari", "Asosiy qism 1",
                     "Asosiy qism 2", "Asosiy qism 3", "Tahlil", "Muammolar va yechimlar",
                     "Xulosa", "Foydalanilgan adabiyotlar"],
        "extra": "Qo'shimcha bob",
        "body": "{topic} bo'yicha {sec} — batafsil ma'lumotlar, faktlar, misollar va tahlillar. "
                "Ushbu bob mavzuning muhim qismlaridan birini o'z ichiga oladi. Har bir gap to'liq, mazmunli va batafsil yozilgan.",
        "slide_sections": ["Kirish va dolzarblik", "Tarixiy kelib chiqishi", "Yoshlik va ta'lim",
                           "Faoliyat bosqichlari", "Asosiy yutuqlar", "Ilm-fan va madaniyatga hissasi",
                           "Bunyodkorlik va xayriya", "So'nggi yillari", "Merosi va zamonaviy ahamiyati", "Xulosa"],
        "slide_body": [
            "{topic} ning {sec} jihati mavzuning eng muhim qismlaridan biridir",
            "Ushbu davrda shaxsning shakllanishi, dunyoqarashi va faoliyati shakllangan",
            "Bu davrda olgan bilim va tajribalari keyingi barcha ishlariga asos bo'lgan",
            "Uning faoliyati davrida ko'plab o'zgarishlar va yangiliklar amalga oshirilgan",
            "Bugungi kunda bu mavzu keng o'rganilmoqda va avlodlarga saboq bo'lib xizmat qilmoqda",
            "Uning merosi kelajak avlodlar uchun ham yo'l ko'rsatuvchi yulduz bo'lib qoladi",
        ],
    },
    "ru": {
        "sections": ["Введение", "Историческое происхождение", "Теоретические основы", "Основная часть 1",
                     "Основная часть 2", "Основная часть 3", "Анализ", "Проблемы и решения",
                     "Заключение", "Список литературы"],
        "extra": "Дополнительная глава",
        "body": "По теме «{topic}» раздел «{sec}» — подробные сведения, факты, примеры и анализ. "
                "Данная глава раскрывает один из важнейших аспектов темы. Каждое предложение полное, содержательное и подробное.",
        "slide_sections": ["Введение и актуальность", "Историческое происхождение", "Молодость и обучение",
                           "Этапы деятельности", "Основные достижения", "Вклад в науку и культуру",
                           "Созидание и благотворительность", "Последние годы", "Наследие и современное значение", "Заключение"],
        "slide_body": [
            "Аспект «{sec}» темы «{topic}» является одним из важнейших",
            "В этот период формировалась личность, мировоззрение и деятельность",
            "Знания и опыт, полученные в этот период, стали основой всех последующих работ",
            "В период его деятельности произошло множество изменений и нововведений",
            "Сегодня эта тема широко изучается и служит уроком для будущих поколений",
            "Его наследие останется путеводной звездой и для будущих поколений",
        ],
    },
    "en": {
        "sections": ["Introduction", "Historical background", "Theoretical foundations", "Main part 1",
                     "Main part 2", "Main part 3", "Analysis", "Problems and solutions",
                     "Conclusion", "References"],
        "extra": "Additional chapter",
        "body": "On the topic «{topic}», the section «{sec}» provides detailed information, facts, examples and analysis. "
                "This chapter covers one of the most important aspects of the topic. Every sentence is complete, meaningful and detailed.",
        "slide_sections": ["Introduction and relevance", "Historical background", "Youth and education",
                           "Stages of activity", "Main achievements", "Contribution to science and culture",
                           "Creation and charity", "Later years", "Legacy and modern significance", "Conclusion"],
        "slide_body": [
            "The «{sec}» aspect of «{topic}» is one of the most important parts",
            "During this period the personality, worldview and activity were formed",
            "The knowledge and experience gained became the foundation for all later work",
            "Many changes and innovations took place during the period of activity",
            "Today this topic is widely studied and serves as a lesson for future generations",
            "The legacy will remain a guiding star for future generations as well",
        ],
    },
    "tr": {
        "sections": ["Giriş", "Tarihî köken", "Kuramsal temeller", "Ana bölüm 1",
                     "Ana bölüm 2", "Ana bölüm 3", "Analiz", "Sorunlar ve çözümler",
                     "Sonuç", "Kaynakça"],
        "extra": "Ek bölüm",
        "body": "«{topic}» konusunun «{sec}» bölümü — detaylı bilgiler, gerçekler, örnekler ve analizler. "
                "Bu bölüm konunun en önemli yönlerinden birini kapsar. Her cümle tam, anlamlı ve detaylıdır.",
        "slide_sections": ["Giriş ve güncellik", "Tarihî köken", "Gençlik ve eğitim",
                           "Faaliyet aşamaları", "Temel başarılar", "Bilim ve kültüre katkı",
                           "Yaratıcılık ve hayırseverlik", "Son yıllar", "Miras ve modern önem", "Sonuç"],
        "slide_body": [
            "«{topic}» konusunun «{sec}» yönü en önemli kısımlardan biridir",
            "Bu dönemde kişilik, dünya görüşü ve faaliyet şekillendi",
            "Bu dönemde kazanılan bilgi ve deneyim sonraki tüm çalışmaların temeli oldu",
            "Faaliyet dönemi boyunca birçok değişiklik ve yenilik gerçekleşti",
            "Bugün bu konu geniş çapta inceleniyor ve gelecek nesillere ders oluyor",
            "Miras gelecek nesiller için de yol gösterici bir yıldız olarak kalacak",
        ],
    },
    "de": {
        "sections": ["Einleitung", "Historischer Hintergrund", "Theoretische Grundlagen", "Hauptteil 1",
                     "Hauptteil 2", "Hauptteil 3", "Analyse", "Probleme und Lösungen",
                     "Fazit", "Literaturverzeichnis"],
        "extra": "Zusätzliches Kapitel",
        "body": "Zum Thema «{topic}» liefert der Abschnitt «{sec}» detaillierte Informationen, Fakten, Beispiele und Analysen. "
                "Dieses Kapitel behandelt einen der wichtigsten Aspekte des Themas. Jeder Satz ist vollständig, inhaltlich und detailliert.",
        "slide_sections": ["Einleitung und Aktualität", "Historischer Hintergrund", "Jugend und Ausbildung",
                           "Phasen der Tätigkeit", "Hauptleistungen", "Beitrag zu Wissenschaft und Kultur",
                           "Schaffen und Wohltätigkeit", "Späte Jahre", "Vermächtnis und moderne Bedeutung", "Fazit"],
        "slide_body": [
            "Der «{sec}»-Aspekt von «{topic}» ist einer der wichtigsten Teile",
            "In dieser Zeit formten sich Persönlichkeit, Weltanschauung und Wirken",
            "Die in dieser Zeit erworbenen Kenntnisse wurden zur Grundlage aller späteren Arbeiten",
            "Während der Wirkungszeit fanden viele Veränderungen und Neuerungen statt",
            "Heute wird dieses Thema umfassend erforscht und dient künftigen Generationen als Lehre",
            "Das Vermächtnis wird auch für künftige Generationen ein Leitstern bleiben",
        ],
    },
    "fr": {
        "sections": ["Introduction", "Contexte historique", "Fondements théoriques", "Partie principale 1",
                     "Partie principale 2", "Partie principale 3", "Analyse", "Problèmes et solutions",
                     "Conclusion", "Bibliographie"],
        "extra": "Chapitre supplémentaire",
        "body": "Sur le thème «{topic}», la section «{sec}» fournit des informations détaillées, des faits, des exemples et des analyses. "
                "Ce chapitre couvre l'un des aspects les plus importants du sujet. Chaque phrase est complète, significative et détaillée.",
        "slide_sections": ["Introduction et pertinence", "Contexte historique", "Jeunesse et formation",
                           "Étapes d'activité", "Réalisations principales", "Contribution à la science et à la culture",
                           "Création et charité", "Années tardives", "Héritage et signification moderne", "Conclusion"],
        "slide_body": [
            "L'aspect «{sec}» de «{topic}» est l'une des parties les plus importantes",
            "Pendant cette période, la personnalité, la vision du monde et l'activité se sont formées",
            "Les connaissances et l'expérience acquises sont devenues le fondement de tous les travaux ultérieurs",
            "De nombreux changements et innovations ont eu lieu pendant la période d'activité",
            "Aujourd'hui, ce sujet est largement étudié et sert de leçon aux générations futures",
            "L'héritage restera une étoile directrice pour les générations futures également",
        ],
    },
}

def _fb(lang):
    return FB.get(str(lang).lower(), FB["uz"])

def _fallback_text(service, topic, options, lang, bob_count=10):
    pages = int(options.get("pages", 10) or 10)
    fb = _fb(lang)
    sections = list(fb["sections"])
    while len(sections) < bob_count:
        sections.insert(len(sections)-2, f"{fb['extra']} {len(sections)-3}")
    parts = []
    for i, sec in enumerate(sections[:bob_count]):
        body = fb["body"].format(topic=topic, sec=sec.lower())
        parts.append(f"{sec}\n{body}\n{body}")
    return f"{topic}\n\n" + "\n\n".join(parts)

def _fallback_slides(topic, count, lang):
    fb = _fb(lang)
    secs = fb["slide_sections"]
    bodies = fb["slide_body"]
    out = []
    for i in range(count):
        sec = secs[i % len(secs)]
        b = bodies[i % len(bodies)].format(topic=topic, sec=sec.lower())
        content = [b] * 5
        out.append({
            "slide_number": i + 1,
            "title": sec,
            "content": content,
            "has_image": _is_image_slide(i, count),
            "image_prompt": _make_image_prompt(topic, i) if _is_image_slide(i, count) else None
            })
        _log(f"✅ Tayyor: {len(out)} slayd")
        return out, True
    
    _log("⚠️ API javobi yaroqsiz, zaxira versiya ishlatilmoqda")
    return _fallback_slides(topic, count, lang), False

def _extract_json(text):
    if not text:
        return None
    m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end+1])
        except Exception:
            pass
    return None

def _make_image_prompt(topic, idx):
    t = topic.lower()
    base = "historical figure, realistic, 8k"
    for uz, en in SEARCH_MAP.items():
        if uz in t:
            base = en
            break
    if idx == 0:
        return f"portrait of {base}, dignified pose, detailed, photorealistic, 8k"
    elif idx == 3:
        return f"{base} epic historical scene, cultural heritage, 8k"
    elif idx == 6:
        return f"{base} ancient architecture, monument, 8k"
    else:
        return f"{base} legacy, starry sky or sunset, inspirational, cinematic, 8k"

def _is_image_slide(idx, total):
    return idx in IMAGE_SLIDE_INDICES or idx == total - 1

async def search_images(query, count=5):
    """Rasm qidiradi — FAQAT MOS KELGANLARINI qabul qiladi."""
    q = re.sub(r'[^\w\s\']', ' ', str(query)).strip()
    if len(q) < 3:
        _log(f"[RASM] So'z juda qisqa: '{q}'")
        return []
    q_en = q
    
    for uz, en in SEARCH_MAP.items():
        if uz in q.lower():
            q_en = en
            _log(f"[RASM] Avtomatik: '{q}' → '{q_en}'")
            break

    # Moslik tekshiruvi uchun kalit so'zlar
    keywords = [w for w in q_en.lower().split() if len(w) > 2]
    # Umumiy keraksiz so'zlarni olib tashlash
    stop = {"portrait", "historical", "hero", "leader", "conqueror", "poet", "writer",
            "scholar", "astronomer", "city", "architecture", "culture", "landmark",
            "warrior", "prince", "scientist", "figure", "realistic", "8k", "photo"}
    keywords = [w for w in keywords if w not in stop]

    urls = []
    for search_q in [q_en, q, f"{q_en} portrait", f"{q_en} historical"]:
        if len(urls) >= count:
            break
        url = (
            f"https://pixabay.com/api/?key={PIXABAY_KEY}"
            f"&q={search_q.replace(' ', '+')}"
            f"&image_type=photo&orientation=horizontal&per_page=50&safesearch=true"
        )
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        continue
                    data = await resp.json()
        except Exception as e:
            _log(f"[RASM] Xato: {e}")
            continue

        for hit in data.get("hits", []):
            u = hit.get("webformatURL")
            if not u or u in urls:
                continue
            # ✅ MOSLIK TEKSHIRUVI: tags yoki title da kamida bitta kalit so'z bo'lishi shart
            tags = (hit.get("tags", "") + " " + hit.get("title", "")).lower()
            mos = sum(1 for kw in keywords if kw in tags)
            if mos == 0 and keywords:
                continue  # umuman mos kelmagan — o'tkazib yuboramiz
            urls.append(u)
            if len(urls) >= count:
                break

    urls = list(dict.fromkeys(urls))[:count]
    if not urls:
        _log(f"⚠️ '{q}' uchun mos rasm topilmadi — dekorativ rasm ishlatiladi")
    else:
        _log(f"📸 '{q}' → {len(urls)} ta MOS rasm topildi ✅")
    return urls

async def download_image(url, save_path):
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    with open(save_path, "wb") as f:
                        f.write(data)
                    try:
                        from PIL import Image
                        with Image.open(save_path) as img:
                            img.verify()
                    except Exception:
                        pass
                    return True
    except Exception as e:
        _log(f"[RASM] Yuklash xatosi: {e}")
    return False

def _extract_json(text):
    if not text:
        return None
    m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end+1])
        except Exception:
            pass
    return None

# ===== 6 til uchun fallback strukturaviy yorliqlar =====
FB = {
    "uz": {
        "sections": ["Kirish", "Tarixiy kelib chiqishi", "Nazariy asoslari", "Asosiy qism 1",
                     "Asosiy qism 2", "Asosiy qism 3", "Tahlil", "Muammolar va yechimlar",
                     "Xulosa", "Foydalanilgan adabiyotlar"],
        "extra": "Qo'shimcha bob",
        "body": "{topic} bo'yicha {sec} — batafsil ma'lumotlar, faktlar, misollar va tahlillar. "
                "Ushbu bob mavzuning muhim qismlaridan birini o'z ichiga oladi. Har bir gap to'liq, mazmunli va batafsil yozilgan.",
        "slide_sections": ["Kirish va dolzarblik", "Tarixiy kelib chiqishi", "Yoshlik va ta'lim",
                           "Faoliyat bosqichlari", "Asosiy yutuqlar", "Ilm-fan va madaniyatga hissasi",
                           "Bunyodkorlik va xayriya", "So'nggi yillari", "Merosi va zamonaviy ahamiyati", "Xulosa"],
        "slide_body": [
            "{topic} ning {sec} jihati mavzuning eng muhim qismlaridan biridir",
            "Ushbu davrda shaxsning shakllanishi, dunyoqarashi va faoliyati shakllangan",
            "Bu davrda olgan bilim va tajribalari keyingi barcha ishlariga asos bo'lgan",
            "Uning faoliyati davrida ko'plab o'zgarishlar va yangiliklar amalga oshirilgan",
            "Bugungi kunda bu mavzu keng o'rganilmoqda va avlodlarga saboq bo'lib xizmat qilmoqda",
            "Uning merosi kelajak avlodlar uchun ham yo'l ko'rsatuvchi yulduz bo'lib qoladi",
        ],
    },
    "ru": {
        "sections": ["Введение", "Историческое происхождение", "Теоретические основы", "Основная часть 1",
                     "Основная часть 2", "Основная часть 3", "Анализ", "Проблемы и решения",
                     "Заключение", "Список литературы"],
        "extra": "Дополнительная глава",
        "body": "По теме «{topic}» раздел «{sec}» — подробные сведения, факты, примеры и анализ. "
                "Данная глава раскрывает один из важнейших аспектов темы. Каждое предложение полное, содержательное и подробное.",
        "slide_sections": ["Введение и актуальность", "Историческое происхождение", "Молодость и обучение",
                           "Этапы деятельности", "Основные достижения", "Вклад в науку и культуру",
                           "Созидание и благотворительность", "Последние годы", "Наследие и современное значение", "Заключение"],
        "slide_body": [
            "Аспект «{sec}» темы «{topic}» является одним из важнейших",
            "В этот период формировалась личность, мировоззрение и деятельность",
            "Знания и опыт, полученные в этот период, стали основой всех последующих работ",
            "В период его деятельности произошло множество изменений и нововведений",
            "Сегодня эта тема широко изучается и служит уроком для будущих поколений",
            "Его наследие останется путеводной звездой и для будущих поколений",
        ],
    },
    "en": {
        "sections": ["Introduction", "Historical background", "Theoretical foundations", "Main part 1",
                     "Main part 2", "Main part 3", "Analysis", "Problems and solutions",
                     "Conclusion", "References"],
        "extra": "Additional chapter",
        "body": "On the topic «{topic}», the section «{sec}» provides detailed information, facts, examples and analysis. "
                "This chapter covers one of the most important aspects of the topic. Every sentence is complete, meaningful and detailed.",
        "slide_sections": ["Introduction and relevance", "Historical background", "Youth and education",
                           "Stages of activity", "Main achievements", "Contribution to science and culture",
                           "Creation and charity", "Later years", "Legacy and modern significance", "Conclusion"],
        "slide_body": [
            "The «{sec}» aspect of «{topic}» is one of the most important parts",
            "During this period the personality, worldview and activity were formed",
            "The knowledge and experience gained became the foundation for all later work",
            "Many changes and innovations took place during the period of activity",
            "Today this topic is widely studied and serves as a lesson for future generations",
            "The legacy will remain a guiding star for future generations as well",
        ],
    },
    "tr": {
        "sections": ["Giriş", "Tarihî köken", "Kuramsal temeller", "Ana bölüm 1",
                     "Ana bölüm 2", "Ana bölüm 3", "Analiz", "Sorunlar ve çözümler",
                     "Sonuç", "Kaynakça"],
        "extra": "Ek bölüm",
        "body": "«{topic}» konusunun «{sec}» bölümü — detaylı bilgiler, gerçekler, örnekler ve analizler. "
                "Bu bölüm konunun en önemli yönlerinden birini kapsar. Her cümle tam, anlamlı ve detaylıdır.",
        "slide_sections": ["Giriş ve güncellik", "Tarihî köken", "Gençlik ve eğitim",
                           "Faaliyet aşamaları", "Temel başarılar", "Bilim ve kültüre katkı",
                           "Yaratıcılık ve hayırseverlik", "Son yıllar", "Miras ve modern önem", "Sonuç"],
        "slide_body": [
            "«{topic}» konusunun «{sec}» yönü en önemli kısımlardan biridir",
            "Bu dönemde kişilik, dünya görüşü ve faaliyet şekillendi",
            "Bu dönemde kazanılan bilgi ve deneyim sonraki tüm çalışmaların temeli oldu",
            "Faaliyet dönemi boyunca birçok değişiklik ve yenilik gerçekleşti",
            "Bugün bu konu geniş çapta inceleniyor ve gelecek nesillere ders oluyor",
            "Miras gelecek nesiller için de yol gösterici bir yıldız olarak kalacak",
        ],
    },
    "de": {
        "sections": ["Einleitung", "Historischer Hintergrund", "Theoretische Grundlagen", "Hauptteil 1",
                     "Hauptteil 2", "Hauptteil 3", "Analyse", "Probleme und Lösungen",
                     "Fazit", "Literaturverzeichnis"],
        "extra": "Zusätzliches Kapitel",
        "body": "Zum Thema «{topic}» liefert der Abschnitt «{sec}» detaillierte Informationen, Fakten, Beispiele und Analysen. "
                "Dieses Kapitel behandelt einen der wichtigsten Aspekte des Themas. Jeder Satz ist vollständig, inhaltlich und detailliert.",
        "slide_sections": ["Einleitung und Aktualität", "Historischer Hintergrund", "Jugend und Ausbildung",
                           "Phasen der Tätigkeit", "Hauptleistungen", "Beitrag zu Wissenschaft und Kultur",
                           "Schaffen und Wohltätigkeit", "Späte Jahre", "Vermächtnis und moderne Bedeutung", "Fazit"],
        "slide_body": [
            "Der «{sec}»-Aspekt von «{topic}» ist einer der wichtigsten Teile",
            "In dieser Zeit formten sich Persönlichkeit, Weltanschauung und Wirken",
            "Die in dieser Zeit erworbenen Kenntnisse wurden zur Grundlage aller späteren Arbeiten",
            "Während der Wirkungszeit fanden viele Veränderungen und Neuerungen statt",
            "Heute wird dieses Thema umfassend erforscht und dient künftigen Generationen als Lehre",
            "Das Vermächtnis wird auch für künftige Generationen ein Leitstern bleiben",
        ],
    },
    "fr": {
        "sections": ["Introduction", "Contexte historique", "Fondements théoriques", "Partie principale 1",
                     "Partie principale 2", "Partie principale 3", "Analyse", "Problèmes et solutions",
                     "Conclusion", "Bibliographie"],
        "extra": "Chapitre supplémentaire",
        "body": "Sur le thème «{topic}», la section «{sec}» fournit des informations détaillées, des faits, des exemples et des analyses. "
                "Ce chapitre couvre l'un des aspects les plus importants du sujet. Chaque phrase est complète, significative et détaillée.",
        "slide_sections": ["Introduction et pertinence", "Contexte historique", "Jeunesse et formation",
                           "Étapes d'activité", "Réalisations principales", "Contribution à la science et à la culture",
                           "Création et charité", "Années tardives", "Héritage et signification moderne", "Conclusion"],
        "slide_body": [
            "L'aspect «{sec}» de «{topic}» est l'une des parties les plus importantes",
            "Pendant cette période, la personnalité, la vision du monde et l'activité se sont formées",
            "Les connaissances et l'expérience acquises sont devenues le fondement de tous les travaux ultérieurs",
            "De nombreux changements et innovations ont eu lieu pendant la période d'activité",
            "Aujourd'hui, ce sujet est largement étudié et sert de leçon aux générations futures",
            "L'héritage restera une étoile directrice pour les générations futures également",
        ],
    },
}

def _fb(lang):
    return FB.get(str(lang).lower(), FB["uz"])

def _fallback_text(service, topic, options, lang, bob_count=10):
    pages = int(options.get("pages", 10) or 10)
    fb = _fb(lang)
    sections = list(fb["sections"])
    while len(sections) < bob_count:
        sections.insert(len(sections)-2, f"{fb['extra']} {len(sections)-3}")
    parts = []
    for i, sec in enumerate(sections[:bob_count]):
        body = fb["body"].format(topic=topic, sec=sec.lower())
        parts.append(f"{sec}\n{body}\n{body}")
    return f"{topic}\n\n" + "\n\n".join(parts)

