"""PDF report: summary, charts (activity, categories donut, histogram, weekdays, people, wallets), smart notes,
then every transaction. Arabic (right-to-left) or English. Uses reportlab (imported lazily) and the bundled
DejaVu Sans font; Arabic shaping/ordering is done by app/arabic.py.
"""
import math
import os
from datetime import datetime

from . import arabic, money
from .analysis import Analysis
from .i18n import tr
from .palette import pick
from .ui import vm

FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")
A4 = (595.27, 841.89)
M = 34                                   # page margin
INK, MUTED, LINE, SOFT = "#14284B", "#5A6A85", "#E3D6BC", "#FFF3DA"
GREEN, RED, BLUE, AMBER = "#0E9F6E", "#E5484D", "#0891B2", "#E0A100"
TONES = {"good": ("#D9F7EA", GREEN), "warn": ("#FFF0C2", AMBER), "bad": ("#FFE3E1", RED), "info": ("#D5F3FA", BLUE)}


class Report:
    def __init__(self, path, lang="ar", title=""):
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.pdfgen import canvas
        self.pm = pdfmetrics
        for name, file in (("DV", "DejaVuSans.ttf"), ("DVB", "DejaVuSans-Bold.ttf")):
            try:
                pdfmetrics.getFont(name)
            except KeyError:
                pdfmetrics.registerFont(TTFont(name, os.path.join(FONT_DIR, file)))
        self.c = canvas.Canvas(path, pagesize=A4)
        self.c.setTitle(title or tr("تقرير المصاريف", lang))
        self.lang, self.rtl = lang, lang == "ar"
        self.W, self.H = A4
        self.page_no = 0
        self.y = 0
        self.title = title
        self._new_page(first=True)

    # ------------------------------------------------------------ text helpers
    def t(self, s):
        return tr(str(s), self.lang)

    def width(self, s, size=9, bold=False):
        return self.pm.stringWidth(arabic.visual(s, self.rtl), "DVB" if bold else "DV", size)

    def text(self, x, y, s, size=9, bold=False, color=INK, align=None):
        """Draw one logical line. align: 'start' (right edge in Arabic) | 'end' | 'center'; x is the anchor."""
        s = self.t(s)
        v = arabic.visual(s, self.rtl)
        c = self.c
        c.setFont("DVB" if bold else "DV", size)
        c.setFillColor(color)
        align = align or "start"
        right = (align == "start") == self.rtl
        if align == "center":
            c.drawCentredString(x, y, v)
        elif right:
            c.drawRightString(x, y, v)
        else:
            c.drawString(x, y, v)

    def lines(self, s, width, size=9, bold=False, logical=False):
        """Wrapped lines: on-paper order (to draw directly), or logical=True (to pass to text())."""
        s = self.t(s)
        return arabic.wrap(s, width, lambda v: self.pm.stringWidth(v, "DVB" if bold else "DV", size), self.rtl, logical)

    def x_start(self, x0, w):          # where text starts inside a box [x0, x0+w]
        return x0 + w - 4 if self.rtl else x0 + 4

    def x_end(self, x0, w):
        return x0 + 4 if self.rtl else x0 + w - 4

    # --------------------------------------------------------------- pages
    def _new_page(self, first=False):
        if not first:
            self._footer()
            self.c.showPage()
        self.page_no += 1
        self.y = self.H - M
        if not first:
            self.text(self.W - M if self.rtl else M, self.y - 4, self.title, 8, color=MUTED)
            self.c.setStrokeColor(LINE)
            self.c.line(M, self.y - 9, self.W - M, self.y - 9)
            self.y -= 24

    def _footer(self):
        self.text(self.W / 2, 18, f"{self.page_no}", 8, color=MUTED, align="center")

    def need(self, h):
        if self.y - h < M + 14:
            self._new_page()

    def finish(self):
        self._footer()
        self.c.save()

    # ------------------------------------------------------------- blocks
    def heading(self, s, color=INK):
        self.need(40)
        self.y -= 10
        x = self.W - M if self.rtl else M
        self.text(x, self.y, s, 13, True, color)
        self.c.setStrokeColor(BLUE)
        self.c.setLineWidth(1.5)
        self.c.line(M, self.y - 5, self.W - M, self.y - 5)
        self.c.setLineWidth(1)
        self.y -= 20

    def kpi_grid(self, kpis, cols=4):
        gap, h = 8, 46
        w = (self.W - 2 * M - gap * (cols - 1)) / cols
        for i in range(0, len(kpis), cols):
            self.need(h + 6)
            for j, k in enumerate(kpis[i:i + cols]):
                col = j if not self.rtl else cols - 1 - j
                x0 = M + col * (w + gap)
                self.c.setFillColor(SOFT)
                self.c.setStrokeColor(LINE)
                self.c.roundRect(x0, self.y - h, w, h, 8, fill=1, stroke=1)
                tone = {"income": GREEN, "expense": RED}.get(k.get("tone"), INK)
                self.text(self.x_start(x0, w), self.y - 15, k["label"], 8, color=MUTED)
                size = 11 if self.width(k["value"], 11, True) < w - 10 else 8.5
                self.text(self.x_start(x0, w), self.y - 33, k["value"], size, True, tone)
            self.y -= h + gap

    def bars(self, points, height=110, label_every=1):
        """points: [{'label', 'bars': [(fraction, color)], 'top': text}]"""
        n = max(1, len(points))
        self.need(height + 40)
        inner = self.W - 2 * M
        slot = inner / n
        nb = max(len(p["bars"]) for p in points) if points else 1
        bw = max(2.5, min(26, (slot - 4) / nb - 1))
        base = self.y - height - 6
        self.c.setStrokeColor(LINE)
        self.c.line(M, base, self.W - M, base)
        for i, p in enumerate(points):
            idx = i if not self.rtl else n - 1 - i
            cx = M + slot * idx + slot / 2
            total_w = bw * nb + (nb - 1)
            for b, (f, color) in enumerate(p["bars"]):
                bx = cx - total_w / 2 + b * (bw + 1)
                h = max(1.5, height * f) if f > 0 else 1.5
                self.c.setFillColor(color if f > 0 else LINE)
                self.c.rect(bx, base, bw, h, fill=1, stroke=0)
            if p.get("top") and nb == 1 and slot > 22:
                self.text(cx, base + max(1.5, height * p["bars"][0][0]) + 3, p["top"], 6.5, color=MUTED, align="center")
            if i % label_every == 0:
                self.text(cx, base - 10, p["label"], 7, color=MUTED, align="center")
        self.y = base - 22

    def hbars(self, rows, color=BLUE):
        """rows: [{'name','amount_text','fraction','pct'}] horizontal bars."""
        label_w, num_w = 120, 118
        bar_w = self.W - 2 * M - label_w - num_w - 12
        for r in rows:
            self.need(18)
            if self.rtl:
                lx, bx, nx = self.W - M, self.W - M - label_w - 6 - bar_w, M
            else:
                lx, bx, nx = M, M + label_w + 6, self.W - M
            self.text(lx, self.y - 8, r["name"], 8.5, align="start")
            left = bx if not self.rtl else bx
            self.c.setFillColor(SOFT)
            self.c.rect(left, self.y - 10, bar_w, 9, fill=1, stroke=0)
            fw = max(1.5, bar_w * r["fraction"])
            self.c.setFillColor(color)
            if self.rtl:
                self.c.rect(left + bar_w - fw, self.y - 10, fw, 9, fill=1, stroke=0)
            else:
                self.c.rect(left, self.y - 10, fw, 9, fill=1, stroke=0)
            self.text(nx, self.y - 8, f"{r['amount_text']}  ({r['pct']}%)", 8, color=MUTED, align="end")
            self.y -= 16
        self.y -= 4

    def donut(self, cx, cy, radius, slices):
        total = sum(s["value"] for s in slices) or 1
        ang = 90.0
        c = self.c
        for s in slices:
            extent = -360.0 * s["value"] / total
            c.setFillColor(s["color"])
            c.setStrokeColor("#FFFFFF")
            c.wedge(cx - radius, cy - radius, cx + radius, cy + radius, ang, extent, fill=1, stroke=1)
            ang += extent
        c.setFillColor("#FFFFFF")
        c.circle(cx, cy, radius * 0.55, fill=1, stroke=0)

    def table(self, cols, rows, head=True, size=8):
        """cols: [{'title', 'w' (fraction), 'align': 'start'|'end', 'color_key'}]; rows: list of dict col-key -> text.
        Columns are laid out from the reading start (right in Arabic)."""
        inner = self.W - 2 * M
        widths = [inner * c["w"] for c in cols]
        xs, acc = [], 0
        for w in widths:
            xs.append((self.W - M - acc - w) if self.rtl else (M + acc))
            acc += w

        def header():
            self.need(22)
            self.c.setFillColor(BLUE)
            self.c.rect(M, self.y - 16, inner, 16, fill=1, stroke=0)
            for c, x0, w in zip(cols, xs, widths):
                self.text(self.x_start(x0, w) if c.get("align", "start") == "start" else self.x_end(x0, w),
                          self.y - 11.5, c["title"], size, True, "#FFFFFF", c.get("align", "start"))
            self.y -= 16

        if head:
            header()
        for n, r in enumerate(rows):
            cells = []
            for c, w in zip(cols, widths):
                v = r.get(c["key"], "")
                cells.append(self.lines(v, w - 8, size) if c.get("wrap") else [arabic.visual(self.t(v), self.rtl)])
            nlines = max(len(x) for x in cells)
            h = max(15, nlines * (size + 3) + 4)
            if self.y - h < M + 14:
                self._new_page()
                if head:
                    header()
            if n % 2 == 0:
                self.c.setFillColor("#FFF9EC")
                self.c.rect(M, self.y - h, inner, h, fill=1, stroke=0)
            for c, x0, w, lines in zip(cols, xs, widths, cells):
                color = r.get("_color", {}).get(c["key"], INK)
                for li, v in enumerate(lines):
                    ay = self.y - 10.5 - li * (size + 3)
                    self.c.setFont("DVB" if c.get("bold") else "DV", size)
                    self.c.setFillColor(color)
                    start = c.get("align", "start") == "start"
                    px = self.x_start(x0, w) if start else self.x_end(x0, w)
                    if start == self.rtl:
                        self.c.drawRightString(px, ay, v)
                    else:
                        self.c.drawString(px, ay, v)
            self.y -= h
        self.y -= 6


# ------------------------------------------------------------------ content
def describe(repo, scope, f, search, lang, today):
    """Human description of what the report covers (period + active filters)."""
    t = lambda s: tr(s, lang)  # noqa: E731
    parts = []
    if scope.get("all"):
        parts.append(t("كل المعاملات"))
    elif scope.get("filtered"):
        span = scope.get("span")
        parts.append(t("المعاملات المفلترة") + (f": {span[0]} → {span[1]}" if span else ""))
    else:
        span = scope.get("span")
        parts.append(f"{span[0]} → {span[1]}" if span else t("كل الفترة"))
    if f and scope.get("filtered"):
        names = {w["id"]: w["name"] for w in repo.list_wallets(include_archived=True)}
        if f["kinds"]:
            parts.append(t("النوع") + ": " + "، ".join(t(vm.KIND_LABELS[k]) for k in sorted(f["kinds"])))
        if f["wallets"]:
            parts.append(t("المحفظة") + ": " + "، ".join(names.get(i, "?") for i in sorted(f["wallets"])))
        if f["people"]:
            pn = {p["id"]: p["name"] for p in repo.list_people()}
            parts.append(t("الشخص") + ": " + "، ".join(pn.get(i, "?") for i in sorted(f["people"])))
        if f["categories"]:
            parts.append(t("الفئة") + f": {len(f['categories'])}" + (" (" + t("استثناء") + ")" if f["exclude_categories"] else ""))
        if f["min"] or f["max"]:
            parts.append(t("المبلغ") + f": {f['min'] or '0'} – {f['max'] or '∞'}")
    if search:
        parts.append(t("بحث") + f": {search}")
    return " · ".join(parts)


def _tx_rows(rows, today, lang):
    out = []
    for t in rows:
        v = vm.tx_row(t, today)
        kind = v["kind"]
        cat = v["title"]
        color = {"income": GREEN, "expense": RED}.get(kind, BLUE)
        out.append({"date": t["date"], "cat": cat, "person": t.get("person_name") or "", "wallet": t["wallet_name"],
                    "note": t["note"] or "", "amount": v["amount_text"] + (f"  → {v['recv_text']}" if v["recv_text"] else ""),
                    "_color": {"amount": color}})
    return out


def build_pdf(path, repo, scope, currency, lang="ar", today=None, filters=None, search="", title=None):
    """Write the report to `path`. scope: {'rows': [...], 'span': (a, b) | None, 'filtered': bool, 'all': bool}."""
    today = today or datetime.now().date().isoformat()
    rate = repo.get_rate()
    an = Analysis(scope["rows"], currency, rate, scope.get("span"))
    title = title or tr("مصاريفي", lang) + " — " + tr("تقرير المصاريف", lang)
    R = Report(path, lang, title)
    x0 = R.W - M if R.rtl else M

    # ---- cover
    R.text(x0, R.y - 14, title, 18, True, BLUE)
    R.y -= 36
    for line in R.lines(describe(repo, scope, filters, search, lang, today), R.W - 2 * M, 9, logical=True):
        R.text(x0, R.y, line, 9, color=MUTED)
        R.y -= 13
    R.text(x0, R.y, f"{tr('تاريخ التقرير', lang)}: {today} · {tr('العملة', lang)}: {currency} · "
                    f"{tr('سعر الصرف', lang)}: {rate:,.0f}", 8, color=MUTED)
    R.y -= 8

    s = vm.summary_view(an, None)
    if s["empty"]:
        R.heading("لا توجد بيانات في هذه الفترة")
    else:
        # ---- summary
        R.heading("ملخص")
        R.kpi_grid([{"label": k["label"], "value": k["value"] + (" " + money.SYMBOLS[currency] if currency == "IQD" and "%" not in k["value"] else ""),
                     "tone": k["tone"]} for k in s["kpis"]])
        tl = s["timeline"]
        if tl["points"]:
            R.heading(tl["title"])
            R.text(x0, R.y + 2, "■ " + R.t("دخل"), 8, color=GREEN)
            R.text(x0 - (50 if R.rtl else -50), R.y + 2, "■ " + R.t("مصروف"), 8, color=RED)
            R.y -= 8
            pts = [{"label": p["label"], "bars": [(p["income_h"], GREEN), (p["expense_h"], RED)]} for p in tl["points"]]
            n = len(pts)
            R.bars(pts, 110, label_every=5 if tl["mode"] == "day" and n > 10 else (2 if n > 8 else 1))
        # ---- categories
        for kind, head in (("expense", "المصاريف"), ("income", "الدخل")):
            cv = vm.categories_view(an, None, kind)
            if cv["empty"]:
                continue
            R.need(230)
            R.heading("الفئات — " + R.t(head))
            shown = cv["rows"][:10]
            kids = 2 if len(shown) <= 6 else 0
            est = sum(13 + 10.5 * min(kids, len(r["children"])) for r in shown)
            R.need(max(175, est + 20))
            cy, rad = R.y - 80, 70
            cx = (M + 90) if R.rtl else (R.W - M - 90)
            R.donut(cx, cy, rad, cv["slices"])
            R.text(cx, cy + 2, cv["total_text"], 9, True, align="center")
            R.text(cx, cy - 10, cv["unit"], 8, color=MUTED, align="center")
            lx0 = (M + 190) if R.rtl else M
            lw = R.W - 2 * M - 190
            y = R.y - 6
            for r in shown:
                R.c.setFillColor(r["color"])
                dot = (lx0 + lw - 5) if R.rtl else (lx0 + 5)
                R.c.circle(dot, y + 3, 3.5, fill=1, stroke=0)
                ax = (lx0 + lw - 14) if R.rtl else (lx0 + 14)
                R.text(ax, y, r["name"], 9, True, align="start")
                R.text(lx0 + 2 if R.rtl else lx0 + lw - 2, y, f"{r['amount_text']}  ({r['pct']}%)", 8.5, color=MUTED, align="end")
                y -= 13
                for ch in r["children"][:kids]:
                    R.text(ax - 10 if R.rtl else ax + 10, y, "· " + ch["name"], 7.5, color=MUTED, align="start")
                    R.text(lx0 + 2 if R.rtl else lx0 + lw - 2, y, ch["amount_text"], 7.5, color=MUTED, align="end")
                    y -= 10.5
            R.y = min(cy - rad - 14, y - 6)
            if len(cv["rows"]) > len(shown):
                R.text(x0, R.y, f"+ {len(cv['rows']) - len(shown)} " + R.t("فئات أخرى"), 8, color=MUTED)
                R.y -= 12
        # ---- analysis
        a = vm.analysis_view(an, today)
        if not a["empty"]:
            if a["histogram"]:
                R.heading("توزيع حجم المصاريف (هستوغرام)")
                R.bars([{"label": h["label"], "bars": [(h["fraction"], BLUE)], "top": str(h["count"])} for h in a["histogram"]], 100)
                R.y += 6
                R.text(x0, R.y, "كل عمود = عدد المعاملات ضمن نطاق مبلغ، والرقم تحته هو الحد الأعلى للنطاق", 7.5, color=MUTED)
                R.y -= 10
            R.heading("الصرف حسب أيام الأسبوع")
            R.bars([{"label": d["label"], "bars": [(d["fraction"], AMBER if d["peak"] else BLUE)], "top": d["top"]} for d in a["weekdays"]], 90)
            if a["people"]:
                R.heading("حسب الشخص")
                R.hbars(a["people"][:12], "#8E6CEF")
            if a["wallets"]:
                R.heading("حسب المحفظة")
                R.hbars(a["wallets"][:12], "#2EC27E")
            if a["top"]:
                R.heading("أكبر 5 مصاريف")
                R.table([{"key": "n", "title": "#", "w": 0.06}, {"key": "title", "title": "الفئة", "w": 0.34, "wrap": True},
                         {"key": "sub", "title": "التاريخ", "w": 0.36, "wrap": True},
                         {"key": "amount", "title": "المبلغ", "w": 0.24, "align": "end", "bold": True}],
                        [{"n": str(t["rank"]), "title": t["title"], "sub": t["subtitle"], "amount": t["amount_text"],
                          "_color": {"amount": RED}} for t in a["top"]])
        if s["insight_items"]:
            R.heading("ملاحظات ذكية")
            for it in s["insight_items"]:
                bg, fg = TONES[it["tone"]]
                lines = R.lines(it["text"], R.W - 2 * M - 22, 9, logical=True)
                h = len(lines) * 12 + 8
                R.need(h + 4)
                R.c.setFillColor(bg)
                R.c.roundRect(M, R.y - h, R.W - 2 * M, h, 6, fill=1, stroke=0)
                R.c.setFillColor(fg)
                R.c.rect(R.W - M - 4 if R.rtl else M, R.y - h, 4, h, fill=1, stroke=0)
                for i, ln in enumerate(lines):
                    R.text(R.W - M - 12 if R.rtl else M + 12, R.y - 12 - i * 12, ln, 9, color=INK)
                R.y -= h + 5

    # ---- transactions
    rows = scope["rows"]
    R.heading(R.t("المعاملات") + f" ({len(rows)})")
    cols = [{"key": "date", "title": "التاريخ", "w": 0.13}, {"key": "cat", "title": "الفئة", "w": 0.24, "wrap": True},
            {"key": "person", "title": "الشخص", "w": 0.11, "wrap": True}, {"key": "wallet", "title": "المحفظة", "w": 0.13, "wrap": True},
            {"key": "note", "title": "الملاحظة", "w": 0.22, "wrap": True},
            {"key": "amount", "title": "المبلغ", "w": 0.17, "align": "end", "bold": True}]
    if rows:
        R.table(cols, _tx_rows(rows, today, lang), size=7.5)
    else:
        R.text(x0, R.y, "لا توجد معاملات مطابقة", 10, color=MUTED)
    R.finish()
    return path
