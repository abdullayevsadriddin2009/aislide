from aiogram.types import (ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton)
from aiogram.types import WebAppInfo
import config
from texts import t
from services import SERVICES, service_name
# Eski dizaynlarga tegishli importlar olib tashlandi
from designs import SUBJECT_KEYS, subject_name, LANGUAGES, DESIGNS, DESIGN_KEYS, design_name

# ===== Asosiy menyu =====
def mini_app_kb(lang="uz"):
    """Mini App'ni ochuvchi inline tugma (Telegram WebApp)."""
    if not config.WEBAPP_URL:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t("btn_app", lang),
                             web_app=WebAppInfo(url=config.WEBAPP_URL + "/app"))
    ]])


def main_kb(lang="uz"):
    mini_row = []
    if config.WEBAPP_URL:
        mini_row = [[KeyboardButton(text=t("btn_app", lang),
                                    web_app=WebAppInfo(url=config.WEBAPP_URL + "/app"))]]
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=t("btn_create", lang))]] + mini_row + [
        [KeyboardButton(text=t("btn_chat", lang)), KeyboardButton(text=t("btn_balance", lang))],
        [KeyboardButton(text=t("btn_referral", lang)), KeyboardButton(text=t("btn_help", lang))],
        [KeyboardButton(text=t("btn_lang", lang))],
    ], resize_keyboard=True)

# ===== Admin menyu =====
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

# ===== Bot tilini tanlash =====
def bot_lang_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="blang:uz"),
         InlineKeyboardButton(text="🇷🇺 Русский", callback_data="blang:ru"),
         InlineKeyboardButton(text="🇬🇧 English", callback_data="blang:en")],
        [InlineKeyboardButton(text="🇹🇷 Türkçe", callback_data="blang:tr"),
         InlineKeyboardButton(text="🇩🇪 Deutsch", callback_data="blang:de"),
         InlineKeyboardButton(text="🇫🇷 Français", callback_data="blang:fr")],
    ])

# ===== Hujjat tilini tanlash =====
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

# ===== Parametr (pages/questions/words) =====
DEFAULT_OPTIONS = {"pages": (10, 15, 20), "questions": (10, 15, 20), "words": (200, 300, 500)}
OPTION_ICONS = {"pages": "📄", "questions": "✅", "words": "✍️"}
OPTION_LABELS = {"pages": "pages_label", "questions": "questions_label", "words": "words_label"}

def service_options(service):
    """Xizmat uchun ruxsat etilgan qiymatlar (masalan Insho: 3/4/5 bet, Esse: 150/250/350 so'z)."""
    s = SERVICES.get(service, {})
    otype = s.get("option_type", "pages")
    values = tuple(s.get("options") or DEFAULT_OPTIONS.get(otype, (10, 15, 20)))
    return otype, values

def option_kb_for(service, lang="uz"):
    otype, values = service_options(service)
    icon = OPTION_ICONS.get(otype, "📄")
    label_key = OPTION_LABELS.get(otype, "pages_label")
    rows = [[InlineKeyboardButton(text=f"{icon} {t(label_key, lang, n=v)}", callback_data=f"opt:{otype}:{v}")]
            for v in values]
    rows.append([InlineKeyboardButton(text=t("btn_cancel", lang), callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def option_label(service, options, lang="uz"):
    otype, values = service_options(service)
    default = values[0] if values else 0
    label_key = OPTION_LABELS.get(otype, "pages_label")
    return t(label_key, lang, n=options.get(otype, default))

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

# ===== Taqdimot slaydlar soni =====
def slide_count_kb(lang="uz"):
    rows = []
    counts = (10, 15, 20)
    labels = {
        "uz": "{n} ta slayd", "ru": "{n} слайдов", "en": "{n} slides",
        "tr": "{n} slayt", "de": "{n} Folien", "fr": "{n} diapositives",
    }
    for i in range(0, len(counts), 3):
        row = [InlineKeyboardButton(
            text=f"📊 {labels.get(lang, labels['en']).format(n=n)}",
            callback_data=f"scnt:{n}"
        ) for n in counts[i:i+3]]
        rows.append(row)
    rows.append([InlineKeyboardButton(text=t("btn_cancel", lang), callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ===== Taqdimot dizayni: 6 ta mustaqil variant =====
def template_kb(lang="uz"):
    """Six presentation designs, with names localized to the selected language."""
    rows = []
    for key in DESIGN_KEYS:
        design = DESIGNS[key]
        label = design_name(key, lang)
        rows.append([InlineKeyboardButton(
            text=f"{design['emoji']} {label}",
            callback_data=f"tmpl:{key}"
        )])
    rows.append([InlineKeyboardButton(text=t("btn_cancel", lang), callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ===== AI Chat: tarixni tozalash tugmasi =====
CHAT_UI = {
    "uz": {"clear": "🧹 Suhbat tarixini tozalash", "cleared": "🧹 <b>Suhbat tarixi tozalandi.</b>\n\nYangi mavzuni yozing — avvalgi suhbatga bog'lanmayman.", "start": "💬 <b>AI Chat</b>\n\nSavolingizni yozing — men javob beraman va suhbatni davom ettiraman.\nYangi mavzu kerak bo'lsa «🧹 Suhbat tarixini tozalash» tugmasini bosing."},
    "ru": {"clear": "🧹 Очистить историю чата", "cleared": "🧹 <b>История чата очищена.</b>\n\nНапишите новую тему — предыдущий разговор учитываться не будет.", "start": "💬 <b>ИИ Чат</b>\n\nНапишите вопрос — я отвечу и продолжу разговор.\nДля новой темы нажмите «🧹 Очистить историю чата»."},
    "en": {"clear": "🧹 Clear chat history", "cleared": "🧹 <b>Chat history cleared.</b>\n\nType a new topic — I won't refer to the previous conversation.", "start": "💬 <b>AI Chat</b>\n\nType your question — I'll answer and continue the conversation.\nFor a new topic press «🧹 Clear chat history»."},
    "tr": {"clear": "🧹 Sohbet geçmişini temizle", "cleared": "🧹 <b>Sohbet geçmişi temizlendi.</b>\n\nYeni konuyu yazın — önceki sohbete bağlanmayacağım.", "start": "💬 <b>AI Sohbet</b>\n\nSorunuzu yazın — cevaplayıp sohbeti sürdüreceğim.\nYeni konu için «🧹 Sohbet geçmişini temizle» düğmesine basın."},
    "de": {"clear": "🧹 Chatverlauf löschen", "cleared": "🧹 <b>Chatverlauf gelöscht.</b>\n\nSchreiben Sie ein neues Thema — ich beziehe mich nicht auf das vorherige Gespräch.", "start": "💬 <b>KI-Chat</b>\n\nSchreiben Sie Ihre Frage — ich antworte und setze das Gespräch fort.\nFür ein neues Thema «🧹 Chatverlauf löschen» drücken."},
    "fr": {"clear": "🧹 Effacer l’historique du chat", "cleared": "🧹 <b>Historique du chat effacé.</b>\n\nÉcrivez un nouveau sujet — je ne tiendrai pas compte de la conversation précédente.", "start": "💬 <b>Chat IA</b>\n\nÉcrivez votre question — je répondrai et poursuivrai la conversation.\nPour un nouveau sujet, appuyez sur «🧹 Effacer l’historique du chat»."},
}


def chat_labels(lang="uz"):
    lang = str(lang).lower()
    return CHAT_UI.get(lang) or CHAT_UI["en"]


def chat_kb(lang="uz"):
    """Inline tugma: suhbat tarixini tozalab, yangi mavzu boshlash."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=chat_labels(lang)["clear"], callback_data="chat:clear")],
    ])


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
