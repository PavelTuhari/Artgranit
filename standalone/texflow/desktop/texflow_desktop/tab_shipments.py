"""Вкладка «Поставки»: список, новая поставка, затраты, упаковочный лист, мешки, сверка."""
from __future__ import annotations

from tkinter import filedialog, ttk

from texflow import exchange, store
from texflow.i18n import _

from .widgets import Form, Table, error, fmt_money, tr_status

ALLOC = ("value", "qty", "weight")


def alloc_names():
    return {"value": _("по стоимости"), "qty": _("по штукам"), "weight": _("по весу мешков")}


class ShipmentsTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=8)
        self.app = app
        self.columnconfigure(0, weight=2)
        self.columnconfigure(1, weight=3)
        self.rowconfigure(1, weight=1)

        left = ttk.Frame(self)
        left.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 8))
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)
        ttk.Label(left, text=_("Поставки"), style="H.TLabel").grid(row=0, column=0, sticky="w")
        self.list = Table(left, [("code", _("Поставка"), 130, "w"), ("supplier", _("Поставщик"), 120, "w"),
                                 ("bags", _("Мешков"), 60, "e"), ("declared", _("По листу"), 70, "e"),
                                 ("counted", _("Принято"), 70, "e"), ("status_t", _("Статус"), 90, "w")],
                          height=12, on_select=self.select)
        self.list.grid(row=1, column=0, sticky="nsew")

        new = ttk.LabelFrame(left, text=_("Новая поставка"), padding=8)
        new.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        self.new_form = Form(new, [("code", _("Номер")), ("supplier", _("Поставщик")),
                                   ("country", _("Страна"), "combo", ["TR", "CN", "OTHER"]),
                                   ("currency", _("Валюта"), "combo", ["USD", "EUR", "TRY", "CNY", "MDL"]),
                                   ("fx_rate", _("Курс к местной")), ("bags", _("Мешков (создать 1..N)"))], cols=2)
        self.new_form.pack(fill="x")
        self.new_form.set_many({"country": "TR", "currency": "USD", "fx_rate": "17.8", "bags": "0"})
        self.btn_create = ttk.Button(new, text=_("Создать"), style="Accent.TButton", command=self.create)
        self.btn_create.pack(anchor="e", pady=(6, 0))

        right = ttk.Frame(self)
        right.grid(row=0, column=1, rowspan=2, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(2, weight=1)
        self.title = ttk.Label(right, text="", style="H.TLabel")
        self.title.grid(row=0, column=0, sticky="w")

        top = ttk.Frame(right)
        top.grid(row=1, column=0, sticky="ew")
        top.columnconfigure(0, weight=1)
        costs = ttk.LabelFrame(top, text=_("Импортные затраты"), padding=8)
        costs.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.costs = Form(costs, [("currency", _("Валюта")), ("fx_rate", _("Курс к местной")),
                                  ("freight", _("Фрахт")), ("customs", _("Таможня")), ("broker", _("Брокер")),
                                  ("other_costs", _("Прочее")),
                                  ("alloc", _("Распределение"), "combo", list(alloc_names().values()))], cols=2)
        self.costs.pack(fill="x")
        self.btn_save = ttk.Button(costs, text=_("Сохранить и пересчитать"), command=self.save_costs)
        self.btn_save.pack(anchor="e", pady=(6, 0))
        self.totals = ttk.Label(costs, text="", style="Muted.TLabel", justify="left")
        self.totals.pack(anchor="w")

        side = ttk.LabelFrame(top, text=_("Упаковочный лист (примерный)"), padding=8)
        side.grid(row=0, column=1, sticky="nsew")
        ttk.Label(side, text="CSV / Excel", style="Muted.TLabel").pack(anchor="w")
        ttk.Button(side, text=_("Загрузить"), command=self.import_packing).pack(fill="x", pady=2)
        bag_row = ttk.Frame(side)
        bag_row.pack(fill="x", pady=(8, 0))
        self.bag_form = Form(bag_row, [("bag_no", _("№ мешка")), ("weight", _("Вес, кг"))], cols=1)
        self.bag_form.pack(fill="x")
        ttk.Button(side, text=_("Добавить мешок"), command=self.add_bag).pack(fill="x", pady=2)
        ttk.Button(side, text=_("Разбор мешков"), style="Accent.TButton",
                   command=lambda: self.app.show("sort")).pack(fill="x", pady=(8, 2))

        nb = ttk.Notebook(right)
        nb.grid(row=2, column=0, sticky="nsew", pady=(8, 0))
        self.bags = Table(nb, [("bag_no", _("Мешок"), 80, "w"), ("weight_kg", _("Вес"), 70, "e"),
                               ("declared", _("По листу"), 80, "e"), ("counted", _("Принято"), 80, "e"),
                               ("status_t", _("Статус"), 110, "w")], height=8,
                          on_double=self.open_bag)
        self.packing = Table(nb, [("bag_no", _("Мешок"), 60, "w"), ("category", _("Категория"), 150, "w"),
                                  ("description", _("Описание"), 220, "w"), ("qty", _("Шт"), 60, "e"),
                                  ("unit_price_fx", _("Цена"), 70, "e"), ("weight_kg", _("Вес"), 60, "e")], height=8)
        cols = [("key", "", 200, "w"), ("declared", _("По листу"), 80, "e"), ("counted", _("Факт"), 80, "e"),
                ("diff", _("Разница"), 80, "e"), ("status_t", _("Статус"), 110, "w")]
        self.rec_cat = Table(nb, cols, height=8)
        self.rec_bag = Table(nb, cols, height=8)
        nb.add(self.bags, text=_("Мешки"))
        nb.add(self.packing, text=_("Упаковочный лист (примерный)"))
        nb.add(self.rec_cat, text=_("Сверка по категориям"))
        nb.add(self.rec_bag, text=_("Сверка по мешкам"))
        self.refresh()

    # ------------------------------------------------------------------ данные
    def refresh(self):
        rows = []
        for s in store.shipments(self.app.con):
            d = dict(s)
            d["status_t"] = tr_status(s["status"])
            rows.append(d)
        self.list.fill(rows)
        if self.app.shipment_id is None and rows:
            self.app.shipment_id = rows[0]["id"]
        if self.app.shipment_id:
            self.list.select(self.app.shipment_id)
        self.show_shipment()

    def select(self, iid):
        if iid:
            self.app.shipment_id = int(iid)
            self.show_shipment()

    def show_shipment(self):
        sid = self.app.shipment_id
        sh = store.shipment(self.app.con, sid) if sid else None
        if not sh:
            self.title.config(text=_("Создать поставку"))
            for t in (self.bags, self.packing, self.rec_cat, self.rec_bag):
                t.fill([])
            return
        self.title.config(text=f"{_('Поставка')} {sh['code']} · {tr_status(sh['status'])}")
        names = alloc_names()
        self.costs.set_many({"currency": sh["currency"], "fx_rate": sh["fx_rate"], "freight": sh["freight"],
                             "customs": sh["customs"], "broker": sh["broker"], "other_costs": sh["other_costs"],
                             "alloc": names[sh["alloc_method"]]})
        store.compute_landed(self.app.con, sid)
        t = store.shipment_totals(self.app.con, sid)
        self.totals.config(text=f"{_('Принято штук')}: {t['pcs']}   {_('Товар в местной')}: {fmt_money(t['goods_local'])}\n"
                                f"{_('Общие затраты')}: {fmt_money(t['lump'])}   "
                                f"{_('Себестоимость всего / средняя за шт.')}: {fmt_money(t['landed'])} / "
                                f"{fmt_money(t['avg_landed'])}")
        bags = []
        for b in store.bags(self.app.con, sid):
            d = dict(b)
            d["status_t"] = tr_status(b["status"], "bag")
            bags.append(d)
        self.bags.fill(bags)
        self.packing.fill([dict(p) | {"category": p["category"] or "?"} for p in store.packing_lines(self.app.con, sid)])
        rec = store.reconciliation(self.app.con, sid)
        st = {"ok": _("совпало"), "short": _("недостача"), "over": _("излишек"), "extra": _("нет в листе")}
        tag = lambda r: {"ok": "ok", "short": "bad"}.get(r["status"], "warn")  # noqa: E731
        self.rec_cat.fill([r | {"status_t": st[r["status"]], "id": i} for i, r in enumerate(rec["by_category"])], tag=tag)
        self.rec_bag.fill([r | {"status_t": st[r["status"]], "id": i} for i, r in enumerate(rec["by_bag"])], tag=tag)

    # ------------------------------------------------------------------ действия
    def create(self):
        f = self.new_form
        code = f.get("code").strip()
        if not code:
            error(_("Укажите номер поставки"))
            return
        try:
            sid = store.create_shipment(self.app.con, code, f.get("supplier"), f.get("country", "TR"),
                                        f.get("currency", "USD"), f.num("fx_rate", 1))
        except Exception as e:  # noqa: BLE001
            error(_("Не создано: {e}", e=e))
            return
        for k in range(1, int(f.num("bags", 0)) + 1):
            store.ensure_bag(self.app.con, sid, str(k))
        self.app.con.commit()
        self.app.shipment_id = sid
        f.set("code", "")
        self.app.say(_("Поставка {code} создана", code=code))
        self.refresh()

    def save_costs(self):
        sid = self.app.shipment_id
        if not sid:
            return
        c = self.costs
        inv = {v: k for k, v in alloc_names().items()}
        store.update_shipment(self.app.con, sid, currency=c.get("currency", "USD").upper(), fx_rate=c.num("fx_rate", 1),
                              freight=c.num("freight"), customs=c.num("customs"), broker=c.num("broker"),
                              other_costs=c.num("other_costs"), alloc_method=inv.get(c.get("alloc"), "value"))
        store.compute_landed(self.app.con, sid)
        self.app.say(_("Затраты сохранены, себестоимость пересчитана"))
        self.refresh()

    def import_packing(self, path: str | None = None):
        sid = self.app.shipment_id
        if not sid:
            error(_("Выберите поставку"))
            return
        path = path or filedialog.askopenfilename(filetypes=[("CSV / Excel", "*.csv *.txt *.tsv *.xlsx *.xlsm")])
        if not path:
            return
        try:
            with open(path, "rb") as fh:
                r = exchange.import_packing(self.app.con, sid, fh.read(), path)
        except Exception as e:  # noqa: BLE001
            error(_("Не загружено: {e}", e=e))
            return
        msg = _("Загружено строк: {lines}, мешков: {bags}", lines=r["lines"], bags=r["bags"])
        if r["unknown_categories"]:
            msg += ". " + _("Не распознаны категории: ") + ", ".join(r["unknown_categories"])
        self.app.say(msg)
        self.refresh()
        return r

    def add_bag(self):
        sid, no = self.app.shipment_id, self.bag_form.get("bag_no").strip()
        if sid and no:
            store.ensure_bag(self.app.con, sid, no, self.bag_form.num("weight") or None)
            self.app.con.commit()
            self.bag_form.set("bag_no", "")
            self.refresh()

    def open_bag(self, iid):
        if iid:
            self.app.bag_id = int(iid)
            self.app.show("sort")
