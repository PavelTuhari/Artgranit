"""Вкладка «Этикетки»: что печатать, шаблон, формат, файл / сетевой принтер / системный принтер."""
from __future__ import annotations

import os
import tempfile
import tkinter as tk
from tkinter import filedialog, ttk

from texflow import label_templates as LT, printing, store
from texflow.i18n import _

from . import label_canvas, paths
from .widgets import Table, ask_string, error

FORMATS = ("pdf_a4", "pdf_roll", "zpl", "tspl")


def format_names(st):
    return {"pdf_a4": _("PDF A4 — лист {c}×{r} (обычный принтер)", c=st.get("sheet_cols"), r=st.get("sheet_rows")),
            "pdf_roll": _("PDF рулон: страница = этикетка шаблона (виртуальный/любой драйвер)"),
            "zpl": _("ZPL — Zebra"), "tspl": _("TSPL — TSC")}


class LabelsTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=8)
        self.app = app
        self.selection: dict[int, int] = {}
        self.columnconfigure(0, weight=3)
        self.columnconfigure(1, weight=2)
        self.rowconfigure(1, weight=1)
        src = ttk.Frame(self)
        src.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        ttk.Label(src, text=_("Поставка")).pack(side="left")
        self.sh_combo = ttk.Combobox(src, state="readonly", width=22)
        self.sh_combo.pack(side="left", padx=4)
        ttk.Label(src, text=_("Мешок")).pack(side="left", padx=(10, 0))
        self.bag_combo = ttk.Combobox(src, state="readonly", width=18)
        self.bag_combo.pack(side="left", padx=4)
        self.sh_combo.bind("<<ComboboxSelected>>", lambda _e: self._fill_bags())
        ttk.Button(src, text=_("Выбрать"), command=self.take_received).pack(side="left", padx=6)
        ttk.Button(src, text=_("Очистить"), command=lambda: self.set_selection({})).pack(side="left")

        self.table = Table(self, [("sku", "SKU", 150, "w"), ("name", _("Модель"), 200, "w"),
                                  ("color", _("Цвет"), 100, "w"), ("size", _("Размер"), 60, "w"),
                                  ("price_t", _("Цена"), 90, "e"), ("ean13", "EAN-13", 120, "w"),
                                  ("copies", _("Копий"), 60, "e")], height=18, on_double=self.edit_copies,
                           on_select=lambda _i: self.preview())
        self.table.grid(row=1, column=0, sticky="nsew", padx=(0, 8))

        right = ttk.Frame(self)
        right.grid(row=1, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        self.summary = ttk.Label(right, text="", style="H.TLabel")
        self.summary.grid(row=0, column=0, sticky="w")
        opt = ttk.LabelFrame(right, text=_("Формат"), padding=8)
        opt.grid(row=1, column=0, sticky="ew", pady=6)
        ttk.Label(opt, text=_("Шаблон этикетки")).grid(row=0, column=0, sticky="w")
        self.tpl_combo = ttk.Combobox(opt, state="readonly", width=34)
        self.tpl_combo.grid(row=0, column=1, sticky="ew")
        self.tpl_combo.bind("<<ComboboxSelected>>", lambda _e: self.preview())
        ttk.Label(opt, text=_("Формат")).grid(row=1, column=0, sticky="w")
        self.fmt_combo = ttk.Combobox(opt, state="readonly", width=34)
        self.fmt_combo.grid(row=1, column=1, sticky="ew")
        ttk.Label(opt, text=_("Начать с ячейки листа A4 (0 = первая)")).grid(row=2, column=0, sticky="w")
        self.cell_var = tk.StringVar(value="0")
        ttk.Entry(opt, textvariable=self.cell_var, width=6).grid(row=2, column=1, sticky="w")
        ttk.Label(opt, text=_("Принтер (для «Печать»)")).grid(row=3, column=0, sticky="w")
        self.target_var = tk.StringVar()
        ttk.Entry(opt, textvariable=self.target_var).grid(row=3, column=1, sticky="ew")
        opt.columnconfigure(1, weight=1)
        btns = ttk.Frame(right)
        btns.grid(row=2, column=0, sticky="ew")
        ttk.Button(btns, text=_("Скачать файлом"), command=self.save_file).pack(fill="x", pady=1)
        ttk.Button(btns, text=_("Открыть / скачать"), command=self.open_file).pack(fill="x", pady=1)
        ttk.Button(btns, text=_("Печать на принтер"), style="Accent.TButton", command=self.print_target).pack(fill="x", pady=1)
        ttk.Button(btns, text=_("Печать на системный принтер (PDF)"), command=self.print_system).pack(fill="x", pady=1)
        ttk.Label(right, text=_("Принтер: tcp://IP:9100 — сетевой Zebra/TSC; cups://ОЧЕРЕДЬ — USB через CUPS (raw); "
                                "dir:///папка — сохранить файл задания. Пусто — из настроек."),
                  style="Muted.TLabel", wraplength=460, justify="left").grid(row=3, column=0, sticky="w", pady=6)
        self.canvas = tk.Canvas(right, height=300, background="#ecebe7", highlightthickness=0)
        self.canvas.grid(row=4, column=0, sticky="nsew")
        right.rowconfigure(4, weight=1)
        self.refresh()

    # ------------------------------------------------------------------ данные
    def refresh(self):
        con = self.app.con
        st = store.settings(con)
        shs = store.shipments(con)
        self._sh_ids = [s["id"] for s in shs]
        self.sh_combo["values"] = [s["code"] for s in shs]
        if self.app.shipment_id in self._sh_ids:
            self.sh_combo.current(self._sh_ids.index(self.app.shipment_id))
        self._fill_bags()
        self._tpls = LT.list_templates(con)
        cur = self.tpl_combo.get()
        self.tpl_combo["values"] = [f"{t['name']} ({t['width_mm']:g}×{t['height_mm']:g})" for t in self._tpls]
        if cur in self.tpl_combo["values"]:
            self.tpl_combo.set(cur)
        elif self._tpls:
            self.tpl_combo.current(0)
        names = format_names(st)
        cur = self.fmt_combo.current()
        self.fmt_combo["values"] = [names[f] for f in FORMATS]
        self.fmt_combo.current(cur if cur >= 0 else 0)
        self._fill_table()

    def _fill_bags(self):
        idx = self.sh_combo.current()
        sid = self._sh_ids[idx] if idx >= 0 else None
        bags = store.bags(self.app.con, sid) if sid else []
        self._bag_ids = [None] + [b["id"] for b in bags]
        self.bag_combo["values"] = [_("все")] + [f"№ {b['bag_no']}" for b in bags]
        self.bag_combo.current(0)

    def take_received(self):
        idx = self.sh_combo.current()
        if idx < 0:
            return
        bag = self._bag_ids[self.bag_combo.current()] if self.bag_combo.current() >= 0 else None
        self.set_selection(store.labels_for_shipment(self.app.con, self._sh_ids[idx], bag))

    def set_selection(self, sel: dict):
        self.selection = {int(k): int(v) for k, v in sel.items() if int(v) > 0}
        self._fill_table()

    def items(self):
        return store.label_rows(self.app.con, self.selection)

    def _fill_table(self):
        rows = []
        for it in self.items():
            rows.append({"id": it.ref, "sku": it.sku, "name": it.name, "color": it.color, "size": it.size,
                         "price_t": it.price_text() or "—", "ean13": it.ean13, "copies": it.copies})
        self.table.fill(rows)
        n = sum(r["copies"] for r in rows)
        self.summary.config(text=_("Выбрано: {v} вариантов, {n} этикеток", v=len(rows), n=n))
        self.preview()

    def edit_copies(self, iid, value: int | None = None):
        if not iid:
            return
        if value is None:
            s = ask_string(self, _("Копий"), _("Копий"), str(self.selection.get(int(iid), 1)))
            if s is None:
                return
            try:
                value = int(s)
            except ValueError:
                return
        if value <= 0:
            self.selection.pop(int(iid), None)
        else:
            self.selection[int(iid)] = value
        self._fill_table()

    def template_id(self):
        i = self.tpl_combo.current()
        return self._tpls[i]["id"] if i >= 0 and self._tpls else None

    def fmt(self):
        i = self.fmt_combo.current()
        return FORMATS[i if i >= 0 else 0]

    def preview(self):
        self.canvas.delete("all")
        tid = self.template_id()
        if not tid:
            return
        tpl = LT.load(self.app.con, tid)
        items = self.items()
        iid = self.table.selected()
        lb = next((i for i in items if str(i.ref) == str(iid)), items[0] if items else LT.sample_label())
        w = max(300, self.canvas.winfo_width() or 420)
        h = max(200, self.canvas.winfo_height() or 300)
        scale = max(2.5, min((w - 40) / tpl.width_mm, (h - 40) / tpl.height_mm, 10))
        label_canvas.draw(self.canvas, tpl, lb, scale, 20, 20)

    # ------------------------------------------------------------------ вывод
    def render(self):
        items = self.items()
        if not items:
            error(_("Нет выбранных этикеток"))
            return None
        try:
            start = int(self.cell_var.get() or 0)
        except ValueError:
            start = 0
        try:
            return store.render_labels(self.app.con, items, self.fmt(), self.template_id(), start)
        except ValueError as e:
            error(e)
            return None

    def save_file(self, path: str | None = None):
        r = self.render()
        if not r:
            return None
        data, ext, _mime = r
        path = path or filedialog.asksaveasfilename(defaultextension="." + ext, initialfile=f"labels.{ext}",
                                                    initialdir=paths.documents_dir())
        if not path:
            return None
        with open(path, "wb") as f:
            f.write(data)
        store.log_label_job(self.app.con, self.fmt(), "file", self._count())
        self.app.say(path)
        return path

    def open_file(self):
        r = self.render()
        if r:
            data, ext, _m = r
            path = os.path.join(tempfile.gettempdir(), f"texflow_labels.{ext}")
            with open(path, "wb") as f:
                f.write(data)
            paths.open_path(path)
            return path
        return None

    def _count(self):
        return sum(self.selection.values())

    def print_target(self):
        r = self.render()
        if not r:
            return None
        data, ext, _m = r
        st = store.settings(self.app.con)
        target = self.target_var.get().strip() or st.get("printer_zpl" if self.fmt() == "zpl" else "printer_tspl", "")
        try:
            msg = printing.dispatch(target, data, ext)
            store.log_label_job(self.app.con, self.fmt(), target, self._count(), "ok", f"{len(data)} B → {target}")
            self.app.say(_("Печать: {n} этикеток — {msg}", n=self._count(), msg=msg))
            return True
        except Exception as e:  # noqa: BLE001
            store.log_label_job(self.app.con, self.fmt(), target, self._count(), "error", str(e))
            error(_("Принтер не ответил: {e}", e=e))
            return False

    def print_system(self):
        if self.fmt() not in ("pdf_a4", "pdf_roll"):
            self.fmt_combo.current(1)
        r = self.render()
        if not r:
            return
        path = os.path.join(tempfile.gettempdir(), "texflow_labels_print.pdf")
        with open(path, "wb") as f:
            f.write(r[0])
        try:
            msg = paths.system_print(path)
            self.app.say(_("Печать: {n} этикеток — {msg}", n=self._count(), msg=msg))
        except Exception as e:  # noqa: BLE001
            error(_("Принтер не ответил: {e}", e=e))
