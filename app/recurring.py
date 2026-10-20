"""Recurring transactions (rent, salary, subscriptions...). Due rules are only REPORTED (pending());
transactions are created when the user asks (run_due)."""
from typing import Optional

from . import money
from .dates import add_period
from .repo import AppError, NotFound, Repo, _rows

FREQUENCIES = {"daily": "يومي", "weekly": "أسبوعي", "monthly": "شهري", "yearly": "سنوي"}
MAX_CATCH_UP = 500


class Recurring:
    def __init__(self, repo: Repo):
        self.repo = repo
        self.conn = repo.conn

    def add(self, kind: str, wallet_id: int, amount, frequency: str, start_date: str, every: int = 1,
            category_id: Optional[int] = None, person_id: Optional[int] = None, note: str = "",
            end_date: Optional[str] = None) -> int:
        if kind not in ("expense", "income"):
            raise AppError("نوع المعاملة غير صحيح")
        if frequency not in FREQUENCIES:
            raise AppError("نوع التكرار غير صحيح")
        every = int(every or 1)
        if every < 1 or every > 365:
            raise AppError("الفاصل بين التكرارات غير صحيح")
        minor = money.to_minor(amount, self.repo.get_wallet(wallet_id)["currency"])
        if minor <= 0:
            raise AppError("المبلغ لازم يكون أكبر من صفر")
        self.repo._check_category(category_id, kind)
        if end_date and end_date < start_date:
            raise AppError("تاريخ النهاية قبل تاريخ البداية")
        with self.conn:
            return self.conn.execute(
                "INSERT INTO recurring(kind,wallet_id,amount,category_id,person_id,note,frequency,every,start_date,end_date) "
                "VALUES(?,?,?,?,?,?,?,?,?,?)",
                (kind, wallet_id, minor, category_id, person_id, note.strip(), frequency, every, start_date,
                 end_date or None)).lastrowid

    def get(self, rid: int) -> dict:
        rows = self.list(rid=rid)
        if not rows:
            raise NotFound("القاعدة غير موجودة")
        return rows[0]

    def list(self, rid: Optional[int] = None) -> list:
        sql = """SELECT r.*, w.name AS wallet_name, w.currency AS currency, c.name AS category_name,
                        c.icon AS category_icon, c.color AS category_color, p.name AS person_name
                 FROM recurring r JOIN wallets w ON w.id=r.wallet_id
                 LEFT JOIN categories c ON c.id=r.category_id LEFT JOIN people p ON p.id=r.person_id"""
        args = ()
        if rid is not None:
            sql += " WHERE r.id=?"
            args = (rid,)
        out = _rows(self.conn.execute(sql + " ORDER BY r.active DESC, r.id", args))
        for r in out:
            nxt = add_period(r["start_date"], r["frequency"], r["done"] * r["every"])
            r["finished"] = bool(r["end_date"]) and nxt > r["end_date"]
            r["next_date"] = None if r["finished"] else nxt
        out.sort(key=lambda r: (not r["active"] or r["finished"], r["next_date"] or "9999", r["id"]))
        return out

    def set_active(self, rid: int, active: bool) -> None:
        self.get(rid)
        with self.conn:
            self.conn.execute("UPDATE recurring SET active=? WHERE id=?", (int(active), rid))

    def update(self, rid: int, amount=None, note: Optional[str] = None, end_date=...) -> None:
        r = self.get(rid)
        with self.conn:
            if amount is not None:
                minor = money.to_minor(amount, r["currency"])
                if minor <= 0:
                    raise AppError("المبلغ لازم يكون أكبر من صفر")
                self.conn.execute("UPDATE recurring SET amount=? WHERE id=?", (minor, rid))
            if note is not None:
                self.conn.execute("UPDATE recurring SET note=? WHERE id=?", (note.strip(), rid))
            if end_date is not ...:
                if end_date and end_date < r["start_date"]:
                    raise AppError("تاريخ النهاية قبل تاريخ البداية")
                self.conn.execute("UPDATE recurring SET end_date=? WHERE id=?", (end_date or None, rid))

    def delete(self, rid: int) -> None:
        """Removes the rule; transactions it already created stay."""
        self.get(rid)
        with self.conn:
            self.conn.execute("DELETE FROM recurring WHERE id=?", (rid,))

    def pending(self, today: str) -> dict:
        """What is due but NOT created yet: {'rules': n, 'count': occurrences, 'items': [rule dicts]}."""
        items, total = [], 0
        for r in self.list():
            if not r["active"] or not r["next_date"] or r["next_date"] > today:
                continue
            n, nxt, done = 0, r["next_date"], r["done"]
            while nxt and nxt <= today and n < MAX_CATCH_UP:
                n += 1
                done += 1
                nxt = add_period(r["start_date"], r["frequency"], done * r["every"])
                if r["end_date"] and nxt > r["end_date"]:
                    break
            items.append({**r, "pending": n})
            total += n
        return {"rules": len(items), "count": total, "items": items}

    def run_due(self, today: str) -> int:
        """Create every occurrence up to `today` (catches up after days without opening the app)."""
        created = 0
        for r in self.list():
            if not r["active"]:
                continue
            adder = self.repo.add_expense if r["kind"] == "expense" else self.repo.add_income
            n = 0
            while r["next_date"] and r["next_date"] <= today and n < MAX_CATCH_UP:
                tx = adder(r["wallet_id"], money.from_minor(r["amount"], r["currency"]), category_id=r["category_id"],
                           person_id=r["person_id"], note=r["note"], date=r["next_date"])
                with self.conn:
                    self.conn.execute("UPDATE transactions SET recurring_id=? WHERE id=?", (r["id"], tx))
                    self.conn.execute("UPDATE recurring SET done=done+1 WHERE id=?", (r["id"],))
                r = self.get(r["id"])
                n += 1
                created += 1
        return created
