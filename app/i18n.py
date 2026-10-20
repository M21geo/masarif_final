"""Two languages: Arabic (the texts written in the code) and English (app/i18n_en.py).

* tr(text)         translate one UI text to the current language. Arabic -> unchanged.
* translate_tree() translate every text of a Flet control tree (so screens do not need to call tr() everywhere).
* localize_defaults() renames the first-run categories/wallets when the language changes. Names the user typed
  are never touched, and notes / categories can still be typed in either language at any time.
"""
import re
from functools import lru_cache

from .i18n_en import EXACT, PATTERNS

_lang = "ar"
LANGUAGES = [("ar", "العربية"), ("en", "English")]

# category / wallet names created on first run (seed.py)
SEED_NAMES = {
    "طعام": "Food", "مواصلات": "Transport", "فواتير": "Bills", "تسوق": "Shopping", "صحة": "Health",
    "مطاعم": "Restaurants", "بقالة": "Groceries", "قهوة": "Coffee", "توصيل": "Delivery", "وقود": "Fuel", "تكسي": "Taxi",
    "صيانة": "Maintenance", "كهرباء": "Electricity", "إنترنت": "Internet", "ماء": "Water", "ملابس": "Clothes",
    "أجهزة": "Electronics", "دواء": "Medicine", "طبيب": "Doctor", "راتب": "Salary", "عمل حر": "Freelance", "هدية": "Gift",
    "نقد": "Cash", "دولار نقد": "Cash USD",
}

_AR = re.compile(r"[؀-ۿ]")
_NUMERIC_ONLY = {"{} من {}", "كل {}"}            # very generic sentences: only fill them with numbers/amounts
_FRAGMENTS = sorted((k for k in EXACT if (k.endswith(" ") or k.startswith(" ")) and k.strip()), key=len, reverse=True)


def set_lang(code: str) -> None:
    global _lang
    _lang = code if code in dict(LANGUAGES) else "ar"
    _cached.cache_clear()


def lang() -> str:
    return _lang


def is_rtl() -> bool:
    return _lang == "ar"


def _all_patterns():
    """PATTERNS plus every fragment key ("المتبقي بعدها ") as a prefix/suffix pattern, so the longest match wins."""
    out = list(PATTERNS)
    for k in _FRAGMENTS:
        out.append((k + "{}", EXACT[k] + "{}") if k.endswith(" ") else ("{}" + k, "{}" + EXACT[k]))
    return out


def _compile():
    out = []
    for ar, en in _all_patterns():
        pieces = ar.split("{}")
        rx = ""
        for i, p in enumerate(pieces):
            rx += re.escape(p)
            if i < len(pieces) - 1:
                rx += "(.*)" if i == len(pieces) - 2 and not pieces[-1] else "(.+?)"
        letters = len(_AR.findall(ar.replace("{}", "")))
        out.append((len(ar.replace("{}", "")), re.compile("^" + rx + "$", re.S), en, ar in _NUMERIC_ONLY, letters))
    out.sort(key=lambda x: -x[0])
    return out


_PATTERNS = _compile()


def _numeric(s: str) -> bool:
    return not _AR.search(s.replace("د.ع", ""))


@lru_cache(maxsize=4096)
def _cached(s: str) -> str:
    return _translate(s)


def _translate(s: str) -> str:
    if s in EXACT:
        return EXACT[s]
    core = s.strip()
    if core != s and core in EXACT:
        return s.replace(core, EXACT[core])
    for _, rx, en, numeric_only, _letters in _PATTERNS:
        m = rx.match(s)
        if m and (not numeric_only or all(_numeric(g) for g in m.groups())):
            parts = [_cached(g) for g in m.groups()]
            return en.format(*parts)
    if " · " in s:                               # composite lines: "المحفظة · الشخص"
        parts = s.split(" · ")
        done = [_cached(p) for p in parts]
        if done != parts:
            return " · ".join(done)
    m = re.match(r"^(.*\S)\s+(\d[\d,.\-/:%$]*)$", s)   # "تشرين الأول 2026"
    if m and _AR.search(m.group(1)):
        head = _cached(m.group(1))
        if head != m.group(1):
            return head + " " + m.group(2)
    if "د.ع" in s or "، " in s:
        return s.replace("د.ع", "IQD").replace("، ", ", ")
    return s


def tr(text, to=None) -> str:
    """Translate one text. `to` forces a language (used by the PDF report), default: the current one."""
    if not isinstance(text, str) or not text:
        return text
    if (to or _lang) == "ar" or not _AR.search(text):
        return text if not (text.strip() in ("IQD",) and (to or _lang) == "ar") else text
    return _cached(text)


# ------------------------------------------------------------------ Flet control trees
_STR_ATTRS = ("text", "label", "hint_text", "helper_text", "error_text", "prefix_text", "suffix_text", "tooltip", "title", "subtitle")
_CHILD_ATTRS = ("content", "controls", "actions", "title", "subtitle", "leading", "trailing", "label", "options",
                "destinations", "tabs", "icon_content", "bottom", "actions_padding")


def translate_tree(node, _seen=None) -> None:
    """Translate (in place) the texts of a control and everything inside it. No-op in Arabic."""
    if _lang == "ar" or node is None:
        return
    seen = _seen if _seen is not None else set()
    if id(node) in seen:
        return
    seen.add(id(node))
    if isinstance(node, (list, tuple)):
        for n in node:
            translate_tree(n, seen)
        return
    if isinstance(node, (str, int, float, bool)):
        return
    cls = type(node).__name__
    if cls == "Text":
        _set(node, "value")
    elif cls == "TextSpan":
        _set(node, "text")
    for a in _STR_ATTRS:
        if cls in ("Text", "TextField") and a == "text":
            continue
        _set(node, a)
    for a in _CHILD_ATTRS:
        try:
            child = getattr(node, a, None)
        except Exception:
            continue
        if child is not None and not isinstance(child, (str, int, float, bool)):
            translate_tree(child, seen)


def _set(node, attr) -> None:
    try:
        v = getattr(node, attr, None)
        if isinstance(v, str) and v:
            new = tr(v)
            if new != v:
                setattr(node, attr, new)
    except Exception:
        pass


# ------------------------------------------------------------------ first-run names
def localize_defaults(repo, to: str) -> int:
    """Rename seeded categories / wallets to `to` ('ar' or 'en'). Returns how many were renamed."""
    ar_en = SEED_NAMES
    en_ar = {v: k for k, v in SEED_NAMES.items()}
    mapping = ar_en if to == "en" else en_ar
    n = 0
    conn = repo.conn
    for table in ("categories", "wallets"):
        for row in conn.execute(f"SELECT id, name FROM {table}").fetchall():
            new = mapping.get(row["name"])
            if not new:
                continue
            try:
                with conn:
                    conn.execute(f"UPDATE {table} SET name=? WHERE id=?", (new, row["id"]))
                n += 1
            except Exception:       # a same-named item already exists: leave this one alone
                pass
    return n
