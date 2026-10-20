"""More > People."""
import flet as ft

from . import kit, theme as T
from .rows import empty_state, page_frame, small_btn


def build_people(ui):
    repo = ui.repo
    counts = {r[0]: r[1] for r in repo.conn.execute("SELECT person_id, COUNT(*) FROM transactions WHERE person_id IS NOT NULL GROUP BY person_id")}

    def rename(p):
        f = kit.field("الاسم", p["name"])

        def ok(e):
            if ui.guard(repo.rename_person, p["id"], f.value) is not False:
                ui.page.close(dlg)
                ui.refresh()

        dlg = ft.AlertDialog(title=ft.Text("تعديل الاسم"), content=f,
                             actions=[ft.TextButton("إلغاء", on_click=lambda e: ui.page.close(dlg)), ft.TextButton("حفظ", on_click=ok)])
        ui.page.open(dlg)

    def delete(p):
        kit.confirm(ui.page, "حذف الشخص", "المعاملات تبقى، بس تنشال علامة الشخص منها.",
                    lambda: (repo.delete_person(p["id"]), ui.refresh()))

    def add(e):
        f = kit.field("اسم الشخص")

        def ok(ev):
            if ui.guard(repo.add_person, f.value) is not None:
                ui.page.close(dlg)
                ui.refresh()

        dlg = ft.AlertDialog(title=ft.Text("شخص جديد"), content=f,
                             actions=[ft.TextButton("إلغاء", on_click=lambda e: ui.page.close(dlg)), ft.TextButton("إضافة", on_click=ok)])
        ui.page.open(dlg)

    def toggle_hidden(p):
        repo.set_person_hidden(p["id"], not p["hidden"])
        ui.toast("رجع يظهر عند إضافة المعاملات" if p["hidden"] else "انخفى من إضافة المعاملات (يبقى هنا)")
        ui.refresh()

    def move(p, d):
        repo.move_person(p["id"], d)
        ui.refresh()

    people = repo.list_people()
    rows = [kit.box(kit.between(kit.col([kit.row([kit.txt(p["name"], 15, True, T.MUTED if p["hidden"] else T.INK),
                                                   *([kit.icon("visibility_off", 15, T.FAINT)] if p["hidden"] else [])], spacing=6),
                                          kit.txt(f"{counts.get(p['id'], 0)} معاملة", 12, color=T.MUTED)], spacing=2),
                                kit.row([small_btn("arrow_upward", lambda e, p=p: move(p, -1), "فوق", color=T.PRIMARY if i > 0 else T.LINE),
                                         small_btn("arrow_downward", lambda e, p=p: move(p, 1), "تحت", color=T.PRIMARY if i < len(people) - 1 else T.LINE),
                                         small_btn("visibility_off" if p["hidden"] else "visibility", lambda e, p=p: toggle_hidden(p),
                                                   "إظهار" if p["hidden"] else "إخفاء", color=T.MUTED if p["hidden"] else T.PRIMARY),
                                         small_btn("edit", lambda e, p=p: rename(p)),
                                         small_btn("delete_outline", lambda e, p=p: delete(p), color=T.EXPENSE)], spacing=0)))
            for i, p in enumerate(people)] or [empty_state("ما في أشخاص بعد")]
    return page_frame(ui, "الأشخاص", [kit.big_button("+ شخص جديد", add)] + rows)
