# ===== Dizayn shablonlari (PPTX uchun rang palitralari) — 6 tilda =====
# Ikki asosiy tema (foydalanuvchi namunaviy fayllariga to'liq mos):
#   "temurid" — To'q ko'k #1B2A41 + Oltin #C9A227 (Amir Temur shabloni)
#   "biolog"  — To'q yashil #1B4332 + Yashil #4ADE80 (Hujayra shabloni)
DESIGNS = {
    "temurid": {
        "emoji": "🏛️",
        "name_uz": "Temuriylar (ko'k+oltin)", "name_ru": "Тимуриды (синий+золото)", "name_en": "Timurid (navy+gold)",
        "name_tr": "Timuri (lacivert+altın)", "name_de": "Timurid (marine+gold)", "name_fr": "Timouride (bleu+or)",
        "bg": (255, 250, 240), "primary": (27, 42, 65), "secondary": (120, 120, 120),
        "accent": (201, 162, 39), "title_font": "Playfair Display", "body_font": "Noto Sans",
        "style": "timurid", "dark_close": (27, 42, 65), "light_text": (220, 225, 230),
    },
    "biolog": {
        "emoji": "🌿",
        "name_uz": "Tabiat (yashil)", "name_ru": "Природа (зелёный)", "name_en": "Nature (green)",
        "name_tr": "Doğa (yeşil)", "name_de": "Natur (grün)", "name_fr": "Nature (vert)",
        "bg": (250, 255, 250), "primary": (27, 42, 65), "secondary": (120, 120, 120),
        "accent": (45, 106, 79), "title_font": "Playfair Display", "body_font": "Noto Sans",
        "style": "biolog", "dark_close": (27, 67, 50), "light_text": (210, 230, 215),
        "accent_bright": (74, 222, 128),
    },
    "marmar": {
        "emoji": "🪨",
        "name_uz": "Marmar", "name_ru": "Мрамор", "name_en": "Marble",
        "name_tr": "Mermer", "name_de": "Marmor", "name_fr": "Marbre",
        "bg": (250, 248, 245), "primary": (60, 60, 65), "secondary": (160, 150, 140),
        "accent": (180, 160, 140), "title_font": "Playfair Display", "body_font": "Noto Sans",
        "style": "elegant", "dark_close": (60, 60, 65), "light_text": (230, 228, 225),
    },
    "oltin": {
        "emoji": "✨",
        "name_uz": "Oltin", "name_ru": "Золотой", "name_en": "Golden",
        "name_tr": "Altın", "name_de": "Gold", "name_fr": "Or",
        "bg": (255, 252, 240), "primary": (80, 60, 20), "secondary": (180, 140, 40),
        "accent": (212, 175, 55), "title_font": "Playfair Display", "body_font": "Noto Sans",
        "style": "luxury", "dark_close": (80, 60, 20), "light_text": (245, 240, 220),
    },
    "davlat": {
        "emoji": "🏛️",
        "name_uz": "Davlat", "name_ru": "Государственный", "name_en": "Official",
        "name_tr": "Resmi", "name_de": "Offiziell", "name_fr": "Officiel",
        "bg": (245, 247, 250), "primary": (20, 40, 80), "secondary": (60, 90, 140),
        "accent": (180, 140, 40), "title_font": "Playfair Display", "body_font": "Noto Sans",
        "style": "official", "dark_close": (20, 40, 80), "light_text": (220, 228, 240),
    },
    "minimal": {
        "emoji": "⬛",
        "name_uz": "Minimal", "name_ru": "Минимализм", "name_en": "Minimalist",
        "name_tr": "Minimal", "name_de": "Minimal", "name_fr": "Minimaliste",
        "bg": (255, 255, 255), "primary": (20, 20, 20), "secondary": (100, 100, 100),
        "accent": (20, 20, 20), "title_font": "Playfair Display", "body_font": "Noto Sans",
        "style": "minimal", "dark_close": (20, 20, 20), "light_text": (230, 230, 230),
    },
    "nature": {
        "emoji": "🌿",
        "name_uz": "Tabiat", "name_ru": "Природа", "name_en": "Nature",
        "name_tr": "Doğa", "name_de": "Natur", "name_fr": "Nature",
        "bg": (245, 250, 245), "primary": (30, 70, 40), "secondary": (80, 130, 90),
        "accent": (45, 106, 79), "title_font": "Playfair Display", "body_font": "Noto Sans",
        "style": "fresh", "dark_close": (27, 67, 50), "light_text": (210, 230, 215),
        "accent_bright": (74, 222, 128),
    },
    "ai_dark": {
        "emoji": "🌌",
        "name_uz": "AI Dizayn", "name_ru": "ИИ-дизайн", "name_en": "AI Design",
        "name_tr": "AI Tasarım", "name_de": "KI-Design", "name_fr": "Design IA",
        "bg": (245, 247, 252), "primary": (20, 40, 80), "secondary": (100, 140, 220),
        "accent": (40, 90, 180), "title_font": "Playfair Display", "body_font": "Noto Sans",
        "style": "modern", "dark_close": (15, 20, 35), "light_text": (200, 220, 255),
    },
    "burgundiya": {
        "emoji": "🍷",
        "name_uz": "Burgundiya", "name_ru": "Бургундия", "name_en": "Burgundy",
        "name_tr": "Bordo", "name_de": "Burgund", "name_fr": "Bourgogne",
        "bg": (252, 245, 245), "primary": (90, 20, 35), "secondary": (140, 50, 60),
        "accent": (128, 0, 32), "title_font": "Playfair Display", "body_font": "Noto Sans",
        "style": "classic", "dark_close": (90, 20, 35), "light_text": (240, 225, 228),
    },
}

def design_name(key, lang="uz"):
    d = DESIGNS.get(key, DESIGNS["minimal"])
    lang = str(lang).lower()
    for k in (f"name_{lang}", "name_en", "name_uz", "name_ru"):
        if d.get(k):
            return d[k]
    return key

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

# Slayd soni + narx (so'm) — foydalanuvchi talabiga ko'ra 10/15/20/25 asosiy
SLIDE_COUNTS = [
    (10, 3000), (15, 4000), (20, 5000), (25, 6000),
    (5, 2000), (7, 2000), (12, 3000), (18, 4000), (30, 7000),
]

# Fan asosida tema (temurid yoki biolog) tanlash — namunaviy 2 faylga mos
def select_theme(subject_key, design_key=None):
    """science fanlari → biolog (yashil); qolganlari → temurid (ko'k+oltin)."""
    science = {"biologiya", "fizika", "kimyo", "matematika", "it", "tibbiyot"}
    if design_key in ("biolog", "nature"):
        return "biolog"
    if design_key in ("temurid", "davlat", "oltin", "burgundiya", "marmar", "minimal", "ai_dark"):
        return "temurid"
    if subject_key in science:
        return "biolog"
    return "temurid"

def suggest_design(subject_key):
    """Fan asosida dizayn tavsiya qilish — 2 asosiy tema."""
    return select_theme(subject_key)

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
