"""Test savollari zaxirasi: savollar va javoblar bir xil bo‘lib qolmasligi."""
import io
import re
import unittest

from docx import Document

import ai_api
import docx_generator
from services import ALL_LANGS, service_name


class QuizFallbackTests(unittest.TestCase):
    def test_every_language_gets_distinct_questions(self):
        for lang in ALL_LANGS:
            with self.subTest(lang=lang):
                text = ai_api._fallback_test_questions("Mexanika", 1, 15, lang)
                lines = [line for line in text.splitlines() if line.strip()]
                stems = [line for line in lines if re.match(r"^\d+\.\s", line)]
                marked = [line for line in lines if "\u2713" in line]
                self.assertEqual(len(stems), 15)
                self.assertEqual(len(set(stems)), 15, "savollar takrorlanmasligi kerak")
                self.assertEqual(len(marked), 15, "har savolda bitta to'g'ri javob bo'lsin")
                letters = {re.match(r"([A-D])\)", line).group(1) for line in marked}
                self.assertGreaterEqual(len(letters), 3, "to'g'ri javob harfi almashtirilishi kerak")
                for number in range(1, 16):
                    block = text.split(f"{number}. ", 1)[1].split("\n\n", 1)[0]
                    options = [line for line in block.splitlines() if re.match(r"^[A-D]\)", line.strip())]
                    self.assertEqual(len(options), 4, f"{lang}: {number}-savolda 4 variant bo'lsin")
                    self.assertEqual(len(set(options)), 4, f"{lang}: variantlar takrorlanmasin")

    def test_docx_quiz_fills_missing_questions_with_varied_keys(self):
        buf = docx_generator.generate_docx(
            "Mexanika", service_name("test", "uz"), "test", "uz", 15, "",
            author="Talaba", extra_data={},
        )
        doc = Document(io.BytesIO(buf.read()))
        text = "\n".join(paragraph.text for paragraph in doc.paragraphs)
        questions = re.findall(r"^\d+\.\s*[A-ZА-Я]", text, flags=re.M)
        self.assertEqual(len(questions), 15, "15 savol chiqishi kerak")
        keys = re.findall(r"^(\d+)-([A-D])\.", text, flags=re.M)
        self.assertEqual(len(keys), 15, "javoblar kaliti to'liq bo'lsin")
        self.assertGreaterEqual(len({letter for _, letter in keys}), 2,
                                "javob kaliti harflari bir xil bo'lib qolmasin")
        # Savollar tartibi va soni buzilmasdan o'tishi shart.
        raw = ai_api._fallback_test_questions("Mexanika", 1, 15, "uz")
        raw_stems = [line.split(". ", 1)[1] for line in raw.splitlines()
                     if re.match(r"^\d+\. ", line)]
        filled = Document(io.BytesIO(docx_generator.generate_docx(
            "Mexanika", service_name("test", "uz"), "test", "uz", 15, raw,
            author="Talaba", extra_data={},
        ).read()))
        docx_stems, expect = [], False
        for paragraph in filled.paragraphs:
            value = paragraph.text.strip()
            if re.match(r"^\d+\.\s*SAVOL$", value):
                expect = True
                continue
            if expect:
                docx_stems.append(value)
                expect = False
        self.assertEqual(docx_stems, raw_stems,
                         "savollar yo'qolmasligi yoki siljimasligi kerak")


if __name__ == "__main__":
    unittest.main()
