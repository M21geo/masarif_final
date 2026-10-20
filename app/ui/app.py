"""App shell: page setup, bottom navigation, FAB, shared state, sheet helpers.

Screens live in screens_*.py / sheet_*.py and are plain functions `build(ui) -> control`.
"""
import time
import traceback
from datetime import date

import flet as ft

from .. import backup, i18n, lock, paths, reminder
from ..db import connect
from ..recurring import Recurring
from ..repo import AppError, Repo
from ..seed import ensure_defaults
from . import kit, theme as T, vm
from .lock_ui import build_lock
from .screens_home import build_home
from .screens_more import build_more
from .screens_txs import build_txs
from .sheet_add import open_add_sheet
from .sheet_tx import show_tx

TABS = [("الرئيسية", "HOME_OUTLINED", "HOME"), ("المعاملات", "BAR_CHART_OUTLINED", "BAR_CHART"),
        ("المزيد", "GRID_VIEW_OUTLINED", "GRID_VIEW")]


class AppUI:
    def __init__(self, page: ft.Page, repo: Repo, today: str = None):
        self.page = page
        self.repo = repo
        self.today = today or date.today().isoformat()
        # shared UI state
        self.currency = repo.get_setting("display_currency", "IQD") or "IQD"  # display currency
        self.tab = 0
        self.more_page = None           # which sub-page of the More tab is open
        self.debt_dir = "on"
        self.budget_ym = self.today[:7]
        self.cat_kind = "expense"
        self.stats_ym = self.today[:7]     # month shown when no filter is active
        self.period_mode = "month"         # month | week (history archives also have all_time)
        self.stats_week = vm.week_start(self.today)
        self.tx_view = "list"              # list | summary | cats | analysis
        self.stats_kind = "expense"
        self.stats_open_cat = None
        self.search = ""
        self.filters = self.default_filters()
        self.body = ft.Container(expand=True)
        self.locked = False           # app lock screen showing
        self.more_unlocked = False    # More tab opened with the password (re-locks when leaving it)
        self.nav = None               # bottom bar and + button (hidden while locked)
        self.fab = None
        self._exit_at = 0.0
        self._paused_at = None
        self._scroll_y = 0.0          # remembered scroll position of the current screen (kept when it is only redrawn)
        self._scroll_key = None
        self.bio_available = False    # filled at startup (fingerprint needs a newer Flet, see biometric.py)

    # ------------------------------------------------------ hidden balances
    @property
    def hide_balances(self) -> bool:
        return self.repo.get_setting("hide_balances", "0") == "1"

    def toggle_hide(self) -> None:
        self.repo.set_setting("hide_balances", "0" if self.hide_balances else "1")
        self.refresh()

    def shown(self, text: str, wallet: dict = None) -> str:
        """A balance as text, or •••• when hidden (globally, or for this wallet)."""
        return "••••••" if (self.hide_balances or (wallet and wallet.get("hide_balance"))) else text

    # ----------------------------------------------------------- geometry
    @property
    def w(self) -> float:
        return float(self.page.width or T.DEFAULT_WIDTH)

    @property
    def h(self) -> float:
        return float(self.page.height or 800)

    # ------------------------------------------------------------ filters
    @staticmethod
    def default_filters() -> dict:
        return {"kinds": set(), "wallets": set(), "categories": set(), "exclude_categories": False,
                "people": set(), "period": "all", "date_from": "", "date_to": "",
                "min": "", "max": "", "order": "newest"}

    def filters_active(self) -> int:
        f, n = self.filters, 0
        n += bool(f["kinds"]) + bool(f["wallets"]) + bool(f["categories"]) + bool(f["people"])
        n += f["period"] != "all" or bool(f["date_from"] or f["date_to"])
        n += bool(f["min"] or f["max"]) + (f["order"] != "newest")
        return n

    # ------------------------------------------------------------ plumbing
    def toast(self, message: str) -> None:
        kit.toast(self.page, message)

    def guard(self, fn, *args):
        """Run an action; show repo rule violations (AppError) as a toast instead of crashing."""
        try:
            return fn(*args)
        except AppError as e:
            self.toast(str(e))
        return None

    def _chrome(self, visible: bool) -> None:
        for c in (self.nav, self.fab):
            if c is not None:
                c.visible = visible

    def unlock(self) -> None:
        self.locked = False
        self.refresh()

    def lock_now(self) -> None:
        """Lock again (app lock) if it is switched on; the More tab always re-locks."""
        self.more_unlocked = False
        if lock.options(self.repo)["app"]:
            self.locked = True
            self.refresh()
        elif self.tab == 2 and lock.options(self.repo)["more"]:
            self.refresh()

    def refresh(self) -> None:
        """Rebuild the current tab (called after any data change)."""
        builders = [build_home, build_txs, build_more]
        self.last_error = None
        if self.locked:
            self._chrome(False)
            self.body.content = build_lock(self, "مصاريفي مقفل", "اكتب كلمة السر للدخول", self.unlock)
            i18n.translate_tree(self.body.content)
            self.page.update()
            return
        self._chrome(True)
        try:
            self.body.content = builders[self.tab](self)
        except Exception:  # show the problem on screen so it can be reported
            self.last_error = traceback.format_exc()
            self.body.content = ft.Container(
                ft.Text("حصل خطأ في عرض هذه الشاشة:\n\n" + traceback.format_exc(), selectable=True, size=12, color=T.EXPENSE),
                padding=20)
        i18n.translate_tree(self.body.content)
        self._track_scroll()
        self.page.update()
        self._restore_scroll()

    # ------------------------------------------------------ keep scroll place
    def _scroll_column(self, c, depth=0):
        """The page's scrolling column (tagged by kit.scroll_body), if the screen has one."""
        if c is None or depth > 14:
            return None
        if getattr(c, "data", None) == "page_scroll":
            return c
        kids = getattr(c, "controls", None)
        kids = list(kids) if isinstance(kids, list) else []
        inner = getattr(c, "content", None)
        if inner is not None and not isinstance(inner, (str, int, float)):
            kids.append(inner)
        for k in kids:
            found = self._scroll_column(k, depth + 1)
            if found is not None:
                return found
        return None

    def _track_scroll(self) -> None:
        """Redrawing the screen (expanding a category, opening the password box...) must not throw you back to the top:
        remember where the list was and put it back, but start from the top when you move to another screen/period."""
        key = (self.tab, self.more_page, self.tx_view, self.stats_ym, self.stats_week, self.period_mode, self.locked)
        if key != self._scroll_key:
            self._scroll_key, self._scroll_y = key, 0.0
        col = self._scroll_column(self.body.content)
        self._col = col
        if col is not None:
            try:
                col.on_scroll_interval = 60
                col.on_scroll = self._on_scroll
            except Exception:
                pass

    def _on_scroll(self, e) -> None:
        try:
            self._scroll_y = float(e.pixels)
        except Exception:
            pass

    def _restore_scroll(self) -> None:
        col = getattr(self, "_col", None)
        if col is not None and self._scroll_y > 1:
            try:
                col.scroll_to(offset=self._scroll_y, duration=0)
            except Exception:
                pass

    def go(self, index: int) -> None:
        self.tab = index
        if index != 2:
            self.more_page = None
            self.more_unlocked = False
        if self.nav is not None:
            self.nav.selected_index = index
        self.refresh()

    # --------------------------------------------------------- system back
    def go_back(self) -> bool:
        """What the phone's back button / swipe-back does inside the app. True if it did something."""
        if self.locked:
            return False
        for c in reversed(list(self.page.overlay)):          # an open dialog / sheet closes first
            if getattr(c, "open", False):
                self.page.close(c)
                return True
        if self.tab == 2 and self.more_page:
            if self.more_page == "history_view" and getattr(self, "hist", None) is not None:
                from .pages_history import close_archive
                close_archive(self)
            elif self.more_page == "history_view":
                self.more_page = "history"
                self.refresh()
            else:
                self.more_page = None
                self.refresh()
            return True
        if self.tab != 0:
            self.go(0)
            return True
        return False

    def on_back(self, e=None) -> None:
        if self.go_back():
            return
        now = time.time()
        if now - self._exit_at < 2.5:                         # second press: leave the app
            try:
                self.page.window.destroy()
            except Exception:
                try:
                    self.page.window_destroy()
                except Exception:
                    pass
            return
        self._exit_at = now
        self.toast("اضغط رجوع مرة ثانية للخروج")

    def on_lifecycle(self, e) -> None:
        """Leaving the app for a while locks it again (and always re-locks the More tab)."""
        state = str(getattr(e, "state", getattr(e, "data", ""))).lower()
        if any(k in state for k in ("pause", "hide", "inactive")):
            self._paused_at = self._paused_at or time.time()
        elif any(k in state for k in ("resume", "show")):
            away = time.time() - self._paused_at if self._paused_at else 0
            self._paused_at = None
            if away > 20:
                self.lock_now()

    def open_sheet(self, content, height=None):
        """Show `content` in a bottom sheet. Returns the sheet (page.close(sheet) to dismiss)."""
        sheet = ft.BottomSheet(
            content=ft.Container(content, padding=ft.padding.only(left=20, right=20, top=14, bottom=20),
                                 height=height or min(self.h * 0.92, 760), bgcolor=T.BG),
            is_scroll_controlled=True, show_drag_handle=True, bgcolor=T.BG)
        i18n.translate_tree(sheet)
        self.page.open(sheet)
        return sheet

    def apply_language(self) -> None:
        """Switch the whole app between Arabic (right-to-left) and English (left-to-right)."""
        code = i18n.lang()
        try:
            self.page.rtl = i18n.is_rtl()
            self.page.locale_configuration = ft.LocaleConfiguration(
                supported_locales=[ft.Locale("ar", "IQ"), ft.Locale("en", "US")],
                current_locale=ft.Locale("ar", "IQ") if code == "ar" else ft.Locale("en", "US"))
        except Exception:
            pass
        if self.nav is not None:
            for dest, (label, _i, _s) in zip(self.nav.destinations, TABS):
                dest.label = i18n.tr(label)
        self.refresh()

    def check_reminder(self) -> None:
        """Show the daily reminder dialog once per day (after the chosen time) if there is something to say."""
        lines = reminder.due(self.repo)
        if not lines:
            return
        reminder.mark_shown(self.repo)
        dlg = ft.AlertDialog(title=ft.Text(reminder.title(self.repo)),
                             content=ft.Column([ft.Text(l) for l in lines], tight=True, spacing=8),
                             actions=[ft.TextButton("لاحقاً", on_click=lambda e: self.page.close(dlg)),
                                      ft.TextButton("سجّل الآن", on_click=lambda e: (self.page.close(dlg), self.add_transaction()))])
        self.page.open(dlg)

    def add_transaction(self, tx=None, kind=None):
        open_add_sheet(self, tx, kind)

    def show_tx(self, tx_id: int):
        show_tx(self, tx_id)


def _install_views(page, ui, nav, fab, loc) -> bool:
    """Two stacked views: Android only delivers the system back button / swipe-back (on_view_pop) when there is a
    view below the current one. The bottom view is never shown; every back press is handled by ui.on_back()."""
    try:
        base = ft.View("/", [ft.Container()], padding=0, bgcolor=T.BG)
        top = ft.View("/", [ft.SafeArea(ui.body, expand=True)], padding=0, bgcolor=T.BG,
                      navigation_bar=nav, floating_action_button=fab, floating_action_button_location=loc)
        page.views.clear()
        page.views.extend([base, top])
        page.on_view_pop = ui.on_back
        return True
    except Exception:
        return False


def build_shell(page: ft.Page, repo: Repo, today: str = None) -> AppUI:
    ui = AppUI(page, repo, today)
    page.title = i18n.tr("مصاريفي")
    page.padding = 0
    page.bgcolor = T.BG
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = ft.Theme(color_scheme_seed=T.PRIMARY)
    try:  # right-to-left layout for Arabic, left-to-right for English
        page.rtl = i18n.is_rtl()
        page.locale_configuration = ft.LocaleConfiguration(
            supported_locales=[ft.Locale("ar", "IQ"), ft.Locale("en", "US")],
            current_locale=ft.Locale("ar", "IQ") if i18n.is_rtl() else ft.Locale("en", "US"))
    except Exception:
        pass
    try:  # dialogs / snackbars opened with page.open() get translated too
        _open = page.open

        def open_translated(control, *a, **k):
            i18n.translate_tree(control)
            return _open(control, *a, **k)

        page.open = open_translated
    except Exception:
        pass
    nav = ft.NavigationBar(
        selected_index=0, bgcolor=T.CARD, indicator_color=T.PRIMARY_SOFT,
        destinations=[ft.NavigationBarDestination(icon=getattr(ft.Icons, i), selected_icon=getattr(ft.Icons, s), label=i18n.tr(l))
                      for l, i, s in TABS],
        on_change=lambda e: ui.go(int(e.control.selected_index)))
    fab = ft.FloatingActionButton(
        icon=ft.Icons.ADD, bgcolor=T.ACCENT, foreground_color="#FFFFFF", on_click=lambda e: ui.add_transaction())
    ui.nav, ui.fab = nav, fab
    loc = ft.FloatingActionButtonLocation.END_FLOAT
    if not _install_views(page, ui, nav, fab, loc):          # fallback: the plain single-page layout
        page.navigation_bar = nav
        page.floating_action_button = fab
        page.floating_action_button_location = loc
        page.add(ft.SafeArea(ui.body, expand=True))
    try:
        page.on_app_lifecycle_state_change = ui.on_lifecycle
    except Exception:
        pass
    ui.locked = lock.options(repo)["app"]
    ui.refresh()
    return ui


def main(page: ft.Page) -> None:
    """Entry point used by main.py (and `flet build apk`)."""
    conn = connect(paths.db_path())
    repo = Repo(conn)
    ensure_defaults(repo)
    i18n.set_lang(repo.get_setting("lang", "ar") or "ar")
    if not i18n.is_rtl():
        i18n.localize_defaults(repo, i18n.lang())
    try:  # daily automatic backup (kept inside the app's private storage)
        backup.run_auto_backup(repo, paths.backup_dir())
    except Exception:
        pass
    try:  # recurring rules that came due: only remind, the user runs them from Home / Recurring
        n = Recurring(repo).pending(date.today().isoformat())["count"]
    except Exception:
        n = 0
    ui = build_shell(page, repo)
    if n:
        ui.toast(f"عندك {n} معاملة تكرارية مستحقة. اضغط «تنفيذ المستحق» بالرئيسية")
    try:
        from ..history import Histories
        Histories(paths.history_dir()).purge_drafts()
    except Exception:
        pass

    async def detect_bio():
        from .. import biometric
        ui.bio_available = await biometric.available(page)

    try:
        page.run_task(detect_bio)
    except Exception:
        pass

    async def reminder_loop():
        import asyncio
        while True:
            try:
                ui.check_reminder()
            except Exception:
                pass
            await asyncio.sleep(60)

    try:
        page.run_task(reminder_loop)
    except Exception:
        ui.check_reminder()
