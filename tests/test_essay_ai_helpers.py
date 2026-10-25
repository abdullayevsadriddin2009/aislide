"""Offline checks for the essay content quality guards."""
import unittest

import ai_api


class EssayAIHelperTests(unittest.TestCase):
    def test_fallback_outline_has_five_items_in_uzbek(self):
        outline = ai_api._fallback_essay_outline("Amir Temur", "uz")
        self.assertEqual(len([x for x in outline.splitlines() if x.strip()]), 5)
        self.assertIn("Kirish:", outline)
        self.assertIn("Xulosa:", outline)

    def test_garbled_repetitive_text_is_rejected(self):
        draft = ("Amir Temurin kirgizlar va sog'liqlar va tizim va tengiz qo'shilgan kuni tug'iladi. ") * 8
        self.assertTrue(ai_api._essay_text_is_suspicious(draft, "uz", 120))

    def test_normal_uzbek_text_is_not_rejected(self):
        draft = (
            "Amir Temur XIV asrda Movarounnahrda kuchli markazlashgan davlat barpo etgan hukmdor "
            "va sarkarda sifatida tarixda muhim o‘rin egallaydi. Uning faoliyati davlat boshqaruvi, "
            "harbiy strategiya va madaniy hayot bilan bog‘liq."
        )
        self.assertFalse(ai_api._essay_text_is_suspicious(draft, "uz", 40))


if __name__ == "__main__":
    unittest.main()
