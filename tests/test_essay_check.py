import io
import unittest

import essay_checker as ec

LONG_TEXT = " ".join(["Bugungi kunda ta'lim tizimi jamiyat taraqqiyotining asosiy omili"] * 15)
CYRILLIC_TEXT = " ".join(["Бугунги кунда таълим тизими жамият тараққиётининг асосий омили"] * 15)


class EssayCheckerTest(unittest.TestCase):
    def _docx(self, paragraphs):
        from docx import Document
        document = Document()
        for text in paragraphs:
            document.add_paragraph(text)
        buffer = io.BytesIO()
        document.save(buffer)
        return buffer.getvalue()

    def _report(self, data=None, text=None, topic=""):
        payload = {"scores": {key: 2 for key in ec.CRITERIA_KEYS}}
        payload.update(data or {})
        return ec.normalize_report(payload, text if text is not None else LONG_TEXT, "uz", topic)

    def test_extract_docx_text(self):
        data = self._docx(["Esse mavzusi", "", "Birinchi xat bosh."])
        text = ec.extract_docx_text(data)
        self.assertIn("Esse mavzusi", text)
        self.assertIn("Birinchi xat bosh.", text)

    def test_decode_text_handles_cp1251(self):
        self.assertEqual(ec.decode_text("Salom dunyo".encode("cp1251")), "Salom dunyo")
        self.assertEqual(ec.decode_text("Şahar".encode("utf-8")), "Şahar")

    def test_twelve_bands_with_two_points_each(self):
        report = self._report()
        self.assertEqual(len(ec.CRITERIA), 12)
        self.assertEqual(report["total"], 24)
        self.assertEqual(report["max_total"], 24)

    def test_band_scores_are_clamped_to_official_range(self):
        report = ec.normalize_report({"scores": {"imlo": 7, "tinish": -3}}, LONG_TEXT, "uz")
        self.assertEqual(report["scores"]["imlo"], 2)
        self.assertEqual(report["scores"]["tinish"], 0)

    def test_short_essay_gets_two_points(self):
        report = self._report(text="Qisqa matn.")
        self.assertIn("short", report["flags"])
        self.assertEqual(report["total"], 2)

    def test_off_topic_essay_gets_two_points(self):
        report = self._report({"topic_match": False}, topic="Ta'limdagi islohotlar")
        self.assertIn("offtopic", report["flags"])
        self.assertEqual(report["total"], 2)

    def test_copied_essay_gets_two_points(self):
        report = self._report({"plagiarism_suspected": True})
        self.assertIn("copied", report["flags"])
        self.assertEqual(report["total"], 2)

    def test_only_introduction_gets_zero(self):
        report = self._report({"sections": {"kirish": True, "asosiy": False, "xulosa": False}})
        self.assertIn("notask", report["flags"])
        self.assertEqual(report["total"], 0)

    def test_full_cyrillic_gets_zero(self):
        report = self._report(text=CYRILLIC_TEXT)
        self.assertIn("cyrillic", report["flags"])
        self.assertEqual(report["total"], 0)

    def test_report_lists_every_band_and_total(self):
        report = self._report({"errors": [{"quote": "kelmagan", "fix": "kelmagan",
                                            "type": "imlo", "rule": "imlo qoidasi"}],
                               "review": "Yaxshi ish."})
        text = ec.format_report(report, "uz")
        self.assertIn("24/24 ball (100%)", text)
        self.assertIn("7. Imlo — 2/2", text)
        self.assertIn("12. Adabiy til me'yorlari — 2/2", text)
        self.assertIn("kelmagan", text)
        self.assertNotIn("<", text)

    def test_prompt_contains_official_bands_and_topic(self):
        prompt = ec.build_prompt("Matn.", "Mavzu matni")
        self.assertIn("12 ta band", prompt)
        self.assertIn("Mavzu matni", prompt)
        self.assertIn("FAQAT 0, 1 yoki 2 ball", prompt)

    def test_word_count_keeps_apostrophe_words(self):
        self.assertEqual(ec.word_count("Bir ikki uch, to'rt!"), 4)

    def test_cyrillic_ratio(self):
        self.assertGreater(ec.cyrillic_ratio(CYRILLIC_TEXT), 0.9)
        self.assertEqual(ec.cyrillic_ratio("Salom dunyo"), 0)

    def test_labels_fallback_for_unknown_language(self):
        self.assertEqual(ec.labels("de")["total"], "Total")


if __name__ == "__main__":
    unittest.main()
