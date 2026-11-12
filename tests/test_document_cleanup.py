"""Hujjat matnidagi ko'rinadigan nuqsonlar: reja axlati, takror xulosa, yorliqlar."""
import io
import re
import unittest

from docx import Document

import docx_generator
from services import service_name


def paragraphs(buf):
    doc = Document(io.BytesIO(buf.read()))
    return [p.text.strip() for p in doc.paragraphs if p.text.strip()]


class DocumentCleanupTests(unittest.TestCase):
    def test_insho_plan_drops_prompt_echo(self):
        plan = ("Mavzu: Yoshlikda berilgan tarbiyaning ahamiyati\n"
                "Vazifa: Aynan besh qator yozing:\n"
                "1. Kirish:\n"
                "Kirish mazmuni: Yoshlikda berilgan tarbiyaning ahamiyati.")
        lines = docx_generator._insho_plan_for_doc(plan, "Yoshlikda berilgan tarbiyaning ahamiyati", "uz")
        self.assertEqual(len(lines), 5)
        self.assertFalse([line for line in lines if re.search(
            r"(?i)vazifa|mavzu:|aynan besh|kirish mazmuni", line)], lines)
        for prefix in ("1.", "2.", "3."):
            self.assertTrue(any(line.startswith(prefix) for line in lines), (prefix, lines))

    def test_english_labels_are_localized(self):
        text = ("Relevance of the topic: Mexanika qonunlarni o'rganadi.\n"
                "Goal of the work: tahlil qilish.\n"
                "Tasks completed: uchta vazifa.")
        uz = docx_generator._localize_label_paragraphs(text, "uz")
        self.assertIn("Mavzuning dolzarbligi:", uz)
        self.assertIn("Ishning maqsadi:", uz)
        self.assertIn("Bajarilgan vazifalar:", uz)
        self.assertNotIn("Relevance of the topic:", uz)
        self.assertEqual(docx_generator._localize_label_paragraphs(text, "en"), text)

    def test_mustaqil_conclusion_does_not_repeat_lead(self):
        lead = "Mavzuni o‘rganib chiqib, quyidagi xulosalarga keldim:"
        content = (f"[[XULOSA]]\n{lead}\n1. {lead}\n"
                   "2. Birinchi xulosa matni to‘liq yozilgan.\n"
                   "3. Ikkinchi xulosa matni ham yozilgan.\n"
                   "4. Uchinchi xulosa bayoni.\n")
        body = paragraphs(docx_generator.generate_docx(
            "Mexanika", service_name("mustaqil", "uz"), "mustaqil", "uz", 10, content,
            author="Talaba"))
        start = body.index("XULOSA")
        block = body[start + 1:start + 6]
        self.assertEqual(block[0], lead)
        self.assertEqual(sum(1 for line in block if lead in line), 1, block)
        self.assertTrue(block[1].startswith("1. "), block)

    def test_foreign_words_are_replaced_in_uzbek(self):
        text = "Kültür antropologiyasi va Nəşriyotu təhsil tizimi."
        fixed = docx_generator._fix_foreign_leaks(text, "uz")
        self.assertNotIn("Kültür", fixed)
        self.assertNotIn("Nəşriyot", fixed)
        self.assertNotIn("təhsil", fixed)
        self.assertEqual(docx_generator._fix_foreign_leaks(text, "tr"), text)

    def test_reference_page_tails_are_removed(self):
        mq = docx_generator._mq("uz")
        entries = docx_generator._mq_reference_lines(
            "1. Qonun hujjati. – 1992 yil. – 1‑sahifa.\n"
            "2. Karimov N. Asoslar. – Toshkent: Fan, 2019. – 45‑bet", mq)
        self.assertFalse([item for item in entries if re.search(r"sahifa|bet", item)], entries)


if __name__ == "__main__":
    unittest.main()
