"""Markdown → Telegram HTML va uzun matnni bo'laklarga ajratish.

CdxChatBot.php dagi `md_to_tg_html` va `split_text` funksiyalarining Python
ko'rinishi: qalin/kursiv, kod, ro'yxat, sarlavha, havola va jadvallar Telegram
qo'llaydigan HTML teglariga o'giriladi.
"""
import html
import re

_PLACEHOLDER = "\x01{}\x02"

_MD_ESCAPE = (
    ("&", "&amp;"),
    ("<", "&lt;"),
    (">", "&gt;"),
)


def _escape(value):
    text = str(value or "")
    for wrong, right in _MD_ESCAPE:
        text = text.replace(wrong, right)
    return text


def md_to_tg_html(markdown):
    text = str(markdown or "")
    if not text:
        return ""
    store = []

    def keep(fragment):
        store.append(fragment)
        return _PLACEHOLDER.format(len(store) - 1)

    def code_block(match):
        language = match.group(1) or ""
        code = _escape(match.group(2).rstrip("\n"))
        if language:
            return keep(f'<pre><code class="language-{_escape(language)}">{code}</code></pre>')
        return keep(f"<pre>{code}</pre>")

    text = re.sub(r"```([\w+#.-]*)[ \t]*\n?(.*?)```", code_block, text, flags=re.S|re.I)

    def table(match):
        return keep(f"<pre>{_escape(match.group(0).rstrip())}</pre>") + "\n"

    text = re.sub(r"(?:^[ \t]*\|.*\|[ \t]*(?:\n|$))+", table, text, flags=re.M)

    text = re.sub(r"`([^`\n]+)`", lambda m: keep(f"<code>{_escape(m.group(1))}</code>"), text)

    text = _escape(text)

    text = re.sub(r"\[([^\]\n]+)\]\((https?://[^\s)\"]+)\)",
                  lambda m: keep(f'<a href="{m.group(2)}">{m.group(1)}</a>'), text)
    text = re.sub(r"^[ \t]*([-*_])([ \t]*\1){2,}[ \t]*$", "──────────", text, flags=re.M)
    text = re.sub(r"^[ \t]{0,3}#{1,6}[ \t]+(.+?)[ \t]*#*[ \t]*$", r"<b>\1</b>", text, flags=re.M)
    text = re.sub(r"^([ \t]*)[-*+][ \t]+", r"\1• ", text, flags=re.M)
    text = re.sub(r"^&gt;[ \t]?(.*)$", r"▎ \1", text, flags=re.M)
    text = re.sub(r"\*\*([^\n]+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\w)__([^\n]+?)__(?!\w)", r"<b>\1</b>", text)
    text = re.sub(r"(?<![\w*])\*(?![\s*])([^*\n]+?)(?<![\s*])\*(?![\w*])", r"<i>\1</i>", text)
    text = re.sub(r"(?<!\w)_(?<![\s_])([^_\n]+?)(?<![\s_])_(?!\w)", r"<i>\1</i>", text)
    text = re.sub(r"~~([^\n]+?)~~", r"<s>\1</s>", text)

    return re.sub(r"\x01(\d+)\x02", lambda m: store[int(m.group(1))], text)


def split_text(text, limit=3500):
    """Matnni qator chegarasida bo'laklarga ajratadi (Telegram limiti 4096)."""
    value = str(text or "")
    parts = []
    while len(value) > limit:
        cut = value.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = limit
        parts.append(value[:cut].rstrip())
        value = value[cut:].lstrip("\n")
    if value.strip():
        parts.append(value)
    return parts or [""]


def html_chunks(markdown, limit=3500):
    """Har bir bo'lakni alohida HTML'ga o'giradi (teglar bo'linib ketmasligi uchun)."""
    return [md_to_tg_html(part) for part in split_text(markdown, limit)]
