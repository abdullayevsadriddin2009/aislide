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


def pptx_to_pdf(data, title=""):
    """Taqdimot slaydlaridagi matndan gorizontal PDF yasaydi."""
    try:
        from pptx import Presentation
        from reportlab.platypus import PageBreak, Paragraph, Spacer
    except Exception:
        return None
    source = Presentation(io.BytesIO(data))
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


def to_pdf(data, suffix="docx", title=""):
    """LibreOffice yo'q bo'lganda ishlatiladigan umumiy kirish nuqtasi."""
    try:
        if str(suffix).lower() == "pptx":
            return pptx_to_pdf(data, title)
        return docx_to_pdf(data, title)
    except Exception as exc:
        print(f"[pdf] zaxira konvertatsiya xatosi: {type(exc).__name__}: {exc}", flush=True)
        return None
