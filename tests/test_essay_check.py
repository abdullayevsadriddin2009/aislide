import asyncio
import io
import json
import unittest

import ai_api
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

    def test_scores_written_as_text_are_parsed(self):
        scores = ec.band_scores({"imlo": "2/2", "tinish": "1 ball", "soz": None})
        self.assertEqual(scores["imlo"], 2)
        self.assertEqual(scores["tinish"], 1)
        self.assertEqual(scores["soz"], 0)

    def test_band_scores_are_clamped_to_official_range(self):
        report = ec.normalize_report({"scores": {"imlo": 7, "tinish": -3}}, LONG_TEXT, "uz")
        self.assertEqual(report["scores"]["imlo"], 2)
        self.assertEqual(report["scores"]["tinish"], 0)

    def test_short_essay_gets_two_points(self):
        report = self._report(text="Qisqa matn.")
        self.assertIn("short", report["flags"])
        self.assertEqual(report["total"], 2)

    def test_partial_ocr_does_not_force_two_points(self):
        # Qo'lyozma rasm to'liq o'qilmagan bo'lsa, rasmiy «100 so'z» qoidasi
        # qo'llanmaydi: foydalanuvchidan aniqroq rasm so'raladi.
        text = " ".join(["Bugungi kunda ta'lim tizimi jamiyat taraqqiyotining omili"] * 6)
        self.assertLess(ec.word_count(text), ec.MIN_WORDS)
        report = ec.normalize_report({"scores": {key: 2 for key in ec.CRITERIA_KEYS}},
                                     text, "uz", "", from_image=True)
        self.assertIn("ocr_short", report["flags"])
        self.assertNotIn("short", report["flags"])
        self.assertEqual(report["total"], 24)
        self.assertIn("to'liq o'qilmadi", ec.format_report(report, "uz"))

    def test_image_with_a_few_words_still_gets_two_points(self):
        report = ec.normalize_report({"scores": {key: 2 for key in ec.CRITERIA_KEYS}},
                                     "Ikki so'z", "uz", "", from_image=True)
        self.assertIn("short", report["flags"])
        self.assertEqual(report["total"], 2)

    def test_fake_errors_are_dropped(self):
        # AI to'g'ri so'zni «xato» deb, tuzatish o'rniga o'sha so'zni qaytargan.
        report = self._report({"errors": [
            {"quote": "Insho", "fix": "Insho", "type": "imlo"},
            {"quote": "universitetlari", "fix": "universitetlari → universitetlari",
             "type": "imlo"},
            {"quote": "ta'lim", "fix": "to'g'ri yozilishi kerak", "type": "imlo"},
            {"quote": "universitetlari", "fix": "universitetlarida", "type": "imlo"},
        ]})
        self.assertEqual(len(report["errors"]), 1)
        self.assertEqual(report["errors"][0]["fix"], "universitetlarida")

    def test_ocr_continuation_does_not_repeat_text(self):
        head = "Birinchi xatbosh. Ikkinchi jumla shu yerda boshlanadi"
        tail = "boshlanadi va davom etadi."
        self.assertEqual(ec._join_continuation(head, tail),
                         "Birinchi xatbosh. Ikkinchi jumla shu yerda boshlanadi va davom etadi.")
        self.assertEqual(ec._join_continuation("Salom", "dunyo"), "Salom\ndunyo")

    def test_vision_config_disables_thinking_for_new_models(self):
        config = ec._vision_config("gemini-2.5-flash", 4096)
        self.assertEqual(config["thinkingConfig"], {"thinkingBudget": 0})
        self.assertNotIn("thinkingConfig", ec._vision_config("gemini-2.0-flash", 4096))

    def test_google_answer_joins_text_parts_without_thoughts(self):
        body = json.dumps({"candidates": [{"content": {"parts": [
            {"text": "o'ylash", "thought": True}, {"text": "{\"a\": "},
            {"text": "1}"}]}, "finishReason": "STOP"}]})
        self.assertEqual(ai_api._google_text(body), '{"a": 1}')
        self.assertTrue(ai_api._google_thinks("gemini-2.5-flash"))
        self.assertTrue(ai_api._google_thinks("gemini-flash-lite-latest"))
        self.assertFalse(ai_api._google_thinks("gemini-2.0-flash"))
        self.assertFalse(ai_api._google_thinks("gemma-3-27b-it"))

    def test_vision_text_reports_truncation(self):
        body = json.dumps({"candidates": [{"content": {"parts": [{"text": "matn"}]},
                                           "finishReason": "MAX_TOKENS"}]})
        self.assertEqual(ec._vision_text(body), ("matn", True))
        done = json.dumps({"candidates": [{"content": {"parts": [{"text": "matn"}]},
                                           "finishReason": "STOP"}]})
        self.assertEqual(ec._vision_text(done), ("matn", False))

    def test_truncated_ai_json_still_gives_a_report(self):
        # Gemini o'ylash byudjetini sarflab javobni yarmida to'xtatishi mumkin.
        cut = '{"scores": {"uslub": 2, "qarashlar": 1, "dalillar":'
        data = ec._parse_json_object(cut)
        self.assertIsNotNone(data)
        self.assertEqual(data["scores"]["uslub"], 2)
        report = ec.normalize_report(data, LONG_TEXT, "uz")
        self.assertGreater(report["total"], 0)

    def test_report_is_requested_again_when_answer_is_not_json(self):
        answers = ["⚠️ AI serverga ulanib bo'lmadi.",
                   json.dumps({"scores": {key: 2 for key in ec.CRITERIA_KEYS},
                               "sections": {"kirish": True, "asosiy": True, "xulosa": True}})]
        calls = []

        async def fake_complete(prompt, **kwargs):
            calls.append(kwargs.get("max_tokens"))
            return answers[min(len(calls), len(answers)) - 1]

        original = ai_api._chat_complete
        ai_api._chat_complete = fake_complete
        try:
            report = asyncio.run(ec.analyze_essay(LONG_TEXT, "uz", ""))
        finally:
            ai_api._chat_complete = original
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1], 4000)
        self.assertEqual(report["total"], 24)

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

    def test_blank_work_gets_zero(self):
        report = self._report(text="")
        self.assertIn("blank", report["flags"])
        self.assertEqual(report["total"], 0)
        self.assertEqual(report["scale_75"], 0)

    def test_full_cyrillic_gets_zero(self):
        report = self._report(text=CYRILLIC_TEXT)
        self.assertIn("cyrillic", report["flags"])
        self.assertEqual(report["total"], 0)

    def test_scale_75_conversion(self):
        self.assertEqual(ec.to_scale_75(24), 75)
        self.assertEqual(ec.to_scale_75(12), 38)
        self.assertEqual(ec.to_scale_75(0), 0)
        self.assertEqual(self._report()["scale_75"], 75)

    def test_plan_and_epigraph_are_reported(self):
        report = self._report({"has_plan": True, "has_epigraph": True})
        self.assertTrue(report["plan_written"])
        self.assertTrue(report["epigraph_written"])
        body = ec.format_report(report, "uz")
        self.assertIn("reja yozilgan", body)
        self.assertIn("epigraf yozilgan", body)

    def test_report_lists_every_band_and_total(self):
        report = self._report({"errors": [{"quote": "kelmagan", "fix": "kelgan",
                                            "type": "imlo", "rule": "imlo qoidasi"}],
                               "review": "Yaxshi ish."})
        text = ec.format_report(report, "uz")
        self.assertIn("24/24 ball (100%)", text)
        self.assertIn("7. Imlo — 2/2", text)
        self.assertIn("12. Adabiy til me'yorlari — 2/2", text)
        self.assertIn("kelmagan", text)
        self.assertNotIn("<", text)

    def test_report_shows_scale_and_structure(self):
        report = self._report({"sections": {"kirish": True, "asosiy": True, "xulosa": False}})
        body = ec.format_report(report, "uz")
        self.assertIn("75 ballik shkala: 75/75", body)
        self.assertIn("Tuzilma", body)
        self.assertIn("Xulosa ❌", body)

    def test_errors_are_capped_at_twenty(self):
        errors = [{"quote": f"xato {i}", "fix": "to'g'ri", "type": "imlo"} for i in range(30)]
        report = self._report({"errors": errors})
        self.assertEqual(len(report["errors"]), 20)

    def test_payload_for_mini_app(self):
        report = self._report({"notes": {"imlo": "Ikki imlo xatosi bor."},
                               "sections": {"kirish": True, "asosiy": True, "xulosa": True}})
        payload = ec.report_payload(report, "uz")
        self.assertEqual(payload["total"], 24)
        self.assertEqual(payload["scale_75"], 75)
        self.assertEqual(payload["percent"], 100)
        self.assertEqual(len(payload["criteria"]), 12)
        self.assertEqual(payload["criteria"][0]["band"], 1)
        self.assertEqual(payload["criteria"][0]["name"], "Publitsistik uslub")
        self.assertEqual(payload["labels"]["total"], "Jami")
        self.assertTrue(payload["sections"]["asosiy"])

    def test_prompt_contains_official_bands_and_topic(self):
        prompt = ec.build_prompt("Matn.", "Mavzu matni")
        self.assertIn("12 ta band", prompt)
        self.assertIn("Mavzu matni", prompt)
        self.assertIn("FAQAT 0, 1 yoki 2 ball", prompt)
        self.assertIn("reja va epigraf yozilmaydi", prompt)

    def test_word_count_keeps_apostrophe_words(self):
        self.assertEqual(ec.word_count("Bir ikki uch, to'rt!"), 4)

    def test_cyrillic_ratio(self):
        self.assertGreater(ec.cyrillic_ratio(CYRILLIC_TEXT), 0.9)
        self.assertEqual(ec.cyrillic_ratio("Salom dunyo"), 0)

    def test_labels_fallback_for_unknown_language(self):
        self.assertEqual(ec.labels("de")["total"], "Total")

    def test_prompt_forbids_copying_the_zero_example(self):
        prompt = ec.build_prompt("Matn.", "Mavzu")
        self.assertIn("nusxa ko'chirmang", prompt)
        self.assertNotIn("QAYTA BAHOLASH", prompt)
        self.assertIn("QAYTA BAHOLASH", ec.build_prompt("Matn.", "Mavzu", retry=True))

    def test_all_zero_answer_is_retried_then_estimated(self):
        calls = []
        zeros = json.dumps({"scores": {key: 0 for key in ec.CRITERIA_KEYS},
                            "sections": {"kirish": False, "asosiy": False, "xulosa": False}})

        async def fake_complete(prompt, **kwargs):
            calls.append(prompt)
            return zeros

        original = ai_api._chat_complete
        ai_api._chat_complete = fake_complete
        try:
            report = asyncio.run(ec.analyze_essay(LONG_TEXT, "uz", "Ta'lim"))
        finally:
            ai_api._chat_complete = original
        self.assertEqual(len(calls), 2)
        self.assertIn("QAYTA BAHOLASH", calls[1])
        self.assertIn("estimated", report["flags"])
        self.assertGreaterEqual(report["total"], 12)
        self.assertGreater(report["scale_75"], 0)
        self.assertIn("taxminiy", ec.format_report(report, "uz"))

    def test_good_first_answer_is_not_retried(self):
        calls = []

        async def fake_complete(prompt, **kwargs):
            calls.append(prompt)
            return json.dumps({"scores": {key: 2 for key in ec.CRITERIA_KEYS},
                               "sections": {"kirish": True, "asosiy": True, "xulosa": True}})

        original = ai_api._chat_complete
        ai_api._chat_complete = fake_complete
        try:
            report = asyncio.run(ec.analyze_essay(LONG_TEXT, "uz", ""))
        finally:
            ai_api._chat_complete = original
        self.assertEqual(len(calls), 1)
        self.assertEqual(report["total"], 24)
        self.assertNotIn("estimated", report["flags"])


if __name__ == "__main__":
    unittest.main()
