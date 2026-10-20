"""Lock screen (password / fingerprint) and the password dialogs used by Settings."""
import flet as ft

from .. import biometric, i18n, lock
from ..repo import AppError
from . import kit, theme as T


def build_lock(ui, title, subtitle, on_ok):
    """Full-body lock card. on_ok() is called after a correct password / fingerprint / recovery code."""
    pw = kit.field("كلمة السر", password=True)
    err = kit.txt("", 13, color=T.EXPENSE)

    def enter(e=None):
        try:
            ok = lock.check_password(ui.repo, pw.value)
        except AppError as ex:
            err.value = i18n.tr(str(ex))
            ui.page.update()
            return
        if ok:
            on_ok()
        else:
            err.value = i18n.tr("كلمة السر غير صحيحة")
            pw.value = ""
            ui.page.update()

    pw.on_submit = enter

    async def try_bio():
        if await biometric.authenticate(ui.page, "افتح مصاريفي"):
            on_ok()

    def bio(e=None):
        try:
            ui.page.run_task(try_bio)
        except Exception:
            pass

    def forgot(e):
        code = kit.field("رمز الاسترجاع (8 خانات)")
        dlg = ft.AlertDialog(modal=True, title=ft.Text("نسيت كلمة السر؟"), content=ft.Column([
            ft.Text("اكتب رمز الاسترجاع اللي ظهر لك وقت تحديد كلمة السر. بعدها ينشال القفل وتكدر تحدد كلمة سر جديدة."), code],
            tight=True, spacing=12))

        def ok(ev):
            if lock.recover(ui.repo, code.value):
                ui.page.close(dlg)
                ui.toast("تم إزالة القفل. حدد كلمة سر جديدة من الإعدادات")
                on_ok()
            else:
                code.error_text = i18n.tr("الرمز غير صحيح")
                ui.page.update()

        dlg.actions = [ft.TextButton("إلغاء", on_click=lambda ev: ui.page.close(dlg)), ft.TextButton("استرجاع", on_click=ok)]
        ui.page.open(dlg)

    opts = lock.options(ui.repo)
    items = [ft.Container(height=30), kit.icon("lock", 54, T.PRIMARY), kit.txt(title, 22, True, align=ft.TextAlign.CENTER),
             kit.txt(subtitle, 13, color=T.MUTED, align=ft.TextAlign.CENTER), ft.Container(height=6), pw, err,
             kit.big_button("دخول", enter)]
    if opts["bio"]:
        items.append(kit.big_button("الدخول بالبصمة", bio, outline=True))
        bio()    # offer the fingerprint prompt right away
    items.append(ft.TextButton("نسيت كلمة السر؟", on_click=forgot))
    return ft.Container(kit.col(items, spacing=12, h_align=ft.CrossAxisAlignment.CENTER, scroll=True, expand=True),
                        padding=ft.padding.symmetric(horizontal=28), expand=True)


def password_dialog(ui, on_done):
    """Set a new password, or change it (asks for the current one). Shows the recovery code once."""
    repo = ui.repo
    has = lock.has_password(repo)
    cur = kit.field("كلمة السر الحالية", password=True)
    new = kit.field("كلمة السر الجديدة (4 خانات أو أكثر)", password=True)
    again = kit.field("أعد كتابتها", password=True)
    msg = kit.txt("", 12, color=T.EXPENSE)

    def save(e):
        if new.value != again.value:
            msg.value = i18n.tr("كلمتا السر مو متطابقتين")
            ui.page.update()
            return
        try:
            code = lock.set_password(repo, new.value, cur.value if has else None)
        except AppError as ex:
            msg.value = i18n.tr(str(ex))
            ui.page.update()
            return
        ui.page.close(dlg)
        recovery_dialog(ui, code)
        on_done()

    dlg = ft.AlertDialog(modal=True, title=ft.Text("تغيير كلمة السر" if has else "تحديد كلمة سر"),
                         content=ft.Column(([cur] if has else []) + [new, again, msg], tight=True, spacing=10),
                         actions=[ft.TextButton("إلغاء", on_click=lambda e: ui.page.close(dlg)), ft.TextButton("حفظ", on_click=save)])
    ui.page.open(dlg)


def recovery_dialog(ui, code):
    dlg = ft.AlertDialog(modal=True, title=ft.Text("احفظ رمز الاسترجاع"), content=ft.Column([
        ft.Text("إذا نسيت كلمة السر هذا الرمز هو الطريقة الوحيدة لفتح التطبيق. اكتبه بمكان آمن، وما يظهر مرة ثانية."),
        ft.Container(ft.Text(code, size=30, weight=ft.FontWeight.BOLD, selectable=True, color=T.PRIMARY),
                     alignment=ft.alignment.center, padding=10, bgcolor=T.SOFT, border_radius=12)], tight=True, spacing=12),
        actions=[ft.TextButton("حفظته", on_click=lambda e: ui.page.close(dlg))])
    ui.page.open(dlg)


def ask_password(ui, title, on_ok):
    """Small confirmation dialog: continue only with the correct password."""
    pw = kit.field("كلمة السر", password=True)
    dlg = ft.AlertDialog(modal=True, title=ft.Text(title), content=pw)

    def ok(e):
        try:
            good = lock.check_password(ui.repo, pw.value)
        except AppError as ex:
            pw.error_text = i18n.tr(str(ex))
            ui.page.update()
            return
        if good:
            ui.page.close(dlg)
            on_ok()
        else:
            pw.error_text = i18n.tr("كلمة السر غير صحيحة")
            ui.page.update()

    dlg.actions = [ft.TextButton("إلغاء", on_click=lambda e: ui.page.close(dlg)), ft.TextButton("تأكيد", on_click=ok)]
    ui.page.open(dlg)
