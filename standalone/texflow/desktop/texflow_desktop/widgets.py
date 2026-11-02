"""Общие виджеты: таблица с прокруткой, форма полей, сообщения."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from texflow.i18n import _


class Table(ttk.Frame):
    """Treeview с прокруткой. columns: [(ключ, заголовок, ширина, выравнивание)]."""

    def __init__(self, master, columns, height=10, on_select=None, on_double=None):
        super().__init__(master)
        self.keys = [c[0] for c in columns]
        self.tree = ttk.Treeview(self, columns=self.keys, show="headings", height=height, selectmode="browse")
        for key, title, width, anchor in columns:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, anchor=anchor, stretch=True)
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        if on_select:
            self.tree.bind("<<TreeviewSelect>>", lambda _e: on_select(self.selected()))
        if on_double:
            self.tree.bind("<Double-1>", lambda _e: on_double(self.selected()))
        self.tree.tag_configure("bad", foreground="#b3202a")
        self.tree.tag_configure("ok", foreground="#1e7a3c")
        self.tree.tag_configure("warn", foreground="#a86a00")

    def fill(self, rows, iid_key="id", tag=None):
        self.tree.delete(*self.tree.get_children())
        for i, r in enumerate(rows):
            iid = str(r.get(iid_key, i)) if isinstance(r, dict) else str(i)
            vals = [("" if r.get(k) is None else r.get(k)) for k in self.keys]
            self.tree.insert("", "end", iid=iid, values=vals, tags=(tag(r),) if tag else ())

    def selected(self):
        sel = self.tree.selection()
        return sel[0] if sel else None

    def select(self, iid):
        if self.tree.exists(str(iid)):
            self.tree.selection_set(str(iid))
            self.tree.see(str(iid))

    def count(self):
        return len(self.tree.get_children())


class Form(ttk.Frame):
    """Сетка «подпись — поле». fields: [(ключ, подпись, вид, значения)] вид: entry|combo|check|spin."""

    def __init__(self, master, fields, cols=2):
        super().__init__(master)
        self.vars, self.widgets = {}, {}
        for i, f in enumerate(fields):
            key, label, kind = f[0], f[1], (f[2] if len(f) > 2 else "entry")
            r, c = divmod(i, cols)
            ttk.Label(self, text=label).grid(row=r, column=c * 2, sticky="w", padx=(0, 6), pady=2)
            if kind == "check":
                var = tk.BooleanVar()
                w = ttk.Checkbutton(self, variable=var)
            elif kind == "combo":
                var = tk.StringVar()
                w = ttk.Combobox(self, textvariable=var, values=f[3] if len(f) > 3 else [], state="readonly", width=24)
            else:
                var = tk.StringVar()
                w = ttk.Entry(self, textvariable=var, width=26)
            w.grid(row=r, column=c * 2 + 1, sticky="we", padx=(0, 14), pady=2)
            self.vars[key], self.widgets[key] = var, w
        for c in range(cols):
            self.columnconfigure(c * 2 + 1, weight=1)

    def get(self, key, default=""):
        v = self.vars[key].get()
        return v if v not in ("", None) else default

    def num(self, key, default=0.0):
        try:
            return float(str(self.vars[key].get()).replace(",", ".").strip() or default)
        except ValueError:
            return default

    def set(self, key, value):
        self.vars[key].set("" if value is None else value)

    def set_many(self, d: dict):
        for k, v in d.items():
            if k in self.vars:
                self.set(k, v)


def info(msg, title="TexFlow"):
    messagebox.showinfo(title, msg)


def error(msg, title="TexFlow"):
    messagebox.showerror(title, str(msg))


def ask(msg, title="TexFlow") -> bool:
    return messagebox.askyesno(title, msg)


def ask_string(parent, title, prompt, initial=""):
    from tkinter import simpledialog
    return simpledialog.askstring(title, prompt, initialvalue=initial, parent=parent)


def fmt_money(v):
    return "" if v is None else f"{float(v):.2f}"


def section(parent, text):
    lf = ttk.LabelFrame(parent, text=text, padding=8)
    return lf


def tr_status(code, kind="shipment"):
    from texflow import i18n
    return i18n.status_name(code, kind)


_ = _
