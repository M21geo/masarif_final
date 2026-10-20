"""Arabic text for PDF: letter shaping (joined forms) + right-to-left ordering, pure Python.

PDF libraries draw glyphs left to right and do not join Arabic letters, so a line is converted to what it must
look like on paper: shaped() joins the letters, visual() reorders a whole line (numbers and Latin words stay
left-to-right inside it). Needs a font that contains the Arabic presentation forms (DejaVu Sans does).
"""
import re

# letter -> (isolated, final, initial, medial); right-joining letters have only the first two
_F = {
    "ء": ("ﺀ",), "آ": ("ﺁ", "ﺂ"), "أ": ("ﺃ", "ﺄ"), "ؤ": ("ﺅ", "ﺆ"), "إ": ("ﺇ", "ﺈ"),
    "ئ": ("ﺉ", "ﺊ", "ﺋ", "ﺌ"), "ا": ("ﺍ", "ﺎ"), "ب": ("ﺏ", "ﺐ", "ﺑ", "ﺒ"), "ة": ("ﺓ", "ﺔ"),
    "ت": ("ﺕ", "ﺖ", "ﺗ", "ﺘ"), "ث": ("ﺙ", "ﺚ", "ﺛ", "ﺜ"), "ج": ("ﺝ", "ﺞ", "ﺟ", "ﺠ"),
    "ح": ("ﺡ", "ﺢ", "ﺣ", "ﺤ"), "خ": ("ﺥ", "ﺦ", "ﺧ", "ﺨ"), "د": ("ﺩ", "ﺪ"), "ذ": ("ﺫ", "ﺬ"),
    "ر": ("ﺭ", "ﺮ"), "ز": ("ﺯ", "ﺰ"), "س": ("ﺱ", "ﺲ", "ﺳ", "ﺴ"), "ش": ("ﺵ", "ﺶ", "ﺷ", "ﺸ"),
    "ص": ("ﺹ", "ﺺ", "ﺻ", "ﺼ"), "ض": ("ﺽ", "ﺾ", "ﺿ", "ﻀ"), "ط": ("ﻁ", "ﻂ", "ﻃ", "ﻄ"),
    "ظ": ("ﻅ", "ﻆ", "ﻇ", "ﻈ"), "ع": ("ﻉ", "ﻊ", "ﻋ", "ﻌ"), "غ": ("ﻍ", "ﻎ", "ﻏ", "ﻐ"),
    "ف": ("ﻑ", "ﻒ", "ﻓ", "ﻔ"), "ق": ("ﻕ", "ﻖ", "ﻗ", "ﻘ"), "ك": ("ﻙ", "ﻚ", "ﻛ", "ﻜ"),
    "ل": ("ﻝ", "ﻞ", "ﻟ", "ﻠ"), "م": ("ﻡ", "ﻢ", "ﻣ", "ﻤ"), "ن": ("ﻥ", "ﻦ", "ﻧ", "ﻨ"),
    "ه": ("ﻩ", "ﻪ", "ﻫ", "ﻬ"), "و": ("ﻭ", "ﻮ"), "ى": ("ﻯ", "ﻰ"), "ي": ("ﻱ", "ﻲ", "ﻳ", "ﻴ"),
    "ـ": ("ـ", "ـ", "ـ", "ـ"),
    # Persian / Iraqi extras
    "پ": ("ﭖ", "ﭗ", "ﭘ", "ﭙ"), "چ": ("ﭺ", "ﭻ", "ﭼ", "ﭽ"), "ژ": ("ﮊ", "ﮋ"), "گ": ("ﮒ", "ﮓ", "ﮔ", "ﮕ"),
    "ک": ("ﮎ", "ﮏ", "ﮐ", "ﮑ"), "ی": ("ﯼ", "ﯽ", "ﯾ", "ﯿ"), "ڤ": ("ﭪ", "ﭫ", "ﭬ", "ﭭ"),
}
_LAM_ALEF = {"ا": ("ﻻ", "ﻼ"), "أ": ("ﻷ", "ﻸ"), "إ": ("ﻹ", "ﻺ"), "آ": ("ﻵ", "ﻶ")}
_MARKS = re.compile("[ً-ٰٟۖ-ۭ]")        # harakat: dropped (no mark positioning in PDF)
_DUAL = {c for c, f in _F.items() if len(f) == 4}
_RIGHT = {c for c, f in _F.items() if len(f) == 2}                # join to the previous letter only
_MIRROR = str.maketrans("()[]{}<>«»", ")(][}{><»«")
_ARABIC_RANGE = re.compile("[؀-ۿﭐ-﷿ﹰ-﻿]")


def has_arabic(text: str) -> bool:
    return bool(_ARABIC_RANGE.search(text))


def shaped(text: str) -> str:
    """Letters replaced by their joined presentation forms, still in logical order."""
    text = _MARKS.sub("", text)
    out, n = [], len(text)
    for i, c in enumerate(text):
        if c not in _F:
            out.append(c)
            continue
        prev = text[i - 1] if i else ""
        nxt = text[i + 1] if i + 1 < n else ""
        joins_prev = prev in _DUAL
        if c == "ل" and nxt in _LAM_ALEF:                # lam + alef = one ligature glyph
            out.append(_LAM_ALEF[nxt][1 if joins_prev else 0])
            out.append("\0")                              # placeholder for the swallowed alef
            continue
        if prev == "ل" and c in _LAM_ALEF:
            continue
        joins_next = (c in _DUAL) and (nxt in _DUAL or nxt in _RIGHT)
        forms = _F[c]
        if len(forms) == 1:
            out.append(forms[0])
        elif len(forms) == 2:
            out.append(forms[1] if joins_prev else forms[0])
        else:
            out.append(forms[3] if joins_prev and joins_next else forms[1] if joins_prev else forms[2] if joins_next else forms[0])
    return "".join(out).replace("\0", "")


def _kind(c: str) -> str:
    if has_arabic(c):
        return "R"
    if c.isdigit() or c.isalpha():
        return "L"           # Latin letters and digits read left-to-right
    return "N"               # spaces / punctuation take the direction around them


def visual(text: str, rtl: bool = True) -> str:
    """Whole line in on-paper order. rtl=True: Arabic paragraph (numbers/Latin stay left-to-right inside it)."""
    if not text:
        return text
    s = shaped(text)
    kinds = [_kind(c) for c in s]
    # join numbers like 1,250.50 / 10:30 / 2026-10-19 / +5% into the digit run; other neutrals follow their neighbours
    for i, c in enumerate(s):
        if kinds[i] == "N" and c in ",.:/-+−%$" and 0 < i < len(s) - 1 and kinds[i - 1] == "L" and kinds[i + 1] == "L":
            kinds[i] = "L"
    for i, c in enumerate(s):                          # 25%  $150  +5  −3
        if kinds[i] == "N":
            if c in "%$" and ((i and kinds[i - 1] == "L") or (i + 1 < len(s) and kinds[i + 1] == "L")):
                kinds[i] = "L"
            elif c in "+−-" and i + 1 < len(s) and kinds[i + 1] == "L" and (i == 0 or s[i - 1] in " ("):
                kinds[i] = "L"
    base = "R" if rtl else "L"
    for i in range(len(s)):
        if kinds[i] == "N":
            j = i - 1
            while j >= 0 and kinds[j] == "N":
                j -= 1
            k = i + 1
            while k < len(s) and kinds[k] == "N":
                k += 1
            left = kinds[j] if j >= 0 else base
            right = kinds[k] if k < len(s) else base
            kinds[i] = left if left == right else base
    runs, cur, ck = [], "", None
    for c, k in zip(s, kinds):
        if k != ck and cur:
            runs.append((ck, cur))
            cur = ""
        cur, ck = cur + c, k
    if cur:
        runs.append((ck, cur))
    if rtl:
        runs.reverse()
        return "".join((r[::-1].translate(_MIRROR) if k == "R" else r) for k, r in runs)
    return "".join(_ltr_run(k, r) for k, r in _group_ltr(runs))


def _group_ltr(runs):
    """LTR paragraph: Arabic runs are reversed individually, consecutive Arabic runs keep reverse order."""
    out, buf = [], []
    for k, r in runs:
        if k == "R":
            buf.append(r)
        else:
            if buf:
                out.append(("R", buf))
                buf = []
            out.append((k, r))
    if buf:
        out.append(("R", buf))
    return out


def _ltr_run(k, r):
    if k == "R":                                          # several Arabic runs in a row: one RTL stretch
        return "".join(x[::-1].translate(_MIRROR) for x in reversed(r))
    return r


def wrap(text: str, width: float, measure, rtl: bool = True, logical: bool = False) -> list:
    """Split into lines that fit `width` (measure(visual_text) -> points).
    Lines come back in on-paper order, or (logical=True) as plain text to be given to a drawing call that reorders."""
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if cur and measure(visual(trial, rtl)) > width:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    if cur:
        lines.append(cur)
    if logical:
        return lines or [""]
    return [visual(l, rtl) for l in lines] or [""]
