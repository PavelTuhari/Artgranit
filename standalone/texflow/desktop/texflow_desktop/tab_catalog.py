"""Вкладка «Каталог»: поиск моделей, карточка, переводы RO/EN, цена и фиксация, варианты."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from texflow import store
from texflow.i18n import _

from .widgets import Form, Table, fmt_money


class CatalogTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=8)
        self.app = app
        self.pid: int | None = None
        self.columnconfigure(0, weight=2)
        self.columnconfigure(1, weight=3)
        self.rowconfigure(1, weight=1)
        top = ttk.Frame(self)
        top.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        ttk.Label(top, text=_("Поиск: название, артикул, SKU, EAN")).pack(side="left")
        self.q = tk.StringVar()
        e = ttk.Entry(top, textvariable=self.q, width=40)
        e.pack(side="left", padx=6)
        e.bind("<KeyRelease>", lambda _e: self.refresh())
        self.list = Table(self, [("style_code", _("Артикул"), 90, "w"), ("title", _("Название"), 220, "w"),
                                 ("category", _("Категория"), 140, "w"), ("stock", _("Остаток"), 70, "e"),
                                 ("price_t", _("Цена"), 90, "e")], height=20, on_select=self.open)
        self.list.grid(row=1, column=0, sticky="nsew", padx=(0, 8))

        card = ttk.Frame(self)
        card.grid(row=1, column=1, sticky="nsew")
        card.columnconfigure(0, weight=1)
        card.rowconfigure(3, weight=1)
        self.head = ttk.Label(card, text="", style="Muted.TLabel")
        self.head.grid(row=0, column=0, sticky="w")
        self.big = ttk.Label(card, text="", style="Big.TLabel")
        self.big.grid(row=1, column=0, sticky="w")
        ed = ttk.LabelFrame(card, text=_("Редактировать карточку"), padding=8)
        ed.grid(row=2, column=0, sticky="ew", pady=6)
        self.form = Form(ed, [("name", _("Название") + f" ({_('основное')})"), ("name_ro", _("Название") + " RO"),
                              ("name_en", _("Название") + " EN"), ("composition", _("Состав") + f" ({_('основной')})"),
                              ("composition_ro", _("Состав") + " RO"), ("composition_en", _("Состав") + " EN"),
                              ("base_cost_fx", _("Закупка за шт. (валюта поставки)")),
                              ("retail_price", _("Цена розничная")), ("price_locked", _("Зафиксировать цену"), "check")],
                         cols=3)
        self.form.pack(fill="x")
        b = ttk.Frame(ed)
        b.pack(fill="x", pady=(6, 0))
        ttk.Button(b, text=_("Сохранить"), style="Accent.TButton", command=self.save).pack(side="right")
        ttk.Button(b, text=_("Этикетки модели"), command=self.labels).pack(side="right", padx=6)
        self.variants = Table(card, [("sku", "SKU", 160, "w"), ("ean13", "EAN-13", 130, "w"),
                                     ("color", _("Цвет"), 120, "w"), ("size", _("Размер"), 60, "w"),
                                     ("stock", _("Остаток"), 70, "e")], height=10)
        self.variants.grid(row=3, column=0, sticky="nsew")
        self.refresh()

    def refresh(self):
        st = store.settings(self.app.con)
        rows = [dict(r) | {"price_t": f"{fmt_money(r['retail_price'])} {st['currency']}"
                           if r["retail_price"] is not None else _("без цены")}
                for r in store.products(self.app.con, self.q.get().strip())]
        self.list.fill(rows)
        if self.pid:
            self.list.select(self.pid)
            self.open(str(self.pid))

    def open(self, iid):
        if not iid:
            return
        self.pid = int(iid)
        p = store.product(self.app.con, self.pid)
        if not p:
            return
        st = store.settings(self.app.con)
        self.head.config(text=f"{p['category']} · REF. {p['style_code']}")
        price = f"{fmt_money(p['retail_price'])} {st['currency']}" if p["retail_price"] is not None \
            else _("Цена не назначена")
        self.big.config(text=f"{p['title']}   {price}")
        self.form.set_many({k: p[k] for k in ("name", "name_ro", "name_en", "composition", "composition_ro",
                                              "composition_en", "base_cost_fx", "retail_price")})
        self.form.vars["price_locked"].set(bool(p["price_locked"]))
        self.variants.fill([dict(v) for v in store.variants(self.app.con, self.pid)])

    def save(self):
        if not self.pid:
            return
        f = self.form
        rp = f.get("retail_price").replace(",", ".").strip()
        store.update_product(self.app.con, self.pid, name=f.get("name"), name_ro=f.get("name_ro").strip(),
                             name_en=f.get("name_en").strip(), composition=f.get("composition"),
                             composition_ro=f.get("composition_ro").strip(),
                             composition_en=f.get("composition_en").strip(), base_cost_fx=f.num("base_cost_fx"),
                             retail_price=float(rp) if rp else None,
                             price_locked=1 if f.vars["price_locked"].get() else 0)
        self.app.say(_("Карточка сохранена"))
        self.refresh()

    def labels(self):
        if self.pid:
            sel = {v["id"]: max(v["stock"], 0) or 1 for v in store.variants(self.app.con, self.pid)}
            self.app.tabs["labels"].set_selection(sel)
            self.app.show("labels")
