"""Taqdimot dizaynlarining rasm ko'rinishidagi ko'rgazmasi.

Bot ham, Mini App ham bir xil funksiyani ishlatadi: 6 ta dizayn uchun muqova
slaydiga o'xshash kichik rasm (PNG baytlar) yasaladi. Har bir rasm o'sha
dizaynning taqdimotdagi haqiqiy palitrasi va bezak uslubida chiziladi
(gold arc, neon glow, hex tech, geometrik pop, tabiat, minimal ramka).
"""
import io
import math
import os
import unicodedata
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

from designs import DESIGN_KEYS, design_name
from pptx_generator import THEMES

WIDTH, HEIGHT = 1200, 675

_FONT_REGULAR = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
)
_FONT_BOLD = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
)

_SAMPLE_TITLE = {
    "uz": "Mavzu nomi", "ru": "Название темы", "en": "Topic title",
    "tr": "Konu başlığı", "de": "Thema der Präsentation", "fr": "Titre du sujet",
}
_SAMPLE_SUB = {
    "uz": "Taqdimot uchun qisqa izoh shu yerda", "ru": "Короткое описание презентации",
    "en": "A short line describing the presentation", "tr": "Sunumun kısa açıklaması",
    "de": "Kurze Beschreibung der Präsentation", "fr": "Brève description du sujet",
}
_SAMPLE_CTA = {
    "uz": "Batafsil", "ru": "Подробнее", "en": "Learn more",
    "tr": "Devamı", "de": "Mehr erfahren", "fr": "En savoir plus",
}


# Foydalanuvchi yuborgan moodboard rasmlarini shu papkaga qo'ysa bo'ladi:
# design_assets/modern.jpg, neon.jpg, amber.jpg, pop.jpg, nature.jpg, elegant.jpg.
# Fayl topilsa, chizilgan rasm o'rniga o'sha rasmning o'zi ko'rsatiladi.
ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "design_assets")
_ASSET_EXTS = (".jpg", ".jpeg", ".png", ".webp")


def asset_path(key):
    """design_assets/<key>.(jpg|png|webp) bo'lsa yo'lini qaytaradi."""
    for ext in _ASSET_EXTS:
        candidate = os.path.join(ASSET_DIR, f"{key}{ext}")
        if os.path.exists(candidate):
            return candidate
    return ""


def _from_asset(path):
    """Rasmni 1200x675 ga markazdan kesib (cover) PNG baytlariga aylantiradi."""
    image = Image.open(path).convert("RGB")
    ratio = max(WIDTH / image.width, HEIGHT / image.height)
    size = (max(WIDTH, int(image.width * ratio)), max(HEIGHT, int(image.height * ratio)))
    image = image.resize(size, Image.LANCZOS)
    left = (image.width - WIDTH) // 2
    top = (image.height - HEIGHT) // 2
    image = image.crop((left, top, left + WIDTH, top + HEIGHT))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _font(size, bold=False):
    for path in (_FONT_BOLD if bold else _FONT_REGULAR):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # eski Pillow
        return ImageFont.load_default()


def _fit(draw, text, size, max_width, bold=False):
    font = _font(size, bold)
    while size > 13 and draw.textlength(text, font=font) > max_width:
        size -= 2
        font = _font(size, bold)
    return font


def _wrap(draw, text, font, max_width, max_lines=3):
    words, lines, current = str(text).split(), [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return "\n".join(lines[:max_lines])


def _shade(color, factor):
    return tuple(max(0, min(255, int(channel * factor))) for channel in color)


def _photo_panel(image, box, base, accent, rounded=18):
    """Rasm uchun joy: gradientli panel va kichik tog' belgisi."""
    x0, y0, x1, y1 = box
    width, height = max(1, x1 - x0), max(1, y1 - y0)
    panel = Image.new("RGB", (width, height), base)
    draw = ImageDraw.Draw(panel)
    for row in range(height):
        ratio = row / height
        color = tuple(
            int(_shade(base, 1.02)[i] * (1 - ratio) + _shade(accent, 0.85)[i] * ratio)
            for i in range(3))
        draw.line([(0, row), (width, row)], fill=color)
    draw.ellipse([width * 0.62, height * 0.18, width * 0.78, height * 0.34],
                 fill=_shade(base, 1.45))
    draw.polygon([(width * 0.16, height * 0.78), (width * 0.42, height * 0.42),
                  (width * 0.68, height * 0.78)], fill=_shade(accent, 1.08))
    draw.polygon([(width * 0.52, height * 0.8), (width * 0.72, height * 0.55),
                  (width * 0.92, height * 0.8)], fill=_shade(accent, 0.8))
    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, width - 1, height - 1], radius=rounded, fill=255)
    image.paste(panel, (x0, y0), mask)


def _pill(draw, xy, text, fill, text_color, font):
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle([x0, y0, x1, y1], radius=(y1 - y0) // 2, fill=fill)
    draw.text((x0 + 22, y0 + (y1 - y0 - font.size) / 2 - 2), text, font=font, fill=text_color)


def _dots(draw, x, y, color, count=4, active=0, gap=16):
    for index in range(count):
        radius = 4 if index == active else 3
        draw.ellipse([x + index * gap, y - radius, x + index * gap + radius * 2, y + radius],
                     fill=color if index <= active else _shade(color, 0.55))


def _title_block(draw, text, x, y, max_width, color, size=62, bold=True):
    font = _fit(draw, text, size, max_width, bold=bold)
    draw.multiline_text((x, y), _wrap(draw, text, font, max_width), font=font, fill=color, spacing=10)


def _sub_block(draw, text, x, y, max_width, color, size=24):
    font = _font(size)
    draw.multiline_text((x, y), _wrap(draw, text, font, max_width, max_lines=2), font=font,
                        fill=color, spacing=6)


# ============================ DIZAYN BO'YICHA CHIZISH ============================

def _draw_modern(image, draw, theme, lc):
    bg, panel, accent, text = theme["bg"], theme["panel"], theme["accent"], theme["text"]
    draw.rectangle([0, 0, WIDTH, HEIGHT], fill=bg)
    # Ingichka oltin chiziq va yulduzcha bezaklari.
    draw.line([(90, 96), (200, 96)], fill=accent, width=3)
    draw.line([(90, 120), (150, 120)], fill=theme["line"], width=2)
    _photo_panel(image, (770, 40, 1150, 600), theme["cover"], accent)
    for radius in (250, 200, 150):
        draw.arc([600, 380, 600 + radius * 2, 380 + radius * 2], 200, 340, fill=accent, width=3)
    draw.line([(632, 120), (660, 90), (688, 120), (660, 150), (632, 120)], fill=accent, width=2)
    _title_block(draw, _SAMPLE_TITLE[lc], 90, 190, 640, theme["primary"], 76)
    _sub_block(draw, _SAMPLE_SUB[lc], 92, 330, 600, _shade(text, 1.35), 24)
    _pill(draw, (92, 420, 300, 470), _SAMPLE_CTA[lc], accent, panel, _font(22, True))
    draw.line([(90, 560), (700, 560)], fill=theme["line"], width=2)
    _dots(draw, 92, 600, accent)


def _draw_neon(image, draw, theme, lc):
    draw.rectangle([0, 0, WIDTH, HEIGHT], fill=theme["cover"])
    cyan, magenta, text = theme["accent"], (232, 62, 190), theme["primary"]
    for index in range(3):
        offset = index * 90
        draw.arc([640 + offset, -140 + offset, 1240 + offset, 500 + offset], 150, 330,
                 fill=(cyan if index % 2 == 0 else magenta), width=22)
    draw.ellipse([960, 70, 1120, 230], fill=cyan + (70,))
    draw.ellipse([760, 380, 880, 500], fill=magenta + (60,))
    draw.rounded_rectangle([90, 78, 300, 108], radius=15, fill=(255, 255, 255, 30))
    draw.line([(700, 430), (1000, 470)], fill=cyan, width=3)
    _title_block(draw, _SAMPLE_TITLE[lc], 90, 190, 660, text, 72)
    _sub_block(draw, _SAMPLE_SUB[lc], 92, 320, 580, theme["secondary"], 24)
    _pill(draw, (92, 410, 320, 462), _SAMPLE_CTA[lc], cyan, theme["cover"], _font(22, True))
    _dots(draw, 92, 600, cyan)


def _draw_amber(image, draw, theme, lc):
    draw.rectangle([0, 0, WIDTH, HEIGHT], fill=theme["cover"])
    yellow, text = theme["accent"], theme["primary"]
    draw.polygon([(820, 40), (1160, 40), (1160, 340)], fill=_shade(yellow, 0.9))
    for cx, cy, radius in ((900, 260, 150), (1080, 470, 90)):
        points = [(cx + radius * math.cos(math.pi / 3 * i - math.pi / 6),
                   cy + radius * math.sin(math.pi / 3 * i - math.pi / 6)) for i in range(6)]
        draw.polygon(points, fill=theme["panel"], outline=yellow, width=4)
        inner = [(cx + radius * 0.55 * math.cos(math.pi / 3 * i - math.pi / 6),
                  cy + radius * 0.55 * math.sin(math.pi / 3 * i - math.pi / 6)) for i in range(6)]
        draw.polygon(inner, fill=yellow)
    for offset in range(4):
        draw.line([(90 + offset * 40, 640), (140 + offset * 70, 560 - offset * 30)],
                  fill=_shade(yellow, 0.5), width=2)
    _title_block(draw, _SAMPLE_TITLE[lc], 90, 200, 620, text, 74)
    _sub_block(draw, _SAMPLE_SUB[lc], 92, 340, 540, theme["secondary"], 23)
    _pill(draw, (92, 430, 300, 480), _SAMPLE_CTA[lc], yellow, theme["cover"], _font(22, True))
    _dots(draw, 92, 600, yellow)


def _draw_pop(image, draw, theme, lc):
    draw.rectangle([0, 0, WIDTH, HEIGHT], fill=theme["bg"])
    red, yellow, pink, black = theme["accent"], (247, 190, 40), theme["soft"], theme["primary"]
    draw.rectangle([0, 0, 150, 130], fill=pink)
    draw.rectangle([0, 130, 150, 240], fill=red)
    draw.rectangle([0, 240, 150, 300], fill=black)
    draw.rectangle([1000, 0, 1200, 230], fill=red)
    draw.rectangle([860, 60, 1000, 230], fill=pink)
    draw.rectangle([1090, 230, 1200, 420], fill=black)
    draw.rectangle([940, 420, 1200, 520], fill=yellow)
    draw.ellipse([1000, 480, 1200, 680], fill=black)
    draw.ellipse([880, 470, 1030, 620], fill=yellow)
    _title_block(draw, _SAMPLE_TITLE[lc], 190, 200, 620, black, 82)
    _sub_block(draw, _SAMPLE_SUB[lc], 192, 350, 560, theme["text"], 23)
    draw.line([(190, 420), (330, 420)], fill=red, width=6)
    _dots(draw, 192, 600, red)


def _draw_nature(image, draw, theme, lc):
    draw.rectangle([0, 0, WIDTH, HEIGHT], fill=theme["bg"])
    green, accent, text = theme["primary"], theme["accent"], theme["text"]
    _photo_panel(image, (760, 50, 1140, 590), theme["cover"], accent, rounded=26)
    for cx, cy, rx, ry in ((690, 120, 120, 55), (1120, 620, 150, 60), (620, 520, 90, 40)):
        draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=accent + (70,))
    draw.line([(90, 150), (90, 360)], fill=green, width=4)
    _title_block(draw, _SAMPLE_TITLE[lc], 120, 190, 600, green, 74)
    _sub_block(draw, _SAMPLE_SUB[lc], 122, 340, 560, _shade(text, 1.3), 23)
    _pill(draw, (122, 420, 330, 470), _SAMPLE_CTA[lc], green, theme["panel"], _font(22, True))
    _dots(draw, 122, 600, green)


def _draw_elegant(image, draw, theme, lc):
    draw.rectangle([0, 0, WIDTH, HEIGHT], fill=(255, 255, 255))
    red, text = theme["accent"], theme["primary"] if theme["primary"] != (255, 255, 255) else (34, 34, 34)
    draw.rectangle([0, 0, 26, HEIGHT], fill=red)
    draw.rectangle([900, 70, 1140, 520], outline=red, width=3)
    _photo_panel(image, (930, 100, 1110, 490), theme["soft"], red, rounded=10)
    draw.rectangle([1090, 470, 1150, 640], fill=_shade(red, 0.85))
    draw.line([(90, 150), (300, 150)], fill=red, width=3)
    _title_block(draw, _SAMPLE_TITLE[lc], 90, 210, 700, text, 76)
    _sub_block(draw, _SAMPLE_SUB[lc], 92, 350, 600, theme["secondary"], 23)
    _pill(draw, (92, 430, 300, 478), _SAMPLE_CTA[lc], red, (255, 255, 255), _font(22, True))
    _dots(draw, 92, 600, red, count=5, active=0, gap=14)


_BUILDERS = {
    "modern": _draw_modern,
    "neon": _draw_neon,
    "amber": _draw_amber,
    "pop": _draw_pop,
    "nature": _draw_nature,
    "elegant": _draw_elegant,
}


@lru_cache(maxsize=64)
def render_design_preview(key, lang="uz", topic=""):
    """Bitta dizayn uchun muqova slaydiga o'xshash PNG baytlarini qaytaradi."""
    asset = asset_path(key)
    if asset:
        try:
            return _from_asset(asset)
        except Exception as exc:  # buzilgan rasm bo'lsa, chizilgan variant qoladi
            print(f"[design_preview] {asset}: {exc}", flush=True)

    theme = THEMES.get(key) or THEMES[DESIGN_KEYS[0]]
    lc = str(lang or "uz").lower()
    if lc not in _SAMPLE_TITLE:
        lc = "en"
    image = Image.new("RGB", (WIDTH, HEIGHT), theme["bg"])
    draw = ImageDraw.Draw(image, "RGBA")
    builder = _BUILDERS.get(key, _draw_modern)
    builder(image, draw, theme, lc)

    # Emoji va ko'rinmas belgilar shriftda kvadrat bo'lib chiqadi: yorliq faqat matn.
    label = "".join(
        ch for ch in design_name(key, lc)
        if ch.isprintable() and ord(ch) < 0x2100
        and not unicodedata.category(ch).startswith("C")
    )
    label = " ".join(label.split()).replace("\u2014", "-").replace("\u2013", "-")
    label_font = _font(20, True)
    label_width = int(draw.textlength(label, font=label_font)) + 34
    pill_fill = (255, 255, 255, 38) if theme.get("dark_content") else (255, 255, 255, 150)
    draw.rounded_rectangle([90, 22, 90 + label_width, 58], radius=18, fill=pill_fill)
    draw.text((102, 30), label, font=label_font, fill=theme["primary"])

    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def all_previews(lang="uz"):
    """[(key, nom, png)] — 1..6 tartibida."""
    return [(key, design_name(key, lang), render_design_preview(key, lang))
            for key in DESIGN_KEYS]
