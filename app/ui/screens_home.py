"""Home: total balance (IQD/USD toggle), this month's income/expense, wallets, recent transactions."""
import flet as ft

from .. import money
from ..budgets import Budgets
from ..recurring import Recurring
from . import kit, theme as T, vm
from .rows import empty_state, tx_tile


def _hero_toggle(ui, dark=True):
    def pill(code, label):
        on = ui.currency == code

        def pick(e):
            ui.currency = code
            ui.refresh()

        return ft.Container(
            content=kit.txt(label, 13, True, (T.HERO if on else T.HERO_TEXT) if dark else (T.INK if on else T.MUTED)),
            padding=ft.padding.symmetric(horizontal=14, vertical=7), border_radius=9, ink=True,
            bgcolor=(T.MINT if dark else T.PRIMARY_SOFT) if on else None, on_click=pick)

    return ft.Container(content=kit.row([pill("IQD", "دينار"), pill("USD", "دولار")], spacing=0),
                        bgcolor=GLASS if dark else T.LINE, border_radius=12, padding=3)


GLASS = ft.Colors.with_opacity(0.2, "#FFFFFF")


def _stat(label, value, color):
    return ft.Container(
        content=kit.col([kit.txt(label, 12, color=T.HERO_TEXT), kit.txt(value, 16, True, color)], spacing=3),
        bgcolor=GLASS, border_radius=16, padding=12, expand=True)


def _wallet_card(ui, w):
    def open_wallet(e):
        ui.filters = ui.default_filters()
        ui.filters["wallets"] = {w["id"]}
        ui.go(1)

    def toggle_eye(e):
        ui.repo.update_wallet(w["id"], hide_balance=not w["hide_balance"])
        ui.refresh()

    def make_main(e):
        ui.repo.set_main_wallet(w["id"])
        ui.toast(f"«{w['name']}» صارت المحفظة الرئيسية")
        ui.refresh()

    accent = T.vivid(w["name"])

    def round_btn(name, on_click, tip, on=False, on_color=T.SUN):
        """Small round icon button: filled when active, soft otherwise."""
        return ft.Container(
            kit.icon(name, 17, "#FFFFFF" if on else T.MUTED), width=30, height=30, border_radius=15, ink=True,
            bgcolor=on_color if on else ft.Colors.with_opacity(0.10, T.INK), alignment=ft.alignment.center,
            on_click=on_click, tooltip=tip)

    return kit.box(
        kit.col([
            kit.txt(w["name"], 15, True, max_lines=2),
            kit.row([ft.Container(kit.txt(w["currency"], 11, True, "#FFFFFF"), bgcolor=accent, border_radius=8,
                                  padding=ft.padding.symmetric(horizontal=8, vertical=3)),
                     ft.Container(expand=True),
                     round_btn("visibility_off" if w["hide_balance"] else "visibility", toggle_eye,
                               "إخفاء/إظهار رصيد هذه المحفظة", on=bool(w["hide_balance"]), on_color=T.MUTED),
                     round_btn("star" if w["is_main"] else "star_border", make_main, "اجعلها المحفظة الرئيسية",
                               on=w["is_main"])], spacing=6),
            kit.txt(ui.shown(w["balance_text"], w), 19, True)], spacing=10),
        width=178, on_click=open_wallet, bg=ft.Colors.with_opacity(0.13, accent), border=accent)


def _main_hero(ui, d):
    m = d["main"]
    if not m:
        return kit.box(kit.txt("أضف محفظة من (المزيد ← المحافظ) لتبدأ", 14, color=T.MUTED))
    hidden = ui.hide_balances or m["hide_balance"]

    def toggle_main(m):
        ui.repo.update_wallet(m["id"], hide_balance=not m["hide_balance"])
        ui.refresh()
    return kit.hero(kit.col([
        kit.between(kit.row([kit.icon("star", 18, T.SUN), kit.txt("المحفظة الرئيسية · " + m["name"], 14, color=T.HERO_TEXT),
                             kit.icon_btn("visibility_off" if hidden else "visibility", lambda e: toggle_main(m),
                                          "إخفاء/إظهار رصيد هذه المحفظة", color=T.HERO_TEXT, size=20)], spacing=4), ft.Container()),
        kit.row([kit.txt("••••••" if hidden else m["balance_text"], 36, True, "#FFFFFF"), kit.txt(m["unit"], 16, True, T.HERO_TEXT)],
                spacing=8, v_align=ft.CrossAxisAlignment.END),
        kit.row([_stat("دخل الشهر (" + d["unit"] + ")", d["income_text"], T.MINT), _stat("مصروف الشهر (" + d["unit"] + ")", d["expense_text"], "#FFB4A8")], spacing=10),
    ], spacing=12))


def _total_card(ui, d):
    """All wallets together (this used to be the big hero card)."""
    return kit.box(kit.col([
        kit.between(kit.txt("إجمالي كل المحافظ", 13, color=T.MUTED), _hero_toggle(ui, dark=False)),
        kit.row([kit.txt(ui.shown(d["total_text"]), 22, True), kit.txt(d["unit"], 14, True, T.MUTED)], spacing=6,
                v_align=ft.CrossAxisAlignment.END),
        kit.txt(ui.shown(d["equiv_text"]) if not ui.hide_balances else "", 12, color=T.FAINT)], spacing=6))


def _recurring_card(ui):
    """Recurring transactions that came due. Nothing is created until the user taps the button."""
    p = Recurring(ui.repo).pending(ui.today)
    if not p["count"]:
        return None

    def run(e):
        n = Recurring(ui.repo).run_due(ui.today)
        ui.toast(f"سُجّلت {n} معاملة")
        ui.refresh()

    names = "، ".join((r["note"] or r.get("category_name") or r["wallet_name"]) for r in p["items"][:3])
    return kit.box(kit.col([
        kit.row([kit.icon("autorenew", 22, "#B77700"),
                 kit.col([kit.txt(f"عندك {p['count']} معاملة تكرارية مستحقة", 14, True, T.TONE["warn"][0]),
                          kit.txt(names, 12, color=T.MUTED, max_lines=2)], spacing=1, expand=True)], spacing=10),
        kit.big_button("تنفيذ المستحق", run)], spacing=10), bg=T.TONE["warn"][1], border="#F2D9A0")


def build_home(ui):
    d = vm.home(ui.repo, ui.currency, ui.today)
    recent = [tx_tile(ui, r) for r in d["recent"]] or [empty_state("ما في معاملات بعد. اضغط + لإضافة أول معاملة")]
    content = kit.scroll_body([
        kit.col([kit.txt(d["month_label"], 13, color=T.MUTED), kit.txt("نظرة عامة", 24, True)], spacing=2),
        _main_hero(ui, d),
        *([c] if (c := _recurring_card(ui)) else []),
        _budget_card(ui),
        kit.section("المحافظ"),
        kit.hscroll([_wallet_card(ui, w) for w in d["wallets"]], spacing=10),
        kit.section("آخر المعاملات", "عرض الكل", lambda e: ui.go(1)),
        kit.col(recent, spacing=0),
        ft.Container(height=90),  # room for the floating + button
    ], spacing=18)
    return ft.Container(content, padding=ft.padding.only(top=20), expand=True)


def _budget_card(ui):
    """Overall monthly budget progress (or a hint to create one)."""
    def open_budgets(e):
        ui.more_page = "budgets"
        ui.go(2)

    st = Budgets(ui.repo).status(ui.today[:7], ui.today)["overall"]
    if not st:
        return kit.box(kit.row([kit.icon("savings", 22, T.PRIMARY), kit.col([kit.txt("حدد ميزانية شهرية", 14, True),
                                                                           kit.txt("تابع صرفك وياك حد معين", 12, color=T.MUTED)], spacing=1, expand=True),
                                kit.icon("chevron_left", 20, T.FAINT)], spacing=10), on_click=open_budgets)
    color = {"ok": T.PRIMARY, "warn": "#B77700", "over": T.EXPENSE}[st["state"]]
    left = (f"المتبقي {money.fmt(st['remaining'], st['currency'])}" if st["remaining"] >= 0
            else f"تجاوزت بـ {money.fmt(-st['remaining'], st['currency'])}")
    extra = f" · {money.fmt(st['daily_left'], st['currency'])} باليوم" if st["daily_left"] and st["remaining"] > 0 else ""
    return kit.box(kit.col([
        kit.between(kit.txt("ميزانية الشهر", 14, True), kit.txt(f"{st['pct']}%", 14, True, color)),
        kit.progress(st["pct"] / 100, color, ui.w - 40 - 28, 10),
        kit.txt(left + extra, 12, color=T.MUTED)], spacing=8), on_click=open_budgets)
