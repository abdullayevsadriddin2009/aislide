"""DOCX generator — 8 ta xizmat turi uchun to'liq struktura.
Har bir xizmat: Titul sahifa → Mundarija → Kirish → Boblar → Xulosa → Adabiyotlar.
6 til qo'llab-quvvatlanadi. Har sahifa pastida: 11pt "Yaratildi: @Talaba_AI_SlideBot".
Muallif bir nechta qator bo'lishi mumkin (Bajaruvchi, Ilmiy rahbar, Kafedra mudiri).
"""
import io
import re
from docx import Document
from docx.shared import Pt, RGBColor, Inches, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.enum.section import WD_SECTION
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from config import BOT_USERNAME

# ===== 6 til uchun strukturaviy yorliqlar =====
L = {
    "uz": {
        "ministry": "O'ZBEKISTON RESPUBLIKASI OLIY TA'LIM, FAN VA INNOVATSIYALAR VAZIRLIGI",
        "inst_placeholder": "[OTM / Institut / Kollej nomi]",
        "dept_placeholder": "[Kafedra / Yo'nalish nomi]",
        "referat": "REFERAT", "mustaqil": "MUSTAQIL ISH", "kurs": "KURS ISHI",
        "diplom": "BITIRUV MALAKAVIY ISHI",
        "topic_label": "MAVZU:", "author_label": "Bajaruvchi:", "supervisor_label": "Ilmiy rahbar:",
        "dept_head_label": "Kafedra mudiri:", "reviewer_label": "Raqamchi:",
        "accepted_label": "Qabul qildi:", "checked_label": "Tekshiruvchi:",
        "city_year": "Toshkent — 2026",
        "toc": "MUNDARIJA", "intro": "KIRISH",
        "relevance": "Mavzuning dolzarbligi:", "goal": "Ishning maqsadi:",
        "object":": Tadqiqot obyekti:", "subject": "Tadqiqot predmeti:",
        "tasks": "Bajarilgan vazifalar:",
        "conclusion": "XULOSA", "conclusion_kurs": "XULOSA VA TAKLIFLAR",
        "conclusion_diplom": "XULOSA VA TAVSIYALAR",
        "references": "FOYDALANILGAN ADABIYOTLAR", "appendix": "ILAVALAR",
        "chapter": "BOB", "important_def": "📌 MUHIM TA'RIF",
        "practical_tip": "🛡 AMALIY MASLAHAT", "stats": "📊 STATISTIK MA'LUMOT",
        "quote": "📜 MASHHUR IQTIBOS", "final_wisdom": "💡 YAKUNIY HIKMAT",
        "author_recommendation": "💡 MUALLIF TAKLIFI", "scientific_rec": "🎓 ILMIY TAKLIF",
        "results": "📊 ASOSIY NATIJALAR", "methods": "📊 USULLAR VA METODOLOGIYA",
        "rationale": "💡 Izoh:", "correct_mark": "(✓ To'g'ri javob)",
        "annotation": "📌 Annotatsiya:", "keywords": "🔑 Kalit so'zlar:",
        "essay_style": "USLUB: Badiiy-Falsafiy Essey", "thesis": "ILMIY TEZIS",
        "author": "Muallif:", "affiliation": "Tashkilot:", "email": "E-mail:",
        "relevance_thesis": "📌 DOLZARBLIGI VA MAQSADI:",
        "test_title": "QUIZ / BILIMLAR TESTI", "questions_count": "Savollar soni:",
        "level": "Daraja: O'rta", "question": "SAVOL",
        "skip_author": "Talaba",
    },
    "ru": {
        "ministry": "МИНИСТЕРСТВО ВЫСШЕГО ОБРАЗОВАНИЯ, НАУКИ И ИННОВАЦИЙ РЕСПУБЛИКИ УЗБЕКИСТАН",
        "inst_placeholder": "[Название ВУЗа / Института / Колледжа]",
        "dept_placeholder": "[Название кафедры / направления]",
        "referat": "РЕФЕРАТ", "mustaqil": "САМОСТОЯТЕЛЬНАЯ РАБОТА", "kurs": "КУРСОВАЯ РАБОТА",
        "diplom": "ВЫПУСКНАЯ КВАЛИФИКАЦИОННАЯ РАБОТА",
        "topic_label": "ТЕМА:", "author_label": "Выполнил:", "supervisor_label": "Научный руководитель:",
        "dept_head_label": "Заведующий кафедрой:", "reviewer_label": "Рецензент:",
        "accepted_label": "Принял:", "checked_label": "Проверил:",
        "city_year": "Ташкент — 2026",
        "toc": "СОДЕРЖАНИЕ", "intro": "ВВЕДЕНИЕ",
        "relevance": "Актуальность темы:", "goal": "Цель работы:",
        "object": "Объект исследования:", "subject": "Предмет исследования:",
        "tasks": "Задачи исследования:",
        "conclusion": "ЗАКЛЮЧЕНИЕ", "conclusion_kurs": "ЗАКЛЮЧЕНИЕ И ПРЕДЛОЖЕНИЯ",
        "conclusion_diplom": "ЗАКЛЮЧЕНИЕ И РЕКОМЕНДАЦИИ",
        "references": "СПИСОК ИСПОЛЬЗОВАННОЙ ЛИТЕРАТУРЫ", "appendix": "ПРИЛОЖЕНИЯ",
        "chapter": "ГЛАВА", "important_def": "📌 ВАЖНОЕ ОПРЕДЕЛЕНИЕ",
        "practical_tip": "🛡 ПРАКТИЧЕСКИЙ СОВЕТ", "stats": "📊 СТАТИСТИЧЕСКИЕ ДАННЫЕ",
        "quote": "📜 ИЗВЕСТНАЯ ЦИТАТА", "final_wisdom": "💡 ИТОГОВАЯ МЫСЛЬ",
        "author_recommendation": "💡 РЕКОМЕНДАЦИЯ АВТОРА", "scientific_rec": "🎓 НАУЧНАЯ РЕКОМЕНДАЦИЯ",
        "results": "📊 ОСНОВНЫЕ РЕЗУЛЬТАТЫ", "methods": "📊 МЕТОДЫ И МЕТОДОЛОГИЯ",
        "rationale": "💡 Обоснование:", "correct_mark": "(✓ Правильный ответ)",
        "annotation": "📌 Аннотация:", "keywords": "🔑 Ключевые слова:",
        "essay_style": "СТИЛЬ: Художественно-философское эссе", "thesis": "НАУЧНЫЙ ТЕЗИС",
        "author": "Автор:", "affiliation": "Организация:", "email": "E-mail:",
        "relevance_thesis": "📌 АКТУАЛЬНОСТЬ И ЦЕЛЬ:",
        "test_title": "ТЕСТ / ПРОВЕРКА ЗНАНИЙ", "questions_count": "Количество вопросов:",
        "level": "Уровень: Средний", "question": "ВОПРОС",
        "skip_author": "Студент",
    },
    "en": {
        "ministry": "MINISTRY OF HIGHER EDUCATION, SCIENCE AND INNOVATIONS OF THE REPUBLIC OF UZBEKISTAN",
        "inst_placeholder": "[University / Institute / College name]",
        "dept_placeholder": "[Department / Major name]",
        "referat": "ESSAY / REPORT", "mustaqil": "ASSIGNMENT", "kurs": "COURSEWORK",
        "diplom": "GRADUATION THESIS",
        "topic_label": "TOPIC:", "author_label": "Prepared by:", "supervisor_label": "Scientific advisor:",
        "dept_head_label": "Head of Department:", "reviewer_label": "Reviewer:",
        "accepted_label": "Accepted by:", "checked_label": "Checked by:",
        "city_year": "Tashkent — 2026",
        "toc": "CONTENTS", "intro": "INTRODUCTION",
        "relevance": "Relevance of the topic:", "goal": "Goal of the work:",
        "object": "Research object:", "subject": "Research subject:",
        "tasks": "Tasks completed:",
        "conclusion": "CONCLUSION", "conclusion_kurs": "CONCLUSION AND RECOMMENDATIONS",
        "conclusion_diplom": "CONCLUSION AND SUGGESTIONS",
        "references": "REFERENCES", "appendix": "APPENDICES",
        "chapter": "CHAPTER", "important_def": "📌 KEY DEFINITION",
        "practical_tip": "🛡 PRACTICAL TIP", "stats": "📊 STATISTICAL DATA",
        "quote": "📜 FAMOUS QUOTE", "final_wisdom": "💡 FINAL THOUGHT",
        "author_recommendation": "💡 AUTHOR'S RECOMMENDATION", "scientific_rec": "🎓 SCIENTIFIC RECOMMENDATION",
        "results": "📊 MAIN RESULTS", "methods": "📊 METHODS AND METHODOLOGY",
        "rationale": "💡 Rationale:", "correct_mark": "(✓ Correct answer)",
        "annotation": "📌 Abstract:", "keywords": "🔑 Keywords:",
        "essay_style": "STYLE: Literary-Philosophical Essay", "thesis": "SCIENTIFIC ABSTRACT",
        "author": "Author:", "affiliation": "Affiliation:", "email": "E-mail:",
        "relevance_thesis": "📌 RELEVANCE AND GOAL:",
        "test_title": "QUIZ / KNOWLEDGE TEST", "questions_count": "Number of questions:",
        "level": "Level: Intermediate", "question": "QUESTION",
        "skip_author": "Student",
    },
    "tr": {
        "ministry": "ÖZBEKİSTAN CUMHURİYETİ YÜKSEKÖĞRETİM, BİLİM VE İNOVASYON BAKANLIĞI",
        "inst_placeholder": "[Üniversite / Enstitü / Kolej adı]",
        "dept_placeholder": "[Bölüm / Anabilim dalı adı]",
        "referat": "RAPOR", "mustaqil": "ÖDEV", "kurs": "DÖNEM ÖDEVİ",
        "diplom": "MEZUNİYET TEZİ",
        "topic_label": "KONU:", "author_label": "Hazırlayan:", "supervisor_label": "Danışman:",
        "dept_head_label": "Bölüm başkanı:", "reviewer_label": "Hakem:",
        "accepted_label": "Kabul eden:", "checked_label": "Kontrol eden:",
        "city_year": "Taşkent — 2026",
        "toc": "İÇİNDEKİLER", "intro": "GİRİŞ",
        "relevance": "Konu güncelliği:", "goal": "Çalışmanın amacı:",
        "object": "Araştırma nesnesi:", "subject": "Araştırma konusu:",
        "tasks": "Yapılan görevler:",
        "conclusion": "SONUÇ", "conclusion_kurs": "SONUÇ VE ÖNERİLER",
        "conclusion_diplom": "SONUÇ VE TAVSİYELER",
        "references": "KAYNAKÇA", "appendix": "EKLER",
        "chapter": "BÖLÜM", "important_def": "📌 ÖNEMLİ TANIM",
        "practical_tip": "🛡 PRATİK ÖNERİ", "stats": "📊 İSTATİSTİKSEL VERİ",
        "quote": "📜 MEŞHUR ALINTI", "final_wisdom": "💡 SON DÜŞÜNCE",
        "author_recommendation": "💡 YAZAR ÖNERİSİ", "scientific_rec": "🎓 BİLİMSEL ÖNERİ",
        "results": "📊 TEMEL BULGULAR", "methods": "📊 YÖNTEM VE METODOLOJİ",
        "rationale": "💡 Açıklama:", "correct_mark": "(✓ Doğru cevap)",
        "annotation": "📌 Özet:", "keywords": "🔑 Anahtar kelimeler:",
        "essay_style": "TARZ: Edebi-Felsefi Deneme", "thesis": "BİLİMSEL TEZ ÖZETİ",
        "author": "Yazar:", "affiliation": "Kurum:", "email": "E-posta:",
        "relevance_thesis": "📌 GÜNCELLİK VE AMAÇ:",
        "test_title": "TEST / BİLGİ SINAVI", "questions_count": "Soru sayısı:",
        "level": "Seviye: Orta", "question": "SORU",
        "skip_author": "Öğrenci",
    },
    "de": {
        "ministry": "MINISTERIUM FÜR HOCHSCHULWESEN, WISSENSCHAFT UND INNOVATION DER REPUBLIK USBEKISTAN",
        "inst_placeholder": "[Name der Universität / Instituts / Kollegs]",
        "dept_placeholder": "[Name des Lehrstuhls / Studiengangs]",
        "referat": "REFERAT", "mustaqil": "HAUSARBEIT", "kurs": "SEMINARARBEIT",
        "diplom": "ABSCHLUSSARBEIT",
        "topic_label": "THEMA:", "author_label": "Verfasser:", "supervisor_label": "Wissenschaftlicher Betreuer:",
        "dept_head_label": "Lehrstuhlleiter:", "reviewer_label": "Gutachter:",
        "accepted_label": "Angenommen von:", "checked_label": "Geprüft von:",
        "city_year": "Taschkent — 2026",
        "toc": "INHALTSVERZEICHNIS", "intro": "EINLEITUNG",
        "relevance": "Aktualität des Themas:", "goal": "Ziel der Arbeit:",
        "object": "Untersuchungsgegenstand:", "subject": "Untersuchungssubjekt:",
        "tasks": "Aufgaben:",
        "conclusion": "FAZIT", "conclusion_kurs": "FAZIT UND EMPFEHLUNGEN",
        "conclusion_diplom": "FAZIT UND VORSCHLÄGE",
        "references": "LITERATURVERZEICHNIS", "appendix": "ANHÄNGE",
        "chapter": "KAPITEL", "important_def": "📌 WICHTIGE DEFINITION",
        "practical_tip": "🛡 PRAKTISCHER TIPP", "stats": "📊 STATISTISCHE DATEN",
        "quote": "📜 BERÜHMTES ZITAT", "final_wisdom": "💡 ABSCHLIESSENDE GEDANKE",
        "author_recommendation": "💡 EMPFEHLUNG DES AUTORES", "scientific_rec": "🎓 WISSENSCHAFTLICHE EMPFEHLUNG",
        "results": "📊 HAUPTERGEBNISSE", "methods": "📊 METHODEN UND METHODIK",
        "rationale": "💡 Begründung:", "correct_mark": "(✓ Richtige Antwort)",
        "annotation": "📌 Zusammenfassung:", "keywords": "🔑 Schlüsselwörter:",
        "essay_style": "STIL: Literarisch-philosophischer Essay", "thesis": "WISSENSCHAFTLICHE THESE",
        "author": "Autor:", "affiliation": "Einrichtung:", "email": "E-Mail:",
        "relevance_thesis": "📌 AKTUALITÄT UND ZIEL:",
        "test_title": "TEST / WISSENSABFRAGE", "questions_count": "Anzahl der Fragen:",
        "level": "Niveau: Mittel", "question": "FRAGE",
        "skip_author": "Student",
    },
    "fr": {
        "ministry": "MINISTÈRE DE L'ENSEIGNEMENT SUPÉRIEUR, DES SCIENCES ET DE L'INNOVATION DE LA RÉPUBLIQUE D'OUBZÉKISTAN",
        "inst_placeholder": "[Nom de l'université / institut / collège]",
        "dept_placeholder": "[Nom du département / filière]",
        "referat": "EXPOSÉ", "mustaqil": "DEVOIR", "kurs": "MÉMOIRE",
        "diplom": "MÉMOIRE DE FIN D'ÉTUDES",
        "topic_label": "SUJET :", "author_label": "Réalisé par :", "supervisor_label": "Directeur de recherche :",
        "dept_head_label": "Chef de département :", "reviewer_label": "Rapporteur :",
        "accepted_label": "Accepté par :", "checked_label": "Vérifié par :",
        "city_year": "Tachkent — 2026",
        "toc": "SOMMAIRE", "intro": "INTRODUCTION",
        "relevance": "Pertinence du sujet :", "goal": "Objectif du travail :",
        "object": "Objet de recherche :", "subject": "Sujet de recherche :",
        "tasks": "Tâches effectuées :",
        "conclusion": "CONCLUSION", "conclusion_kurs": "CONCLUSION ET RECOMMANDATIONS",
        "conclusion_diplom": "CONCLUSION ET SUGGESTIONS",
        "references": "BIBLIOGRAPHIE", "appendix": "ANNEXES",
        "chapter": "CHAPITRE", "important_def": "📌 DÉFINITION CLÉ",
        "practical_tip": "🛡 CONSEIL PRATIQUE", "stats": "📊 DONNÉES STATISTIQUES",
        "quote": "📜 CITATION CÉLÈBRE", "final_wisdom": "💡 PENSÉE FINALE",
        "author_recommendation": "💡 RECOMMANDATION DE L'AUTEUR", "scientific_rec": "🎓 RECOMMANDATION SCIENTIFIQUE",
        "results": "📊 RÉSULTATS PRINCIPAUX", "methods": "📊 MÉTHODES ET MÉTHODOLOGIE",
        "rationale": "💡 Explication :", "correct_mark": "(✓ Bonne réponse)",
        "annotation": "📌 Résumé :", "keywords": "🔑 Mots-clés :",
        "essay_style": "STYLE : Essai littéraire et philosophique", "thesis": "THÈSE SCIENTIFIQUE",
        "author": "Auteur :", "affiliation": "Affiliation :", "email": "E-mail :",
        "relevance_thesis": "📌 PERTINENCE ET OBJECTIF :",
        "test_title": "QUIZ / TEST DE CONNAISSANCES", "questions_count": "Nombre de questions :",
        "level": "Niveau : Intermédiaire", "question": "QUESTION",
        "skip_author": "Étudiant",
    },
}

def _lbl(lang):
    return L.get(str(lang).lower(), L["uz"])

def _set_cell_bg(cell, color_hex):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:fill'), color_hex)
    tcPr.append(shd)

def _add_footer(section, lang):
    """Har sahifa pastiga: 11pt 'Yaratildi: @Talaba_AI_SlideBot'."""
    footer = section.footer
    footer.is_linked_to_previous = False
    p = footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    _cb = {"uz": "Yaratildi:", "ru": "Создано:", "en": "Created by:"}.get(str(lang).lower(), "Created by:")
    run = p.add_run(f"{_cb} {BOT_USERNAME}")
    run.font.size = Pt(11)
    run.font.italic = True
    run.font.color.rgb = RGBColor(120, 120, 120)

def _add_heading(doc, text, level=1, center=False):
    h = doc.add_heading(text, level=level)
    if center:
        h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in h.runs:
        run.font.name = "Times New Roman"
        if level == 0:
            run.font.size = Pt(22)
        elif level == 1:
            run.font.size = Pt(16)
        else:
            run.font.size = Pt(14)
        run.font.bold = True
        run.font.color.rgb = RGBColor(20, 20, 20)
    return h

def _add_para(doc, text, size=14, bold=False, italic=False, align=None, indent=True, color=None):
    p = doc.add_paragraph()
    if align:
        p.alignment = align
    if indent:
        p.paragraph_format.first_line_indent = Cm(1.25)
    p.paragraph_format.line_spacing = 1.5
    p.paragraph_format.space_after = Pt(6)
    run = p.add_run(text)
    run.font.size = Pt(size)
    run.font.name = "Times New Roman"
    run.font.bold = bold
    run.font.italic = italic
    if color:
        run.font.color.rgb = color
    return p

def _add_label_para(doc, label, text, size=14):
    p = doc.add_paragraph()
    p.paragraph_format.line_spacing = 1.5
    p.paragraph_format.space_after = Pt(6)
    r1 = p.add_run(label + " ")
    r1.font.bold = True; r1.font.size = Pt(size); r1.font.name = "Times New Roman"
    r2 = p.add_run(text)
    r2.font.size = Pt(size); r2.font.name = "Times New Roman"
    return p

def _add_box(doc, title, body, bg_hex="FFF8E1", border_color=None):
    """Ramkali blok — jadval orqali (fon rangli, chegarali)."""
    table = doc.add_table(rows=1, cols=1)
    table.style = "Table Grid"
    cell = table.cell(0, 0)
    _set_cell_bg(cell, bg_hex)
    # Sarlavha
    p1 = cell.paragraphs[0]
    r1 = p1.add_run(title)
    r1.font.bold = True; r1.font.size = Pt(14); r1.font.name = "Times New Roman"
    r1.font.color.rgb = RGBColor(120, 60, 0)
    # Matn
    for line in body.split("\n"):
        if not line.strip():
            continue
        p = cell.add_paragraph()
        p.paragraph_format.line_spacing = 1.3
        run = p.add_run(line.strip())
        run.font.size = Pt(13); run.font.name = "Times New Roman"
    doc.add_paragraph()  # bo'sh qator

def _split_content(text, n):
    """AI matnini n ta bobga bo'ladi."""
    if not text:
        return ["" for _ in range(n)]
    paras = [p.strip() for p in re.split(r'\n\s*\n|\n', text) if p.strip() and len(p.strip()) > 20]
    if not paras:
        paras = [text[i:i+400] for i in range(0, len(text), 400)]
    per = max(1, len(paras) // n)
    parts = []
    idx = 0
    for i in range(n):
        if i == n - 1:
            parts.append("\n".join(paras[idx:]))
        else:
            parts.append("\n".join(paras[idx:idx+per]))
            idx += per
    return parts

def _parse_author(author, lbl):
    """Muallif maydonini bir nechta qatorga bo'ladi.
    1-qator: Bajaruvchi, keyingi qatorlar: Ilmiy rahbar, Kafedra mudiri h.k."""
    if not author or author.strip() in ("-", "—", ""):
        return [(lbl["author_label"], lbl["skip_author"])]
    lines = [l.strip() for l in author.split("\n") if l.strip()]
    result = []
    labels = [lbl["author_label"], lbl["supervisor_label"], lbl["dept_head_label"], lbl["reviewer_label"]]
    for i, line in enumerate(lines):
        # Agar foydalanuvchi o'zi yorliq bilan yozgan bo'lsa — shunday qoldiramiz
        if ":" in line[:20]:
            lab, val = line.split(":", 1)
            result.append((lab.strip() + ":", val.strip()))
        else:
            result.append((labels[i] if i < len(labels) else labels[-1], line))
    return result

def _add_title_page(doc, service, topic, author, lbl, include_dept=False):
    """Titul sahifasi."""
    service_key = service if service in ("referat","mustaqil","kurs","diplom") else "referat"
    doc.add_paragraph()
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(lbl["ministry"]); r.font.size = Pt(12); r.font.bold = True; r.font.name = "Times New Roman"
    doc.add_paragraph()
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(lbl["inst_placeholder"]); r.font.size = Pt(14); r.font.name = "Times New Roman"
    if include_dept:
        p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(lbl["dept_placeholder"]); r.font.size = Pt(13); r.font.name = "Times New Roman"
    for _ in range(4):
        doc.add_paragraph()
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(lbl[service_key]); r.font.size = Pt(20); r.font.bold = True; r.font.name = "Times New Roman"
    doc.add_paragraph()
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(f'{lbl["topic_label"]} {topic}'); r.font.size = Pt(16); r.font.bold = True; r.font.name = "Times New Roman"
    for _ in range(3):
        doc.add_paragraph()
    # Muallif ma'lumotlari — o'ng tomonda
    author_pairs = _parse_author(author, lbl)
    for lab, val in author_pairs:
        p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        r1 = p.add_run(f"{lab} "); r1.font.size = Pt(14); r1.font.name = "Times New Roman"
        r2 = p.add_run(val); r2.font.size = Pt(14); r2.font.name = "Times New Roman"
    for _ in range(4):
        doc.add_paragraph()
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(lbl["city_year"]); r.font.size = Pt(14); r.font.name = "Times New Roman"
    doc.add_page_break()

def _add_toc(doc, sections, lbl):
    """Mundarija — nuqtalar bilan."""
    _add_heading(doc, lbl["toc"], level=1, center=True)
    doc.add_paragraph()
    for title, page in sections:
        p = doc.add_paragraph()
        p.paragraph_format.line_spacing = 1.5
        dots = "." * max(3, 60 - len(title))
        run = p.add_run(f"{title} {dots} {page}")
        run.font.size = Pt(13); run.font.name = "Times New Roman"
    doc.add_page_break()

def _add_references(doc, topic, lbl):
    _add_heading(doc, lbl["references"], level=1, center=True)
    refs = [
        f"1. Official legislative acts and regulations related to {topic[:40]}.",
        f"2. Academic sources — monographs and textbooks on {topic}. 2024.",
        f"3. Ilmiy maqolalar — {topic} mavzusida jurnal chop etilgan tadqiqotlar, 2023-2025.",
        "4. Rasmiy statistik ma'lumotlar portali.",
        "5. Xalqaro tajriba — ilg'or mamlakatlar amaliyoti.",
    ]
    if lbl is L["ru"]:
        refs = [
            f"1. Законодательные акты Республики Узбекистан по теме «{topic[:40]}».",
            f"2. Монографии и учебные пособия по теме «{topic[:40]}». Ташкент, 2024.",
            f"3. Научные статьи по теме «{topic[:40]}», 2023-2025.",
            "4. Официальный портал статистических данных.",
            "5. Международный опыт передовых стран.",
        ]
    elif lbl is L["en"]:
        refs = [
            f"1. Legislative acts of the Republic of Uzbekistan on «{topic[:40]}».",
            f"2. Monographs and textbooks on «{topic[:40]}». Tashkent, 2024.",
            f"3. Scientific articles on «{topic[:40]}», 2023-2025.",
            "4. Official statistical data portal.",
            "5. International experience of leading countries.",
        ]
    for ref in refs:
        p = doc.add_paragraph(ref)
        p.paragraph_format.line_spacing = 1.5
        for run in p.runs:
            run.font.size = Pt(13); run.font.name = "Times New Roman"

def _add_intro(doc, topic, lbl, include_object=False, content_text=""):
    _add_heading(doc, lbl["intro"], level=1, center=True)
    _add_label_para(doc, lbl["relevance"],
        f"Today, the topic of {topic} is of particular relevance. This field is developing rapidly in line with modern requirements and occupies an important place in society. The main reason for this research is to identify gaps in the topic and develop ways to address them.")
    _add_label_para(doc, lbl["goal"],
        f"To analyze the current state of {topic}, identify problems, and develop practical recommendations for solving them.")
    if include_object:
        _add_label_para(doc, lbl["object"], f"{topic} sohasidagi iqtisodiy-ijtimoiy jarayonlar va ularni boshqarish tizimi.")
        _add_label_para(doc, lbl["subject"], f"{topic} ni optimallashtirish va samaradorligini oshirish jarayonidagi munosabatlar.")
    if content_text:
        _add_para(doc, content_text[:600])

def _add_chapter(doc, num, title, body, lbl, subsections=None):
    _add_heading(doc, f'{lbl["chapter"]} {num}. {title}', level=1)
    if subsections:
        for sub_num, sub_title in subsections:
            _add_heading(doc, f"{num}.{sub_num}. {sub_title}", level=2)
    paras = [p for p in body.split("\n") if p.strip()]
    for p in paras[:8]:
        _add_para(doc, p)
    if not paras:
        _add_para(doc, f"A detailed analysis of {title}, statistical data and practical observations are presented. This chapter examines the theoretical foundations, classification principles and international experience.")

def _add_conclusion(doc, topic, lbl, conclusion_key="conclusion"):
    _add_heading(doc, lbl[conclusion_key], level=1, center=True)
    points = [
        f"1. As a result of the analysis of {topic}, the current state and development prospects were identified.",
        f"2. Mavjud muammolar va ularning sabablari tizimlashtirildi, ulardan xalos bo'lishning ustuvor yo'llari belgilandi.",
        f"3. Taklif etilayotgan chora-tadbirlar amalga oshirilishi bilan samaradorlik sezilarli darajada oshirilishi mumkin.",
        f"4. In the future, a deeper study of this field and expansion of scientific research are necessary.",
    ]
    if lbl is L["ru"]:
        points = [
            f"1. В результате анализа по теме «{topic}» выявлено современное состояние и перспективы развития.",
            f"2. Систематизированы существующие проблемы и их причины, определены приоритетные пути решения.",
            f"3. Реализация предложенных мероприятий позволит значительно повысить эффективность.",
            f"4. В дальнейшем необходимо углублённое изучение данной сферы и расширение научных исследований.",
        ]
    elif lbl is L["en"]:
        points = [
            f"1. The analysis on «{topic}» revealed the current state and development prospects.",
            f"2. Existing problems and their causes were systematized; priority solutions identified.",
            f"3. Implementation of proposed measures can significantly improve efficiency.",
            f"4. Further in-depth study and expanded research in this field is necessary.",
        ]
    for pt in points:
        _add_para(doc, pt, indent=False)

# ===== Asosiy funksiya =====
def generate_docx(topic, service_name, service_code, lang, pages, content_text, author=""):
    doc = Document()
    # Standart stil
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(14)
    # Sahifa parametrlari
    section = doc.sections[0]
    section.top_margin = Cm(2); section.bottom_margin = Cm(2)
    section.left_margin = Cm(3); section.right_margin = Cm(1.5)
    _add_footer(section, lang)

    lbl = _lbl(lang)
    content_text = content_text or ""

    if service_code == "test":
        return _generate_test(doc, topic, lang, pages, content_text, author, lbl)
    if service_code == "maqola":
        return _generate_article(doc, topic, lang, content_text, author, lbl)
    if service_code == "tezis":
        return _generate_thesis(doc, topic, lang, content_text, author, lbl)
    if service_code == "insho":
        return _generate_essay(doc, topic, lang, content_text, author, lbl)

    # Akademik turlar: referat, mustaqil, kurs, diplom
    include_dept = service_code in ("kurs", "diplom")
    _add_title_page(doc, service_code, topic, author, lbl, include_dept=include_dept)

    # Boblar soni
    if service_code == "referat":
        chapters = [("Nazariy asoslar", None), ("Tahlil va amaliy qism", None)]
        concl_key = "conclusion"
    elif service_code == "mustaqil":
        chapters = [("Asosiy tushunchalar", None), ("Amaliy qism", None)]
        concl_key = "conclusion"
    elif service_code == "kurs":
        chapters = [
            ("Nazariy asoslar", [("1", "Tushuncha va kelib chiqish sabablari"), ("2", "Xalqaro tajriba")]),
            ("Tahlil qismi", [("1", "Holat tahlili"), ("2", "Muammolarni baholash")]),
            ("Recommendations", [("1", "Implementation of new methods"), ("2", "Recommendations for improvement")]),
        ]
        concl_key = "conclusion_kurs"
    else:  # diplom
        chapters = [
            ("Nazariy-metodologik asoslar", [("1", "Tushuncha va tasniflash"), ("2", "Zamonaviy usullar roli")]),
            ("Tahlil va baholash", [("1", "Ko'rsatkichlar dinamikasi"), ("2", "Mavjud tizim samaradorligi")]),
            ("Takliflar va samaradorlik", [("1", "Yangi modelni joriy etish"), ("2", "Iqtisodiy samaradorlik hisobi")]),
        ]
        concl_key = "conclusion_diplom"

    # Mundarija
    toc_items = [(lbl["intro"], "3")]
    for i, (ct, subs) in enumerate(chapters, 1):
        toc_items.append((f'{lbl["chapter"]} {i}. {ct}', str(4 + i*3)))
    toc_items.append((lbl[concl_key], str(4 + len(chapters)*3 + 2)))
    toc_items.append((lbl["references"], str(4 + len(chapters)*3 + 4)))
    if service_code == "diplom":
        toc_items.append((lbl["appendix"], str(4 + len(chapters)*3 + 6)))
    _add_toc(doc, toc_items, lbl)

    # Kirish
    _add_intro(doc, topic, lbl, include_object=(service_code in ("kurs","diplom")),
               content_text=content_text[:400])
    doc.add_page_break()

    # Boblar — kontentni taqsimlaymiz
    parts = _split_content(content_text, len(chapters))
    for i, ((ct, subs), body) in enumerate(zip(chapters, parts), 1):
        _add_chapter(doc, i, ct, body, lbl, subsections=subs)
        # Maxsus ramkalar
        if i == 1:
            _add_box(doc, lbl["important_def"],
                     f"«{topic}» is a fundamental category of the field whose essence must be fully understood.\nThis definition is the key to an in-depth study of the theoretical foundations.")
        if service_code == "mustaqil" and i == len(chapters):
            _add_box(doc, lbl["practical_tip"],
                     "Har doim 2 bosqichli autentifikatsiyadan foydalaning va parollarni muntazam yangilab boring!")
        if service_code in ("kurs", "diplom") and i == 2:
            _add_box(doc, lbl["stats"],
                     "According to international agencies, this indicator is projected to exceed 50% by 2030.")
        doc.add_page_break()

    # Xulosa
    _add_conclusion(doc, topic, lbl, conclusion_key=concl_key)
    doc.add_page_break()

    # Adabiyotlar
    _add_references(doc, topic, lbl)

    # Ilavalar (faqat diplom)
    if service_code == "diplom":
        doc.add_page_break()
        _add_heading(doc, lbl["appendix"], level=1, center=True)
        _add_para(doc, "Ilova 1. Jadval shaklida asosiy ko'rsatkichlar.", indent=False)
        _add_para(doc, "Ilova 2. Grafiklar va diagrammalar.", indent=False)
        _add_para(doc, "Ilova 3. So'rovnoma natijalari.", indent=False)

    buf = io.BytesIO()
    doc.save(buf); buf.seek(0)
    return buf

def _generate_essay(doc, topic, lang, content_text, author, lbl):
    """Insho / Esse."""
    doc.add_paragraph()
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(f"{lbl.get('essay_style','ESSAY')}"); r.font.size = Pt(14); r.font.italic = True; r.font.name = "Times New Roman"
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(f'{lbl["topic_label"]} {topic}'); r.font.size = Pt(18); r.font.bold = True; r.font.name = "Times New Roman"
    author_pairs = _parse_author(author, lbl)
    for lab, val in author_pairs:
        p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(f"{lab} {val}"); r.font.size = Pt(13); r.font.name = "Times New Roman"
    doc.add_paragraph()
    _add_heading(doc, lbl["intro"], level=1, center=True)
    _add_para(doc, f"«{topic}» is acquiring ever greater significance. Today this subject is important not only scientifically but also ethically. It deeply affects a person's inner world and the relationship with the environment.")
    _add_label_para(doc, "💭 " + lbl["goal"], f"{topic} haqidagi o'z qarashlarimni asoslash va oqibatlarini tahlil qilish.")
    doc.add_paragraph()
    _add_heading(doc, lbl.get("chapter","ASOSIY QISM") + ": " + lbl.get("box_titles",["Tahlil"])[0] if False else "ASOSIY QISM", level=1, center=True)
    parts = _split_content(content_text, 3)
    for i, part in enumerate(parts):
        _add_para(doc, part or f"A deep analysis and reflections on {topic}. Human history shows that every great idea emerges from people's aspiration and labor.")
    _add_box(doc, lbl["quote"],
             '"Kitob — vaqt ummonida suzib yurgan va o\'zining qimmatbaho yukini avloddan-avlodga aytib berayotgan kemadir."\n— Frensis Bekon',
             bg_hex="F3E5F5")
    doc.add_paragraph()
    _add_heading(doc, lbl["conclusion"], level=1, center=True)
    _add_para(doc, f"In conclusion, {topic} is the greatest investment in the future. Every new discovery brightens the road ahead.")
    _add_box(doc, lbl["final_wisdom"],
             "Dunyoni o'zgartirmoqchi bo'lsangiz, avvalo o'zingizdan boshlang va bilim olishni hech vaqt to'xtatmang!",
             bg_hex="E8F5E9")
    buf = io.BytesIO(); doc.save(buf); buf.seek(0)
    return buf

def _parse_test_questions(content_text, n_q, topic, lang):
    """AI matnidan savollar + variantlar + to'g'ri javob + izohni ajratib oladi.
    Hech qachon variant ichida to'g'ri javob belgisi qolmaydi — hammasi oxirgi kalitda."""
    AK_RAT = {"uz": "To'g'ri javob — mavzuning asosiy mohiyatini ifodalaydi.",
              "ru": "Правильный ответ отражает суть темы.",
              "en": "The correct answer reflects the core essence of the topic.",
              "tr": "Doğru cevap konunun temel özünü yansıtır.",
              "de": "Die richtige Antwort spiegelt den Kern des Themas wider.",
              "fr": "La bonne réponse reflète l'essence du sujet."}
    default_rat = AK_RAT.get(str(lang).lower(), AK_RAT["en"])
    questions = []
    if content_text and len(str(content_text).strip()) > 50:
        lines = [ln.rstrip() for ln in str(content_text).split("\n")]
        cur = None
        opt_re = re.compile(r'^\s*([A-Da-d1-4])[\.\)]\s*(.+)$')
        qhead_re = re.compile(r'^\s*(\d+)[\.\-\)]\s*(?:SAVOL|QUESTION|SORU|FRAGE|ВОПРОС|Вопрос|Question)?\s*[:\-]?\s*(.*)$', re.I)
        rat_re = re.compile(r'^\s*(?:💡\s*)?(?:Izoh|Rationale|Açıklama|Begründung|Explication|Обоснование|Explanation)\s*[:\-]?\s*(.*)$', re.I)
        for ln in lines:
            if not ln.strip():
                continue
            qm = qhead_re.match(ln)
            om = opt_re.match(ln)
            rm = rat_re.match(ln)
            if qm and not om and len(qm.group(2) or "") > 3:
                if cur: questions.append(cur)
                cur = {"text": qm.group(2).strip(), "options": [], "correct": None, "rationale": ""}
            elif om and cur is not None:
                opt_text = om.group(2).strip()
                is_correct = ("✓" in opt_text) or ("✔" in opt_text) or ("(✓" in opt_text) or ("to'g'ri javob" in opt_text.lower()) or ("correct answer" in opt_text.lower()) or ("doğru cevap" in opt_text.lower()) or ("richtige antwort" in opt_text.lower()) or ("bonne réponse" in opt_text.lower()) or ("правильный ответ" in opt_text.lower())
                # To'g'ri javob belgisini variant matnidan tozalash
                opt_text = re.sub(r'\s*\(?(?:✓|✔)[^)]*\)?', '', opt_text).strip()
                opt_text = re.sub(r'\s*\([^)]*(to\'g\'ri|correct|doğru|richtige|bonne|правильн)[^)]*\)', '', opt_text, flags=re.I).strip()
                letter = "ABCD"["ABCD1234".find(om.group(1).upper()) % 4] if om.group(1).upper() in "ABCD1234" else "A"
                cur["options"].append((letter, opt_text))
                if is_correct:
                    cur["correct"] = letter
            elif rm and cur is not None:
                cur["rationale"] = rm.group(1).strip()
            elif cur is not None and not om:
                # savol matnining davomi
                if len(cur["options"]) == 0:
                    cur["text"] = (cur["text"] + " " + ln.strip()).strip()
        if cur: questions.append(cur)
    # Fallback — agar AI matni parse bo'lmasa (til-neytral, o'zbekchasiz)
    fallback_opts = [
        "The most complete and detailed answer reflecting the essence of the topic.",
        "An alternative approach to the question.",
        "A practical indicator related to the topic.",
        "International experience on the issue.",
    ]
    while len(questions) < n_q:
        i = len(questions) + 1
        questions.append({
            "text": f"Question {i} on the topic: {topic}. Which aspect is most important? Choose the correct answer.",
            "options": [("A", fallback_opts[0]), ("B", fallback_opts[1]), ("C", fallback_opts[2]), ("D", fallback_opts[3])],
            "correct": "ABCD"[i % 4], "rationale": default_rat,
        })
    out = []
    for i, q in enumerate(questions[:n_q]):
        opts = q["options"]
        if len(opts) < 4:
            used = {o[0] for o in opts}
            for L in "ABCD":
                if L not in used:
                    opts.append((L, fallback_opts[len(opts) % 4]))
                if len(opts) >= 4: break
        q["options"] = opts[:4]
        if not q["correct"]:
            q["correct"] = "ABCD"[i % 4]
        if not q["rationale"]:
            q["rationale"] = default_rat
        out.append(q)
    return out

def _generate_test(doc, topic, lang, pages, content_text, author, lbl):
    """Quiz / Test — variantlarda to'g'ri javob belgilanmaydi; oxirida JAVOBLAR KALITI + izoh."""
    AK = {"uz": "JAVOBLAR KALITI VA IZOHLAR", "ru": "КЛЮЧ К ОТВЕТАМ И ОБЪЯСНЕНИЯ",
          "en": "ANSWER KEY AND EXPLANATIONS", "tr": "CEVAP ANAHTARI VE AÇIKLAMALAR",
          "de": "LÖSUNGSSCHLÜSSEL UND ERKLÄRUNGEN", "fr": "CORRIGÉ ET EXPLICATIONS"}
    ak_title = AK.get(str(lang).lower(), AK["en"])
    doc.add_paragraph()
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(lbl["test_title"]); r.font.size = Pt(18); r.font.bold = True; r.font.name = "Times New Roman"
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(f'{lbl["topic_label"]} {topic}'); r.font.size = Pt(15); r.font.name = "Times New Roman"
    n_q = max(5, min(30, pages))
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(f'{lbl["questions_count"]}: {n_q}   •   {lbl["level"]}'); r.font.size = Pt(13); r.font.italic = True; r.font.name = "Times New Roman"
    author_pairs = _parse_author(author, lbl)
    for lab, val in author_pairs:
        p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(f"{lab} {val}"); r.font.size = Pt(12); r.font.name = "Times New Roman"
    doc.add_paragraph()

    questions = _parse_test_questions(content_text, n_q, topic, lang)
    answer_key = []  # (raqam, to'g'ri harf, izoh)
    for i, q in enumerate(questions, 1):
        _add_heading(doc, f'{i}. {lbl["question"]}', level=2)
        _add_para(doc, q["text"], indent=False)
        for letter, opt in q["options"]:
            p = doc.add_paragraph(f"{letter}) {opt}")
            p.paragraph_format.left_indent = Cm(1)
            for run in p.runs:
                run.font.size = Pt(13); run.font.name = "Times New Roman"
        answer_key.append((i, q["correct"], q["rationale"]))
        doc.add_paragraph()

    # === OXIRIDA — JAVOBLAR KALITI VA IZOHLAR (alohida sahifada) ===
    doc.add_page_break()
    _add_heading(doc, ak_title, level=1, center=True)
    doc.add_paragraph()
    for num, letter, rationale in answer_key:
        p = doc.add_paragraph()
        p.paragraph_format.line_spacing = 1.3
        p.paragraph_format.space_after = Pt(6)
        r1 = p.add_run(f"{num}-{letter}.  "); r1.font.bold = True; r1.font.size = Pt(13); r1.font.name = "Times New Roman"; r1.font.color.rgb = RGBColor(20, 120, 40)
        r2 = p.add_run(f"{lbl['rationale']} {rationale}"); r2.font.size = Pt(12); r2.font.name = "Times New Roman"
    buf = io.BytesIO(); doc.save(buf); buf.seek(0)
    return buf

def _generate_article(doc, topic, lang, content_text, author, lbl):
    """Maqola."""
    doc.add_paragraph()
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(f"📰 {topic}"); r.font.size = Pt(18); r.font.bold = True; r.font.name = "Times New Roman"
    author_pairs = _parse_author(author, lbl)
    for lab, val in author_pairs:
        p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(f"{lab} {val}"); r.font.size = Pt(12); r.font.name = "Times New Roman"
    doc.add_paragraph()
    _add_label_para(doc, lbl["annotation"],
        f"This article analyzes the current state of {topic}, development prospects and practical recommendations. Priority directions have been identified.")
    _add_label_para(doc, lbl["keywords"], f"{topic}, analysis, development, efficiency, recommendations.")
    doc.add_paragraph()
    _add_heading(doc, lbl["intro"], level=1, center=True)
    _add_para(doc, f"Today, {topic} has become one of the globally important issues. Therefore an in-depth study of this field is the demand of the time.")
    doc.add_paragraph()
    _add_heading(doc, "ASOSIY QISM", level=1, center=True)
    parts = _split_content(content_text, 3)
    for part in parts:
        _add_para(doc, part or f"A detailed analysis of {topic} is presented. Statistical data, international experience and national practice are compared.")
    _add_box(doc, lbl["stats"],
             "According to international agencies, this indicator is projected to exceed 50% by 2030, which will bring both new opportunities and challenges.",
             bg_hex="E3F2FD")
    doc.add_paragraph()
    _add_heading(doc, lbl["conclusion"], level=1, center=True)
    _add_para(doc, f"In conclusion, developing the field of {topic} is the guarantee of a sustainable future. Cooperation of all parties is needed.")
    _add_box(doc, lbl["author_recommendation"],
             "It is necessary to further encourage the study of this field among the public and business entities. Support through government programs should be expanded.",
             bg_hex="FFF3E0")
    buf = io.BytesIO(); doc.save(buf); buf.seek(0)
    return buf

def _generate_thesis(doc, topic, lang, content_text, author, lbl):
    """Ilmiy tezis."""
    doc.add_paragraph()
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(lbl["thesis"]); r.font.size = Pt(16); r.font.bold = True; r.font.name = "Times New Roman"
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(f'{lbl["topic_label"]} {topic.upper()}'); r.font.size = Pt(15); r.font.bold = True; r.font.name = "Times New Roman"
    author_pairs = _parse_author(author, lbl)
    for lab, val in author_pairs:
        p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(f"{lab} {val}"); r.font.size = Pt(12); r.font.name = "Times New Roman"
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(f'{lbl["email"]} example@mail.uz'); r.font.size = Pt(11); r.font.italic = True; r.font.name = "Times New Roman"
    doc.add_paragraph()
    _add_label_para(doc, lbl["relevance_thesis"],
        f"Today, improving the field of {topic} has become a demand of the time. The goal of the research is to develop new methods for increasing efficiency in this field.")
    _add_label_para(doc, lbl["methods"],
        "Tadqiqot davomida tahlil-sintez, qiyosiy-statistik, matematik modellashtirish va ekspert baholash usullaridan foydalanildi. 200 nafar ishtirokchi orqali sinov o'tkazildi.")
    doc.add_paragraph()
    parts = _split_content(content_text, 2)
    for part in parts:
        _add_para(doc, part or f"The results of the research on {topic} are presented. The data obtained proved statistically reliable.")
    _add_box(doc, lbl["results"],
             "The experimental group's indicators showed results 23% higher according to the theoretical hypothesis. This confirms the effectiveness of the proposed model.",
             bg_hex="E8F5E9")
    doc.add_paragraph()
    _add_heading(doc, lbl["conclusion"], level=1, center=True)
    _add_para(doc, f"Olingan natijalar shuni ko'rsatadiki, {topic} sohasida yangi yondashuvlarni joriy etish samaradorlikni sezilarli darajada oshiradi.")
    _add_box(doc, lbl["scientific_rec"],
             "It is necessary to create a national platform for this field at universities and expand staff training.",
             bg_hex="F3E5F5")
    buf = io.BytesIO(); doc.save(buf); buf.seek(0)
    return buf
