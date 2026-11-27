"""The reference lookup must work in every language and for long topics.

Regression tests for the two ways a deck used to lose its source: a descriptive
topic (ten words, no article of that name) was rejected outright, and a Latin
name was never matched against a Cyrillic article. Photo lookup rides on the same
resolution, so a topic without a resolvable article had no pictures either.
"""
import io
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from PIL import Image
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

import ai_api
import wiki_source
from designs import DESIGN_KEYS
from pptx_generator import generate_pptx

LONG_TOPIC = ("O'zbekistonda ta'lim tizimining rivojlanishi va uning bugungi "
              "kundagi ahamiyati")


class TitleMatchTest(unittest.TestCase):
    def test_long_topic_finds_its_own_key_phrase(self):
        self.assertGreaterEqual(
            wiki_source.title_score("O'zbekistonda ta'lim", "Oʻzbekistonda taʼlim"), 0.9)
        self.assertGreaterEqual(
            wiki_source.title_score(LONG_TOPIC, "Oʻzbekistonda taʼlim"), 0.5)

    def test_unrelated_article_is_never_the_subject(self):
        self.assertEqual(wiki_source.title_score(LONG_TOPIC, "Yasli-bogʻcha"), 0.0)
        self.assertEqual(wiki_source.title_score("Fotosintez", "Grape cells"), 0.0)

    def test_a_named_work_is_not_the_subject(self):
        self.assertTrue(wiki_source._noise_title("Biologiya (albom)", "biologiya"))
        self.assertFalse(wiki_source._noise_title("Fotosintez", "fotosintez"))

    def test_topic_suffix_forms_still_match(self):
        # "sog'liqni saqlash tizimi" must reach the exact article, not a country one.
        exact = wiki_source.title_score("sog'liqni saqlash tizimi", "Sogʻliqni saqlash tizimi")
        other = wiki_source.title_score("sog'liqni saqlash tizimi", "Eron sogʻliqni saqlash tizimi")
        self.assertGreater(exact, other)


class QueryBuildingTest(unittest.TestCase):
    def test_long_topic_is_searched_through_its_own_words(self):
        queries = wiki_source.short_queries(
            "O'zbekistonda ta'lim tizimining rivojlanishi")
        self.assertIn("O'zbekistonda ta'lim", queries)
        self.assertTrue(all(query.strip() for query in queries))

    def test_latin_name_is_also_searched_in_cyrillic(self):
        # Translation is not needed for a name: the letters are transliterated.
        variants = wiki_source.cyrillic_variants("Axmatova muzeyi")
        self.assertIn("ахматова музейи", variants)
        # The Uzbek possessive ending is dropped for the Russian search too:
        # "ахматова музей" is the phrase that finds the museum article.
        self.assertIn("ахматова музей", variants)

    def test_topic_words_keep_their_apostrophe(self):
        self.assertIn("o'zbekistonda", ai_api._keyword_words("O'zbekistonda ta'lim"))
        self.assertNotIn("zbekistonda", ai_api._keyword_words("O'zbekistonda ta'lim"))


class WikipediaFetchTest(unittest.IsolatedAsyncioTestCase):
    async def test_resolved_article_is_returned(self):
        page = {"found": True, "lang": "ru", "title": "Музей Анны Ахматовой",
                "text": "Музей открылся в 1989 году." * 10, "image": "", "url": "u",
                "qid": "", "source": "wikipedia"}
        with patch.object(wiki_source, "fetch", new=AsyncMock(return_value=page)):
            got = await ai_api.wikipedia_fetch("Axmatova muzeyi", gen_lang="ru")
        self.assertTrue(got["found"])
        self.assertEqual(got["title"], "Музей Анны Ахматовой")
        self.assertEqual(got["lang"], "ru")

    async def test_missing_article_is_reported_not_invented(self):
        with patch.object(wiki_source, "fetch", new=AsyncMock(return_value={})), \
                patch.object(ai_api, "_wikipedia_related", new=AsyncMock(return_value={})):
            got = await ai_api.wikipedia_fetch("ba'zi bir mavzu", gen_lang="uz")
        self.assertFalse(got["found"])
        self.assertEqual(got["text"], "")


class WikipediaSourceTest(unittest.IsolatedAsyncioTestCase):
    async def test_deck_language_article_replaces_the_foreign_one(self):
        resolved = {"lang": "uz", "title": "Fotosintez", "score": 100}
        original = {"found": True, "lang": "uz", "title": "Fotosintez", "qid": "Q11982",
                    "text": "uz matn", "image": "", "url": "u"}
        upgraded = {"found": True, "lang": "en", "title": "Photosynthesis", "qid": "Q11982",
                    "text": "english text", "image": "", "url": "u2"}
        with patch.object(wiki_source, "resolve", new=AsyncMock(return_value=resolved)), \
                patch.object(wiki_source, "extract", new=AsyncMock(return_value=original)), \
                patch.object(wiki_source, "extract_for_item", new=AsyncMock(return_value=upgraded)):
            page = await wiki_source.fetch("Fotosintez", ["en", "uz"], "en")
        self.assertEqual(page["lang"], "en")
        self.assertEqual(page["title"], "Photosynthesis")

    async def test_wikidata_entity_is_the_second_source(self):
        entity = {"found": True, "lang": "uz", "title": "Mavzu",
                  "text": "matn" * 60, "image": "", "url": "u", "source": "wikidata"}
        with patch.object(wiki_source, "resolve", new=AsyncMock(return_value={})), \
                patch.object(wiki_source, "entity_source", new=AsyncMock(return_value=entity)):
            page = await wiki_source.fetch("noma'lum mavzu", ["uz"], "uz")
        self.assertEqual(page["source"], "wikidata")


class DesignImageTest(unittest.TestCase):
    def test_every_design_shows_the_topic_photos(self):
        folder = tempfile.mkdtemp()
        paths = []
        for index in range(3):
            path = os.path.join(folder, f"photo_{index}.jpg")
            Image.new("RGB", (1600, 900), (24 + index * 30, 64, 96)).save(path)
            paths.append(path)
        slides = [{"title": f"Bo'lim {index + 1}",
                   "content": ["Gap bir.", "Gap ikki.", "Gap uch.", "Gap to'rt.", "Gap besh."]}
                  for index in range(4)]
        for key in DESIGN_KEYS:
            buf = generate_pptx(topic="Sog'liqni saqlash", subject="Tibbiyot", lang="uz",
                                design_key=key, slide_count=6, slides_content=slides,
                                images=paths)
            deck = Presentation(io.BytesIO(buf.read()))
            pictures = sum(1 for slide in deck.slides for shape in slide.shapes
                           if shape.shape_type == MSO_SHAPE_TYPE.PICTURE)
            self.assertEqual(len(deck.slides), 6, key)
            self.assertGreaterEqual(pictures, 3, f"{key} design dropped the photos")


if __name__ == "__main__":
    unittest.main()
