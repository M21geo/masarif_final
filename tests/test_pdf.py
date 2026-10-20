import os
import random
import tempfile
import unittest

from app import arabic
from app.db import connect
from app.repo import Repo
from app.seed import ensure_defaults

try:
    import reportlab  # noqa: F401
    HAVE = True
except ImportError:
    HAVE = False


class ArabicText(unittest.TestCase):
    def test_shaping_joins_letters(self):
        s = arabic.shaped("بيت")
        self.assertEqual(len(s), 3)
        self.assertEqual(s[0], "ﺑ")        # initial beh
        self.assertEqual(s[2], "ﺖ")        # final teh
        self.assertEqual(arabic.shaped("لا"), "ﻻ")   # lam-alef ligature
        self.assertEqual(arabic.shaped("ء"), "ﺀ")

    def test_visual_order(self):
        v = arabic.visual("طعام 25,000")
        self.assertTrue(v.startswith("25,000"))            # number ends up on the left of the Arabic word
        self.assertIn("25,000", v)                          # digits keep their order
        self.assertEqual(arabic.visual("abc", rtl=False), "abc")
        self.assertEqual(arabic.visual("+5%"), "+5%")
        self.assertEqual(arabic.visual("(أ)"), "(ﺋ)".replace("ﺋ", arabic.shaped("أ")))  # brackets mirror

    def test_wrap_keeps_all_words(self):
        lines = arabic.wrap("كلمة " * 30, 80, lambda s: len(s) * 5)
        self.assertGreater(len(lines), 2)


@unittest.skipUnless(HAVE, "reportlab not installed")
class Pdf(unittest.TestCase):
    def build(self, lang, currency):
        from app import pdf_report
        r = Repo(connect(":memory:"))
        ensure_defaults(r)
        w = r.list_wallets()
        random.seed(1)
        cats = r.category_tree("expense")
        for i in range(120):
            c = random.choice(cats)
            r.add_expense(w[0]["id"], random.choice([1000, 5000, 25000]), category_id=c["id"],
                          date=f"2026-10-{random.randint(1, 28):02d}", note="ملاحظة " * random.randint(0, 8))
        r.add_income(w[0]["id"], 1000000, date="2026-10-02")
        scope = {"rows": r.list_transactions(), "span": None, "filtered": False, "all": True}
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "r.pdf")
            pdf_report.build_pdf(path, r, scope, currency, lang, "2026-10-19")
            data = open(path, "rb").read()
        return data

    def test_arabic_and_english_reports(self):
        for lang, cur in (("ar", "IQD"), ("en", "USD")):
            data = self.build(lang, cur)
            self.assertTrue(data.startswith(b"%PDF"))
            self.assertGreater(len(data), 20000)

    def test_empty_period(self):
        from app import pdf_report
        r = Repo(connect(":memory:"))
        ensure_defaults(r)
        with tempfile.TemporaryDirectory() as d:
            pdf_report.build_pdf(os.path.join(d, "e.pdf"), r, {"rows": [], "span": None, "filtered": False}, "IQD", "ar", "2026-10-19")
            self.assertTrue(os.path.exists(os.path.join(d, "e.pdf")))


if __name__ == "__main__":
    unittest.main()
