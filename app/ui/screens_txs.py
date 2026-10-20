"""Transactions tab = list + statistics in one place.

No filter  -> the selected month (month navigator).
Any filter -> exactly the filtered rows, for the list AND every chart.
Sub-tabs: list | summary | categories | analysis. A summary strip is always visible.
"""
from datetime import datetime

import flet as ft

from .pdf_export import open_pdf_sheet
from . import kit, theme as T, vm
from .rows import empty_state, tx_tile
from .. import money
from ..stats import NO_CATEGORY, NO_PERSON, month_label, shift_month

QUICK_KINDS = [("expense", "مصروف"), ("income", "دخل"), ("transfer", "تحويل")]
ORDERS = [("newest", "الأحدث"), ("oldest", "الأقدم"), ("highest", "الأعلى مبلغاً"), ("lowest", "الأقل مبلغاً")]
VIEWS = [("list", "المعاملات"), ("summary", "ملخص"), ("cats", "الفئات"), ("analysis", "تحليل")]


def card(title, *items, sub=None):
    head = [kit.txt(title, 15, True)] + ([kit.txt(sub, 12, color=T.MUTED)] if sub else [])
    return kit.box(kit.col([kit.col(head, spacing=2), *items], spacing=12), padding=16)


def legend_dot(color, label):
    return kit.row([ft.Container(width=10, height=10, bgcolor=color, border_radius=3), kit.txt(label, 12, color=T.MUTED)],
                   spacing=5)


def tappable(content, on_click):
    return ft.Container(content, ink=True, border_radius=10, padding=ft.padding.symmetric(vertical=3), on_click=on_click)


def hbar(label, amount, fraction, color, width, sub=""):
    return kit.col([kit.between(kit.row([kit.txt(label, 14, True), kit.txt(sub, 12, color=T.MUTED)], spacing=6),
                                kit.txt(amount, 14, True)),
                    kit.progress(fraction, color, width)], spacing=5)


# ------------------------------------------------------------------ pieces
def header_controls(ui, scope, an):
    f = ui.filters

    def on_search(e):
        ui.search = e.control.value

    search = ft.TextField(
        value=ui.search, hint_text="ابحث بالملاحظة أو الفئة أو الشخص", on_change=on_search,
        on_submit=lambda e: ui.refresh(), prefix_icon=kit.icon_name("search"), border_radius=14, border_color=T.LINE,
        bgcolor=T.CARD, filled=True, text_size=14, content_padding=ft.padding.symmetric(horizontal=12, vertical=10),
        expand=True)
    n = ui.filters_active()
    filt_btn = ft.Container(
        content=kit.row([kit.icon("tune", 20, "#FFFFFF" if n else T.INK),
                         kit.txt(f"فلتر{f' ({n})' if n else ''}", 13, True, "#FFFFFF" if n else T.INK)], spacing=4),
        padding=ft.padding.symmetric(horizontal=12, vertical=11), border_radius=14, ink=True,
        bgcolor=T.PRIMARY if n else T.CARD, border=ft.border.all(1, T.PRIMARY if n else T.LINE),
        on_click=lambda e: open_filter_sheet(ui))

    def toggle_kind(k):
        f["kinds"] ^= {k}
        ui.refresh()

    def clear(e):
        ui.filters = ui.default_filters()
        ui.search = ""
        ui.refresh()

    chips = [kit.chip(label, k in f["kinds"], lambda e, k=k: toggle_kind(k)) for k, label in QUICK_KINDS]
    if scope["filtered"]:
        chips.append(kit.chip("مسح الفلاتر", False, clear, color=T.EXPENSE))
    return [kit.row([search, filt_btn], spacing=8), kit.hscroll(chips, 8)]


def period_switch(ui):
    """أسبوعي | شهري (| كل الفترة في الأرشيف)."""
    opts = [("week", "أسبوعي"), ("month", "شهري")] + ([("all", "كل الفترة")] if getattr(ui, "allow_all_time", False) else [])
    cur = "all" if getattr(ui, "all_time", False) else ui.period_mode

    def pick(v):
        ui.all_time = v == "all"
        if v != "all":
            ui.period_mode = v
        ui.stats_open_cat = None
        ui.refresh()

    return kit.segmented(opts, cur, pick)


def scope_bar(ui, scope):
    if scope["filtered"]:
        f = ui.filters
        per = dict(vm.PERIODS).get(f["period"], "")
        if f["date_from"] or f["date_to"]:
            per = f"{f['date_from'] or '…'} ← {f['date_to'] or '…'}"
        txt = "نتائج الفلتر" + (f" · {per}" if per and f["period"] != "all" or f["date_from"] or f["date_to"] else " · كل الفترات")
        return kit.box(kit.row([kit.icon("filter_alt", 20, T.PRIMARY), kit.txt(txt, 14, True, T.PRIMARY)], spacing=8),
                       bg=T.PRIMARY_SOFT, border=None, padding=12)

    if scope.get("all_time"):
        return kit.box(kit.row([kit.icon("history", 20, T.PRIMARY), kit.txt("كل بيانات الأرشيف", 14, True, T.PRIMARY)], spacing=8),
                       bg=T.PRIMARY_SOFT, border=None, padding=12)

    if scope.get("mode") == "week":
        def move(d):
            ui.stats_week = vm.shift_week(ui.stats_week, d)
            ui.refresh()

        label = vm.week_label(ui.stats_week)
        reset = lambda e: (setattr(ui, "stats_week", vm.week_start(ui.today)), ui.refresh())
    else:
        def move(d):
            ui.stats_ym = shift_month(ui.stats_ym, d)
            ui.stats_open_cat = None
            ui.refresh()

        label = month_label(ui.stats_ym)
        reset = lambda e: (setattr(ui, "stats_ym", ui.today[:7]), ui.refresh())
    return kit.between(kit.icon_btn("chevron_right", lambda e: move(-1)),
                       ft.Container(kit.txt(label, 17, True), ink=True, border_radius=8,
                                    padding=ft.padding.symmetric(horizontal=10, vertical=4), on_click=reset),
                       kit.icon_btn("chevron_left", lambda e: move(1)))


def summary_strip(ui, an):
    v = vm.strip_view(an, ui.filters["kinds"])

    def cell(label, value, color):
        size = 18 if len(value) <= 10 else 15 if len(value) <= 13 else 12
        return ft.Container(kit.col([kit.txt(label, 12, color=T.HERO_TEXT), kit.txt(value, size, True, color, no_wrap=True)],
                                    spacing=3), expand=True)

    cells = []
    if v["show_income"]:
        cells.append(cell("دخل", v["income"], T.MINT))
    if v["show_expense"]:
        cells.append(cell("مصروف", v["expense"], "#FFD3C8"))
    if v["show_income"] and v["show_expense"]:
        cells.append(cell("الصافي", v["net"], "#FFFFFF" if v["net_good"] else "#FFD3C8"))
    return kit.hero(kit.row(cells, spacing=8), padding=ft.padding.symmetric(horizontal=16, vertical=12), radius=18)


# ---------------------------------------------------------------- drill-down
def open_drill(ui, scope, title, pred, subtitle=""):
    """Bottom sheet with every transaction of the current scope that matches `pred`."""
    rows = [t for t in scope["rows"] if pred(t)]
    ref = {}

    class _Click:  # tiles inside the sheet: close it, then show the transaction
        today = ui.today

        @staticmethod
        def show_tx(tx_id):
            ui.page.close(ref["s"])
            ui.show_tx(tx_id)

    cur = ui.currency
    rate = ui.repo.get_rate()
    inc = sum(money.convert_minor(t["amount"], t["currency"], cur, rate) for t in rows if t["kind"] == "income")
    exp = sum(money.convert_minor(t["amount"], t["currency"], cur, rate) for t in rows if t["kind"] == "expense")
    sums = []
    if inc:
        sums.append(kit.txt("+" + money.fmt(inc, cur, symbol=False), 14, True, T.INCOME))
    if exp:
        sums.append(kit.txt("−" + money.fmt(exp, cur, symbol=False), 14, True, T.EXPENSE))
    body = tx_list(_Click, rows, ui.page, ui.today)
    head = [kit.between(kit.txt(title, 18, True, expand=True), kit.icon_btn("close", lambda e: ui.page.close(ref["s"]))),
            kit.row([kit.txt(f"{len(rows)} معاملة" + (f" · {subtitle}" if subtitle else ""), 12, color=T.MUTED)] + sums,
                    spacing=12, wrap=True)]
    ref["s"] = ui.open_sheet(kit.col(head + [kit.col(body, spacing=12, scroll=True, expand=True)], spacing=10, expand=True))


def tx_list(click_ui, all_rows, page, today):
    """Day-grouped transaction tiles, rendered in batches (40, then +80 per 'show more' tap): a Flet control per row
    is expensive and an old archive can hold tens of thousands of transactions."""
    if not all_rows:
        return [empty_state("لا توجد معاملات مطابقة")]
    holder = ft.Column(spacing=12)
    state = {"n": 0, "last": None}

    def more_button():
        left = len(all_rows) - state["n"]
        btn = ft.Container(kit.big_button(f"عرض المزيد ({left} متبقية)", lambda e: load(PAGE_NEXT), outline=True),
                           padding=ft.padding.only(top=6))
        btn.data = "more"
        return btn

    def load(count):
        batch = [vm.tx_row(t, today) for t in all_rows[state["n"]:state["n"] + count]]
        state["n"] += len(batch)
        if holder.controls and getattr(holder.controls[-1], "data", None) == "more":
            holder.controls.pop()
        for g in vm.group_by_day(batch):
            if g["label"] != state["last"]:
                holder.controls.append(kit.txt(g["label"], 13, True, T.MUTED))
                state["last"] = g["label"]
            holder.controls.append(kit.box(kit.col([tx_tile(click_ui, r) for r in g["rows"]], spacing=0),
                                           padding=ft.padding.symmetric(horizontal=12, vertical=4)))
        if state["n"] < len(all_rows):
            holder.controls.append(more_button())
        if count != PAGE_FIRST:
            page.update()

    load(PAGE_FIRST)
    return [holder]


# ---------------------------------------------------------------- sub-views
PAGE_FIRST, PAGE_NEXT = 40, 80


def view_list(ui, scope):
    rows = scope["rows"]
    if not rows:
        return [empty_state("لا توجد معاملات مطابقة")]
    return [kit.txt(f"{len(rows)} معاملة", 12, color=T.MUTED)] + tx_list(ui, rows, ui.page, ui.today)


def view_summary(ui, scope, an, prev):
    d = vm.summary_view(an, prev)
    if d["empty"]:
        return [empty_state("لا توجد بيانات في هذه الفترة")]
    kw = (ui.w - 40 - 10) / 2
    cards = []
    for k in d["kpis"]:
        color = {"income": T.INCOME, "expense": T.EXPENSE}.get(k["tone"], T.INK)
        items = [kit.txt(k["label"], 12, color=T.MUTED), kit.txt(k["value"], 17, True, color)]
        if k["chip"]:
            items.append(kit.row([kit.badge(k["chip"]["text"], k["chip"]["tone"]), kit.txt(k["suffix"], 11, color=T.FAINT)], spacing=4))
        kind = {"الدخل": "income", "الصافي": "both", "نسبة الادخار": "both"}.get(k["label"], "expense")
        kinds = {"income": {"income"}, "expense": {"expense"}, "both": {"income", "expense"}}[kind]
        cards.append(kit.box(kit.col(items, spacing=4), width=kw,
                             on_click=lambda e, k=k, kinds=kinds: open_drill(ui, scope, k["label"], lambda t: t["kind"] in kinds)))
    grid = [kit.row(cards[i:i + 2], spacing=10) for i in range(0, len(cards), 2)]
    tl = d["timeline"]
    n = len(tl["points"])
    def bucket(p):
        key, month = p["key"], tl["mode"] == "month"
        return lambda e: open_drill(ui, scope, ("شهر " if month else "يوم ") + p["label"],
                                    lambda t: (t["date"][:7] == key if month else t["date"] == key) and t["kind"] != "transfer")

    pts = [{"label": p["label"] if tl["mode"] == "day" else p["label"][:4], "top": "", "on_click": bucket(p),
            "bars": [(p["income_h"], T.CHART_INCOME), (p["expense_h"], T.CHART_EXPENSE)]} for p in tl["points"]]
    chart = kit.columns_chart(pts, ui.w - 40 - 32, 110, label_every=5 if tl["mode"] == "day" and n > 10 else (2 if n > 8 else 1))
    spent_color = T.EXPENSE if d["spent_warn"] else T.PRIMARY
    out = grid + [
        card(tl["title"], chart, kit.row([legend_dot(T.CHART_INCOME, "دخل"), legend_dot(T.CHART_EXPENSE, "مصروف")], spacing=14),
             sub="اضغط على أي عمود لعرض معاملاته"),
        card("نسبة المصروف من الدخل",
             kit.between(kit.txt("—" if d["spent_pct"] is None else f"{d['spent_pct']}%", 22, True, spent_color), kit.txt("", 1)),
             kit.progress(d["spent_fraction"], spent_color, ui.w - 40 - 32, 10),
             kit.txt(d["spent_note"], 12, color=T.MUTED)),
    ]
    if d["insights"]:
        out.append(card("ملاحظات ذكية", *[
            ft.Container(kit.row([kit.icon(i["icon"], 20, T.TONE_ICON[i["tone"]]),
                                  kit.txt(i["text"], 14, color=T.TONE[i["tone"]][0], expand=True)], spacing=10,
                                 v_align=ft.CrossAxisAlignment.START),
                         bgcolor=T.TONE[i["tone"]][1], border_radius=12, padding=ft.padding.symmetric(horizontal=12, vertical=10))
            for i in d["insight_items"]]))
    return out


def view_cats(ui, scope, an, prev):
    d = vm.categories_view(an, prev, ui.stats_kind)

    def set_kind(k):
        ui.stats_kind = k
        ui.stats_open_cat = None
        ui.refresh()

    top = kit.segmented([("expense", "المصاريف"), ("income", "الدخل")], ui.stats_kind, set_kind)
    if d["empty"]:
        return [top, empty_state("لا توجد بيانات")]
    # tiny slices (< 3%) are merged into one grey "أخرى" slice so the ring stays readable; the list below keeps them all
    big = [x for x in d["slices"] if x["pct"] >= 3]
    rest = sum(x["value"] for x in d["slices"] if x["pct"] < 3)
    shown = [dict(x, title=f"{x['pct']}%" if x["pct"] >= 7 else "") for x in big]
    if rest:
        shown.append({"name": "أخرى", "value": rest, "pct": 0, "color": T.FAINT, "title": ""})
    center = kit.col([kit.txt("الإجمالي", 12, color=T.MUTED), kit.txt(d["total_text"], 17, True),
                      kit.txt(d["unit"], 11, color=T.MUTED), kit.txt(f"{len(d['rows'])} فئة", 11, color=T.FAINT)],
                     spacing=1, h_align=ft.CrossAxisAlignment.CENTER, align=ft.MainAxisAlignment.CENTER)
    donut = kit.donut(shown, size=230, hole=72, center=center)
    legend = ft.Row([ft.Container(
        kit.row([ft.Container(width=10, height=10, bgcolor=x["color"], border_radius=5),
                 kit.txt(x["name"], 12, True), kit.txt(f"{x['pct']}%", 12, color=T.MUTED)], spacing=6),
        padding=ft.padding.symmetric(horizontal=10, vertical=6), border_radius=14, border=ft.border.all(1.5, x["color"]))
        for x in d["slices"][:8]], wrap=True, spacing=8, run_spacing=8, alignment=ft.MainAxisAlignment.CENTER)
    width = ui.w - 40 - 32
    rows = []
    kind = ui.stats_kind

    def top_pred(name):
        return lambda t: t["kind"] == kind and (t["parent_category_name"] or t["category_name"] or NO_CATEGORY) == name

    def sub_pred(parent, name):
        return lambda t: t["kind"] == kind and t["category_name"] == name and t["parent_category_name"] == parent

    for r in d["rows"]:
        def toggle(e, name=r["name"]):
            ui.stats_open_cat = None if ui.stats_open_cat == name else name
            ui.refresh()

        head = kit.between(kit.row([ft.Container(width=12, height=12, bgcolor=r["color"], border_radius=4),
                                    kit.txt(r["name"], 14, True), kit.txt(f"{r['pct']}%", 12, color=T.MUTED)], spacing=8),
                           kit.row([kit.txt(r["amount_text"], 14, True)] + (
                               [kit.icon_btn("expand_less" if ui.stats_open_cat == r["name"] else "expand_more", toggle,
                                             "الفئات الفرعية", color=T.MUTED, size=20)] if r["children"] else []), spacing=0))
        parts = [ft.Container(kit.col([head, kit.progress(r["pct"] / 100, r["color"], width)], spacing=6), ink=True,
                              border_radius=10, on_click=lambda e, r=r: open_drill(ui, scope, r["name"], top_pred(r["name"]),
                                                                                  f"{r['amount_text']} {d['unit']}"))]
        if r["chip"]:
            parts.append(kit.row([kit.badge(r["chip"]["text"], r["chip"]["tone"]), kit.txt("عن الفترة السابقة", 11, color=T.FAINT)], spacing=4))
        if ui.stats_open_cat == r["name"]:
            parts += [ft.Container(kit.between(kit.txt("— " + c["name"], 13, color=T.MUTED),
                                               kit.txt(f"{c['amount_text']}  ({c['pct']}%)", 13, color=T.MUTED)),
                                   ink=True, border_radius=8, padding=ft.padding.symmetric(vertical=4),
                                   on_click=lambda e, c=c, r=r: open_drill(ui, scope, f"{r['name']} › {c['name']}",
                                                                           sub_pred(r["name"], c["name"])))
                      for c in r["children"]]
        rows.append(ft.Container(kit.col(parts, spacing=6), padding=4))
    return [top, kit.box(kit.col([ft.Container(donut, alignment=ft.alignment.center), legend], spacing=14), padding=16),
            card("التفصيل", *rows, sub="اضغط على فئة لعرض معاملاتها، والسهم لفرعياتها")]


def view_analysis(ui, scope, an):
    d = vm.analysis_view(an, ui.today)
    if d["empty"]:
        return [empty_state("لا توجد مصاريف في هذه الفترة")]
    W = ui.w - 40 - 32
    out = []
    cur, rate = ui.currency, ui.repo.get_rate()
    nbins = len(d["histogram"])

    def bin_pred(i, b):
        def pred(t):
            if t["kind"] != "expense":
                return False
            v = money.convert_minor(t["amount"], t["currency"], cur, rate)
            return v > 0 and v >= b["lo"] and (i == nbins - 1 or v < b["hi"])
        return pred

    hist = [{"label": b["label"], "top": str(b["count"]) if b["count"] else "", "bars": [(b["fraction"], T.CHART_INCOME)],
             "on_click": lambda e, i=i, b=b: open_drill(ui, scope, "مصاريف " + b["range"], bin_pred(i, b))}
            for i, b in enumerate(d["histogram"])]
    out.append(card("توزيع حجم المصاريف (هستوغرام)", kit.columns_chart(hist, W, 120),
                    kit.txt("كل عمود = عدد المعاملات ضمن نطاق مبلغ، والرقم تحته هو الحد الأعلى للنطاق", 11, color=T.MUTED)))
    wd = [{"label": x["label"], "top": x["top"], "bars": [(x["fraction"], T.CHART_EXPENSE if x["peak"] else T.SERIES[0])],
           "on_click": lambda e, x=x: open_drill(
               ui, scope, "مصاريف يوم " + x["label"],
               lambda t: t["kind"] == "expense" and datetime.strptime(t["date"], "%Y-%m-%d").weekday() == x["wd"])}
          for x in d["weekdays"]]
    out.append(card("الصرف حسب أيام الأسبوع", kit.columns_chart(wd, W, 100)))
    if d["people"]:
        out.append(card("حسب الشخص", *[tappable(hbar(p["name"], p["amount_text"], p["fraction"], T.CHART_INCOME, W, f"{p['count']} · {p['pct']}%"),
                                               lambda e, p=p: open_drill(ui, scope, p["name"], lambda t: t["kind"] == "expense" and (t["person_name"] or NO_PERSON) == p["name"]))
                                       for p in d["people"]]))
    out.append(card("حسب المحفظة", *[tappable(hbar(w["name"], w["amount_text"], w["fraction"], T.CHART_EXPENSE, W, f"{w['pct']}%"),
                                             lambda e, w=w: open_drill(ui, scope, w["name"], lambda t: t["kind"] == "expense" and t["wallet_name"] == w["name"]))
                                     for w in d["wallets"]]))
    top = [tappable(kit.row([kit.txt(str(t["rank"]), 15, True, T.MUTED),
                             kit.col([kit.txt(t["title"], 14, True), kit.txt(t["subtitle"], 12, color=T.MUTED)], spacing=2, expand=True),
                             kit.txt(t["amount_text"], 14, True, T.EXPENSE)], spacing=10),
                    lambda e, t=t: ui.show_tx(t["id"])) for t in d["top"]]
    out.append(card("أكبر 5 مصاريف", *top))
    return out


# ------------------------------------------------------------------ screen
def build_txs(ui):
    scope, an, prev = vm.scope_and_analysis(ui)

    def set_cur(c):
        ui.currency = c
        ui.refresh()

    def set_view(v):
        ui.tx_view = v
        ui.refresh()

    body = {"list": lambda: view_list(ui, scope), "summary": lambda: view_summary(ui, scope, an, prev),
            "cats": lambda: view_cats(ui, scope, an, prev), "analysis": lambda: view_analysis(ui, scope, an)}[ui.tx_view]()
    head = [
        kit.between(kit.txt(getattr(ui, "title", "المعاملات"), 24, True),
                    kit.row([kit.icon_btn("picture_as_pdf", lambda e: open_pdf_sheet(ui), "تصدير PDF", color=T.PRIMARY),
                             ft.Container(kit.segmented([("IQD", "دينار"), ("USD", "دولار")], ui.currency, set_cur), width=150)],
                            spacing=4)),
        *header_controls(ui, scope, an),
        period_switch(ui),
        scope_bar(ui, scope),
        summary_strip(ui, an),
        kit.segmented(VIEWS, ui.tx_view, set_view),
    ]
    # one scrolling page: the header scrolls away with the list, so the transactions get the whole screen
    return ft.Container(kit.scroll_body(head + body + [ft.Container(height=90)], spacing=12),
                        padding=ft.padding.only(top=20), expand=True)


def open_filter_sheet(ui):
    repo = ui.repo
    f = {k: (set(v) if isinstance(v, set) else v) for k, v in ui.filters.items()}  # working copy
    body = ft.Column(spacing=12, scroll=ft.ScrollMode.AUTO, expand=True)
    mn, mx = kit.field("من مبلغ", f["min"], thousands=True, expand=True), kit.field("إلى مبلغ", f["max"], thousands=True, expand=True)
    d1 = kit.DateInput(ui, "من تاريخ", f["date_from"], clearable=True)
    d2 = kit.DateInput(ui, "إلى تاريخ", f["date_to"], clearable=True)
    ref = {}

    def tog(key, value):
        f[key] ^= {value}
        render()

    def setv(key, value):
        f[key] = value
        render()

    def group(title, chips):
        return [kit.txt(title, 13, True, T.MUTED), ft.Row(chips, wrap=True, spacing=8, run_spacing=8)]

    def render():
        cats, subs = [], []
        for kind in ("expense", "income"):
            for c in repo.category_tree(kind):
                cats.append(kit.chip(c["name"], c["id"] in f["categories"], lambda e, i=c["id"]: tog("categories", i),
                                     color=c["color"] or T.PRIMARY))
                if c["id"] in f["categories"] and c["children"]:
                    subs += group(f"فرعيات «{c['name']}»", [
                        kit.chip(ch["name"], ch["id"] in f["categories"], lambda e, i=ch["id"]: tog("categories", i), color=T.MUTED)
                        for ch in c["children"]])
        body.controls = (
            [kit.txt("فلتر متقدم", 20, True)]
            + group("النوع", [kit.chip(l, k in f["kinds"], lambda e, k=k: tog("kinds", k)) for k, l in QUICK_KINDS])
            + group("الفترة", [kit.chip(l, f["period"] == k, lambda e, k=k: setv("period", k)) for k, l in vm.PERIODS])
            + [d1.control, d2.control]
            + group("المحفظة", [kit.chip(w["name"], w["id"] in f["wallets"], lambda e, i=w["id"]: tog("wallets", i))
                                for w in repo.list_wallets()])
            + group("الفئة (الرئيسية تشمل فرعياتها)", cats) + subs
            + [kit.row([kit.txt("استثناء الفئات المحددة (كل شي ما عدا)", 13, expand=True),
                        ft.Switch(value=f["exclude_categories"], on_change=lambda e: setv("exclude_categories", e.control.value))])]
            + group("الشخص", [kit.chip(p["name"], p["id"] in f["people"], lambda e, i=p["id"]: tog("people", i))
                              for p in repo.list_people()] or [kit.txt("لا يوجد أشخاص", 13, color=T.MUTED)])
            + [kit.txt("المبلغ (لعملة المحفظة)", 13, True, T.MUTED), kit.row([mn, mx], spacing=8)]
            + group("الترتيب", [kit.chip(l, f["order"] == k, lambda e, k=k: setv("order", k)) for k, l in ORDERS])
            + [kit.row([ft.Container(kit.big_button("مسح", reset, outline=True), expand=True),
                        ft.Container(kit.big_button("تطبيق", apply), expand=True)], spacing=10)])
        ui.page.update()

    def reset(e):
        ui.filters = ui.default_filters()
        ui.page.close(ref["s"])
        ui.refresh()

    def apply(e):
        f["min"], f["max"], f["date_from"], f["date_to"] = mn.value.strip(), mx.value.strip(), d1.value, d2.value
        ui.filters = f
        ui.page.close(ref["s"])
        ui.refresh()

    ref["s"] = ui.open_sheet(body)
    render()
