"""Export the transactions (shown now, or all) with their statistics as a PDF."""
import os
import shutil
from datetime import datetime

from .. import i18n, paths
from . import kit, theme as T, vm


def open_pdf_sheet(ui):
    repo = ui.repo

    def make(which):
        ui.page.close(sheet)
        try:
            from .. import pdf_report
        except Exception:
            ui.toast("ما قدرت أنشئ الـPDF (مكتبة reportlab غير موجودة)")
            return
        ui.toast("جاري تجهيز الملف...")
        scope, _an, _prev = vm.scope_and_analysis(ui)
        if which == "all":
            scope = {"rows": repo.list_transactions(order="newest"), "span": None, "filtered": False, "all": True}
        name = f"masarif-{datetime.now():%Y%m%d-%H%M}.pdf"
        tmp = os.path.join(paths.export_dir(), name)
        try:
            pdf_report.build_pdf(tmp, repo, scope, ui.currency, i18n.lang(), ui.today,
                                 filters=ui.filters if which != "all" else None, search=ui.search if which != "all" else "")
        except Exception as ex:           # show the reason instead of failing silently
            ui.toast(f"PDF: {ex}")
            return
        with open(tmp, "rb") as fh:
            data = fh.read()

        def write(path):
            if not path.lower().endswith(".pdf"):
                path += ".pdf"
            if os.path.abspath(path) != os.path.abspath(tmp):
                shutil.copyfile(tmp, path)
            ui.toast("تم حفظ ملف PDF")

        kit.save_file(ui, name, write, ["pdf"], "حفظ التقرير", data=data)

    sheet = ui.open_sheet(kit.col([
        kit.txt("تصدير PDF", 20, True),
        kit.txt("التقرير يحتوي الملخص والرسوم والفئات والتحليل ثم كل المعاملات.", 13, color=T.MUTED),
        kit.big_button("المعاملات المعروضة الآن", lambda e: make("shown")),
        kit.big_button("كل المعاملات (بدون فلتر)", lambda e: make("all"), outline=True),
        kit.txt(paths.export_dir(), 11, color=T.FAINT, selectable=True),
    ], spacing=12), height=330)
