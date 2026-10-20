import ast
import glob
import os
import re
import unittest

from app import i18n
from app.db import connect
from app.repo import Repo
from app.seed import ensure_defaults

AR = re.compile(r"[؀-ۿ]")
ROOT = os.path.join(os.path.dirname(__file__), "..", "app")
# data / keyword lists, not UI text
SKIP = ("importer.py", "reminder.py", "reminders.py", "seed.py", "i18n.py", "i18n_en.py", "pdf_report.py", "arabic.py", "money.py")
IGNORE = {"ال"}


def ui_strings():
    exact, pats = set(), set()
    for path in glob.glob(os.path.join(ROOT, "**", "*.py"), recursive=True):
        if path.endswith(SKIP):
            continue
        with open(path, encoding="utf8") as fh:
            tree = ast.parse(fh.read())
        docs, in_f = set(), set()
        for n in ast.walk(tree):
            if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)) and n.body \
                    and isinstance(n.body[0], ast.Expr) and isinstance(getattr(n.body[0], "value", None), ast.Constant):
                docs.add(id(n.body[0].value))
            if isinstance(n, ast.JoinedStr):
                tpl = ""
                for v in n.values:
                    if isinstance(v, ast.Constant):
                        tpl += v.value
                        in_f.add(id(v))
                    else:
                        tpl += "{}"
                if AR.search(tpl):
                    pats.add((tpl, os.path.basename(path)))
        for n in ast.walk(tree):
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs and id(n) not in in_f \
                    and AR.search(n.value):
                exact.add((n.value, os.path.basename(path)))
    return exact, pats


class I18n(unittest.TestCase):
    def setUp(self):
        i18n.set_lang("en")

    def tearDown(self):
        i18n.set_lang("ar")

    def test_every_ui_text_has_english(self):
        exact, pats = ui_strings()
        missing = sorted(f"{f}: {s!r}" for s, f in exact if s not in IGNORE and AR.search(i18n.tr(s)))
        missing += sorted(f"{f}: {t!r}" for t, f in pats if AR.search(i18n.tr(t.replace("{}", "7"))))
        self.assertEqual(missing, [], "texts without an English version:\n" + "\n".join(missing))

    def test_dynamic_texts(self):
        t = i18n.tr
        self.assertEqual(t("المتبقي بعدها 5,000 د.ع"), "Left after it: 5,000 IQD")
        self.assertEqual(t("تشرين الأول 2026"), "October 2026")
        self.assertEqual(t("12 معاملة"), "12 transactions")
        self.assertEqual(t("كل 2 أسبوع"), "Every 2 weeks")
        self.assertEqual(t("اليوم"), "Today")
        self.assertEqual(t("غدا"), "غدا")                       # user text stays as typed
        self.assertEqual(t("12,000 د.ع"), "12,000 IQD")
        self.assertEqual(t(t("اليوم")), "Today")               # idempotent
        self.assertEqual(i18n.tr("اليوم", to="ar"), "اليوم")

    def test_arabic_is_untouched(self):
        i18n.set_lang("ar")
        self.assertEqual(i18n.tr("الرئيسية"), "الرئيسية")
        self.assertTrue(i18n.is_rtl())

    def test_translate_tree(self):
        class Ctl:
            def __init__(self, **kw):
                self.__dict__.update(kw)
        Text = type("Text", (Ctl,), {})
        TextField = type("TextField", (Ctl,), {})
        Row = type("Row", (Ctl,), {})
        field = TextField(label="المبلغ", value="الرئيسية", hint_text=None)
        tree = Row(controls=[Text(value="المحافظ"), field, Row(controls=[Text(value="غدا")], tooltip="حفظ")])
        i18n.translate_tree(tree)
        self.assertEqual(tree.controls[0].value, "Wallets")
        self.assertEqual(field.label, "Amount")
        self.assertEqual(field.value, "الرئيسية")               # what the user typed is never translated
        self.assertEqual(tree.controls[2].controls[0].value, "غدا")
        self.assertEqual(tree.controls[2].tooltip, "Save")

    def test_localize_defaults_both_ways(self):
        r = Repo(connect(":memory:"))
        ensure_defaults(r)
        r.add_person("علي")
        mine = r.add_category("expense", "طعام الكلب")           # user-made: never touched
        n = i18n.localize_defaults(r, "en")
        self.assertGreater(n, 10)
        names = {c["name"] for c in r.category_tree("expense")}
        self.assertIn("Food", names)
        self.assertIn("طعام الكلب", names)
        self.assertEqual({w["name"] for w in r.list_wallets()}, {"Cash", "Cash USD"})
        i18n.localize_defaults(r, "ar")
        self.assertIn("طعام", {c["name"] for c in r.category_tree("expense")})
        self.assertEqual({w["name"] for w in r.list_wallets()}, {"نقد", "دولار نقد"})


if __name__ == "__main__":
    unittest.main()
