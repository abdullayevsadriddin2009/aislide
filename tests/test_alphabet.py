import unittest

from alphabet import slides_to_new_alphabet, to_new_alphabet


class NewAlphabetTest(unittest.TestCase):
    def test_four_letter_pairs(self):
        self.assertEqual(to_new_alphabet("O'zbekiston g'ururi"), "Özbekiston ğururi")
        self.assertEqual(to_new_alphabet("shahar va choy"), "şahar va çoy")

    def test_apostrophe_variants(self):
        for text in ("O'zbek", "O\u2018zbek", "O\u2019zbek", "O\u02bbzbek", "O\u02bczbek"):
            self.assertEqual(to_new_alphabet(text), "Özbek", text)

    def test_capital_digraphs(self):
        self.assertEqual(to_new_alphabet("SH va CH"), "Ş va Ç")
        self.assertEqual(to_new_alphabet("Shahar, Chilonzor"), "Şahar, Çilonzor")

    def test_plain_text_unchanged(self):
        self.assertEqual(to_new_alphabet("salom dunyo"), "salom dunyo")
        self.assertEqual(to_new_alphabet(""), "")

    def test_links_are_not_touched(self):
        text = "Havola: https://shahar.uz/choy va www.chilonzor.uz/sh"
        self.assertEqual(to_new_alphabet(text), text)

    def test_emails_are_not_touched(self):
        text = "Yozing: shahar.choy@checker.uz yoki ch@mail.ru"
        self.assertEqual(to_new_alphabet(text), text)

    def test_text_around_a_link_is_converted(self):
        result = to_new_alphabet("shahar https://shahar.uz/choy choy")
        self.assertEqual(result, "şahar https://shahar.uz/choy çoy")

    def test_slide_structure(self):
        slides = [{"title": "O'zbek tili", "content": ["g'oya", "chora"]}]
        result = slides_to_new_alphabet(slides)
        self.assertEqual(result[0]["title"], "Özbek tili")
        self.assertEqual(result[0]["content"], ["ğoya", "çora"])


if __name__ == "__main__":
    unittest.main()
