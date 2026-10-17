# 🤖 Ai Slide Bot — @aislidebot analogi

AI orqali slayd, referat, kurs ishi, maqola va boshqa o'quv materiallarini yaratuvchi Telegram bot.
@aislidebotning to'liq analogi — tugmalar, xizmatlar, balans, referal, admin panel hammasi bilan.

## ✅ Imkoniyatlar
- **18 ta xizmat**: slayd, referat, mustaqil ish, kurs ishi, diplom, AI rasm, insho, krossvord, flesh-karta, test, rezyume, maqola, tezis, infografika, tinglash mashqlari, saralash o'yini, podkast, ovozli tabriknoma
- **3 til**: O'zbekcha, Русский, English
- **Balans tizimi**: so'mda hisob, to'ldirish (chek orqali admin tasdig'i bilan)
- **Referal tizimi**: do'st taklif qilish → to'lovdan foiz bonus (admin sozlaydi)
- **Obuna rejalar**: 3 ta paket (29k / 99k / 199k so'm, 30 kun)
- **Sozlamalar**: til, sahifa soni, premium rejim
- **Admin panel (bot ichida)**: statistika, broadcast, chek tasdiqlash, foydalanuvchi qidirish + balans tuzatish, referal foiz, to'lov rekvizitlari
- **Web admin panel**: brauzer orqali dashboard (http://IP:8080, parol: admin123)
- **AI API integratsiyasi**: `http://127.0.0.1:31415` ga ulanadi; API ishlamasa namunaviy kontent generatsiya qiladi (bot har doim ishlaydi)
- **Hozircha BEPUL rejim** (FREE_MODE=1) — keyinchalik /pull rejimga o'tkazish mumkin

## 🚀 Ishga tushirish
```bash
pip3 install -r requirements.txt
python3 run.py
```

## ⚙️ Konfiguratsiya
Barcha sozlamalar `config.py` faylida (yoki muhit o'zgaruvchilari orqali):
- `BOT_TOKEN` — bot tokeni (allaqachon o'rnatilgan)
- `ADMIN_ID` — admin Telegram ID (allaqachon o'rnatilgan)
- `AI_API_URL` / `AI_API_KEY` — mahalliy AI server (allaqachon o'rnatilgan)
- `FREE_MODE=1` — bepul rejim (pulli qilish uchun 0 qiling)
- `WEB_ADMIN_PORT=8080`, `WEB_ADMIN_PASSWORD=admin123`

## 📋 Buyruqlar
| Buyruq | Tavsif |
|---|---|
| /start | Botni ishga tushirish |
| /help | Yordam |
| /balance | Balans |
| /price | Narxlar |
| /buy | Balans to'ldirish |
| /chekyubor | Chek yuborish |
| /referral | Referal havola |
| /settings | Sozlamalar |
| /reset | Qayta ishga tushirish |
| /admin | Admin panel (faqat admin) |

## 📁 Loyiha tuzilishi
```
aislide_bot/
├── run.py              # asosiy fayl
├── config.py           # konfiguratsiya
├── services.py         # xizmatlar va narxlar
├── texts.py            # 3 tilli matnlar
├── states.py           # FSM state'lar
├── database.py         # SQLite baza
├── ai_api.py           # AI API + fallback generator
├── keyboards.py        # barcha tugmalar
├── admin_web.py        # Flask web admin panel
├── handlers/
│   ├── user.py         # foydalanuvchi handlerlari
│   ├── creation.py     # yaratish oqimi (FSM)
│   └── admin.py        # admin handlerlari
└── requirements.txt
```

## 🔄 Pulli rejimga o'tkazish
`config.py` da `FREE_MODE = "0"` qiling yoki muhit o'zgaruvchisi `FREE_MODE=0` belgilang. Shundan so'ng har bir buyurtma balansdan yechiladi.

## 🧪 AI API
`ai_api.py` avval `http://127.0.0.1:31415/generate` ga so'rov yuboradi (Bearer token bilan). Agar server javob bermasa, `generate_fallback()` namunaviy hujjat yaratadi. O'z API'ingizni ulash uchun `call_ai_api()` funksiyasini moslang.
