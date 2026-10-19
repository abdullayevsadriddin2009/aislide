"""AI API — avval Groq, limit tugasa Cloudflare va boshqalarga avtomatik o'tadi.
Har bir API ichida bir nechta model. 6 til to'liq qo'llab-quvvatlanadi.
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
PIXABAY_KEY = os.getenv("PIXABAY_KEY", "")
IMAGE_SLIDE_INDICES = [0, 3, 6]

# === API ro'yxati — AVVAL GROQ, keyin qolganlari ===
API_LIST = [
    {"name": "Groq 1 (asosiy)", "base_url": "https://api.groq.com/openai/v1",
     "api_key": os.getenv("GROQ_KEY_1", ""), "type": "openai",
     "models": ["llama-3-8b-8192", "llama-3-70b-8192", "llama-3.1-8b-instruct",
                "llama-3.1-70b-instruct", "mixtral-8x7b-32768", "gemma2-9b-it"]},
    {"name": "Groq 2", "base_url": "https://api.groq.com/openai/v1",
     "api_key": os.getenv("GROQ_KEY_2", ""), "type": "openai",
     "models": ["llama-3-8b-8192", "llama-3-70b-8192", "llama-3.1-8b-instruct",
                "llama-3.1-70b-instruct", "mixtral-8x7b-32768", "gemma2-9b-it"]},
    {"name": "Cloudflare AI (zaxira)",
     "base_url": "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run",
     "account_id": os.getenv("CLOUDFLARE_ACCOUNT_ID", ""),
     "api_key": os.getenv("CLOUDFLARE_KEY", ""), "type": "cloudflare",
     "models": ["@cf/meta/llama-3-8b-instruct", "@cf/meta/llama-3.1-8b-instruct",
                "@cf/mistral/mistral-7b-instruct-v0.2", "@cf/google/gemma-7b-it-lora"]},
    {"name": "OpenRouter", "base_url": "https://openrouter.ai/api/v1",
     "api_key": os.getenv("OPENROUTER_KEY", ""), "type": "openai",
     "models": ["openai/gpt-3.5-turbo", "openai/gpt-4o-mini", "meta-llama/llama-3.1-8b-instruct"]},
    {"name": "Google AI", "base_url": "https://generativelanguage.googleapis.com/v1beta",
     "api_key": os.getenv("GOOGLE_KEY_1", ""), "type": "google",
     "models": ["gemini-1.5-flash", "gemini-1.5-flash-8b", "gemini-1.5-pro"]},
    {"name": "Local FreeLLMAPI", "base_url": AI_API_URL,
     "api_key": os.getenv("AI_API_KEY", ""), "type": "openai",
     "models": [AI_MODEL, "gpt-3.5-turbo", "llama3"]},
]

CURRENT_API_INDEX = 0
CURRENT_MODEL_INDEX = 0

def get_current_api(): return API_LIST[CURRENT_API_INDEX]
def get_current_model():
    api = get_current_api()
    return api["models"][CURRENT_MODEL_INDEX % len(api["models"])]

def switch_to_next_model() -> bool:
    global CURRENT_MODEL_INDEX
    api = get_current_api()
    CURRENT_MODEL_INDEX += 1
    if CURRENT_MODEL_INDEX >= len(api["models"]):
        CURRENT_MODEL_INDEX = 0
        _log(f"⚠️ {api['name']} da barcha modellar tugadi. Keyingi API ga o'tilmoqda...")
        return False
    _log(f"🔄 Model almashtirildi: {api['name']} → {get_current_model()}")
    return True

def switch_to_next_api():
    global CURRENT_API_INDEX, CURRENT_MODEL_INDEX
    CURRENT_API_INDEX = (CURRENT_API_INDEX + 1) % len(API_LIST)
    CURRENT_MODEL_INDEX = 0
    _log(f"➡️ Keyingi API: {get_current_api()['name']}")

def _log(msg): print(f"[AI_API] {msg}", flush=True)
def get_last_error(): return LAST_ERROR

# === Yordamchi ===
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

LANG_NAMES = {"uz": "o'zbek", "ru": "rus", "en": "english", "tr": "turkish", "de": "german", "fr": "french"}
def _lang_name(code): return LANG_NAMES.get(str(code).lower(), "o'zbek")

SEARCH_MAP = {
    "alisher navoiy": "Alisher Navoi portrait historical poet", "navoiy": "Alisher Navoi writer historical",
    "amir temur": "Amir Temur historical leader conqueror", "temur": "Amir Temur Timurid empire",
    "jaloliddin manguberdi": "Jaloliddin Manguberdi Khwarazmshah warrior hero", "manguberdi": "Jaloliddin Manguberdi medieval hero",
    "mirzo ulugbek": "Mirzo Ulugh Beg astronomer observatory Samarkand", "ulugbek": "Ulugh Beg Timurid scholar scientist",
    "ibn sino": "Avicenna Ibn Sina philosopher physician", "toshkent": "Tashkent city Uzbekistan architecture",
    "samarqand": "Samarkand Registan historical", "buxoro": "Bukhara historical Uzbekistan",
    "uzbekiston": "Uzbekistan culture landmark",
}

# === So'rov yuborish ===
async def _try_post(api, model, payload):
    global LAST_ERROR
    if not api["api_key"]:
        LAST_ERROR = f"Kalit kiritilmagan: {api['name']}"
        return None, None, LAST_ERROR
    try:
        if api["type"] == "google":
            url = f"{api['base_url']}/models/{model}:generateContent?key={api['api_key']}"
            data = {"contents": [{"parts": [{"text": payload["messages"][-1]["content"]}]}]}
            headers = {"Content-Type": "application/json"}
        elif api["type"] == "cloudflare":
            if not api.get("account_id"):
                LAST_ERROR = "Cloudflare Account ID kiritilmagan!"
                return None, None, LAST_ERROR
            url = api["base_url"].format(account_id=api["account_id"]) + f"/{model}"
            data = {"messages": payload["messages"], "max_tokens": payload.get("max_tokens", 4000),
                    "temperature": payload.get("temperature", 0.7)}
            headers = {"Authorization": f"Bearer {api['api_key']}", "Content-Type": "application/json"}
        else:
            url = f"{api['base_url']}/chat/completions"
            data = dict(payload); data["model"] = model
            headers = {"Authorization": f"Bearer {api['api_key']}", "Content-Type": "application/json"}

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=AI_TIMEOUT)) as session:
            async with session.post(url, headers=headers, json=data, timeout=AI_TIMEOUT) as resp:
                body = await resp.text()
                if resp.status == 200:
                    LAST_ERROR = None
                    try:
                        dj = json.loads(body)
                        if api["type"] == "cloudflare": text = dj["result"]["response"]
                        elif api["type"] == "google": text = dj["candidates"][0]["content"]["parts"][0]["text"]
                        else: text = dj["choices"][0]["message"]["content"]
                        return 200, text, None
                    except Exception as e:
                        LAST_ERROR = f"Javobni tahlil qilib bo'lmadi: {e}"
                        return resp.status, None, LAST_ERROR
                LAST_ERROR = f"HTTP {resp.status}: {body[:200]}"
                return resp.status, None, LAST_ERROR
    except Exception as e:
        LAST_ERROR = f"Xato: {type(e).__name__}: {e}"
        return None, None, LAST_ERROR

async def _chat_complete(prompt, system=None, max_tokens=16000):
    messages = [
        {"role": "system", "content": system or "Siz mutaxassis yordamchisiz. Javoblar to'liq, batafsil, faktlarga asoslangan bo'lsin. Hech qanday * # belgi ishlatmang."},
        {"role": "user", "content": prompt}
    ]
    payload = {"messages": messages, "temperature": 0.7, "max_tokens": max_tokens}
    start_api = CURRENT_API_INDEX
    while True:
        api = get_current_api(); model = get_current_model()
        if not api["api_key"]:
            _log(f"⏭️ {api['name']} — kalit yo'q, o'tkazib yuborildi")
            switch_to_next_api()
            if CURRENT_API_INDEX == start_api: break
            continue
        _log(f"🔍 Sinab ko'rilmoqda: {api['name']} | {model}")
        status, text, err = await _try_post(api, model, payload)
        if status == 200 and text:
            text = clean_ai_text(text); text = verify_facts(text)
            _log(f"✅ {api['name']} | {model} — javob olindi!")
            return text.strip()
        _log(f"❌ {api['name']} | {model} — {err}")
        if not switch_to_next_model():
            if CURRENT_API_INDEX == start_api: break
        await asyncio.sleep(0.3)
    _log("⚠️ BARCHA API va modellar ishlamadi!")
    return "⚠️ Hozir barcha manbalar ishlashdan to'xtadi. Iltimos, kalitlarni tekshiring va keyinroq urinib ko'ring."

async def chat_answer(question):
    return await _chat_complete(question, system="Siz do'stona, bilimdon AI yordamchisiz. Foydalanuvchi savollariga to'liq, batafsil javob bering. Hech qanday * # belgi ishlatmang.")

# === Hujjat generatsiyasi ===
async def generate(service, topic, options, lang="uz"):
    from services import SERVICES
    s = SERVICES.get(service, {}); name = s.get("name", service)
    pages = int(options.get("pages", 10) or 10); ln = _lang_name(lang)
    bob_count = max(8, pages); doc_chars = pages * 900
    prompt = (f"Topic: {topic}\nService: {name}\nLength: {pages} sahifa (kamida {doc_chars} belgi)\n\n"
              f"Faqat {ln} tilida yozing! Boshqa til aralashmasin.\n\n"
              f"Kamida {bob_count} bo'lim: Kirish → Asosiy qism → Tahlil → Xulosa. Faktlar, sanalar, raqamlar bilan.")
    result = await _chat_complete(prompt)
    if result and "⚠️" not in result: return result, True
    await asyncio.sleep(1)
    return _fallback_text(service, topic, options, lang, bob_count), False

def _is_image_slide(idx, total): return idx in IMAGE_SLIDE_INDICES or idx == total - 1

async def generate_slides_structured(topic, subject, lang, count):
    ln = _lang_name(lang)
    char_map = {5: 4000, 7: 5000, 10: 7000, 12: 8500, 15: 10000, 18: 11500, 20: 13000, 25: 18000, 30: 22000}
    target_chars = char_map.get(count, count * 750)
    system = f"Siz akademik kontent yozuvchisisiz. Faqat {ln} tilida yozing. Har slayd: sarlavha + 8-10 gap. Jami kamida {target_chars} belgi. Faqat JSON qaytaring."
    prompt = f"""{topic} mavzusida {count} ta slaydli taqdimot. Til: {ln}. Har slayd: sarlavha + 8-10 gap, faktlar bilan.
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
                        "image_prompt": _make_image_prompt(topic, i) if _is_image_slide(i, count) else None})
        _log(f"✅ Tayyor: {len(out)} slayd")
        return out, True
    _log("⚠️ API javobi yaroqsiz, zaxira ishlatilmoqda")
    return _fallback_slides(topic, count, lang), False

def _extract_json(text):
    if not text: return None
    m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    if m:
        try: return json.loads(m.group(1))
        except: pass
    s, e = text.find("["), text.rfind("]")
    if s != -1 and e > s:
        try: return json.loads(text[s:e+1])
        except: pass
    return None

def _make_image_prompt(topic, idx):
    t = topic.lower(); base = "historical figure, realistic, 8k"
    for uz, en in SEARCH_MAP.items():
        if uz in t: base = en; break
    if idx == 0: return f"portrait of {base}, dignified pose, detailed, photorealistic, 8k"
    elif idx == 3: return f"{base} epic historical scene, cultural heritage, 8k"
    elif idx == 6: return f"{base} ancient architecture, monument, 8k"
    else: return f"{base} legacy, starry sky or sunset, inspirational, cinematic, 8k"

async def search_images(query, count=5):
    q = re.sub(r'[^\w\s\']', ' ', str(query)).strip()
    if len(q) < 3: return []
    q_en = q
    for uz, en in SEARCH_MAP.items():
        if uz in q.lower(): q_en = en; break
    kws = [w for w in q_en.lower().split() if len(w) > 2 and w not in
           {"portrait","historical","hero","leader","conqueror","poet","writer","scholar","astronomer",
            "city","architecture","culture","landmark","warrior","prince","scientist","figure","realistic","8k","photo"}]
    urls = []
    for sq in [q_en, q, f"{q_en} portrait", f"{q_en} historical"]:
        if len(urls) >= count: break
        url = (f"https://pixabay.com/api/?key={PIXABAY_KEY}&q={sq.replace(' ','+')}"
               f"&image_type=photo&orientation=horizontal&per_page=50&safesearch=true")
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as s:
                async with s.get(url) as r:
                    if r.status != 200: continue
                    data = await r.json()
        except Exception as e:
            _log(f"[RASM] Xato: {e}"); continue
        for hit in data.get("hits", []):
            u = hit.get("webformatURL")
            if not u or u in urls: continue
            tags = (hit.get("tags","") + " " + hit.get("title","")).lower()
            if kws and not any(kw in tags for kw in kws): continue
            urls.append(u)
            if len(urls) >= count: break
    urls = list(dict.fromkeys(urls))[:count]
    _log(f"📸 '{q}' → {len(urls)} ta rasm")
    return urls

async def download_image(url, save_path):
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as s:
            async with s.get(url) as r:
                if r.status == 200:
                    with open(save_path, "wb") as f: f.write(await r.read())
                    return True
    except Exception as e:
        _log(f"[RASM] Yuklash xatosi: {e}")
    return False

# === API test funksiyasi (admin /testapi uchun) ===
async def test_api():
    results = []
    test_prompt = "Salom, faqat 'OK' deb javob bering."
    messages = [{"role": "user", "content": test_prompt}]
    payload = {"messages": messages, "temperature": 0.3, "max_tokens": 10}
    for api in API_LIST:
        if not api["api_key"]:
            results.append(f"❌ {api['name']}: kalit kiritilmagan"); continue
        ok = False; err_msg = ""
        for model in api["models"]:
            status, text, err = await _try_post(api, model, payload)
            if status == 200 and text:
                ok = True; err_msg = f"✅ ishladi ({model})"; break
            else:
                err_msg = str(err)[:80] if err else "noma'lum xato"
        results.append(f"{'✅' if ok else '❌'} {api['name']}: {err_msg}")
        await asyncio.sleep(0.3)
    return "\n".join(results)

# ===== 6 til uchun zaxira matn tizimi =====
FB = {
    "uz": {"sections": ["Kirish","Tarixiy kelib chiqishi","Nazariy asoslari","Asosiy qism 1","Asosiy qism 2","Asosiy qism 3","Tahlil","Muammolar va yechimlar","Xulosa","Foydalanilgan adabiyotlar"],
           "extra": "Qo'shimcha bob",
           "body": "{topic} bo'yicha {sec} — batafsil ma'lumotlar, faktlar, misollar va tahlillar. Ushbu bob mavzuning muhim qismlaridan birini o'z ichiga oladi. Har bir gap to'liq, mazmunli va batafsil yozilgan.",
           "slide_sections": ["Kirish va dolzarblik","Tarixiy kelib chiqishi","Yoshlik va ta'lim","Faoliyat bosqichlari","Asosiy yutuqlar","Ilm-fan va madaniyatga hissasi","Bunyodkorlik va xayriya","So'nggi yillari","Merosi va zamonaviy ahamiyati","Xulosa"],
           "slide_body": ["{topic} ning {sec} jihati mavzuning eng muhim qismlaridan biridir","Ushbu davrda shaxsning shakllanishi, dunyoqarashi va faoliyati shakllangan","Bu davrda olgan bilim va tajribalari keyingi barcha ishlariga asos bo'lgan","Uning faoliyati davrida ko'plab o'zgarishlar va yangiliklar amalga oshirilgan","Bugungi kunda bu mavzu keng o'rganilmoqda va avlodlarga saboq bo'lib xizmat qilmoqda","Uning merosi kelajak avlodlar uchun ham yo'l ko'rsatuvchi yulduz bo'lib qoladi"]},
    "ru": {"sections": ["Введение","Историческое происхождение","Теоретические основы","Основная часть 1","Основная часть 2","Основная часть 3","Анализ","Проблемы и решения","Заключение","Список литературы"],
           "extra": "Дополнительная глава",
           "body": "По теме «{topic}» раздел «{sec}» — подробные сведения, факты, примеры и анализ. Данная глава раскрывает один из важнейших аспектов темы. Каждое предложение полное, содержательное и подробное.",
           "slide_sections": ["Введение и актуальность","Историческое происхождение","Молодость и обучение","Этапы деятельности","Основные достижения","Вклад в науку и культуру","Созидание и благотворительность","Последние годы","Наследие и современное значение","Заключение"],
           "slide_body": ["Аспект «{sec}» темы «{topic}» является одним из важнейших","В этот период формировалась личность, мировоззрение и деятельность","Знания и опыт, полученные в этот период, стали основой всех последующих работ","В период его деятельности произошло множество изменений и нововведений","Сегодня эта тема широко изучается и служит уроком для будущих поколений","Его наследие останется путеводной звездой и для будущих поколений"]},
    "en": {"sections": ["Introduction","Historical background","Theoretical foundations","Main part 1","Main part 2","Main part 3","Analysis","Problems and solutions","Conclusion","References"],
           "extra": "Additional chapter",
           "body": "On the topic «{topic}», the section «{sec}» provides detailed information, facts, examples and analysis. This chapter covers one of the most important aspects of the topic. Every sentence is complete, meaningful and detailed.",
           "slide_sections": ["Introduction and relevance","Historical background","Youth and education","Stages of activity","Main achievements","Contribution to science and culture","Creation and charity","Later years","Legacy and modern significance","Conclusion"],
           "slide_body": ["The «{sec}» aspect of «{topic}» is one of the most important parts","During this period the personality, worldview and activity were formed","The knowledge and experience gained became the foundation for all later work","Many changes and innovations took place during the period of activity","Today this topic is widely studied and serves as a lesson for future generations","The legacy will remain a guiding star for future generations as well"]},
    "tr": {"sections": ["Giriş","Tarihî köken","Kuramsal temeller","Ana bölüm 1","Ana bölüm 2","Ana bölüm 3","Analiz","Sorunlar ve çözümler","Sonuç","Kaynakça"],
           "extra": "Ek bölüm",
           "body": "«{topic}» konusunun «{sec}» bölümü — detaylı bilgiler, gerçekler, örnekler ve analizler. Bu bölüm konunun en önemli yönlerinden birini kapsar. Her cümle tam, anlamlı ve detaylıdır.",
           "slide_sections": ["Giriş ve güncellik","Tarihî köken","Gençlik ve eğitim","Faaliyet aşamaları","Temel başarılar","Bilim ve kültüre katkı","Yaratıcılık ve hayırseverlik","Son yıllar","Miras ve modern önem","Sonuç"],
           "slide_body": ["«{topic}» konusunun «{sec}» yönü en önemli kısımlardan biridir","Bu dönemde kişilik, dünya görüşü ve faaliyet şekillendi","Bu dönemde kazanılan bilgi ve deneyim sonraki tüm çalışmaların temeli oldu","Faaliyet dönemi boyunca birçok değişiklik ve yenilik gerçekleşti","Bugün bu konu geniş çapta inceleniyor ve gelecek nesillere ders oluyor","Miras gelecek nesiller için de yol gösterici bir yıldız olarak kalacak"]},
    "de": {"sections": ["Einleitung","Historischer Hintergrund","Theoretische Grundlagen","Hauptteil 1","Hauptteil 2","Hauptteil 3","Analyse","Probleme und Lösungen","Fazit","Literaturverzeichnis"],
           "extra": "Zusätzliches Kapitel",
           "body": "Zum Thema «{topic}» liefert der Abschnitt «{sec}» detaillierte Informationen, Fakten, Beispiele und Analysen. Dieses Kapitel behandelt einen der wichtigsten Aspekte des Themas. Jeder Satz ist vollständig, inhaltlich und detailliert.",
           "slide_sections": ["Einleitung und Aktualität","Historischer Hintergrund","Jugend und Ausbildung","Phasen der Tätigkeit","Hauptleistungen","Beitrag zu Wissenschaft und Kultur","Schaffen und Wohltätigkeit","Späte Jahre","Vermächtnis und moderne Bedeutung","Fazit"],
           "slide_body": ["Der «{sec}»-Aspekt von «{topic}» ist einer der wichtigsten Teile","In dieser Zeit formten sich Persönlichkeit, Weltanschauung und Wirken","Die in dieser Zeit erworbenen Kenntnisse wurden zur Grundlage aller späteren Arbeiten","Während der Wirkungszeit fanden viele Veränderungen und Neuerungen statt","Heute wird dieses Thema umfassend erforscht und dient künftigen Generationen als Lehre","Das Vermächtnis wird auch für künftige Generationen ein Leitstern bleiben"]},
    "fr": {"sections": ["Introduction","Contexte historique","Fondements théoriques","Partie principale 1","Partie principale 2","Partie principale 3","Analyse","Problèmes et solutions","Conclusion","Bibliographie"],
           "extra": "Chapitre supplémentaire",
           "body": "Sur le thème «{topic}», la section «{sec}» fournit des informations détaillées, des faits, des exemples et des analyses. Ce chapitre couvre l'un des aspects les plus importants du sujet. Chaque phrase est complète, significative et détaillée.",
           "slide_sections": ["Introduction et pertinence","Contexte historique","Jeunesse et formation","Étapes d'activité","Réalisations principales","Contribution à la science et à la culture","Création et charité","Années tardives","Héritage et signification moderne","Conclusion"],
           "slide_body": ["L'aspect «{sec}» de «{topic}» est l'une des parties les plus importantes","Pendant cette période, la personnalité, la vision du monde et l'activité se sont formées","Les connaissances et l'expérience acquises sont devenues le fondement de tous les travaux ultérieurs","De nombreux changements et innovations ont eu lieu pendant la période d'activité","Aujourd'hui, ce sujet est largement étudié et sert de leçon aux générations futures","L'héritage restera une étoile directrice pour les générations futures également"]},
}

def _fb(lang): return FB.get(str(lang).lower(), FB["uz"])

def _fallback_text(service, topic, options, lang, bob_count=10):
    pages = int(options.get("pages", 10) or 10)
    fb = _fb(lang)
    sections = list(fb["sections"])
    while len(sections) < bob_count:
        sections.insert(len(sections)-2, f"{fb['extra']} {len(sections)-3}")
    parts = []
    for sec in sections[:bob_count]:
        body = fb["body"].format(topic=topic, sec=sec.lower())
        parts.append(f"{sec}\n{body}\n{body}")
    return f"{topic}\n\n" + "\n\n".join(parts)

def _fallback_slides(topic, count, lang):
    fb = _fb(lang)
    secs, bodies = fb["slide_sections"], fb["slide_body"]
    out = []
    for i in range(count):
        sec = secs[i % len(secs)]
        b = bodies[i % len(bodies)].format(topic=topic, sec=sec.lower())
        out.append({"slide_number": i+1, "title": sec, "content": [b]*5,
                    "has_image": _is_image_slide(i, count),
                    "image_prompt": _make_image_prompt(topic, i) if _is_image_slide(i, count) else None})
    return out
