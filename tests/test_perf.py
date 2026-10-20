"""Archive performance guards: big archives must render in batches and reuse computed statistics."""
import sys
import time
import unittest
from unittest.mock import MagicMock

sys.modules["flet"] = MagicMock()

from app.db import connect  # noqa: E402
from app.repo import Repo  # noqa: E402
from app.seed import ensure_defaults  # noqa: E402
from app.ui import app as appmod, screens_txs, vm  # noqa: E402


class FakePage:
    width, height = 390, 800

    def __getattr__(self, n):
        return MagicMock()


class Perf(unittest.TestCase):
    def setUp(self):
        self.repo = Repo(connect(":memory:"))
        ensure_defaults(self.repo)
        w = self.repo.list_wallets()[0]["id"]
        rows = [(w, "expense", (i % 400 + 1) * 1000, f"20{18 + i % 7}-{i % 12 + 1:02d}-{i % 28 + 1:02d}") for i in range(20000)]
        with self.repo.conn:
            self.repo.conn.executemany("INSERT INTO transactions(wallet_id,kind,amount,date) VALUES(?,?,?,?)", rows)
        self.ui = appmod.AppUI(FakePage(), self.repo, "2026-10-18")
        self.ui.all_time = self.ui.allow_all_time = self.ui.cacheable = True

    def test_list_renders_only_first_batch(self):
        built = []
        orig = screens_txs.tx_tile
        screens_txs.tx_tile = lambda ui, r, *a, **k: built.append(r) or orig(ui, r, *a, **k)
        try:
            t = time.perf_counter()
            screens_txs.build_txs(self.ui)
            self.assertLess(time.perf_counter() - t, 3)
        finally:
            screens_txs.tx_tile = orig
        self.assertEqual(len(built), screens_txs.PAGE_FIRST)

    def test_scope_cached_until_inputs_change(self):
        a = vm.scope_and_analysis(self.ui)
        self.assertIs(a, vm.scope_and_analysis(self.ui))
        self.ui.currency = "USD"
        self.assertIsNot(a, vm.scope_and_analysis(self.ui))

    def test_main_ui_not_cached(self):
        self.ui.cacheable = False
        self.assertIsNot(vm.scope_and_analysis(self.ui), vm.scope_and_analysis(self.ui))


if __name__ == "__main__":
    unittest.main()


class PaymentDetails(unittest.TestCase):
    def test_payment_list_has_wallet_and_balance_after(self):
        from app.debts import Debts
        repo = Repo(connect(":memory:"))
        ensure_defaults(repo)
        w = repo.list_wallets()[0]
        pid = repo.add_person("علي")
        deb = Debts(repo)
        did = deb.add_debt("on", pid, 90000, w["currency"], "2026-10-01", "x", installments=3, first_due="2026-11-01")
        deb.pay(did, 30000, w["id"], "2026-11-01")
        deb.pay(did, 30000, None, "2026-12-01", "نقداً")
        pays = deb.list_payments(did)
        self.assertEqual([p["n"] for p in pays], [2, 1])
        self.assertEqual([p["remaining_after"] for p in pays], [30000, 60000])
        self.assertEqual(pays[1]["wallet_name"], w["name"])
        self.assertIsNone(pays[0]["wallet_name"])


class ImportArabicFile(unittest.TestCase):
    def test_arabic_dates_and_transfers(self):
        from app import importer
        self.assertEqual(importer.parse_date("21 يناير، 2026 07:06 PM"), "2026-01-21")
        self.assertEqual(importer.parse_date("9 سبتمبر، 2024 10:06 PM"), "2024-09-09")
        self.assertEqual(importer.parse_date("5 أيلول 2024"), "2024-09-05")
        self.assertEqual(importer.parse_date("3 ابريل، 2020 01:00 AM"), "2020-04-03")
        headers = ["الملاحظات", "جهة الإتصال", "الى (المحفظة)", "المحفظة", "العملة", "التكلفة", "القسم", "القسم الرئيسي", "التاريخ"]
        m = importer.guess_mapping(headers)
        self.assertEqual((m["to_wallet"], m["wallet"], m["category"], m["subcategory"]),
                         ("الى (المحفظة)", "المحفظة", "القسم الرئيسي", "القسم"))
        rows = [dict(zip(headers, r)) for r in [
            ["", ".علي", "", "النقد", "IQD", "-5000", "بنزين", "المواصلات", "9 سبتمبر، 2024 10:06 PM"],
            ["سحب", "", "النقد", "المصرف", "IQD", "700000", "تحويل رصيد", "تحويل رصيد", "1 سبتمبر، 2024 12:03 AM"]]]
        repo = Repo(connect(":memory:"))
        items = importer.preview(repo, rows, m)
        self.assertEqual([i["kind"] for i in items], ["expense", "transfer"])
        self.assertEqual(items[0]["person"], "علي")
        self.assertEqual(importer.commit(repo, items)["added"], 2)
        tr = repo.list_transactions(kinds=["transfer"])[0]
        self.assertEqual((tr["wallet_name"], tr["to_wallet_name"]), ("المصرف", "النقد"))


class WeekAndDrill(unittest.TestCase):
    def setUp(self):
        self.repo = Repo(connect(":memory:"))
        ensure_defaults(self.repo)
        w = self.repo.list_wallets()[0]["id"]
        cat = self.repo.category_tree("expense")[0]["id"]
        self.repo.add_income(w, 500000, date="2026-10-17")
        self.repo.add_expense(w, 20000, category_id=cat, date="2026-10-18")
        self.repo.add_expense(w, 30000, category_id=cat, date="2026-10-10")
        self.ui = appmod.AppUI(FakePage(), self.repo, "2026-10-18")

    def test_week_scope_is_saturday_to_friday_with_previous_week(self):
        self.assertEqual(vm.week_start("2026-10-18"), "2026-10-17")  # Saturday
        self.ui.period_mode = "week"
        scope, an, prev = vm.scope_and_analysis(self.ui)
        self.assertEqual(scope["span"][0], "2026-10-17")
        self.assertEqual(len(scope["rows"]), 2)
        self.assertEqual(scope["prev"], ("2026-10-10", "2026-10-16"))
        self.assertEqual(prev.totals()["expense"], 30000)

    def test_week_label(self):
        self.assertEqual(vm.week_label("2026-10-17"), "17 – 23 " + vm.MONTH_NAMES[9] + " 2026")

    def test_all_views_in_week_mode_and_drill(self):
        self.ui.period_mode = "week"
        self.ui.tab = 1
        for v in ("list", "summary", "cats", "analysis"):
            self.ui.tx_view = v
            self.ui.refresh()
            self.assertIsNone(self.ui.last_error, self.ui.last_error)
        scope = vm.scope_and_analysis(self.ui)[0]
        screens_txs.open_drill(self.ui, scope, "t", lambda t: t["kind"] == "expense")

    def test_signed_amounts_start_with_ltr_mark(self):
        from app.ui import kit
        kit.txt("−5,000")  # must not raise; sign is isolated by a left-to-right mark in the real widget
