"""Taqdimot dizaynlarining rasm ko'rinishidagi ko'rgazmasi.

Bot ham, Mini App ham bir xil funksiyani ishlatadi: 6 ta dizayn uchun
muqova slaydiga o'xshash kichik rasm (PNG baytlar) yasaladi. Rasmlar
`pptx_generator.THEMES` palitrasidan foydalanadi, shuning uchun tanlov
paytida ko'rsatilgan rang haqiqiy taqdimotdagi rang bilan bir xil bo'ladi.
"""
import io
import math
import os
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

from designs import DESIGN_KEYS, design_name
from pptx_generator import THEMES

WIDTH, HEIGHT = 1200, 675

_FONT_PATHS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
)

_SAMPLE_TITLE = {
    "uz": "Mavzu nomi shu yerda",
    "ru": "Название темы",
    "en": "Topic title goes here",
    "tr": "Konu başlığı burada",
    "de": "Thema der Präsentation",
    "fr": "Titre du sujet",
}

_SAMPLE_BULLETS = {
    "uz": ("Asosiy tushuncha va ta'rif", "Muhim dalillar va misollar", "Amaliy xulosa"),
    "ru": ("Основное понятие и определение", "Важные факты и примеры", "Практический вывод"),
    "en": ("Key concept and definition", "Important facts and examples", "Practical conclusion"),
    "tr": ("Temel kavram ve tanım", "Önemli kanıtlar ve örnekler", "Uygulamalı sonuç"),
    "de": ("Grundbegriff und Definition", "Wichtige Belege und Beispiele", "Praktisches Fazit"),
    "fr": ("Concept clé et définition", "Faits et exemples importants", "Conclusion pratique"),
}


def _font(size, bold=False):
    for path in (_FONT_PATHS if bold else tuple(reversed(_FONT_PATHS))):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # eski Pillow
        return ImageFont.load_default()


def _fit(draw, text, size, max_width, bold=False):
    """Matnni rasm kengligiga sig'adigan qilib kichraytiradi."""
    font = _font(size, bold)
    while size > 14 and draw.textlength(text, font=font) > max_width:
        size -= 2
        font = _font(size, bold)
    return font


def _decorate(draw, key, theme, width, height):
    accent, secondary, soft = theme["accent"], theme["secondary"], theme["soft"]
    style = theme.get("decorate", "arc")
    if style == "arc":
        for radius in (330, 250, 170):
            draw.arc([width - radius - 40, height - radius - 20, width + radius - 40, height + radius - 20],
                     start=180, end=360, fill=accent, width=3)
        draw.ellipse([width - 210, height - 170, width - 140, height - 100], fill=accent)
    elif style == "bubbles":
        bubbles = ((900, 120, 150, accent), (1030, 300, 90, secondary),
                   (840, 430, 120, accent), (1120, 90, 60, secondary), (700, 560, 80, accent))
        for cx, cy, r, colour in bubbles:
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=colour + (60,))
    elif style == "hex":
        for cx, cy, r in ((1000, 160, 110), (1120, 420, 80), (860, 520, 60)):
            points = [(cx + r * math.cos(math.pi / 3 * i - math.pi / 6),
                       cy + r * math.sin(math.pi / 3 * i - math.pi / 6)) for i in range(6)]
            draw.polygon(points, outline=accent, width=3)
    elif style == "shapes":
        draw.rectangle([width - 260, 0, width - 140, 160], fill=accent)
        draw.polygon([(width - 120, 0), (width, 0), (width, 120)], fill=soft)
        draw.ellipse([width - 90, height - 200, width - 10, height - 120], fill=accent)
        draw.rectangle([width - 300, height - 120, width - 160, height - 100], fill=accent)
    elif style == "leaf":
        for cx, cy, rx, ry in ((1010, 150, 130, 60), (1090, 360, 90, 40), (880, 540, 110, 50)):
            draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=accent + (70,))
    else:  # elegant
        draw.line([(80, height - 90), (width - 80, height - 90)], fill=accent, width=2)
        draw.ellipse([width - 150, 80, width - 110, 120], fill=accent)
        draw.line([(width - 200, 100), (width - 170, 100)], fill=secondary, width=2)


@lru_cache(maxsize=64)
def render_design_preview(key, lang="uz", topic=""):
    """Bitta dizayn uchun muqova slaydiga o'xshash PNG baytlarini qaytaradi."""
    theme = THEMES.get(key) or THEMES[DESIGN_KEYS[0]]
    lc = str(lang or "uz").lower()
    if lc not in _SAMPLE_TITLE:
        lc = "en"
    image = Image.new("RGB", (WIDTH, HEIGHT), theme["cover"])
    draw = ImageDraw.Draw(image, "RGBA")
    _decorate(draw, key, theme, WIDTH, HEIGHT)

    on_dark = theme["on_dark"]
    margin = 90
    # Yuqori yorliq: dizayn nomi va raqami.
    # Emoji shriftda kvadrat bo'lib ko'rinadi, yorliq faqat matndan iborat.
    label = "".join(ch for ch in design_name(key, lc) if ord(ch) < 0x2100).strip()
    draw.text((margin, 70), label, font=_font(30, bold=True), fill=theme["accent"])
    draw.line([(margin, 118), (margin + 90, 118)], fill=theme["accent"], width=4)

    title = str(topic or "").strip() or _SAMPLE_TITLE[lc]
    title_font = _fit(draw, title, 58, WIDTH - margin * 2 - 260, bold=True)
    draw.multiline_text((margin, 170), _wrap(draw, title, title_font, WIDTH - margin * 2 - 260),
                        font=title_font, fill=on_dark, spacing=12)

    y = 380
    for index, bullet in enumerate(_SAMPLE_BULLETS[lc], 1):
        draw.rounded_rectangle([margin, y - 14, margin + 26, y + 12], radius=6, fill=theme["accent"])
        draw.text((margin + 46, y - 20), bullet, font=_font(28), fill=on_dark)
        y += 62

    draw.text((WIDTH - margin - 90, HEIGHT - 70), "01", font=_font(26), fill=theme["secondary"])
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _wrap(draw, text, font, max_width):
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
    return "\n".join(lines[:3])


def all_previews(lang="uz"):
    """[(key, nom, png)] — 1..6 tartibida."""
    return [(key, design_name(key, lang), render_design_preview(key, lang))
            for key in DESIGN_KEYS]
