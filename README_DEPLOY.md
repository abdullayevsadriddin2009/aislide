# Render.com + GitHub orqali doimiy ishlatish qo'llanmasi

## ⚠️ Eng muhim narsa
Render serverda **lokal AI API (127.0.0.1:31415) ishlamaydi**. Cloud AI API ishlating:
- OpenRouter (https://openrouter.ai) — bitta kalit bilan 100+ model
- OpenAI, Gemini, Anthropic — OpenAI-kompatibil endpoint

`AI_BASE_URL` va `AI_API_KEY` ni Render dashboard'da kiriting.

---

## 1-qadam: GitHub'ga yuklash
1. GitHub'da yangi repository yarating (xususiy — private tavsiya etiladi, chunki config'da kalitlar bo'lishi mumkin).
2. Kodni yuklang:
   ```bash
   git init
   git add .
   git commit -m "Ai Slide Bot"
   git branch -M main
   git remote add origin https://github.com/SIZNING_LOGININGIZ/repo_nomi.git
   git push -u origin main
   ```

## 2-qadam: Render'ga ulash
1. https://render.com → ro'yxatdan o'ting (GitHub bilan kirish).
2. **New → Web Service** → GitHub repo'ni tanlang.
3. Render avtomatik `render.yaml` ni o'qiydi.
4. **Environment Variables** ga quyilarni kiriting:
   - `BOT_TOKEN` — BotFather token
   - `ADMIN_ID` — sizning Telegram ID
   - `AI_BASE_URL` — cloud AI (masalan `https://openrouter.ai/api/v1`)
   - `AI_API_KEY` — cloud AI kaliti
   - `WEB_ADMIN_PASSWORD` — admin panel paroli
5. **Create Web Service** — build boshlanadi (~2-3 daqiqa).

## 3-qadam: Doimiy tirik tutish (free plan uchun)
Render free plan 15 daqiqa HTTP so'rovi bo'lmasa uxlab qoladi. Bot polling uxlatmaydi, lekin xavfsizlik uchun:
- https://uptimerobot.com (bepul) → yangi monitor → botning Render URL manzilini har 5 daqiqada ping qilsin.
- Yoki **Starter plan** ($7/oy) — hech qachon uxlamaydi.

## 4-qadam: Ma'lumotlar bazasi (ixtiyoriy)
Render'da fayl tizimi vaqtinchalik — har deployda SQLite DB qayta yoziladi. Saqlab qolish uchun:
- Render dashboard → Service → **Disks** → yangi disk ulang (masalan `/var/data`, 1 GB).
- `DATA_DIR=/var/data` env var qo'shing.

## Tekshirish
- Botga Telegram'da `/start` yuboring — javob bersa, ishlayapti.
- Admin panel: `https://sizning-serviceningiz.onrender.com` (parol: WEB_ADMIN_PASSWORD).

## Loglar
Render dashboard → Logs — barcha xatolar ko'rinadi.
