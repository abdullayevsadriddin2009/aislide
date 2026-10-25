# ===== Yangi taqdimot dizaynlari (faqat 3 ta faol variant) =====
DESIGNS = {
    "modern": {
        "emoji": "🏛️",
        "name_uz": "Temuriylar — ko‘k va oltin", "name_ru": "Тимуриды — синий и золото", "name_en": "Timurid — navy and gold",
        "name_tr": "Timurlu — lacivert ve altın", "name_de": "Timuriden — Marineblau und Gold", "name_fr": "Timouride — bleu nuit et or",
    },
    "nature": {
        "emoji": "🌿",
        "name_uz": "Ilmiy tabiat — yashil", "name_ru": "Научная природа — зелёный", "name_en": "Scientific nature — green",
        "name_tr": "Bilimsel doğa — yeşil", "name_de": "Wissenschaftliche Natur — Grün", "name_fr": "Nature scientifique — vert",
    },
    "elegant": {
        "emoji": "✨",
        "name_uz": "Minimal premium", "name_ru": "Минимализм премиум", "name_en": "Minimal premium",
        "name_tr": "Minimal premium", "name_de": "Minimal Premium", "name_fr": "Minimal premium",
    },
}


def design_name(key, lang="uz"):
    """Return one of the three active, localized presentation design names."""
    design = DESIGNS.get(key, DESIGNS["modern"])
    return design.get(f"name_{str(lang).lower()}", design["name_en"])

# Fanlar (subjects) — 6 tilda
SUBJECTS = {
    "tarix":      {"uz": "Tarix", "ru": "История", "en": "History", "tr": "Tarih", "de": "Geschichte", "fr": "Histoire"},
    "adabiyot":   {"uz": "Adabiyot", "ru": "Литература", "en": "Literature", "tr": "Edebiyat", "de": "Literatur", "fr": "Littérature"},
    "biologiya":  {"uz": "Biologiya", "ru": "Биология", "en": "Biology", "tr": "Biyoloji", "de": "Biologie", "fr": "Biologie"},
    "din":        {"uz": "Dinshunoslik", "ru": "Религиоведение", "en": "Religious Studies", "tr": "İlahiyat", "de": "Religionswissenschaft", "fr": "Sciences religieuses"},
    "falsafa":    {"uz": "Falsafa", "ru": "Философия", "en": "Philosophy", "tr": "Felsefe", "de": "Philosophie", "fr": "Philosophie"},
    "fizika":     {"uz": "Fizika", "ru": "Физика", "en": "Physics", "tr": "Fizik", "de": "Physik", "fr": "Physique"},
    "geografiya": {"uz": "Geografiya", "ru": "География", "en": "Geography", "tr": "Coğrafya", "de": "Geographie", "fr": "Géographie"},
    "huquq":      {"uz": "Huquq", "ru": "Право", "en": "Law", "tr": "Hukuk", "de": "Recht", "fr": "Droit"},
    "it":         {"uz": "Informatika / IT", "ru": "Информатика / IT", "en": "Computer Science / IT", "tr": "Bilişim / IT", "de": "Informatik / IT", "fr": "Informatique / TI"},
    "iqtisod":    {"uz": "Iqtisodiyot", "ru": "Экономика", "en": "Economics", "tr": "Ekonomi", "de": "Wirtschaft", "fr": "Économie"},
    "kimyo":      {"uz": "Kimyo", "ru": "Химия", "en": "Chemistry", "tr": "Kimya", "de": "Chemie", "fr": "Chimie"},
    "matematika": {"uz": "Matematika", "ru": "Математика", "en": "Mathematics", "tr": "Matematik", "de": "Mathematik", "fr": "Mathématiques"},
    "til":        {"uz": "Ona tili / Tilshunoslik", "ru": "Родной язык / Языкознание", "en": "Linguistics / Language", "tr": "Dilbilim", "de": "Linguistik", "fr": "Linguistique"},
    "pedagogika": {"uz": "Pedagogika / Ta'lim", "ru": "Педагогика / Образование", "en": "Pedagogy / Education", "tr": "Pedagoji / Eğitim", "de": "Pädagogik / Bildung", "fr": "Pédagogie / Éducation"},
    "rus_tili":   {"uz": "Rus tili", "ru": "Русский язык", "en": "Russian Language", "tr": "Rusça", "de": "Russisch", "fr": "Russe"},
    "sanat":      {"uz": "San'at va madaniyat", "ru": "Искусство и культура", "en": "Art & Culture", "tr": "Sanat ve kültür", "de": "Kunst & Kultur", "fr": "Art & Culture"},
    "sport":      {"uz": "Sport", "ru": "Спорт", "en": "Sports", "tr": "Spor", "de": "Sport", "fr": "Sport"},
    "tibbiyot":   {"uz": "Tibbiyot", "ru": "Медицина", "en": "Medicine", "tr": "Tıp", "de": "Medizin", "fr": "Médecine"},
}
SUBJECT_KEYS = list(SUBJECTS.keys())

def subject_name(key, lang="uz"):
    s = SUBJECTS.get(key, {"uz": key, "ru": key, "en": key, "tr": key, "de": key, "fr": key})
    lang = str(lang).lower()
    return s.get(lang) or s.get("en") or s.get("uz", key)

# ===== 6 TIL =====
ALL_LANGS = ("uz", "ru", "en", "tr", "de", "fr")
LANGUAGES = [
    ("uz", "🇺🇿 O'zbekcha"),
    ("ru", "🇷🇺 Русский"),
    ("en", "🇬🇧 English"),
    ("tr", "🇹🇷 Türkçe"),
    ("de", "🇩🇪 Deutsch"),
    ("fr", "🇫🇷 Français"),
]
LANG_NAMES_FULL = {
    "uz": {"uz": "O'zbekcha", "ru": "Узбекский", "en": "Uzbek", "tr": "Özbekçe", "de": "Usbekisch", "fr": "Ouzbek"},
    "ru": {"uz": "Ruscha", "ru": "Русский", "en": "Russian", "tr": "Rusça", "de": "Russisch", "fr": "Russe"},
    "en": {"uz": "Inglizcha", "ru": "Английский", "en": "English", "tr": "İngilizce", "de": "Englisch", "fr": "Anglais"},
    "tr": {"uz": "Turkcha", "ru": "Турецкий", "en": "Turkish", "tr": "Türkçe", "de": "Türkisch", "fr": "Turc"},
    "de": {"uz": "Nemischa", "ru": "Немецкий", "en": "German", "tr": "Almanca", "de": "Deutsch", "fr": "Allemand"},
    "fr": {"uz": "Fransuzcha", "ru": "Французский", "en": "French", "tr": "Fransızca", "de": "Französisch", "fr": "Français"},
}

def lang_full_name(code, ui_lang="uz"):
    """Hujjat tilini to'liq nomini UI tiliga ko'ra qaytaradi."""
    ui_lang = str(ui_lang).lower() if ui_lang in ALL_LANGS else "uz"
    return LANG_NAMES_FULL.get(code, {}).get(ui_lang, code)

# Slayd soni va standart narxlar (so‘m). Dizayn tanlovi slayd sonidan mustaqil.
SLIDE_COUNTS = [
    (10, 3000), (15, 4000), (20, 5000), (25, 6000),
    (5, 2000), (7, 2000), (12, 3000), (18, 4000), (30, 7000),
]

def select_theme(subject_key=None, design_key=None):
    """Return a valid new design key; never auto-override the user's choice."""
    return design_key if design_key in DESIGNS else "modern"

def suggest_design(subject_key=None):
    """Compatibility default; the bot now asks the user to choose explicitly."""
    return "modern"

def detect_subject_key(topic):
    """Mavzudan fan kalitini aniqlash."""
    tp = (topic or "").lower()
    mapping = {
        "hujayra": "biologiya", "biolog": "biologiya", "gen": "biologiya", "ekolog": "biologiya",
        "tarix": "tarix", "amir temur": "tarix", "temur": "tarix", "navoiy": "adabiyot",
        "huquq": "huquq", "iqtisod": "iqtisod", "bot": "it", "kompyuter": "it",
        "ai": "it", "sun'iy intellekt": "it", "python": "it", "intellekt": "it",
        "matem": "matematika", "fizik": "fizika", "energetika": "fizika",
        "kimyo": "kimyo", "tibbiy": "tibbiyot", "dori": "tibbiyot",
        "adabiy": "adabiyot", "til": "til", "geograf": "geografiya",
        "falsaf": "falsafa", "pedagog": "pedagogika", "sport": "sport",
        "san'at": "sanat", "rus": "rus_tili", "din": "din",
    }
    for k, v in mapping.items():
        if k in tp:
            return v
    return "tarix"
