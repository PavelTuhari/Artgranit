"""Вкладка «Цены»: себестоимость, предложение по наценкам, своя цена, запись в карточки."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from texflow import store
from texflow.i18n import _

from .widgets import Table, ask_string, fmt_money


class PricingTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=8)
        self.app = app
        self.overrides: dict[int, float] = {}
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        bar = ttk.Frame(self)
        bar.grid(row=0, column=0, sticky="ew")
        ttk.Label(bar, text=_("Ценообразование"), style="H.TLabel").pack(side="left")
        self.sh_combo = ttk.Combobox(bar, state="readonly", width=24)
        self.sh_combo.pack(side="left", padx=12)
        self.sh_combo.bind("<<ComboboxSelected>>", lambda _e: self._pick())
        self.info = ttk.Label(self, text="", style="Muted.TLabel", wraplength=1200, justify="left")
        self.info.grid(row=1, column=0, sticky="w", pady=6)
        self.table = Table(self, [("style_code", _("Артикул"), 90, "w"), ("name", _("Модель"), 220, "w"),
                                  ("category", _("Категория"), 150, "w"), ("qty", _("Шт"), 50, "e"),
                                  ("cost_fx_t", _("Закупка"), 80, "e"), ("landed_t", _("Себест."), 80, "e"),
                                  ("markup_t", _("Наценка"), 70, "e"), ("gross_t", _("Расчёт"), 80, "e"),
                                  ("price_t", _("Предложено"), 90, "e"), ("real_t", _("Факт. наценка"), 90, "e"),
                                  ("current_t", _("Текущая"), 90, "e"), ("own_t", _("Своя цена"), 90, "e")],
                           height=16, on_double=self.own_price)
        self.table.grid(row=2, column=0, sticky="nsew")
        act = ttk.Frame(self)
        act.grid(row=3, column=0, sticky="ew", pady=(6, 0))
        ttk.Label(act, text=_("Своя цена") + ": " + _("двойной щелчок по строке"), style="Muted.TLabel").pack(side="left")
        ttk.Button(act, text=_("Записать цены в карточки"), style="Accent.TButton", command=self.apply).pack(side="right")
        ttk.Button(act, text=_("К этикеткам"), command=self.to_labels).pack(side="right", padx=6)
        self.refresh()

    def refresh(self):
        shs = store.shipments(self.app.con)
        self._ids = [s["id"] for s in shs]
        self.sh_combo["values"] = [s["code"] for s in shs]
        if self.app.shipment_id in self._ids:
            self.sh_combo.current(self._ids.index(self.app.shipment_id))
        self.load()

    def _pick(self):
        self.app.shipment_id = self._ids[self.sh_combo.current()]
        self.overrides = {}
        self.load()

    def load(self):
        sid = self.app.shipment_id
        if not sid:
            self.table.fill([])
            return
        sh = store.shipment(self.app.con, sid)
        st = store.settings(self.app.con)
        t = store.shipment_totals(self.app.con, sid)
        vat = f" × (1 + {_('НДС')} {st['vat_pct']}%)" if st.get("prices_include_vat") == "1" else ""
        self.info.config(text=_("Себестоимость = закупка × курс {fx} + пошлина категории + доля затрат поставки "
                                "({lump} {cur}, {method}).", fx=sh["fx_rate"], lump=fmt_money(t["lump"]),
                                cur=st["currency"], method={"value": _("по стоимости"), "qty": _("по штукам"),
                                                            "weight": _("по весу мешков")}[sh["alloc_method"]])
                         + " " + _("Цена = себестоимость × (1 + наценка категории)") + vat
                         + _(", округление вверх до шага {step} минус {end}. Мин. наценка {min}%.",
                             step=st["round_step"], end=st["round_ending"], min=st["min_markup_pct"]))
        rows = []
        for r in store.price_proposal(self.app.con, sid):
            rows.append(r | {"cost_fx_t": fmt_money(r["cost_fx"]), "landed_t": fmt_money(r["landed"]),
                             "markup_t": f"{r['markup_pct']:g}%", "gross_t": fmt_money(r["gross"]),
                             "price_t": fmt_money(r["price"]), "real_t": f"{r['real_markup_pct']}%",
                             "current_t": (fmt_money(r["retail_price"]) if r["retail_price"] is not None else "—")
                             + (" 🔒" if r["price_locked"] else ""),
                             "own_t": fmt_money(self.overrides.get(r["id"])) if r["id"] in self.overrides else ""})
        self.rows = rows
        self.table.fill(rows)

    def own_price(self, iid, value: float | None = None):
        if not iid:
            return
        if value is None:
            s = ask_string(self, _("Своя цена"), _("Своя цена"), "")
            if not s:
                return
            try:
                value = float(s.replace(",", "."))
            except ValueError:
                return
        self.overrides[int(iid)] = value
        self.load()

    def apply(self):
        sid = self.app.shipment_id
        if sid:
            n = store.apply_prices(self.app.con, sid, self.overrides)
            self.overrides = {}
            self.app.say(_("Цены записаны в {n} карточек", n=n))
            self.load()
            return n
        return 0

    def to_labels(self):
        if self.app.shipment_id:
            self.app.tabs["labels"].set_selection(store.labels_for_shipment(self.app.con, self.app.shipment_id))
            self.app.show("labels")
