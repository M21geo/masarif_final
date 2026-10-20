import os, sqlite3, tempfile, unittest
from datetime import datetime, timedelta

from app import backup
from app.analysis import Analysis
from app.db import connect, init_schema
from app.recurring import Recurring
from app.repo import Repo
from app.seed import ensure_defaults


def make():
    r = Repo(connect(":memory:"))
    ensure_defaults(r)
    return r


class Step8(unittest.TestCase):
    def test_people_order_and_migration(self):
        r = make()
        a, b, c = r.add_person("أ"), r.add_person("ب"), r.add_person("ج")
        self.assertEqual([p["name"] for p in r.list_people()], ["أ", "ب", "ج"])
        r.move_person(c, -1)
        r.move_person(c, -1)
        self.assertEqual([p["name"] for p in r.list_people()], ["ج", "أ", "ب"])
        r.move_person(c, -1)                      # already first: no change
        self.assertEqual(r.list_people()[0]["name"], "ج")
        r.move_person(a, 1)
        self.assertEqual([p["name"] for p in r.list_people()], ["ج", "ب", "أ"])
        # an old (v3) database without sort_order is upgraded and keeps its order
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript("CREATE TABLE people(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE);"
                           "INSERT INTO people(name) VALUES('x'),('y');")
        init_schema(conn)
        self.assertEqual([p[0] for p in conn.execute("SELECT name FROM people ORDER BY sort_order,id")], ["x", "y"])

    def test_main_wallet(self):
        r = make()
        ws = r.list_wallets()
        self.assertEqual(r.main_wallet_id(), ws[0]["id"])
        r.set_main_wallet(ws[1]["id"])
        self.assertEqual(r.main_wallet_id(), ws[1]["id"])
        r.archive_wallet(ws[1]["id"])             # archived main falls back to the first active wallet
        self.assertEqual(r.main_wallet_id(), ws[0]["id"])

    def test_recurring_only_reports(self):
        r = make()
        w = r.list_wallets()[0]
        rc = Recurring(r)
        rc.add("expense", w["id"], 1000, "monthly", "2026-08-31")
        before = r.balance(w["id"])
        p = rc.pending("2026-10-15")
        self.assertEqual((p["rules"], p["count"]), (1, 2))
        self.assertEqual(r.balance(w["id"]), before)       # nothing created by pending()
        self.assertEqual(rc.run_due("2026-10-15"), 2)
        self.assertEqual(rc.pending("2026-10-15")["count"], 0)

    def test_backup_schedule(self):
        r = make()
        self.assertEqual(backup.auto_settings(r), {"enabled": True, "every": 1, "keep": 7})
        r.set_setting("backup_every_days", "7")
        r.set_setting("backup_keep", "5")
        with tempfile.TemporaryDirectory() as d:
            t0 = datetime.now()
            self.assertTrue(backup.run_auto_backup(r, d, now=t0))
            self.assertIsNone(backup.run_auto_backup(r, d, now=t0 + timedelta(days=3)))   # not a week yet
            self.assertTrue(backup.run_auto_backup(r, d, now=t0 + timedelta(days=8)))
            r.set_setting("auto_backup", "0")
            self.assertIsNone(backup.run_auto_backup(r, d, now=t0 + timedelta(days=30)))

    def test_keep_last_n(self):
        r = make()
        with tempfile.TemporaryDirectory() as d:
            for i in range(8):
                backup.create_backup(r, d, keep=5)
                os.utime(os.path.join(d, sorted(os.listdir(d))[-1]), None)
            self.assertLessEqual(len([f for f in os.listdir(d) if f.startswith("masarif-")]), 5)


class LockAndReminder(unittest.TestCase):
    def test_password_flow(self):
        from app import lock
        from app.repo import AppError
        r = make()
        self.assertFalse(lock.has_password(r))
        with self.assertRaises(AppError):
            lock.set_option(r, "app", True)                  # needs a password first
        with self.assertRaises(AppError):
            lock.set_password(r, "12")                       # too short
        code = lock.set_password(r, "1234")
        self.assertEqual(len(code), 8)
        self.assertNotEqual(r.get_setting("lock_hash"), "1234")   # never stored in clear
        self.assertTrue(lock.check_password(r, "1234"))
        self.assertFalse(lock.check_password(r, "9999"))
        with self.assertRaises(AppError):
            lock.set_password(r, "5678", current="bad")      # changing needs the current password
        lock.set_password(r, "5678", current="1234")
        self.assertTrue(lock.check_password(r, "5678"))
        lock.set_option(r, "more", True)
        self.assertEqual(lock.options(r), {"password": True, "app": False, "more": True, "bio": False})

    def test_throttle_and_recovery(self):
        from app import lock
        from app.repo import AppError
        r = make()
        code = lock.set_password(r, "1234")
        for _ in range(lock.MAX_FREE_ATTEMPTS):
            lock.check_password(r, "x")
        with self.assertRaises(AppError):
            lock.check_password(r, "1234")                   # blocked for a while even with the right one
        lock._attempts.update(n=0, until=0.0)
        self.assertFalse(lock.recover(r, "WRONGCOD"))
        self.assertTrue(lock.recover(r, code.lower()))       # case-insensitive
        self.assertFalse(lock.has_password(r))
        self.assertEqual(lock.options(r)["more"], False)

    def test_reminder_varies_and_mentions_recurring(self):
        from app import reminder
        import random
        r = make()
        seen = []
        for i in range(6):
            seen.append(reminder.lines(r, "2026-10-19", random.Random(i))[0])
        self.assertGreater(len(set(seen)), 3)
        self.assertTrue(all(seen[i] != seen[i + 1] for i in range(5)))   # never the same twice in a row
        w = r.list_wallets()[0]["id"]
        Recurring(r).add("expense", w, 1000, "monthly", "2026-10-01")
        self.assertEqual(len(reminder.lines(r, "2026-10-19")), 2)        # no-transaction line + recurring line
        r.set_setting("lang", "en")
        self.assertFalse(any("\u0600" <= ch <= "\u06ff" for ch in reminder.lines(r, "2026-10-19")[0]))   # English wording
