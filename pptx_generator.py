# -*- coding: utf-8 -*-
"""
YANGI PPTX GENERATOR (v2.0) - 4 ta maxsus shablon.
Gold (10 slayd), Green (15 slayd), Wine (20 slayd), Teal (25 slayd).
Interfeys o'zgarmagan: creation.py dan chaqiriladi.
"""
import io
import os

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

BOT_USERNAME = "@Talaba_AI_SlideBot"

# ===== Shablon ranglari (4 xil uslub) =====
THEMES = {
    "10": {"name": "Gold",  "bg": (255, 255, 255), "primary": (201, 162, 39),  "text": (40, 40, 40),   "light": (252, 248, 235), "dark": (150, 110, 10)},
    "15": {"name": "Green", "bg": (255, 255, 255), "primary": (45, 106, 79),   "text": (40, 40, 40),   "light": (240, 248, 240), "dark": (25, 70, 50)},
    "20": {"name": "Wine",  "bg": (255, 255, 255), "primary": (128, 0, 32),    "text": (40, 40, 40),   "light": (250, 240, 240), "dark": (80, 0, 20)},
    "25": {"name": "Teal",  "bg": (255, 255, 255), "primary": (15, 118, 110),  "text": (40, 40, 40),   "light": (230, 245, 245), "dark": (10, 80, 75)}
}

def _rgb(tup): return RGBColor(tup[0], tup[1], tup[2])

def _set_bg(slide, rgb):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = _rgb(rgb)

def _rect(slide, x, y, w, h, fill_rgb, line_rgb=None, rounded=False):
    shp_type = MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE
    sp = slide.shapes.add_shape(shp_type, Inches(x), Inches(y), Inches(w), Inches(h))
    sp.fill.solid()
    sp.fill.fore_color.rgb = _rgb(fill_rgb)
    if line_rgb:
        sp.line.color.rgb = _rgb(line_rgb)
        sp.line.width = Pt(1.0)
    else:
        sp.line.fill.background()
    try:
        sp.shadow.inherit = False
    except Exception:
        pass
    return sp

def _txt(slide, x, y, w, h, text, size=16, bold=False, rgb=(40,40,40), font="Arial", align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = Emu(0); tf.margin_right = Emu(0); tf.margin_top = Emu(0); tf.margin_bottom = Emu(0)
    lines = text.split("\n") if isinstance(text, str) else list(text)
    for i, ln in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = 1.2
        r = p.add_run()
        r.text = ln
        r.font.name = font
        r.font.size = Pt(size)
        r.font.bold = bold
        r.font.color.rgb = _rgb(rgb)
    return tb

def _pic(slide, path, x, y, w, h):
    try:
        if path and os.path.exists(str(path)):
            return slide.shapes.add_picture(str(path), Inches(x), Inches(y), Inches(w), Inches(h))
    except Exception:
        pass
    return None

def _get_sd(sc, idx, default_title="Ma'lumot", default_content=None):
    """AI generatsiya qilgan ro'yxatdan xavfsiz ma'lumot olish."""
    if default_content is None: default_content = ["Asosiy ma'lumotlar.", "Tahliliy xulosalar."]
    if idx < len(sc):
        d = sc[idx]
        if isinstance(d, dict):
            t = str(d.get("title", default_title))
            c = d.get("content", default_content)
            if isinstance(c, str): c = [p.strip() for p in c.split("\n") if p.strip()]
            return t, c
    return default_title, default_content

# ================= LAYOUTS =================

def _slide_cover(prs, th, topic, subject, author):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(slide, th["light"])
    _rect(slide, 0, 0, 13.333, 0.5, th["primary"]) # Tepa chiziq
    _rect(slide, 0, 7.0, 13.333, 0.5, th["primary"]) # Pastki chiziq
    
    _txt(slide, 1.0, 1.5, 11.333, 0.5, subject.upper(), size=18, bold=True, rgb=th["primary"])
    _txt(slide, 1.0, 2.2, 11.333, 2.0, topic, size=44, bold=True, rgb=th["text"], font="Georgia")
    
    _rect(slide, 1.0, 4.5, 2.0, 0.08, th["primary"])
    
    _txt(slide, 1.0, 4.8, 10.0, 0.5, "Qisqa tavsif: taqdimotning asosiy g'oyasi shu yerda yoziladi", size=16, rgb=(100,100,100))
    
    _txt(slide, 1.0, 5.8, 10.0, 0.5, f"Tayyorlovchi: {author if author else 'Ism Familiya'}", size=16, bold=True, rgb=th["dark"])
    _txt(slide, 10.0, 6.5, 2.5, 0.3, f"{BOT_USERNAME}", size=10, rgb=(150,150,150), align=PP_ALIGN.RIGHT)

def _slide_toc(prs, th, sc):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(slide, th["bg"])
    _txt(slide, 0.8, 0.8, 10, 0.8, "Taqdimot mazmuni", size=36, bold=True, rgb=th["primary"], font="Georgia")
    _txt(slide, 0.8, 1.8, 10, 0.4, "BO'LIMLAR — 6 TA BO'LIM", size=14, bold=True, rgb=th["primary"])
    
    for i in range(2):
        for j in range(3):
            idx = i*3 + j
            title, _ = _get_sd(sc, idx+2, f"Bo'lim {idx+1}")
            x = 0.8 + j * 4.1
            y = 2.8 + i * 2.0
            _rect(slide, x, y, 3.8, 1.5, th["light"])
            _txt(slide, x+0.2, y+0.2, 3.4, 0.4, f"0{idx+1}", size=20, bold=True, rgb=th["primary"])
            _txt(slide, x+0.2, y+0.7, 3.4, 0.6, title, size=14, bold=True, rgb=th["text"])

def _slide_section(prs, th, num, title, subtitle=""):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(slide, th["primary"])
    _txt(slide, 1.0, 2.0, 5, 1.5, f"0{num}", size=90, bold=True, rgb=th["bg"])
    _txt(slide, 1.2, 3.8, 8, 1.0, title, size=40, bold=True, rgb=th["bg"])
    if subtitle:
        _txt(slide, 1.2, 4.8, 8, 0.5, subtitle, size=18, rgb=th["light"])

def _slide_img_text(prs, th, title, content, images, img_idx):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(slide, th["bg"])
    _txt(slide, 0.8, 0.6, 11.7, 0.8, title, size=32, bold=True, rgb=th["primary"], font="Georgia")
    
    img = images[img_idx % len(images)] if images else None
    if not _pic(slide, img, 0.8, 2.0, 5.5, 4.2):
        _rect(slide, 0.8, 2.0, 5.5, 4.2, th["light"])
        _txt(slide, 0.8, 3.8, 5.5, 0.5, "[ RASM / SXEMA JOYI ]", size=14, bold=True, rgb=(150,150,150), align=PP_ALIGN.CENTER)
    
    _txt(slide, 0.8, 6.3, 5.5, 0.3, "Shakl 1 · Rasm izohi", size=11, rgb=(150,150,150), align=PP_ALIGN.CENTER)
    
    bullets = "\n\n".join([f"• {c}" for c in content[:5]])
    _txt(slide, 7.0, 2.0, 5.5, 4.5, bullets, size=16, rgb=th["text"])

def _slide_two_col(prs, th, title, content, col_a="Birinchi guruh", col_b="Ikkinchi guruh"):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(slide, th["bg"])
    _txt(slide, 0.8, 0.6, 11.7, 0.8, title, size=32, bold=True, rgb=th["primary"], font="Georgia")
    
    mid = max(1, len(content)//2)
    txt_a = content[:mid]
    txt_b = content[mid:] if len(content) > mid else ["Qo'shimcha ma'lumotlar."]
    
    _rect(slide, 0.8, 1.8, 5.5, 0.6, th["primary"])
    _txt(slide, 0.8, 1.9, 5.5, 0.4, col_a, size=18, bold=True, rgb=(255,255,255), align=PP_ALIGN.CENTER)
    _rect(slide, 0.8, 2.4, 5.5, 4.0, th["light"])
    _txt(slide, 1.0, 2.6, 5.1, 3.6, "\n\n".join([f"• {c}" for c in txt_a]), size=15, rgb=th["text"])
    
    _rect(slide, 7.0, 1.8, 5.5, 0.6, th["primary"])
    _txt(slide, 7.0, 1.9, 5.5, 0.4, col_b, size=18, bold=True, rgb=(255,255,255), align=PP_ALIGN.CENTER)
    _rect(slide, 7.0, 2.4, 5.5, 4.0, th["light"])
    _txt(slide, 7.2, 2.6, 5.1, 3.6, "\n\n".join([f"• {c}" for c in txt_b]), size=15, rgb=th["text"])

def _slide_stats(prs, th, title, content):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(slide, th["bg"])
    _txt(slide, 0.8, 0.6, 11.7, 0.8, title, size=32, bold=True, rgb=th["primary"], font="Georgia")
    
    for i in range(3):
        x = 0.8 + i * 4.1
        _rect(slide, x, 2.5, 3.8, 3.5, th["light"])
        val = ["4 ta", "15 daq", "100%"][i]
        lbl = ["Asosiy bo'lim", "Tavsiya etilgan vaqt", "Tahrirlanadigan"][i]
        _txt(slide, x, 3.0, 3.8, 1.0, val, size=48, bold=True, rgb=th["primary"], align=PP_ALIGN.CENTER)
        _txt(slide, x, 4.2, 3.8, 0.5, lbl, size=18, bold=True, rgb=th["text"], align=PP_ALIGN.CENTER)
        desc = content[i] if i < len(content) else "Qo'shimcha ma'lumot"
        _txt(slide, x+0.2, 4.8, 3.4, 1.0, desc[:100], size=13, rgb=(100,100,100), align=PP_ALIGN.CENTER)

def _slide_process(prs, th, title, content):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(slide, th["bg"])
    _txt(slide, 0.8, 0.6, 11.7, 0.8, title, size=32, bold=True, rgb=th["primary"], font="Georgia")
    
    steps = ["1. BOSQICH", "2. BOSQICH", "3. BOSQICH", "4. BOSQICH"]
    for i in range(4):
        x = 0.8 + i * 3.0
        _rect(slide, x, 2.0, 2.8, 0.6, th["primary"])
        _txt(slide, x, 2.1, 2.8, 0.4, steps[i], size=14, bold=True, rgb=(255,255,255), align=PP_ALIGN.CENTER)
        _rect(slide, x, 2.6, 2.8, 2.5, th["light"], line_rgb=th["primary"])
        text = content[i] if i < len(content) else "Ma'lumot"
        _txt(slide, x+0.1, 2.8, 2.6, 2.0, text[:150], size=13, rgb=th["text"])
        
    _rect(slide, 0.8, 5.4, 11.7, 1.0, th["light"], line_rgb=th["primary"])
    _txt(slide, 1.0, 5.5, 11.3, 0.8, "Qisqa xulosa yoki izoh: Bu yerda jarayon bo'yicha umumlashtirilgan xulosa yoziladi.", size=14, rgb=th["text"])

def _slide_quote(prs, th, title, content):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(slide, th["primary"])
    _txt(slide, 1.0, 1.0, 11.3, 0.5, "MUHIM G'OYA", size=16, bold=True, rgb=th["light"])
    _txt(slide, 1.0, 2.0, 11.3, 2.0, title, size=40, bold=True, rgb=(255,255,255), align=PP_ALIGN.CENTER, font="Georgia")
    text = content[0] if content else "Bu yerga iqtibos yoki muhim g'oya yoziladi."
    _txt(slide, 1.0, 4.0, 11.3, 1.5, f'"{text}"', size=24, italic=True, rgb=th["light"], align=PP_ALIGN.CENTER)
    _txt(slide, 1.0, 5.5, 11.3, 0.5, "— Muallif nomi, manba", size=18, rgb=(255,255,255), align=PP_ALIGN.RIGHT)

def _slide_grid_2x2(prs, th, title, content):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(slide, th["bg"])
    _txt(slide, 0.8, 0.6, 11.7, 0.8, title, size=32, bold=True, rgb=th["primary"], font="Georgia")
    
    for i in range(4):
        r, c = i // 2, i % 2
        x = 0.8 + c * 6.0
        y = 2.0 + r * 2.4
        _rect(slide, x, y, 5.7, 2.0, th["light"])
        _txt(slide, x+0.2, y+0.2, 5.3, 0.5, f"Xususiyat {i+1}", size=18, bold=True, rgb=th["primary"])
        txt = content[i] if i < len(content) else "Qisqa tavsif."
        _txt(slide, x+0.2, y+0.8, 5.3, 1.0, txt[:120], size=14, rgb=th["text"])

def _slide_table(prs, th, title, content):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(slide, th["bg"])
    _txt(slide, 0.8, 0.6, 11.7, 0.8, title, size=32, bold=True, rgb=th["primary"], font="Georgia")
    
    rows, cols = 5, 4
    table = slide.shapes.add_table(rows, cols, Inches(0.8), Inches(2.0), Inches(11.7), Inches(4.0)).table
    headers = ["Xususiyat", "Guruh A", "Guruh B", "Xulosa"]
    for c in range(cols):
        cell = table.cell(0, c)
        cell.text = headers[c]
        cell.fill.solid(); cell.fill.fore_color.rgb = _rgb(th["primary"])
        for p in cell.text_frame.paragraphs:
            for r in p.runs:
                r.font.bold = True; r.font.color.rgb = _rgb((255,255,255))
                
    for r in range(1, rows):
        for c in range(cols):
            cell = table.cell(r, c)
            cell.text = content[(r-1)*cols + c] if (r-1)*cols + c < len(content) else "Qiymat"
            cell.fill.solid(); cell.fill.fore_color.rgb = _rgb(th["light"] if r%2==0 else (255,255,255))

def _slide_timeline(prs, th, title, content):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(slide, th["bg"])
    _txt(slide, 0.8, 0.6, 11.7, 0.8, title, size=32, bold=True, rgb=th["primary"], font="Georgia")
    _txt(slide, 0.8, 1.5, 11.7, 0.4, "TARIXIY JADVAL", size=14, bold=True, rgb=th["primary"])
    
    _rect(slide, 0.8, 3.2, 11.7, 0.1, th["primary"])
    years = ["2020", "2022", "2024", "2026"]
    for i in range(4):
        x = 1.5 + i * 3.0
        _rect(slide, x, 3.05, 0.4, 0.4, th["primary"])
        _txt(slide, x-0.5, 2.5, 1.5, 0.5, years[i], size=24, bold=True, rgb=th["primary"], align=PP_ALIGN.CENTER)
        text = content[i] if i < len(content) else "Voqea"
        _txt(slide, x-1.2, 3.6, 3.0, 1.5, text[:100], size=14, rgb=th["text"], align=PP_ALIGN.CENTER)

def _slide_facts(prs, th, title, content):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(slide, th["bg"])
    _txt(slide, 0.8, 0.6, 11.7, 0.8, title, size=32, bold=True, rgb=th["primary"], font="Georgia")
    for i in range(6):
        r, c = i // 3, i % 3
        x = 0.8 + c * 4.1
        y = 2.0 + r * 2.4
        _rect(slide, x, y, 3.8, 2.0, th["light"])
        _txt(slide, x+0.2, y+0.2, 3.4, 0.5, f"0{i+1}", size=24, bold=True, rgb=th["primary"])
        txt = content[i] if i < len(content) else "Fakt ma'lumoti."
        _txt(slide, x+0.2, y+0.8, 3.4, 1.0, txt[:100], size=14, rgb=th["text"])

def _slide_chart(prs, th, title, content):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(slide, th["bg"])
    _txt(slide, 0.8, 0.6, 11.7, 0.8, title, size=32, bold=True, rgb=th["primary"], font="Georgia")
    _txt(slide, 0.8, 2.0, 5.0, 4.0, "\n\n".join([f"• {c}" for c in content[:4]]), size=16, rgb=th["text"])
    _rect(slide, 6.5, 2.0, 6.0, 4.0, th["light"])
    _txt(slide, 6.5, 3.8, 6.0, 0.5, "[ GRAFIK / DIAGRAMMA JOYI ]", size=14, bold=True, rgb=(150,150,150), align=PP_ALIGN.CENTER)

def _slide_refs(prs, th, title, content):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(slide, th["bg"])
    _txt(slide, 0.8, 0.6, 11.7, 0.8, title, size=32, bold=True, rgb=th["primary"], font="Georgia")
    refs = "1. Muallif. Kitob nomi. Nashriyot, yil.\n2. Muallif. Maqola nomi. Jurnal nomi, son, yil.\n3. Veb-sayt manzili — tashrif buyurilgan sana.\n4. Konferentsiya materiali, yil.\n5. Darslik yoki o'quv qo'llanma."
    if content and len(content) > 1:
        refs = "\n".join([f"{i+1}. {c}" for i, c in enumerate(content[:6])])
    _txt(slide, 0.8, 2.0, 11.7, 4.5, refs, size=16, rgb=th["text"])

def _slide_conclusion(prs, th, title, content):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(slide, th["bg"])
    _txt(slide, 0.8, 0.6, 11.7, 0.8, "XULOSA • SUMMARY", size=20, bold=True, rgb=th["primary"])
    _txt(slide, 0.8, 1.5, 11.7, 0.8, title, size=32, bold=True, rgb=th["text"], font="Georgia")
    
    bullets = content[:4] if content else ["Asosiy xulosalar."]
    _txt(slide, 0.8, 2.8, 11.7, 2.5, "\n\n".join([f"✓ {c}" for c in bullets]), size=18, rgb=th["text"])
    _txt(slide, 0.8, 5.8, 11.7, 1.0, "E'tiboringiz uchun rahmat! Savollaringiz bormi?", size=24, bold=True, rgb=th["primary"], align=PP_ALIGN.CENTER)

# ================= ASOSIY GENERATOR =================

def generate_pptx(topic, subject, lang, design_key, slide_count, slides_content, images=None, author=""):
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    
    # design_key "10", "15", "20" yoki "25" bo'ladi
    t_key = str(slide_count) if str(slide_count) in THEMES else "10"
    th = THEMES[t_key]
    sc = slides_content or []
    imgs = images if isinstance(images, list) else ([images] if images else [])
    
    # ================= 10 SLAYD (GOLD) =================
    if t_key == "10":
        _slide_cover(prs, th, topic, subject, author)
        _slide_toc(prs, th, sc)
        
        t, c = _get_sd(sc, 2); _slide_img_text(prs, th, t, c, imgs, 1)
        t, c = _get_sd(sc, 3); _slide_two_col(prs, th, t, c, "Birinchi guruh", "Ikkinchi guruh")
        t, c = _get_sd(sc, 4); _slide_stats(prs, th, t, c)
        t, c = _get_sd(sc, 5); _slide_process(prs, th, t, c)
        t, c = _get_sd(sc, 6); _slide_quote(prs, th, t, c)
        t, c = _get_sd(sc, 7); _slide_two_col(prs, th, t, c, "Variant A", "Variant B")
        
        _slide_refs(prs, th, "Foydalanilgan adabiyotlar", [])
        t, c = _get_sd(sc, 9, "Xulosa"); _slide_conclusion(prs, th, t, c)

    # ================= 15 SLAYD (GREEN) =================
    elif t_key == "15":
        _slide_cover(prs, th, topic, subject, author)
        _slide_toc(prs, th, sc)
        
        _slide_section(prs, th, 1, "Nazariy asoslar", "Mavzuning teoriyasi va tarixi")
        t, c = _get_sd(sc, 3); _slide_img_text(prs, th, t, c, imgs, 1)
        t, c = _get_sd(sc, 4); _slide_two_col(prs, th, t, c, "Birinchi tur", "Ikkinchi tur")
        t, c = _get_sd(sc, 5); _slide_stats(prs, th, t, c)
        t, c = _get_sd(sc, 6); _slide_table(prs, th, t, c)
        
        _slide_section(prs, th, 2, "Amaliy qism", "Tadqiqot va natijalar")
        t, c = _get_sd(sc, 8); _slide_process(prs, th, t, c)
        t, c = _get_sd(sc, 9); _slide_grid_2x2(prs, th, t, c)
        t, c = _get_sd(sc, 10); _slide_quote(prs, th, t, c)
        t, c = _get_sd(sc, 11); _slide_two_col(prs, th, t, c, "Variant A", "Variant B")
        t, c = _get_sd(sc, 12); _slide_chart(prs, th, t, c)
        
        _slide_refs(prs, th, "Foydalanilgan adabiyotlar", [])
        t, c = _get_sd(sc, 14, "Xulosa"); _slide_conclusion(prs, th, t, c)

    # ================= 20 SLAYD (WINE) =================
    elif t_key == "20":
        _slide_cover(prs, th, topic, subject, author)
        _slide_toc(prs, th, sc)
        
        _slide_section(prs, th, 1, "Kirish va mavzuning ahamiyati", "Mavzuning ahamiyati va tarixi")
        t, c = _get_sd(sc, 3); _slide_img_text(prs, th, t, c, imgs, 1)
        t, c = _get_sd(sc, 4); _slide_two_col(prs, th, t, c, "Konsept A", "Konsept B")
        t, c = _get_sd(sc, 5); _slide_timeline(prs, th, t, c)
        t, c = _get_sd(sc, 6); _slide_stats(prs, th, t, c)
        
        _slide_section(prs, th, 2, "Tahlil va tadqiqot natijalari", "Metodika va natijalar")
        t, c = _get_sd(sc, 8); _slide_table(prs, th, t, c)
        t, c = _get_sd(sc, 9); _slide_process(prs, th, t, c)
        t, c = _get_sd(sc, 10); _slide_chart(prs, th, t, c)
        t, c = _get_sd(sc, 11); _slide_grid_2x2(prs, th, t, c)
        
        _slide_section(prs, th, 3, "Muhokama va xulosa", "Natijalarni baholash")
        t, c = _get_sd(sc, 13); _slide_two_col(prs, th, t, c, "Variant A", "Variant B")
        t, c = _get_sd(sc, 14); _slide_quote(prs, th, t, c)
        t, c = _get_sd(sc, 15); _slide_facts(prs, th, t, c)
        t, c = _get_sd(sc, 16); _slide_two_col(prs, th, t, c, "Afzalliklar", "Cheklovlar")
        t, c = _get_sd(sc, 17); _slide_img_text(prs, th, t, c, imgs, 2)
        
        _slide_refs(prs, th, "Foydalanilgan adabiyotlar", [])
        t, c = _get_sd(sc, 19, "Xulosa"); _slide_conclusion(prs, th, t, c)

    # ================= 25 SLAYD (TEAL) =================
    else:
        _slide_cover(prs, th, topic, subject, author)
        _slide_toc(prs, th, sc)
        
        _slide_section(prs, th, 1, "Kirish", "Mavzuning ahamiyati va maqsadi")
        t, c = _get_sd(sc, 3); _slide_img_text(prs, th, t, c, imgs, 1)
        t, c = _get_sd(sc, 4); _slide_two_col(prs, th, t, c, "Asosiy maqsad", "Vazifalar")
        t, c = _get_sd(sc, 5); _slide_timeline(prs, th, t, c)
        t, c = _get_sd(sc, 6); _slide_stats(prs, th, t, c)
        
        _slide_section(prs, th, 2, "Nazariy asoslar", "Tushunchalar va tasniflash")
        t, c = _get_sd(sc, 8); _slide_img_text(prs, th, t, c, imgs, 2)
        t, c = _get_sd(sc, 9); _slide_two_col(prs, th, t, c, "Guruh A", "Guruh B")
        t, c = _get_sd(sc, 10); _slide_table(prs, th, t, c)
        t, c = _get_sd(sc, 11); _slide_grid_2x2(prs, th, t, c)
        
        _slide_section(prs, th, 3, "Tadqiqot va tahlil", "Metodika va natijalar")
        t, c = _get_sd(sc, 13); _slide_process(prs, th, t, c)
        t, c = _get_sd(sc, 14); _slide_chart(prs, th, t, c)
        t, c = _get_sd(sc, 15); _slide_chart(prs, th, t, c)
        t, c = _get_sd(sc, 16); _slide_table(prs, th, t, c)
        t, c = _get_sd(sc, 17); _slide_grid_2x2(prs, th, t, c)
        t, c = _get_sd(sc, 18); _slide_facts(prs, th, t, c)
        
        _slide_section(prs, th, 4, "Muhokama va xulosa", "Natijalarni baholash")
        t, c = _get_sd(sc, 20); _slide_two_col(prs, th, t, c, "Variant A", "Variant B")
        t, c = _get_sd(sc, 21); _slide_quote(prs, th, t, c)
        t, c = _get_sd(sc, 22); _slide_img_text(prs, th, t, c, imgs, 3)
        
        _slide_refs(prs, th, "Foydalanilgan adabiyotlar", [])
        t, c = _get_sd(sc, 24, "Xulosa"); _slide_conclusion(prs, th, t, c)

    # Saqlash
    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    return buf
