"""Главное окно TexFlow Desktop: вкладки, язык, база."""
from __future__ import annotations

import sys
import tkinter as tk
from tkinter import ttk

from texflow import __version__, db, i18n, store
from texflow.i18n import _

from . import paths

TAB_KEYS = ("shipments", "sort", "pricing", "catalog", "labels", "editor", "exchange", "settings")


class App(tk.Tk):
    def __init__(self, db_file: str | None = None, lang: str | None = None):
        super().__init__()
        self.db_file = db_file or paths.db_path()
        self.con = db.connect(self.db_file)
        db.init_db(self.con)
        st = store.settings(self.con)
        i18n.set_lang(lang or st.get("ui_lang", "ru"))
        self.shipment_id: int | None = None
        self.bag_id: int | None = None
        self.tabs: dict = {}
        self._style()
        self.geometry("1360x860")
        self.minsize(1080, 700)
        self.build()

    # ------------------------------------------------------------------ оформление
    def _style(self):
        s = ttk.Style(self)
        if "clam" in s.theme_names():
            s.theme_use("clam")
        base = ("Helvetica", 10)
        self.option_add("*Font", base)
        s.configure("TNotebook.Tab", padding=(14, 6))
        s.configure("Treeview", rowheight=24)
        s.configure("Treeview.Heading", font=("Helvetica", 9, "bold"))
        s.configure("Accent.TButton", foreground="#ffffff", background="#111111")
        s.map("Accent.TButton", background=[("active", "#333333")])
        s.configure("Big.TLabel", font=("Helvetica", 18, "bold"))
        s.configure("H.TLabel", font=("Helvetica", 12, "bold"))
        s.configure("Muted.TLabel", foreground="#666666")
        s.configure("Ok.TLabel", foreground="#1e7a3c")
        s.configure("Bad.TLabel", foreground="#b3202a")

    # ------------------------------------------------------------------ сборка
    def build(self):
        for w in self.winfo_children():
            w.destroy()
        self.title(f"TexFlow {__version__} — {_('Приёмка одежды из мешков')}")
        self._menu()
        top = ttk.Frame(self, padding=(10, 6))
        top.pack(fill="x")
        ttk.Label(top, text="TEXFLOW", style="H.TLabel").pack(side="left")
        ttk.Label(top, text=f"  {_('Приёмка одежды из мешков')}", style="Muted.TLabel").pack(side="left")
        for code in reversed(i18n.LANGS):
            b = ttk.Button(top, text=code.upper(), width=4, command=lambda c=code: self.set_language(c),
                           style="Accent.TButton" if code == i18n.current_lang() else "TButton")
            b.pack(side="right", padx=1)
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=8, pady=(0, 4))
        from .tab_shipments import ShipmentsTab
        from .tab_sort import SortTab
        from .tab_pricing import PricingTab
        from .tab_catalog import CatalogTab
        from .tab_labels import LabelsTab
        from .label_editor import LabelEditor
        from .tab_exchange import ExchangeTab
        from .tab_settings import SettingsTab
        titles = {"shipments": _("Поставки"), "sort": _("Разбор"), "pricing": _("Цены"), "catalog": _("Каталог"),
                  "labels": _("Этикетки"), "editor": _("Редактор этикеток"), "exchange": "Excel / CSV",
                  "settings": _("Настройки")}
        classes = {"shipments": ShipmentsTab, "sort": SortTab, "pricing": PricingTab, "catalog": CatalogTab,
                   "labels": LabelsTab, "editor": LabelEditor, "exchange": ExchangeTab, "settings": SettingsTab}
        self.tabs = {}
        for key in TAB_KEYS:
            frame = classes[key](self.nb, self)
            self.nb.add(frame, text=titles[key])
            self.tabs[key] = frame
        self.nb.bind("<<NotebookTabChanged>>", self._on_tab)
        self.status = tk.StringVar()
        bar = ttk.Frame(self, padding=(10, 2))
        bar.pack(fill="x")
        ttk.Label(bar, textvariable=self.status, style="Muted.TLabel").pack(side="left")
        ttk.Label(bar, text=f"{self.db_file}", style="Muted.TLabel").pack(side="right")
        self.say(_("Готово"))

    def _menu(self):
        m = tk.Menu(self)
        f = tk.Menu(m, tearoff=0)
        f.add_command(label=_("Загрузить демо-поставку"), command=self.load_demo)
        f.add_command(label=_("Открыть папку данных"), command=lambda: paths.open_path(paths.data_dir()))
        f.add_separator()
        f.add_command(label=_("Выход"), command=self.destroy)
        m.add_cascade(label=_("Файл"), menu=f)
        lang = tk.Menu(m, tearoff=0)
        for code in i18n.LANGS:
            lang.add_command(label=i18n.LANG_NAMES[code], command=lambda c=code: self.set_language(c))
        m.add_cascade(label=_("Язык"), menu=lang)
        h = tk.Menu(m, tearoff=0)
        h.add_command(label=_("О программе"), command=self.about)
        m.add_cascade(label="?", menu=h)
        self.config(menu=m)

    def _on_tab(self, _e=None):
        key = self.current_tab()
        if key and hasattr(self.tabs[key], "refresh"):
            self.tabs[key].refresh()

    # ------------------------------------------------------------------ общее
    def current_tab(self) -> str | None:
        try:
            idx = self.nb.index(self.nb.select())
        except tk.TclError:
            return None
        return TAB_KEYS[idx]

    def show(self, key: str):
        self.nb.select(TAB_KEYS.index(key))
        self.update_idletasks()
        self._on_tab()

    def say(self, msg: str):
        self.status.set(msg)

    def set_language(self, code: str):
        i18n.set_lang(code)
        store.save_settings(self.con, {"ui_lang": code})
        current = self.current_tab() or "shipments"
        self.build()
        self.show(current)

    def load_demo(self):
        from texflow.demo import load_demo
        msg = load_demo(self.con)
        self.say(msg)
        self._on_tab()

    def about(self):
        from .widgets import info
        info(f"TexFlow {__version__}\n{_('Приёмка одежды из мешков')}\n\n"
             f"{paths.platform_name()}\nTk {tk.TkVersion}\n\n{_('База данных')}: {self.db_file}")


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="TexFlow Desktop")
    ap.add_argument("--db", default=None)
    ap.add_argument("--lang", choices=i18n.LANGS, default=None)
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args(argv)
    app = App(a.db, a.lang)
    if a.demo:
        app.load_demo()
    app.mainloop()


if __name__ == "__main__":
    main(sys.argv[1:])
