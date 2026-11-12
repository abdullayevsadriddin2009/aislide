import html
import random
import re
import time

from aiogram import Router, F, types
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
import config
import database as db
from texts import t, btn_all
from keyboards import (main_kb, mini_app_kb, bot_lang_kb, balance_kb, check_review_kb,
                       services_all_kb, chat_kb, chat_labels)
from states import TopUp, Chat, Creation, Admin
from services import SERVICES, SUBSCRIPTION_PLANS, service_name, ALL_LANGS

router = Router()


@router.message(Command("app"))
async def cmd_mini_app(message: Message):
    """Mini App'ni ochish: /app buyrug'i."""
    lang = await _lang(message.from_user.id)
    kb = mini_app_kb(lang)
    if kb is None:
        await message.answer("Mini App manzili sozlanmagan (WEBAPP_URL).")
        return
    await message.answer(
        "📱 <b>Mini App</b>\n\nHujjat va taqdimotlarni bot ichidagi qulay ilovada yaratishingiz mumkin.",
        reply_markup=kb)

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
        # sqlite3.Row da .get() yo'q — avval shu xato sababli Firebase'ga
        # foydalanuvchi umuman yozilmasdi (AttributeError jim yutilardi).
        _fb_lang = u["lang"] if u and u["lang"] else "uz"
        await fb_add_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            lang=_fb_lang,
            balance=u["balance"] if u else 0,
            bonus_balance=u["bonus_balance"] if u else 0,
            created_at=u["created_at"] if u else None,
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
@router.message(F.text.func(lambda text: _menu_action_for(text) == "lang"))
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

# ===== Asosiy menyu tugmalari — faqat aniq tugma matni bilan ishlaydi =====
def _normalize_button(text):
    """Case/space-insensitive form used to recognise real menu button presses."""
    return re.sub(r"\s+", " ", str(text or "").casefold()).strip(" .!?…") or ""


def _menu_actions():
    """Map every localized main-menu label to the action it triggers.

    Exact matching keeps normal chat questions working: a long sentence that
    merely contains the word "yaratish" must be answered by the AI, not treated
    as a menu button press.
    """
    cached = getattr(_menu_actions, "_cache", None)
    if cached is not None:
        return cached
    actions = {}
    pairs = (
        ("balance", "btn_balance"), ("referral", "btn_referral"),
        ("create", "btn_create"), ("help", "btn_help"),
        ("chat", "btn_chat"), ("lang", "btn_lang"),
    )
    for code in ALL_LANGS:
        for action, key in pairs:
            label = _normalize_button(t(key, code))
            if label:
                actions.setdefault(label, action)
    for label in ("Tilni o'zgartirish", "Tilni", "язык", "language", "🌐"):
        actions.setdefault(_normalize_button(label), "lang")
    _menu_actions._cache = actions
    return actions


def _menu_action_for(text):
    return _menu_actions().get(_normalize_button(text))


def _split_message(text, limit=3900):
    """Split a long AI answer on paragraph/sentence boundaries for Telegram."""
    text = str(text or "")
    if len(text) <= limit:
        return [text]
    parts = []
    while text:
        if len(text) <= limit:
            parts.append(text)
            break
        cut = text.rfind("\n\n", 0, limit)
        if cut < limit // 2:
            cut = text.rfind(". ", 0, limit)
        if cut < limit // 2:
            cut = text.rfind(" ", 0, limit)
        if cut <= 0:
            cut = limit
        parts.append(text[:cut].rstrip())
        text = text[cut:].lstrip()
    return [part for part in parts if part]


@router.message(F.text.func(lambda text: _menu_action_for(text) == "create"))
async def btn_create(message: Message, state: FSMContext):
    if not await _is_subscribed(message.bot, message.from_user.id):
        lang = await _lang(message.from_user.id)
        await _sub_message(message.bot, message, lang); return
    lang = await _lang(message.from_user.id)
    await state.clear()
    await state.set_state(Creation.service)
    await message.answer(t("choose_service_msg", lang), reply_markup=services_all_kb(lang))

# ===== 💬 AI CHAT =====
async def _send_message_draft(chat_id, draft_id, text):
    """Telegram `sendMessageDraft`: javob yozilayotgandek ko'rinadi (oqim).

    CdxChatBot.php dagi `sendMessageDraft` chaqirig'i bilan bir xil; metod
    mavjud bo'lmasa yoki xato qaytarsa (False, sabab) qaytadi va oddiy
    yuborish davom etadi.
    """
    import aiohttp
    token = config.BOT_TOKEN
    if not token:
        return False, "BOT_TOKEN kiritilmagan"
    url = f"https://api.telegram.org/bot{token}/sendMessageDraft"
    payload = {"chat_id": int(chat_id), "draft_id": int(draft_id), "text": str(text)[:4096]}
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.post(url, json=payload) as resp:
                data = await resp.json(content_type=None)
                if resp.status == 200 and isinstance(data, dict) and data.get("ok"):
                    return True, ""
                reason = (data or {}).get("description") if isinstance(data, dict) else ""
                return False, str(reason or f"HTTP {resp.status}")
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def _draft_callback(message):
    """`on_text` — matn kelganda 0.8 soniyada bir marta draftni yangilaydi."""
    try:
        import ai_pool
        enabled = ai_pool.chat_draft_stream()
    except Exception:
        enabled = True
    draft_id = random.randint(1, 2000000000)
    state = {"last": 0.0, "on": enabled}

    async def on_text(partial):
        if not state["on"]:
            return
        now = time.monotonic()
        if now - state["last"] < 0.8:
            return
        state["last"] = now
        ok, detail = await _send_message_draft(message.chat.id, draft_id, partial)
        try:
            import ai_pool
            if ok:
                ai_pool.note_draft_error("")
            else:
                state["on"] = False
                ai_pool.note_draft_error(detail)
                print(f"[chat] sendMessageDraft: {detail}", flush=True)
        except Exception:
            state["on"] = False

    return on_text


@router.message(Command("chat"))
@router.message(F.text.func(lambda text: _menu_action_for(text) == "chat"))
async def btn_chat(message: Message, state: FSMContext):
    if not await _is_subscribed(message.bot, message.from_user.id):
        lang = await _lang(message.from_user.id)
        await _sub_message(message.bot, message, lang); return
    lang = await _lang(message.from_user.id)
    await state.clear()
    await state.set_state(Chat.active)
    labels = chat_labels(lang)
    await message.answer(labels["start"], reply_markup=chat_kb(lang))


@router.callback_query(F.data == "chat:clear")
async def cb_chat_clear(call: CallbackQuery, state: FSMContext):
    """Suhbat tarixini tozalash — keyingi xabar yangi mavzu sifatida qabul qilinadi."""
    lang = await _lang(call.from_user.id)
    await db.clear_chat_history(call.from_user.id)
    await state.set_state(Chat.active)
    labels = chat_labels(lang)
    message = call.message
    if message is not None and getattr(message, "text", None):
        try:
            await message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
    await message.answer(labels["cleared"], reply_markup=chat_kb(lang))
    await call.answer()


@router.message(Command("newchat", "reset_chat"))
async def cmd_new_chat(message: Message, state: FSMContext):
    lang = await _lang(message.from_user.id)
    await db.clear_chat_history(message.from_user.id)
    await state.set_state(Chat.active)
    await message.answer(chat_labels(lang)["cleared"], reply_markup=chat_kb(lang))


@router.message(Chat.active)
async def chat_handle(message: Message, state: FSMContext):
    txt = (message.text or "").strip()
    lang = await _lang(message.from_user.id)

    # An exact menu button press leaves chat mode; everything else is a question.
    action = _menu_action_for(txt) if txt else None
    if action:
        await state.clear()
        if action == "balance":
            await cmd_balance(message); return
        if action == "referral":
            await cmd_referral(message, state); return
        if action == "create":
            await btn_create(message, state); return
        if action == "help":
            await cmd_help(message); return
        if action == "chat":
            await btn_chat(message, state); return
        if action == "lang":
            await btn_change_lang(message); return
        return

    if not txt:
        # Stickers, photos and other non-text messages still get an explanation
        # instead of an unanswered "thinking" bubble.
        label = chat_labels(lang)
        await message.answer(label["start"], reply_markup=chat_kb(lang))
        return

    from ai_api import chat_answer
    user_id = message.from_user.id
    # Oldingi xabarlar AI kontekstiga beriladi — shu bilan suhbat davom etadi.
    history = await db.get_chat_history(user_id, limit=16)
    thinking = await message.answer(t("chat_thinking", lang))
    try:
        answer = await chat_answer(txt, user_lang=lang, history=history,
                                   on_text=_draft_callback(message))
    except Exception as exc:
        # Never leave the user stuck on "O'ylayapman...": log and answer clearly.
        print(f"[chat] chat_answer failed: {type(exc).__name__}: {exc}", flush=True)
        answer = None
    if not answer or not str(answer).strip():
        # Admin panelda belgilangan xato matni bo'lsa — o'sha ko'rsatiladi.
        custom_error = ""
        try:
            import ai_pool
            custom_error = ai_pool.chat_error()
        except Exception:
            pass
        answer = custom_error or t("chat_failed", lang)
    answer = str(answer).strip()[:8000]

    try:
        await db.add_chat_message(user_id, "user", txt)
        await db.add_chat_message(user_id, "assistant", answer)
    except Exception as exc:
        print(f"[chat] history save failed: {exc}", flush=True)

    # The bot runs with parse_mode=HTML, so "<" or "&" inside an AI answer would
    # otherwise make Telegram reject the message and leave the user with no reply.
    # Long answers are split instead of being cut off at Telegram's 4096 limit.
    # AI javobidagi markdown Telegram HTML'ga o'giriladi (qalin, kod, ro'yxat,
    # havola). Formatlash rad etilsa, o'sha bo'lak oddiy matn bo'lib ketadi.
    from chat_format import md_to_tg_html, split_text
    try:
        import ai_pool
        use_markdown = ai_pool.chat_markdown()
    except Exception:
        use_markdown = True
    parts = split_text(answer, 3500) or [answer]
    chunks = [md_to_tg_html(part) if use_markdown else html.escape(part, quote=False)
              for part in parts]

    async def deliver(text, part, first=False):
        markup = chat_kb(lang) if first and len(chunks) == 1 else None
        if first:
            try:
                await thinking.edit_text(text, reply_markup=markup)
                return
            except Exception:
                pass
        try:
            await message.answer(text, reply_markup=markup if first else chat_kb(lang))
        except Exception:
            plain = html.escape(part, quote=False)
            try:
                if first:
                    await thinking.edit_text(plain, reply_markup=markup)
                else:
                    await message.answer(plain, reply_markup=chat_kb(lang))
            except Exception as exc:
                print(f"[chat] answer delivery failed: {type(exc).__name__}: {exc}", flush=True)

    for index, (chunk, part) in enumerate(zip(chunks, parts)):
        await deliver(chunk, part, first=(index == 0))


@router.message(F.text.func(lambda text: _menu_action_for(text) == "balance"))
async def btn_balance(message: Message):
    await cmd_balance(message)

@router.message(F.text.func(lambda text: _menu_action_for(text) == "referral"))
async def btn_referral(message: Message, state: FSMContext):
    await cmd_referral(message, state)

@router.message(F.text.func(lambda text: _menu_action_for(text) == "help"))
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
