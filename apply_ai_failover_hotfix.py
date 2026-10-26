#!/usr/bin/env python3
"""Apply a minimal AI failover fix without replacing the project's API_LIST."""
from pathlib import Path
import re
import sys

ROOT = Path.cwd()
AI_PATH = ROOT / "ai_api.py"
CREATION_PATH = ROOT / "handlers" / "creation.py"
PATCH_DIR = Path(__file__).resolve().parent
FUNCTION_PATH = PATCH_DIR / "ai_api_chat_complete_replacement.txt"

if not AI_PATH.is_file():
    print("XATO: ai_api.py topilmadi. Skriptni loyiha asosiy papkasida ishga tushiring.")
    sys.exit(1)

function = FUNCTION_PATH.read_text(encoding="utf-8").strip()
ai_text = AI_PATH.read_text(encoding="utf-8")
start_marker = "async def _chat_complete("
end_marker = "\nCHAT_LANGUAGE_NAMES ="
if start_marker not in ai_text or end_marker not in ai_text[ai_text.index(start_marker):]:
    print("XATO: _chat_complete yoki CHAT_LANGUAGE_NAMES belgisi topilmadi. Fayl kutilgan versiyadan farq qiladi; fayl o'zgartirilmadi.")
    sys.exit(2)
start = ai_text.index(start_marker)
end = ai_text.index(end_marker, start)
ai_text = ai_text[:start] + function + "\n" + ai_text[end:]

# On bad structured outputs, retain a useful reason rather than displaying n/a.
quiz_sig = 'async def _generate_test(service, topic, options, lang):\n    """Generate exactly 10/15/20 questions, and never leak an invalid language response."""\n'
if quiz_sig in ai_text and quiz_sig + '    global LAST_ERROR\n' not in ai_text:
    ai_text = ai_text.replace(quiz_sig, quiz_sig + '    global LAST_ERROR\n', 1)
quiz_old = '''            else:
                txt = _fallback_test_questions(topic, start, end, lc)
                used_fallback = True
        all_questions.append(clean_ai_text(txt))'''
quiz_new = '''            else:
                if not LAST_ERROR:
                    LAST_ERROR = (
                        f"AI javobi {start}-{end}-savollar uchun format/til tekshiruvidan o'tmadi; "
                        "shu qismga zaxira savollar qo'shildi."
                    )
                txt = _fallback_test_questions(topic, start, end, lc)
                used_fallback = True
        all_questions.append(clean_ai_text(txt))'''
if quiz_old in ai_text:
    ai_text = ai_text.replace(quiz_old, quiz_new, 1)
elif quiz_new not in ai_text:
    print("OGOHLANTIRISH: test fallback diagnostics bloki qo'shilmadi (kod tuzilishi farq qiladi).")

slides_sig = 'async def generate_slides_structured(topic, subject, lang, count):\n'
if slides_sig in ai_text and slides_sig + '    global LAST_ERROR\n' not in ai_text:
    ai_text = ai_text.replace(slides_sig, slides_sig + '    global LAST_ERROR\n', 1)
slides_marker = '    # Keep count exact without inserting text from another language.\n    used_fallback = not bool(all_slides)'
slides_repl = '''    if not parsed and not str(txt or "").strip().startswith("⚠️") and not LAST_ERROR:
        LAST_ERROR = "AI javobi yaroqli JSON/til tekshiruvidan o'tmadi; taqdimot zaxira mazmun bilan tuzildi."

    # Keep count exact without inserting text from another language.
    used_fallback = not bool(all_slides)'''
if slides_marker in ai_text:
    ai_text = ai_text.replace(slides_marker, slides_repl, 1)
elif slides_repl not in ai_text:
    print("OGOHLANTIRISH: taqdimot JSON diagnostics bloki qo'shilmadi (kod tuzilishi farq qiladi).")

slides_empty = '''    if not all_slides:
        all_slides = _fallback_slides(topic, count, lang)
    else:
        if len(all_slides) < count:
            used_fallback = True'''
slides_empty_repl = '''    if not all_slides:
        if not LAST_ERROR:
            LAST_ERROR = "AI mazmuni yaroqsiz yoki bo'sh; taqdimot uchun zaxira slaydlar ishlatildi."
        used_fallback = True
        all_slides = _fallback_slides(topic, count, lang)
    else:
        if len(all_slides) < count:
            used_fallback = True
            if not LAST_ERROR:
                LAST_ERROR = f"AI faqat {len(all_slides)} ta slayd qaytardi; qolgan slaydlar zaxiradan to'ldirildi."'''
if slides_empty in ai_text:
    ai_text = ai_text.replace(slides_empty, slides_empty_repl, 1)
elif slides_empty_repl not in ai_text:
    print("OGOHLANTIRISH: taqdimot fallback diagnostics bloki qo'shilmadi (kod tuzilishi farq qiladi).")

# Preserve the exact live provider list and all other API code.
backup = AI_PATH.with_suffix(AI_PATH.suffix + ".before_failover_fix.bak")
if not backup.exists():
    backup.write_text(AI_PATH.read_text(encoding="utf-8"), encoding="utf-8")
AI_PATH.write_text(ai_text, encoding="utf-8")
changed = [str(AI_PATH.relative_to(ROOT))]

# For DOCX fallback, show the real failure reason instead of only a generic warning.
if CREATION_PATH.is_file():
    creation = CREATION_PATH.read_text(encoding="utf-8")
    pattern = re.compile(r'^(?P<indent>[ \t]*)caption = t\("gen_done", lang\) if real else t\("gen_failed", lang\)\s*$', re.M)
    def repl(match):
        i = match.group("indent")
        return (
            f'{i}if real:\n'
            f'{i}    caption = t("gen_done", lang)\n'
            f'{i}else:\n'
            f'{i}    caption = t("gen_failed", lang)\n'
            f'{i}    detail = get_last_error()\n'
            f'{i}    if detail:\n'
            f'{i}        caption += f"\\n\\n🔍 {{str(detail)[:350]}}"'
        )
    creation_new, n = pattern.subn(repl, creation)
    if n:
        backup_creation = CREATION_PATH.with_suffix(CREATION_PATH.suffix + ".before_failover_fix.bak")
        if not backup_creation.exists():
            backup_creation.write_text(creation, encoding="utf-8")
        CREATION_PATH.write_text(creation_new, encoding="utf-8")
        changed.append(str(CREATION_PATH.relative_to(ROOT)))

print("Hotfix qo'llandi. O'zgartirilgan fayllar: " + ", ".join(changed))
print("API_LIST va API kalit nomlari saqlandi; zaxira nusxalar .bak fayllarda yaratildi.")
print("Endi tekshiring: python -m py_compile ai_api.py handlers/creation.py")
