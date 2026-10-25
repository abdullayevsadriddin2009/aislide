"""Smoke tests for localized DOCX and PPTX generation.

Run with: python -m unittest discover -s tests -v
"""
import io
import unittest

from pptx import Presentation

from docx_generator import generate_docx, L
from pptx_generator import generate_pptx, THEMES, UI

LANGS = ("uz", "ru", "en", "tr", "de", "fr")
SERVICES = ("referat", "mustaqil", "kurs", "diplom", "insho", "test", "maqola", "tezis")
SLIDE_COUNTS = (5, 7, 10, 12, 15, 18, 20, 25, 30)
SAMPLE_SLIDES = [
    {"title": "Kirish", "content": ["Birinchi fikr.", "Ikkinchi fikr.", "Uchinchi fikr."]},
    {"title": "Asosiy tushunchalar", "content": ["Muhim tushuncha.", "Amaliy misol.", "Natija."]},
    {"title": "Xulosa", "content": ["Natijalar umumlashtiriladi.", "Tavsiyalar beriladi.", "Keyingi ishlar belgilanadi."]},
]
SAMPLE_TEXT = {
    "uz": "Kirish\n\nMavzuning asosiy jihatlari tahlil qilinadi. Amaliy misollar ko‘rib chiqiladi.\n\nXulosa\nAsosiy natijalar umumlashtiriladi.",
    "ru": "Введение\n\nРассматриваются основные аспекты темы и практические примеры.\n\nЗаключение\nОсновные результаты обобщены.",
    "en": "Introduction\n\nThe main aspects and practical examples of the topic are examined.\n\nConclusion\nThe key findings are summarized.",
    "tr": "Giriş\n\nKonunun temel yönleri ve uygulamalı örnekler incelenir.\n\nSonuç\nTemel bulgular özetlenir.",
    "de": "Einleitung\n\nDie wichtigsten Aspekte des Themas und praktische Beispiele werden untersucht.\n\nFazit\nDie wichtigsten Erkenntnisse werden zusammengefasst.",
    "fr": "Introduction\n\nLes principaux aspects du sujet et des exemples pratiques sont examinés.\n\nConclusion\nLes principaux résultats sont résumés.",
}
EXTRA_DATA = {
    "ref_subject": "Computer Science",
    "ref_institution": "Example University",
    "ref_faculty": "Information Technology",
    "ref_dept": "Computer Science",
    "ref_author": "Test Student, Group 101",
    "ref_checker": "Test Teacher",
}


class PPTXGeneratorTests(unittest.TestCase):
    def test_all_designs_languages_and_counts(self):
        for lang in LANGS:
            for design in THEMES:
                for total in SLIDE_COUNTS:
                    with self.subTest(lang=lang, design=design, total=total):
                        stream = generate_pptx(
                            "Example topic", "Computer Science", lang, design, total,
                            SAMPLE_SLIDES, author="Test Student",
                        )
                        deck = Presentation(io.BytesIO(stream.read()))
                        self.assertEqual(len(deck.slides), total)
                        last_slide_text = " ".join(
                            shape.text for shape in deck.slides[-1].shapes if hasattr(shape, "text")
                        )
                        self.assertIn(UI[lang]["thanks"], last_slide_text)


class DOCXGeneratorTests(unittest.TestCase):
    def test_translation_dictionaries_have_matching_keys(self):
        expected = set(L["uz"])
        for lang in LANGS:
            self.assertEqual(set(L[lang]), expected, msg=f"Missing localization key for {lang}")


    def test_essay_has_five_point_plan_without_section_headings(self):
        from docx import Document
        content = (
            "[[ESSAY_INTRO]]\nI. KIRISH QISMI\nAmir Temur XIV asrda muhim davlat arbobi bo‘lgan.\n\n"
            "[[ESSAY_BODY]]\nII. ASOSIY QISM\nU davlat boshqaruvini mustahkamlashga intilgan.\n\n"
            "Samarqand madaniy markaz sifatida rivojlangan.\n\n"
            "Uning merosini xolis baholash kerak.\n\n"
            "[[ESSAY_CONCLUSION]]\nIII. XULOSA QISMI\nXulosa qilib aytganda, tarixiy merosni dalillar asosida o‘rganish muhim."
        )
        stream = generate_docx(
            topic="Amir Temur", service_name="INSHO / ESSEY", service_code="insho",
            lang="uz", pages=2, content_text=content, author="Talaba",
            extra_data={
                "essay_target_words": 200,
                "essay_outline": "1. Kirish: mavzuning tarixiy ahamiyati\n"
                                "2. Birinchi fikr: davlat boshqaruvi\n"
                                "3. Ikkinchi fikr: Samarqand madaniyati\n"
                                "4. Uchinchi fikr: merosga xolis baho\n"
                                "5. Xulosa: tarixiy saboqlar",
            },
        )
        doc = Document(io.BytesIO(stream.getvalue()))
        full_text = "\n".join(p.text for p in doc.paragraphs)
        self.assertIn("REJA", full_text)
        for n in range(1, 6):
            self.assertIn(f"{n}.", full_text)
        self.assertNotIn("KIRISH QISMI", full_text)
        self.assertNotIn("ASOSIY QISM", full_text)
        self.assertNotIn("XULOSA QISMI", full_text)
        self.assertIn("Amir Temur XIV asrda", full_text)

    def test_all_services_and_languages_generate(self):
        for lang in LANGS:
            for service in SERVICES:
                with self.subTest(lang=lang, service=service):
                    stream = generate_docx(
                        topic="Example topic",
                        service_name="Example service",
                        service_code=service,
                        lang=lang,
                        pages=5,
                        content_text=SAMPLE_TEXT[lang],
                        author="Test Student",
                        extra_data=EXTRA_DATA,
                    )
                    self.assertGreater(len(stream.getvalue()), 1000)


if __name__ == "__main__":
    unittest.main()
