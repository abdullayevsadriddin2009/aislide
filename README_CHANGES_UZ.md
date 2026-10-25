# Yangilangan AI Slide Bot — o‘zgarishlar

## Yangi taqdimot generatori
- 3 dizayn: **Temuriylar (ko‘k/oltin)**, **Ilmiy tabiat (yashil)** va **Minimal premium**.
- Dizayn tanlovi slayd sonidan mustaqil. Barcha dizaynlar 5, 7, 10, 12, 15, 18, 20, 25 yoki 30 slayd yaratadi.
- Taqdimotda muqova, mazmun/reja, asosiy slaydlar va yakuniy xulosa/rahmat sahifasi bo‘ladi.
- Taqdimot generatoridagi barcha statik matnlar o‘zbek, rus, ingliz, turk, nemis va fransuz tillariga moslangan.

## Xizmatlar oldindan so‘raydigan ma’lumotlar
- Taqdimot: mavzu, fan, hujjat tili, slaydlar soni, dizayn va muallif.
- Referat, mustaqil ish, kurs ishi va diplom ishi: hajm, til, fan, muassasa, fakultet, kafedra/yo‘nalish, muallif va tekshiruvchi/rahbar.
- Insho, test, maqola va tezis: xizmatga tegishli hajm/so‘z/savol soni, til, fan va muallif.
- Hujjatlar DOCX va PDF tanlovini qo‘llab-quvvatlaydi (PDF konvertatsiyasi muhitda LibreOffice bo‘lishiga bog‘liq).

## Hujjat namunalariga moslash
- DOCX shriftlari Times New Roman, A4 sahifa va akademik chet maydonlari bilan tayyorlanadi.
- Titul varaqlari va kompakt sarlavhalar tanlangan tilga moslashtirildi.
- Yetishmayotgan generator yordamchi funksiyalari va test fallback savollari qo‘shildi.

## Maxfiy sozlamalar
Yangi versiyada maxfiy kalitlar kod ichida saqlanmaydi. Ishga tushirishdan oldin hostingda yoki `.env` faylida quyidagilarni sozlang:
`BOT_TOKEN`, `ADMIN_ID`, `AI_API_KEY`, `WEB_ADMIN_PASSWORD`, `WEB_ADMIN_SECRET_KEY`.

Oldingi versiyada kod ichida bo‘lgan token yoki API kalitlari oshkor bo‘lgan deb qaralishi kerak. BotFather va tegishli AI provayder orqali ularni yangilang. `.env` faylini Git orqali yuklamang.

## Sinov holati
Python sintaksisi va generatorlar uchun lokal sinovlar bajarilishi kerak. Telegram handlerlarini to‘liq ishga tushirish uchun `requirements.txt` dagi bog‘liqliklarni o‘rnating va haqiqiy, yangi muhit o‘zgaruvchilarini sozlang.
