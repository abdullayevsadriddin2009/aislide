"""O'zbek lotin yozuvidagi matnni yangi alifboga o'girish.

2023-yilgi islohotga ko'ra to'rtta harf birikmasi almashtiriladi:

    o' → ö      g' → ğ      sh → ş      ch → ç

Apostrofning barcha ko'rinishlari (' ‘ ’ ʻ ʼ ` ′) hisobga olinadi, shuning uchun
AI qaysi uslubda yozsa ham natija bir xil bo'ladi.
"""
import re

_APOSTROPHES = "'\u2018\u2019\u02bb\u02bc\u2032`"
_LETTERS = {"O": "Ö", "o": "ö", "G": "Ğ", "g": "ğ"}
_OG = re.compile("([OoGg])[%s]" % re.escape(_APOSTROPHES))
_DIGRAPHS = (("Sh", "Ş"), ("SH", "Ş"), ("sh", "ş"),
             ("Ch", "Ç"), ("CH", "Ç"), ("ch", "ç"))


def to_new_alphabet(text):
    """Matnning hamma joyida o'/g'/sh/ch ni ö/ğ/ş/ç ga almashtiradi."""
    if text is None:
        return text
    s = _OG.sub(lambda match: _LETTERS[match.group(1)], str(text))
    for old, new in _DIGRAPHS:
        s = s.replace(old, new)
    return s


def slides_to_new_alphabet(slides):
    """Slaydlar ro'yxatidagi sarlavha va matnlarni yangi alifboga o'giradi."""
    result = []
    for item in slides or []:
        if not isinstance(item, dict):
            result.append(item)
            continue
        copy = dict(item)
        for key in ("title", "subtitle", "text", "content"):
            value = copy.get(key)
            if isinstance(value, str):
                copy[key] = to_new_alphabet(value)
            elif isinstance(value, (list, tuple)):
                copy[key] = [to_new_alphabet(v) if isinstance(v, str) else v for v in value]
        result.append(copy)
    return result
