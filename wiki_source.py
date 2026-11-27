"""Encyclopedic reference lookup for generated decks and documents.

The topic arrives in whatever language and length the user typed it:

* ``Fotosintez`` — one word, Uzbek;
* ``O'zbekistonda ta'lim tizimining rivojlanishi va uning bugungi kundagi
  ahamiyati`` — a whole descriptive phrase with no article of that name;
* ``Axmatova muzeyi`` — a Latin-script name in a Russian deck;
* ``The role of artificial intelligence in modern medicine`` — English.

A presentation still needs verifiable facts, so this module resolves that text to
the exact article instead of giving up: the phrase's own key words are searched,
a Latin name is also tried in Cyrillic, and the Wikidata item bridges spellings
and languages. When no full-text search reaches an article, the entity itself is
looked up on Wikidata and its article is read in the deck's language — a second
source instead of no source.
"""
import asyncio
import re
import time
from urllib.parse import quote

import aiohttp

USER_AGENT = ("TalabaAISlideBot/1.0 (educational presentation image retrieval; "
              "https://github.com/abdullayevsadriddin2009/aislide)")
WIKI_API = "https://{lang}.wikipedia.org/w/api.php"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
SITES = {"uz": "uzwiki", "ru": "ruwiki", "en": "enwiki", "tr": "trwiki",
         "de": "dewiki", "fr": "frwiki"}
APOSTROPHES = ("\u02bb", "\u02bc", "\u2018", "\u2019", "`", "\u00b4")

# Function words carry no subject, so they neither build a query nor count when
# an article title is compared with the topic.
STOPWORDS = {
    "the", "and", "for", "with", "in", "on", "to", "of", "a", "an", "its", "from",
    "role", "about", "into", "their", "this", "that", "these", "those",
    "va", "bu", "uchun", "bilan", "ning", "ham", "esa", "kabi", "orqali",
    "и", "в", "на", "по", "о", "об", "для", "как", "это", "с", "к", "у", "из",
    "ve", "ile", "için", "bir", "der", "die", "das", "und", "für", "mit",
    "le", "la", "les", "et", "de", "des", "pour", "avec",
}

# Titles that are a different kind of work with the same name. They are skipped
# unless the topic itself asks for them ("biologiya" is not the album).
_NOISE = ("(album)", "(albom)", "(film)", "(filmi)", "(song)", "(qo'shiq)",
          "(band)", "(novel)", "(disambiguation)", "(альбом)", "(фильм)",
          "дизамбиг")

_CYR_DIGRAPHS = (("shch", "щ"), ("sh", "ш"), ("ch", "ч"), ("yo", "ё"), ("yu", "ю"),
                 ("ya", "я"), ("ts", "ц"), ("kh", "х"), ("o'", "о"), ("g'", "г"))
_CYR_LETTERS = {"a": "а", "b": "б", "c": "к", "d": "д", "e": "е", "f": "ф",
                "g": "г", "h": "х", "i": "и", "j": "ж", "k": "к", "l": "л",
                "m": "м", "n": "н", "o": "о", "p": "п", "q": "к", "r": "р",
                "s": "с", "t": "т", "u": "у", "v": "в", "w": "в", "x": "х",
                "y": "й", "z": "з"}
_UZ_SUFFIXES = ("larining", "laridan", "lariga", "larning", "larini", "larda",
                "larga", "lardan", "ning", "dagi", "dan", "lar", "ga", "da",
                "ni", "si", "i")

_MISS_TTL = 600
_RESOLVE_CACHE: dict[tuple, tuple[dict, float]] = {}
_EXTRACT_CACHE: dict[tuple, dict] = {}
_SITELINK_CACHE: dict[str, dict] = {}
_LIMITS: dict = {}


def _limit():
    """One semaphore per event loop.

    The Mini App generates in worker threads, so several event loops live in the
    same process; a single module-level semaphore would bind to the first loop.
    """
    loop = asyncio.get_running_loop()
    semaphore = _LIMITS.get(loop)
    if semaphore is None:
        semaphore = _LIMITS[loop] = asyncio.Semaphore(4)
    return semaphore


# ---------------------------------------------------------------- text helpers
def normalize(value):
    text = str(value or "")
    for mark in APOSTROPHES:
        text = text.replace(mark, "'")
    return re.sub(r"\s+", " ", text).strip()


def fold(value):
    """Apostrophe-free, casefolded form: ``Oʻzbekiston`` == ``O'zbekiston``."""
    return re.sub(r"\s+", " ", normalize(value).replace("'", "")).strip().casefold()


def tokens(value):
    """Comparable words only: no punctuation, no apostrophes, no short words."""
    return re.findall(r"[^\W\d_]{2,}", fold(value))


def words(value):
    """The user's own words, apostrophes kept, so a query still reads naturally."""
    return re.findall(r"[^\W\d_][\w'\-]*", normalize(value))


def _content(values):
    kept = [word for word in values if word.casefold() not in STOPWORDS]
    return kept or list(values)


def to_cyrillic(value):
    """Latin name in Cyrillic, for a ru.wikipedia search.

    ``Axmatova`` becomes ``Ахматова``; apostrophes are dropped because Russian
    spelling has no equivalent for the Uzbek marks.
    """
    text = re.sub(r"['\u2019\u02bb\u02bc]", "", normalize(value)).casefold()
    out, index = [], 0
    while index < len(text):
        for source, target in _CYR_DIGRAPHS:
            if text.startswith(source, index):
                out.append(target)
                index += len(source)
                break
        else:
            out.append(_CYR_LETTERS.get(text[index], text[index]))
            index += 1
    return "".join(out)


def stem_word(word):
    """Drop a common Uzbek ending: ``muzeyi`` -> ``muzey``, ``ta'limi`` -> ``ta'lim``."""
    low = word.casefold()
    for suffix in _UZ_SUFFIXES:
        if len(low) > len(suffix) + 3 and low.endswith(suffix):
            return word[: len(word) - len(suffix)]
    return word


def cyrillic_variants(phrase):
    if not re.search(r"[A-Za-z]", str(phrase or "")):
        return []
    out = []
    for variant in (phrase, " ".join(stem_word(word) for word in words(phrase))):
        cyr = to_cyrillic(variant)
        if re.search(r"[А-Яа-яЁё]", cyr) and cyr not in out:
            out.append(cyr)
    return out


def short_queries(phrase, limit=4):
    """Key phrases built from the topic's own words, in their original order.

    A twenty-word topic has no article of that name, but its own pairs do:
    ``O'zbekistonda ta'lim tizimining rivojlanishi`` reaches
    ``Oʻzbekistonda taʼlim``. Nothing is translated or invented here.
    """
    kept = _content(words(phrase))
    if len(kept) < 3:
        return []
    out = []
    if len(kept) >= 4:
        out.append(" ".join(kept[:3]))
    for index in range(len(kept) - 1):
        out.append(f"{kept[index]} {kept[index + 1]}")
    unique = []
    for query in out:
        if query.casefold() not in {item.casefold() for item in unique}:
            unique.append(query)
    return unique[:limit]


def title_score(query, title):
    """How much of the searched phrase an article title actually covers."""
    needle = _content(tokens(query))
    haystack = _content(tokens(title))
    if not needle or not haystack:
        return 0.0

    def hit(word, pool):
        if word in pool:
            return True
        if len(word) < 5:
            return False
        head = word[: max(4, len(word) - 2)]
        for other in pool:
            if other.startswith(head):
                return True
            if len(other) >= 5 and word.startswith(other[: max(4, len(other) - 2)]):
                return True
        return False

    covered = sum(1 for word in needle if hit(word, haystack)) / len(needle)
    precise = sum(1 for word in haystack if hit(word, needle)) / len(haystack)
    # Precision is weighted higher: the article's title should not wander off into
    # another subject ("Орден Отечественной войны" for a question about the war),
    # while coverage keeps the topic's own words in the answer.
    return 0.65 * precise + 0.35 * covered


def _accepted(score, query):
    # A title that shares nothing with the searched phrase is never the subject.
    return score >= 0.5


def _noise_title(title, query):
    low = fold(title)
    asked = fold(query)
    for noise in _NOISE:
        if fold(noise) in low and fold(noise) not in asked:
            return True
    return False


# ------------------------------------------------------------------- requests
async def _get(session, url, params):
    # Wikimedia answers 429 when a deck asks for many titles at once; one short
    # pause turns that into the real answer instead of "no article found".
    for attempt in range(2):
        try:
            async with session.get(url, params=params) as resp:
                if resp.status in (429, 500, 502, 503, 504) and attempt == 0:
                    await asyncio.sleep(1.0)
                    continue
                if resp.status != 200:
                    return {}
                return await resp.json(content_type=None)
        except Exception:
            if attempt == 0:
                await asyncio.sleep(0.5)
                continue
            return {}
    return {}


async def _search(session, lang, query, limit=6):
    """Article titles for a phrase, disambiguation pages left out.

    A disambiguation page is a list of things with the same name, not a subject:
    its extract is empty and its photos are none, so it must not win the search.
    """
    data = await _get(session, WIKI_API.format(lang=lang),
                      {"action": "query", "generator": "search", "gsrsearch": query,
                       "gsrnamespace": 0, "gsrlimit": max(1, int(limit)),
                       "prop": "pageprops", "ppprop": "disambiguation",
                       "format": "json", "formatversion": 2})
    pages = (data.get("query") or {}).get("pages") or []
    if isinstance(pages, dict):
        pages = list(pages.values())
    pages = sorted(pages, key=lambda page: int(page.get("index") or 99))
    return [str(page.get("title") or "") for page in pages
            if str(page.get("title") or "")
            and (page.get("pageprops") or {}).get("disambiguation") is None]


async def extract(lang, title, max_chars=4000, full=False):
    """Plain-text extract of one article, plus its lead image and Wikidata item."""
    lang = str(lang or "").lower()
    title = str(title or "").strip()
    if lang not in SITES or not title:
        return {}
    key = (lang, title.casefold(), bool(full))
    cached = _EXTRACT_CACHE.get(key)
    if cached is not None:
        if not cached:
            return {}
        return dict(cached, text=cached["text"][:max_chars])
    params = {"action": "query", "prop": "extracts|pageimages|pageprops",
              "explaintext": 1, "titles": title, "format": "json", "redirects": 1,
              "piprop": "original", "ppprop": "wikibase_item|disambiguation"}
    if not full:
        params["exintro"] = 1
    page = {}
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20),
                                     headers={"User-Agent": USER_AGENT}) as session:
        data = await _get(session, WIKI_API.format(lang=lang), params)
    pages = (data.get("query") or {}).get("pages") or {}
    if isinstance(pages, dict):
        pages = list(pages.values())
    if pages:
        page = pages[0] or {}
    text = str(page.get("extract") or "")
    props = page.get("pageprops") or {}
    if props.get("disambiguation") is not None or len(text) <= 100:
        _EXTRACT_CACHE[key] = {}
        return {}
    real_title = str(page.get("title") or title)
    result = {
        "found": True,
        "lang": lang,
        "title": real_title,
        "text": text,
        "image": str((page.get("original") or {}).get("source") or ""),
        "url": f"https://{lang}.wikipedia.org/wiki/{quote(real_title.replace(' ', '_'))}",
        "qid": str(props.get("wikibase_item") or ""),
    }
    _EXTRACT_CACHE[key] = result
    return dict(result, text=text[:max_chars])


async def _sitelinks(session, qid, langs):
    """Article title of one Wikidata item in each requested language."""
    qid = str(qid or "").strip()
    if not qid.startswith("Q"):
        return {}
    if qid in _SITELINK_CACHE:
        return dict(_SITELINK_CACHE[qid])
    sites = [SITES[lang] for lang in langs if lang in SITES]
    if not sites:
        return {}
    data = await _get(session, WIKIDATA_API,
                      {"action": "wbgetentities", "ids": qid, "props": "sitelinks",
                       "sitefilter": "|".join(sites), "format": "json"})
    entity = (data.get("entities") or {}).get(qid) or {}
    links = {}
    for lang, site in SITES.items():
        title = ((entity.get("sitelinks") or {}).get(site) or {}).get("title")
        if title:
            links[lang] = str(title)
    _SITELINK_CACHE[qid] = links
    return dict(links)


async def extract_for_item(qid, lang, max_chars=4000, full=False):
    """The same subject's article in the deck's language, through its sitelink."""
    if not qid or lang not in SITES:
        return {}
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20),
                                     headers={"User-Agent": USER_AGENT}) as session:
        links = await _sitelinks(session, qid, [lang])
    title = links.get(lang)
    if not title:
        return {}
    return await extract(lang, title, max_chars=max_chars, full=full)


# -------------------------------------------------------------------- resolve
async def _best(session, queries, langs, gen_lang):
    async def one(lang, query):
        found = []
        for rank, title in enumerate(await _search(session, lang, query)):
            if _noise_title(title, query):
                continue
            ratio = title_score(query, title)
            if not _accepted(ratio, query):
                continue
            score = ratio * 100 + (6 - rank) + (8 if lang == gen_lang else 0)
            found.append({"lang": lang, "title": title, "ratio": ratio, "score": score})
        return found

    pairs = [(lang, query) for query in queries for lang in langs]
    groups = await asyncio.gather(*(one(lang, query) for lang, query in pairs))
    candidates = [item for group in groups for item in group if item]
    if not candidates:
        return {}
    candidates.sort(key=lambda item: (-item["score"], -item["ratio"]))
    return candidates[0]


async def _resolve_uncached(phrase, langs, gen_lang):
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=25),
                                     headers={"User-Agent": USER_AGENT}) as session:
        primary = [phrase] + (cyrillic_variants(phrase) if "ru" in langs else [])
        best = await _best(session, primary, langs, gen_lang)
        # An exact article already answers the question; only a vague result is
        # worth a second round of shorter, still user-written key phrases.
        if not best or best["ratio"] < 0.85:
            extra = short_queries(phrase)
            if extra:
                more = await _best(session, extra, langs, gen_lang)
                if more and (not best or more["score"] > best["score"]):
                    best = more
    return best


async def resolve(topic, langs, gen_lang="uz"):
    """The article that really covers this topic, or ``{}``."""
    phrase = normalize(topic)
    langs = [str(lang).lower() for lang in langs if str(lang).lower() in SITES]
    gen_lang = str(gen_lang or "uz").lower()
    if len(fold(phrase)) < 2 or not langs:
        return {}
    key = (gen_lang, tuple(langs), fold(phrase))
    cached = _RESOLVE_CACHE.get(key)
    if cached:
        out, saved = cached
        # A momentary rate limit must not turn into "this topic has no article"
        # for the rest of the process, so a miss is remembered only briefly.
        if out or time.time() - saved < _MISS_TTL:
            return dict(out)
    async with _limit():
        try:
            best = await _resolve_uncached(phrase, langs, gen_lang)
        except Exception:
            best = {}
    out = {}
    if best:
        out = {"lang": best["lang"], "title": best["title"], "score": best["score"]}
    _RESOLVE_CACHE[key] = (out, time.time())
    return dict(out)


# ---------------------------------------------------------------- entity path
async def _search_entities(session, query, lang, limit=3):
    data = await _get(session, WIKIDATA_API,
                      {"action": "wbsearchentities", "search": query,
                       "language": lang, "uselang": lang, "format": "json",
                       "limit": max(1, int(limit))})
    return list(data.get("search") or [])


async def entity_source(topic, langs, gen_lang="uz", max_chars=4000, full=False):
    """Second source: the topic's Wikidata item, read in the deck's language.

    Used when no full-text search reaches an article — a narrow subject, a name
    spelled differently in every language, or a topic whose article exists only
    under another title.
    """
    phrase = normalize(topic)
    if not phrase:
        return {}
    wanted = list(dict.fromkeys([str(gen_lang).lower()] + [str(l).lower() for l in langs] + ["en"]))
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=25),
                                     headers={"User-Agent": USER_AGENT}) as session:
        for lang in dict.fromkeys([str(gen_lang).lower(), "en"]):
            if lang not in SITES:
                continue
            queries = [phrase] + (cyrillic_variants(phrase) if lang == "ru" else [])
            for query in queries[:2]:
                for item in (await _search_entities(session, query, lang))[:2]:
                    qid = str(item.get("id") or "")
                    description = str(item.get("description") or "").lower()
                    if not qid or "disambiguation" in description:
                        continue
                    links = await _sitelinks(session, qid, wanted)
                    for pick in wanted:
                        title = links.get(pick)
                        if not title:
                            continue
                        page = await extract(pick, title, max_chars=max_chars, full=full)
                        if page.get("found"):
                            page["source"] = "wikidata"
                            return page
    return {}


async def fetch(topic, langs, gen_lang="uz", max_chars=4000, full=False):
    """Facts for the topic: the article, in the deck's language when it exists."""
    gen_lang = str(gen_lang or "uz").lower()
    page = {}
    resolved = await resolve(topic, langs, gen_lang)
    if resolved:
        page = await extract(resolved["lang"], resolved["title"],
                            max_chars=max_chars, full=full)
        if page.get("found"):
            page["source"] = "wikipedia"
    if page.get("found") and page.get("qid") and page.get("lang") != gen_lang:
        # Same item, deck language: the AI then writes from facts it does not
        # have to translate itself, and the whole deck stays in one language.
        upgraded = await extract_for_item(page["qid"], gen_lang,
                                          max_chars=max_chars, full=full)
        if upgraded.get("found"):
            upgraded["source"] = "wikipedia"
            page = upgraded
    if page.get("found"):
        return page
    return await entity_source(topic, langs, gen_lang, max_chars=max_chars, full=full)
