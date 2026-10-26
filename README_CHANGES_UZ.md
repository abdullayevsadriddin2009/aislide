# AI Slide Bot — tekshiruv va tuzatishlar (UZ)

## Nimalar tuzatildi

- DOCX xizmatlari uchun foydalanuvchi bergan `templates/*_IT.docx` namunalarining sahifa o‘lchami, chetlar, asosiy stil va mavjud format sozlamalari ishlatiladi. Namunalar ichida buzilgan yoki eski AI matnlari borligi sababli ularning matni tozalanib, hujjat tuzilishi qaytadan quriladi. Shuning uchun natija shablonning uslubiga mos, lekin har bir paragrafning joylashuvi pikselma-piksel bir xil bo‘lishi kafolatlanmaydi.
- PowerPoint uchun `templates/presentation_IT.pptx` mavzu va layout manbasi sifatida ishlatiladi; namuna slaydlardagi noto‘g‘ri mazmun o‘rniga yangi slaydlar tuziladi.
- Sahifa/slayd soni tanlovlari faqat `10`, `15`, `20` qilib cheklangan. Test xizmatida savollar soni 10/15/20; insho xizmatida so‘z hajmi 200/300/500 bo‘lib qoladi.
- Hujjat mazmuni va asosiy statik sarlavhalar tanlangan tilga moslanadi (o‘zbek, rus, ingliz, turk, nemis, fransuz). AI noto‘g‘ri til yoki takrorlangan matn qaytarsa, generator qayta so‘raydi; yaroqsiz natija xom holida hujjatga ko‘chirilmaydi.
- Esse uchun avval 5 bandli reja, keyin bo‘lim sarlavhalarisiz uzluksiz matn va xulosa berish oqimi saqlangan.
- Taqdimotga internet rasmlari bo‘lmaganda ham ichki zaxira vizual qo‘shiladi. Yuklangan rasm fayllari haqiqiy rasm ekanligi tekshiriladi; HTML/xato javobi rasm sifatida ishlatilmaydi.
- PowerPoint yaratishda 3 dizayn va 10/15/20 slayd variantlari bir-biridan mustaqil.
- `config.py` da `ADMIN_USERNAME` mavjud, `SUPPORT_CHAT` qiymati Render environment orqali o‘zgartirilishi mumkin.

## Tekshiruvlar

Lokal tekshiruvda `python -m compileall -q .` muvaffaqiyatli bajarildi. Generator testlari: 14 testdan 12 tasi o‘tdi, 2 tasi `aiogram`/`aiosqlite` lokal muhitda o‘rnatilmagani sababli skip qilindi. 10/15/20 sahifali referat, mustaqil ish, kurs ishi, diplom ishi, maqola va tezis DOCX fayllari LibreOffice orqali PDFga aylantirilib sahifalari sanalganda, sinov ma’lumotlari bilan mos ravishda 10/15/20 sahifa chiqdi. Taqdimot sinovlari 3 dizayn va 6 tilda 10/15/20 slayd sonini tekshirdi.

Bu lokal test natijalari Render’dagi haqiqiy AI provayderi, Telegram polling, tashqi rasm qidiruvi yoki barcha admin/to‘lov ssenariylari real vaqtda tekshirilganini anglatmaydi. “Xatosiz” ishlashni kafolatlab bo‘lmaydi; deploydan keyin botdagi oqimlarni amalda sinash kerak.

## Render/GitHub’ga joylash

1. ZIPni oching va loyiha fayllarini GitHub repozitoriyasiga birgalikda joylang. `templates/` papkasi va ichidagi 9 ta faylni albatta saqlang.
2. Render’dagi Environment variables’ni saqlab qoling: `BOT_TOKEN`, `ADMIN_ID`, `AI_API_KEY`, `AI_BASE_URL`, `WEB_ADMIN_PASSWORD`, `WEB_ADMIN_SECRET_KEY` va siz ishlatadigan boshqa parametrlar.
3. `.env` faylini GitHub’ga yuklamang. Faqat `.env.example` namuna sifatida bor.
4. Deploy tugagach, Telegram’da har bir til, 10/15/20 sahifali Word xizmati, 10/15/20 slaydli taqdimot, rasm va test xizmatlarini sinang.

## Muhim farq

Shablon fayllaridagi sahifa sozlamalari va uslublar qayta ishlatiladi, lekin shablon matnlari ichida noto‘g‘ri yoki eski namunaviy kontent bo‘lgani uchun aynan shu matnlar saqlanmaydi. Generator ularning o‘rniga toza, tanlangan tilga mos mazmun yozadi. Bu eski noto‘g‘ri matnni yangi hujjatga ko‘chirishdan afzal, ammo original fayl bilan pikselma-piksel nusxa bo‘lishi emas.
