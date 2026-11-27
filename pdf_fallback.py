"""Zaxira PDF yaratish — LibreOffice o'rnatilmagan hostinglar uchun.

Render'ning oddiy (native) muhitida `apt-get` bilan o'rnatilgan LibreOffice
ish vaqtida mavjud bo'lmaydi, docx2pdf esa Microsoft Word talab qiladi. Shu
sababli PDF tanlanganda fayl DOCX bo'lib qaytardi. Bu modul reportlab bilan
hujjat/slayd matnidan o'qiladigan PDF yasaydi: format saqlanadi.
"""
import io
import os
import re
import xml.sax.saxutils as saxutils

_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
)


def _font():
    """Kirill va o'zbek harflarini qo'llaydigan shrift nomi."""
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except Exception:
        return "Helvetica"
    for path in _FONT_CANDIDATES:
        if not os.path.isfile(path):
            continue
        try:
            pdfmetrics.registerFont(TTFont("PdfFallback", path))
            return "PdfFallback"
        except Exception:
            continue
    return "Helvetica"


def _escape(text):
    return saxutils.escape(str(text or "").strip())


def _document(suffix, title=""):
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate

    name = _font()
    body = ParagraphStyle("body", fontName=name, fontSize=11, leading=16, spaceAfter=5)
    heading = ParagraphStyle("heading", fontName=name, fontSize=15, leading=20,
                             spaceAfter=10, spaceBefore=6)
    cover = ParagraphStyle("cover", fontName=name, fontSize=20, leading=26, spaceAfter=18)
    pagesize = landscape(A4) if suffix == "pptx" else A4
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=pagesize,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm,
        title=str(title or "")[:120],
    )
    return doc, buffer, body, heading, cover


def _finish(build, buffer):
    try:
        build()
    except Exception as exc:
        print(f"[pdf] zaxira PDF yasalmadi: {type(exc).__name__}: {exc}", flush=True)
        return None
    return buffer.getvalue()


def docx_to_pdf(data, title=""):
    """DOCX paragraflari va jadvallaridan PDF yasaydi."""
    try:
        from docx import Document
        from reportlab.platypus import Paragraph, Spacer
    except Exception:
        return None
    source = Document(io.BytesIO(data))
    doc, buffer, body, heading, cover = _document("docx", title)
    story = []
    first = True
    for paragraph in source.paragraphs:
        text = re.sub(r"\s+", " ", paragraph.text or "").strip()
        if not text:
            continue
        style = cover if first else (heading if _is_heading(paragraph) else body)
        story.append(Paragraph(_escape(text), style))
        first = False
    for table in source.tables:
        for row in table.rows:
            cells = [re.sub(r"\s+", " ", cell.text or "").strip() for cell in row.cells]
            line = " | ".join(cell for cell in cells if cell)
            if line:
                story.append(Paragraph(_escape(line), body))
        story.append(Spacer(1, 6))
    if not story:
        story.append(Paragraph(_escape(title or "Hujjat"), heading))
    return _finish(lambda: doc.build(story), buffer)


def _is_heading(paragraph):
    try:
        name = str(paragraph.style.name or "").lower()
    except Exception:
        return False
    return "heading" in name or "title" in name


def _pptx_text_pdf(data, title=""):
    """Oddiy matnli PDF — dizayn chizishning o'zi ishlamay qolganda ishlatiladi."""
    try:
        from pptx import Presentation
        from reportlab.platypus import PageBreak, Paragraph, Spacer
    except Exception:
        return None
    try:
        source = Presentation(io.BytesIO(data))
    except Exception:
        return None
    doc, buffer, body, heading, cover = _document("pptx", title)
    story = []
    for number, slide in enumerate(source.slides, 1):
        lines = []
        for shape in slide.shapes:
            if not getattr(shape, "has_text_frame", False):
                continue
            for paragraph in shape.text_frame.paragraphs:
                value = re.sub(r"\s+", " ", paragraph.text or "").strip()
                if value:
                    lines.append(value)
        if not lines:
            continue
        story.append(Paragraph(f"{number}. {_escape(lines[0])}", cover))
        for line in lines[1:]:
            story.append(Paragraph(f"• {_escape(line)}", body))
        story.append(Spacer(1, 10))
        story.append(PageBreak())
    if not story:
        story.append(Paragraph(_escape(title or "Taqdimot"), heading))
    return _finish(lambda: doc.build(story), buffer)


# ---------------------------------------------------------------------------
# Dizaynli slayd -> PDF
#
# Render'ning native muhitida LibreOffice o'rnatilmaydi, shuning uchun ilgari
# PDF faqat matndan yasalardi: rang, karta, rasm va joylashuv yo'qolib, foydalanuvchi
# "dizayn ishlamadi" deb qolardi. Quyidagi chizuvchi PPTX ichidagi har bir shaklni
# (fon, karta, rasm, matn) o'z joyi, o'lchami va rangida PDF sahifasiga ko'chiradi.
# ---------------------------------------------------------------------------

_EMU_PER_INCH = 914400.0

_PPTX_FONT_DIRS = (
    "/usr/share/fonts/truetype/dejavu",
    "/usr/share/fonts/dejavu",
    "/usr/share/fonts/TTF",
    "/usr/share/fonts/truetype/liberation",
)
_FONT_CACHE = {}


def _font_dirs():
    """Shrift papkalari: ixtiyoriy SLIDE_PDF_FONT_DIR birinchi tekshiriladi."""
    custom = str(os.environ.get("SLIDE_PDF_FONT_DIR") or "").strip()
    return ((custom,) if custom else ()) + _PPTX_FONT_DIRS


def _slide_fonts():
    """Kirill/lotin shriftlari: (regular, bold) nomlari yoki Helvetica."""
    if "pair" in _FONT_CACHE:
        return _FONT_CACHE["pair"]
    pair = ("Helvetica", "Helvetica-Bold")
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except Exception:
        _FONT_CACHE["pair"] = pair
        return pair
    for folder in _font_dirs():
        regular = os.path.join(folder, "DejaVuSans.ttf")
        bold = os.path.join(folder, "DejaVuSans-Bold.ttf")
        if not (os.path.isfile(regular) and os.path.isfile(bold)):
            continue
        try:
            pdfmetrics.registerFont(TTFont("SlideSans", regular))
            pdfmetrics.registerFont(TTFont("SlideSans-Bold", bold))
            pair = ("SlideSans", "SlideSans-Bold")
        except Exception:
            pair = ("Helvetica", "Helvetica-Bold")
        break
    _FONT_CACHE["pair"] = pair
    return pair


def _inches(value):
    try:
        return int(value or 0) / _EMU_PER_INCH
    except Exception:
        return 0.0


def _color_of(color):
    """RGBColor -> reportlab Color; mavjud bo'lmasa None."""
    try:
        red, green, blue = int(color[0]), int(color[1]), int(color[2])
    except Exception:
        return None
    from reportlab.lib.colors import Color
    return Color(red / 255.0, green / 255.0, blue / 255.0)


def _rgb_tuple(color):
    try:
        return (int(color[0]), int(color[1]), int(color[2]))
    except Exception:
        return None


def _shape_fill(shape):
    try:
        if shape.fill.type is None:
            return None
        return _color_of(shape.fill.fore_color.rgb)
    except Exception:
        return None


def _shape_stroke(shape):
    """(rang, qalinlik nuqtada) yoki None."""
    try:
        color = _color_of(shape.line.color.rgb)
        if color is None:
            return None
        width = max(0.4, _inches(shape.line.width) * 72.0)
        return color, width
    except Exception:
        return None


def _run_style(run, default_size):
    size = default_size
    try:
        if run.font.size is not None:
            size = float(run.font.size.pt)
    except Exception:
        pass
    bold = False
    try:
        bold = bool(run.font.bold)
    except Exception:
        bold = False
    color = None
    try:
        color = _color_of(run.font.color.rgb)
    except Exception:
        color = None
    return size, bold, color


def _paragraph_words(paragraph, default_size):
    """Paragrafni uslubli so'zlarga ajratadi: (so'z, size, bold, rang, oldingi bo'shliq)."""
    words = []
    for run in paragraph.runs:
        text = run.text or ""
        if not text:
            continue
        size, bold, color = _run_style(run, default_size)
        parts = text.split(" ")
        for position, part in enumerate(parts):
            if part == "":
                continue
            space = position > 0 or bool(words)
            words.append((part, size, bold, color, space))
    return words


def _layout_lines(words, max_width, regular, bold):
    """So'zlarni karta kengligiga o'rab, qatorlarga bo'ladi."""
    from reportlab.pdfbase.pdfmetrics import stringWidth
    # stringWidth nuqtada o'lchaydi; butun joylashuv dyuymda hisoblanadi.
    lines, line, width = [], [], 0.0
    for word, size, is_bold, color, space in words:
        font = bold if is_bold else regular
        piece = stringWidth(word, font, size) / 72.0
        gap = stringWidth(" ", font, size) / 72.0 if space and line else 0.0
        if line and width + gap + piece > max_width:
            lines.append(line)
            line, width = [], 0.0
            gap = 0.0
        line.append((word, size, font, color, gap, piece))
        width += gap + piece
    if line:
        lines.append(line)
    return lines


def _default_size(frame):
    for paragraph in frame.paragraphs:
        for run in paragraph.runs:
            try:
                if run.font.size is not None:
                    return float(run.font.size.pt)
            except Exception:
                continue
    return 18.0


def _draw_textbox(canvas, shape, page_height, regular, bold):
    """Shakl ichidagi matnni o'z joyida, o'lchamida va rangida chizadi."""
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR

    frame = shape.text_frame
    default_size = _default_size(frame)
    left = _inches(shape.left) + _inches(frame.margin_left or 0)
    top = _inches(shape.top) + _inches(frame.margin_top or 0)
    width = _inches(shape.width) - _inches(frame.margin_left or 0) - _inches(frame.margin_right or 0)
    height = _inches(shape.height) - _inches(frame.margin_top or 0) - _inches(frame.margin_bottom or 0)
    if width <= 0.1 or height <= 0.05:
        return

    blocks, total = [], 0.0
    for paragraph in frame.paragraphs:
        words = _paragraph_words(paragraph, default_size)
        spacing = 1.0
        try:
            if paragraph.line_spacing:
                spacing = float(paragraph.line_spacing)
        except Exception:
            spacing = 1.0
        lines = _layout_lines(words, width, regular, bold) if words else []
        space_after = 0.0
        try:
            if paragraph.space_after is not None:
                space_after = float(paragraph.space_after.pt) / 72.0
        except Exception:
            space_after = 0.0
        heights = [max((word[1] for word in line), default=default_size) / 72.0 * 1.24 * spacing
                   for line in lines]
        blocks.append((lines, heights, paragraph.alignment, space_after))
        total += sum(heights) + space_after

    anchor = None
    try:
        anchor = frame.vertical_anchor
    except Exception:
        anchor = None
    if anchor == MSO_ANCHOR.MIDDLE:
        cursor = top + max(0.0, (height - total) / 2.0)
    elif anchor == MSO_ANCHOR.BOTTOM:
        cursor = top + max(0.0, height - total)
    else:
        cursor = top

    for lines, heights, alignment, space_after in blocks:
        for line, line_height in zip(lines, heights):
            line_width = sum(word[4] + word[5] for word in line)
            if alignment == PP_ALIGN.CENTER:
                x = left + max(0.0, (width - line_width) / 2.0)
            elif alignment == PP_ALIGN.RIGHT:
                x = left + max(0.0, width - line_width)
            else:
                x = left
            baseline = cursor + line_height * 0.78
            for word, size, font, color, gap, piece in line:
                x += gap
                if color is not None:
                    canvas.setFillColor(color)
                else:
                    canvas.setFillColorRGB(0.16, 0.16, 0.16)
                canvas.setFont(font, size)
                canvas.drawString(x * 72.0, (page_height - baseline) * 72.0, word)
                x += piece
            cursor += line_height
        cursor += space_after


def _rounded_radius(shape, width, height):
    try:
        if shape.adjustments:
            return max(0.02, min(width, height) * float(shape.adjustments[0]))
    except Exception:
        pass
    return min(width, height) * 0.12


def _draw_geometry(canvas, shape, page_height):
    """Karta/fon/bezak shaklini o'z rangi va konturida chizadi."""
    from pptx.enum.shapes import MSO_SHAPE

    width, height = _inches(shape.width), _inches(shape.height)
    if width <= 0 or height <= 0:
        return
    x = _inches(shape.left)
    y = page_height - _inches(shape.top) - height
    fill, stroke = _shape_fill(shape), _shape_stroke(shape)
    if fill is None and stroke is None:
        return
    kind = None
    try:
        kind = shape.auto_shape_type
    except Exception:
        kind = None
    canvas.saveState()
    if fill is not None:
        canvas.setFillColor(fill)
    if stroke is not None:
        canvas.setStrokeColor(stroke[0])
        canvas.setLineWidth(stroke[1])
    try:
        if kind == MSO_SHAPE.OVAL:
            canvas.ellipse(x * 72.0, y * 72.0, (x + width) * 72.0, (y + height) * 72.0,
                           stroke=1 if stroke else 0, fill=1 if fill else 0)
        elif kind in (MSO_SHAPE.ROUNDED_RECTANGLE, MSO_SHAPE.ROUND_2_SAME_RECTANGLE,
                      MSO_SHAPE.ROUND_2_DIAG_RECTANGLE):
            radius = _rounded_radius(shape, width, height)
            canvas.roundRect(x * 72.0, y * 72.0, width * 72.0, height * 72.0, radius * 72.0,
                             stroke=1 if stroke else 0, fill=1 if fill else 0)
        elif kind == MSO_SHAPE.HEXAGON:
            inset = width * 0.25
            path = canvas.beginPath()
            path.moveTo((x + inset) * 72.0, y * 72.0)
            path.lineTo((x + width - inset) * 72.0, y * 72.0)
            path.lineTo((x + width) * 72.0, (y + height / 2.0) * 72.0)
            path.lineTo((x + width - inset) * 72.0, (y + height) * 72.0)
            path.lineTo((x + inset) * 72.0, (y + height) * 72.0)
            path.lineTo(x * 72.0, (y + height / 2.0) * 72.0)
            path.close()
            canvas.drawPath(path, stroke=1 if stroke else 0, fill=1 if fill else 0)
        else:
            canvas.rect(x * 72.0, y * 72.0, width * 72.0, height * 72.0,
                        stroke=1 if stroke else 0, fill=1 if fill else 0)
    except Exception as exc:
        print(f"[pdf] shakl chizilmadi: {exc}", flush=True)
    canvas.restoreState()


def _draw_picture(canvas, shape, page_height, background):
    width, height = _inches(shape.width), _inches(shape.height)
    if width <= 0 or height <= 0:
        return
    x = _inches(shape.left)
    y = page_height - _inches(shape.top) - height
    try:
        blob = shape.image.blob
    except Exception:
        return
    try:
        from PIL import Image as PILImage
        image = PILImage.open(io.BytesIO(blob))
        if image.mode in ("RGBA", "LA", "P"):
            rgba = image.convert("RGBA")
            plate = PILImage.new("RGB", rgba.size, background or (255, 255, 255))
            plate.paste(rgba, mask=rgba.split()[-1])
            out = io.BytesIO()
            plate.save(out, "PNG")
            blob = out.getvalue()
    except Exception:
        pass
    try:
        from reportlab.lib.utils import ImageReader
        canvas.drawImage(ImageReader(io.BytesIO(blob)), x * 72.0, y * 72.0,
                         width * 72.0, height * 72.0, mask=None)
    except Exception as exc:
        print(f"[pdf] rasm chizilmadi: {exc}", flush=True)


def _pptx_has_text(shape):
    try:
        if not shape.has_text_frame:
            return False
        return bool((shape.text_frame.text or "").strip())
    except Exception:
        return False


def _pptx_design_pdf(data, title=""):
    """Har bir slaydni o'z dizaynida (fon, karta, rasm, matn) chizadi."""
    try:
        from pptx import Presentation
        from pptx.enum.shapes import MSO_SHAPE_TYPE
        from reportlab.lib.units import inch
        from reportlab.pdfgen import canvas as pdfcanvas
    except Exception:
        return None
    try:
        source = Presentation(io.BytesIO(data))
    except Exception:
        return None
    if not len(source.slides):
        return None

    regular, bold = _slide_fonts()
    page_w = _inches(source.slide_width) or 13.333
    page_h = _inches(source.slide_height) or 7.5
    buffer = io.BytesIO()
    canvas = pdfcanvas.Canvas(buffer, pagesize=(page_w * inch, page_h * inch))
    if title:
        canvas.setTitle(str(title)[:120])

    for slide in source.slides:
        background = None
        try:
            background = _color_of(slide.background.fill.fore_color.rgb)
        except Exception:
            background = None
        canvas.setFillColor(background or _color_of((255, 255, 255)))
        canvas.rect(0, 0, page_w * inch, page_h * inch, stroke=0, fill=1)
        fill_tuple = _rgb_tuple(slide.background.fill.fore_color.rgb) \
            if background is not None else None
        for shape in slide.shapes:
            try:
                is_picture = shape.shape_type == MSO_SHAPE_TYPE.PICTURE
                if not is_picture:
                    try:
                        is_picture = shape.image is not None
                    except Exception:
                        is_picture = False
                if is_picture:
                    _draw_picture(canvas, shape, page_h, fill_tuple)
                    if _pptx_has_text(shape):
                        _draw_textbox(canvas, shape, page_h, regular, bold)
                    continue
                _draw_geometry(canvas, shape, page_h)
                if _pptx_has_text(shape):
                    _draw_textbox(canvas, shape, page_h, regular, bold)
            except Exception as exc:
                print(f"[pdf] slayd elementi o'tkazib yuborildi: {exc}", flush=True)
        canvas.showPage()
    canvas.save()
    return buffer.getvalue()


def pptx_to_pdf(data, title=""):
    """Taqdimotni o'z dizaynida PDF qiladi; iloji bo'lmasa matnli PDF."""
    designed = _pptx_design_pdf(data, title)
    if designed:
        return designed
    return _pptx_text_pdf(data, title)


def to_pdf(data, suffix="docx", title=""):
    """LibreOffice yo'q bo'lganda ishlatiladigan umumiy kirish nuqtasi."""
    try:
        if str(suffix).lower() == "pptx":
            return pptx_to_pdf(data, title)
        return docx_to_pdf(data, title)
    except Exception as exc:
        print(f"[pdf] zaxira konvertatsiya xatosi: {type(exc).__name__}: {exc}", flush=True)
        return None
