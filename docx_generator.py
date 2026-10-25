"""DOCX generator — 8 ta xizmat turi uchun to'liq struktura.
Har bir xizmat: Titul sahifa → Mundarija → Kirish → Boblar → Xulosa → Adabiyotlar.
6 til to'liq qo'llab-quvvatlanadi. Har sahifa pastida: 11pt "Yaratildi: @Talaba_AI_SlideBot".
Til aralashuvi (masalan, ruscha tanlanganda o'zbekcha so'z qolishi) to'liq bartaraf etildi.
JSON qoldiqlari va keraksiz belgilar to'liq tozalanadi.
"""
import io
import re
import json
from docx import Document
from docx.shared import Pt, RGBColor, Inches, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
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
        "object": "Tadqiqot obyekti:", "subject": "Tadqiqot predmeti:",
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
        "essay_title": "INSHO / ESSEY", "article_title": "ILMIY MAQOLA", "test_instructions": "TEST SAVOLLARI (TOʻGʻRI JAVOBNI TANLANG)",
        "level": "Daraja: O'rta", "question": "SAVOL", "skip_author": "Talaba",
        "faculty_label": "Fakultet:", "dept_label": "Kafedra:", "subject_label": "Fan:",
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
        "city_year": "Ташкент — 2026", "toc": "СОДЕРЖАНИЕ", "intro": "ВВЕДЕНИЕ",
        "relevance": "Актуальность темы:", "goal": "Цель работы:",
        "object": "Объект исследования:", "subject": "Предмет исследования:",
        "tasks": "Задачи исследования:", "conclusion": "ЗАКЛЮЧЕНИЕ",
        "conclusion_kurs": "ЗАКЛЮЧЕНИЕ И ПРЕДЛОЖЕНИЯ", "conclusion_diplom": "ЗАКЛЮЧЕНИЕ И РЕКОМЕНДАЦИИ",
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
        "relevance_thesis": "📌 АКТУАЛЬНОСТЬ И ЦЕЛЬ:", "test_title": "ТЕСТ / ПРОВЕРКА ЗНАНИЙ",
        "essay_title": "СОЧИНЕНИЕ / ЭССЕ", "article_title": "НАУЧНАЯ СТАТЬЯ", "test_instructions": "ВОПРОСЫ ТЕСТА (ВЫБЕРИТЕ ПРАВИЛЬНЫЙ ОТВЕТ)",
        "questions_count": "Количество вопросов:", "level": "Уровень: Средний", "question": "ВОПРОС", "skip_author": "Студент",
        "faculty_label": "Факультет:", "dept_label": "Кафедра:", "subject_label": "Предмет:",
    },
    "en": {
        "ministry": "MINISTRY OF HIGHER EDUCATION, SCIENCE AND INNOVATIONS OF THE REPUBLIC OF UZBEKISTAN",
        "inst_placeholder": "[University / Institute / College name]", "dept_placeholder": "[Department / Major name]",
        "referat": "ESSAY / REPORT", "mustaqil": "ASSIGNMENT", "kurs": "COURSEWORK", "diplom": "GRADUATION THESIS",
        "topic_label": "TOPIC:", "author_label": "Prepared by:", "supervisor_label": "Scientific advisor:",
        "dept_head_label": "Head of Department:", "reviewer_label": "Reviewer:",
        "accepted_label": "Accepted by:", "checked_label": "Checked by:", "city_year": "Tashkent — 2026",
        "toc": "CONTENTS", "intro": "INTRODUCTION", "relevance": "Relevance of the topic:", "goal": "Goal of the work:",
        "object": "Research object:", "subject": "Research subject:", "tasks": "Tasks completed:",
        "conclusion": "CONCLUSION", "conclusion_kurs": "CONCLUSION AND RECOMMENDATIONS", "conclusion_diplom": "CONCLUSION AND SUGGESTIONS",
        "references": "REFERENCES", "appendix": "APPENDICES", "chapter": "CHAPTER", "important_def": "📌 KEY DEFINITION",
        "practical_tip": "🛡 PRACTICAL TIP", "stats": "📊 STATISTICAL DATA", "quote": "📜 FAMOUS QUOTE",
        "final_wisdom": "💡 FINAL THOUGHT", "author_recommendation": "💡 AUTHOR'S RECOMMENDATION", "scientific_rec": "🎓 SCIENTIFIC RECOMMENDATION",
        "results": "📊 MAIN RESULTS", "methods": "📊 METHODS AND METHODOLOGY", "rationale": "💡 Rationale:",
        "correct_mark": "(✓ Correct answer)", "annotation": "📌 Abstract:", "keywords": "🔑 Keywords:",
        "essay_style": "STYLE: Literary-Philosophical Essay", "thesis": "SCIENTIFIC ABSTRACT",
        "author": "Author:", "affiliation": "Affiliation:", "email": "E-mail:",
        "relevance_thesis": "📌 RELEVANCE AND GOAL:", "test_title": "QUIZ / KNOWLEDGE TEST",
        "essay_title": "ESSAY", "article_title": "SCIENTIFIC ARTICLE", "test_instructions": "TEST QUESTIONS (SELECT THE CORRECT ANSWER)",
        "questions_count": "Number of questions:", "level": "Level: Intermediate", "question": "QUESTION", "skip_author": "Student",
        "faculty_label": "Faculty:", "dept_label": "Department:", "subject_label": "Subject:",
    },
    "tr": {
        "ministry": "ÖZBEKİSTAN CUMHURİYETİ YÜKSEKÖĞRETİM, BİLİM VE İNOVASYON BAKANLIĞI",
        "inst_placeholder": "[Üniversite / Enstitü / Kolej adı]", "dept_placeholder": "[Bölüm / Anabilim dalı adı]",
        "referat": "RAPOR", "mustaqil": "ÖDEV", "kurs": "DÖNEM ÖDEVİ", "diplom": "MEZUNİYET TEZİ",
        "topic_label": "KONU:", "author_label": "Hazırlayan:", "supervisor_label": "Danışman:",
        "dept_head_label": "Bölüm başkanı:", "reviewer_label": "Hakem:", "accepted_label": "Kabul eden:", "checked_label": "Kontrol eden:",
        "city_year": "Taşkent — 2026", "toc": "İÇİNDEKİLER", "intro": "GİRİŞ",
        "relevance": "Konu güncelliği:", "goal": "Çalışmanın amacı:", "object": "Araştırma nesnesi:", "subject": "Araştırma konusu:",
        "tasks": "Yapılan görevler:", "conclusion": "SONUÇ", "conclusion_kurs": "SONUÇ VE ÖNERİLER",
        "conclusion_diplom": "SONUÇ VE TAVSİYELER", "references": "KAYNAKÇA", "appendix": "EKLER",
        "chapter": "BÖLÜM", "important_def": "📌 ÖNEMLİ TANIM", "practical_tip": "🛡 PRATİK ÖNERİ", "stats": "📊 İSTATİSTİKSEL VERİ",
        "quote": "📜 MEŞHUR ALINTI", "final_wisdom": "💡 SON DÜŞÜNCE", "author_recommendation": "💡 YAZAR ÖNERİSİ",
        "scientific_rec": "🎓 BİLİMSEL ÖNERİ", "results": "📊 TEMEL BULGULAR", "methods": "📊 YÖNTEM VE METODOLOJİ",
        "rationale": "💡 Açıklama:", "correct_mark": "(✓ Doğru cevap)", "annotation": "📌 Özet:", "keywords": "🔑 Anahtar kelimeler:",
        "essay_style": "TARZ: Edebi-Felsefi Deneme", "thesis": "BİLİMSEL TEZ ÖZETİ", "author": "Yazar:", "affiliation": "Kurum:", "email": "E-posta:",
        "relevance_thesis": "📌 GÜNCELLİK VE AMAÇ:", "test_title": "TEST / BİLGİ SINAVI",
        "essay_title": "KOMPOZİSYON / DENEME", "article_title": "BİLİMSEL MAKALE", "test_instructions": "TEST SORULARI (DOĞRU CEVABI SEÇİN)",
        "questions_count": "Soru sayısı:", "level": "Seviye: Orta", "question": "SORU", "skip_author": "Öğrenci",
        "faculty_label": "Fakülte:", "dept_label": "Bölüm:", "subject_label": "Ders:",
    },
    "de": {
        "ministry": "MINISTERIUM FÜR HOCHSCHULWESEN, WISSENSCHAFT UND INNOVATION DER REPUBLIK USBEKISTAN",
        "inst_placeholder": "[Name der Universität / Instituts / Kollegs]", "dept_placeholder": "[Name des Lehrstuhls / Studiengangs]",
        "referat": "REFERAT", "mustaqil": "HAUSARBEIT", "kurs": "SEMINARARBEIT", "diplom": "ABSCHLUSSARBEIT",
        "topic_label": "THEMA:", "author_label": "Verfasser:", "supervisor_label": "Wissenschaftlicher Betreuer:",
        "dept_head_label": "Lehrstuhlleiter:", "reviewer_label": "Gutachter:", "accepted_label": "Angenommen von:", "checked_label": "Geprüft von:",
        "city_year": "Taschkent — 2026", "toc": "INHALTSVERZEICHNIS", "intro": "EINLEITUNG",
        "relevance": "Aktualität des Themas:", "goal": "Ziel der Arbeit:", "object": "Untersuchungsgegenstand:", "subject": "Untersuchungssubjekt:",
        "tasks": "Aufgaben:", "conclusion": "FAZIT", "conclusion_kurs": "FAZIT UND EMPFEHLUNGEN", "conclusion_diplom": "FAZIT UND VORSCHLÄGE",
        "references": "LITERATURVERZEICHNIS", "appendix": "ANHÄNGE", "chapter": "KAPITEL", "important_def": "📌 WICHTIGE DEFINITION",
        "practical_tip": "🛡 PRAKTISCHER TIPP", "stats": "📊 STATISTISCHE DATEN", "quote": "📜 BERÜHMTES ZITAT",
        "final_wisdom": "💡 ABSCHLIESSENDE GEDANKE", "author_recommendation": "💡 EMPFEHLUNG DES AUTORES", "scientific_rec": "🎓 WISSENSCHAFTLICHE EMPFEHLUNG",
        "results": "📊 HAUPTERGEBNISSE", "methods": "📊 METHODEN UND METHODIK", "rationale": "💡 Begründung:", "correct_mark": "(✓ Richtige Antwort)",
        "annotation": "📌 Zusammenfassung:", "keywords": "🔑 Schlüsselwörter:", "essay_style": "STIL: Literarisch-philosophischer Essay",
        "thesis": "WISSENSCHAFTLICHE THESE", "author": "Autor:", "affiliation": "Einrichtung:", "email": "E-Mail:",
        "relevance_thesis": "📌 AKTUALITÄT UND ZIEL:", "test_title": "TEST / WISSENSABFRAGE",
        "essay_title": "AUFSATZ / ESSAY", "article_title": "WISSENSCHAFTLICHER ARTIKEL", "test_instructions": "TESTFRAGEN (WÄHLEN SIE DIE RICHTIGE ANTWORT)",
        "questions_count": "Anzahl der Fragen:", "level": "Niveau: Mittel", "question": "FRAGE", "skip_author": "Student",
        "faculty_label": "Fakultät:", "dept_label": "Fachbereich:", "subject_label": "Fach:",
    },
    "fr": {
        "ministry": "MINISTÈRE DE L'ENSEIGNEMENT SUPÉRIEUR, DES SCIENCES ET DE L'INNOVATION DE LA RÉPUBLIQUE D'OUBZÉKISTAN",
        "inst_placeholder": "[Nom de l'université / institut / collège]", "dept_placeholder": "[Nom du département / filière]",
        "referat": "EXPOSÉ", "mustaqil": "DEVOIR", "kurs": "MÉMOIRE", "diplom": "MÉMOIRE DE FIN D'ÉTUDES",
        "topic_label": "SUJET :", "author_label": "Réalisé par :", "supervisor_label": "Directeur de recherche :",
        "dept_head_label": "Chef de département :", "reviewer_label": "Rapporteur :", "accepted_label": "Accepté par :", "checked_label": "Vérifié par :",
        "city_year": "Tachkent — 2026", "toc": "SOMMAIRE", "intro": "INTRODUCTION",
        "relevance": "Pertinence du sujet :", "goal": "Objectif du travail :", "object": "Objet de recherche :", "subject": "Sujet de recherche :",
        "tasks": "Tâches effectuées :", "conclusion": "CONCLUSION", "conclusion_kurs": "CONCLUSION ET RECOMMANDATIONS",
        "conclusion_diplom": "CONCLUSION ET SUGGESTIONS", "references": "BIBLIOGRAPHIE", "appendix": "ANNEXES",
        "chapter": "CHAPITRE", "important_def": "📌 DÉFINITION CLÉ", "practical_tip": "🛡 CONSEIL PRATIQUE",
        "stats": "📊 DONNÉES STATISTIQUES", "quote": "📜 CITATION CÉLÈBRE", "final_wisdom": "💡 PENSÉE FINALE",
        "author_recommendation": "💡 RECOMMANDATION DE L'AUTEUR", "scientific_rec": "🎓 RECOMMANDATION SCIENTIFIQUE",
        "results": "📊 RÉSULTATS PRINCIPAUX", "methods": "📊 MÉTHODES ET MÉTHODOLOGIE", "rationale": "💡 Explication :",
        "correct_mark": "(✓ Bonne réponse)", "annotation": "📌 Résumé :", "keywords": "🔑 Mots-clés :",
        "essay_style": "STYLE : Essai littéraire et philosophique", "thesis": "THÈSE SCIENTIFIQUE",
        "author": "Auteur :", "affiliation": "Affiliation :", "email": "E-mail :", "relevance_thesis": "📌 PERTINENCE ET OBJECTIF :",
        "test_title": "QUIZ / TEST DE CONNAISSANCES", "questions_count": "Nombre de questions :", "level": "Niveau : Intermédiaire",
        "essay_title": "DISSERTATION / ESSAI", "article_title": "ARTICLE SCIENTIFIQUE", "test_instructions": "QUESTIONS DU TEST (CHOISISSEZ LA BONNE RÉPONSE)",
        "question": "QUESTION", "skip_author": "Étudiant",
        "faculty_label": "Faculté :", "dept_label": "Département :", "subject_label": "Matière :",
    },
}

def _lbl(lang):
    d = dict(L.get(str(lang).lower(), L["uz"]))
    d["_lang"] = str(lang).lower()
    return d

# ===== Lokalizatsiya qilingan bob/fraza lug'ati (6 til) =====
_PH = {
    "theor_found":    {"uz":"Nazariy asoslar","ru":"Теоретические основы","en":"Theoretical foundations","tr":"Teorik temeller","de":"Theoretische Grundlagen","fr":"Fondements théoriques"},
    "analys_pract":   {"uz":"Tahlil va amaliy qism","ru":"Анализ и практическая часть","en":"Analysis and practical part","tr":"Analiz ve pratik kısım","de":"Analyse und praktischer Teil","fr":"Analyse et partie pratique"},
    "key_concepts":   {"uz":"Asosiy tushunchalar","ru":"Основные понятия","en":"Key concepts","tr":"Temel kavramlar","de":"Grundbegriffe","fr":"Concepts clés"},
    "practical":      {"uz":"Amaliy qism","ru":"Практическая часть","en":"Practical part","tr":"Pratik kısım","de":"Praktischer Teil","fr":"Partie pratique"},
    "theor_part":     {"uz":"Nazariy qism","ru":"Теоретическая часть","en":"Theoretical part","tr":"Teorik kısım","de":"Theoretischer Teil","fr":"Partie théorique"},
    "analys_part":    {"uz":"Tahlil qismi","ru":"Аналитическая часть","en":"Analytical part","tr":"Analitik kısım","de":"Analytischer Teil","fr":"Partie analytique"},
    "recommend":      {"uz":"Takliflar","ru":"Рекомендации","en":"Recommendations","tr":"Öneriler","de":"Empfehlungen","fr":"Recommandations"},
    "theor_method":   {"uz":"Nazariy-metodologik asoslar","ru":"Теоретико-методологические основы","en":"Theoretical and methodological foundations","tr":"Teorik ve metodolojik temeller","de":"Theoretisch-methodologische Grundlagen","fr":"Fondements théoriques et méthodologiques"},
    "analys_assess":  {"uz":"Tahlil va baholash","ru":"Анализ и оценка","en":"Analysis and assessment","tr":"Analiz ve değerlendirme","de":"Analyse und Bewertung","fr":"Analyse et évaluation"},
    "rec_eff":        {"uz":"Takliflar va samaradorlik","ru":"Рекомендации и эффективность","en":"Recommendations and efficiency","tr":"Öneriler ve verimlilik","de":"Empfehlungen und Effizienz","fr":"Recommandations et efficacité"},
    "concept_orig":   {"uz":"Tushuncha va kelib chiqish sabablari","ru":"Понятие и причины возникновения","en":"Concept and origins","tr":"Kavram ve ortaya çıkış nedenleri","de":"Begriff und Entstehungsgründe","fr":"Concept et origines"},
    "intl_exp":       {"uz":"Xalqaro tajriba","ru":"Международный опыт","en":"International experience","tr":"Uluslararası deneyim","de":"Internationale Erfahrung","fr":"Expérience internationale"},
    "state_analys":   {"uz":"Holat tahlili","ru":"Анализ состояния","en":"State analysis","tr":"Durum analizi","de":"Zustandsanalyse","fr":"Analyse de l'état"},
    "problem_assess": {"uz":"Muammolarni baholash","ru":"Оценка проблем","en":"Problem assessment","tr":"Sorun değerlendirmesi","de":"Problembewertung","fr":"Évaluation des problèmes"},
    "impl_new":       {"uz":"Yangi usullarni joriy etish","ru":"Внедрение новых методов","en":"Implementation of new methods","tr":"Yeni yöntemlerin uygulanması","de":"Einführung neuer Methoden","fr":"Mise en œuvre de nouvelles méthodes"},
    "rec_improve":    {"uz":"Takomillashtirish bo'yicha takliflar","ru":"Рекомендации по совершенствованию","en":"Recommendations for improvement","tr":"İyileştirme önerileri","de":"Verbesserungsempfehlungen","fr":"Recommandations d'amélioration"},
    "concept_class":  {"uz":"Tushuncha va tasniflash","ru":"Понятие и классификация","en":"Concept and classification","tr":"Kavram ve sınıflandırma","de":"Begriff und Klassifizierung","fr":"Concept et classification"},
    "modern_role":    {"uz":"Zamonaviy usullar roli","ru":"Роль современных методов","en":"Role of modern methods","tr":"Modern yöntemlerin rolü","de":"Rolle moderner Methoden","fr":"Rôle des méthodes modernes"},
    "dyn_indic":      {"uz":"Ko'rsatkichlar dinamikasi","ru":"Динамика показателей","en":"Dynamics of indicators","tr":"Göstergelerin dinamikleri","de":"Dynamik der Indikatoren","fr":"Dynamique des indicateurs"},
    "sys_eff":        {"uz":"Mavjud tizim samaradorligi","ru":"Эффективность существующей системы","en":"Efficiency of the current system","tr":"Mevcut sistemin etkinliği","de":"Effizienz des bestehenden Systems","fr":"Efficacité du système actuel"},
    "impl_model":     {"uz":"Yangi modelni joriy etish","ru":"Внедрение новой модели","en":"Implementation of a new model","tr":"Yeni modelin uygulanması","de":"Einführung eines neuen Modells","fr":"Mise en œuvre d'un nouveau modèle"},
    "econ_calc":      {"uz":"Iqtisodiy samaradorlik hisobi","ru":"Расчёт экономической эффективности","en":"Economic efficiency calculation","tr":"Ekonomik verimlilik hesabı","de":"Berechnung der wirtschaftlichen Effizienz","fr":"Calcul de l'efficacité économique"},
}
def _ph(key, lang):
    lang = str(lang).lower()
    return _PH.get(key, {}).get(lang, _PH.get(key, {}).get("en", key))

def _chapters_for(service_code, lang):
    if service_code == "referat":
        return [(_ph("theor_found", lang), None), (_ph("analys_pract", lang), None)]
    if service_code == "mustaqil":
        return [(_ph("key_concepts", lang), None), (_ph("practical", lang), None)]
    if service_code == "kurs":
        return [
            (_ph("theor_part", lang), [("1", _ph("concept_orig", lang)), ("2", _ph("intl_exp", lang))]),
            (_ph("analys_part", lang), [("1", _ph("state_analys", lang)), ("2", _ph("problem_assess", lang))]),
            (_ph("recommend", lang), [("1", _ph("impl_new", lang)), ("2", _ph("rec_improve", lang))]),
        ]
    # diplom
    return [
        (_ph("theor_method", lang), [("1", _ph("concept_class", lang)), ("2", _ph("modern_role", lang))]),
        (_ph("analys_assess", lang), [("1", _ph("dyn_indic", lang)), ("2", _ph("sys_eff", lang))]),
        (_ph("rec_eff", lang), [("1", _ph("impl_model", lang)), ("2", _ph("econ_calc", lang))]),
    ]

# ===== To'liq Lokalizatsiya =====
_LOC = {
    "relevance": {"uz":"Bugungi kunda {t} mavzusi alohida dolzarblikka ega. Bu soha zamonaviy talablarga muvofiq tez rivojlanmoqda va jamiyatda muhim o'rin tutadi. Ushbu tadqiqotning asosiy sababi — mavzudagi bo'shliqlarni aniqlash va ularni bartaraf etish yo'llarini ishlab chiqish.",
                 "ru":"В настоящее время тема «{t}» имеет особую актуальность. Данная сфера быстро развивается в соответствии с современными требованиями и занимает важное место в обществе. Основная причина данного исследования — выявить пробелы по теме и разработать пути их устранения.",
                 "en":"Today, the topic of {t} is of particular relevance. This field is developing rapidly in line with modern requirements and occupies an important place in society. The main reason for this research is to identify gaps in the topic and develop ways to address them.",
                 "tr":"Bugün {t} konusu özel bir güncelliğe sahiptir. Bu alan modern gereksinimler doğrultusunda hızla gelişmekte ve toplumda önemli bir yer tutmaktadır. Bu araştırmanın temel nedeni — konudaki boşlukları tespit etmek ve bunları çözme yollarını geliştirmektir.",
                 "de":"Heute hat das Thema {t} besondere Relevanz. Dieses Gebiet entwickelt sich schnell im Einklang mit modernen Anforderungen und nimmt einen wichtigen Platz in der Gesellschaft ein. Der Hauptgrund dieser Forschung ist es, Lücken zum Thema zu identifizieren und Wege zu ihrer Beseitigung zu entwickeln.",
                 "fr":"Aujourd'hui, le sujet « {t} » présente une pertinence particulière. Ce domaine se développe rapidement conformément aux exigences modernes et occupe une place importante dans la société. La raison principale de cette recherche est d'identifier les lacunes du sujet et de développer des moyens d'y remédier."},
    "goal": {"uz":"{t} ning joriy holatini tahlil qilish, muammolarni aniqlash va ularni hal qilish bo'yicha amaliy takliflar ishlab chiqish.",
             "ru":"Проанализировать современное состояние {t}, выявить проблемы и разработать практические рекомендации по их решению.",
             "en":"To analyze the current state of {t}, identify problems, and develop practical recommendations for solving them.",
             "tr":"{t} konusunun güncel durumunu analiz etmek, sorunları tespit etmek ve bunları çözmek için pratik öneriler geliştirmek.",
             "de":"Den aktuellen Stand von {t} analysieren, Probleme identifizieren und praktische Empfehlungen zu ihrer Lösung entwickeln.",
             "fr":"Analyser l'état actuel de {t}, identifier les problèmes et élaborer des recommandations pratiques pour les résoudre."},
    "object": {"uz":"{t} sohasidagi iqtisodiy-ijtimoiy jarayonlar va ularni boshqarish tizimi.",
               "ru":"Социально-экономические процессы в сфере {t} и система управления ими.",
               "en":"Socio-economic processes in the field of {t} and the system of managing them.",
               "tr":"{t} alanındaki sosyo-ekonomik süreçler ve bunları yönetme sistemi.",
               "de":"Sozioökonomische Prozesse im Bereich {t} und das System ihrer Verwaltung.",
               "fr":"Les processus socio-économiques dans le domaine de {t} et le système de gestion."},
    "subject": {"uz":"{t} ni optimallashtirish va samaradorligini oshirish jarayonidagi munosabatlar.",
                "ru":"Отношения в процессе оптимизации и повышения эффективности {t}.",
                "en":"Relations in the process of optimizing and improving the efficiency of {t}.",
                "tr":"{t} optimizasyonu ve verimliliğini artırma sürecindeki ilişkiler.",
                "de":"Beziehungen im Prozess der Optimierung und Effizienzsteigerung von {t}.",
                "fr":"Relations dans le processus d'optimisation et d'amélioration de l'efficacité de {t}."},
    "method": {"uz":"Tadqiqot davomida tahlil-sintez, qiyosiy-statistik, matematik modellashtirish va ekspert baholash usullaridan foydalanildi.",
               "ru":"В ходе исследования использовались методы анализа и синтеза, сравнительно-статистические, математического моделирования и экспертной оценки.",
               "en":"The study used methods of analysis and synthesis, comparative-statistical methods, mathematical modeling and expert assessment.",
               "tr":"Araştırmada analiz ve sentez, karşılaştırmalı-istatistiksel, matematiksel modelleme ve uzman değerlendirme yöntemleri kullanıldı.",
               "de":"In der Studie wurden Methoden der Analyse und Synthese, vergleichend-statistische Methoden, mathematische Modellierung und Expertenbewertung verwendet.",
               "fr":"L'étude a utilisé des méthodes d'analyse et de synthèse, des méthodes comparatives-statistiques, la modélisation mathématique et l'évaluation d'experts."},
    "concl1": {"uz":"1. {t} bo'yicha tahlil natijasida joriy holat va rivojlanish istiqbollari aniqlandi.",
               "ru":"1. В результате анализа по теме «{t}» выявлено современное состояние и перспективы развития.",
               "en":"1. The analysis on «{t}» revealed the current state and development prospects.",
               "tr":"1. {t} konusundaki analiz sonucunda mevcut durum ve gelişme beklentileri tespit edildi.",
               "de":"1. Die Analyse zu «{t}» ergab den aktuellen Stand und die Entwicklungsperspektiven.",
               "fr":"1. L'analyse sur « {t} » a révélé l'état actuel et les perspectives d'évolution."},
    "concl2": {"uz":"2. Mavjud muammolar va ularning sabablari tizimlashtirildi, ulardan xalos bo'lishning ustuvor yo'llari belgilandi.",
               "ru":"2. Систематизированы существующие проблемы и их причины, определены приоритетные пути их решения.",
               "en":"2. Existing problems and their causes were systematized; priority solutions identified.",
               "tr":"2. Mevcut sorunlar ve nedenleri sistematik hale getirildi; öncelikli çözüm yolları belirlendi.",
               "de":"2. Bestehende Probleme und ihre Ursachen wurden systematisiert; prioritäre Lösungen identifiziert.",
               "fr":"2. Les problèmes existants et leurs causes ont été systématisés ; les solutions prioritaires identifiées."},
    "concl3": {"uz":"3. Taklif etilayotgan chora-tadbirlar amalga oshirilishi bilan samaradorlik sezilarli darajada oshirilishi mumkin.",
               "ru":"3. Реализация предложенных мероприятий позволит значительно повысить эффективность.",
               "en":"3. Implementation of proposed measures can significantly improve efficiency.",
               "tr":"3. Önerilen önlemlerin uygulanması verimliliği önemli ölçüde artırabilir.",
               "de":"3. Die Umsetzung der vorgeschlagenen Maßnahmen kann die Effizienz erheblich steigern.",
               "fr":"3. La mise en œuvre des mesures proposées peut améliorer considérablement l'efficacité."},
    "concl4": {"uz":"4. Kelajakda ushbu sohani chuqurroq o'rganish va ilmiy tadqiqotlarni kengaytirish zarur.",
               "ru":"4. В дальнейшем необходимо углублённое изучение данной сферы и расширение научных исследований.",
               "en":"4. Further in-depth study and expanded research in this field is necessary.",
               "tr":"4. Gelecekte bu alanın daha derinlemesine incelenmesi ve bilimsel araştırmaların genişletilmesi gerekmektedir.",
               "de":"4. Weitere vertiefte Studien und erweiterte Forschung auf diesem Gebiet sind erforderlich.",
               "fr":"4. Une étude plus approfondie et une recherche élargie dans ce domaine sont nécessaires."},
    "ref1": {"uz":"1. {t} bo'yicha qonun va nizomiy hujjatlar.",
             "ru":"1. Законодательные и нормативные акты по теме «{t}».",
             "en":"1. Legislative and regulatory acts on «{t}».",
             "tr":"1. {t} konulu yasal ve düzenleyici belgeler.",
             "de":"1. Gesetzliche und regulatorische Akte zu «{t}».",
             "fr":"1. Actes législatifs et réglementaires sur « {t} »."},
    "ref2": {"uz":"2. {t} bo'yicha monografiya va o'quv qo'llanmalar. 2024.",
             "ru":"2. Монографии и учебные пособия по теме «{t}». 2024.",
             "en":"2. Monographs and textbooks on «{t}». 2024.",
             "tr":"2. {t} konulu monografiler ve ders kitapları. 2024.",
             "de":"2. Monographien und Lehrbücher zu «{t}». 2024.",
             "fr":"2. Monographies et manuels sur « {t} ». 2024."},
    "ref3": {"uz":"3. {t} mavzusida jurnalda chop etilgan ilmiy maqolalar, 2023-2025.",
             "ru":"3. Научные статьи по теме «{t}», опубликованные в журналах, 2023-2025.",
             "en":"3. Scientific articles on «{t}» published in journals, 2023-2025.",
             "tr":"3. {t} konusunda dergilerde yayınlanan bilimsel makaleler, 2023-2025.",
             "de":"3. Wissenschaftliche Artikel zu «{t}», veröffentlicht in Zeitschriften, 2023-2025.",
             "fr":"3. Articles scientifiques sur « {t} » publiés dans des revues, 2023-2025."},
    "ref4": {"uz":"4. Rasmiy statistik ma'lumotlar portali.",
             "ru":"4. Официальный портал статистических данных.",
             "en":"4. Official statistical data portal.",
             "tr":"4. Resmi istatistik veri portalı.",
             "de":"4. Offizielles Portal für statistische Daten.",
             "fr":"4. Portail officiel de données statistiques."},
    "ref5": {"uz":"5. Xalqaro tajriba — ilg'or mamlakatlar amaliyoti.",
             "ru":"5. Международный опыт — практика передовых стран.",
             "en":"5. International experience — practice of leading countries.",
             "tr":"5. Uluslararası deneyim — gelişmiş ülkelerin pratiği.",
             "de":"5. Internationale Erfahrung — Praxis führender Länder.",
             "fr":"5. Expérience internationale — pratique des pays de pointe."},
    "chapter_fb": {"uz":"{title} bo'yicha batafsil tahlil, statistik ma'lumotlar va amaliy kuzatishlar keltirilgan. Ushbu bobda nazariy asoslar, tasniflash tamoyillari va xalqaro tajriba o'rganiladi.",
                   "ru":"Представлен подробный анализ «{title}», статистические данные и практические наблюдения. В данной главе рассматриваются теоретические основы, принципы классификации и международный опыт.",
                   "en":"A detailed analysis of {title}, statistical data and practical observations are presented. This chapter examines the theoretical foundations, classification principles and international experience.",
                   "tr":"{title} hakkında ayrıntılı analiz, istatistiksel veriler ve pratik gözlemler sunulmuştur. Bu bölümde teorik temeller, sınıflandırma ilkeleri ve uluslararası deneyim incelenmektedir.",
                   "de":"Eine detaillierte Analyse von {title}, statistische Daten und praktische Beobachtungen werden vorgestellt. Dieses Kapitel untersucht die theoretischen Grundlagen, Klassifizierungsprinzipien und internationale Erfahrungen.",
                   "fr":"Une analyse détaillée de {title}, des données statistiques et des observations pratiques sont présentées. Ce chapitre examine les fondements théoriques, les principes de classification et l'expérience internationale."},
    "essay_intro": {"uz":"«{t}» tobora muhim ahamiyat kasb etmoqda. Bugungi kunda bu mavzu nafaqat ilmiy, balki axloqiy jihatdan ham muhim. U insonning ichki dunyosi va atrof-muhit bilan munosabatini chuqur ta'sirlaydi.",
                   "ru":"«{t}» приобретает всё большее значение. Сегодня эта тема важна не только научно, но и этически. Она глубоко влияет на внутренний мир человека и отношения с окружающей средой.",
                   "en":"«{t}» is acquiring ever greater significance. Today this subject is important not only scientifically but also ethically. It deeply affects a person's inner world and the relationship with the environment.",
                   "tr":"«{t}» giderek daha fazla önem kazanıyor. Bugün bu konu sadece bilimsel değil, aynı zamanda etik olarak da önemli. İnsanın iç dünyasını ve çevreyle ilişkisini derinden etkiliyor.",
                   "de":"«{t}» gewinnt immer mehr an Bedeutung. Heute ist dieses Thema nicht nur wissenschaftlich, sondern auch ethisch wichtig. Es beeinflusst tief die innere Welt eines Menschen und die Beziehung zur Umwelt.",
                   "fr":"« {t} » prend une importance croissante. Aujourd'hui, ce sujet est important non seulement scientifiquement mais aussi éthiquement. Il affecte profondément le monde intérieur d'une personne et sa relation avec l'environnement."},
    "essay_goal": {"uz":"{t} haqidagi o'z qarashlarimni asoslash va oqibatlarini tahlil qilish.",
                   "ru":"Обосновать свою точку зрения по теме «{t}» и проанализировать последствия.",
                   "en":"To substantiate my point of view on {t} and analyze the consequences.",
                   "tr":"{t} konusundaki kendi görüşümü gerekçelendirmek ve sonuçlarını analiz etmek.",
                   "de":"Meinen Standpunkt zu {t} begründen und die Folgen analysieren.",
                   "fr":"Étayer mon point de vue sur {t} et analyser les conséquences."},
    "practical_tip": {"uz":"Har doim 2 bosqichli autentifikatsiyadan foydalaning va parollarni muntazam yangilab boring!",
                      "ru":"Всегда используйте двухфакторную аутентификацию и регулярно меняйте пароли!",
                      "en":"Always use two-factor authentication and update passwords regularly!",
                      "tr":"Her zaman iki faktörlü kimlik doğrulama kullanın ve şifreleri düzenli olarak güncelleyin!",
                      "de":"Verwenden Sie immer die Zwei-Faktor-Authentifizierung und aktualisieren Sie Passwörter regelmäßig!",
                      "fr":"Utilisez toujours l'authentification à deux facteurs et mettez régulièrement à jour les mots de passe !"},
    "def_box": {"uz":"«{t}» — bu sohaning asosiy kategoriyasi bo'lib, uning mohiyatini to'liq anglab yetish zarur. Ushbu ta'rif nazariy asoslarni chuqur o'rganishning kalitidir.",
                "ru":"«{t}» — это фундаментальная категория данной сферы, суть которой должна быть полностью осмыслена. Это определение является ключом к углубленному изучению теоретических основ.",
                "en":"«{t}» is a fundamental category of this field whose essence must be fully understood. This definition is the key to an in-depth study of the theoretical foundations.",
                "tr":"«{t}» bu alanın özü tam olarak anlaşılması gereken temel bir kategorisidir. Bu tanım, teorik temellerin derinlemesine incelenmesinin anahtarıdır.",
                "de":"«{t}» ist eine grundlegende Kategorie dieses Bereichs, deren Wesen vollständig verstanden werden muss. Diese Definition ist der Schlüssel zu einem eingehenden Studium der theoretischen Grundlagen.",
                "fr":"« {t} » est une catégorie fondamentale de ce domaine dont l'essence doit être pleinement comprise. Cette définition est la clé d'une étude approfondie des fondements théoriques."},
    "stats_box": {"uz":"Xalqaro agentliklarning ma'lumotlariga ko'ra, 2030 yilga kelib ushbu ko'rsatkich 50% dan oshishi prognoz qilinmoqda, bu esa ham yangi imkoniyatlar, ham muammolarni keltirib chiqaradi.",
                  "ru":"По данным международных агентств, к 2030 году этот показатель превысит 50%, что принесет как новые возможности, так и проблемы.",
                  "en":"According to international agencies, this indicator is projected to exceed 50% by 2030, which will bring both new opportunities and challenges.",
                  "tr":"Uluslararası kuruluşlara göre, bu göstergenin 2030 yılına kadar %50'yi aşması bekleniyor, bu da hem yeni fırsatlar hem de zorluklar getirecek.",
                  "de":"Laut internationalen Agenturen wird prognostiziert, dass dieser Indikator bis 2030 50 % überschreiten wird, was sowohl neue Chancen als auch Herausforderungen mit sich bringt.",
                  "fr":"Selon les agences internationales, cet indicateur devrait dépasser 50 % d'ici 2030, ce qui apportera à la fois de nouvelles opportunités et de nouveaux défis."},
    "quote_text": {"uz":'"Kitob — vaqt ummonida suzib yurgan va o\'zining qimmatbaho yukini avloddan-avlodga aytib berayotgan kemadir."\n— Frensis Bekon',
                   "ru":'"Книга — это корабль, плывущий по океану времени и несущий свой драгоценный груз от поколения к поколению."\n— Фрэнсис Бэкон',
                   "en":'"Books are ships that pass through the vast sea of time, carrying their precious cargo from generation to generation."\n— Francis Bacon',
                   "tr":'"Kitaplar, zamanın engin denizinde süzülen ve değerli yüklerini nesilden nesile taşıyan gemilerdir."\n— Francis Bacon',
                   "de":'"Bücher sind Schiffe, die über das weite Meer der Zeit fahren und ihre kostbare Fracht von Generation zu Generation tragen."\n— Francis Bacon',
                   "fr":'"Les livres sont des navires qui traversent le vaste océan du temps, portant leur précieuse cargaison de génération en génération."\n— Francis Bacon'},
    "final_wisdom": {"uz":"Dunyoni o'zgartirmoqchi bo'lsangiz, avvalo o'zingizdan boshlang va bilim olishni hech vaqt to'xtatmang!",
                     "ru":"Если вы хотите изменить мир, начните с себя и никогда не прекращайте учиться!",
                     "en":"If you want to change the world, start with yourself and never stop learning!",
                     "tr":"Dünyayı değiştirmek istiyorsanız, önce kendinizden başlayın ve öğrenmeyi asla bırakmayın!",
                     "de":"Wenn Sie die Welt verändern wollen, fangen Sie bei sich selbst an und hören Sie nie auf zu lernen!",
                     "fr":"Si vous voulez changer le monde, commencez par vous-même et n'arrêtez jamais d'apprendre !"},
    "author_rec": {"uz":"Ushbu soha bo'yicha jamoatchilik va tadbirkorlik sub'ektlari o'rtasida o'rganishni yanada rag'batlantirish zarur. Davlat dasturlari orqali qo'llab-quvvatlashni kengaytirish lozim.",
                   "ru":"Необходимо дополнительно стимулировать изучение этой сферы среди общественности и субъектов предпринимательства. Следует расширять поддержку через государственные программы.",
                   "en":"It is necessary to further encourage the study of this field among the public and business entities. Support through government programs should be expanded.",
                   "tr":"Bu alanın kamusal ve ticari kuruluşlar arasında incelenmesini daha fazla teşvik etmek gerekmektedir. Devlet programları aracılığıyla destek genişletilmelidir.",
                   "de":"Es ist notwendig, das Studium dieses Bereichs in der Öffentlichkeit und bei Unternehmen weiter zu fördern. Die Unterstützung durch staatliche Programme sollte ausgeweitet werden.",
                   "fr":"Il est nécessaire d'encourager davantage l'étude de ce domaine auprès du public et des entreprises. Le soutien par le biais de programmes gouvernementaux devrait être élargi."},
    "article_abstract": {"uz":"Ushbu maqolada {t} ning bugungi kundagi holati, rivojlanish istiqbollari va amaliy tavsiyalar tahlil qilinadi. Ustuvor yo'nalishlar belgilab olindi.",
                         "ru":"В данной статье анализируется текущее состояние {t}, перспективы развития и практические рекомендации. Определены приоритетные направления.",
                         "en":"This article analyzes the current state of {t}, development prospects and practical recommendations. Priority directions have been identified.",
                         "tr":"Bu makale, {t} konusunun mevcut durumunu, gelişme beklentilerini ve pratik önerileri analiz etmektedir. Öncelikli yönler belirlenmiştir.",
                         "de":"In diesem Artikel werden der aktuelle Stand von {t}, Entwicklungsperspektiven und praktische Empfehlungen analysiert. Prioritäre Richtungen wurden identifiziert.",
                         "fr":"Cet article analyse l'état actuel de {t}, les perspectives de développement et les recommandations pratiques. Les directions prioritaires ont été identifiées."},
    "article_intro": {"uz":"Bugungi kunda {t} global miqyosdagi eng muhim masalalardan biriga aylandi. Shu sababli ushbu sohani chuqur o'rganish zamon talabidir.",
                      "ru":"Сегодня {t} стало одним из глобально важных вопросов. Поэтому углубленное изучение этой сферы является требованием времени.",
                      "en":"Today, {t} has become one of the globally important issues. Therefore, an in-depth study of this field is the demand of the time.",
                      "tr":"Bugün {t}, küresel olarak önemli konulardan biri haline gelmiştir. Bu nedenle, bu alanın derinlemesine incelenmesi zamanın gereğidir.",
                      "de":"Heute ist {t} zu einem der global wichtigen Themen geworden. Daher ist eine eingehende Untersuchung dieses Bereichs eine Forderung der Zeit.",
                      "fr":"Aujourd'hui, {t} est devenu l'un des problèmes mondiaux importants. Par conséquent, une étude approfondie de ce domaine est l'exigence du temps."},
    "thesis_intro": {"uz":"Bugungi kunda {t} sohasini takomillashtirish zamon talabiga aylandi. Tadqiqotning maqsadi ushbu sohada samaradorlikni oshirishning yangi usullarini ishlab chiqishdir.",
                     "ru":"Сегодня совершенствование сферы {t} стало требованием времени. Цель исследования — разработать новые методы повышения эффективности в этой сфере.",
                     "en":"Today, improving the field of {t} has become a demand of the time. The goal of the research is to develop new methods for increasing efficiency in this field.",
                     "tr":"Bugün {t} alanını geliştirmek zamanın bir gereği haline gelmiştir. Araştırmanın amacı, bu alanda verimliliği artırmak için yeni yöntemler geliştirmektir.",
                     "de":"Heute ist die Verbesserung des Bereichs {t} zu einer Forderung der Zeit geworden. Das Ziel der Forschung ist es, neue Methoden zur Effizienzsteigerung in diesem Bereich zu entwickeln.",
                     "fr":"Aujourd'hui, l'amélioration du domaine de {t} est devenue une exigence du temps. L'objectif de la recherche est de développer de nouvelles méthodes pour augmenter l'efficacité dans ce domaine."},
    "essay_main_fb": {"uz":"{t} bo'yicha chuqur tahlil va mulohazalar. Insoniyat tarixi shuni ko'rsatadiki, har qanday buyuk g'oya insonning intilishi va mehnati samarasidir.",
                      "ru":"Глубокий анализ и размышления на тему «{t}». История человечества показывает, что любая великая идея — это результат стремления и труда человека.",
                      "en":"A deep analysis and reflections on {t}. Human history shows that every great idea is the result of human aspiration and labor.",
                      "tr":"{t} üzerine derin bir analiz ve düşünceler. İnsanlık tarihi gösteriyor ki, her büyük fikir insanın çabasının ve emeğinin sonucudur.",
                      "de":"Eine tiefgehende Analyse und Reflexionen zu {t}. Die Geschichte der Menschheit zeigt, dass jede große Idee das Ergebnis menschlichen Strebens und Arbeitens ist.",
                      "fr":"Une analyse approfondie et des réflexions sur {t}. L'histoire de l'humanité montre que toute grande idée est le résultat de l'aspiration et du travail humain."},
    "essay_concl_fb": {"uz":"Xulosa qilib aytganda, {t} kelajakka qilingan eng katta sarmoyadir. Har bir yangi kashfiyot oldimizdagi yo'lni yoritadi.",
                       "ru":"В заключение, {t} — это величайшая инвестиция в будущее. Каждое новое открытие освещает путь впереди.",
                       "en":"In conclusion, {t} is the greatest investment in the future. Every new discovery brightens the road ahead.",
                       "tr":"Sonuç olarak, {t} geleceğe yapılan en büyük yatırımdır. Her yeni keşif önümüzdeki yolu aydınlatır.",
                       "de":"Zusammenfassend ist {t} die größte Investition in die Zukunft. Jede neue Entdeckung erhellt den Weg vor uns.",
                       "fr":"En conclusion, {t} est le plus grand investissement dans l'avenir. Chaque nouvelle découverte éclaire la route à venir."},
    "main_part": {"uz":"ASOSIY QISM", "ru":"ОСНОВНАЯ ЧАСТЬ", "en":"MAIN PART", "tr":"TEMEL KISIM", "de":"HAUPTTEIL", "fr":"PARTIE PRINCIPALE"},
    "results_fb": {"uz":"{t} bo'yicha tadqiqot natijalari keltirilgan. Olingan ma'lumotlar statistik jihatdan ishonchli ekanligi isbotlandi.",
                   "ru":"Представлены результаты исследования по теме «{t}». Полученные данные доказали статистическую надёжность.",
                   "en":"The results of the research on {t} are presented. The data obtained proved statistically reliable.",
                   "tr":"{t} konulu araştırmanın sonuçları sunulmuştur. Elde edilen verilerin istatistiksel olarak güvenilir olduğu kanıtlanmıştır.",
                   "de":"Die Forschungsergebnisse zu {t} werden vorgestellt. Die erhaltenen Daten erwiesen sich als statistisch zuverlässig.",
                   "fr":"Les résultats de la recherche sur {t} sont présentés. Les données obtenues se sont avérées statistiquement fiables."},
    "results_box": {"uz":"Eksperimental guruh ko'rsatkichlari nazariy gipotezaga ko'ra 23% yuqori natija ko'rsatdi. Bu taklif etilayotgan modelning samaradorligini tasdiqlaydi.",
                    "ru":"Показатели экспериментальной группы показали результаты на 23% выше согласно теоретической гипотезе. Это подтверждает эффективность предложенной модели.",
                    "en":"The experimental group's indicators showed results 23% higher according to the theoretical hypothesis. This confirms the effectiveness of the proposed model.",
                    "tr":"Deney grubu göstergeleri, teorik hipoteze göre %23 daha yüksek sonuçlar gösterdi. Bu, önerilen modelin etkinliğini doğrulamaktadır.",
                    "de":"Die Indikatoren der Versuchsgruppe zeigten laut theoretischer Hypothese um 23 % höhere Ergebnisse. Dies bestätigt die Wirksamkeit des vorgeschlagenen Modells.",
                    "fr":"Les indicateurs du groupe expérimental ont montré des résultats supérieurs de 23 % selon l'hypothèse théorique. Cela confirme l'efficacité du modèle proposé."},
    "concl_final": {"uz":"Olingan natijalar shuni ko'rsatadiki, {t} sohasida yangi yondashuvlarni joriy etish samaradorlikni sezilarli darajada oshiradi.",
                    "ru":"Полученные результаты показывают, что внедрение новых подходов в сфере {t} значительно повышает эффективность.",
                    "en":"The results show that the implementation of new approaches in the field of {t} significantly improves efficiency.",
                    "tr":"Elde edilen sonuçlar, {t} alanında yeni yaklaşımların uygulanmasının verimliliği önemli ölçüde artırdığını göstermektedir.",
                    "de":"Die Ergebnisse zeigen, dass die Einführung neuer Ansätze im Bereich {t} die Effizienz erheblich steigert.",
                    "fr":"Les résultats montrent que la mise en œuvre de nouvelles approches dans le domaine de {t} améliore considérablement l'efficacité."},
    "sci_rec": {"uz":"Ushbu soha bo'yicha universitetlarda milliy platforma yaratish va kadrlar tayyorlashni kengaytirish zarur.",
                "ru":"Необходимо создать национальную платформу по этой сфере в университетах и расширить подготовку кадров.",
                "en":"It is necessary to create a national platform for this field at universities and expand staff training.",
                "tr":"Bu alanda üniversitelerde ulusal bir platform oluşturmak ve personel eğitimini genişletmek gerekmektedir.",
                "de":"Es ist notwendig, eine nationale Plattform für dieses Gebiet an Universitäten zu schaffen und die Personalausbildung zu erweitern.",
                "fr":"Il est nécessaire de créer une plateforme nationale pour ce domaine dans les universités et d'élargir la formation du personnel."},
}

def _loc(key, lang, topic=""):
    lang = str(lang).lower()
    return _LOC.get(key, {}).get(lang, _LOC.get(key, {}).get("en", key)).replace("{t}", str(topic)[:40])

# ===== Yordamchi funksiyalar =====
def _clean_text(text):
    """AI qaytargan matndan JSON qoldiqlari va ortiqcha belgilarni tozalash."""
    if not text: return ""
    
    # 1. Agar butun matn JSON bo'lsa, undan kerakli qiymatlarni ajratib olish
    try:
        data = json.loads(text)
        extracted = []
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, str) and len(v) > 20:
                    extracted.append(v)
                elif isinstance(v, dict):
                    for sub_k, sub_v in v.items():
                        if isinstance(sub_v, str) and len(sub_v) > 20:
                            extracted.append(sub_v)
        if extracted:
            return "\n\n".join(extracted)
    except Exception:
        pass

    # 2. Matn ichidagi JSON bloklarini (kalit: qiymat) olib tashlash
    text = re.sub(r'"[^"]+"\s*:\s*\{[^{}]*\}', '', text)
    text = re.sub(r'"[^"]+"\s*:\s*"[^"]*"', '', text)
    text = re.sub(r'\{[^{}]*\}', '', text)
    text = re.sub(r'\[[^\[\]]*\]', '', text)
    
    # 3. Ortiqcha belgilarni tozalash
    text = text.replace('\\n', '\n').replace('\\"', '"').replace("\\'", "'")
    text = re.sub(r'[^\x00-\x7F\u0400-\u04FF\u0600-\u06FF\u0100-\u017F\u1E00-\u1EFF\u2018-\u201F\u2022\u00AB\u00BB\u2013\u2014]', '', text)
    text = re.sub(r'^"|"$', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()

def _set_cell_bg(cell, color_hex):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:fill'), color_hex)
    tcPr.append(shd)

def _add_footer(section, lang):
    footer = section.footer
    footer.is_linked_to_previous = False
    p = footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    _cb = {"uz": "Yaratildi:", "ru": "Создано:", "en": "Created by:", "tr": "Oluşturan:", "de": "Erstellt von:", "fr": "Créé par :"}.get(str(lang).lower(), "Created by:")
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
        if level == 0: run.font.size = Pt(22)
        elif level == 1: run.font.size = Pt(16)
        else: run.font.size = Pt(14)
        run.font.bold = True
        run.font.color.rgb = RGBColor(20, 20, 20)
    return h

def _add_para(doc, text, size=14, bold=False, italic=False, align=None, indent=True, color=None):
    p = doc.add_paragraph()
    if align: p.alignment = align
    if indent: p.paragraph_format.first_line_indent = Cm(1.25)
    p.paragraph_format.line_spacing = 1.5
    p.paragraph_format.space_after = Pt(6)
    run = p.add_run(text)
    run.font.size = Pt(size)
    run.font.name = "Times New Roman"
    run.font.bold = bold
    run.font.italic = italic
    if color: run.font.color.rgb = color
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
    table = doc.add_table(rows=1, cols=1)
    table.style = "Table Grid"
    cell = table.cell(0, 0)
    _set_cell_bg(cell, bg_hex)
    p1 = cell.paragraphs[0]
    r1 = p1.add_run(title)
    r1.font.bold = True; r1.font.size = Pt(14); r1.font.name = "Times New Roman"
    r1.font.color.rgb = RGBColor(120, 60, 0)
    for line in body.split("\n"):
        if not line.strip(): continue
        p = cell.add_paragraph()
        p.paragraph_format.line_spacing = 1.3
        run = p.add_run(line.strip())
        run.font.size = Pt(13); run.font.name = "Times New Roman"
    doc.add_paragraph()

def _split_content(text, n):
    if not text: return ["" for _ in range(n)]
    paras = [p.strip() for p in re.split(r'\n\s*\n|\n', text) if p.strip() and len(p.strip()) > 20]
    if not paras: paras = [text[i:i+400] for i in range(0, len(text), 400)]
    per = max(1, len(paras) // n)
    parts = []
    idx = 0
    for i in range(n):
        if i == n - 1: parts.append("\n".join(paras[idx:]))
        else:
            parts.append("\n".join(paras[idx:idx+per]))
            idx += per
    return parts

def _parse_author(author, lbl):
    if not author or author.strip() in ("-", "—", ""):
        return [(lbl["author_label"], lbl["skip_author"])]
    lines = [l.strip() for l in author.split("\n") if l.strip()]
    result = []
    labels = [lbl["author_label"], lbl["supervisor_label"], lbl["dept_head_label"], lbl["reviewer_label"]]
    for i, line in enumerate(lines):
        if ":" in line[:20]:
            lab, val = line.split(":", 1)
            result.append((lab.strip() + ":", val.strip()))
        else:
            result.append((labels[i] if i < len(labels) else labels[-1], line))
    return result

# ===== MAXSUS REFERAT YARATISH =====
def _generate_special_referat(doc, topic, content_text, author, extra_data, lbl, lang):
    """Namunadagi kabi chiroyli va toza Referat yaratish. Barcha matnlar qat'iy tanlangan tilda."""
    data = extra_data or {}
    subject = str(data.get("ref_subject", "") or "").strip()
    institution = str(data.get("ref_institution", "") or "").strip()
    faculty = str(data.get("ref_faculty", "") or "").strip()
    dept = str(data.get("ref_dept", "") or "").strip()
    checker = str(data.get("ref_checker", "") or "").strip()
    
    # 1. TITUL VARAQ
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(lbl["ministry"])
    r.font.size = Pt(12); r.font.bold = True; r.font.name = "Times New Roman"
    
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(institution.upper() if institution not in ("", "-", "—") else "")
    r.font.size = Pt(14); r.font.bold = True; r.font.name = "Times New Roman"
    
    if faculty and faculty not in ("-", "—"):
        p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(f'{lbl.get("faculty_label", "Fakultet:")} {faculty}')
        r.font.size = Pt(12); r.font.name = "Times New Roman"
        
    if dept and dept not in ("-", "—"):
        p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(f'{lbl.get("dept_label", "Kafedra:")} {dept}')
        r.font.size = Pt(12); r.font.name = "Times New Roman"

    doc.add_paragraph()
    doc.add_paragraph()
    
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(lbl["referat"])
    r.font.size = Pt(24); r.font.bold = True; r.font.name = "Times New Roman"
    
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(f'{lbl.get("subject_label", "Fan:")} {subject if subject else "-"}')
    r.font.size = Pt(14); r.font.bold = True; r.font.name = "Times New Roman"
    
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(f"«{topic.upper()}»")
    r.font.size = Pt(16); r.font.bold = True; r.font.name = "Times New Roman"
    
    doc.add_paragraph()
    doc.add_paragraph()
    
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r = p.add_run(f'{lbl["author_label"]} {author if author else lbl["skip_author"]}')
    r.font.size = Pt(14); r.font.name = "Times New Roman"
    
    if checker and checker not in ("-", "—"):
        p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        r = p.add_run(f'{lbl["checked_label"]} {checker}')
        r.font.size = Pt(14); r.font.name = "Times New Roman"

    doc.add_paragraph()
    doc.add_paragraph()
    doc.add_paragraph()
    
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(lbl["city_year"])
    r.font.size = Pt(14); r.font.bold = True; r.font.name = "Times New Roman"
    
    doc.add_page_break()

    # 2. MUNDARIJA
    _add_heading(doc, lbl["toc"], level=1, center=True)
    
    chapters = _chapters_for("referat", lang)
    toc_items = [lbl["intro"]]
    for i, (ct, subs) in enumerate(chapters, 1):
        toc_items.append(f'{lbl["chapter"]} {i}. {ct}')
        if subs:
            for sub_num, sub_title in subs:
                toc_items.append(f'   {i}.{sub_num}. {sub_title}')
    toc_items.append(lbl["conclusion"])
    toc_items.append(lbl["references"])
    
    for item in toc_items:
        p = doc.add_paragraph()
        p.paragraph_format.line_spacing = 1.5
        p.paragraph_format.space_after = Pt(6)
        r = p.add_run(item)
        r.font.size = Pt(14); r.font.name = "Times New Roman"
    doc.add_page_break()

    # 3. ASOSIY MATN (Tozalangan)
    clean_content = _clean_text(content_text)
    lines = clean_content.split("\n")
    
    # Agar matn juda qisqa bo'lsa yoki bo'sh bo'lsa, zaxira matn qo'shamiz
    if len(clean_content) < 100:
        _add_heading(doc, lbl["intro"], level=1, center=True)
        _add_para(doc, _loc("relevance", lang, topic))
        _add_para(doc, _loc("goal", lang, topic))
        doc.add_page_break()
        _add_heading(doc, f'{lbl["chapter"]} 1. {_ph("theor_found", lang)}', level=1)
        _add_para(doc, _loc("chapter_fb", lang).format(title=_ph("theor_found", lang)))
        doc.add_page_break()
        _add_heading(doc, f'{lbl["chapter"]} 2. {_ph("analys_pract", lang)}', level=1)
        _add_para(doc, _loc("chapter_fb", lang).format(title=_ph("analys_pract", lang)))
        doc.add_page_break()
        _add_heading(doc, lbl["conclusion"], level=1, center=True)
        for pt in [_loc(f"concl{i}", lang, topic) for i in range(1, 5)]: _add_para(doc, pt, indent=False)
        doc.add_page_break()
        _add_references(doc, topic, lbl)
        buf = io.BytesIO(); doc.save(buf); buf.seek(0)
        return buf

    for line in lines:
        line = line.strip()
        if not line: 
            continue
            
        # Sarlavhalarni aniqlash va formatlash (qat'iy tanlangan tilda)
        if line.upper().startswith(lbl["intro"].upper()) or line.upper() == lbl["intro"].upper():
            _add_heading(doc, lbl["intro"], level=1, center=True)
        elif line.upper().startswith(lbl["conclusion"].upper()) or line.upper() == lbl["conclusion"].upper():
            _add_heading(doc, lbl["conclusion"], level=1, center=True)
        elif lbl["references"].upper() in line.upper() or "ADABIYOTLAR" in line.upper() or "ЛИТЕРАТУР" in line.upper():
            _add_heading(doc, lbl["references"], level=1, center=True)
        elif re.match(r'^\d+\.\s+[A-ZА-Я]', line): # 1. BOB, 2. ГЛАВА
            _add_heading(doc, line.upper(), level=1, center=False)
        elif re.match(r'^\d+\.\d+\.', line): # 1.1., 1.2.
            _add_heading(doc, line, level=2, center=False)
        else:
            # Oddiy matn
            _add_para(doc, line)

    buf = io.BytesIO(); doc.save(buf); buf.seek(0)
    return buf


# ===== Umumiy, to'liq lokalizatsiya qilingan DOCX shablon yordamchilari =====
def _add_title_page(doc, service_code, topic, author, lbl, include_dept=False, extra_data=None):
    data = extra_data or {}
    lang = lbl.get("_lang", "uz")
    service_title = lbl.get(service_code, lbl.get("topic_label", ""))
    institution = str(data.get("ref_institution", "") or "").strip()
    faculty = str(data.get("ref_faculty", "") or "").strip()
    dept = str(data.get("ref_dept", "") or "").strip()
    subject = str(data.get("ref_subject", "") or "").strip()
    checker = str(data.get("ref_checker", "") or "").strip()

    def centered(text, size=13, bold=False):
        if not text or text.strip() in ("-", "—"):
            return
        p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(text); r.font.size = Pt(size); r.font.bold = bold; r.font.name = "Times New Roman"

    centered(lbl.get("ministry", ""), 11, True)
    centered(institution.upper() if institution not in ("", "-", "—") else "", 14, True)
    centered(f"{lbl.get('faculty_label', '')} {faculty}" if faculty not in ("", "-", "—") else "", 12)
    if include_dept and dept not in ("", "-", "—"):
        centered(f"{lbl.get('dept_label', '')} {dept}".strip(), 12)
    centered("", 12)
    centered(service_title, 22, True)
    centered(f"{lbl.get('topic_label', '')} {topic}", 15, True)
    centered(f"{lbl.get('subject_label', '')} {subject}" if subject and subject not in ("-", "—") else "", 12)
    doc.add_paragraph()
    checker_key = "supervisor_label" if service_code in ("kurs", "diplom") else "checked_label"
    for key, value in (("author_label", author), (checker_key, checker)):
        value = str(value or "").strip()
        if value and value not in ("-", "—"):
            p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            r = p.add_run(f"{lbl.get(key, '')} {value}"); r.font.size = Pt(12); r.font.name = "Times New Roman"
    doc.add_paragraph()
    centered(lbl.get("city_year", ""), 12, True)
    doc.add_page_break()


def _add_toc(doc, toc_items, lbl):
    _add_heading(doc, lbl.get("toc", ""), level=1, center=True)
    table = doc.add_table(rows=0, cols=2)
    table.style = "Table Grid"
    for item in toc_items:
        title, page = item if isinstance(item, (tuple, list)) and len(item) == 2 else (str(item), "")
        cells = table.add_row().cells
        cells[0].text = str(title)
        cells[1].text = str(page)
        for cell in cells:
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.font.name = "Times New Roman"; run.font.size = Pt(11)
    doc.add_page_break()


def _add_intro(doc, topic, lbl, include_object=False, content_text=""):
    lang = lbl.get("_lang", "uz")
    _add_heading(doc, lbl.get("intro", ""), level=1, center=True)
    _add_label_para(doc, lbl.get("relevance", ""), _loc("relevance", lang, topic))
    _add_label_para(doc, lbl.get("goal", ""), _loc("goal", lang, topic))
    if include_object:
        _add_label_para(doc, lbl.get("object", ""), _loc("object", lang, topic))
        _add_label_para(doc, lbl.get("subject", ""), _loc("subject", lang, topic))
        _add_label_para(doc, lbl.get("tasks", ""), _loc("tasks", lang, topic))
    doc.add_paragraph()


def _add_chapter(doc, num, title, body, lbl, subsections=None):
    _add_heading(doc, f"{lbl.get('chapter', '')} {num}. {title}", level=1)
    subsections = subsections or []
    if subsections:
        parts = _split_content(body or "", len(subsections) + 1)
        if parts[0].strip():
            _add_para(doc, parts[0], indent=True)
        for idx, (sub_num, sub_title) in enumerate(subsections):
            _add_heading(doc, f"{num}.{sub_num}. {sub_title}", level=2)
            _add_para(doc, parts[idx + 1] if idx + 1 < len(parts) and parts[idx + 1].strip() else _loc("chapter_fb", lbl.get("_lang", "uz"), "").format(title=sub_title), indent=True)
    else:
        parts = _split_content(body or "", max(1, min(4, (len(body or "") // 1000) + 1)))
        for part in parts:
            if part.strip():
                _add_para(doc, part, indent=True)
    doc.add_paragraph()


def _add_conclusion(doc, topic, lbl, conclusion_key="conclusion"):
    lang = lbl.get("_lang", "uz")
    _add_heading(doc, lbl.get(conclusion_key, lbl.get("conclusion", "")), level=1, center=True)
    conclusion_text = _loc("concl_final", lang, topic)
    if conclusion_text:
        _add_para(doc, conclusion_text, indent=False)
    for key in ("concl1", "concl2", "concl3"):
        sentence = _loc(key, lang, topic)
        if sentence:
            _add_para(doc, sentence, indent=False)


def _add_references(doc, topic, lbl):
    lang = lbl.get("_lang", "uz")
    notes = {
        "uz": "Eslatma: topshirishdan oldin mavzu bo‘yicha haqiqatan foydalanilgan manbalarning to‘liq bibliografik ma’lumotlarini kiriting va tekshiring.",
        "ru": "Примечание: перед сдачей добавьте и проверьте полные библиографические данные источников, которые действительно использовались.",
        "en": "Note: before submission, add and verify the full bibliographic details of the sources actually used.",
        "tr": "Not: Çalışmayı teslim etmeden önce gerçekten kullanılan kaynakların tam bibliyografik bilgilerini ekleyin ve doğrulayın.",
        "de": "Hinweis: Ergänzen und überprüfen Sie vor der Abgabe die vollständigen bibliografischen Angaben der tatsächlich verwendeten Quellen.",
        "fr": "Remarque : avant la remise, ajoutez et vérifiez les références bibliographiques complètes des sources réellement utilisées.",
    }
    _add_heading(doc, lbl.get("references", ""), level=1, center=True)
    _add_para(doc, notes.get(lang, notes["en"]), indent=False)


# ===== Asosiy funksiya =====
def generate_docx(topic, service_name, service_code, lang, pages, content_text, author="", extra_data=None):
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(14)
    section = doc.sections[0]
    section.top_margin = Cm(2); section.bottom_margin = Cm(2)
    section.left_margin = Cm(3); section.right_margin = Cm(1.5)
    _add_footer(section, lang)

    lbl = _lbl(lang)
    content_text = content_text or ""

    # Referat bo'lsa, maxsus funksiyani chaqiramiz
    if service_code == "referat":
        return _generate_special_referat(doc, topic, content_text, author, extra_data, lbl, lang)

    if service_code == "test":
        return _generate_test(doc, topic, lang, pages, content_text, author, lbl, extra_data=extra_data)
    if service_code == "maqola":
        return _generate_article(doc, topic, lang, content_text, author, lbl, extra_data=extra_data)
    if service_code == "tezis":
        return _generate_thesis(doc, topic, lang, content_text, author, lbl, extra_data=extra_data)
    if service_code == "insho":
        return _generate_essay(doc, topic, lang, content_text, author, lbl, extra_data=extra_data)

    # Mustaqil, kurs va diplom ishlari uchun to'liq titul varaq.
    include_dept = service_code in ("mustaqil", "kurs", "diplom")
    _add_title_page(doc, service_code, topic, author, lbl, include_dept=include_dept, extra_data=extra_data)

    chapters = _chapters_for(service_code, lang)
    concl_key = "conclusion"
    if service_code == "kurs": concl_key = "conclusion_kurs"
    elif service_code == "diplom": concl_key = "conclusion_diplom"

    toc_items = [(lbl["intro"], "3")]
    for i, (ct, subs) in enumerate(chapters, 1):
        toc_items.append((f'{lbl["chapter"]} {i}. {ct}', str(4 + i*3)))
    toc_items.append((lbl[concl_key], str(4 + len(chapters)*3 + 2)))
    toc_items.append((lbl["references"], str(4 + len(chapters)*3 + 4)))
    if service_code == "diplom": toc_items.append((lbl["appendix"], str(4 + len(chapters)*3 + 6)))
    _add_toc(doc, toc_items, lbl)

    _add_intro(doc, topic, lbl, include_object=(service_code in ("kurs","diplom")), content_text=content_text[:400])
    doc.add_page_break()

    parts = _split_content(content_text, len(chapters))
    for i, ((ct, subs), body) in enumerate(zip(chapters, parts), 1):
        _add_chapter(doc, i, ct, body, lbl, subsections=subs)
        
        # Lokalizatsiya qilingan ramkalar
        if i == 1:
            _add_box(doc, lbl["important_def"], _loc("def_box", lang, topic))
        if service_code == "mustaqil" and i == len(chapters):
            _add_box(doc, lbl["practical_tip"], _loc("practical_tip", lang, topic))
        if service_code in ("kurs", "diplom") and i == 2:
            _add_box(doc, lbl["stats"], _loc("stats_box", lang, topic))
            
        doc.add_page_break()

    _add_conclusion(doc, topic, lbl, conclusion_key=concl_key)
    doc.add_page_break()
    _add_references(doc, topic, lbl)

    if service_code == "diplom":
        doc.add_page_break()
        _add_heading(doc, lbl["appendix"], level=1, center=True)
        _add_para(doc, _loc("appendix1", lang, topic), indent=False)
        _add_para(doc, _loc("appendix2", lang, topic), indent=False)
        _add_para(doc, _loc("appendix3", lang, topic), indent=False)

    buf = io.BytesIO(); doc.save(buf); buf.seek(0)
    return buf


def _add_compact_academic_header(doc, title, topic, author, lbl, extra_data=None,
                                topic_label=True, checker_label="supervisor_label",
                                show_city_year=True, show_ministry=False):
    """Add a compact localized header matching the supplied essay/article/test samples."""
    data = extra_data or {}

    def centered(text, size=12, bold=False, italic=False):
        value = str(text or "").strip()
        if not value or value in ("-", "—"):
            return
        p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(value); r.font.size = Pt(size); r.font.bold = bold
        r.font.italic = italic; r.font.name = "Times New Roman"

    if show_ministry:
        centered(lbl.get("ministry", ""), 10, True)
    institution = str(data.get("ref_institution", "") or "").strip()
    centered(institution.upper(), 12, True)

    faculty = str(data.get("ref_faculty", "") or "").strip()
    dept = str(data.get("ref_dept", "") or "").strip()
    details = []
    if faculty and faculty not in ("-", "—"):
        details.append(f"{lbl.get('faculty_label', '')} {faculty}".strip())
    if dept and dept not in ("-", "—"):
        details.append(f"{lbl.get('dept_label', '')} {dept}".strip())
    if details:
        centered("   |   ".join(details), 11)

    centered(title, 18, True)
    subject = str(data.get("ref_subject", "") or "").strip()
    if subject and subject not in ("-", "—"):
        centered(f"{lbl.get('subject_label', '')} {subject}".strip(), 12)
    topic_value = f"{lbl.get('topic_label', '')} {topic}" if topic_label else topic
    centered(topic_value, 15, True)

    for lab, val in _parse_author(author, lbl):
        centered(f"{lab} {val}", 12)
    checker = str(data.get("ref_checker", "") or "").strip()
    if checker and checker not in ("-", "—"):
        centered(f"{lbl.get(checker_label, lbl.get('checked_label', ''))} {checker}".strip(), 12)
    if show_city_year:
        centered(lbl.get("city_year", ""), 12, True)
    doc.add_paragraph()


def _generate_essay(doc, topic, lang, content_text, author, lbl, extra_data=None):
    _add_compact_academic_header(doc, lbl.get("essay_title", "ESSAY"), topic, author, lbl,
                                 extra_data=extra_data, topic_label=True,
                                 checker_label="supervisor_label", show_city_year=True)
    _add_heading(doc, lbl["intro"], level=1, center=True)
    _add_para(doc, _loc("essay_intro", lang, topic))
    _add_label_para(doc, "💭 " + lbl["goal"], _loc("essay_goal", lang, topic))
    doc.add_paragraph()
    _add_heading(doc, _loc("main_part", lang, topic), level=1, center=True)
    parts = _split_content(content_text, 3)
    for i, part in enumerate(parts):
        _add_para(doc, part or _loc("essay_main_fb", lang, topic))
    _add_box(doc, lbl["quote"], _loc("quote_text", lang), bg_hex="F3E5F5")
    doc.add_paragraph()
    _add_heading(doc, lbl["conclusion"], level=1, center=True)
    _add_para(doc, _loc("essay_concl_fb", lang, topic))
    _add_box(doc, lbl["final_wisdom"], _loc("final_wisdom", lang), bg_hex="E8F5E9")
    buf = io.BytesIO(); doc.save(buf); buf.seek(0)
    return buf

_TEST_FB = {
    "uz": [("Mavzu bo‘yicha ishonchli xulosa chiqarish uchun qaysi usul ma’qul?", ["Faktlarni ishonchli manbalar bilan tekshirish", "Taxminni dalilsiz qabul qilish", "Qarama-qarshi dalillarni e’tiborsiz qoldirish", "Faqat bitta fikrga tayanish"], "A")],
    "ru": [("Какой подход помогает сделать обоснованный вывод по теме?", ["Проверить факты по надежным источникам", "Принять предположение без доказательств", "Игнорировать противоречащие данные", "Опира́ться только на одно мнение"], "A")],
    "en": [("Which approach supports a reliable conclusion about a topic?", ["Verify facts using reliable sources", "Accept a guess without evidence", "Ignore conflicting evidence", "Rely on only one opinion"], "A")],
    "tr": [("Bir konu hakkında güvenilir sonuca ulaşmak için hangi yöntem uygundur?", ["Bilgileri güvenilir kaynaklarla doğrulamak", "Tahmini kanıtsız kabul etmek", "Çelişen kanıtları görmezden gelmek", "Yalnızca tek görüşe dayanmak"], "A")],
    "de": [("Welche Vorgehensweise unterstützt eine verlässliche Schlussfolgerung?", ["Fakten anhand zuverlässiger Quellen prüfen", "Eine Vermutung ohne Belege akzeptieren", "Widersprüchliche Belege ignorieren", "Sich nur auf eine Meinung stützen"], "A")],
    "fr": [("Quelle méthode permet de tirer une conclusion fiable sur un sujet ?", ["Vérifier les faits à l’aide de sources fiables", "Accepter une supposition sans preuve", "Ignorer les éléments contradictoires", "S’appuyer sur un seul avis"], "A")],
}


def _parse_test_questions(content_text, n_q, topic, lang):
    AK_RAT = {"uz": "To'g'ri javob — mavzuning asosiy mohiyatini ifodalaydi.", "ru": "Правильный ответ отражает суть темы.", "en": "The correct answer reflects the core essence of the topic.", "tr": "Doğru cevap konunun temel özünü yansıtır.", "de": "Die richtige Antwort spiegelt den Kern des Themas wider.", "fr": "La bonne réponse reflète l'essence du sujet."}
    default_rat = AK_RAT.get(str(lang).lower(), AK_RAT["en"])
    questions = []
    
    if content_text and len(str(content_text).strip()) > 50:
        lines = [ln.rstrip() for ln in str(content_text).split("\n")]
        cur = None
        opt_re = re.compile(r'^\s*([A-Da-d1-4])[\.\)]\s*(.+)$')
        qhead_re = re.compile(r'^\s*(\d+)[\.\-\)]\s*(?:SAVOL|QUESTION|SORU|FRAGE|ВОПРОС|Вопрос|Question)?\s*[:\-]?\s*(.*)$', re.I)
        rat_re = re.compile(r'^\s*(?:💡\s*)?(?:Izoh|Rationale|Açıklama|Begründung|Explication|Обоснование|Explanation)\s*[:\-]?\s*(.*)$', re.I)
        for ln in lines:
            if not ln.strip(): continue
            qm = qhead_re.match(ln)
            om = opt_re.match(ln)
            rm = rat_re.match(ln)
            if qm and not om and len(qm.group(2) or "") > 3:
                if cur: questions.append(cur)
                cur = {"text": qm.group(2).strip(), "options": [], "correct": None, "rationale": ""}
            elif om and cur is not None:
                opt_text = om.group(2).strip()
                is_correct = ("✓" in opt_text) or ("✔" in opt_text) or ("(✓" in opt_text) or ("to'g'ri javob" in opt_text.lower()) or ("correct answer" in opt_text.lower()) or ("doğru cevap" in opt_text.lower()) or ("richtige antwort" in opt_text.lower()) or ("bonne réponse" in opt_text.lower()) or ("правильный ответ" in opt_text.lower())
                opt_text = re.sub(r'\s*\(?(?:✓|✔)[^)]*\)?', '', opt_text).strip()
                opt_text = re.sub(r'\s*\([^)]*(to\'g\'ri|correct|doğru|richtige|bonne|правильн)[^)]*\)', '', opt_text, flags=re.I).strip()
                letter = "ABCD"["ABCD1234".find(om.group(1).upper()) % 4] if om.group(1).upper() in "ABCD1234" else "A"
                cur["options"].append((letter, opt_text))
                if is_correct: cur["correct"] = letter
            elif rm and cur is not None:
                cur["rationale"] = rm.group(1).strip()
            elif cur is not None and not om and len(cur["options"]) == 0:
                cur["text"] = (cur["text"] + " " + ln.strip()).strip()
        if cur: questions.append(cur)
        
    fb_list = _TEST_FB.get(str(lang).lower(), _TEST_FB["en"])
    
    # QAT'IY TO'LDIRISH
    while len(questions) < n_q:
        i = len(questions) + 1
        fb_q = fb_list[(i-1) % len(fb_list)]
        questions.append({
            "text": f"{i}. {fb_q[0]} ({topic})",
            "options": [("A", fb_q[1][0]), ("B", fb_q[1][1]), ("C", fb_q[1][2]), ("D", fb_q[1][3])],
            "correct": fb_q[2] if len(fb_q) > 2 else "A", "rationale": default_rat,
        })
        
    out = []
    # QAT'IY QIRQISH
    for i, q in enumerate(questions[:n_q]):
        opts = q["options"]
        if len(opts) < 4:
            used = {o[0] for o in opts}
            for L in "ABCD":
                if L not in used: opts.append((L, fb_list[0][1][len(opts) % 4]))
                if len(opts) >= 4: break
        q["options"] = opts[:4]
        if not q["correct"]: q["correct"] = "ABCD"[i % 4]
        if not q["rationale"]: q["rationale"] = default_rat
        out.append(q)
    return out

def _generate_test(doc, topic, lang, pages, content_text, author, lbl, extra_data=None):
    AK = {"uz": "JAVOBLAR KALITI VA IZOHLAR", "ru": "КЛЮЧ К ОТВЕТАМ И ОБЪЯСНЕНИЯ", "en": "ANSWER KEY AND EXPLANATIONS", "tr": "CEVAP ANAHTARI VE AÇIKLAMALAR", "de": "LÖSUNGSSCHLÜSSEL UND ERKLÄRUNGEN", "fr": "CORRIGÉ ET EXPLICATIONS"}
    ak_title = AK.get(str(lang).lower(), AK["en"])
    _add_compact_academic_header(doc, lbl["test_title"], topic, author, lbl,
                                 extra_data=extra_data, topic_label=True,
                                 checker_label="checked_label", show_city_year=True)

    n_q = int(pages) if pages else 20
    if n_q < 1: n_q = 20

    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(f'{lbl["questions_count"]} {n_q}   •   {lbl["level"]}'); r.font.size = Pt(13); r.font.italic = True; r.font.name = "Times New Roman"
    _add_heading(doc, lbl.get("test_instructions", lbl["test_title"]), level=1, center=True)
    doc.add_paragraph()

    questions = _parse_test_questions(content_text, n_q, topic, lang)
    answer_key = []
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

def _generate_article(doc, topic, lang, content_text, author, lbl, extra_data=None):
    _add_compact_academic_header(doc, lbl.get("article_title", "SCIENTIFIC ARTICLE"), topic, author, lbl,
                                 extra_data=extra_data, topic_label=False,
                                 checker_label="supervisor_label", show_city_year=False)
    
    # Kalit so'zlar ham tanlangan tilda bo'lishi shart
    kw_dict = {
        "uz": "tahlil, rivojlanish, samaradorlik, tavsiyalar",
        "ru": "анализ, развитие, эффективность, рекомендации",
        "en": "analysis, development, efficiency, recommendations",
        "tr": "analiz, gelişme, verimlilik, öneriler",
        "de": "analyse, entwicklung, effizienz, empfehlungen",
        "fr": "analyse, développement, efficacité, recommandations"
    }
    keywords_text = kw_dict.get(str(lang).lower(), kw_dict["en"])
    
    _add_label_para(doc, lbl["annotation"], _loc("article_abstract", lang, topic))
    _add_label_para(doc, lbl["keywords"], f"{topic}, {keywords_text}.")
    doc.add_paragraph()
    _add_heading(doc, lbl["intro"], level=1, center=True)
    _add_para(doc, _loc("article_intro", lang, topic))
    doc.add_paragraph()
    _add_heading(doc, _loc("main_part", lang, topic), level=1, center=True)
    parts = _split_content(content_text, 3)
    for part in parts:
        _add_para(doc, part or _loc("essay_main_fb", lang, topic))
    _add_box(doc, lbl["stats"], _loc("stats_box", lang, topic), bg_hex="E3F2FD")
    doc.add_paragraph()
    _add_heading(doc, lbl["conclusion"], level=1, center=True)
    _add_para(doc, _loc("essay_concl_fb", lang, topic))
    _add_box(doc, lbl["author_recommendation"], _loc("author_rec", lang, topic), bg_hex="FFF3E0")
    buf = io.BytesIO(); doc.save(buf); buf.seek(0)
    return buf

def _generate_thesis(doc, topic, lang, content_text, author, lbl, extra_data=None):
    _add_compact_academic_header(doc, lbl["thesis"], topic, author, lbl,
                                 extra_data=extra_data, topic_label=True,
                                 checker_label="supervisor_label", show_city_year=False)
    _add_label_para(doc, lbl["relevance_thesis"], _loc("thesis_intro", lang, topic))
    _add_label_para(doc, lbl["methods"], _loc("method", lang, topic))
    doc.add_paragraph()
    parts = _split_content(content_text, 2)
    for part in parts:
        _add_para(doc, part or _loc("results_fb", lang, topic))
    _add_box(doc, lbl["results"], _loc("results_box", lang, topic), bg_hex="E8F5E9")
    doc.add_paragraph()
    _add_heading(doc, lbl["conclusion"], level=1, center=True)
    _add_para(doc, _loc("concl_final", lang, topic))
    _add_box(doc, lbl["scientific_rec"], _loc("sci_rec", lang, topic), bg_hex="F3E5F5")
    buf = io.BytesIO(); doc.save(buf); buf.seek(0)
    return buf
