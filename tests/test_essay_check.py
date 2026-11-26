import asyncio
import io
import json
import time
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
        # Baholanmagan band 0 emas, o'rtacha 1 ball oladi.
        self.assertEqual(scores["soz"], 1)

    def test_criteria_with_other_names_are_counted(self):
        # AI bandni «qo'shimchalar», «punktuatsiya», «adabiy til» deb yozsa ham
        # hisobotda o'sha band baholangan bo'lishi kerak — 0 ga tushmasin.
        scores = ec.band_scores({"Uslub": 2, "qo'shimchalar": 1, "so'z qo'llash": 2,
                                 "punktuatsiya": 1, "orfografiya": 2, "adabiy til": 2,
                                 "tuzilma": 2, "mazmuniy izchillik": 2})
        self.assertEqual(scores["uslub"], 2)
        self.assertEqual(scores["qoshimchalar"], 1)
        self.assertEqual(scores["soz"], 2)
        self.assertEqual(scores["tinish"], 1)
        self.assertEqual(scores["imlo"], 2)
        self.assertEqual(scores["adabiy"], 2)
        self.assertEqual(scores["qismlar"], 2)
        self.assertEqual(scores["izchillik"], 2)
        self.assertEqual(scores["dalillar"], 1)

    def test_notes_with_other_names_are_kept(self):
        data = {"scores": {key: 1 for key in ec.CRITERIA_KEYS},
                "notes": {"qo'shimchalar": "«bormoqda» so'zida qo'shimcha noto'g'ri."}}
        report = ec.normalize_report(data, LONG_TEXT, "uz")
        self.assertIn("bormoqda", report["notes"]["qoshimchalar"])

    def test_missing_criteria_are_filled_not_scored_zero(self):
        data = {"scores": {"uslub": 2, "qarashlar": 2}}
        report = ec.normalize_report(data, LONG_TEXT, "uz")
        self.assertEqual(len(report["scores"]), 12)
        for key in ec.CRITERIA_KEYS:
            self.assertGreaterEqual(report["scores"][key], 1)
        self.assertEqual(report["missing_criteria"],
                         [key for key in ec.CRITERIA_KEYS if key not in ("uslub", "qarashlar")])
        self.assertIn("estimated", report["flags"])
        self.assertEqual(len(ec.criteria_payload(report, "uz")), 12)

    def test_report_lists_all_twelve_criteria(self):
        body = ec.format_report(self._report(), "uz")
        crit = ec.labels("uz")["crit"]
        for band, key in enumerate(ec.CRITERIA_KEYS, 1):
            self.assertIn(f"{band}. {crit[key]} — 2/2", body)

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
        text = ("Insho mavzusida ta'lim tizimi haqida yozildi. "
                "Universitetlari bugun keng imkoniyat yaratmoqda. ") * 8
        report = self._report({"errors": [
            {"quote": "Insho", "fix": "Insho", "type": "imlo"},
            {"quote": "universitetlari", "fix": "universitetlari → universitetlari",
             "type": "imlo"},
            {"quote": "ta'lim", "fix": "to'g'ri yozilishi kerak", "type": "imlo"},
            {"quote": "universitetlari", "fix": "universitetlarida", "type": "imlo"},
        ]}, text=text)
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
        report = self._report({"errors": [{"quote": "taraqqiyotining", "fix": "taraqqiyotning",
                                            "type": "imlo", "rule": "imlo qoidasi"}],
                               "review": "Yaxshi ish."})
        text = ec.format_report(report, "uz")
        self.assertIn("24/24 ball (100%)", text)
        self.assertIn("7. Imlo — 2/2", text)
        self.assertIn("12. Adabiy til me'yorlari — 2/2", text)
        self.assertIn("taraqqiyotining", text)
        self.assertNotIn("<", text)

    def test_report_shows_scale_and_structure(self):
        report = self._report({"sections": {"kirish": True, "asosiy": True, "xulosa": False}})
        body = ec.format_report(report, "uz")
        self.assertIn("75 ballik shkala: 75/75", body)
        self.assertIn("Tuzilma", body)
        self.assertIn("Xulosa ❌", body)

    def test_errors_are_capped_at_twenty(self):
        errors = [{"quote": f"xato {i}", "fix": "to'g'ri", "type": "imlo"} for i in range(30)]
        report = self._report({"errors": errors},
                              text=" ".join(f"xato {i}" for i in range(30)))
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

    def test_ocr_line_breaks_are_joined(self):
        raw = "Yangi Oʻzbe-\nkiston nashri, maʼlumot-\nlariga ko'ra"
        self.assertEqual(ec.clean_ocr_text(raw),
                         "Yangi Oʻzbekiston nashri, maʼlumotlariga ko'ra")
        # Raqamlar orasidagi chiziqcha (yil oralig'i) tegilmaydi.
        self.assertEqual(ec.clean_ocr_text("2020-\n2021 yil"), "2020-\n2021 yil")

    def test_handwriting_report_does_not_zero_bands_without_errors(self):
        """Qo'lyozmada AI xato ko'rsatmasa, imlo/tinish kabi bandlar 0 bo'lmasin."""
        scores = {"uslub": 1, "qarashlar": 2, "dalillar": 1, "qismlar": 1,
                  "mantiq": 0, "izchillik": 0, "imlo": 0, "tinish": 0,
                  "qoshimchalar": 0, "soz": 0, "paremiya": 0, "adabiy": 0}
        data = {"scores": scores,
                "sections": {"kirish": True, "asosiy": True, "xulosa": True},
                "errors": [{"quote": "tizimi", "fix": "tizim", "type": "imlo"}]}
        image = ec.normalize_report(data, LONG_TEXT, "uz", "AI", from_image=True)
        self.assertEqual(image["scores"]["imlo"], 0)      # xatosi ko'rsatilgan
        self.assertEqual(image["scores"]["tinish"], 2)    # xato ko'rsatilmagan
        self.assertEqual(image["scores"]["paremiya"], 2)  # dalilsiz tushirilmaydi
        self.assertGreater(image["total"], 5)
        # Matn faylida bunday yumshoq tuzatish yo'q.
        plain = ec.normalize_report(data, LONG_TEXT, "uz", "AI")
        self.assertEqual(plain["scores"]["tinish"], 0)

    def test_structure_is_detected_from_the_text_not_from_ai(self):
        """Uch xatboshli esse «kirish/asosiy/xulosa yo'q» bo'lib qolmasin."""
        body = ("Bugungi kunda avtomobil importi masalasi dolzarb bo'lib qoldi va "
                "bu haqda ko'p yozilmoqda. Chet el mashinalari sifat va "
                "texnologiya bilan ajralib turadi. ")
        last = ("Xulosa qilib aytganda, ikkala yondashuv ham muhim va muvozanat "
                "kerak. Shu bois mahalliy sanoatni qo'llab-quvvatlash lozim. ")
        text = body * 2 + "\n\n" + body * 2 + "\n\n" + last * 2
        data = {"scores": {key: 1 for key in ec.CRITERIA_KEYS},
                "sections": {"kirish": False, "asosiy": False, "xulosa": False}}
        report = ec.normalize_report(data, text, "uz")
        self.assertTrue(all(report["sections"].values()))
        self.assertEqual(report["scores"]["qismlar"], 2)
        self.assertNotIn("notask", report["flags"])

    def test_error_quote_missing_from_text_is_dropped(self):
        """OCR xatosi/to'qib chiqarilgan so'z «xato» sifatida hisoblanmasin."""
        data = {"scores": {key: 1 for key in ec.CRITERIA_KEYS},
                "errors": [{"quote": "xamonaviy", "fix": "zamonaviy", "type": "imlo"},
                           {"quote": "tizimi", "fix": "tizim", "type": "imlo"}]}
        report = ec.normalize_report(data, LONG_TEXT, "uz")
        self.assertEqual(len(report["errors"]), 1)
        self.assertEqual(report["errors"][0]["quote"], "tizimi")

    def test_line_break_hyphen_is_not_a_punctuation_error(self):
        """«standart--larga» — qator oxiridagi ko'chirish chizig'i, tinish xatosi emas."""
        data = {"scores": {key: 2 for key in ec.CRITERIA_KEYS},
                "errors": [{"quote": "standart--larga", "fix": "standartlarga",
                            "type": "tinish"}]}
        report = ec.normalize_report(data, LONG_TEXT, "uz")
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["scores"]["tinish"], 2)

    def test_bands_lowered_without_quoted_defect_are_not_lowered(self):
        """Umumiy gap («ba'zi joylarda...») bilan band tushirilmaydi."""
        scores = {key: 2 for key in ec.CRITERIA_KEYS}
        scores.update({"uslub": 1, "izchillik": 1})
        data = {"scores": scores,
                "notes": {"uslub": "Matn uslubga yaqin, lekin ba'zi joylarda "
                                   "chetga chiqadi",
                          "izchillik": "Mavzular takrorlanadi, izchil oqim yo'q"}}
        report = ec.normalize_report(data, LONG_TEXT, "uz")
        self.assertEqual(report["scores"]["uslub"], 2)
        self.assertEqual(report["scores"]["izchillik"], 2)
        self.assertEqual(report["notes"]["uslub"], "")

    def test_repetition_claim_with_a_single_occurrence_is_ignored(self):
        # AI «takrorlanadi» deb bir marta uchraydigan jumlani keltirsa, bu
        # tasdiqlangan kamchilik emas.
        scores = {key: 2 for key in ec.CRITERIA_KEYS}
        scores["mantiq"] = 1
        text = LONG_TEXT + " Mening fikrimcha, bu masala jiddiy o'rganishni talab qiladi."
        data = {"scores": scores,
                "notes": {"mantiq": "Ba'zi jumlalar takrorlanadi "
                                    "(«Mening fikrimcha, bu masala jiddiy»)"}}
        report = ec.normalize_report(data, text, "uz")
        self.assertEqual(report["scores"]["mantiq"], 2)

    def test_quoted_defect_still_lowers_the_band(self):
        scores = {key: 2 for key in ec.CRITERIA_KEYS}
        scores["izchillik"] = 1
        data = {"scores": scores,
                "notes": {"izchillik": "«Bugungi kunda ta'lim tizimi» fikri har "
                                       "gapda takrorlangan"}}
        report = ec.normalize_report(data, LONG_TEXT, "uz")
        self.assertEqual(report["scores"]["izchillik"], 1)

    def test_paremiya_and_dalillar_are_not_lowered_for_missing_extras(self):
        """Maqol va statistika talab qilinmaydi: shu sabab bilan ball tushmaydi."""
        scores = {key: 2 for key in ec.CRITERIA_KEYS}
        scores.update({"paremiya": 1, "dalillar": 1})
        data = {"scores": scores,
                "notes": {"paremiya": "Atamalar bor, lekin aniq maqol yoki paremiya yo'q",
                          "dalillar": "Misollar bor, lekin aniq statistik ma'lumot yetarli emas"}}
        report = ec.normalize_report(data, LONG_TEXT, "uz")
        self.assertEqual(report["scores"]["paremiya"], 2)
        self.assertEqual(report["scores"]["dalillar"], 2)

    def test_missing_plan_is_not_reported_as_a_defect(self):
        data = {"scores": {key: 1 for key in ec.CRITERIA_KEYS},
                "notes": {"qismlar": "Kirish va xulosa yetarli emas; reja yoki "
                                     "epigraf ham yo'q."}}
        report = ec.normalize_report(data, LONG_TEXT, "uz")
        self.assertNotIn("reja", report["notes"]["qismlar"].lower())
        self.assertIn("Kirish", report["notes"]["qismlar"])

    def test_quota_window_separates_minute_and_daily_limits(self):
        row = {"name": "Google AI 1"}
        ec._VISION_SKIP.clear()
        ec._vision_fail(row, "m1", 429, "quota exceeded ... requests per minute")
        ec._vision_fail(row, "m2", 429, "quota exceeded ... requests per day")
        minute = ec._VISION_SKIP[ec._vision_key(row, "m1")][0] - time.time()
        daily = ec._VISION_SKIP[ec._vision_key(row, "m2")][0] - time.time()
        self.assertLess(minute, 300)
        self.assertGreater(daily, 1500)
        ec._VISION_SKIP.clear()

    def test_prompt_forbids_copying_the_zero_example(self):
        prompt = ec.build_prompt("Matn.", "Mavzu")
        self.assertIn("nusxa ko'chirmang", prompt)
        self.assertNotIn("QAYTA BAHOLASH", prompt)
        self.assertIn("QAYTA BAHOLASH", ec.build_prompt("Matn.", "Mavzu", retry=True))

    def test_all_zero_answer_is_retried_then_not_graded(self):
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
        self.assertTrue(report["not_graded"])
        self.assertEqual(report["reason"], "no_scores")
        # Yaroqli essega yolg'on ball qo'yilmaydi.
        self.assertNotIn("total", report)
        message = ec.format_report(report, "uz")
        self.assertIn("Baholab bo'lmadi", message)
        self.assertNotIn("/24", message)

    def test_ai_outage_returns_honest_not_graded_message(self):
        async def fake_complete(prompt, **kwargs):
            return ""

        original = ai_api._chat_complete
        ai_api._chat_complete = fake_complete
        try:
            report = asyncio.run(ec.analyze_essay(LONG_TEXT, "uz", "Ta'lim"))
        finally:
            ai_api._chat_complete = original
        self.assertTrue(report["not_graded"])
        self.assertEqual(report["reason"], "unavailable")
        self.assertEqual(report["word_count"], ec.word_count(LONG_TEXT))
        self.assertIn("Qayta tekshirish", ec.format_report(report, "uz"))
        self.assertEqual(ec.report_payload(report, "uz")["not_graded"], True)

    def test_incomplete_answer_is_asked_again(self):
        calls = []
        partial = json.dumps({"scores": {"uslub": 2, "qarashlar": 2},
                              "sections": {"kirish": True, "asosiy": True, "xulosa": True}})
        full = json.dumps({"scores": {key: 2 for key in ec.CRITERIA_KEYS},
                           "sections": {"kirish": True, "asosiy": True, "xulosa": True}})

        async def fake_complete(prompt, **kwargs):
            calls.append(prompt)
            return partial if len(calls) == 1 else full

        original = ai_api._chat_complete
        ai_api._chat_complete = fake_complete
        try:
            report = asyncio.run(ec.analyze_essay(LONG_TEXT, "uz", ""))
        finally:
            ai_api._chat_complete = original
        self.assertEqual(len(calls), 2)
        self.assertIn("QAYTA BAHOLASH", calls[1])
        self.assertEqual(report["missing_criteria"], [])
        self.assertEqual(report["total"], 24)

    def test_correction_with_foreign_letters_is_not_a_spelling_error(self):
        # «enagalar» to'g'ri yozilgan; AI uni «enağalar» ga «tuzatgan». O'zbek
        # lotin alifbosida ğ yo'q — bu imlo xatosi emas.
        data = {"scores": {key: 1 for key in ec.CRITERIA_KEYS},
                "errors": [{"quote": "enagalar", "fix": "enağalar", "type": "imlo"},
                           {"quote": "enapalar", "fix": "enağalar", "type": "imlo"}]}
        report = ec.normalize_report(data, LONG_TEXT + " enagalar", "uz", "",
                                     from_image=True)
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["scores"]["imlo"], 2)

    def test_self_cancelling_spelling_claim_is_removed_from_the_note(self):
        data = {"scores": {key: 2 for key in ec.CRITERIA_KEYS},
                "notes": {"qoshimchalar": "Qo'shimcha xatolari: «azosi» o'rniga «azosi», "
                                          "«tazieyqqa» → «tazyiqqa»."}}
        report = ec.normalize_report(data, "azosi tazieyqqa", "uz")
        self.assertNotIn("azosi", report["notes"]["qoshimchalar"])
        self.assertIn("tazyiqqa", report["notes"]["qoshimchalar"])

    def test_pasted_paragraphs_with_indentation_are_detected(self):
        # Telegramdan ko'chirilganda xatboshilar bo'sh qator bilan emas, faqat
        # chekinish bilan boshlanadi — esse bitta xatbosh bo'lib qolmasin.
        body = ("Bugungi kunda oila tinchligi jamiyat taraqqiyotining asosidir va bu "
                "haqda ko'p yozilmoqda, biroq ba'zi xonadonlarda o'zaro "
                "kelishmovchiliklar hamon kuzatilmoqda. Ayrimlar turmush o'rtog'i "
                "bilan kelishmovchilik chiqsa davlat organlariga murojaat qilish "
                "tarafdori, boshqalar esa masalani o'zlari hal qilishni ma'qul "
                "ko'radilar. ")
        second = ("     Avvalo, juft halol bilan tortishuvlar bo'lganida mahalla va "
                  "ichki ishlarga murojaat qilish tarafdorlari fikriga to'xtalsak, "
                  "chunki kichik urushlar jiddiylashib ketishi mumkin. Masalan, "
                  "jismoniy zo'ravonlikka uchragan ayollar ham afsuski bor. ")
        third = ("     Endi oilaviy muammolarni uyda hal qilish tarafdorlari "
                 "qarashiga e'tibor qaratsak, har bir a'zoning xavfsizligini "
                 "o'zlari himoya qilishi kerak, deb hisoblaydilar. Uydagi gap "
                 "ko'chaga chiqsa, na uyning fayzi qoladi, na insonning qadri. ")
        last = ("     Xulosa qilib aytganda, oilaning tinchligi muhim, shuning "
                "uchun ham bir-birini tushunib yashash lozim, shundagina tinch va "
                "bunyodkor oila hosil bo'ladi. ")
        text = body + "\n" + second + "\n" + third + "\n" + last
        data = {"scores": {key: 1 for key in ec.CRITERIA_KEYS},
                "sections": {"kirish": True, "asosiy": False, "xulosa": True}}
        report = ec.normalize_report(data, text, "uz")
        self.assertGreaterEqual(ec.word_count(text), ec.MIN_WORDS)
        self.assertTrue(report["sections"]["asosiy"])
        self.assertEqual(report["scores"]["qismlar"], 2)

    def test_two_sided_views_with_personal_opinion_get_two_points(self):
        text = LONG_TEXT + " Mening fikrimcha, bu masala jiddiy o'rganishni talab qiladi."
        scores = {key: 2 for key in ec.CRITERIA_KEYS}
        scores["qarashlar"] = 1
        data = {"scores": scores,
                "notes": {"qarashlar": "Ikkala qarash keltirilgan, lekin shaxsiy fikr "
                                       "aniq ajratilmagan"}}
        report = ec.normalize_report(data, text, "uz")
        self.assertEqual(report["scores"]["qarashlar"], 2)
        self.assertEqual(report["notes"]["qarashlar"], "")

    def test_missing_sources_is_not_a_reason_to_lower_evidence(self):
        scores = {key: 2 for key in ec.CRITERIA_KEYS}
        scores["dalillar"] = 1
        data = {"scores": scores,
                "notes": {"dalillar": "Statistik ma'lumotlar «2024-yilda ajrashgan "
                                      "oilalar soni ortgan» keltirilgan, lekin manbalar "
                                      "ko'rsatilmagan"}}
        text = LONG_TEXT + " 2024-yilda ajrashgan oilalar soni ortgan."
        report = ec.normalize_report(data, text, "uz")
        self.assertEqual(report["scores"]["dalillar"], 2)

    def test_partly_quoted_proverb_still_earns_the_band(self):
        scores = {key: 2 for key in ec.CRITERIA_KEYS}
        scores["paremiya"] = 1
        data = {"scores": scores,
                "notes": {"paremiya": "Matnda maqol mavjud: «Oila bu muqaddas dargoh» "
                                      "lekin u to'liq va aniq ifodalangan emas"}}
        text = LONG_TEXT + " Oila bu muqaddas dargoh."
        report = ec.normalize_report(data, text, "uz")
        self.assertEqual(report["scores"]["paremiya"], 2)

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
        self.assertFalse(report.get("not_graded"))


if __name__ == "__main__":
    unittest.main()
