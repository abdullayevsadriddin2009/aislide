AISLIDE BOT — RUNTIME HOTFIX

Ushbu patch 2 ta mavjud faylni almashtiradi:
1. handlers/admin.py
2. handlers/user.py

Tuzatishlar:
- Asosiy menyudagi "🎁 Referal" tugmasi admin panelidagi "🎁 Referal bonus" handleriga tushib qolmasligi uchun admin handler faqat ADMIN_ID va aniq admin tugmasiga bog'landi.
- /balance va balans tugmasi foydalanuvchini bazadan topa olmasa TypeError bilan to'xtamasligi uchun db.ensure_user() va himoya tekshiruvlari qo'shildi.

Qo'llash:
1. ZIP ni oching.
2. handlers/admin.py ni GitHub dagi handlers/admin.py bilan almashtiring.
3. handlers/user.py ni GitHub dagi handlers/user.py bilan almashtiring.
4. Ikkala faylni bitta commit bilan push qiling va Render redeployni kuting.

MUHIM: TelegramConflictError boshqa alohida bot nusxasi ham shu token bilan getUpdates chaqirayotganini bildiradi. Bu patch uni o'zi bartaraf etmaydi. Bot shu token bilan ishlayotgan boshqa Render service, lokal kompyuter, Replit/AlwaysData yoki eski hosting jarayonini to'xtating. Bir vaqtning o'zida faqat bitta polling nusxasi ishlasin.
