"""Ai Slide Bot — asosiy ishga tushirish fayli.
Ishga tushirish: python run.py
"""
import db_firebase
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession

import config
import database as db
from handlers import user, creation, admin
from admin_web import start_web_thread

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bot")


async def _resolve_webapp_url(bot):
    """Mini App uchun public HTTPS manzil: WEBAPP_URL -> Render domeni -> webhook domeni.

    Telegram web_app tugmasi faqat https:// manzil bilan ko'rinadi, shuning uchun
    qo'lda sozlanmagan bo'lsa botning o'z webhook manzilidan domen olinadi.
    """
    if config.WEBAPP_URL:
        return config.WEBAPP_URL
    try:
        info = await bot.get_webhook_info()
        url = (info.url or "").strip()
    except Exception as e:
        log.warning("Webhook manzilini olib bo'lmadi: %s", e)
        return ""
    if not url.startswith("https://"):
        return ""
    origin = "/".join(url.split("/")[:3])
    config.WEBAPP_URL = origin.rstrip("/")
    log.info("Mini App manzili webhook domenidan olindi: %s", config.WEBAPP_URL)
    return config.WEBAPP_URL


async def _notify_admin(bot, text):
    try:
        if config.ADMIN_ID:
            await bot.send_message(int(config.ADMIN_ID), text)
    except Exception:
        pass


async def main():
    if not config.BOT_TOKEN:
        log.error("BOT_TOKEN muhit o'zgaruvchisi sozlanmagan. .env yoki hosting Environment Variables ichida kiriting.")
        return
    if not config.WEB_ADMIN_PASSWORD:
        log.warning("WEB_ADMIN_PASSWORD sozlanmagan: web-admin login vaqtincha yopiq bo'ladi.")
    await db.get_db()
    log.info("Database initialized: %s", config.DB_PATH)
    # Firebase-ga ulanish (agar kalit fayl bo'lsa)
    if db_firebase.db:
        log.info("Firebase ulandi: foydalanuvchilar va harakatlar saqlanadi")
    else:
        log.warning("Firebase ulanmadi — firebase_key.json yo'q")
    log.info("Database initialized: %s", config.DB_PATH)

    session = AiohttpSession(proxy=config.PROXY_URL) if config.PROXY_URL else None
    if session:
        log.info("Proxy ishlatilmoqda: %s", config.PROXY_URL)

    bot = Bot(token=config.BOT_TOKEN, session=session,
              default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(admin.router)
    dp.include_router(creation.router)
    dp.include_router(user.router)

    try:
        start_web_thread()
        log.info("Web admin server ishga tushirishga yuborildi (port=%s). Maxfiy parol logga chiqarilmaydi.", config.WEB_ADMIN_PORT)
    except Exception as e:
        log.warning("Web panel ishga tushmadi: %s", e)

    try:
        me = await bot.get_me()
    except Exception as e:
        log.error("Telegram'ga ulanib bo'lmadi: %s", e)
        log.error("YECHIM: VPN yoqing yoki config.py da PROXY_URL o'rnating.")
        return

    log.info("Bot ishga tushdi: @%s (id=%s). Admin: %s", me.username, me.id, config.ADMIN_ID)

    # Mini App: chat input yonidagi "Ilova" tugmasi
    await _resolve_webapp_url(bot)
    if config.WEBAPP_URL:
        try:
            from aiogram.types import BotCommand, MenuButtonWebApp, WebAppInfo
            await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(
                text=config.MINI_APP_TEXT,
                web_app=WebAppInfo(url=config.WEBAPP_URL + "/app"),
            ))
            await bot.set_my_commands([
                BotCommand(command="start", description="Boshlash"),
                BotCommand(command="app", description="📱 Ilova (Mini App)"),
                BotCommand(command="price", description="Narxlar"),
                BotCommand(command="balance", description="Balans"),
                BotCommand(command="buy", description="Balansni to'ldirish"),
                BotCommand(command="referral", description="Taklif qilish"),
                BotCommand(command="help", description="Yordam"),
            ])
            log.info("Mini App menyu tugmasi o'rnatildi: %s/app", config.WEBAPP_URL)
        except Exception as e:
            log.warning("Mini App menyu tugmasi o'rnatilmadi: %s", e)
            await _notify_admin(bot, (
                "⚠️ Mini App tugmasi o'rnatilmadi.\n"
                f"Manzil: {config.WEBAPP_URL}/app\n"
                f"Sabab: {e}\n\n"
                "Manzil public HTTPS bo'lishi shart (Render domeni yoki o'z domeningiz)."))
    else:
        log.warning("WEBAPP_URL sozlanmagan — Mini App tugmasi ko'rinmaydi.")
        await _notify_admin(bot, (
            "⚠️ Mini App tugmasi ko'rinmaydi: public HTTPS manzil yo'q.\n"
            "Render → Environment → WEBAPP_URL = https://<domen> qo'ying "
            "va qayta deploy qiling, keyin BotFather → Menu Button ga shu "
            "manzilning /app qismini yozing."))
    try:
        from texts import t
        try:
            _u = await db.get_user(config.ADMIN_ID)
            _alang = _u["lang"] if _u and _u["lang"] in ("uz","ru","en","tr","de","fr") else "uz"
        except Exception:
            _alang = "uz"
        await bot.send_message(config.ADMIN_ID, t("bot_started", _alang, port=config.WEB_ADMIN_PORT))
    except Exception:
        pass

    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Bot to'xtatildi.")
