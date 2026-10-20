import os, sqlite3, sys, tempfile, unittest
from unittest.mock import MagicMock

from app import noteimg
from app.db import connect, init_schema
from app.repo import AppError, Repo
from app.seed import ensure_defaults
from app.analysis import Analysis


def make():
    r = Repo(connect(":memory:"))
    ensure_defaults(r)
    return r


class Step9(unittest.TestCase):
    def usd_wallet(self, r):
        return next(w for w in r.list_wallets() if w["currency"] == "USD")

    def test_rate_per_transaction(self):
        r = make()
        usd = self.usd_wallet(r)
        r.add_income(usd["id"], 1000, date="2026-10-01")
        a = r.add_expense(usd["id"], 10, date="2026-10-02", rate=1400)
        b = r.add_expense(usd["id"], 10, date="2026-10-03", rate=1500)
        c = r.add_expense(usd["id"], 10, date="2026-10-04")          # no own rate: falls back to the default
        self.assertEqual(r.get_transaction(a)["rate"], 1400)
        r.set_rate(1480)
        rows = r.list_transactions(kinds=["expense"])
        an = Analysis(rows, "IQD", r.get_rate())
        self.assertEqual(sum(v for _, v in an.items), 10 * 1400 + 10 * 1500 + 10 * 1480)
        r.update_transaction(b, rate=1520)
        self.assertEqual(r.get_transaction(b)["rate"], 1520)
        with self.assertRaises(AppError):
            r.update_transaction(b, rate=-1)
        # IQD wallets never keep a rate
        iqd = next(w for w in r.list_wallets() if w["currency"] == "IQD")
        t = r.add_expense(iqd["id"], 5000, rate=1500)
        self.assertIsNone(r.get_transaction(t)["rate"])

    def test_hidden_people(self):
        r = make()
        a, b = r.add_person("أ"), r.add_person("ب")
        r.set_person_hidden(a, True)
        self.assertEqual([p["id"] for p in r.list_people()], [a, b])
        self.assertEqual([p["id"] for p in r.list_people(visible_only=True)], [b])
        self.assertEqual([p["id"] for p in r.list_people(visible_only=True, keep=a)], [a, b])  # already on this transaction
        r.set_person_hidden(a, False)
        self.assertEqual(len(r.list_people(visible_only=True)), 2)

    def test_note_image(self):
        r = make()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "x.png")
            open(path, "wb").write(b"\x89PNG\r\n\x1a\n" + b"0" * 50)
            b64 = noteimg.load(path)
            self.assertEqual(noteimg.guess_ext(b64), "png")
            bad = os.path.join(d, "x.exe")
            open(bad, "wb").write(b"1")
            with self.assertRaises(AppError):
                noteimg.load(bad)
        n = r.add_note("", image=b64)                     # a picture alone is a valid note
        self.assertEqual(r.list_notes()[0]["image"], b64)
        r.update_note(n, "نص")                            # keeps the picture
        self.assertEqual(r.list_notes()[0]["image"], b64)
        r.update_note(n, "نص", "")                        # removes it
        self.assertEqual(r.list_notes()[0]["image"], "")
        with self.assertRaises(AppError):
            r.update_note(n, "  ", "")

    def test_upgrade_from_v4(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "old.db")
            c = sqlite3.connect(path)
            c.executescript("CREATE TABLE people(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, sort_order INTEGER NOT NULL DEFAULT 0);"
                            "CREATE TABLE notes(id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT NOT NULL, pinned INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL DEFAULT (datetime('now')));"
                            "INSERT INTO people(name) VALUES('x'); INSERT INTO notes(text) VALUES('n'); PRAGMA user_version=4;")
            c.commit(); c.close()
            r = Repo(connect(path))
            self.assertEqual(r.list_people()[0]["hidden"], 0)
            self.assertEqual(r.list_notes()[0]["image"], "")


class Step9Ui(unittest.TestCase):
    def test_screens(self):
        sys.modules.setdefault("flet", MagicMock())
        from tests.test_ui_smoke import FakePage
        from app.ui import app as appmod
        from app.ui.pages_notes import build_notes
        from app.ui.pages_people import build_people
        from app.ui.sheet_add import open_add_sheet
        r = make()
        r.add_note("a", image="aGVsbG8=")
        r.add_person("س"); r.set_person_hidden(r.list_people()[0]["id"], True)
        ui = appmod.AppUI(FakePage(), r, "2026-10-20")
        build_notes(ui); build_people(ui)
        open_add_sheet(ui)
        open_add_sheet(ui, kind="income")
        usd = next(w for w in r.list_wallets() if w["currency"] == "USD")
        t = r.add_expense(usd["id"], 10, rate=1400)
        open_add_sheet(ui, r.get_transaction(t))
        ui.tab = 0; ui.refresh()
        self.assertIsNone(ui.last_error, ui.last_error)


if __name__ == "__main__":
    unittest.main()
