# ===== Xizmatlar (9 ta) — 6 tilda nomlar bilan =====
# name_uz / name_ru / name_en / name_tr / name_de / name_fr
SERVICES = {
    "slide":    {"emoji": "📊", "option_type": "slides",    "price": 0,
                 "name_uz": "Taqdimot (Slayd)", "name_ru": "Презентация", "name_en": "Presentation",
                 "name_tr": "Sunum (Slayt)", "name_de": "Präsentation", "name_fr": "Présentation"},
    "referat":  {"emoji": "📄", "option_type": "pages",     "price": 0,
                 "name_uz": "Referat", "name_ru": "Реферат", "name_en": "Essay / Report",
                 "name_tr": "Rapor", "name_de": "Referat", "name_fr": "Exposé"},
    "mustaqil": {"emoji": "📝", "option_type": "pages",     "price": 0,
                 "name_uz": "Mustaqil ish", "name_ru": "Самостоятельная работа", "name_en": "Assignment",
                 "name_tr": "Ödev", "name_de": "Hausarbeit", "name_fr": "Devoir"},
    "kurs":     {"emoji": "📘", "option_type": "pages",     "price": 0,
                 "name_uz": "Kurs ishi", "name_ru": "Курсовая работа", "name_en": "Coursework",
                 "name_tr": "Dönem ödevi", "name_de": "Seminararbeit", "name_fr": "Mémoire"},
    "diplom":   {"emoji": "🎓", "option_type": "pages",     "price": 0,
                 "name_uz": "Diplom ishi", "name_ru": "Дипломная работа", "name_en": "Thesis / Diploma",
                 "name_tr": "Mezuniyet tezi", "name_de": "Abschlussarbeit", "name_fr": "Mémoire de fin d'études"},
    "insho":    {"emoji": "✍️", "option_type": "pages",     "price": 0,
                 "name_uz": "Insho / Essey", "name_ru": "Сочинение / Эссе", "name_en": "Composition / Essay",
                 "name_tr": "Kompozisyon / Deneme", "name_de": "Aufsatz / Essay", "name_fr": "Dissertation / Essai"},
    "test":     {"emoji": "✅", "option_type": "questions", "price": 0,
                 "name_uz": "Quiz / Test", "name_ru": "Тест / Квиз", "name_en": "Quiz / Test",
                 "name_tr": "Test / Quiz", "name_de": "Test / Quiz", "name_fr": "Quiz / Test"},
    "maqola":   {"emoji": "📰", "option_type": "pages",     "price": 0,
                 "name_uz": "Maqola", "name_ru": "Статья", "name_en": "Article",
                 "name_tr": "Makale", "name_de": "Artikel", "name_fr": "Article"},
    "tezis":    {"emoji": "🎓", "option_type": "pages",     "price": 0,
                 "name_uz": "Tezis", "name_ru": "Тезисы", "name_en": "Abstract / Theses",
                 "name_tr": "Tez özeti", "name_de": "Thesen", "name_fr": "Résumé / Thèses"},
}

ALL_LANGS = ("uz", "ru", "en", "tr", "de", "fr")

def service_name(code, lang="uz"):
    """Xizmat nomini tanlangan tilda qaytaradi (6 til, fallback: en → uz)."""
    s = SERVICES.get(code, {})
    lang = str(lang).lower()
    for k in (f"name_{lang}", "name_en", "name_uz", "name_ru"):
        if s.get(k):
            return s[k]
    return code

SUBSCRIPTION_PLANS = [
    {"id": "plan1", "name": "1-reja", "price": 29000,  "bonus": "10%", "quota": 32000},
    {"id": "plan2", "name": "2-reja", "price": 99000,  "bonus": "20%", "quota": 120000},
    {"id": "plan3", "name": "3-reja", "price": 199000, "bonus": "30%", "quota": 260000},
]
PAYMENT_METHODS = ["Payme", "Click", "Uzum", "Uzcard", "Humo", "VISA", "Mastercard"]
DEFAULT_REFERRAL_BONUS = 500
