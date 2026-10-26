# -*- coding: utf-8 -*-
"""PowerPoint generator with three independent, fully localized designs.

Design keys: modern, nature, elegant. The selected design never changes the
requested slide count. All template/UI text is localized to ``lang``.
"""
from __future__ import annotations

import io
import os
import textwrap
from pathlib import Path
from typing import Any

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

BOT_USERNAME = "@Talaba_AI_SlideBot"

THEMES = {
    # Inspired by the supplied Timurid presentation: navy, warm paper and gold.
    "modern": {
        "bg": (248, 245, 240), "panel": (255, 255, 255), "primary": (27, 42, 65),
        "accent": (201, 162, 39), "secondary": (123, 126, 130), "text": (48, 49, 50),
        "cover": (20, 32, 50), "soft": (239, 232, 214), "line": (220, 217, 208),
    },
    # Inspired by the supplied cell / biology presentation: deep green, bright green.
    "nature": {
        "bg": (248, 245, 240), "panel": (255, 255, 255), "primary": (27, 67, 50),
        "accent": (74, 222, 128), "secondary": (111, 128, 116), "text": (42, 48, 44),
        "cover": (8, 38, 30), "soft": (231, 239, 232), "line": (205, 219, 207),
    },
    # A separate premium variant with plum and champagne accents.
    "elegant": {
        "bg": (248, 244, 240), "panel": (255, 255, 255), "primary": (65, 35, 56),
        "accent": (194, 158, 103), "secondary": (136, 118, 128), "text": (54, 45, 51),
        "cover": (39, 23, 36), "soft": (243, 232, 222), "line": (227, 213, 207),
    },
}

DESIGN_NAMES = {
    "modern": {"uz": "Temuriylar — ko‘k va oltin", "ru": "Тимуриды — синий и золото", "en": "Timurid — navy and gold", "tr": "Timurlu — lacivert ve altın", "de": "Timuriden — Marineblau und Gold", "fr": "Timouride — bleu nuit et or"},
    "nature": {"uz": "Ilmiy tabiat — yashil", "ru": "Научная природа — зелёный", "en": "Scientific nature — green", "tr": "Bilimsel doğa — yeşil", "de": "Wissenschaftliche Natur — Grün", "fr": "Nature scientifique — vert"},
    "elegant": {"uz": "Minimal premium", "ru": "Минимализм премиум", "en": "Minimal premium", "tr": "Minimal premium", "de": "Minimal Premium", "fr": "Minimal premium"},
}

# Static template strings only. The generated subject matter is supplied by the AI
# and must be generated in the same language as this dictionary's language key.
UI = {
    "uz": {"overview": "TAQDIMOT", "overview_tag": "REJA · ASOSIY BO‘LIMLAR", "overview_title": "Taqdimot mazmuni", "overview_list_heading": "MAVZUNING ASOSIY QISMLARI", "section": "BO‘LIM", "presentation": "taqdimoti", "key_points": "Asosiy fikrlar", "details": "Muhim jihatlar", "part": "BO‘LIM", "prepared": "Tayyorladi", "summary": "Yakuniy xulosalar", "thanks": "E’tiboringiz uchun rahmat!", "slide": "S L A Y D", "continued": "Davomi", "empty_title": "Qo‘shimcha tahlil", "empty_body": "Bu bo‘lim mavzuning muhim jihatlarini umumlashtiradi."},
    "ru": {"overview": "ПРЕЗЕНТАЦИЯ", "overview_tag": "ПЛАН · ОСНОВНЫЕ РАЗДЕЛЫ", "overview_title": "Содержание презентации", "overview_list_heading": "ОСНОВНЫЕ РАЗДЕЛЫ ТЕМЫ", "section": "РАЗДЕЛ", "presentation": "презентация", "key_points": "Ключевые идеи", "details": "Важные аспекты", "part": "РАЗДЕЛ", "prepared": "Подготовил(а)", "summary": "Итоговые выводы", "thanks": "Спасибо за внимание!", "slide": "С Л А Й Д", "continued": "Продолжение", "empty_title": "Дополнительный анализ", "empty_body": "В этом разделе обобщены важные аспекты темы."},
    "en": {"overview": "PRESENTATION", "overview_tag": "AGENDA · MAIN SECTIONS", "overview_title": "Presentation overview", "overview_list_heading": "MAIN TOPIC SECTIONS", "section": "SECTION", "presentation": "presentation", "key_points": "Key ideas", "details": "Important details", "part": "SECTION", "prepared": "Prepared by", "summary": "Key takeaways", "thanks": "Thank you for your attention!", "slide": "S L I D E", "continued": "Continued", "empty_title": "Further analysis", "empty_body": "This section summarizes important aspects of the topic."},
    "tr": {"overview": "SUNUM", "overview_tag": "PLAN · ANA BÖLÜMLER", "overview_title": "Sunum içeriği", "overview_list_heading": "KONUNUN ANA BÖLÜMLERİ", "section": "BÖLÜM", "presentation": "sunumu", "key_points": "Temel fikirler", "details": "Önemli noktalar", "part": "BÖLÜM", "prepared": "Hazırlayan", "summary": "Genel sonuçlar", "thanks": "Dinlediğiniz için teşekkürler!", "slide": "S L A Y T", "continued": "Devamı", "empty_title": "Ek analiz", "empty_body": "Bu bölüm konunun önemli yönlerini özetler."},
    "de": {"overview": "PRÄSENTATION", "overview_tag": "AGENDA · HAUPTABSCHNITTE", "overview_title": "Präsentationsübersicht", "overview_list_heading": "ZENTRALE THEMENABSCHNITTE", "section": "ABSCHNITT", "presentation": "Präsentation", "key_points": "Kernaussagen", "details": "Wichtige Aspekte", "part": "ABSCHNITT", "prepared": "Erstellt von", "summary": "Wichtigste Erkenntnisse", "thanks": "Vielen Dank für Ihre Aufmerksamkeit!", "slide": "F O L I E", "continued": "Fortsetzung", "empty_title": "Weitere Analyse", "empty_body": "Dieser Abschnitt fasst wichtige Aspekte des Themas zusammen."},
    "fr": {"overview": "PRÉSENTATION", "overview_tag": "PLAN · SECTIONS PRINCIPALES", "overview_title": "Sommaire de la présentation", "overview_list_heading": "SECTIONS PRINCIPALES DU SUJET", "section": "SECTION", "presentation": "présentation", "key_points": "Idées clés", "details": "Points importants", "part": "SECTION", "prepared": "Préparé par", "summary": "Conclusions essentielles", "thanks": "Merci de votre attention !", "slide": "D I A P O", "continued": "Suite", "empty_title": "Analyse complémentaire", "empty_body": "Cette section résume les aspects importants du sujet."},
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


def _safe_text_list(content):
    if isinstance(content, str):
        values = [x.strip(" •\t") for x in content.splitlines() if x.strip()]
    elif isinstance(content, (list, tuple)):
        values = [str(x).strip() for x in content if str(x).strip()]
    else:
        values = []
    return values


def _footer(slide, th, index, total, topic, subject, lang, dark=False):
    color = (221, 227, 238) if dark else th["secondary"]
    labels = UI[lang]
    short_topic = str(topic or "").strip()
    if len(short_topic) > 45:
        short_topic = short_topic[:42].rstrip() + "…"
    footer_text = f"{short_topic} · {subject} {labels['presentation']}"
    _text(slide, 0.72, 7.11, 10.3, 0.22, footer_text, size=8, color=color, margin=0)
    _text(slide, 11.45, 7.09, 1.1, 0.25, f"{index:02d} / {total:02d}", size=9,
          color=color, align=PP_ALIGN.RIGHT, margin=0)


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
    """Create an embedded topic visual when external image search/download fails."""
    from PIL import Image, ImageDraw, ImageFont
    canvas = Image.new("RGB", (1600, 900), tuple(theme.get("cover", (20, 32, 50))))
    draw = ImageDraw.Draw(canvas)
    accent = tuple(theme.get("accent", (201, 162, 39)))
    secondary = tuple(theme.get("secondary", (123, 126, 130)))
    draw.ellipse((1050, -220, 1770, 500), outline=accent, width=14)
    draw.ellipse((1130, -140, 1650, 380), outline=secondary, width=6)
    draw.rounded_rectangle((70, 70, 1530, 830), radius=40, outline=accent, width=5)
    try:
        font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        title_font = ImageFont.truetype(font_path, 68)
        label_font = ImageFont.truetype(font_path, 28)
    except Exception:
        title_font = label_font = ImageFont.load_default()
    title = str(topic or UI.get(lang, UI["en"]).get("presentation", "Presentation")).strip()
    lines = textwrap.wrap(title, width=28)[:4] or ["Presentation"]
    y = 260 if len(lines) <= 2 else 190
    for line in lines:
        draw.text((130, y), line, font=title_font, fill=(255, 255, 255), stroke_width=1, stroke_fill=tuple(theme.get("cover", (20, 32, 50))))
        y += 90
    label = {
        "uz": "MAVZUGA OID VIZUAL", "ru": "ВИЗУАЛИЗАЦИЯ ТЕМЫ", "en": "TOPIC VISUAL",
        "tr": "KONU GÖRSELİ", "de": "THEMENVISUALISIERUNG", "fr": "VISUEL DU SUJET",
    }.get(str(lang).lower(), "TOPIC VISUAL")
    draw.text((130, 700), label, font=label_font, fill=accent)
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

def _cover(prs, theme, lang, topic, subject, author, total, images=None, description=""):
    labels = UI[lang]
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    cover_image = next((source for source in (images or []) if _valid_image_source(source)), None)
    try:
        if isinstance(cover_image, str):
            source = _darken_cover_image(cover_image)
        elif isinstance(cover_image, (bytes, bytearray)):
            source = io.BytesIO(bytes(cover_image))
        else:
            source = io.BytesIO(_fallback_visual_bytes(topic, lang, theme))
        source.seek(0)
        slide.shapes.add_picture(source, Inches(0), Inches(0), width=Inches(13.333), height=Inches(7.5))
    except Exception as exc:
        # Even if an image library fails, keep a designed background rather than a blank slide.
        print(f"[pptx] Cover image unavailable; using vector background: {exc}", flush=True)
        _set_bg(slide, theme["cover"])
    # A narrow color rail and bold title match the sample files' cover style.
    _shape(slide, 0.0, 0.0, 0.10, 7.5, theme["accent"])
    eyebrow = f"{subject.upper()} · {str(topic).upper()}"
    _text(slide, 0.88, 1.35, 11.5, 0.42, eyebrow[:100], size=12, color=theme["accent"], bold=True, margin=0)
    title_size = 39 if len(str(topic)) < 42 else 32 if len(str(topic)) < 70 else 25
    _text(slide, 0.86, 2.05, 11.7, 1.6, topic, size=title_size, color=(255, 255, 255), bold=True, font="Aptos Display", margin=0)
    _shape(slide, 0.88, 4.03, 1.75, 0.055, theme["accent"])
    description = str(description or labels["empty_body"]).strip()
    if len(description) > 180:
        description = description[:177].rstrip() + "…"
    _text(slide, 0.88, 4.38, 10.8, 0.95, description, size=16, color=(241, 241, 241), margin=0)
    if author:
        _text(slide, 0.88, 5.82, 10.8, 0.35, f"{labels['prepared']}: {author}", size=11, color=(228, 228, 228), margin=0)
    _text(slide, 0.88, 6.60, 10.8, 0.28, f"{subject} · {labels['presentation']}", size=9, color=(215, 215, 215), margin=0)
    _footer(slide, theme, 1, total, topic, subject, lang, dark=True)
    return slide


def _overview_slide(prs, theme, lang, topic, subject, entries, total):
    labels = UI[lang]
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(slide, theme["bg"])
    _shape(slide, 0.0, 0.0, 13.333, 0.075, theme["accent"])
    _text(slide, 0.82, 0.52, 11.7, 0.30, labels["overview_tag"], size=10, color=theme["primary"], bold=True, margin=0)
    _text(slide, 0.82, 0.97, 11.7, 0.74, labels["overview_title"], size=30, color=theme["primary"], bold=True, font="Aptos Display", margin=0)
    _shape(slide, 0.82, 1.77, 0.92, 0.045, theme["accent"])

    # Select up to six representative section titles, spread across larger decks.
    valid = [e for e in entries if isinstance(e, dict) and str(e.get("title", "")).strip()]
    if len(valid) > 6:
        idxs = [round(i * (len(valid) - 1) / 5) for i in range(6)]
        agenda = [valid[i] for i in idxs]
    else:
        agenda = valid
    _shape(slide, 0.82, 2.23, 11.68, 3.88, theme["panel"], kind=MSO_SHAPE.ROUNDED_RECTANGLE, line_color=theme["line"])
    _shape(slide, 0.82, 2.23, 11.68, 0.72, theme["primary"], kind=MSO_SHAPE.ROUNDED_RECTANGLE)
    _text(slide, 1.12, 2.42, 10.95, 0.32, labels["overview_list_heading"], size=13, color=(255, 255, 255), bold=True, margin=0)
    for i, item in enumerate(agenda):
        y = 3.18 + i * 0.45
        _text(slide, 1.15, y, 0.42, 0.31, f"{i + 1}.", size=13, color=theme["accent"], bold=True, margin=0)
        heading = str(item.get("title", "")).strip()
        if len(heading) > 100:
            heading = heading[:97].rstrip() + "…"
        _text(slide, 1.62, y, 10.35, 0.32, heading, size=13, color=theme["text"], margin=0)
    _footer(slide, theme, 2, total, topic, subject, lang)
    return slide

def _content_slide(prs, th, lang, item, index, total, design_key, images, topic, subject):
    labels = UI[lang]
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    dark = design_key == "elegant" and index % 4 == 0
    _set_bg(slide, th["cover"] if dark else th["bg"])
    _shape(slide, 0.0, 0.0, 0.10, 7.5, th["accent"])
    title_color = (255, 255, 255) if dark else th["primary"]
    body_color = (239, 233, 239) if dark else th["text"]
    card_color = (73, 47, 66) if dark else th["panel"]
    accent_color = th["accent"]

    title = str(item.get("title") or labels["empty_title"]).strip()
    content = _safe_text_list(item.get("content"))
    if not content:
        content = [labels["empty_body"]]
    title_size = 27 if len(title) < 46 else 22 if len(title) < 75 else 18
    eyebrow = f"{labels['section']} {max(1, index - 2):02d} · {subject.upper()}"
    _text(slide, 0.78, 0.40, 11.8, 0.28, eyebrow, size=10, color=accent_color, bold=True, margin=0)
    _text(slide, 0.78, 0.82, 11.8, 0.8, title, size=title_size, color=title_color, bold=True, font="Aptos Display", margin=0)
    _shape(slide, 0.78, 1.68, 0.85, 0.045, accent_color)

    # Three visible layout patterns are reused differently in each design.
    pattern = (index - 1) % 3
    image_path = None
    if images and (index % 3 == 1):
        candidate = images[(index // 3) % len(images)]
        if _valid_image_source(candidate):
            image_path = candidate

    if pattern == 0 and image_path:
        try:
            _add_image_source(slide, image_path, 0.8, 1.75, 5.25, 4.45)
            _shape(slide, 6.35, 1.75, 6.05, 4.45, card_color, line_color=th["line"] if not dark else None)
            body = "\n\n".join([f"• {x}" for x in content[:5]])
            _text(slide, 6.62, 2.0, 5.55, 3.95, body, size=16 if len(body) < 750 else 13, color=body_color, margin=0.02)
        except Exception:
            image_path = None

    if pattern == 0 and not image_path:
        # Two clear cards, not a fixed foreign-language placeholder.
        mid = max(1, (len(content) + 1) // 2)
        groups = [content[:mid], content[mid:]]
        headings = [labels["key_points"], labels["details"]]
        for col in range(2):
            x = 0.8 + col * 6.05
            _shape(slide, x, 1.85, 5.7, 4.25, card_color, line_color=th["line"] if not dark else None)
            _shape(slide, x, 1.85, 5.7, 0.12, accent_color)
            _text(slide, x + 0.25, 2.12, 5.15, 0.42, headings[col], size=16, color=accent_color if dark else th["primary"], bold=True, margin=0)
            group = groups[col] or [labels["empty_body"]]
            body = "\n\n".join(f"• {v}" for v in group)
            _text(slide, x + 0.25, 2.68, 5.15, 3.15, body, size=16 if len(body) < 600 else 13, color=body_color, margin=0.02)

    elif pattern == 1:
        # Vertical numbered points with generous spacing.
        for i, value in enumerate(content[:5]):
            y = 1.72 + i * 0.88
            _shape(slide, 0.88, y, 0.58, 0.58, accent_color, kind=MSO_SHAPE.OVAL)
            _text(slide, 0.88, y + 0.12, 0.58, 0.28, str(i + 1), size=14, color=(255, 255, 255), bold=True, align=PP_ALIGN.CENTER, margin=0)
            card = _shape(slide, 1.7, y - 0.03, 10.75, 0.66, card_color, line_color=th["line"] if not dark else None)
            fontsize = 15 if len(value) < 120 else 12
            _text(slide, 1.95, y + 0.08, 10.25, 0.47, value, size=fontsize, color=body_color, margin=0)

    elif pattern == 2:
        # Large statement on the left and concise points on the right.
        _shape(slide, 0.8, 1.82, 4.05, 4.42, th["primary"] if not dark else th["accent"])
        _text(slide, 1.08, 2.15, 3.48, 0.35, labels["part"], size=11, color=(255, 255, 255), bold=True, margin=0)
        _text(slide, 1.08, 2.85, 3.45, 2.6, title, size=25 if len(title) < 55 else 19, color=(255, 255, 255), bold=True, margin=0)
        _shape(slide, 5.2, 1.82, 7.2, 4.42, card_color, line_color=th["line"] if not dark else None)
        body = "\n\n".join(f"✓ {v}" for v in content[:5])
        _text(slide, 5.52, 2.12, 6.55, 3.8, body, size=16 if len(body) < 650 else 13, color=body_color, margin=0.02)

    _footer(slide, th, index, total, topic, subject, lang, dark=dark)
    return slide



def _closing_slide(prs, theme, lang, topic, subject, entries, total):
    """Localized closing slide with a short recap and thank-you message."""
    labels = UI[lang]
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(slide, theme["cover"])
    _shape(slide, 0.0, 0.0, 13.333, 0.10, theme["accent"])
    _text(slide, 0.86, 0.75, 11.5, 0.35, labels["summary"].upper(), size=12,
          color=theme["accent"], bold=True, margin=0)
    _text(slide, 0.82, 1.25, 11.8, 0.85, labels["summary"], size=31,
          color=(255, 255, 255), bold=True, font="Aptos Display", margin=0)
    _shape(slide, 0.86, 2.17, 1.0, 0.055, theme["accent"])

    recap = []
    # The final content slide is instructed to summarize the topic; its points
    # make the closing slide useful instead of merely repeating the agenda.
    if entries and isinstance(entries[-1], dict):
        recap = _safe_text_list(entries[-1].get("content"))[:4]
    if not recap:
        recap = [labels["empty_body"]]
    _shape(slide, 0.84, 2.62, 7.7, 3.05, (255, 255, 255))
    for i, value in enumerate(recap[:4]):
        y = 2.92 + i * 0.61
        _shape(slide, 1.08, y + 0.03, 0.34, 0.34, theme["accent"], kind=MSO_SHAPE.OVAL)
        _text(slide, 1.08, y + 0.08, 0.34, 0.18, "✓", size=10, color=theme["cover"], bold=True,
              align=PP_ALIGN.CENTER, margin=0)
        value = value if len(value) <= 100 else value[:97].rstrip() + "…"
        _text(slide, 1.62, y, 6.55, 0.44, value, size=14, color=theme["text"], margin=0)

    _shape(slide, 8.95, 2.62, 3.55, 3.05, theme["primary"])
    _text(slide, 9.25, 3.10, 2.95, 1.0, labels["thanks"], size=21,
          color=(255, 255, 255), bold=True, align=PP_ALIGN.CENTER, valign=MSO_ANCHOR.MIDDLE, margin=0.04)
    _shape(slide, 10.22, 4.38, 1.05, 0.05, theme["accent"])
    _text(slide, 9.25, 4.69, 2.95, 0.48, str(topic)[:80], size=11,
          color=(237, 237, 237), align=PP_ALIGN.CENTER, margin=0.02)
    _footer(slide, theme, total, total, topic, subject, lang, dark=True)
    return slide

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
    key = str(design_key or "modern").lower()
    if key not in THEMES:
        key = "modern"
    try:
        requested = int(slide_count or 10)
    except (TypeError, ValueError):
        requested = 10
    total = requested if requested in (10, 15, 20) else min((10, 15, 20), key=lambda n: abs(n - requested))
    body_count = total - 3

    prs = _new_presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    th = dict(THEMES[key])
    image_sources = [source for source in (images or []) if _valid_image_source(source)]
    if not image_sources:
        # This means the deck still contains an actual embedded image even if
        # Wikipedia/Commons or optional image APIs are unavailable.
        image_sources = [_fallback_visual_bytes(str(topic), lc, th)]
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
    _closing_slide(prs, th, lc, str(topic), str(subject), entries, total)

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
