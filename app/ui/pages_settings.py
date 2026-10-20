"""More > Settings: display currency, exchange rate, automatic backups."""
import flet as ft

from .. import backup, i18n, lock, money, paths, reminder, reset
from . import kit, theme as T
from .forms import choices, label
from .lock_ui import ask_password, password_dialog
from .rows import page_frame


EVERY = [(1, "كل يوم"), (3, "كل 3 أيام"), (7, "كل أسبوع"), (14, "كل أسبوعين"), (30, "كل شهر")]
KEEP = [(3, "آخر 3"), (5, "آخر 5"), (7, "آخر 7"), (10, "آخر 10"), (20, "آخر 20")]


def build_settings(ui):
    repo = ui.repo
    rate = kit.field("سعر الصرف (دينار لكل 1 دولار)", f"{repo.get_rate():g}", thousands=True)

    def save_rate(e):
        v = money.parse_input(rate.value)
        if v <= 0:
            ui.toast("اكتب سعراً صحيحاً")
            return
        ui.guard(repo.set_rate, v)
        ui.toast("تم حفظ السعر")
        ui.refresh()

    def set_cur(c):
        repo.set_setting("display_currency", c)
        ui.currency = c
        ui.refresh()

    def set_auto(v):
        repo.set_setting("auto_backup", "1" if v else "0")
        ui.refresh()

    def set_hide(v):
        repo.set_setting("hide_balances", "1" if v else "0")
        ui.refresh()

    cfg = reminder.settings(repo)

    def set_reminder(v):
        repo.set_setting("reminder_enabled", "1" if v else "0")
        if v:
            repo.set_setting("reminder_last", "")
        ui.refresh()

    def set_time(t):
        repo.set_setting("reminder_time", t)
        repo.set_setting("reminder_last", "")
        ui.refresh()

    def safety_backup():
        try:
            backup.create_backup(repo, paths.backup_dir(), keep=5, prefix="pre-reset")
        except Exception:
            pass

    def do_clear():
        safety_backup()
        reset.clear_transactions(repo)
        ui.toast("تم مسح كل المعاملات والديون")
        ui.refresh()

    def do_factory():
        safety_backup()
        reset.factory_reset(repo)
        ui.currency = repo.get_setting("display_currency", "IQD") or "IQD"
        ui.toast("تمت إعادة الضبط. ابدأ من جديد")
        ui.refresh()

    bk = backup.auto_settings(repo)
    auto = bk["enabled"]

    def set_language(code):
        if code == i18n.lang():
            return
        repo.set_setting("lang", code)
        i18n.set_lang(code)
        i18n.localize_defaults(repo, code)
        ui.apply_language()
    lk = lock.options(repo)

    def set_lock(name, v):
        if v and not lk["password"]:                 # needs a password first
            password_dialog(ui, lambda: (lock.set_option(repo, name, True), ui.refresh()))
            ui.refresh()
            return
        if name == "bio" and v and not ui.bio_available:
            ui.toast("البصمة غير متوفرة بهذا الإصدار من التطبيق أو الجهاز")
            ui.refresh()
            return
        ui.guard(lock.set_option, repo, name, v)
        ui.refresh()

    def remove_password():
        ask_password(ui, "أدخل كلمة السر لإزالتها", lambda: (lock.remove(repo), ui.toast("تم إزالة القفل"), ui.refresh()))

    def guarded(action):
        """Destructive actions ask for the password first when a lock is set."""
        return (lambda: ask_password(ui, "أدخل كلمة السر للمتابعة", action)) if lk["password"] else action

    def set_every(v):
        repo.set_setting("backup_every_days", str(v))
        ui.refresh()

    def set_keep(v):
        repo.set_setting("backup_keep", str(v))
        ui.refresh()

    return page_frame(ui, "الإعدادات", [
        kit.box(kit.col([label("اللغة"), choices(i18n.LANGUAGES, i18n.lang(), set_language),
                         kit.txt("اللغة تغيّر واجهة التطبيق فقط. الملاحظات وأسماء الفئات تكدر تكتبها بأي لغة.", 12, color=T.MUTED)], spacing=10)),
        kit.box(kit.col([label("العملة الافتراضية للعرض"), choices([("IQD", "دينار"), ("USD", "دولار")], ui.currency, set_cur)], spacing=10)),
        kit.box(kit.col([label("سعر الصرف"), rate, kit.big_button("حفظ السعر", save_rate),
                         kit.txt("السعر يُستخدم في التحويلات بين المحافظ وفي الإحصائيات (حسب سعر اليوم).", 12, color=T.MUTED)], spacing=10)),
        kit.box(kit.between(kit.col([kit.txt("إخفاء الأرصدة", 15, True),
                                     kit.txt("يعرض •••• بدل الأرصدة بالرئيسية والمحافظ", 12, color=T.MUTED)], spacing=2),
                            ft.Switch(value=ui.hide_balances, on_change=lambda e: set_hide(e.control.value)))),
        kit.box(kit.col([
            kit.between(kit.col([kit.txt("تذكير يومي", 15, True),
                                 kit.txt("يطلع تنبيه داخل التطبيق إذا ما سجلت شي اليوم أو عندك قسط قريب", 12, color=T.MUTED)], spacing=2),
                        ft.Switch(value=cfg["enabled"], on_change=lambda e: set_reminder(e.control.value))),
            ft.Container(kit.row([kit.icon("schedule", 20, T.PRIMARY), kit.txt("وقت التذكير: " + cfg["time"], 14, True)], spacing=8),
                         ink=True, border_radius=10, padding=8, on_click=lambda e: kit.pick_time(ui, cfg["time"], set_time)),
            kit.txt("التنبيه يظهر لما يكون التطبيق مفتوح. التنبيهات خارج التطبيق تحتاج مكوّن أندرويد إضافي (نرجع له بخطوة الـAPK).", 11, color=T.FAINT)],
            spacing=8)),
        kit.box(kit.col([
            kit.between(kit.col([kit.txt("نسخة احتياطية تلقائية", 15, True),
                                 kit.txt("تحفظ داخل التطبيق وتمسح الأقدم تلقائياً", 12, color=T.MUTED)], spacing=2),
                        ft.Switch(value=auto, on_change=lambda e: set_auto(e.control.value))),
            *([label("كل كم يوم؟"), choices(EVERY, bk["every"] if bk["every"] in dict(EVERY) else 1, set_every),
               label("كم نسخة أحتفظ؟"), choices(KEEP, bk["keep"] if bk["keep"] in dict(KEEP) else 7, set_keep)] if auto else [])],
            spacing=10)),
        kit.box(kit.col([
            kit.txt("الأمان", 15, True),
            kit.txt("كلمة السر " + ("محددة ✓" if lk["password"] else "غير محددة"), 12, color=T.MUTED),
            kit.row([ft.Container(kit.big_button("تغيير كلمة السر" if lk["password"] else "تحديد كلمة سر",
                                                 lambda e: password_dialog(ui, ui.refresh), outline=True), expand=True)] +
                    ([ft.Container(kit.big_button("إزالة", lambda e: remove_password(), outline=True), expand=True)] if lk["password"] else []),
                    spacing=10),
            kit.between(kit.col([kit.txt("قفل التطبيق عند الفتح", 14, True),
                                 kit.txt("يطلب كلمة السر (أو البصمة) كل ما تفتح التطبيق", 12, color=T.MUTED)], spacing=2),
                        ft.Switch(value=lk["app"], on_change=lambda e: set_lock("app", e.control.value))),
            kit.between(kit.col([kit.txt("قفل قسم «المزيد»", 14, True),
                                 kit.txt("تدخل التطبيق بدون كلمة سر، بس «المزيد» (الإعدادات والنسخ...) يطلبها", 12, color=T.MUTED)], spacing=2),
                        ft.Switch(value=lk["more"], on_change=lambda e: set_lock("more", e.control.value))),
            kit.between(kit.col([kit.txt("الدخول بالبصمة", 14, True),
                                 kit.txt("يفتح القفل بالبصمة بدل كتابة كلمة السر" if ui.bio_available else
                                         "غير متوفرة بهذا الإصدار (تحتاج نسخة Flet الأحدث). كلمة السر تشتغل دائماً", 12, color=T.MUTED)], spacing=2),
                        ft.Switch(value=lk["bio"], on_change=lambda e: set_lock("bio", e.control.value)))], spacing=10)),
        kit.box(kit.col([
            kit.txt("مسح البيانات (البدء من جديد)", 15, True, T.EXPENSE),
            kit.txt("تُحفظ نسخة أمان تلقائياً قبل أي مسح (تلقاها بشاشة النسخ الاحتياطي). الهستوري ما ينمسح.", 12, color=T.MUTED),
            kit.big_button("مسح كل المعاملات والديون", lambda e: kit.confirm_typed(
                ui.page, "مسح المعاملات", "تنحذف كل المعاملات والديون. تبقى المحافظ (بأرصدتها الابتدائية) والفئات والأشخاص والميزانيات.", "مسح", guarded(do_clear)),
                outline=True),
            kit.big_button("إعادة ضبط كاملة", lambda e: kit.confirm_typed(
                ui.page, "إعادة ضبط كاملة", "يتم مسح كل شي: المحافظ والمعاملات والفئات والأشخاص والديون والملاحظات والميزانيات، ويرجع التطبيق مثل أول مرة.", "مسح", guarded(do_factory)),
                bg=T.EXPENSE)], spacing=10)),
    ])
