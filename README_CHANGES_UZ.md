# Esse reja va matn tuzilmasi — tuzatish paketi

## Almashtiriladigan asosiy fayllar

GitHub loyihasida faqat quyidagi to‘rtta faylni almashtiring:

1. `ai_api.py`
2. `docx_generator.py`
3. `keyboards.py`
4. `handlers/creation.py`  (shu fayl `handlers` papkasida qoladi)

`tests/` ichidagi ikkita fayl — avtomatik tekshiruvlar uchun. `README_ESSAY_PLAN_FIX_UZ.md` — yo‘riqnoma.

## Nima tuzatildi?

- Esse hujjatining titul ma’lumotlaridan keyin `REJA` sarlavhasi va aniq 5 band chiqadi: kirish rejasi, asosiy qism uchun 3 band, xulosa rejasi.
- Rejadan keyin esse matni bevosita boshlanadi. Matn ichida `I. KIRISH QISMI`, `II. ASOSIY QISM`, `III. XULOSA QISMI` kabi bo‘lim sarlavhalari qo‘yilmaydi.
- AI javobida aralash til, juda qisqa javob yoki takrorlanadigan/g‘alati matn aniqlansa, bir marta qayta yozdiriladi. Qayta urinishi ham sifatsiz bo‘lsa, buzilgan matn o‘rniga shu tildagi ehtiyotkor zaxira matn qo‘llanadi.
- 200 so‘z tanlovi qo‘shildi. Kod avval so‘z sonini kamida 320 ga ko‘tarib yuborardi; endi 200 tanlansa, taxminiy taqsimot 40 so‘z kirish, 120 so‘z 3 ta asosiy paragrafga, 40 so‘z xulosaga bo‘ladi.
- Fan nomida `تاريخ` kabi keng tarqalgan arabcha nomlar tanlangan tilga tarjima qilinadi.

## Yuklash va tekshirish

`ai_api.py`, `docx_generator.py`, `keyboards.py`, `handlers/creation.py` fayllarini birgalikda almashtiring va bitta commit bilan GitHub’ga yuboring. `handlers/admin.py` va `handlers/user.py` ni bu patch uchun almashtirmang — oldingi referal/balans tuzatishlari saqlansin.

Lokal tekshiruvda DOCX xizmatlari uchun 3 ta test va esse sifat nazorati uchun 3 ta test muvaffaqiyatli o‘tdi. Taqdimot shablonlarining to‘liq testi ushbu tuzatish doirasiga kirmaydi.
