# TIL TIZIMI YANGILANDI — 3 til (UZ / RU / EN)

## O'zgartirilgan fayllar:

1. **texts.py** — FAQAT 3 til (uz, ru, en). 80+ yangi kalit qo'shildi (tugmalar, admin panel, xabarlar).
   `t(key, lang, **kwargs)` funksiyasi saqlandi.

2. **keyboards.py** — BARCHA tugmalar endi `t()` orqali tilga bog'liq.
   `lang` parametri endi haqiqatan ishlatiladi (avval umuman ishlatilmayotgan!).
   Yangi: `bot_lang_kb()` — bot tilini tanlash, `channel_sub_kb()`.

3. **services.py** — Har bir xizmat uchun `name_uz`, `name_ru`, `name_en`.
   `service_name(code, lang)` funksiyasi qo'shildi.

4. **designs.py** — Dizayn nomlari 3 tilda (`name_uz/ru/en`).
   Fanlar (SUBJECTS) kalit tizimiga o'tkazildi — `subject_name(key, lang)`.
   Tillar ro'yxati 3 taga qisqartirildi. `detect_subject_key()`, `lang_full_name()` qo'shildi.

5. **handlers/user.py** — 
   - `/start` da YANGI FOYDALANUVCHI uchun avval til tanlash so'raladi!
   - "🌐 Tilni o'zgartirish" tugmasi qo'shildi (asosiy menyuda)
   - Barcha qattiq yozilgan o'zbekcha matnlar `t()` orqali almashtirildi
   - Tugma filterlari 3 tilda ham ishlaydi (Yaratish/Создать/Create)

6. **handlers/creation.py** — Barcha matnlar tilga bog'liq.
   Fayl nomlari: `presentation_`, `essay_`, `coursework_` va h.k. (tilga ko'ra).
   Fan/dizayn/til nomlari UI tilida ko'rsatiladi.

7. **handlers/admin.py** — Admin panel endi ADMINNING o'z tilida ishlaydi!
   (avval har doim o'zbekcha edi). Foydalanuvchiga yuboriladigan xabarlar ham
   foydalanuvchi tilida bo'ladi.

8. **admin_web.py** — Veb-panel to'liq INGLIZ tiliga o'tkazildi.

9. **pptx_generator.py / docx_generator.py** — Footer "Yaratildi:" endi
   hujjat tilida (Yaratildi / Создано / Created by).

10. **database.py** — `lang_set` ustuni uchun migratsiya qo'shildi.

11. **ai_api.py** — LANG_NAMES 3 tilga qisqartirildi.

12. **run.py** — Bot ishga tushgan xabari admin tilida yuboriladi.

## Ishlatish:
- Eski `.pyc` fayllarni O'CHIRING: `rm -rf __pycache__ handlers/__pycache__`
- Eski bazada til o'zgarmaydi — yangi foydalanuvchilar til tanlaydi.
- Joriy foydalanuvchilar "🌐 Tilni o'zgartirish" tugmasi orqali tilni almashtira oladi.

---

# VERSIYA 2.0 — 6 TIL + YANGI SLAYD SHABLONI (Amir Temur / Hujayra)

## Asosiy o'zgarishlar:
1. **6 til** — bot interfeysi va hujjatlar: 🇺🇿 uz / 🇷🇺 ru / 🇬🇧 en / 🇹🇷 tr / 🇩🇪 de / 🇫🇷 fr.
   - `texts.py` — tr/de/fr lug'atlar qo'shildi, `t()` fallback zanjiri: lang → en → uz → kalit.
   - `designs.py` — `LANGUAGES`, `LANG_NAMES_FULL`, `SUBJECTS`, dizayn nomlari 6 tilda. `ALL_LANGS` konstanta.
   - `services.py` — 9 xizmat nomi 6 tilda. `service_name()` fallback.
   - `keyboards.py` — `bot_lang_kb()` 6 tugma (3×2). `languages_kb` avtomatik 2 qator.
   - `handlers/creation.py`, `handlers/user.py`, `handlers/admin.py`, `run.py` — til tekshiruvi 6 tilga kengaytirildi.
   - `ai_api.py` — `LANG_NAMES` 6 tilga kengaytirildi.

2. **pptx_generator.py — to'liq qayta yozildi** (namunaviy `Amir_Temur.pptx` va `Hujayra.pptx` fayllariga 1:1 mos):
   - 16:9 (13.333×7.5 dyuym). Sarlavha: **Playfair Display** qalin. Matn: **Noto Sans, 15pt**.
   - 2 tema avtomatik tanlanadi: fan (biologiya/fizika/kimyo/matematika/it/tibbiyot) → 🌿 yashil (#1B4332 + #4ADE80); qolganlari → 🏛️ to'q ko'k+oltin (#1B2A41 + #C9A227).
   - Tuzilma: 1 muqova + 1 mundarija + (N−3) kontent + 1 yakuniy = N. 10/15/20/25 slayd to'liq qo'llab-quvvatlanadi.
   - Kontent slaydlari 6 xil layout navbat bilan (rasm+matn, keng rasm+ro'yxat, 2 ustun matn, 3×2 faktlar paneli, 4 bosqichli timeline+solishtirma, jadval) — **bo'sh joy qolmaydi** (yetishmaydigan qatorlar mavzuga mos to'ldiriladi).
   - Rasm yo'q bo'lsa — gradient dekor avtomatik yaratiladi.

3. **docx_generator.py** — o'zgartirilmadi (allaqachon 6 til + 8 xizmat shabloni: referat/mustaqil/kurs/diplom/insho/test/maqola/tezis, 📌 ta'rif / 🛡 maslahat / 📊 statistika / 📜 iqtibos / 💡 xulosa bloklari bilan).

4. **Malumotlar tekshiruvi** — `ai_api.verify_facts()` saqlandi (API orqali olingan ma'lumotlarni 100% to'g'rilash uchun).

## O'rnatish:
- Eski `.pyc` fayllarni o'chiring: `rm -rf __pycache__ handlers/__pycache__`
- `pip install -r requirements.txt`
- `python3 run.py`


---

# VERSIYA 2.1 — Test formati + Til sofligi
1. **Test/Quiz formatidan to'g'ri javob belgisi olib tashlandi** — variantlar (A/B/C/D) oddiy chiqadi, hech qayerda (✓) belgilangan bo'lmaydi. Hujjat oxirida (alohida sahifada) **Javoblar kaliti va izohlar** bo'limi: 1-A, 2-B, ... + izoh. AI matni avtomatik parse qilinadi.
2. **Til aralashuvi tuzatildi** — barcha xizmatlardagi fallback matnlardan o'zbekcha olib tashlandi. Qaysi til tanlansa sof o'sha tilda chiqadi. ai_api.py slayd to'ldiruvchi qatorlari ham tilga moslandi.
