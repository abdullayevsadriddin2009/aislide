"""Dizaynli PPTX -> PDF: slaydlar soni va sahifa o'lchami saqlanishi."""
import io
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pdf_fallback
import pptx_generator


def _deck(lang="ru", design="modern", count=5):
    content = [
        {"title": "Создание клуба-музея в Ташкенте",
         "content": ["Клуб-музей открылся в 2023 году в историческом центре Ташкента.",
                     "В его стенах размещено 150 экспонатов.",
                     "Экспозиция привлекает около 10 000 посетителей ежегодно."]},
        {"title": "Экспозиция «Реквием»",
         "content": ["Полная копия поэмы 1934-1943 годов.",
                     "Рукописные листы и редкие издания."]},
    ]
    buf = pptx_generator.generate_pptx("Клуб-музей Анны Ахматовой", "Общая тема", lang,
                                       design, count, content)
    return buf.getvalue()


class PdfDesignTest(unittest.TestCase):
    def test_designed_pdf_keeps_every_slide(self):
        pdf = pdf_fallback.to_pdf(_deck(count=5), "pptx", "Клуб-музей Анны Ахматовой")
        self.assertTrue(pdf and pdf.startswith(b"%PDF"))
        pages = len(re.findall(rb"/Type\s*/Page[^s]", pdf))
        self.assertEqual(pages, 5)

    def test_pptx_to_pdf_reports_landscape_pages(self):
        pdf = pdf_fallback.pptx_to_pdf(_deck(count=4), "Taqdimot")
        self.assertTrue(pdf)
        media = re.findall(rb"/MediaBox\s*\[([^\]]+)\]", pdf)
        self.assertTrue(media)
        box = [float(value) for value in media[0].split()]
        width, height = box[2] - box[0], box[3] - box[1]
        self.assertGreater(width, height)

    def test_broken_pptx_returns_nothing(self):
        self.assertIsNone(pdf_fallback.pptx_to_pdf(b"not a presentation", "x"))


if __name__ == "__main__":
    unittest.main()
