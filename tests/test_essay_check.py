import io
import unittest

import essay_checker


class EssayCheckerTest(unittest.TestCase):
    def _docx(self, paragraphs):
        from docx import Document
        document = Document()
        for text in paragraphs:
            document.add_paragraph(text)
        buffer = io.BytesIO()
        document.save(buffer)
        return buffer.getvalue()

    def test_extract_docx_text(self):
        data = self._docx(["Esse mavzusi", "", "Birinchi xat bosh."])
        text = essay_checker.extract_docx_text(data)
        self.assertIn("Esse mavzusi", text)
        self.assertIn("Birinchi xat bosh.", text)
        self.assertNotIn("\n\n\n", text)

    def test_decode_text_handles_cp1251(self):
        raw = "Salom dunyo".encode("cp1251")
        self.assertEqual(essay_checker.decode_text(raw), "Salom dunyo")
        self.assertEqual(essay_checker.decode_text("Şahar".encode("utf-8")), "Şahar")

    def test_normalize_clamps_and_totals(self):
        report = essay_checker.normalize_report(
            {"scores": {"imlo": 99, "grammatika": -5, "tinish": 10},
             "errors": [{"quote": "xato", "fix": "to'g'ri", "type": "imlo", "rule": "qoida"}],
             "advice": ["ko'proq o'qing"]},
            "Bu qisqa matn.", "uz")
        self.assertEqual(report["scores"]["imlo"], 25)
        self.assertEqual(report["scores"]["grammatika"], 0)
        self.assertEqual(report["total"], 35)
        self.assertEqual(report["grade"], "qoniqarsiz")
        self.assertEqual(report["errors"][0]["fix"], "to'g'ri")

    def test_report_text_contains_scores_and_errors(self):
        report = essay_checker.normalize_report(
            {"scores": {key: maximum for key, maximum in essay_checker.CRITERIA},
             "errors": [{"quote": "kelmagan", "fix": "kelmagan", "type": "imlo",
                         "rule": "imlo qoidasi"}],
             "summary": "Yaxshi ish."},
            "Matn.", "uz")
        text = essay_checker.format_report(report, "uz")
        self.assertIn("Umumiy ball: 100/100", text)
        self.assertIn("a'lo", text)
        self.assertIn("kelmagan", text)
        self.assertNotIn("<", text)

    def test_word_count(self):
        self.assertEqual(essay_checker.word_count("Bir ikki uch, to'rt!"), 4)


if __name__ == "__main__":
    unittest.main()
