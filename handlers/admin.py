from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
import config
import database as db
from texts import t, btn_all  # btn_all qo'shildi (barcha tillardagi tugma matnlari uchun)
from states import Admin
from keyboards import admin_kb, main_kb, check_review_kb, payment_type_kb, price_kb, channel_sub_kb
from services import SERVICES, service_name

router = Router()

def is_admin(uid):
    return uid == config.ADMIN_ID

async def _admin_lang():
    """Admin tilini olish."""
    u = await db.get_user(config.ADMIN_ID)
    if u and u["lang"] in ("uz", "ru", "en", "tr", "de", "fr"):
        return u["lang"]
    return "uz"

async def _lang_safe(uid):
    u = await db.get_user(uid)
    if u and u["lang"] in ("uz", "ru", "en", "tr", "de", "fr"):
        return u["lang"]
    return "uz"

async def _menu(message: Message):
    lang = await _admin_lang()
    users = await db.user_count()
    total_bal = await db.total_balance()
    orders = await db.order_count()
    checks = await db.pending_check_count()
    ref_bonus = await db.get_referral_bonus()
    await message.answer(
        t("admin_panel", lang, users=users, balance=total_bal, orders=orders,
          checks=checks, ref_bonus=ref_bonus),
        reply_markup=admin_kb(lang))

@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        lang = await _lang_safe(message.from_user.id)
        await message.answer(t("not_admin", lang)); return
    await state.clear()
    await _menu(message)

@router.message(Command("testapi"))
async def cmd_testapi(message: Message):
    if not is_admin(message.from_user.id): return
    lang = await _admin_lang()
    await message.answer(t("api_checking", lang))
    from ai_api import test_api
    result = await test_api()
    await message.answer(t("api_result", lang, result=result))

# ===== Statistika =====
@router.message(F.text.contains("📊") | F.text.contains("Statistika") | F.text.contains("Статистика") | F.text.contains("Statistics"))
async def adm_stats(message: Message):
    if not is_admin(message.from_user.id): return
    lang = await _admin_lang()
    users = await db.user_count()
    total_bal = await db.total_balance()
    orders = await db.order_count()
    checks = await db.pending_check_count()
    ref_bonus = await db.get_referral_bonus()
    prices = await db.get_all_prices()
    plines = "\n".join(f'  {SERVICES[c]["emoji"]} {service_name(c, lang)}: {p} so\'m' for c, p in prices.items())
    await message.answer(
        t("adm_stats", lang, users=users, balance=total_bal, orders=orders,
          checks=checks, ref_bonus=ref_bonus, price_lines=plines))

# ===== Broadcast =====
@router.message(F.text.contains("Broadcast") | F.text.contains("Рассылка") | F.text.contains("Xabar yuborish"))
async def adm_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    lang = await _admin_lang()
    await state.set_state(Admin.broadcast)
    await message.answer(t("adm_broadcast_text", lang))

@router.message(Admin.broadcast)
async def adm_broadcast_send(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    lang = await _admin_lang()
    users = await db.all_users()
    count = 0
    for u in users:
        try:
            await message.bot.send_message(u["telegram_id"], message.text)
            count += 1
        except Exception:
            pass
    await state.clear()
    await message.answer(t("adm_broadcast_done", lang, count=count))

# ===== Cheklar =====
@router.message(F.text.contains("✅") | F.text.contains("Chek") | F.text.contains("Чек"))
async def adm_checks(message: Message):
    if not is_admin(message.from_user.id): return
    lang = await _admin_lang()
    checks = await db.pending_checks()
    if not checks:
        await message.answer(t("adm_no_checks", lang)); return
    for c in checks:
        try:
            await message.bot.send_photo(message.chat.id, c["photo_file_id"],
                caption=t("adm_check_caption", lang, cid=c["id"], uid=c["user_id"], amount=c["amount"]),
                reply_markup=check_review_kb(c["id"], lang))
        except Exception:
            await message.answer(f"#{c['id']}: {c['amount']}", reply_markup=check_review_kb(c["id"], lang))

@router.callback_query(F.data.startswith("chk:"))
async def adm_check_review(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        lang = await _lang_safe(call.from_user.id)
        await call.answer(t("not_admin", lang)); return
    lang = await _admin_lang()
    _, cid, action = call.data.split(":")
    cid = int(cid)
    check = await db.get_check(cid)
    if not check or check["status"] != "pending":
        await call.answer(t("adm_already_reviewed", lang)); return
        
    if action == "approve":
        await db.review_check(cid, "approved", call.from_user.id)
        await db.add_balance(check["user_id"], check["amount"])
        try:
            user_lang = await _lang_safe(check["user_id"])
            await call.bot.send_message(check["user_id"], t("topup_notify", user_lang, amount=check["amount"]))
        except Exception:
            pass
        # Tahrirlashda ham tilga moslashtiriladi
        approved_txt = t("btn_approve", lang).replace("✅ ", "")
        await call.message.edit_caption(caption=(call.message.caption or "") + f"\n\n✅ {approved_txt}")
        await call.answer(t("adm_approved", lang, amount=check["amount"]))
    else:
        await db.review_check(cid, "rejected", call.from_user.id)
        rejected_txt = t("btn_reject", lang).replace("❌ ", "")
        await call.message.edit_caption(caption=(call.message.caption or "") + f"\n\n❌ {rejected_txt}")
        await call.answer(t("adm_rejected", lang))

# ===== Foydalanuvchi + balans =====
@router.message(F.text.contains("👤") | F.text.contains("Foydalanuvchi") | F.text.contains("Пользователь") | F.text.contains("User"))
async def adm_users(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    lang = await _admin_lang()
    await state.set_state(Admin.user_lookup)
    await message.answer(t("adm_enter_user_id", lang))

@router.message(Admin.user_lookup)
async def adm_user_info(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    lang = await _admin_lang()
    try:
        uid = int(message.text.strip())
    except Exception:
        await message.answer(t("adm_invalid_id", lang)); await state.clear(); return
    u = await db.get_user(uid)
    if not u:
        await message.answer(t("adm_user_not_found", lang)); await state.clear(); return
    refs, earned = await db.referral_stats(uid)
    orders = await db.order_count(uid)
    await state.update_data(uid=uid)
    await state.set_state(Admin.balance_adjust)
    await message.answer(
        t("adm_user_info", lang, uid=uid, balance=u['balance'], bonus=u['bonus_balance'],
          refs=refs, orders=orders))

@router.message(Admin.balance_adjust)
async def adm_balance_adjust(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    lang = await _admin_lang()
    try:
        amt = int(message.text.strip())
    except Exception:
        await message.answer(t("adm_invalid_amount", lang)); await state.clear(); return
    data = await state.get_data()
    uid = data.get("uid")
    await db.add_balance(uid, amt)
    u = await db.get_user(uid)
    try:
        user_lang = await _lang_safe(uid)
        await message.bot.send_message(uid, t("balance_changed", user_lang, amount=amt, balance=u['balance']))
    except Exception:
        pass
    await state.clear()
    await message.answer(t("adm_balance_updated", lang, balance=u['balance']))

# ===== Narxlar =====
@router.message(F.text.contains("💲") | F.text.contains("Narx") | F.text.contains("Цен") | F.text.contains("Price"))
async def adm_prices(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    lang = await _admin_lang()
    prices = await db.get_all_prices()
    lines = "\n".join(f'{SERVICES[c]["emoji"]} {service_name(c, lang)}: <b>{p}</b>' for c, p in prices.items())
    await message.answer(t("adm_prices_current", lang, lines=lines), reply_markup=price_kb(lang))

@router.callback_query(F.data.startswith("setprice:"))
async def adm_set_price_cb(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        lang = await _lang_safe(call.from_user.id)
        await call.answer(t("not_admin", lang)); return
    lang = await _admin_lang()
    code = call.data.split(":")[1]
    s = SERVICES.get(code, {})
    cur = await db.get_price(code)
    await state.update_data(price_code=code)
    await state.set_state(Admin.set_price)
    await call.message.answer(t("adm_enter_new_price", lang, emoji=s.get("emoji",""),
                                name=service_name(code, lang), cur=cur))
    await call.answer()

@router.message(Admin.set_price)
async def adm_set_price_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    lang = await _admin_lang()
    try:
        amt = int(message.text.strip())
    except Exception:
        await message.answer(t("adm_invalid_amount", lang)); await state.clear(); return
    data = await state.get_data()
    code = data.get("price_code")
    await db.set_price(code, amt)
    await state.clear()
    await message.answer(t("adm_price_saved", lang, name=service_name(code, lang), amount=amt))

# ===== Referal bonus =====
@router.message(F.from_user.id == config.ADMIN_ID, F.text == "🎁 Referal bonus")
async def adm_ref(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    lang = await _admin_lang()
    cur = await db.get_referral_bonus()
    await state.set_state(Admin.set_ref_bonus)
    await message.answer(t("adm_enter_ref_bonus", lang, cur=cur))

@router.message(Admin.set_ref_bonus)
async def adm_ref_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    lang = await _admin_lang()
    try:
        amt = int(message.text.strip())
    except Exception:
        await message.answer(t("adm_invalid_amount", lang)); await state.clear(); return
    await db.set_referral_bonus(amt)
    await state.clear()
    await message.answer(t("adm_ref_bonus_saved", lang, amount=amt))

# ===== To'lov rekvizitlari =====
@router.message(F.text.contains("💳") | F.text.contains("To'lov") | F.text.contains("Платеж") | F.text.contains("Payment"))
async def adm_payment(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    lang = await _admin_lang()
    await state.set_state(Admin.payment_type)
    await message.answer(t("adm_choose_payment_type", lang), reply_markup=payment_type_kb(lang))

@router.message(Admin.payment_type)
async def adm_payment_type(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    lang = await _admin_lang()
    # 6 tildagi "Orqaga" tugmasini tekshirish
    if message.text in btn_all("btn_back") or "⬅️" in message.text:
        await state.clear(); await _menu(message); return
    p_type = message.text
    await state.update_data(payment_type=p_type)
    await state.set_state(Admin.payment_number)
    await message.answer(t("adm_enter_payment_number", lang, ptype=p_type),
                         reply_markup=types.ReplyKeyboardRemove())

@router.message(Admin.payment_number)
async def adm_payment_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    lang = await _admin_lang()
    data = await state.get_data()
    p_type = data.get("payment_type", "Card")
    p_number = message.text.strip()
    await db.set_setting("payment_type", p_type)
    await db.set_setting("payment_number", p_number)
    await db.set_setting("payment_info", f"{p_type}\n{p_number}")
    await state.clear()
    await message.answer(t("adm_payment_saved", lang, ptype=p_type, pnumber=p_number),
                         reply_markup=admin_kb(lang))

# ===== Majburiy kanal obunasi =====
@router.message(F.text.contains("Majburiy") | F.text.contains("Обязательная") | F.text.contains("Subscription"))
async def adm_channel(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    lang = await _admin_lang()
    require_sub = await db.get_setting("require_channel_sub", "0")
    channel = await db.get_setting("channel_username", "@channel")
    status = t("adm_channel_on", lang) if require_sub == "1" else t("adm_channel_off", lang)
    await message.answer(t("adm_channel_status", lang, status=status, channel=channel),
                         reply_markup=channel_sub_kb(lang))

@router.callback_query(F.data.startswith("chsub:"))
async def adm_channel_cb(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        lang = await _lang_safe(call.from_user.id)
        await call.answer(t("not_admin", lang)); return
    lang = await _admin_lang()
    action = call.data.split(":")[1]
    if action == "on":
        await db.set_setting("require_channel_sub", "1")
        await call.message.edit_text(t("adm_channel_turned_on", lang))
    elif action == "off":
        await db.set_setting("require_channel_sub", "0")
        await call.message.edit_text(t("adm_channel_turned_off", lang))
    elif action == "set":
        await state.set_state(Admin.set_channel)
        await call.message.answer(t("adm_enter_channel", lang))
    await call.answer()

@router.message(Admin.set_channel)
async def adm_channel_save(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    lang = await _admin_lang()
    ch = message.text.strip()
    if not ch.startswith("@"):
        ch = "@" + ch
    await db.set_setting("channel_username", ch)
    await state.clear()
    await message.answer(t("adm_channel_saved", lang, channel=ch), reply_markup=admin_kb(lang))

# ===== Orqaga =====
@router.message(F.text.in_(btn_all("btn_back")) | F.text.contains("⬅️"))
async def adm_back(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await state.clear()
    lang = await _lang_safe(message.from_user.id)
    await message.answer(t("main_menu", lang), reply_markup=main_kb(lang))
