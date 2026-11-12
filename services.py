# ===== Xizmatlar (10 ta) — 6 tilda nomlar bilan =====
# name_uz / name_ru / name_en / name_tr / name_de / name_fr
SERVICES = {
    "slide":    {"emoji": "📊", "option_type": "slides", "options": (10, 15, 20), "price": 0,
                 "name_uz": "Taqdimot (Slayd)", "name_ru": "Презентация", "name_en": "Presentation",
                 "name_tr": "Sunum (Slayt)", "name_de": "Präsentation", "name_fr": "Présentation"},
    "referat":  {"emoji": "📄", "option_type": "pages",     "options": (7, 8, 9, 10), "price": 0,
                 "name_uz": "Referat", "name_ru": "Реферат", "name_en": "Essay / Report",
                 "name_tr": "Rapor", "name_de": "Referat", "name_fr": "Exposé"},
    "mustaqil": {"emoji": "📝", "option_type": "pages",     "options": (10, 15, 20), "price": 0,
                 "name_uz": "Mustaqil ish", "name_ru": "Самостоятельная работа", "name_en": "Assignment",
                 "name_tr": "Ödev", "name_de": "Hausarbeit", "name_fr": "Devoir"},
    "kurs":     {"emoji": "📘", "option_type": "pages",     "options": (25, 28, 30), "price": 0,
                 "name_uz": "Kurs ishi", "name_ru": "Курсовая работа", "name_en": "Coursework",
                 "name_tr": "Dönem ödevi", "name_de": "Seminararbeit", "name_fr": "Mémoire"},
    "diplom":   {"emoji": "🎓", "option_type": "pages",     "options": (50, 60, 70), "price": 0,
                 "name_uz": "Diplom ishi", "name_ru": "Дипломная работа", "name_en": "Thesis / Diploma",
                 "name_tr": "Mezuniyet tezi", "name_de": "Abschlussarbeit", "name_fr": "Mémoire de fin d'études"},
    # Insho — adabiy ijodiy ish (REJA majburiy, 3-5 bet).
    "insho":    {"emoji": "✍️", "option_type": "pages", "options": (3, 4, 5), "price": 0,
                 "name_uz": "Insho", "name_ru": "Сочинение", "name_en": "Composition",
                 "name_tr": "Kompozisyon", "name_de": "Aufsatz", "name_fr": "Dissertation"},
    # Esse — argumentli qisqa yozma ish (rejasiz, 150-350 so'z).
    "esse":     {"emoji": "🖊️", "option_type": "words", "options": (250, 400, 600), "price": 0,
                 "name_uz": "Esse", "name_ru": "Эссе", "name_en": "Essay",
                 "name_tr": "Deneme", "name_de": "Essay", "name_fr": "Essai"},
    "test":     {"emoji": "✅", "option_type": "questions", "price": 0,
                 "name_uz": "Quiz / Test", "name_ru": "Тест / Квиз", "name_en": "Quiz / Test",
                 "name_tr": "Test / Quiz", "name_de": "Test / Quiz", "name_fr": "Quiz / Test"},
    "maqola":   {"emoji": "📰", "option_type": "pages",     "options": (5, 6, 8), "price": 0,
                 "name_uz": "Maqola", "name_ru": "Статья", "name_en": "Article",
                 "name_tr": "Makale", "name_de": "Artikel", "name_fr": "Article"},
    "tezis":    {"emoji": "🎓", "option_type": "pages",     "options": (1, 2, 3), "price": 0,
                 "name_uz": "Tezis", "name_ru": "Тезисы", "name_en": "Abstract / Theses",
                 "name_tr": "Tez özeti", "name_de": "Thesen", "name_fr": "Résumé / Thèses"},
}

ALL_LANGS = ("uz", "ru", "en", "tr", "de", "fr")

SLIDE_COUNT_OPTIONS = (10, 15, 20)


def _as_int(value, fallback):
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def slide_body_count(slide_count):
    """Taqdimotdagi kontent slaydlari: muqova, mundarija va yakuniy slayd ayiriladi."""
    return max(2, _as_int(slide_count, SLIDE_COUNT_OPTIONS[0]) - 3)


def slide_image_total(body_slides):
    """Rasm yuklash byudjeti — bot ham, Mini App ham bir xil qiymat oladi."""
    return min(12, max(5, _as_int(body_slides, 5)))


def document_pages(service, options):
    """Hujjat generatori uchun hajm: esse — so'z, test — savol, qolganlari sahifa.

    Bot va Mini App shu funksiyani chaqiradi, aks holda bir xil so'rov ikki
    joyda har xil hajmda hujjat beradi.
    """
    options = options or {}
    if service == "test":
        return _as_int(options.get("questions") or options.get("pages"), 20)
    if service == "esse":
        words = _as_int(options.get("words"), 250)
        return max(2, (words + 299) // 300)
    if service == "insho":
        return _as_int(options.get("pages"), 3)
    return _as_int(options.get("pages") or options.get("count"), 10)

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
