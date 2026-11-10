# -*- coding: utf-8 -*-
"""PowerPoint generator with six independent, fully localized designs.

Design keys: modern, neon, amber, pop, nature, elegant. The selected design
never changes the requested slide count. All template/UI text is localized to
``lang``.
"""
from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Any

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

from designs import DESIGNS, DESIGN_KEYS

BOT_USERNAME = "@Talaba_AI_SlideBot"

# Each theme carries its own palette, page mode and decoration style so the six
# designs are visibly different rather than recolored copies of one layout.
THEMES = {
    # Warm Timurid paper, terracotta and gold.
    "modern": {
        "bg": (250, 246, 240), "panel": (255, 255, 255), "primary": (124, 58, 32),
        "accent": (196, 106, 58), "secondary": (150, 130, 115), "text": (58, 46, 38),
        "cover": (92, 42, 22), "soft": (245, 232, 219), "line": (228, 214, 201),
        "header": (124, 58, 32), "dark_content": False, "card": (255, 255, 255),
        "on_dark": (245, 240, 235), "decorate": "arc",
    },
    # Neon tech: deep indigo with cyan and magenta glow.
    "neon": {
        "bg": (18, 22, 48), "panel": (28, 33, 72), "primary": (240, 240, 255),
        "accent": (46, 224, 224), "secondary": (140, 152, 205), "text": (226, 232, 246),
        "cover": (11, 15, 38), "soft": (34, 39, 88), "line": (54, 60, 116),
        "header": (36, 41, 92), "dark_content": True, "card": (30, 35, 78),
        "on_dark": (224, 230, 248), "decorate": "bubbles",
    },
    # Engineering: black plates with amber accents.
    "amber": {
        "bg": (24, 24, 24), "panel": (34, 34, 34), "primary": (255, 255, 255),
        "accent": (247, 178, 42), "secondary": (155, 155, 155), "text": (232, 232, 232),
        "cover": (14, 14, 14), "soft": (44, 44, 44), "line": (64, 64, 64),
        "header": (40, 40, 40), "dark_content": True, "card": (32, 32, 32),
        "on_dark": (234, 234, 234), "decorate": "hex",
    },
    # Geometric pop: red, pink and yellow blocks on white.
    "pop": {
        "bg": (250, 250, 247), "panel": (255, 255, 255), "primary": (26, 26, 26),
        "accent": (230, 51, 35), "secondary": (120, 120, 120), "text": (34, 34, 34),
        "cover": (26, 26, 26), "soft": (255, 214, 224), "line": (232, 232, 228),
        "header": (26, 26, 26), "dark_content": False, "card": (255, 255, 255),
        "on_dark": (245, 240, 235), "decorate": "shapes",
    },
    # Scientific nature: deep green and bright leaf green.
    "nature": {
        "bg": (248, 245, 240), "panel": (255, 255, 255), "primary": (27, 67, 50),
        "accent": (74, 222, 128), "secondary": (111, 128, 116), "text": (42, 48, 44),
        "cover": (8, 38, 30), "soft": (231, 239, 232), "line": (205, 219, 207),
        "header": (27, 67, 50), "dark_content": False, "card": (255, 255, 255),
        "on_dark": (236, 244, 238), "decorate": "leaf",
    },
    # Premium minimal: plum and champagne with occasional dark slides.
    "elegant": {
        "bg": (248, 244, 240), "panel": (255, 255, 255), "primary": (65, 35, 56),
        "accent": (194, 158, 103), "secondary": (136, 118, 128), "text": (54, 45, 51),
        "cover": (39, 23, 36), "soft": (243, 232, 222), "line": (227, 213, 207),
        "header": (65, 35, 56), "dark_content": False, "card": (255, 255, 255),
        "on_dark": (239, 233, 239), "decorate": "frame",
    },
}

DESIGN_NAMES = {key: {lang: DESIGNS[key][f"name_{lang}"] for lang in ("uz", "ru", "en", "tr", "de", "fr")}
                for key in DESIGN_KEYS}

# Static template strings only. The generated subject matter is supplied by the AI
# and must be generated in the same language as this dictionary's language key.
UI = {
    "uz": {"overview": "TAQDIMOT", "overview_tag": "REJA · ASOSIY BO‘LIMLAR", "overview_title": "Taqdimot mazmuni", "overview_list_heading": "MAVZUNING ASOSIY QISMLARI", "section": "BO‘LIM", "presentation": "taqdimoti", "key_points": "Asosiy fikrlar", "details": "Muhim jihatlar", "part": "BO‘LIM", "prepared": "Tayyorladi", "summary": "Yakuniy xulosalar", "thanks": "E’tiboringiz uchun rahmat!", "slide": "S L A Y D", "continued": "Davomi", "image_label": "RASM UCHUN JOY", "empty_title": "Qo‘shimcha tahlil", "empty_body": "Bu bo‘lim mavzuning muhim jihatlarini umumlashtiradi."},
    "ru": {"overview": "ПРЕЗЕНТАЦИЯ", "overview_tag": "ПЛАН · ОСНОВНЫЕ РАЗДЕЛЫ", "overview_title": "Содержание презентации", "overview_list_heading": "ОСНОВНЫЕ РАЗДЕЛЫ ТЕМЫ", "section": "РАЗДЕЛ", "presentation": "презентация", "key_points": "Ключевые идеи", "details": "Важные аспекты", "part": "РАЗДЕЛ", "prepared": "Подготовил(а)", "summary": "Итоговые выводы", "thanks": "Спасибо за внимание!", "slide": "С Л А Й Д", "continued": "Продолжение", "image_label": "МЕСТО ДЛЯ ИЗОБРАЖЕНИЯ", "empty_title": "Дополнительный анализ", "empty_body": "В этом разделе обобщены важные аспекты темы."},
    "en": {"overview": "PRESENTATION", "overview_tag": "AGENDA · MAIN SECTIONS", "overview_title": "Presentation overview", "overview_list_heading": "MAIN TOPIC SECTIONS", "section": "SECTION", "presentation": "presentation", "key_points": "Key ideas", "details": "Important details", "part": "SECTION", "prepared": "Prepared by", "summary": "Key takeaways", "thanks": "Thank you for your attention!", "slide": "S L I D E", "continued": "Continued", "image_label": "IMAGE AREA", "empty_title": "Further analysis", "empty_body": "This section summarizes important aspects of the topic."},
    "tr": {"overview": "SUNUM", "overview_tag": "PLAN · ANA BÖLÜMLER", "overview_title": "Sunum içeriği", "overview_list_heading": "KONUNUN ANA BÖLÜMLERİ", "section": "BÖLÜM", "presentation": "sunumu", "key_points": "Temel fikirler", "details": "Önemli noktalar", "part": "BÖLÜM", "prepared": "Hazırlayan", "summary": "Genel sonuçlar", "thanks": "Dinlediğiniz için teşekkürler!", "slide": "S L A Y T", "continued": "Devamı", "image_label": "GÖRSEL ALANI", "empty_title": "Ek analiz", "empty_body": "Bu bölüm konunun önemli yönlerini özetler."},
    "de": {"overview": "PRÄSENTATION", "overview_tag": "AGENDA · HAUPTABSCHNITTE", "overview_title": "Präsentationsübersicht", "overview_list_heading": "ZENTRALE THEMENABSCHNITTE", "section": "ABSCHNITT", "presentation": "Präsentation", "key_points": "Kernaussagen", "details": "Wichtige Aspekte", "part": "ABSCHNITT", "prepared": "Erstellt von", "summary": "Wichtigste Erkenntnisse", "thanks": "Vielen Dank für Ihre Aufmerksamkeit!", "slide": "F O L I E", "continued": "Fortsetzung", "image_label": "BILD BEREICH", "empty_title": "Weitere Analyse", "empty_body": "Dieser Abschnitt fasst wichtige Aspekte des Themas zusammen."},
    "fr": {"overview": "PRÉSENTATION", "overview_tag": "PLAN · SECTIONS PRINCIPALES", "overview_title": "Sommaire de la présentation", "overview_list_heading": "SECTIONS PRINCIPALES DU SUJET", "section": "SECTION", "presentation": "présentation", "key_points": "Idées clés", "details": "Points importants", "part": "SECTION", "prepared": "Préparé par", "summary": "Conclusions essentielles", "thanks": "Merci de votre attention !", "slide": "D I A P O", "continued": "Suite", "image_label": "ZONE IMAGE", "empty_title": "Analyse complémentaire", "empty_body": "Cette section résume les aspects importants du sujet."},
}


def _rgb(value):
    return RGBColor(*value)


def _set_bg(slide, color):
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = _rgb(color)


def _shape(slide, x, y, w, h, color, kind=MSO_SHAPE.RECTANGLE, line_color=None, radius=None):
    sh = slide.shapes.add_shape(kind, Inches(x), Inches(y), Inches(w), Inches(h))
    sh.fill.solid()
    sh.fill.fore_color.rgb = _rgb(color)
    if line_color:
        sh.line.color.rgb = _rgb(line_color)
        sh.line.width = Pt(1)
    else:
        sh.line.fill.background()
    return sh


def _outline(slide, kind, x, y, w, h, color, width=2.0):
    """Transparent shape used for design-specific decorative motifs."""
    sh = slide.shapes.add_shape(kind, Inches(x), Inches(y), Inches(w), Inches(h))
    sh.fill.background()
    sh.line.color.rgb = _rgb(color)
    sh.line.width = Pt(width)
    return sh


def _cover_motif(slide, theme, style):
    """Corner motif that makes each of the six covers visually distinct."""
    accent = theme["accent"]
    try:
        if style == "bubbles":
            _outline(slide, MSO_SHAPE.OVAL, 11.55, 0.15, 1.35, 1.35, accent, 3)
            _outline(slide, MSO_SHAPE.OVAL, 12.35, 1.15, 0.72, 0.72, (214, 51, 193), 2.5)
        elif style == "hex":
            _outline(slide, MSO_SHAPE.HEXAGON, 11.75, 0.22, 1.3, 1.3, accent, 3)
            _shape(slide, 12.55, 6.28, 0.62, 0.62, accent)
        elif style == "shapes":
            _shape(slide, 11.95, 0.22, 1.0, 1.0, accent)
            _shape(slide, 12.35, 1.24, 0.6, 0.6, theme["soft"], kind=MSO_SHAPE.OVAL)
            _shape(slide, 12.85, 1.9, 0.3, 0.3, (26, 26, 26))
        elif style == "leaf":
            _outline(slide, MSO_SHAPE.OVAL, 11.55, 0.28, 1.35, 0.82, accent, 2.5)
            _outline(slide, MSO_SHAPE.OVAL, 12.15, 1.02, 0.78, 0.5, accent, 2)
        elif style == "frame":
            _outline(slide, MSO_SHAPE.RECTANGLE, 0.46, 0.44, 12.4, 6.62, accent, 1.5)
        else:  # arc
            _outline(slide, MSO_SHAPE.OVAL, 11.35, -0.65, 2.5, 2.5, accent, 3)
            _outline(slide, MSO_SHAPE.OVAL, 11.7, -0.3, 1.8, 1.8, (255, 255, 255), 1)
    except Exception as exc:
        print(f"[pptx] Cover motif skipped: {exc}", flush=True)


def _text(slide, x, y, w, h, value, size=18, color=(35, 46, 65), bold=False,
          align=PP_ALIGN.LEFT, font="Aptos", valign=MSO_ANCHOR.TOP, margin=0.06, italic=False):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.vertical_anchor = valign
    tf.margin_left = Inches(margin)
    tf.margin_right = Inches(margin)
    tf.margin_top = Inches(margin)
    tf.margin_bottom = Inches(margin)
    lines = str(value if value is not None else "").split("\n")
    for idx, line in enumerate(lines):
        p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(5)
        p.line_spacing = 1.08
        r = p.add_run()
        r.text = line
        r.font.name = font
        r.font.size = Pt(size)
        r.font.bold = bold
        r.font.italic = italic
        r.font.color.rgb = _rgb(color)
    return box


def _body_size(value, base=16):
    """Keep long AI paragraphs inside their card instead of overflowing it."""
    length = len(str(value or ""))
    if length > 1400:
        return 10
    if length > 1150:
        return 11
    if length > 900:
        return 12
    if length > 750:
        return 13
    if length > 450:
        # Six full sentences already fill the card at the base size.
        return max(12, base - 1)
    return base


def _safe_text_list(content):
    if isinstance(content, str):
        values = [x.strip(" •\t") for x in content.splitlines() if x.strip()]
    elif isinstance(content, (list, tuple)):
        values = [str(x).strip() for x in content if str(x).strip()]
    else:
        values = []
    return values


def _footer(slide, th, index, total, topic, subject, lang, dark=False, x=0.72, y=7.11,
            width=10.3, page_x=11.45, page_dark=None):
    labels = UI[lang]
    if dark:
        color = (221, 227, 238)
    elif sum(th["text"]) > 600:
        # Amber theme carries light body text because most of its pages are dark;
        # on its white pages the footer needs a readable grey instead.
        color = (110, 110, 110)
    else:
        color = th["secondary"]
    page_color = (221, 227, 238) if (page_dark if page_dark is not None else dark) else color
    short_topic = str(topic or "").strip()
    if len(short_topic) > 45:
        short_topic = short_topic[:42].rstrip() + "…"
    footer_text = f"{short_topic} · {subject} {labels['presentation']}"
    topic_box = _text(slide, x, y, width, 0.22, footer_text, size=8, color=color, margin=0)
    page_box = _text(slide, page_x, y - 0.02, 1.1, 0.25, f"{index:02d} / {total:02d}", size=9,
                      color=page_color, align=PP_ALIGN.RIGHT, margin=0)
    # Marked so the mirrored repeat of a layout keeps the footer on its side.
    topic_box.name = "footer-topic"
    page_box.name = "footer-page"


def _darken_cover_image(path):
    """Crop a topic image to widescreen and darken it behind cover text."""
    from PIL import Image, ImageEnhance, ImageOps
    source = Image.open(path).convert("RGB")
    source = ImageOps.fit(source, (1600, 900), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    source = ImageEnhance.Brightness(source).enhance(0.40)
    out = io.BytesIO()
    source.save(out, format="JPEG", quality=88, optimize=True)
    out.seek(0)
    return out


def _fallback_visual_bytes(topic, lang, theme):
    """Abstract, theme-colored artwork used only when no real photo is available.

    No text is drawn: the picture is cropped differently by every template, so a
    geometric composition stays readable in any frame while the actual wording is
    always PowerPoint text on top of it.
    """
    from PIL import Image, ImageDraw
    width, height = 1600, 900
    cover = tuple(theme.get("cover", (20, 32, 50)))
    accent = tuple(theme.get("accent", (201, 162, 39)))
    soft = tuple(theme.get("soft", (240, 232, 220)))
    panel = tuple(theme.get("panel", (255, 255, 255)))

    canvas = Image.new("RGB", (width, height), cover)
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.ellipse((780, -320, 1820, 720), fill=accent + (70,))
    draw.ellipse((1030, -180, 1720, 510), outline=accent + (235,), width=12)
    draw.ellipse((1130, -80, 1600, 390), outline=panel + (110,), width=5)
    draw.polygon([(0, 900), (0, 640), (620, 900)], fill=soft + (38,))
    draw.rounded_rectangle((90, 96, 700, 804), radius=34, outline=accent + (150,), width=4)
    for i in range(4):
        cx, cy = 1150 + i * 96, 660 - i * 34
        draw.ellipse((cx, cy, cx + 22, cy + 22), fill=accent + (220,))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")
    out = io.BytesIO()
    canvas.save(out, format="JPEG", quality=90, optimize=True)
    return out.getvalue()


def _valid_image_source(source):
    """Return True only for decodable images, not merely non-empty files."""
    try:
        from PIL import Image
        if isinstance(source, (bytes, bytearray)):
            if len(source) < 1000:
                return False
            with Image.open(io.BytesIO(source)) as image:
                if image.width < 120 or image.height < 80:
                    return False
                image.verify()
            return True
        if isinstance(source, str) and os.path.isfile(source) and os.path.getsize(source) > 1000:
            with Image.open(source) as image:
                if image.width < 120 or image.height < 80:
                    return False
                image.verify()
            return True
    except Exception:
        return False
    return False


def _add_image_source(slide, source, x, y, width, height):
    """Add a filesystem or in-memory image source safely to a slide."""
    if isinstance(source, (bytes, bytearray)):
        stream = io.BytesIO(source)
        stream.seek(0)
        return slide.shapes.add_picture(stream, Inches(x), Inches(y), width=Inches(width), height=Inches(height))
    return slide.shapes.add_picture(source, Inches(x), Inches(y), width=Inches(width), height=Inches(height))

# ===========================================================================
#  SHABLONLASHTIRILGAN SLAYDLAR
#  Har bir dizayn (modern/neon/amber/pop/nature/elegant) o'z muqovasi, reja
#  slaydi, 5 xil kontent joylashuvi va yakuniy slaydiga ega. Ya'ni shablon
#  tanlanganda faqat rang emas, rasm va matn joylashuvi ham o'zgaradi.
# ===========================================================================
_IMG_CACHE: dict[Any, bytes] = {}


def _crop_stream(source, w_in, h_in, circle=False):
    """Cover-crop an image to the target box so photos are never stretched."""
    key = (source if isinstance(source, str) else hash(bytes(source)), round(w_in, 2), round(h_in, 2), circle)
    cached = _IMG_CACHE.get(key)
    if cached:
        return io.BytesIO(cached)
    from PIL import Image, ImageDraw, ImageOps
    if isinstance(source, (bytes, bytearray)):
        image = Image.open(io.BytesIO(bytes(source)))
    else:
        image = Image.open(source)
    px_w = max(480, int(w_in * 210))
    px_h = max(270, int(h_in * 210))
    image = image.convert("RGBA" if circle else "RGB")
    image = ImageOps.fit(image, (px_w, px_h), method=Image.Resampling.LANCZOS, centering=(0.5, 0.4))
    out = io.BytesIO()
    if circle:
        mask = Image.new("L", (px_w, px_h), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, px_w, px_h), fill=255)
        image.putalpha(mask)
        image.save(out, format="PNG", optimize=True)
    else:
        image.save(out, format="JPEG", quality=86, optimize=True)
    data = out.getvalue()
    if len(_IMG_CACHE) > 60:
        _IMG_CACHE.clear()
    _IMG_CACHE[key] = data
    return io.BytesIO(data)


def _photo(slide, th, lang, x, y, w, h, source=None, circle=False, rounded=False, frame=None,
           label=True):
    """Place a photo cropped to the box; otherwise draw the localized image slot."""
    pic = None
    if source and _valid_image_source(source):
        try:
            pic = slide.shapes.add_picture(_crop_stream(source, w, h, circle=circle),
                                           Inches(x), Inches(y), Inches(w), Inches(h))
        except Exception as exc:
            print(f"[pptx] image skipped: {exc}", flush=True)
    if pic is None:
        kind = MSO_SHAPE.OVAL if circle else (MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE)
        _shape(slide, x, y, w, h, th.get("soft", th["panel"]), kind=kind)
        if label and w >= 1.15:
            _text(slide, x + 0.1, y + h / 2 - 0.16, max(0.6, w - 0.2), 0.32, UI[lang]["image_label"],
                  size=9, color=th.get("secondary", th["text"]), bold=True,
                  align=PP_ALIGN.CENTER, margin=0)
    if frame:
        kind = MSO_SHAPE.OVAL if circle else (MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE)
        _outline(slide, kind, x, y, w, h, frame, 1.6)
    return pic


def _entry(item, lang):
    title = str((item or {}).get("title") or UI[lang]["empty_title"]).strip()
    content = _safe_text_list((item or {}).get("content")) or [UI[lang]["empty_body"]]
    return title, content


def _head(slide, th, lang, item, index, subject, color, rule, x=0.78, y=0.46,
          w=11.8, big=30, eyebrow=None):
    title, content = _entry(item, lang)
    _text(slide, x, y, w, 0.26, f"{UI[lang]['section']} {max(1, index - 2):02d} · {subject.upper()}",
          size=9, color=eyebrow or rule, bold=True, margin=0)
    tsize = big if len(title) < 42 else max(18, int(big * 0.8)) if len(title) < 72 else max(16, int(big * 0.64))
    _text(slide, x, y + 0.34, w, 0.95, title, size=tsize, color=color, bold=True,
          font="Aptos Display", margin=0)
    _shape(slide, x, y + 1.34, 0.9, 0.045, rule)
    return title, content


def _points(content, marker="•", limit=5):
    return "\n\n".join(f"{marker} {v}" for v in content[:limit])


# ============================== MUQOVALAR ==============================
def _cover_modern(slide, th, lang, topic, subject, author, total, image, description):
    labels = UI[lang]
    _set_bg(slide, (255, 252, 247))
    _shape(slide, 7.05, 0.55, 6.3, 6.6, th["cover"])
    _photo(slide, th, lang, 7.3, 0.8, 5.8, 6.1, image)
    _shape(slide, 0.72, 0.72, 0.55, 0.045, th["accent"])
    _text(slide, 1.42, 0.6, 5.2, 0.28, subject.upper(), size=10, color=th["accent"], bold=True, margin=0)
    title_size = 40 if len(topic) < 34 else 33 if len(topic) < 58 else 26
    _text(slide, 0.72, 1.5, 6.1, 2.5, topic, size=title_size, color=th["primary"], bold=True,
          font="Georgia", margin=0)
    _shape(slide, 0.72, 4.22, 1.55, 0.05, th["accent"])
    _text(slide, 0.72, 4.5, 5.85, 1.0, (description or labels["empty_body"])[:200],
          size=14, color=th["text"], margin=0)
    _shape(slide, 0.72, 5.72, 2.5, 0.46, th["accent"], kind=MSO_SHAPE.ROUNDED_RECTANGLE)
    _text(slide, 0.72, 5.82, 2.5, 0.28, labels["presentation"].upper(), size=10, color=(255, 255, 255),
          bold=True, align=PP_ALIGN.CENTER, margin=0)
    if author:
        _text(slide, 0.72, 6.44, 5.9, 0.3, f"{labels['prepared']}: {author}", size=11,
              color=th["secondary"], margin=0)
    _outline(slide, MSO_SHAPE.OVAL, 6.35, 5.95, 0.6, 0.6, th["accent"], 2)
    _outline(slide, MSO_SHAPE.OVAL, 6.14, 6.2, 0.32, 0.32, th["accent"], 1.5)


def _cover_neon(slide, th, lang, topic, subject, author, total, image, description):
    labels = UI[lang]
    _set_bg(slide, th["cover"])
    band = _shape(slide, 8.55, -2.4, 7.4, 12.6, th["accent"])
    band.rotation = -21
    glow = _shape(slide, 10.9, -2.8, 3.1, 12.8, (198, 56, 214))
    glow.rotation = -21
    _photo(slide, th, lang, 7.55, 1.05, 4.6, 5.45, image, rounded=True, frame=th["accent"])
    _outline(slide, MSO_SHAPE.OVAL, 12.2, 5.95, 1.0, 1.0, th["accent"], 2)
    _outline(slide, MSO_SHAPE.OVAL, 6.4, 6.45, 0.55, 0.55, th["accent"], 1.8)
    _text(slide, 0.88, 0.9, 6.3, 0.3, f"{subject.upper()} · {labels['overview']}", size=10,
          color=th["accent"], bold=True, margin=0)
    title_size = 42 if len(topic) < 32 else 34 if len(topic) < 58 else 27
    _text(slide, 0.86, 1.55, 6.5, 2.6, topic, size=title_size, color=(255, 255, 255), bold=True,
          font="Aptos Display", margin=0)
    _text(slide, 0.88, 4.42, 6.0, 0.95, (description or labels["empty_body"])[:170], size=13,
          color=th["secondary"], margin=0)
    _shape(slide, 0.88, 5.52, 2.35, 0.5, th["accent"], kind=MSO_SHAPE.ROUNDED_RECTANGLE)
    _text(slide, 0.88, 5.64, 2.35, 0.28, labels["overview"], size=10, color=th["cover"],
          bold=True, align=PP_ALIGN.CENTER, margin=0)
    if author:
        _text(slide, 0.88, 6.35, 5.9, 0.3, f"{labels['prepared']}: {author}", size=11,
              color=th["secondary"], margin=0)


def _cover_amber(slide, th, lang, topic, subject, author, total, image, description):
    labels = UI[lang]
    _set_bg(slide, th["cover"])
    corner = _shape(slide, 11.15, -3.3, 4.6, 4.6, th["accent"])
    corner.rotation = 45
    _photo(slide, th, lang, 7.85, 1.5, 4.3, 4.3, image)
    _outline(slide, MSO_SHAPE.HEXAGON, 7.68, 1.33, 4.65, 4.65, th["accent"], 4)
    _shape(slide, 0.88, 0.92, 0.9, 0.09, th["accent"])
    _text(slide, 0.88, 1.12, 6.4, 0.28, f"{subject.upper()} // {labels['overview']}", size=10,
          color=th["accent"], bold=True, margin=0)
    title_size = 41 if len(topic) < 32 else 33 if len(topic) < 58 else 26
    _text(slide, 0.88, 1.62, 6.4, 2.7, topic, size=title_size, color=(255, 255, 255), bold=True,
          font="Aptos Display", margin=0)
    _text(slide, 0.88, 4.55, 6.0, 0.95, (description or labels["empty_body"])[:175], size=13,
          color=th["text"], margin=0)
    _shape(slide, 0.88, 5.62, 2.4, 0.5, th["accent"], kind=MSO_SHAPE.ROUNDED_RECTANGLE)
    _text(slide, 0.88, 5.74, 2.4, 0.28, labels["overview"], size=10, color=th["cover"],
          bold=True, align=PP_ALIGN.CENTER, margin=0)
    if author:
        _text(slide, 0.88, 6.4, 5.9, 0.3, f"{labels['prepared']}: {author}", size=11,
              color=th["secondary"], margin=0)
    _shape(slide, 12.4, 1.6, 0.45, 0.45, th["accent"])


def _cover_pop(slide, th, lang, topic, subject, author, total, image, description):
    labels = UI[lang]
    _set_bg(slide, (250, 250, 246))
    _shape(slide, 9.55, 0.0, 3.78, 3.05, th["accent"])
    _shape(slide, 8.55, 3.25, 2.6, 2.1, (247, 183, 51))
    _shape(slide, 11.55, 4.05, 1.78, 1.78, th["soft"], kind=MSO_SHAPE.OVAL)
    _shape(slide, 12.05, 0.55, 1.1, 1.1, (26, 26, 26))
    _photo(slide, th, lang, 9.95, 3.85, 2.55, 2.55, image, circle=True)
    _shape(slide, 0.78, 1.05, 0.9, 0.12, th["accent"])
    _text(slide, 0.78, 1.32, 6.6, 0.28, f"{subject.upper()} · {labels['overview']}", size=10,
          color=th["accent"], bold=True, margin=0)
    title_size = 46 if len(topic) < 30 else 37 if len(topic) < 54 else 29
    _text(slide, 0.76, 1.95, 7.55, 2.6, topic, size=title_size, color=(26, 26, 26), bold=True,
          font="Aptos Display", margin=0)
    _shape(slide, 0.78, 4.35, 1.7, 0.16, th["accent"])
    _text(slide, 0.78, 4.72, 6.6, 1.0, (description or labels["empty_body"])[:180], size=14,
          color=th["text"], margin=0)
    if author:
        _text(slide, 0.78, 6.25, 6.6, 0.3, f"{labels['prepared']}: {author}", size=11,
              color=th["secondary"], margin=0)
    _shape(slide, 0.78, 5.95, 2.3, 0.5, (26, 26, 26), kind=MSO_SHAPE.ROUNDED_RECTANGLE)
    _text(slide, 0.78, 6.07, 2.3, 0.28, labels["overview"], size=10, color=(255, 255, 255),
          bold=True, align=PP_ALIGN.CENTER, margin=0)


def _cover_nature(slide, th, lang, topic, subject, author, total, image, description):
    labels = UI[lang]
    _set_bg(slide, (250, 248, 243))
    _outline(slide, MSO_SHAPE.OVAL, 8.05, 0.35, 4.9, 4.9, th["primary"], 3)
    _photo(slide, th, lang, 8.75, 1.05, 3.9, 3.9, image, circle=True, frame=th["accent"])
    _outline(slide, MSO_SHAPE.OVAL, 11.9, 4.75, 1.05, 1.05, th["accent"], 2.5)
    _shape(slide, 0.8, 0.95, 1.1, 0.06, th["primary"])
    _text(slide, 0.8, 1.15, 6.4, 0.28, f"{subject.upper()} · {labels['overview']}", size=10,
          color=th["primary"], bold=True, margin=0)
    title_size = 41 if len(topic) < 32 else 33 if len(topic) < 58 else 26
    _text(slide, 0.8, 1.7, 6.6, 2.6, topic, size=title_size, color=th["primary"], bold=True,
          font="Georgia", margin=0)
    _text(slide, 0.8, 4.55, 6.2, 1.0, (description or labels["empty_body"])[:185], size=14,
          color=th["text"], margin=0)
    _shape(slide, 0.8, 5.68, 2.45, 0.5, th["primary"], kind=MSO_SHAPE.ROUNDED_RECTANGLE)
    _text(slide, 0.8, 5.8, 2.45, 0.28, labels["overview"], size=10, color=(255, 255, 255),
          bold=True, align=PP_ALIGN.CENTER, margin=0)
    if author:
        _text(slide, 0.8, 6.42, 6.0, 0.3, f"{labels['prepared']}: {author}", size=11,
              color=th["secondary"], margin=0)
    for i in range(3):
        _shape(slide, 12.05 + i * 0.34, 6.28 - i * 0.16, 0.16, 0.16, th["primary"], kind=MSO_SHAPE.OVAL)


def _cover_elegant(slide, th, lang, topic, subject, author, total, image, description):
    labels = UI[lang]
    _set_bg(slide, (249, 246, 242))
    _outline(slide, MSO_SHAPE.RECTANGLE, 0.5, 0.46, 12.33, 6.58, th["accent"], 1.2)
    _shape(slide, 8.15, 1.5, 4.35, 4.35, th["soft"])
    _photo(slide, th, lang, 7.95, 1.3, 4.35, 4.35, image, frame=th["accent"])
    _text(slide, 0.95, 1.35, 6.6, 0.26, subject.upper(), size=9, color=th["accent"], bold=True, margin=0)
    title_size = 42 if len(topic) < 32 else 34 if len(topic) < 58 else 27
    _text(slide, 0.95, 1.78, 6.55, 2.6, topic, size=title_size, color=th["primary"], bold=True,
          font="Georgia", margin=0)
    _shape(slide, 0.97, 4.42, 1.35, 0.04, th["accent"])
    _text(slide, 0.95, 4.68, 6.35, 1.0, (description or labels["empty_body"])[:190], size=13,
          color=th["text"], margin=0)
    if author:
        _text(slide, 0.95, 6.15, 6.4, 0.3, f"{labels['prepared']}: {author}", size=10,
              color=th["secondary"], margin=0)
    _text(slide, 0.95, 6.55, 6.4, 0.28, labels["presentation"], size=9, color=th["secondary"],
          margin=0, italic=True)


# ================================ REJA ================================
def _agenda_modern(slide, th, lang, topic, subject, entries, total):
    labels = UI[lang]
    _set_bg(slide, (255, 252, 247))
    _text(slide, 0.8, 0.85, 4.3, 0.28, labels["overview_tag"], size=10, color=th["accent"], bold=True, margin=0)
    _text(slide, 0.78, 1.22, 4.15, 1.75, labels["overview_title"], size=30, color=th["primary"],
          bold=True, font="Georgia", margin=0)
    _shape(slide, 0.8, 3.05, 1.45, 0.05, th["accent"])
    _outline(slide, MSO_SHAPE.OVAL, 0.9, 4.7, 1.35, 1.35, th["accent"], 2)
    _outline(slide, MSO_SHAPE.OVAL, 2.15, 5.6, 0.62, 0.62, th["accent"], 1.5)
    _text(slide, 0.8, 6.4, 3.9, 0.3, f"{len(entries) + 3:02d} · {labels['slide']}", size=9,
          color=th["secondary"], margin=0)
    _shape(slide, 5.15, 1.1, 7.5, 5.6, th["panel"], line_color=th["line"])
    _shape(slide, 5.15, 1.1, 0.16, 5.6, th["accent"])
    _text(slide, 5.6, 1.35, 6.7, 0.3, labels["overview_list_heading"], size=11, color=th["primary"], bold=True, margin=0)
    agenda = _agenda_entries(entries)
    for i, (title, _) in enumerate(agenda):
        y = 1.95 + i * 0.75
        _text(slide, 5.6, y, 0.5, 0.34, f"{i + 1}", size=17, color=th["accent"], bold=True, margin=0)
        _text(slide, 6.2, y, 6.0, 0.34, title, size=13, color=th["text"], margin=0)
        _shape(slide, 5.6, y + 0.45, 6.6, 0.012, th["line"])


def _agenda_neon(slide, th, lang, topic, subject, entries, total):
    labels = UI[lang]
    _set_bg(slide, th["cover"])
    _shape(slide, 0.0, 0.0, 13.333, 0.09, th["accent"])
    _text(slide, 0.85, 0.72, 11.7, 0.3, labels["overview_tag"], size=10, color=th["accent"], bold=True, margin=0)
    _text(slide, 0.82, 1.05, 11.7, 0.8, labels["overview_title"], size=30, color=(255, 255, 255),
          bold=True, font="Aptos Display", margin=0)
    agenda = _agenda_entries(entries)[:6]
    n = max(1, len(agenda))
    gap = 0.35
    w = (11.75 - gap * (n - 1)) / n
    for i, (title, _) in enumerate(agenda):
        x = 0.8 + i * (w + gap)
        _shape(slide, x, 2.35, w, 3.85, th["panel"], kind=MSO_SHAPE.ROUNDED_RECTANGLE, line_color=th["line"])
        _shape(slide, x, 2.35, w, 0.1, th["accent"])
        _text(slide, x + 0.25, 2.65, 0.9, 0.5, f"{i + 1:02d}", size=22, color=th["accent"], bold=True, margin=0)
        _text(slide, x + 0.25, 3.35, w - 0.5, 2.6, title, size=13, color=(240, 243, 255), bold=True, margin=0)
    _text(slide, 0.85, 6.6, 11.5, 0.3, f"{subject} · {labels['presentation']}", size=9, color=th["secondary"], margin=0)


def _agenda_amber(slide, th, lang, topic, subject, entries, total):
    labels = UI[lang]
    _set_bg(slide, (250, 250, 250))
    _shape(slide, 0.0, 0.0, 13.333, 1.35, th["cover"])
    _text(slide, 0.85, 0.72, 9.0, 0.4, labels["overview_title"], size=26, color=(255, 255, 255),
          bold=True, font="Aptos Display", margin=0)
    _text(slide, 10.2, 0.8, 2.4, 0.3, f"{subject.upper()}", size=9, color=th["accent"], bold=True,
          align=PP_ALIGN.RIGHT, margin=0)
    agenda = _agenda_entries(entries)[:6]
    for i, (title, _) in enumerate(agenda):
        y = 1.75 + i * 0.82
        _shape(slide, 0.9, y, 0.62, 0.62, th["accent"], kind=MSO_SHAPE.HEXAGON)
        _text(slide, 0.9, y + 0.16, 0.62, 0.3, f"{i + 1}", size=13, color=th["cover"], bold=True,
              align=PP_ALIGN.CENTER, margin=0)
        _shape(slide, 1.75, y - 0.02, 10.6, 0.66, (255, 255, 255), line_color=(226, 226, 226))
        _text(slide, 2.0, y + 0.12, 10.1, 0.4, title, size=14, color=(34, 34, 34), margin=0)
    _shape(slide, 12.45, 1.62, 0.42, 0.42, th["accent"])


def _agenda_pop(slide, th, lang, topic, subject, entries, total):
    labels = UI[lang]
    _set_bg(slide, (250, 250, 246))
    _shape(slide, 0.0, 0.0, 0.42, 7.5, th["accent"])
    _shape(slide, 10.9, 1.0, 2.44, 2.44, (247, 183, 51))
    _shape(slide, 12.0, 5.55, 0.95, 0.95, th["soft"], kind=MSO_SHAPE.OVAL)
    _text(slide, 0.9, 0.8, 5.7, 1.4, labels["overview_title"], size=32, color=(26, 26, 26),
          bold=True, font="Aptos Display", margin=0)
    _shape(slide, 0.92, 2.25, 1.5, 0.14, th["accent"])
    agenda = _agenda_entries(entries)[:6]
    for i, (title, _) in enumerate(agenda):
        y = 2.62 + i * 0.66
        _shape(slide, 0.9, y, 0.34, 0.34, [(230, 51, 35), (247, 183, 51), (26, 26, 26), (255, 178, 196), (230, 51, 35), (247, 183, 51)][i % 6])
        _text(slide, 1.45, y - 0.02, 8.9, 0.4, title, size=14, color=(26, 26, 26), bold=i % 2 == 0, margin=0)


def _agenda_nature(slide, th, lang, topic, subject, entries, total):
    labels = UI[lang]
    _set_bg(slide, (250, 248, 243))
    _shape(slide, 0.0, 0.0, 4.35, 7.5, th["primary"])
    _outline(slide, MSO_SHAPE.OVAL, 1.55, 5.15, 2.1, 2.1, th["accent"], 2)
    _text(slide, 0.75, 1.05, 3.3, 0.3, labels["overview_tag"], size=9, color=th["accent"], bold=True, margin=0)
    _text(slide, 0.72, 1.45, 3.35, 1.7, labels["overview_title"], size=25, color=(255, 255, 255),
          bold=True, font="Georgia", margin=0)
    _shape(slide, 0.75, 3.35, 1.1, 0.05, th["accent"])
    _text(slide, 0.75, 3.62, 3.2, 0.3, f"{len(entries) + 3:02d} {labels['slide']}", size=9,
          color=(210, 228, 214), margin=0)
    agenda = _agenda_entries(entries)[:6]
    for i, (title, _) in enumerate(agenda):
        y = 1.15 + i * 0.86
        _text(slide, 4.95, y, 0.55, 0.36, f"{i + 1:02d}", size=15, color=th["accent"], bold=True, margin=0)
        _text(slide, 5.6, y, 7.0, 0.36, title, size=14, color=th["text"], margin=0)
        if i < len(agenda) - 1:
            _shape(slide, 4.95, y + 0.62, 7.4, 0.015, th["line"])


def _agenda_elegant(slide, th, lang, topic, subject, entries, total):
    labels = UI[lang]
    _set_bg(slide, (249, 246, 242))
    _shape(slide, 12.0, 0.0, 1.333, 7.5, th["soft"])
    _text(slide, 0.85, 1.1, 7.0, 0.28, labels["overview_tag"], size=9, color=th["accent"], bold=True, margin=0)
    _text(slide, 0.82, 1.5, 7.4, 1.1, labels["overview_title"], size=30, color=th["primary"],
          bold=True, font="Georgia", margin=0)
    _shape(slide, 0.85, 2.72, 11.1, 0.02, th["line"])
    agenda = _agenda_entries(entries)[:6]
    for i, (title, _) in enumerate(agenda):
        y = 3.05 + i * 0.64
        _text(slide, 0.85, y, 0.6, 0.3, f"{i + 1:02d}", size=11, color=th["accent"], bold=True, margin=0)
        _text(slide, 1.6, y - 0.04, 8.4, 0.36, title, size=14, color=th["text"], margin=0)
        _shape(slide, 1.6, y + 0.33, 10.35, 0.012, th["line"])


def _agenda_entries(entries):
    valid = [e for e in entries if isinstance(e, dict) and str(e.get("title", "")).strip()]
    if len(valid) > 6:
        idxs = [round(i * (len(valid) - 1) / 5) for i in range(6)]
        valid = [valid[i] for i in idxs]
    rows = []
    for item in valid:
        title = str(item.get("title", "")).strip()
        rows.append((title if len(title) <= 90 else title[:87].rstrip() + "…", item))
    return rows


def _overview_slide(prs, theme, lang, topic, subject, entries, total):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    builder = {"arc": _agenda_modern, "bubbles": _agenda_neon, "hex": _agenda_amber,
               "shapes": _agenda_pop, "leaf": _agenda_nature, "frame": _agenda_elegant}.get(
        theme.get("decorate"), _agenda_modern)
    builder(slide, theme, lang, str(topic), str(subject), entries or [], total)
    _footer(slide, theme, 2, total, topic, subject, lang,
            dark=theme.get("decorate") == "bubbles")
    return slide


# ============================ KONTENT SLAYDLAR ============================
def _m_photo_right(slide, th, lang, item, index, total, image, gallery, topic, subject):
    _set_bg(slide, (255, 252, 247))
    _shape(slide, 0.0, 0.0, 13.333, 0.06, th["accent"])
    title, content = _head(slide, th, lang, item, index, subject, th["primary"], th["accent"], big=28)
    body = _points(content)
    _text(slide, 0.8, 2.05, 6.5, 4.3, body, size=_body_size(body, base=15), color=th["text"])
    _shape(slide, 7.55, 1.2, 5.0, 5.5, th["cover"])
    _photo(slide, th, lang, 7.78, 1.42, 4.55, 5.05, image)
    _shape(slide, 0.8, 6.55, 1.9, 0.34, th["accent"], kind=MSO_SHAPE.ROUNDED_RECTANGLE)
    _text(slide, 0.8, 6.6, 1.9, 0.24, UI[lang]["details"].upper(), size=8, color=(255, 255, 255),
          bold=True, align=PP_ALIGN.CENTER, margin=0)
    _footer(slide, th, index, total, topic, subject, lang)


def _m_panel_left(slide, th, lang, item, index, total, image, gallery, topic, subject):
    title, content = _entry(item, lang)
    _set_bg(slide, (255, 252, 247))
    _photo(slide, th, lang, 0.0, 0.0, 6.15, 7.5, image)
    _shape(slide, 6.05, 0.0, 7.29, 7.5, th["primary"])
    _text(slide, 6.55, 0.85, 6.2, 0.26, f"{UI[lang]['section']} {max(1, index - 2):02d}", size=9,
          color=th["accent"], bold=True, margin=0)
    tsize = 30 if len(title) < 40 else 24 if len(title) < 70 else 19
    _text(slide, 6.52, 1.25, 6.2, 1.5, title, size=tsize, color=(255, 255, 255), bold=True,
          font="Aptos Display", margin=0)
    _shape(slide, 6.55, 2.9, 0.9, 0.045, th["accent"])
    body = _points(content, "—")
    _text(slide, 6.55, 3.2, 6.2, 3.4, body, size=_body_size(body, base=14), color=(246, 239, 233))
    _footer(slide, th, index, total, topic, subject, lang, dark=True, x=6.55, y=7.11,
            width=5.6, page_x=11.45, page_dark=True)


def _m_band(slide, th, lang, item, index, total, image, gallery, topic, subject):
    _set_bg(slide, (255, 252, 247))
    title, content = _head(slide, th, lang, item, index, subject, th["primary"], th["accent"], big=26)
    mid = max(1, (len(content) + 1) // 2)
    left, right = content[:mid], content[mid:] or content[:1]
    _text(slide, 0.8, 1.98, 6.0, 2.1, _points(left), size=_body_size(_points(left), base=13), color=th["text"])
    _text(slide, 6.95, 1.98, 5.55, 2.1, _points(right), size=_body_size(_points(right), base=13), color=th["text"])
    _photo(slide, th, lang, 0.8, 4.28, 11.75, 2.62, image)
    _shape(slide, 10.0, 4.28, 2.55, 0.55, th["accent"])
    _text(slide, 10.0, 4.4, 2.55, 0.3, subject.upper()[:26], size=9, color=(255, 255, 255), bold=True,
          align=PP_ALIGN.CENTER, margin=0)
    _footer(slide, th, index, total, topic, subject, lang)


def _m_feature(slide, th, lang, item, index, total, image, gallery, topic, subject):
    _set_bg(slide, (255, 252, 247))
    title, content = _entry(item, lang)
    _photo(slide, th, lang, 0.8, 1.9, 6.35, 4.55, image)
    _shape(slide, 0.8, 1.9, 0.16, 4.55, th["accent"])
    _text(slide, 7.55, 0.7, 5.0, 0.26, f"{UI[lang]['section']} {max(1, index - 2):02d} · {subject.upper()}",
          size=9, color=th["accent"], bold=True, margin=0)
    _text(slide, 7.52, 1.05, 4.95, 1.2, title, size=26 if len(title) < 44 else 20,
          color=th["primary"], bold=True, font="Aptos Display", margin=0)
    body = _points(content[:4], "▸")
    _text(slide, 7.55, 2.55, 4.95, 3.7, body, size=_body_size(body, base=13), color=th["text"])
    _footer(slide, th, index, total, topic, subject, lang)


def _m_numbered(slide, th, lang, item, index, total, image, gallery, topic, subject):
    _set_bg(slide, (255, 252, 247))
    title, content = _head(slide, th, lang, item, index, subject, th["primary"], th["accent"], big=28)
    rows = content[:4]
    for i, value in enumerate(rows):
        y = 2.0 + i * 1.18
        _shape(slide, 0.82, y, 10.9, 0.98, (255, 255, 255), line_color=th["line"])
        _shape(slide, 0.82, y, 0.11, 0.98, th["accent"])
        _text(slide, 1.15, y + 0.12, 0.7, 0.5, f"{i + 1:02d}", size=20, color=th["accent"], bold=True, margin=0)
        _text(slide, 2.0, y + 0.1, 9.4, 0.78, value, size=_body_size(value, base=14), color=th["text"])
    _photo(slide, th, lang, 11.95, 2.0, 0.9, 4.1, image, rounded=True, label=False)
    _footer(slide, th, index, total, topic, subject, lang)


def _n_glass_right(slide, th, lang, item, index, total, image, gallery, topic, subject):
    _set_bg(slide, th["cover"])
    _photo(slide, th, lang, 7.9, 1.15, 4.75, 5.2, image, rounded=True, frame=th["accent"])
    _outline(slide, MSO_SHAPE.OVAL, 0.55, 5.9, 0.9, 0.9, th["accent"], 2)
    title, content = _head(slide, th, lang, item, index, subject, (255, 255, 255), th["accent"], w=6.7, big=27)
    body = _points(content)
    _text(slide, 0.82, 2.05, 6.75, 4.3, body, size=_body_size(body, base=14), color=th["on_dark"])
    _footer(slide, th, index, total, topic, subject, lang, dark=True)


def _n_photo_left(slide, th, lang, item, index, total, image, gallery, topic, subject):
    title, content = _entry(item, lang)
    _set_bg(slide, th["cover"])
    _photo(slide, th, lang, 0.0, 0.0, 5.9, 7.5, image)
    _shape(slide, 5.8, 0.0, 7.54, 7.5, th["panel"])
    _shape(slide, 5.8, 0.0, 0.1, 7.5, th["accent"])
    _text(slide, 6.3, 0.95, 6.5, 0.26, f"{UI[lang]['section']} {max(1, index - 2):02d}", size=9,
          color=th["accent"], bold=True, margin=0)
    _text(slide, 6.28, 1.3, 6.55, 1.3, title, size=27 if len(title) < 46 else 21,
          color=(244, 246, 255), bold=True, font="Aptos Display", margin=0)
    _shape(slide, 6.3, 2.72, 0.9, 0.05, th["accent"])
    body = _points(content[:4], "▪")
    _text(slide, 6.3, 3.0, 6.5, 3.4, body, size=_body_size(body, base=13), color=th["on_dark"])
    _footer(slide, th, index, total, topic, subject, lang, dark=True, x=6.3, y=7.11,
            width=5.7, page_x=11.45, page_dark=True)


def _n_full_band(slide, th, lang, item, index, total, image, gallery, topic, subject):
    title, content = _entry(item, lang)
    _set_bg(slide, th["cover"])
    _photo(slide, th, lang, 0.0, 0.0, 13.333, 4.0, image)
    _shape(slide, 0.0, 3.65, 13.333, 3.85, th["panel"])
    _shape(slide, 0.0, 3.65, 13.333, 0.07, th["accent"])
    _text(slide, 0.85, 3.95, 11.6, 0.26, f"{UI[lang]['section']} {max(1, index - 2):02d} · {subject.upper()}",
          size=9, color=th["accent"], bold=True, margin=0)
    _text(slide, 0.82, 4.28, 11.6, 0.7, title, size=25 if len(title) < 50 else 20, color=(255, 255, 255),
          bold=True, font="Aptos Display", margin=0)
    mid = max(1, (len(content) + 1) // 2)
    _text(slide, 0.85, 5.1, 5.8, 1.85, _points(content[:mid], "•"), size=11, color=th["on_dark"])
    _text(slide, 6.95, 5.1, 5.6, 1.85, _points(content[mid:] or content[:1], "•"), size=11, color=th["on_dark"])
    _footer(slide, th, index, total, topic, subject, lang, dark=True)


def _n_cards(slide, th, lang, item, index, total, image, gallery, topic, subject):
    _set_bg(slide, th["cover"])
    _outline(slide, MSO_SHAPE.OVAL, 10.6, -0.9, 3.4, 3.4, th["accent"], 2)
    title, content = _head(slide, th, lang, item, index, subject, (255, 255, 255), th["accent"], big=26)
    rows = content[:3]
    n = max(1, len(rows))
    gap = 0.3
    w = (11.75 - gap * (n - 1)) / n
    for i, value in enumerate(rows):
        x = 0.8 + i * (w + gap)
        _shape(slide, x, 2.2, w, 3.1, th["panel"], kind=MSO_SHAPE.ROUNDED_RECTANGLE, line_color=th["accent"])
        _shape(slide, x + 0.28, 2.48, 0.55, 0.55, th["accent"], kind=MSO_SHAPE.OVAL)
        _text(slide, x + 0.28, 2.6, 0.55, 0.3, f"{i + 1}", size=13, color=th["cover"], bold=True,
              align=PP_ALIGN.CENTER, margin=0)
        _text(slide, x + 0.28, 3.2, w - 0.56, 1.9, value, size=_body_size(value, base=12), color=th["on_dark"])
    _footer(slide, th, index, total, topic, subject, lang, dark=True)


def _n_orbit(slide, th, lang, item, index, total, image, gallery, topic, subject):
    _set_bg(slide, th["cover"])
    _outline(slide, MSO_SHAPE.OVAL, 0.75, 1.35, 4.85, 4.85, th["line"], 1.5)
    _outline(slide, MSO_SHAPE.OVAL, 1.05, 1.65, 4.25, 4.25, th["accent"], 2.5)
    _photo(slide, th, lang, 1.5, 2.1, 3.35, 3.35, image, circle=True)
    title, content = _entry(item, lang)
    _text(slide, 6.35, 0.75, 6.4, 0.26, f"{UI[lang]['section']} {max(1, index - 2):02d} · {subject.upper()}",
          size=9, color=th["accent"], bold=True, margin=0)
    _text(slide, 6.32, 1.1, 6.4, 1.1, title, size=26 if len(title) < 46 else 20,
          color=(255, 255, 255), bold=True, font="Aptos Display", margin=0)
    body = _points(content[:4], "◆")
    _text(slide, 6.35, 2.45, 6.35, 3.9, body, size=_body_size(body, base=13), color=th["on_dark"])
    _footer(slide, th, index, total, topic, subject, lang, dark=True)


def _a_light_blocks(slide, th, lang, item, index, total, image, gallery, topic, subject):
    _set_bg(slide, (250, 250, 250))
    _shape(slide, 0.0, 0.0, 0.16, 7.5, th["accent"])
    title, content = _head(slide, th, lang, item, index, subject, (26, 26, 26), th["accent"], big=28)
    body = _points(content)
    _text(slide, 0.85, 2.0, 6.6, 4.3, body, size=_body_size(body, base=14), color=(44, 44, 44))
    _shape(slide, 8.05, 1.55, 4.4, 3.55, (28, 28, 28))
    _photo(slide, th, lang, 7.85, 1.33, 4.4, 3.55, image)
    _shape(slide, 12.0, 4.55, 0.58, 0.58, th["accent"])
    _text(slide, 7.85, 5.35, 4.4, 0.5, subject.upper()[:30], size=9, color=(120, 120, 120), bold=True, margin=0)
    _footer(slide, th, index, total, topic, subject, lang)


def _a_hex_photo(slide, th, lang, item, index, total, image, gallery, topic, subject):
    _set_bg(slide, th["cover"])
    _photo(slide, th, lang, 0.95, 1.55, 4.55, 4.55, image)
    _outline(slide, MSO_SHAPE.HEXAGON, 0.78, 1.38, 4.9, 4.9, th["accent"], 4)
    title, content = _entry(item, lang)
    _text(slide, 6.5, 0.8, 6.2, 0.26, f"{UI[lang]['section']} {max(1, index - 2):02d}", size=9,
          color=th["accent"], bold=True, margin=0)
    _text(slide, 6.47, 1.15, 6.25, 1.2, title, size=27 if len(title) < 44 else 21,
          color=(255, 255, 255), bold=True, font="Aptos Display", margin=0)
    _shape(slide, 6.5, 2.5, 0.9, 0.06, th["accent"])
    body = _points(content[:4], "▪")
    _text(slide, 6.5, 2.8, 6.2, 3.6, body, size=_body_size(body, base=13), color=th["text"])
    _footer(slide, th, index, total, topic, subject, lang, dark=True)


def _a_chart(slide, th, lang, item, index, total, image, gallery, topic, subject):
    """Numbered key-point cards beside a squared photo, amber/black styling."""
    _set_bg(slide, (250, 250, 250))
    title, content = _head(slide, th, lang, item, index, subject, (26, 26, 26), th["accent"], big=27)
    rows = content[:3]
    for i, value in enumerate(rows):
        y = 2.05 + i * 1.45
        _shape(slide, 0.9, y, 7.35, 1.2, (255, 255, 255), line_color=(226, 226, 226))
        _shape(slide, 0.9, y, 0.12, 1.2, th["accent"])
        _text(slide, 1.2, y + 0.16, 0.7, 0.32, f"{i + 1:02d}", size=15, color=th["accent"], bold=True, margin=0)
        _text(slide, 1.95, y + 0.12, 6.1, 0.95, value, size=_body_size(value, base=12), color=(44, 44, 44))
    _photo(slide, th, lang, 8.65, 1.95, 3.85, 3.85, image)
    _shape(slide, 8.85, 5.75, 3.45, 0.16, th["accent"])
    _footer(slide, th, index, total, topic, subject, lang)


def _a_duo_cards(slide, th, lang, item, index, total, image, gallery, topic, subject):
    _set_bg(slide, th["cover"])
    _photo(slide, th, lang, 0.0, 0.0, 13.333, 2.35, image)
    _shape(slide, 0.0, 2.35, 13.333, 0.09, th["accent"])
    title, content = _entry(item, lang)
    _text(slide, 0.85, 2.62, 11.6, 0.55, title, size=24 if len(title) < 50 else 19, color=(255, 255, 255),
          bold=True, font="Aptos Display", margin=0)
    mid = max(1, (len(content) + 1) // 2)
    for col, group in enumerate((content[:mid], content[mid:] or content[:1])):
        x = 0.85 + col * 5.95
        _shape(slide, x, 3.4, 5.6, 2.85, th["panel"], line_color=th["accent"])
        _shape(slide, x, 3.4, 5.6, 0.1, th["accent"])
        body = _points(group[:3], "▪")
        _text(slide, x + 0.25, 3.66, 5.1, 2.4, body, size=_body_size(body, base=12), color=(46, 46, 46))
    _footer(slide, th, index, total, topic, subject, lang, dark=True)


def _a_number_rows(slide, th, lang, item, index, total, image, gallery, topic, subject):
    _set_bg(slide, (250, 250, 250))
    title, content = _head(slide, th, lang, item, index, subject, (26, 26, 26), th["accent"], big=27)
    rows = content[:4]
    for i, value in enumerate(rows):
        y = 2.05 + i * 1.12
        _shape(slide, 0.9, y + 0.06, 0.72, 0.72, th["accent"], kind=MSO_SHAPE.ROUNDED_RECTANGLE)
        _text(slide, 0.9, y + 0.24, 0.72, 0.34, f"{i + 1}", size=14, color=(26, 26, 26), bold=True,
              align=PP_ALIGN.CENTER, margin=0)
        _text(slide, 1.9, y, 6.1, 0.8, value, size=_body_size(value, base=13), color=(44, 44, 44))
        _shape(slide, 1.9, y + 0.86, 6.1, 0.012, (228, 228, 228))
    _photo(slide, th, lang, 8.55, 1.85, 3.95, 3.95, image)
    _shape(slide, 8.75, 5.55, 3.6, 0.16, th["accent"])
    _footer(slide, th, index, total, topic, subject, lang)


def _p_split_blocks(slide, th, lang, item, index, total, image, gallery, topic, subject):
    _set_bg(slide, (250, 250, 246))
    _shape(slide, 0.0, 0.0, 0.38, 7.5, th["accent"])
    title, content = _head(slide, th, lang, item, index, subject, (26, 26, 26), th["accent"], big=30)
    body = _points(content, "●")
    _text(slide, 0.85, 2.0, 6.2, 4.2, body, size=_body_size(body, base=14), color=(30, 30, 30))
    _photo(slide, th, lang, 8.15, 1.45, 4.3, 3.55, image, frame=th["accent"])
    _shape(slide, 7.85, 3.85, 1.45, 1.45, th["soft"], kind=MSO_SHAPE.OVAL)
    _shape(slide, 12.05, 4.95, 0.9, 0.9, (247, 183, 51))
    _footer(slide, th, index, total, topic, subject, lang)


def _p_red_panel(slide, th, lang, item, index, total, image, gallery, topic, subject):
    title, content = _entry(item, lang)
    _set_bg(slide, (250, 250, 246))
    _photo(slide, th, lang, 0.0, 0.0, 6.15, 7.5, image)
    _shape(slide, 6.05, 0.0, 7.29, 7.5, th["accent"])
    _shape(slide, 6.05, 0.0, 7.29, 0.18, (247, 183, 51))
    _text(slide, 6.5, 0.9, 6.3, 0.26, f"{UI[lang]['section']} {max(1, index - 2):02d}", size=9,
          color=(255, 255, 255), bold=True, margin=0)
    _text(slide, 6.47, 1.25, 6.35, 1.3, title, size=28 if len(title) < 44 else 22,
          color=(255, 255, 255), bold=True, font="Aptos Display", margin=0)
    _shape(slide, 6.5, 2.7, 1.2, 0.1, (247, 183, 51))
    body = _points(content[:4], "•")
    _text(slide, 6.5, 3.0, 6.3, 3.4, body, size=_body_size(body, base=13), color=(255, 255, 255))
    _footer(slide, th, index, total, topic, subject, lang, dark=True, x=6.5, y=7.11,
            width=6.0, page_x=11.45, page_dark=True)


def _p_grid_cards(slide, th, lang, item, index, total, image, gallery, topic, subject):
    _set_bg(slide, (250, 250, 246))
    _shape(slide, 0.0, 0.0, 13.333, 0.14, th["accent"])
    title, content = _head(slide, th, lang, item, index, subject, (26, 26, 26), th["accent"], big=26)
    rows = content[:4]
    colors = [(230, 51, 35), (247, 183, 51), (26, 26, 26), (255, 178, 196)]
    for i, value in enumerate(rows):
        col, row = i % 2, i // 2
        x = 0.85 + col * 5.95
        y = 2.05 + row * 1.9
        _shape(slide, x, y, 5.6, 1.65, (255, 255, 255), line_color=(232, 232, 228))
        _shape(slide, x, y, 0.14, 1.65, colors[i % 4])
        _text(slide, x + 0.35, y + 0.16, 4.9, 1.3, value, size=_body_size(value, base=12), color=(30, 30, 30))
    _footer(slide, th, index, total, topic, subject, lang)


def _p_circle_feature(slide, th, lang, item, index, total, image, gallery, topic, subject):
    _set_bg(slide, (250, 250, 246))
    _photo(slide, th, lang, 0.85, 1.35, 4.5, 4.5, image, circle=True, frame=th["accent"])
    _shape(slide, 5.0, 5.35, 0.55, 0.55, (247, 183, 51), kind=MSO_SHAPE.OVAL)
    _shape(slide, 0.4, 6.3, 1.0, 1.0, th["soft"], kind=MSO_SHAPE.OVAL)
    title, content = _entry(item, lang)
    _text(slide, 6.35, 0.8, 6.2, 0.26, f"{UI[lang]['section']} {max(1, index - 2):02d} · {subject.upper()}",
          size=9, color=th["accent"], bold=True, margin=0)
    _text(slide, 6.32, 1.15, 6.3, 1.2, title, size=28 if len(title) < 44 else 22,
          color=(26, 26, 26), bold=True, font="Aptos Display", margin=0)
    _shape(slide, 6.35, 2.55, 1.1, 0.12, th["accent"])
    body = _points(content[:4], "—")
    _text(slide, 6.35, 2.9, 6.25, 3.5, body, size=_body_size(body, base=13), color=(30, 30, 30))
    _footer(slide, th, index, total, topic, subject, lang)


def _p_bar_statement(slide, th, lang, item, index, total, image, gallery, topic, subject):
    _set_bg(slide, (250, 250, 246))
    title, content = _entry(item, lang)
    _shape(slide, 0.0, 1.55, 13.333, 1.85, (26, 26, 26))
    _shape(slide, 0.0, 1.55, 1.1, 1.85, th["accent"])
    _text(slide, 1.35, 1.85, 11.0, 1.25, title, size=30 if len(title) < 44 else 23,
          color=(255, 255, 255), bold=True, font="Aptos Display", margin=0)
    mid = max(1, (len(content) + 1) // 2)
    _text(slide, 0.85, 3.75, 6.0, 2.7, _points(content[:mid], "•"), size=_body_size(_points(content[:mid]), base=13), color=(30, 30, 30))
    _text(slide, 7.0, 3.75, 5.5, 2.7, _points(content[mid:] or content[:1], "•"), size=11, color=(30, 30, 30))
    _shape(slide, 11.35, 0.55, 1.5, 0.5, (247, 183, 51))
    _footer(slide, th, index, total, topic, subject, lang)


def _g_rounded_photo(slide, th, lang, item, index, total, image, gallery, topic, subject):
    _set_bg(slide, (250, 248, 243))
    _shape(slide, 0.0, 0.0, 13.333, 0.07, th["primary"])
    title, content = _head(slide, th, lang, item, index, subject, th["primary"], th["accent"], big=28)
    body = _points(content, "•")
    _text(slide, 0.82, 2.0, 6.5, 4.3, body, size=_body_size(body, base=14), color=th["text"])
    _photo(slide, th, lang, 7.85, 1.3, 4.55, 4.5, image, rounded=True)
    _outline(slide, MSO_SHAPE.ROUNDED_RECTANGLE, 7.62, 1.52, 4.55, 4.5, th["primary"], 1.4)
    _shape(slide, 11.0, 6.15, 1.35, 0.16, th["accent"])
    _footer(slide, th, index, total, topic, subject, lang)


def _g_two_cards(slide, th, lang, item, index, total, image, gallery, topic, subject):
    _set_bg(slide, (250, 248, 243))
    title, content = _head(slide, th, lang, item, index, subject, th["primary"], th["accent"], big=27)
    mid = max(1, (len(content) + 1) // 2)
    left, right = content[:mid], content[mid:] or content[:1]
    height = min(4.0, 1.15 + 0.95 * max(len(left), len(right)))
    for col, (heading, group) in enumerate(((UI[lang]["key_points"], left),
                                           (UI[lang]["details"], right))):
        x = 0.85 + col * 5.95
        _shape(slide, x, 2.0, 5.6, height, (255, 255, 255) if col else th["soft"],
               kind=MSO_SHAPE.ROUNDED_RECTANGLE, line_color=th["line"])
        _shape(slide, x + 0.3, 2.28, 0.14, 0.5, th["accent"])
        _text(slide, x + 0.6, 2.2, 4.7, 0.4, heading, size=15, color=th["primary"], bold=True, margin=0)
        body = _points(group[:3], "▪")
        _text(slide, x + 0.32, 2.85, 5.0, height - 1.0, body, size=_body_size(body, base=12), color=th["text"])
    _footer(slide, th, index, total, topic, subject, lang)


def _g_band_caption(slide, th, lang, item, index, total, image, gallery, topic, subject):
    _set_bg(slide, (250, 248, 243))
    title, content = _entry(item, lang)
    _text(slide, 0.82, 0.72, 11.6, 0.8, title, size=26 if len(title) < 46 else 20, color=th["primary"],
          bold=True, font="Georgia", margin=0)
    _shape(slide, 0.85, 1.55, 1.0, 0.05, th["accent"])
    _photo(slide, th, lang, 0.82, 1.85, 11.7, 3.15, image, rounded=True)
    _shape(slide, 0.95, 4.55, 3.3, 0.45, th["accent"], kind=MSO_SHAPE.ROUNDED_RECTANGLE)
    _text(slide, 0.95, 4.64, 3.3, 0.28, subject.upper()[:34], size=9, color=(255, 255, 255), bold=True,
          align=PP_ALIGN.CENTER, margin=0)
    mid = max(1, (len(content) + 1) // 2)
    _text(slide, 0.85, 5.28, 5.75, 1.7, _points(content[:mid], "•"), size=11, color=th["text"])
    _text(slide, 6.95, 5.28, 5.5, 1.7, _points(content[mid:] or content[:1], "•"), size=11, color=th["text"])
    _footer(slide, th, index, total, topic, subject, lang)


def _g_insight(slide, th, lang, item, index, total, image, gallery, topic, subject):
    _set_bg(slide, th["primary"])
    _outline(slide, MSO_SHAPE.OVAL, 9.55, -1.0, 4.6, 4.6, th["accent"], 2)
    _outline(slide, MSO_SHAPE.OVAL, 10.3, -0.25, 3.1, 3.1, th["accent"], 1.2)
    title, content = _entry(item, lang)
    _text(slide, 0.9, 0.8, 7.0, 0.3, UI[lang]["key_points"].upper(), size=10, color=th["accent"], bold=True, margin=0)
    _text(slide, 0.88, 1.25, 8.6, 1.5, title, size=32 if len(title) < 40 else 24, color=(255, 255, 255),
          bold=True, font="Georgia", margin=0)
    _shape(slide, 0.9, 2.95, 2.2, 0.05, th["accent"])
    _text(slide, 0.9, 3.25, 7.9, 2.0, content[0], size=17, color=(236, 244, 238), margin=0)
    body = _points(content[1:4], "•")
    _text(slide, 0.9, 5.35, 7.6, 1.6, body, size=11, color=(206, 222, 210))
    _photo(slide, th, lang, 9.0, 3.55, 3.3, 3.3, image, circle=True, frame=th["accent"])
    _footer(slide, th, index, total, topic, subject, lang, dark=True)


def _g_circle_stats(slide, th, lang, item, index, total, image, gallery, topic, subject):
    _set_bg(slide, (250, 248, 243))
    _photo(slide, th, lang, 1.05, 1.7, 4.2, 4.2, image, circle=True, frame=th["accent"])
    _outline(slide, MSO_SHAPE.OVAL, 0.75, 1.4, 4.8, 4.8, th["line"], 1.4)
    title, content = _entry(item, lang)
    _text(slide, 6.2, 0.8, 6.3, 0.26, f"{UI[lang]['section']} {max(1, index - 2):02d} · {subject.upper()}",
          size=9, color=th["primary"], bold=True, margin=0)
    _text(slide, 6.18, 1.15, 6.4, 1.2, title, size=27 if len(title) < 44 else 21, color=th["primary"],
          bold=True, font="Georgia", margin=0)
    rows = content[:3]
    for i, value in enumerate(rows):
        y = 2.65 + i * 1.3
        _shape(slide, 6.2, y, 5.9, 1.05, (255, 255, 255), kind=MSO_SHAPE.ROUNDED_RECTANGLE, line_color=th["line"])
        _shape(slide, 6.2, y, 0.12, 1.05, th["accent"])
        _text(slide, 6.52, y + 0.1, 5.35, 0.85, value, size=_body_size(value, base=11), color=th["text"])
    _footer(slide, th, index, total, topic, subject, lang)


def _e_photo_offset(slide, th, lang, item, index, total, image, gallery, topic, subject):
    _set_bg(slide, (249, 246, 242))
    title, content = _head(slide, th, lang, item, index, subject, th["primary"], th["accent"], big=28)
    body = _points(content)
    _text(slide, 0.85, 2.0, 6.6, 4.3, body, size=_body_size(body, base=14), color=th["text"])
    _shape(slide, 8.3, 1.65, 3.95, 3.95, th["soft"])
    _photo(slide, th, lang, 8.05, 1.4, 3.95, 3.95, image, frame=th["accent"])
    _footer(slide, th, index, total, topic, subject, lang)


def _e_centered(slide, th, lang, item, index, total, image, gallery, topic, subject):
    _set_bg(slide, (249, 246, 242))
    title, content = _entry(item, lang)
    _text(slide, 1.2, 0.85, 10.9, 0.85, title, size=30 if len(title) < 42 else 23, color=th["primary"],
          bold=True, font="Georgia", align=PP_ALIGN.CENTER, margin=0)
    _shape(slide, 5.95, 1.85, 1.4, 0.03, th["accent"])
    mid = max(1, (len(content) + 1) // 2)
    _text(slide, 1.0, 2.2, 5.3, 2.4, _points(content[:mid], "—"), size=_body_size(_points(content[:mid]), base=12), color=th["text"])
    _text(slide, 6.9, 2.2, 5.3, 2.4, _points(content[mid:] or content[:1], "—"), size=11, color=th["text"])
    _photo(slide, th, lang, 1.0, 4.9, 11.3, 1.95, image)
    _footer(slide, th, index, total, topic, subject, lang)


def _e_plate(slide, th, lang, item, index, total, image, gallery, topic, subject):
    title, content = _entry(item, lang)
    _set_bg(slide, (249, 246, 242))
    _photo(slide, th, lang, 0.0, 0.0, 7.0, 7.5, image)
    _shape(slide, 6.15, 1.0, 6.75, 5.5, (255, 255, 255), line_color=th["line"])
    _shape(slide, 6.15, 1.0, 0.1, 5.5, th["accent"])
    _text(slide, 6.6, 1.4, 6.0, 0.26, f"{UI[lang]['section']} {max(1, index - 2):02d}", size=9,
          color=th["accent"], bold=True, margin=0)
    _text(slide, 6.57, 1.72, 6.0, 1.2, title, size=26 if len(title) < 44 else 20, color=th["primary"],
          bold=True, font="Georgia", margin=0)
    _shape(slide, 6.6, 3.05, 0.9, 0.03, th["accent"])
    body = _points(content[:4], "—")
    _text(slide, 6.6, 3.3, 5.95, 3.0, body, size=_body_size(body, base=12), color=th["text"])
    _footer(slide, th, index, total, topic, subject, lang, dark=False, x=6.6, y=7.11,
            width=5.9, page_x=11.45, page_dark=False)


def _e_quote(slide, th, lang, item, index, total, image, gallery, topic, subject):
    _set_bg(slide, (249, 246, 242))
    _shape(slide, 0.0, 0.0, 0.35, 7.5, th["soft"])
    title, content = _entry(item, lang)
    _text(slide, 1.35, 1.35, 8.4, 0.3, f"{UI[lang]['section']} {max(1, index - 2):02d} · {subject.upper()}",
          size=9, color=th["accent"], bold=True, margin=0)
    _text(slide, 1.32, 1.75, 8.6, 1.9, title, size=33 if len(title) < 40 else 25, color=th["primary"],
          bold=True, font="Georgia", margin=0)
    _shape(slide, 1.35, 3.85, 1.8, 0.03, th["accent"])
    _text(slide, 1.35, 4.15, 8.0, 2.1, content[0], size=15, color=th["text"], italic=True, margin=0)
    _photo(slide, th, lang, 10.1, 2.35, 2.5, 2.5, image, circle=True, frame=th["accent"])
    _footer(slide, th, index, total, topic, subject, lang)


def _e_cards(slide, th, lang, item, index, total, image, gallery, topic, subject):
    _set_bg(slide, (249, 246, 242))
    title, content = _head(slide, th, lang, item, index, subject, th["primary"], th["accent"], big=27)
    rows = content[:4]
    for i, value in enumerate(rows):
        col, row = i % 2, i // 2
        x = 0.85 + col * 5.95
        y = 2.05 + row * 1.95
        _shape(slide, x, y, 5.6, 1.7, (255, 255, 255), line_color=th["line"])
        _text(slide, x + 0.35, y + 0.16, 0.8, 0.3, f"{i + 1:02d}", size=11, color=th["accent"], bold=True, margin=0)
        _shape(slide, x + 0.35, y + 0.5, 4.9, 0.015, th["line"])
        _text(slide, x + 0.35, y + 0.65, 4.9, 0.9, value, size=_body_size(value, base=11), color=th["text"])
    _footer(slide, th, index, total, topic, subject, lang)


CONTENT_LAYOUTS = {
    "modern": [_m_photo_right, _m_panel_left, _m_band, _m_feature, _m_numbered],
    "neon": [_n_glass_right, _n_photo_left, _n_full_band, _n_cards, _n_orbit],
    "amber": [_a_light_blocks, _a_hex_photo, _a_chart, _a_duo_cards, _a_number_rows],
    "pop": [_p_split_blocks, _p_red_panel, _p_grid_cards, _p_circle_feature, _p_bar_statement],
    "nature": [_g_rounded_photo, _g_two_cards, _g_band_caption, _g_insight, _g_circle_stats],
    "elegant": [_e_photo_offset, _e_centered, _e_plate, _e_quote, _e_cards],
}


WATERMARK_TEXT = "@Talaba_AI_SlideBot orqali yaratildi"


def _watermark(slide, text=WATERMARK_TEXT):
    """Small credit line tucked into the bottom-right corner.

    It used to run across the whole bottom edge, where it landed on top of the
    design's own footer and page number and both lines became unreadable.
    """
    _text(slide, 9.6, 7.35, 3.55, 0.14, text, size=6, color=(170, 170, 170),
          align=PP_ALIGN.RIGHT, margin=0)


def _content_slide(prs, th, lang, item, index, total, design_key, images, topic, subject):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    variants = CONTENT_LAYOUTS.get(design_key) or CONTENT_LAYOUTS["modern"]
    n = max(0, index - 3)
    gallery = [src for src in (images or []) if _valid_image_source(src)]
    # images[0] is the cover photo, so body slides start one place later; otherwise
    # the cover picture reappears on the first content slide.
    image = gallery[(n + 1) % len(gallery)] if gallery else None
    variants[n % len(variants)](slide, th, lang, item or {}, index, total, image, gallery,
                                str(topic), str(subject))
    return slide


def _cover(prs, theme, lang, topic, subject, author, total, images=None, description=""):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    gallery = [src for src in (images or []) if _valid_image_source(src)]
    image = gallery[0] if gallery else _fallback_visual_bytes(topic, lang, theme)
    builder = {"arc": _cover_modern, "bubbles": _cover_neon, "hex": _cover_amber,
               "shapes": _cover_pop, "leaf": _cover_nature, "frame": _cover_elegant}.get(
        theme.get("decorate"), _cover_modern)
    builder(slide, theme, lang, str(topic), str(subject), str(author or "").strip(), total,
            image, str(description or ""))
    # A cover is not numbered: every design already ends the slide with its own
    # author/footer line, and a page number there collided with the artwork.
    return slide


# ============================== YAKUNIY SLAYDLAR ==============================
def _c_modern(slide, th, lang, topic, subject, recap, total):
    labels = UI[lang]
    _set_bg(slide, (255, 252, 247))
    _shape(slide, 0.0, 0.0, 0.14, 7.5, th["accent"])
    _shape(slide, 8.9, 0.0, 4.44, 7.5, th["primary"])
    _text(slide, 0.85, 0.9, 7.4, 0.3, labels["summary"].upper(), size=10, color=th["accent"], bold=True, margin=0)
    _text(slide, 0.82, 1.3, 7.5, 1.0, labels["summary"], size=30, color=th["primary"], bold=True, font="Georgia", margin=0)
    _shape(slide, 0.85, 2.45, 1.2, 0.05, th["accent"])
    for i, value in enumerate(recap[:4]):
        y = 2.85 + i * 0.85
        _text(slide, 0.85, y, 0.5, 0.34, f"{i + 1:02d}", size=13, color=th["accent"], bold=True, margin=0)
        _text(slide, 1.45, y - 0.03, 7.0, 0.72, value[:110], size=13, color=th["text"], margin=0)
    _text(slide, 9.2, 2.6, 3.8, 1.65, labels["thanks"], size=24, color=(255, 255, 255), bold=True,
          align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE, margin=0.05, font="Georgia")
    _shape(slide, 10.65, 4.45, 0.9, 0.04, th["accent"])
    _text(slide, 9.2, 4.7, 3.8, 0.6, str(topic)[:70], size=10, color=(240, 230, 222),
          align=PP_ALIGN.CENTER, margin=0.02)


def _c_neon(slide, th, lang, topic, subject, recap, total):
    labels = UI[lang]
    _set_bg(slide, th["cover"])
    band = _shape(slide, 9.5, -2.6, 6.2, 12.0, th["accent"])
    band.rotation = -24
    _shape(slide, 0.0, 0.0, 13.333, 0.1, th["accent"])
    _text(slide, 0.88, 1.0, 7.6, 0.3, labels["summary"].upper(), size=10, color=th["accent"], bold=True, margin=0)
    _text(slide, 0.85, 2.3, 8.1, 1.5, labels["thanks"], size=40, color=(255, 255, 255), bold=True,
          font="Aptos Display", margin=0)
    _text(slide, 0.88, 4.0, 7.2, 0.6, str(topic)[:90], size=13, color=th["secondary"], margin=0)
    _shape(slide, 0.88, 4.85, 2.0, 0.06, th["accent"])
    for i, value in enumerate(recap[:3]):
        _text(slide, 0.88, 5.15 + i * 0.5, 7.8, 0.42, f"◆ {value[:95]}", size=11, color=th["on_dark"], margin=0)


def _c_amber(slide, th, lang, topic, subject, recap, total):
    labels = UI[lang]
    _set_bg(slide, th["cover"])
    corner = _shape(slide, 10.6, 4.4, 4.4, 4.4, th["accent"])
    corner.rotation = 45
    _text(slide, 0.9, 0.9, 8.0, 0.3, labels["summary"].upper(), size=10, color=th["accent"], bold=True, margin=0)
    _text(slide, 0.88, 1.3, 8.4, 1.4, labels["thanks"], size=38, color=(255, 255, 255), bold=True,
          font="Aptos Display", margin=0)
    _shape(slide, 0.9, 2.85, 2.0, 0.1, th["accent"])
    for i, value in enumerate(recap[:4]):
        _text(slide, 0.9, 3.2 + i * 0.55, 9.4, 0.45, f"{i + 1:02d}  {value[:90]}", size=11,
              color=th["text"], margin=0)
    _text(slide, 0.9, 6.6, 8.0, 0.3, str(topic)[:80], size=9, color=th["secondary"], margin=0)


def _c_pop(slide, th, lang, topic, subject, recap, total):
    labels = UI[lang]
    _set_bg(slide, (250, 250, 246))
    _shape(slide, 9.6, 3.85, 3.7, 3.7, th["accent"], kind=MSO_SHAPE.OVAL)
    _shape(slide, 11.5, 0.4, 1.5, 1.5, (247, 183, 51))
    _shape(slide, 0.0, 0.0, 0.42, 7.5, th["accent"])
    _text(slide, 0.95, 0.9, 8.3, 0.3, labels["summary"].upper(), size=10, color=th["accent"], bold=True, margin=0)
    _text(slide, 0.92, 1.3, 8.6, 1.6, labels["thanks"], size=44, color=(26, 26, 26), bold=True,
          font="Aptos Display", margin=0)
    _shape(slide, 0.95, 2.95, 2.0, 0.16, th["accent"])
    for i, value in enumerate(recap[:4]):
        _text(slide, 0.95, 3.35 + i * 0.62, 8.2, 0.5, f"• {value[:95]}", size=12, color=(30, 30, 30), margin=0)
    _text(slide, 0.95, 6.6, 8.0, 0.3, str(topic)[:80], size=9, color=(120, 120, 120), margin=0)


def _c_nature(slide, th, lang, topic, subject, recap, total):
    labels = UI[lang]
    _set_bg(slide, th["primary"])
    _outline(slide, MSO_SHAPE.OVAL, 9.4, -1.2, 5.4, 5.4, th["accent"], 2)
    _outline(slide, MSO_SHAPE.OVAL, 10.25, -0.35, 3.7, 3.7, th["accent"], 1.2)
    _text(slide, 0.9, 0.95, 8.0, 0.3, labels["summary"].upper(), size=10, color=th["accent"], bold=True, margin=0)
    _text(slide, 0.88, 1.35, 8.4, 1.4, labels["thanks"], size=36, color=(255, 255, 255), bold=True,
          font="Georgia", margin=0)
    _shape(slide, 0.9, 2.88, 2.0, 0.05, th["accent"])
    for i, value in enumerate(recap[:4]):
        _text(slide, 0.9, 3.2 + i * 0.6, 9.0, 0.5, f"• {value[:95]}", size=12, color=(226, 240, 230), margin=0)
    _text(slide, 0.9, 6.6, 8.0, 0.3, str(topic)[:80], size=9, color=(190, 214, 196), margin=0)


def _c_elegant(slide, th, lang, topic, subject, recap, total):
    labels = UI[lang]
    _set_bg(slide, (249, 246, 242))
    _outline(slide, MSO_SHAPE.RECTANGLE, 0.5, 0.46, 12.33, 6.58, th["accent"], 1.2)
    _text(slide, 0.95, 1.15, 6.0, 0.3, labels["summary"].upper(), size=9, color=th["accent"], bold=True, margin=0)
    _text(slide, 0.92, 1.55, 8.0, 1.4, labels["thanks"], size=38, color=th["primary"], bold=True,
          font="Georgia", margin=0)
    _shape(slide, 0.95, 3.05, 2.2, 0.03, th["accent"])
    mid = max(1, (len(recap) + 1) // 2)
    _text(slide, 0.95, 3.35, 5.3, 2.3, _points(recap[:mid], "—"), size=11, color=th["text"])
    _text(slide, 6.9, 3.35, 5.3, 2.3, _points(recap[mid:] or recap[:1], "—"), size=11, color=th["text"])
    _text(slide, 0.95, 6.55, 11.4, 0.28, str(topic)[:90], size=9, color=th["secondary"], margin=0, italic=True)


CLOSING_LAYOUTS = {"arc": _c_modern, "bubbles": _c_neon, "hex": _c_amber,
                   "shapes": _c_pop, "leaf": _c_nature, "frame": _c_elegant}


def _closing_slide(prs, theme, lang, topic, subject, entries, total, credits=None):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    recap = []
    if entries and isinstance(entries[-1], dict):
        recap = _safe_text_list(entries[-1].get("content"))[:4]
    recap = [value if len(value) <= 110 else value[:107].rstrip() + "…" for value in recap] or [UI[lang]["empty_body"]]
    builder = CLOSING_LAYOUTS.get(theme.get("decorate"), _c_modern)
    builder(slide, theme, lang, str(topic), str(subject), recap, total)
    _credit_line(slide, lang, credits)
    return slide


def _image_credits(images):
    """Author/licence lines for the downloaded photos, written beside each file."""
    credits = []
    for source in images or []:
        try:
            text = Path(str(source) + ".credit").read_text(encoding="utf-8").strip()
        except (OSError, UnicodeError):
            continue
        text = " ".join(text.split())
        if text and text not in credits:
            credits.append(text)
    return credits


def _credit_line(slide, lang, credits):
    """Wikimedia Commons requires the photographer and licence be shown."""
    if not credits:
        return
    label = {"uz": "Rasmlar", "ru": "Изображения", "en": "Images", "tr": "Görseller",
             "de": "Bilder", "fr": "Images"}.get(str(lang).lower(), "Images")
    text = f"{label}: " + "; ".join(credits)
    if len(text) > 240:
        text = text[:237].rstrip() + "…"
    box = slide.shapes.add_textbox(Inches(0.55), Inches(6.9), Inches(12.2), Inches(0.42))
    frame = box.text_frame
    frame.word_wrap = True
    frame.margin_left = frame.margin_right = 0
    frame.margin_top = frame.margin_bottom = 0
    run = frame.paragraphs[0].add_run()
    run.text = text
    run.font.size = Pt(8)
    run.font.color.rgb = RGBColor(130, 140, 155)


def _new_presentation():
    """Use the supplied PPTX as a theme/layout source, not as a content source."""
    template_path = Path(__file__).resolve().parent / "templates" / "presentation_IT.pptx"
    if template_path.is_file():
        try:
            prs = Presentation(str(template_path))
            # Remove contaminated example slides while retaining theme, masters, and layouts.
            for slide_id in list(prs.slides._sldIdLst):
                rel_id = slide_id.rId
                prs.part.drop_rel(rel_id)
                prs.slides._sldIdLst.remove(slide_id)
            return prs
        except Exception:
            # Do not break generation if the supplied template is damaged.
            pass
    return Presentation()


def generate_pptx(topic: str, subject: str, lang: str, design_key: str, slide_count: int,
                  slides_content: list[dict[str, Any]] | None, images=None, author: str = ""):
    """Create a localized deck with cover, agenda, content, and closing slides.

    The requested slide count includes all four parts and is preserved exactly.
    ``slides_content`` should contain ``slide_count - 3`` body slides.
    """
    lc = str(lang or "en").lower()
    if lc not in UI:
        lc = "en"
    key = str(design_key or DESIGN_KEYS[0]).lower()
    if key not in THEMES:
        key = DESIGN_KEYS[0]
    try:
        requested = int(slide_count or 10)
    except (TypeError, ValueError):
        requested = 10
    # The requested slide count is honoured exactly (cover + agenda + body + closing).
    total = max(4, min(60, requested))
    body_count = total - 3

    prs = _new_presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    th = dict(THEMES[key])
    # Only real downloaded photos are used on content slides. When none are
    # available the layouts draw their labeled "image area" slot instead of a
    # blank dark plate, and the cover uses a themed abstract backdrop.
    image_sources = [source for source in (images or []) if _valid_image_source(source)]
    entries = list(slides_content or [])
    while len(entries) < body_count:
        n = len(entries) + 1
        title_fallback, body_fallback = _localized_fallback_entry(lc, n)
        entries.append({"title": title_fallback, "content": body_fallback})
    entries = entries[:body_count]
    desc = ""
    if entries:
        first_content = _safe_text_list(entries[0].get("content")) if isinstance(entries[0], dict) else []
        desc = first_content[0] if first_content else ""

    _cover(prs, th, lc, str(topic), str(subject), str(author or "").strip(), total,
           images=image_sources, description=desc)
    _overview_slide(prs, th, lc, str(topic), str(subject), entries, total)
    for i, item in enumerate(entries):
        item = item if isinstance(item, dict) else {}
        actual_slide_number = i + 3
        _content_slide(prs, th, lc, item, actual_slide_number, total, key, image_sources, str(topic), str(subject))
    _closing_slide(prs, th, lc, str(topic), str(subject), entries, total,
                   credits=_image_credits(image_sources))
    for slide in prs.slides:
        _watermark(slide)

    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    return buf


def _localized_fallback_entry(lang, index):
    """Never introduce English placeholder content into a non-English deck."""
    fallback = {
        "uz": (f"Qo‘shimcha tahlil {index}", ["Mavzuning asosiy jihatlari tahlil qilinadi.", "Muhim dalillar va misollar ko‘rib chiqiladi.", "Natijalar mavzu bilan bog‘liq holda umumlashtiriladi."]),
        "ru": (f"Дополнительный анализ {index}", ["Рассматриваются основные аспекты темы.", "Изучаются важные факты и примеры.", "Результаты обобщаются в контексте темы."]),
        "en": (f"Further analysis {index}", ["The main aspects of the topic are examined.", "Important facts and examples are considered.", "The findings are summarized in context."]),
        "tr": (f"Ek analiz {index}", ["Konunun temel yönleri incelenir.", "Önemli bilgiler ve örnekler ele alınır.", "Sonuçlar konu bağlamında özetlenir."]),
        "de": (f"Weitere Analyse {index}", ["Die wichtigsten Aspekte des Themas werden untersucht.", "Wichtige Fakten und Beispiele werden betrachtet.", "Die Ergebnisse werden zusammengefasst."]),
        "fr": (f"Analyse complémentaire {index}", ["Les principaux aspects du sujet sont examinés.", "Les faits et exemples importants sont étudiés.", "Les résultats sont résumés dans leur contexte."]),
    }
    return fallback.get(lang, fallback["en"])
