"""More > Wallets: balances, add/edit, reorder, archive, delete, transfer."""
import flet as ft

from .. import money
from . import kit, theme as T
from .forms import FormSheet, choices, label
from .rows import empty_state, page_frame, small_btn


def build_wallets(ui):
    repo = ui.repo
    wallets = repo.balances(include_archived=True)
    active = [w for w in wallets if not w["archived"]]

    main_id = repo.main_wallet_id()

    def toggle_eye(w):
        repo.update_wallet(w["id"], hide_balance=not w["hide_balance"])
        ui.refresh()

    def set_cur(c):
        ui.currency = c
        ui.refresh()

    cur = ui.currency
    other = "USD" if cur == "IQD" else "IQD"
    total = kit.box(kit.col([
        kit.between(kit.txt("إجمالي كل المحافظ", 13, color=T.MUTED),
                    ft.Container(kit.segmented([("IQD", "دينار"), ("USD", "دولار")], cur, set_cur), width=150)),
        kit.txt(ui.shown(money.fmt(repo.total_balance(cur), cur)), 22, True),
        kit.txt(ui.shown(f"يعادل {money.fmt(repo.total_balance(other), other)} بسعر {repo.get_rate():,.0f}"), 12, color=T.FAINT)],
        spacing=6))

    def set_main(w):
        repo.set_main_wallet(w["id"])
        ui.toast(f"«{w['name']}» صارت المحفظة الرئيسية")
        ui.refresh()

    def move(w, d):
        ids = [x["id"] for x in active]
        i = ids.index(w["id"])
        j = i + d
        if 0 <= j < len(ids):
            ids[i], ids[j] = ids[j], ids[i]
            repo.reorder_wallets(ids)
            ui.refresh()

    def archive(w, flag):
        ui.guard(repo.archive_wallet, w["id"], flag)
        ui.refresh()

    def delete(w):
        def do():
            ui.guard(repo.delete_wallet, w["id"])
            ui.refresh()
        kit.confirm(ui.page, "حذف المحفظة", f"حذف «{w['name']}»؟ (ما تنحذف إذا فيها معاملات)", do)

    def card(w):
        arch = bool(w["archived"])
        acts = [small_btn("edit", lambda e, w=w: wallet_form(ui, w), "تعديل"),
                small_btn("visibility_off" if w["hide_balance"] else "visibility", lambda e, w=w: toggle_eye(w),
                          "إخفاء/إظهار رصيد هذه المحفظة")]
        if not arch:
            is_main = w["id"] == main_id
            acts.append(small_btn("star" if is_main else "star_border", lambda e, w=w: set_main(w),
                                  "المحفظة الرئيسية", color=T.SUN if is_main else T.MUTED))
        if not arch:
            acts += [small_btn("arrow_upward", lambda e, w=w: move(w, -1)), small_btn("arrow_downward", lambda e, w=w: move(w, 1))]
        acts += [small_btn("unarchive" if arch else "archive", lambda e, w=w: archive(w, not arch)),
                 small_btn("delete_outline", lambda e, w=w: delete(w), color=T.EXPENSE)]
        return kit.box(kit.col([
            kit.between(kit.row([kit.txt(w["name"], 16, True), kit.badge(w["currency"], "neutral")] +
                                ([kit.badge("رئيسية", "warn")] if w["id"] == main_id and not arch else []) +
                                ([kit.badge("مؤرشفة", "warn")] if arch else []), spacing=8),
                        kit.txt(ui.shown(money.fmt(w["balance"], w["currency"]), w), 17, True)),
            kit.row(acts, spacing=0)], spacing=6), bg=T.SOFT if arch else T.CARD)

    items = [card(w) for w in wallets] or [empty_state("ما في محافظ")]
    top = kit.row([ft.Container(kit.big_button("+ محفظة", lambda e: wallet_form(ui, None)), expand=True),
                   ft.Container(kit.big_button("تحويل بين محافظ", lambda e: ui.add_transaction(kind="transfer"), outline=True),
                                expand=True)], spacing=10)
    return page_frame(ui, "المحافظ", [total, top] + items)


def wallet_form(ui, w):
    repo, s = ui.repo, {"cur": w["currency"] if w else "IQD"}
    name = kit.field("اسم المحفظة", w["name"] if w else "")
    hide = ft.Switch(label="إخفاء رصيد هذه المحفظة دائماً", value=bool(w and w["hide_balance"]))
    initial = kit.field("الرصيد الابتدائي", str(money.from_minor(w["initial_balance"], w["currency"])) if w else "0", thousands=True)

    def controls():
        out = [name]
        if not w:
            out += [label("العملة"), choices([("IQD", "دينار عراقي"), ("USD", "دولار")], s["cur"], pick)]
        return out + [initial, hide]

    def pick(c):
        s["cur"] = c
        form.render()

    def save():
        if w:
            repo.update_wallet(w["id"], name=name.value, initial=money.parse_input(initial.value), hide_balance=hide.value)
        else:
            wid = repo.add_wallet(name.value, s["cur"], money.parse_input(initial.value))
            repo.update_wallet(wid, hide_balance=hide.value)
        return True

    form = FormSheet(ui, "تعديل محفظة" if w else "محفظة جديدة", controls, save).open()
