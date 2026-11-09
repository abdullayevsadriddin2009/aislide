"""Akademik xizmatlar uchun yagona tuzilma va sahifa byudjetlari.

Referat, kurs ishi, diplom ishi, ilmiy maqola va tezis bir xil manbadan
foydalanadi: AI matn yozishda ham, DOCX sahifalarni joylashda ham shu reja
olinadi. Shu tufayli mundarija sahifa raqamlari haqiqiy joylashuvga mos keladi
va hech bir sahifa bo'sh qolmaydi.
"""

LANGS = ("uz", "ru", "en", "tr", "de", "fr")

# ===== Sarlavhalar (6 til) =====
SECTION_TITLES = {
    "plan": ("REJA", "ПЛАН", "OUTLINE", "PLAN", "GLIEDERUNG", "PLAN"),
    "toc": ("MUNDARIJA", "СОДЕРЖАНИЕ", "CONTENTS", "İÇİNDEKİLER", "INHALT", "SOMMAIRE"),
    "intro": ("KIRISH", "ВВЕДЕНИЕ", "INTRODUCTION", "GİRİŞ", "EINLEITUNG", "INTRODUCTION"),
    "concl": ("XULOSA", "ЗАКЛЮЧЕНИЕ", "CONCLUSION", "SONUÇ", "FAZIT", "CONCLUSION"),
    "concl_dipl": ("XULOSA VA TAKLIFLAR", "ЗАКЛЮЧЕНИЕ И ПРЕДЛОЖЕНИЯ", "CONCLUSION AND RECOMMENDATIONS",
                   "SONUÇ VE ÖNERİLER", "FAZIT UND EMPFEHLUNGEN", "CONCLUSION ET RECOMMANDATIONS"),
    "refs": ("FOYDALANILGAN ADABIYOTLAR RO‘YXATI", "СПИСОК ИСПОЛЬЗОВАННОЙ ЛИТЕРАТУРЫ",
             "REFERENCES", "KAYNAKÇA", "LITERATURVERZEICHNIS", "RÉFÉRENCES"),
    "appendix": ("ILOVALAR", "ПРИЛОЖЕНИЯ", "APPENDICES", "EKLER", "ANHÄNGE", "ANNEXES"),
    "task": ("TOPSHIRIQ", "ЗАДАНИЕ", "ASSIGNMENT", "GÖREV", "AUFGABENSTELLUNG", "DEVOIR"),
    "annot": ("ANNOTATSIYA", "АННОТАЦИЯ", "ANNOTATION", "ÖZET", "ZUSAMMENFASSUNG", "RÉSUMÉ"),
    "abstract": ("Annotatsiya", "Аннотация", "Abstract", "Öz", "Zusammenfassung", "Résumé"),
    "keywords": ("Kalit so‘zlar", "Ключевые слова", "Keywords", "Anahtar kelimeler",
                 "Schlüsselwörter", "Mots-clés"),
    "reviewer": ("Taqrizchi", "Рецензент", "Reviewer", "Değerlendirici", "Gutachter", "Rapporteur"),
    "chapter": ("BOB", "ГЛАВА", "CHAPTER", "BÖLÜM", "KAPITEL", "CHAPITRE"),
    "task_content": ("Ishning mazmuni", "Содержание работы", "Scope of the work",
                     "Çalışmanın içeriği", "Inhalt der Arbeit", "Contenu du travail"),
    "task_deadline": ("Topshirish muddati", "Срок сдачи", "Submission deadline",
                      "Teslim tarihi", "Abgabetermin", "Date de remise"),
    "task_student": ("Bajaruvchi", "Исполнитель", "Student", "Öğrenci", "Bearbeiter", "Étudiant"),
    "task_supervisor": ("Ilmiy rahbar", "Научный руководитель", "Supervisor", "Danışman",
                        "Betreuer", "Directeur de recherche"),
    # Referat / kurs / diplom bandlari
    "s_theory": ("Mavzuning nazariy asoslari", "Теоретические основы темы",
                 "Theoretical foundations of the topic", "Konunun teorik temelleri",
                 "Theoretische Grundlagen des Themas", "Fondements théoriques du sujet"),
    "s_concepts": ("Asosiy tushunchalar va ilmiy yondashuvlar", "Основные понятия и научные подходы",
                   "Key concepts and scholarly approaches", "Temel kavramlar ve bilimsel yaklaşımlar",
                   "Grundbegriffe und wissenschaftliche Ansätze", "Concepts clés et approches scientifiques"),
    "s_foreign": ("Xorijiy tajriba va adabiyotlar tahlili", "Зарубежный опыт и анализ литературы",
                  "International experience and literature review", "Yabancı deneyim ve literatür analizi",
                  "Internationale Erfahrungen und Literaturanalyse", "Expérience internationale et analyse de la littérature"),
    "s_practice": ("Amaliy ahamiyati va asosiy xulosalar", "Практическое значение и основные выводы",
                   "Practical significance and main findings", "Pratik önemi ve temel bulgular",
                   "Praktische Bedeutung und wichtigste Ergebnisse", "Portée pratique et principaux résultats"),
    "s_status": ("Sohaning bugungi holati", "Современное состояние сферы", "Current state of the field",
                 "Alanın güncel durumu", "Aktueller Stand des Bereichs", "État actuel du domaine"),
    "s_problems": ("Muammolar va ularning sabablari", "Проблемы и их причины", "Problems and their causes",
                   "Sorunlar ve nedenleri", "Probleme und ihre Ursachen", "Problèmes et leurs causes"),
    "s_solutions": ("Rivojlantirish bo‘yicha takliflar", "Предложения по развитию", "Proposals for development",
                    "Geliştirme önerileri", "Entwicklungsvorschläge", "Propositions de développement"),
    "s_method": ("Tahlil metodikasi va ma’lumotlar bazasi", "Методика анализа и база данных",
                 "Analysis methodology and data base", "Analiz metodolojisi ve veri tabanı",
                 "Analysemethodik und Datenbasis", "Méthodologie d’analyse et base de données"),
    "s_stats": ("Aniq holat va statistik tahlil", "Фактическое состояние и статистический анализ",
                "Concrete situation and statistical analysis", "Somut durum ve istatistiksel analiz",
                "Konkrete Lage und statistische Analyse", "Situation concrète et analyse statistique"),
    "s_factors": ("Muammolar va omillar tahlili", "Анализ проблем и факторов", "Analysis of problems and factors",
                  "Sorunlar ve faktör analizi", "Analyse von Problemen und Faktoren", "Analyse des problèmes et facteurs"),
    "s_model": ("Rivojlantirish modeli va istiqbollar", "Модель развития и перспективы",
                "Development model and prospects", "Gelişim modeli ve perspektifler",
                "Entwicklungsmodell und Perspektiven", "Modèle de développement et perspectives"),
    "s_offers": ("Amaliy takliflar va kutilayotgan samaradorlik", "Практические предложения и ожидаемая эффективность",
                 "Practical proposals and expected efficiency", "Pratik öneriler ve beklenen verimlilik",
                 "Praktische Vorschläge und erwartete Effizienz", "Propositions pratiques et efficacité attendue"),
    "s_ch1": ("Nazariy asoslar", "Теоретические основы", "Theoretical foundations",
              "Teorik temeller", "Theoretische Grundlagen", "Fondements théoriques"),
    "s_ch2": ("Tahlil va baholash", "Анализ и оценка", "Analysis and assessment",
              "Analiz ve değerlendirme", "Analyse und Bewertung", "Analyse et évaluation"),
    "s_ch3": ("Takliflar va istiqbollar", "Предложения и перспективы", "Recommendations and prospects",
              "Öneriler ve perspektifler", "Empfehlungen und Perspektiven", "Recommandations et perspectives"),
    "imrad_intro": ("Introduction", "Введение", "Introduction", "Giriş", "Einleitung", "Introduction"),
    "imrad_method": ("Methodology", "Методология", "Methodology", "Yöntem", "Methodik", "Méthodologie"),
    "imrad_results": ("Results and Discussion", "Результаты и обсуждение", "Results and Discussion",
                      "Sonuçlar ve tartışma", "Ergebnisse und Diskussion", "Résultats et discussion"),
    "imrad_concl": ("Conclusion", "Заключение", "Conclusion", "Sonuç", "Fazit", "Conclusion"),
    "thesis_intro": ("Kirish", "Введение", "Introduction", "Giriş", "Einleitung", "Introduction"),
    "thesis_problem": ("Muammo va uning yechimi", "Проблема и её решение", "Problem and its solution",
                       "Sorun ve çözümü", "Problem und Lösung", "Problème et solution"),
    "thesis_concl": ("Xulosa", "Заключение", "Conclusion", "Sonuç", "Fazit", "Conclusion"),
    "table1": ("1-jadval. Mavzuning qiyosiy tahlili", "Таблица 1. Сравнительный анализ темы",
               "Table 1. Comparative analysis of the topic", "Tablo 1. Konunun karşılaştırmalı analizi",
               "Tabelle 1. Vergleichende Analyse des Themas", "Tableau 1. Analyse comparative du sujet"),
    "table2": ("2-jadval. Muammolar va yechimlar", "Таблица 2. Проблемы и решения",
               "Table 2. Problems and solutions", "Tablo 2. Sorunlar ve çözümler",
               "Tabelle 2. Probleme und Lösungen", "Tableau 2. Problèmes et solutions"),
    "row_org": ("Tashkiliy shakl", "Организационная форма", "Organisational form",
                "Örgütsel biçim", "Organisationsform", "Forme organisationnelle"),
    "row_source": ("Ma’lumot manbasi", "Источник данных", "Data source", "Veri kaynağı",
                   "Datenquelle", "Source des données"),
    "row_control": ("Nazorat tizimi", "Система контроля", "Control system", "Kontrol sistemi",
                    "Kontrollsystem", "Système de contrôle"),
    "row_result": ("Kutilayotgan natija", "Ожидаемый результат", "Expected result", "Beklenen sonuç",
                   "Erwartetes Ergebnis", "Résultat attendu"),
    "col_criteria": ("Mezon", "Критерий", "Criterion", "Ölçüt", "Kriterium", "Critère"),
    "col_old": ("An’anaviy yondashuv", "Традиционный подход", "Traditional approach", "Geleneksel yaklaşım",
                "Traditioneller Ansatz", "Approche traditionnelle"),
    "col_new": ("Zamonaviy yondashuv", "Современный подход", "Modern approach", "Modern yaklaşım",
                "Moderner Ansatz", "Approche moderne"),
    "col_problem": ("Muammo", "Проблема", "Problem", "Sorun", "Problem", "Problème"),
    "col_cause": ("Sabab", "Причина", "Cause", "Neden", "Ursache", "Cause"),
    "col_solution": ("Yechim", "Решение", "Solution", "Çözüm", "Lösung", "Solution"),
}
_T = {key: dict(zip(LANGS, values)) for key, values in SECTION_TITLES.items()}


def title(key, lang="uz"):
    """Sarlavhani tanlangan tilda qaytaradi."""
    lang = str(lang or "uz").lower()
    table = _T.get(key, {})
    return table.get(lang) or table.get("en") or key


# ===== Bo'lim tavsiflari (AI uchun, ingliz tilida ko'rsatma) =====
DESCRIPTIONS = {
    "intro_short": (
        "Write the introduction as three separate paragraphs that start exactly with "
        "“Relevance of the topic:”, “Goal of the work:”, “Tasks:”. The first explains why the "
        "topic matters today, the second states the goal, the third lists 4-6 concrete tasks."
    ),
    "intro_kurs": (
        "Write the introduction as five separate labeled paragraphs starting exactly with "
        "“Relevance of the topic:”, “Goal of the work:”, “Tasks:”, “Object of the research:”, "
        "“Subject of the research:”. Be specific about the topic."
    ),
    "intro_dipl": (
        "Write the introduction as six separate labeled paragraphs starting exactly with "
        "“Relevance of the topic:”, “Goal of the work:”, “Tasks:”, “Object of the research:”, "
        "“Subject of the research:”, “Research methods:”. Add structural detail for a diploma thesis."
    ),
    "theory": "Explain the theoretical basis of the topic, its key concepts, definitions and scholarly views in depth.",
    "concepts": "Present the core concepts, classifications and scientific approaches with clear explanations.",
    "foreign": "Present international experience and a review of the scholarly literature on the topic.",
    "practice": "Show the practical significance of the topic and the main findings that follow from it.",
    "status": "Describe the current state of the field with concrete tendencies, mechanisms and real examples.",
    "problems": "Identify the main problems, explain their causes and show how they affect the field.",
    "solutions": "Give concrete, realistic proposals for development and explain their expected effect.",
    "method": "Describe the methodology of the analysis, the data base used and the logic of the calculations.",
    "stats": "Analyse the concrete situation in depth: dynamics, structure, comparisons between periods or regions.",
    "factors": "Analyse the problems and factors that shape them, showing cause-and-effect relations.",
    "model": "Present the development model and the prospects of the field, with mechanisms of implementation.",
    "offers": "Give practical proposals and describe the expected efficiency (organisational, social, economic).",
    "concl_short": (
        "Write the conclusion as 4-5 numbered points that summarise the findings of the work. "
        "Do not introduce new information."
    ),
    "concl_long": (
        "Write the conclusion as 7-9 numbered points that summarise the findings, and add 2-3 "
        "sentences about future research. Do not introduce new information."
    ),
    "concl_dipl": (
        "Write the conclusion as 8-10 numbered points that summarise the findings, followed by "
        "a separate recommendation part with 4-5 numbered practical proposals."
    ),
    "imrad_intro": (
        "Write the introduction of a scientific article: state the problem, the gap in the literature, "
        "the aim and the novelty of the study."
    ),
    "imrad_method": (
        "Describe the research methodology: methods, data, sample or materials, and the order of the analysis."
    ),
    "imrad_results": (
        "Present the results and discuss them: concrete findings, comparisons, interpretation and "
        "their agreement or disagreement with previous studies."
    ),
    "imrad_concl": (
        "Write a short conclusion of the article: the main result, its scientific and practical meaning, "
        "and one or two lines about further research."
    ),
    "thesis_intro": "Introduce the topic in one or two sentences and state the purpose of the theses.",
    "thesis_problem": "State the scientific or practical problem and explain the proposed solution with its result.",
    "thesis_concl": "Write one short concluding paragraph with the main result and its significance.",
}

# ===== Tuzilmalar =====
# body: (marker, title_key, description_key, weight)
STRUCTURES = {
    "referat": {
        "front": ("plan",),
        "intro": ("KIRISH", "intro", "intro_short"),
        "body": [
            ("1", "s_theory", "theory", 1),
            ("2", "s_concepts", "concepts", 1),
            ("3", "s_practice", "practice", 1),
        ],
        "body_count": 2,
        "concl": ("XULOSA", "concl", "concl_short"),
        "concl_pages": 1,
        "refs": 0,
        "refs_range": (5, 5),
        "plan": True,
        "toc": False,
    },
    "kurs": {
        "front": ("toc",),
        "intro": ("KIRISH", "intro", "intro_kurs"),
        "body": [
            ("1.1", "s_theory", "theory", 1),
            ("1.2", "s_concepts", "concepts", 1),
            ("1.3", "s_foreign", "foreign", 1),
            ("2.1", "s_status", "status", 1),
            ("2.2", "s_problems", "problems", 1),
            ("2.3", "s_solutions", "solutions", 1),
        ],
        "chapters": {"1": "s_ch1", "2": "s_ch2"},
        "intro_pages": 2,
        "concl": ("XULOSA", "concl", "concl_long"),
        "concl_pages": 2,
        "refs": 1,
        "refs_range": (12, 15),
        "tables": True,
        "toc": True,
    },
    "diplom": {
        "front": ("task", "annot", "toc"),
        "intro": ("KIRISH", "intro", "intro_dipl"),
        "body": [
            ("1.1", "s_theory", "theory", 1),
            ("1.2", "s_concepts", "concepts", 1),
            ("2.1", "s_method", "method", 1),
            ("2.2", "s_stats", "stats", 1),
            ("2.3", "s_factors", "factors", 1),
            ("3.1", "s_model", "model", 1),
            ("3.2", "s_offers", "offers", 1),
        ],
        "chapters": {"1": "s_ch1", "2": "s_ch2", "3": "s_ch3"},
        "intro_pages": 4,
        "concl": ("XULOSA", "concl_dipl", "concl_dipl"),
        "concl_pages": 2,
        "refs": 2,
        "refs_range": (30, 35),
        "appendix": 2,
        "tables": True,
        "toc": True,
    },
}

# Maqola (IMRAD) va tezis sahifa taqsimoti (12 pt, 1.15 interval).
ARTICLE_STRUCTURE = [
    ("INTRO", "imrad_intro", "imrad_intro", 2),
    ("METHOD", "imrad_method", "imrad_method", 2),
    ("RESULTS", "imrad_results", "imrad_results", 5),
    ("CONCL", "imrad_concl", "imrad_concl", 1),
]
THESIS_STRUCTURE = [
    ("INTRO", "thesis_intro", "thesis_intro", 1),
    ("PROBLEM", "thesis_problem", "thesis_problem", 2),
    ("CONCL", "thesis_concl", "thesis_concl", 1),
]
COMPACT_SERVICES = ("maqola", "tezis")
ACADEMIC_SERVICES = ("referat", "kurs", "diplom")


def _allocate(total, weights):
    """`total` sahifani og'irliklarga ko'ra butun sonlarda taqsimlaydi (har biri >= 1)."""
    count = len(weights)
    total = max(count, int(total))
    base = total // count
    extra = total % count
    return [base + (1 if index < extra else 0) for index in range(count)]


def plan(service, pages, lang="uz"):
    """Xizmat uchun bo'limlar rejasi: [(marker, title, description, pages), ...]."""
    lang = str(lang or "uz").lower()
    pages = max(1, int(pages or 1))

    if service in COMPACT_SERVICES:
        # Maqola va tezis yaxlit matn: bo'limlar sahifaga bo'linmaydi, umumiy hajm
        # sahifa soniga qarab taqsimlanadi (12 pt, 1.15 interval).
        structure = ARTICLE_STRUCTURE if service == "maqola" else THESIS_STRUCTURE
        refs_pages = 1 if service == "maqola" else 0
        body_total = max(0.6, pages - refs_pages)
        weights = [item[3] for item in structure]
        total_weight = float(sum(weights))
        result, used = [], 0.0
        for index, (marker, title_key, desc_key, weight) in enumerate(structure):
            if index == len(structure) - 1:
                share = max(0.05, round(body_total - used, 2))
            else:
                share = round(body_total * weight / total_weight, 2)
                used += share
            result.append((marker, title(title_key, lang), DESCRIPTIONS[desc_key], max(0.05, share)))
        return result

    structure = STRUCTURES[service]
    front = 1 + len(structure["front"])  # titul + old qism sahifalari
    intro_pages = int(structure.get("intro_pages", 1))
    concl_pages = float(structure.get("concl_pages", 1))
    refs_pages = int(structure.get("refs", 1))
    appendix_pages = int(structure.get("appendix", 0))
    body_total = pages - front - intro_pages - concl_pages - refs_pages - appendix_pages

    sections = list(structure["body"])
    if service == "referat" and pages <= 7:
        sections = sections[:2]
    body_pages = max(len(sections), int(round(body_total)))
    split = _allocate(body_pages, [item[3] for item in sections])

    marker, title_key, desc_key = structure["intro"]
    result = [(marker, title(title_key, lang), DESCRIPTIONS[desc_key], intro_pages)]
    for index, (marker, title_key, desc_key, _weight) in enumerate(sections):
        result.append((marker, title(title_key, lang), DESCRIPTIONS[desc_key], split[index]))
    marker, title_key, desc_key = structure["concl"]
    result.append((marker, title(title_key, lang), DESCRIPTIONS[desc_key], concl_pages))
    return result


def section_numbers(service):
    """Bo'lim belgilarini bob raqami bilan bog'laydi: {'1.1': '1', ...}."""
    structure = STRUCTURES.get(service, {})
    mapping = {}
    for marker, _title, _desc, _weight in structure.get("body", []):
        mapping[marker] = str(marker).split(".")[0]
    return mapping


def fixed_pages(service, pages):
    """Titul, reja/mundarija, annotatsiya va ilovalar uchun ajratilgan sahifalar."""
    pages = max(1, int(pages or 1))
    if service in COMPACT_SERVICES:
        return {"cover": 0, "plan": 0, "task": 0, "annot": 0, "toc": 0, "appendix": 0,
                "refs": 1 if service == "maqola" else 0}
    structure = STRUCTURES[service]
    return {
        "cover": 1,
        "plan": 1 if structure.get("plan") else 0,
        "task": 1 if "task" in structure["front"] else 0,
        "annot": 1 if "annot" in structure["front"] else 0,
        "toc": 1 if structure.get("toc") else 0,
        "appendix": int(structure.get("appendix", 0)),
        "refs": int(structure.get("refs", 1)),
    }


def chars_per_page(service):
    """Bir sahifaga sig'adigan taxminiy belgi soni (12 pt, 1.15 interval uchun ko'proq)."""
    return 2900 if service in COMPACT_SERVICES else 1650
