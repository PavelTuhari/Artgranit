"""Вкладка «Excel / CSV»: выгрузка наборов данных и полного отчёта, загрузка листа, цен, каталога, приёмки."""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, ttk

from texflow import exchange, store
from texflow.i18n import _

from . import paths
from .widgets import error

IMPORT_KINDS = ("packing", "catalog", "prices", "intake")


def import_names():
    return {"packing": _("Упаковочный лист"), "catalog": _("Каталог: модели и варианты"),
            "prices": _("Цены (после правки в Excel)"), "intake": _("Результаты приёмки с другого места")}


class ExchangeTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=12)
        self.app = app
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        ex = ttk.LabelFrame(self, text=_("Выгрузка"), padding=10)
        ex.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        ttk.Label(ex, text=_("Набор данных")).grid(row=0, column=0, sticky="w")
        self.ds_keys = ["full"] + list(exchange.DATASETS)
        self.ds_combo = ttk.Combobox(ex, state="readonly", width=36,
                                     values=[_("Полный отчёт (Excel, все листы)")] +
                                     [exchange.dataset_title(d) for d in exchange.DATASETS])
        self.ds_combo.current(0)
        self.ds_combo.grid(row=0, column=1, sticky="ew", pady=2)
        ttk.Label(ex, text=_("Поставка")).grid(row=1, column=0, sticky="w")
        self.sh_combo = ttk.Combobox(ex, state="readonly", width=36)
        self.sh_combo.grid(row=1, column=1, sticky="ew", pady=2)
        bf = ttk.Frame(ex)
        bf.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Button(bf, text="Excel (.xlsx)", style="Accent.TButton", command=lambda: self.export("xlsx")).pack(side="left")
        ttk.Button(bf, text="CSV", command=lambda: self.export("csv")).pack(side="left", padx=6)
        self.open_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(ex, text=_("Открыть файл после выгрузки"), variable=self.open_var).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))
        ex.columnconfigure(1, weight=1)

        im = ttk.LabelFrame(self, text=_("Загрузка"), padding=10)
        im.grid(row=0, column=1, sticky="nsew")
        ttk.Label(im, text=_("Что загружаем")).grid(row=0, column=0, sticky="w")
        self.kind_combo = ttk.Combobox(im, state="readonly", width=36, values=[import_names()[k] for k in IMPORT_KINDS])
        self.kind_combo.current(0)
        self.kind_combo.grid(row=0, column=1, sticky="ew", pady=2)
        ttk.Label(im, text=_("Поставка")).grid(row=1, column=0, sticky="w")
        self.ish_combo = ttk.Combobox(im, state="readonly", width=36)
        self.ish_combo.grid(row=1, column=1, sticky="ew", pady=2)
        ttk.Button(im, text=_("Выберите файл CSV или Excel") + "…", style="Accent.TButton",
                   command=self.do_import).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        im.columnconfigure(1, weight=1)
        ttk.Label(self, text=_("Заголовки колонок понимаются на русском, румынском и английском. Цены: выгрузите «Цены», "
                               "поправьте колонку «Цена» в Excel и загрузите обратно. Каталог: если выбрана поставка и "
                               "заполнено «Кол-во», вещи сразу попадают в приёмку."),
                  style="Muted.TLabel", wraplength=1100, justify="left").grid(row=1, column=0, columnspan=2, sticky="w",
                                                                             pady=10)
        self.result = tk.Text(self, height=12, font=("Courier", 10))
        self.result.grid(row=2, column=0, columnspan=2, sticky="nsew")
        self.rowconfigure(2, weight=1)
        self.refresh()

    def refresh(self):
        shs = store.shipments(self.app.con)
        self._sh_ids = [None] + [s["id"] for s in shs]
        vals = ["— " + _("все") + " —"] + [s["code"] for s in shs]
        for cb in (self.sh_combo, self.ish_combo):
            cur = cb.current()
            cb["values"] = vals
            cb.current(cur if 0 <= cur < len(vals) else 0)
        if self.app.shipment_id in self._sh_ids and self.ish_combo.current() == 0:
            self.ish_combo.current(self._sh_ids.index(self.app.shipment_id))

    def log(self, msg):
        self.result.insert("1.0", msg + "\n")

    def export(self, fmt: str, path: str | None = None):
        ds = self.ds_keys[self.ds_combo.current()]
        sid = self._sh_ids[self.sh_combo.current()]
        try:
            data, name, _mime = exchange.export(self.app.con, ds, fmt, sid)
        except ValueError as e:
            error(e)
            return None
        path = path or filedialog.asksaveasfilename(initialdir=paths.documents_dir(), initialfile=name,
                                                    defaultextension="." + fmt)
        if not path:
            return None
        with open(path, "wb") as f:
            f.write(data)
        self.log(f"✓ {path}")
        self.app.say(path)
        if self.open_var.get():
            try:
                paths.open_path(path)
            except Exception:  # noqa: BLE001
                pass
        return path

    def do_import(self, path: str | None = None, kind: str | None = None):
        kind = kind or IMPORT_KINDS[self.kind_combo.current()]
        sid = self._sh_ids[self.ish_combo.current()]
        path = path or filedialog.askopenfilename(filetypes=[("CSV / Excel", "*.csv *.txt *.tsv *.xlsx *.xlsm")])
        if not path:
            return None
        con = self.app.con
        try:
            with open(path, "rb") as f:
                data = f.read()
            if kind in ("packing", "intake") and not sid:
                raise ValueError(_("Выберите поставку"))
            if kind == "packing":
                r = exchange.import_packing(con, sid, data, path)
                msg = _("Загружено строк: {lines}, мешков: {bags}", lines=r["lines"], bags=r["bags"])
            elif kind == "prices":
                r = exchange.import_prices(con, data, path)
                msg = _("Цены обновлены: {n}; неизвестные артикулы: {u}", n=r["updated"], u=", ".join(r["unknown"]) or "—")
            elif kind == "catalog":
                r = exchange.import_catalog(con, data, path, sid)
                msg = _("Моделей создано: {p}, вариантов: {v}, принято шт.: {q}", p=r["products"], v=r["variants"],
                        q=r["received"])
                if r["errors"]:
                    msg += "\n" + _("Ошибки в строках: ") + "\n  " + "\n  ".join(r["errors"])
            else:
                r = exchange.import_intake(con, sid, data, path)
                msg = _("Принято {n} шт.", n=r["pcs"]) + ("\n" + _("Не найдены: ") + ", ".join(r["unknown"])
                                                          if r["unknown"] else "")
        except Exception as e:  # noqa: BLE001
            error(_("Не загружено: {e}", e=e))
            return None
        self.log(f"✓ {path}\n{msg}")
        self.app.say(msg.splitlines()[0])
        return r
