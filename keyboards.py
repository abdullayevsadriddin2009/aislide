from aiogram.types import (ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton)
from texts import t
from services import SERVICES, service_name
from designs import DESIGNS, SLIDE_COUNTS, SUBJECT_KEYS, subject_name, design_name, LANGUAGES

# ===== Asosiy menyu =====
def main_kb(lang="uz"):
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=t("btn_create", lang))],
        [KeyboardButton(text=t("btn_chat", lang)), KeyboardButton(text=t("btn_balance", lang))],
        [KeyboardButton(text=t("btn_referral", lang)), KeyboardButton(text=t("btn_help", lang))],
        [KeyboardButton(text=t("btn_lang", lang))],
    ], resize_keyboard=True)

# ===== Admin menyu — tugmalarda 3 til kalit so'zlari bor (filter ishlashi uchun) =====
def admin_kb(lang="uz"):
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📊 Statistika"), KeyboardButton(text="📢 Broadcast")],
        [KeyboardButton(text="✅ Cheklar"), KeyboardButton(text="👤 Foydalanuvchi")],
        [KeyboardButton(text="💲 Narxlar"), KeyboardButton(text="🎁 Referal bonus")],
        [KeyboardButton(text="💳 To'lov rekvizitlari"), KeyboardButton(text="📢 Majburiy obuna")],
        [KeyboardButton(text=t("btn_back", lang))],
    ], resize_keyboard=True)

# ===== To'lov turi tanlash =====
def payment_type_kb(lang="uz"):
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=t("pay_humo", lang)), KeyboardButton(text=t("pay_uzcard", lang))],
        [KeyboardButton(text=t("pay_bank", lang)), KeyboardButton(text=t("pay_visa", lang))],
        [KeyboardButton(text=t("btn_back", lang))],
    ], resize_keyboard=True)

# ===== Balans =====
def balance_kb(lang="uz"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("btn_topup", lang), callback_data="topup")],
        [InlineKeyboardButton(text=t("btn_subs", lang), callback_data="subs")],
    ])

# ===== Bot tilini tanlash (start da) — 6 TIL =====
def bot_lang_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="blang:uz"),
         InlineKeyboardButton(text="🇷🇺 Русский", callback_data="blang:ru"),
         InlineKeyboardButton(text="🇬🇧 English", callback_data="blang:en")],
        [InlineKeyboardButton(text="🇹🇷 Türkçe", callback_data="blang:tr"),
         InlineKeyboardButton(text="🇩🇪 Deutsch", callback_data="blang:de"),
         InlineKeyboardButton(text="🇫🇷 Français", callback_data="blang:fr")],
    ])

# ===== Hujjat tilini tanlash (yaratishda) =====
def languages_kb(lang="uz"):
    rows = []
    row = []
    for code, name in LANGUAGES:
        row.append(InlineKeyboardButton(text=name, callback_data=f"lng:{code}"))
        if len(row) == 3:
            rows.append(row); row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ===== Barcha xizmatlar =====
def services_all_kb(lang="uz"):
    rows = []
    for code, s in SERVICES.items():
        rows.append([InlineKeyboardButton(text=f'{s["emoji"]} {service_name(code, lang)}', callback_data=f"svc:{code}")])
    rows.append([InlineKeyboardButton(text=t("btn_cancel", lang), callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ===== Parametr (pages/questions) =====
def option_kb_for(service, lang="uz"):
    s = SERVICES.get(service, {})
    ot = s.get("option_type", "pages")
    rows = []
    if ot == "pages":
        for v in [6, 10, 15, 20, 30]:
            rows.append([InlineKeyboardButton(text=f"📄 {t('pages_label', lang, n=v)}", callback_data=f"opt:pages:{v}")])
    elif ot == "questions":
        for v in [10, 20, 30, 50]:
            rows.append([InlineKeyboardButton(text=f"✅ {t('questions_label', lang, n=v)}", callback_data=f"opt:questions:{v}")])
    rows.append([InlineKeyboardButton(text=t("btn_cancel", lang), callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def option_label(service, options, lang="uz"):
    s = SERVICES.get(service, {})
    ot = s.get("option_type", "pages")
    if ot == "pages":
        return t("pages_label", lang, n=options.get("pages", 10))
    if ot == "questions":
        return t("questions_label", lang, n=options.get("questions", 10))
    return "—"

# ===== Tasdiqlash =====
def confirm_kb(lang="uz"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("btn_confirm", lang), callback_data="confirm:yes"),
         InlineKeyboardButton(text=t("btn_cancel", lang), callback_data="cancel")],
    ])

# ===== Fan (slayd) =====
def subjects_kb(detected_key, lang="uz"):
    rows = []
    row = []
    for key in SUBJECT_KEYS:
        name = subject_name(key, lang)
        mark = " ✅" if key == detected_key else ""
        row.append(InlineKeyboardButton(text=f"{name}{mark}", callback_data=f"subj:{key}"))
        if len(row) == 2:
            rows.append(row); row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ===== Dizayn tasdiq =====
def design_confirm_kb(suggested, lang="uz"):
    d = DESIGNS.get(suggested, DESIGNS["minimal"])
    dname = design_name(suggested, lang)
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ {d['emoji']} {dname} — {t('btn_continue_design', lang)}", callback_data=f"dsg:{suggested}")],
        [InlineKeyboardButton(text=t("btn_choose_design", lang), callback_data="dsg:choose")],
        [InlineKeyboardButton(text=t("btn_ai_design", lang), callback_data="dsg:ai_new")],
    ])

def designs_kb(lang="uz"):
    rows = []
    row = []
    for key, d in DESIGNS.items():
        row.append(InlineKeyboardButton(text=f"{d['emoji']} {design_name(key, lang)}", callback_data=f"dsg:{key}"))
        if len(row) == 2:
            rows.append(row); row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ===== Slayd soni =====
def slide_count_kb(lang="uz"):
    rows = []
    row = []
    for cnt, price in SLIDE_COUNTS:
        row.append(InlineKeyboardButton(text=f"📊 {t('slides_label', lang, n=cnt)}", callback_data=f"slcnt:{cnt}:{price}"))
        if len(row) == 3:
            rows.append(row); row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ===== Chek ko'rib chiqish =====
def check_review_kb(check_id, lang="uz"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("btn_approve", lang), callback_data=f"chk:{check_id}:approve"),
         InlineKeyboardButton(text=t("btn_reject", lang), callback_data=f"chk:{check_id}:reject")],
    ])

# ===== Narxlar (admin) =====
def price_kb(lang="uz"):
    rows = []
    for code, s in SERVICES.items():
        rows.append([InlineKeyboardButton(text=f'{s["emoji"]} {service_name(code, lang)}', callback_data=f"setprice:{code}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ===== Fayl formati (docx/pdf) =====
def format_kb(lang="uz"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("word_format", lang), callback_data="fmt:docx"),
         InlineKeyboardButton(text=t("pdf_format", lang), callback_data="fmt:pdf")],
        [InlineKeyboardButton(text=t("btn_cancel", lang), callback_data="cancel")],
    ])

# ===== Kanal obunasi (admin) =====
def channel_sub_kb(lang="uz"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("btn_on", lang), callback_data="chsub:on"),
         InlineKeyboardButton(text=t("btn_off", lang), callback_data="chsub:off")],
        [InlineKeyboardButton(text=t("btn_set_channel", lang), callback_data="chsub:set")],
    ])
