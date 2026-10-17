"""Ai Slide Bot — asosiy ishga tushirish fayli.
Ishga tushirish: python run.py
"""
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

async def main():
    await db.get_db()
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
        log.info("Web admin: http://127.0.0.1:%s (parol: %s)", config.WEB_ADMIN_PORT, config.WEB_ADMIN_PASSWORD)
    except Exception as e:
        log.warning("Web panel ishga tushmadi: %s", e)

    try:
        me = await bot.get_me()
    except Exception as e:
        log.error("Telegram'ga ulanib bo'lmadi: %s", e)
        log.error("YECHIM: VPN yoqing yoki config.py da PROXY_URL o'rnating.")
        return

    log.info("Bot ishga tushdi: @%s (id=%s). Admin: %s", me.username, me.id, config.ADMIN_ID)
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
