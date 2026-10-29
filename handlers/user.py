from aiogram import Router, F, types
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
import config
import database as db
from texts import t, btn_all
from keyboards import (main_kb, bot_lang_kb, balance_kb, check_review_kb, services_all_kb)
from states import TopUp, Chat, Creation, Admin
from services import SERVICES, SUBSCRIPTION_PLANS, service_name

router = Router()

async def _lang(user_id):
    u = await db.get_user(user_id)
    return u["lang"] if u else "uz"

async def _award_referral_bonus(bot, user_id):
    """Referal bonus beradi — yangi foydalanuvchi til tanlaganda va /start da chaqiriladi."""
    try:
        u = await db.get_user(user_id)
        if not u: return
        ref_id = u["referred_by"]
        if not ref_id or ref_id == user_id or u["bonus_awarded"]:
            return
        bonus = await db.get_referral_bonus()
        if bonus <= 0: return
        await db.add_balance(ref_id, bonus)
        await db.add_referral_earned(ref_id, bonus)
        await db.update_user(user_id, bonus_awarded=1)
        print(f"[referral] 🎁 Bonus +{bonus} so'm → {ref_id} (taklif: {user_id})", flush=True)
        try:
            ref_lang = await _lang(ref_id)
            await bot.send_message(ref_id, t("referal_bonus_notify", ref_lang, bonus=bonus))
        except Exception:
            pass
    except Exception as e:
        print(f"[referral] bonus xato: {e}", flush=True)

async def _is_subscribed(bot, user_id):
    """Majburiy obuna tekshiruvi. True = obuna bo'lgan yoki kerak emas."""
    require_sub = (await db.get_setting("require_channel_sub",
        "1" if config.REQUIRE_CHANNEL_SUBSCRIPTION else "0")) == "1"
    if not require_sub:
        return True
    channel = await db.get_setting("channel_username", config.CHANNEL_USERNAME)
    if not channel or channel == "@channel":
        return True
    if user_id == config.ADMIN_ID:
        return True
    try:
        member = await bot.get_chat_member(channel, user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception:
        return False

async def _sub_message(bot, event, lang="uz"):
    """Obuna bo'lmagan foydalanuvchiga xabar."""
    channel = await db.get_setting("channel_username", config.CHANNEL_USERNAME)
    ch = channel.lstrip("@")
    text = t("subscribe_warning", lang, channel=channel)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("btn_channel_go", lang), url=f"https://t.me/{ch}")]])
    if isinstance(event, CallbackQuery):
        await event.message.answer(text, reply_markup=kb)
        await event.answer()
    else:
        await event.answer(text, reply_markup=kb)

# ===== Til tanlash (start da birinchi marta) =====
@router.callback_query(F.data.startswith("blang:"))
async def cb_bot_lang(call: CallbackQuery, state: FSMContext):
    from designs import ALL_LANGS
    lang_code = call.data.split(":")[1]
    if lang_code not in ALL_LANGS:
        lang_code = "uz"
    
    await db.update_user(call.from_user.id, lang=lang_code)
    await call.answer(t("lang_saved", lang_code))
    
    # Yangi foydalanuvchi til tanlagan paytda referal bonusini beramiz
    await _award_referral_bonus(call.bot, call.from_user.id)
    
    # Firebase: tilni yangilash
    try:
        from db_firebase import fb_add_user
        await fb_add_user(
            telegram_id=call.from_user.id,
            lang=lang_code
        )
    except: pass
    
    # Welcome xabarini yangi tilda ko'rsatish
    if not await _is_subscribed(call.bot, call.from_user.id):
        await _sub_message(call.bot, call, lang_code)
        return
    
    try:
        await call.message.answer(t("welcome", lang_code), reply_markup=main_kb(lang_code))
    except Exception:
        pass

@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, state: FSMContext):
    await state.clear()
    referred_by = None
    if command.args and command.args.startswith("ref"):
        try:
            referred_by = int(command.args.replace("ref", ""))
        except Exception:
            referred_by = None
    # 1. Foydalanuvchini bazaga saqlaymiz
    u = await db.ensure_user(message.from_user.id, message.from_user.username,
                             message.from_user.first_name, referred_by)
        # ===== Firebase-ga saqlash =====
    try:
        from db_firebase import fb_add_user, fb_log_action
        await fb_add_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            lang=u.get("lang", "uz") if u else "uz",
        )
        await fb_log_action(
            telegram_id=message.from_user.id,
            action_type="/start",
            topic=None,
            service_type="bot"
        )
    except Exception as _e:
        print(f"[FB] xato: {_e}", flush=True)
    # ===== Firebase tugadi =====
    from designs import ALL_LANGS
    lang = u["lang"] if u["lang"] in ALL_LANGS else "uz"

    # 2. Yangi foydalanuvchi bo'lsa — avval til tanlashni so'raymiz
    # (created_at yaqin bo'lsa yoki til birinchi marta so'ralsa)
    # Soddalik uchun: har doim start da til tugmasi ham bor, lekin birinchi marta til so'raladi
    # Yangi foydalanuvchi bo'lsa — avval til tanlashni so'raymiz
    try:
        lang_set = u["lang_set"] if u else 0
    except (KeyError, IndexError, TypeError):
        lang_set = 0
    if not lang_set:
        try:
            await db.update_user(message.from_user.id, lang_set=1)
        except Exception:
            pass
        await message.answer(t("choose_bot_lang", "uz"), reply_markup=bot_lang_kb())
        return

    # 3. Majburiy obuna tekshirish
    if not await _is_subscribed(message.bot, message.from_user.id):
        await _sub_message(message.bot, message, lang)
        return

    # 4. Referal bonus (qayta foydalanuvchilar uchun ham tekshiriladi)
    await _award_referral_bonus(message.bot, message.from_user.id)
    try:
        await message.answer(t("welcome", lang), reply_markup=main_kb(lang))
    except Exception:
        pass

# ===== Tilni o'zgartirish tugmasi =====
@router.message(F.text.contains("Tilni") | F.text.contains("язык") | F.text.contains("anguage") | F.text.contains("🌐"))
async def btn_change_lang(message: Message):
    await message.answer(t("choose_bot_lang", "uz"), reply_markup=bot_lang_kb())

@router.message(Command("help"))
async def cmd_help(message: Message):
    if not await _is_subscribed(message.bot, message.from_user.id):
        lang = await _lang(message.from_user.id)
        await _sub_message(message.bot, message, lang); return
    lang = await _lang(message.from_user.id)
    await message.answer(t("help_text", lang, support=config.SUPPORT_CHAT, admin=config.ADMIN_USERNAME))

@router.message(Command("reset"))
async def cmd_reset(message: Message, state: FSMContext):
    await state.clear()
    lang = await _lang(message.from_user.id)
    try:
        await message.answer(t("welcome", lang), reply_markup=main_kb(lang))
    except Exception:
        pass

@router.message(Command("price"))
async def cmd_price(message: Message):
    if not await _is_subscribed(message.bot, message.from_user.id):
        lang = await _lang(message.from_user.id)
        await _sub_message(message.bot, message, lang); return
    lang = await _lang(message.from_user.id)
    prices = await db.get_all_prices()
    lines = [f'{SERVICES[c]["emoji"]} {service_name(c, lang)} — {p} so\'m' for c, p in prices.items()]
    await message.answer(t("prices", lang, price_list="\n".join(lines)))

@router.message(Command("balance"))
async def cmd_balance(message: Message):
    uid = message.from_user.id
    # Menyu tugmasi /balance dan oldin bosilganda ham foydalanuvchi bazada bo'lishi kerak.
    # ensure_user INSERT OR IGNORE ishlatadi, mavjud foydalanuvchi ma'lumotlarini o'zgartirmaydi.
    u = await db.ensure_user(
        uid,
        message.from_user.username,
        message.from_user.first_name,
    )
    if not u:
        await message.answer("⚠️ Hisob ma'lumotlarini yuklab bo'lmadi. /start buyrug'ini yuborib qayta urinib ko'ring.")
        return
    lang = u["lang"] if u["lang"] in ("uz", "ru", "en", "tr", "de", "fr") else "uz"
    if not await _is_subscribed(message.bot, uid):
        await _sub_message(message.bot, message, lang)
        return
    # O'qishni yangilab olamiz; ensure_user dan keyin row yo'q bo'lsa ham qulamaymiz.
    u = await db.get_user(uid)
    if not u:
        await message.answer("⚠️ Hisob ma'lumotlari topilmadi. /start buyrug'ini yuborib qayta urinib ko'ring.")
        return
    orders = await db.order_count(uid)
    refs, earned = await db.referral_stats(uid)
    deposited = await db.total_deposited(uid)
    await message.answer(
        t("balance_full", lang, uid=uid, balance=u['balance'], bonus=u['bonus_balance'],
          orders=orders, refs=refs, deposited=deposited),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t("btn_topup", lang), callback_data="topup")]]))

@router.message(Command("buy"))
async def cmd_buy(message: Message, state: FSMContext):
    if not await _is_subscribed(message.bot, message.from_user.id):
        lang = await _lang(message.from_user.id)
        await _sub_message(message.bot, message, lang); return
    lang = await _lang(message.from_user.id)
    await state.set_state(TopUp.amount)
    await message.answer(t("enter_amount", lang, min=config.MIN_TOPUP))

@router.message(Command("referral"))
async def cmd_referral(message: Message, state: FSMContext = None):
    if not await _is_subscribed(message.bot, message.from_user.id):
        lang = await _lang(message.from_user.id)
        await _sub_message(message.bot, message, lang); return
    uid = message.from_user.id
    lang = await _lang(uid)
    me = await message.bot.me()
    link = f"https://t.me/{me.username}?start=ref{uid}"
    refs, earned = await db.referral_stats(uid)
    bonus = await db.get_referral_bonus()
    share_url = f"https://t.me/share/url?url={link}&text=AI%20study%20materials%20bot!"
    await message.answer(
        t("referral_info", lang, link=link, bonus=bonus, refs=refs, earned=earned),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=t("btn_share", lang), url=share_url)]]))

# ===== Asosiy menyu tugmalari — 3 tilda ham ishlaydi =====
_CREATE_WORDS = ["Yaratish", "Создать", "Создание", "Create", "Start creating", "Начать"]
_CHAT_WORDS = ["AI Chat", "ИИ Чат", "Чат", "Chat", "chat"]
_BALANCE_WORDS = ["Balans", "Баланс", "Balance", "balance"]
_REFERRAL_WORDS = ["Referal", "Реферал", "Referral", "referral"]
_HELP_WORDS = ["Yordam", "Помощь", "Help", "help"]

@router.message(F.text.contains("Yaratish") | F.text.contains("Создать") | F.text.contains("Create") | F.text.contains("Начать"))
async def btn_create(message: Message, state: FSMContext):
    if not await _is_subscribed(message.bot, message.from_user.id):
        lang = await _lang(message.from_user.id)
        await _sub_message(message.bot, message, lang); return
    lang = await _lang(message.from_user.id)
    await state.clear()
    await state.set_state(Creation.service)
    await message.answer(t("choose_service_msg", lang), reply_markup=services_all_kb(lang))

# ===== 💬 AI CHAT =====
@router.message(Command("chat"))
@router.message(F.text.contains("AI Chat") | F.text.contains("ИИ Чат") | F.text.contains("Chat") | F.text.contains("Чат"))
async def btn_chat(message: Message, state: FSMContext):
    if not await _is_subscribed(message.bot, message.from_user.id):
        lang = await _lang(message.from_user.id)
        await _sub_message(message.bot, message, lang); return
    lang = await _lang(message.from_user.id)
    await state.clear()
    await state.set_state(Chat.active)
    await message.answer(t("chat_start", lang))

@router.message(Chat.active)
async def chat_handle(message: Message, state: FSMContext):
    txt = message.text or ""
    lang = await _lang(message.from_user.id)
    # Asosiy menyu tugmasi bosilsa — chat rejimidan chiqish
    menu_words = _BALANCE_WORDS + _REFERRAL_WORDS + _CREATE_WORDS + _HELP_WORDS + _CHAT_WORDS + ["Tilni", "язык", "anguage"]
    if any(k.lower() in txt.lower() for k in menu_words):
        await state.clear()
        if any(k.lower() in txt.lower() for k in _BALANCE_WORDS):
            await cmd_balance(message); return
        if any(k.lower() in txt.lower() for k in _REFERRAL_WORDS):
            await cmd_referral(message, state); return
        if any(k.lower() in txt.lower() for k in _CREATE_WORDS):
            await btn_create(message, state); return
        if any(k.lower() in txt.lower() for k in _HELP_WORDS):
            await cmd_help(message); return
        if any(k.lower() in txt.lower() for k in _CHAT_WORDS):
            await btn_chat(message, state); return
        return
    from ai_api import chat_answer
    thinking = await message.answer(t("chat_thinking", lang))
    answer = await chat_answer(message.text, user_lang=lang)
    try:
        if answer:
            await thinking.edit_text(answer[:4000])
        else:
            await thinking.edit_text(t("chat_failed", lang))
    except Exception:
        if answer:
            await message.answer(answer[:4000])
        else:
            await message.answer(t("chat_failed", lang))

@router.message(F.text.contains("Balans") | F.text.contains("Баланс") | F.text.contains("Balance"))
async def btn_balance(message: Message):
    await cmd_balance(message)

@router.message(F.text.contains("Referal") | F.text.contains("Реферал") | F.text.contains("Referral"))
async def btn_referral(message: Message, state: FSMContext):
    await cmd_referral(message, state)

@router.message(F.text.contains("Yordam") | F.text.contains("Помощь") | F.text.contains("Help"))
async def btn_help(message: Message):
    await cmd_help(message)

# ===== Balans to'ldirish =====
@router.message(TopUp.amount)
async def topup_amount(message: Message, state: FSMContext):
    lang = await _lang(message.from_user.id)
    try:
        amount = int(message.text.strip())
    except Exception:
        await message.answer(t("invalid_amount", lang)); return
    if amount < config.MIN_TOPUP:
        await message.answer(t("min_amount_error", lang, min=config.MIN_TOPUP)); return
    await state.update_data(amount=amount)
    await state.set_state(TopUp.check_photo)
    p_type = await db.get_setting("payment_type")
    p_number = await db.get_setting("payment_number")
    if p_type and p_number:
        pay_text = f"{p_type}\n{p_number}"
    else:
        pay_text = await db.get_setting("payment_info", config.DEFAULT_PAYMENT_INFO)
    await message.answer(t("payment_info", lang, payment_info=pay_text, amount=amount))

@router.message(TopUp.check_photo, F.photo)
async def topup_check_photo(message: Message, state: FSMContext):
    lang = await _lang(message.from_user.id)
    data = await state.get_data()
    amount = data.get("amount", 0)
    photo_id = message.photo[-1].file_id
    check_id = await db.add_check(message.from_user.id, amount, photo_id)
    await state.clear()
    await message.answer(t("check_sent", lang))
    try:
        admin_lang = await _lang(config.ADMIN_ID)
        await message.bot.send_photo(config.ADMIN_ID, photo_id,
            caption=t("adm_check_caption", admin_lang, cid=check_id, uid=message.from_user.id, amount=amount) +
                    f"\n@{message.from_user.username or '-'}",
            reply_markup=check_review_kb(check_id, admin_lang))
    except Exception:
        pass

# ===== Callbacklar =====
@router.callback_query(F.data == "subs")
async def cb_subs(call: CallbackQuery):
    if not await _is_subscribed(call.bot, call.from_user.id):
        lang = await _lang(call.from_user.id)
        await _sub_message(call.bot, call, lang); return
    lang = await _lang(call.from_user.id)
    lines = [t("sub_plan_line", lang, name=p["name"], price=p["price"]) for p in SUBSCRIPTION_PLANS]
    await call.message.answer("\n\n".join(lines))
    await call.answer()

@router.callback_query(F.data == "topup")
async def cb_topup(call: CallbackQuery, state: FSMContext):
    if not await _is_subscribed(call.bot, call.from_user.id):
        lang = await _lang(call.from_user.id)
        await _sub_message(call.bot, call, lang); return
    lang = await _lang(call.from_user.id)
    await state.set_state(TopUp.amount)
    await call.message.answer(t("enter_amount", lang, min=config.MIN_TOPUP))
    await call.answer()

@router.callback_query(F.data == "cancel")
async def cb_cancel(call: CallbackQuery, state: FSMContext):
    await state.clear()
    lang = await _lang(call.from_user.id)
    await call.message.answer(t("cancelled", lang), reply_markup=main_kb(lang))
    await call.answer()
