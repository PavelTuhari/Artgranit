"""Вкладка «Разбор мешка»: сканер, новая модель, матрица цвет × размер, журнал приёмки."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from texflow import store
from texflow.i18n import _

from .widgets import Form, Table, error


class SortTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=8)
        self.app = app
        self.product_id: int | None = None
        self.cells: dict = {}          # (color_id, size_id) → StringVar
        self.rows: list = []           # [(color_id, name, hex)]
        self.columnconfigure(1, weight=1)
        self.rowconfigure(1, weight=1)

        bar = ttk.Frame(self)
        bar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        ttk.Label(bar, text=_("Поставка")).pack(side="left")
        self.sh_var = tk.StringVar()
        self.sh_combo = ttk.Combobox(bar, textvariable=self.sh_var, state="readonly", width=22)
        self.sh_combo.pack(side="left", padx=(4, 14))
        self.sh_combo.bind("<<ComboboxSelected>>", lambda _e: self._pick_shipment())
        ttk.Label(bar, text=_("Мешок")).pack(side="left")
        self.bag_var = tk.StringVar()
        self.bag_combo = ttk.Combobox(bar, textvariable=self.bag_var, state="readonly", width=26)
        self.bag_combo.pack(side="left", padx=(4, 8))
        self.bag_combo.bind("<<ComboboxSelected>>", lambda _e: self._pick_bag())
        ttk.Button(bar, text=_("Мешок разобран"), command=self.bag_done).pack(side="left")

        # ---------------- левая колонка
        left = ttk.Frame(self, width=330)
        left.grid(row=1, column=0, sticky="nsw", padx=(0, 8))
        sc = ttk.LabelFrame(left, text=_("1. Сканер (повторный товар)"), padding=8)
        sc.pack(fill="x")
        self.scan_var = tk.StringVar()
        self.scan_entry = ttk.Entry(sc, textvariable=self.scan_var, font=("Helvetica", 14))
        self.scan_entry.pack(fill="x")
        self.scan_entry.bind("<Return>", lambda _e: self.scan())
        self.scan_log = tk.Listbox(sc, height=4)
        self.scan_log.pack(fill="x", pady=(4, 0))

        nm = ttk.LabelFrame(left, text=_("2. Новая модель"), padding=8)
        nm.pack(fill="x", pady=(8, 0))
        self.cat_map = {}
        self.model = Form(nm, [("name", _("Название")), ("category", _("Категория"), "combo", []),
                               ("style_code", _("Артикул (пусто — авто)")), ("cost", _("Закупка за шт.")),
                               ("composition", _("Состав"))], cols=1)
        self.model.pack(fill="x")
        ttk.Button(nm, text=_("Создать и открыть матрицу"), style="Accent.TButton",
                   command=self.create_model).pack(fill="x", pady=(6, 0))

        fm = ttk.LabelFrame(left, text=_("Недавние модели:"), padding=8)
        fm.pack(fill="both", expand=True, pady=(8, 0))
        self.search_var = tk.StringVar()
        se = ttk.Entry(fm, textvariable=self.search_var)
        se.pack(fill="x")
        se.bind("<KeyRelease>", lambda _e: self._fill_products())
        self.products = tk.Listbox(fm, height=8)
        self.products.pack(fill="both", expand=True, pady=(4, 0))
        self.products.bind("<<ListboxSelect>>", lambda _e: self._pick_product())
        self._product_ids: list[int] = []

        # ---------------- матрица и журнал
        main = ttk.Frame(self)
        main.grid(row=1, column=1, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(2, weight=1)
        self.mtitle = ttk.Label(main, text=_("3. Матрица"), style="H.TLabel")
        self.mtitle.grid(row=0, column=0, sticky="w")
        mx = ttk.Frame(main)
        mx.grid(row=1, column=0, sticky="nsew")
        mx.columnconfigure(0, weight=1)
        self.colors_frame = ttk.Frame(mx)
        self.colors_frame.grid(row=0, column=0, sticky="ew")
        self.grid_frame = ttk.Frame(mx)
        self.grid_frame.grid(row=1, column=0, sticky="w", pady=(8, 0))
        act = ttk.Frame(mx)
        act.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        ttk.Label(act, text=_("Закупка за шт.")).pack(side="left")
        self.cost_var = tk.StringVar()
        ttk.Entry(act, textvariable=self.cost_var, width=10).pack(side="left", padx=(4, 12))
        ttk.Button(act, text=_("Записать (Ctrl+Enter)"), style="Accent.TButton", command=self.save).pack(side="left")
        ttk.Button(act, text=_("Записать и печатать этикетки"), command=lambda: self.save(print_labels=True)).pack(
            side="left", padx=6)
        self.total_var = tk.StringVar(value="Σ 0")
        ttk.Label(act, textvariable=self.total_var, style="H.TLabel").pack(side="right")

        lg = ttk.LabelFrame(main, text=_("Журнал приёмки"), padding=6)
        lg.grid(row=2, column=0, sticky="nsew", pady=(8, 0))
        lg.columnconfigure(0, weight=1)
        lg.rowconfigure(0, weight=1)
        self.log = Table(lg, [("time", _("Время"), 70, "w"), ("bag_no", _("Мешок"), 60, "w"), ("sku", "SKU", 150, "w"),
                              ("name", _("Модель"), 200, "w"), ("color", _("Цвет"), 100, "w"),
                              ("size", _("Размер"), 60, "w"), ("qty", _("Шт"), 50, "e")], height=7)
        self.log.grid(row=0, column=0, sticky="nsew")
        ttk.Button(lg, text=_("удалить строку"), command=self.delete_line).grid(row=1, column=0, sticky="e", pady=(4, 0))
        self.bind_all("<Control-Return>", lambda _e: self.save() if self.app.current_tab() == "sort" else None)
        self.refresh()

    # ------------------------------------------------------------------ обновление
    def refresh(self):
        con = self.app.con
        shs = store.shipments(con)
        self._sh_ids = [s["id"] for s in shs]
        self.sh_combo["values"] = [s["code"] for s in shs]
        if self.app.shipment_id in self._sh_ids:
            self.sh_combo.current(self._sh_ids.index(self.app.shipment_id))
        elif shs:
            self.app.shipment_id = shs[0]["id"]
            self.sh_combo.current(0)
        cats = store.categories(con)
        self.cat_map = {f"{c['title']} ({c['code']})": c["id"] for c in cats}
        self.model.widgets["category"]["values"] = list(self.cat_map)
        if not self.model.get("category") and cats:
            self.model.widgets["category"].current(0)
        self._fill_bags()
        self._fill_products()
        self._fill_log()
        self.scan_entry.focus_set()

    def _fill_bags(self):
        sid = self.app.shipment_id
        bags = store.bags(self.app.con, sid) if sid else []
        self._bag_ids = [None] + [b["id"] for b in bags]
        self.bag_combo["values"] = [_("без мешка")] + [f"№ {b['bag_no']} · {b['counted']}/{b['declared']}"
                                                       + (" ✓" if b["status"] == "done" else "") for b in bags]
        self.bag_combo.current(self._bag_ids.index(self.app.bag_id) if self.app.bag_id in self._bag_ids else 0)
        if self.app.bag_id not in self._bag_ids:
            self.app.bag_id = None

    def _fill_products(self):
        rows = store.products(self.app.con, self.search_var.get().strip())[:40]
        self._product_ids = [r["id"] for r in rows]
        self.products.delete(0, "end")
        for r in rows:
            self.products.insert("end", f"{r['style_code']} · {r['title']} ({r['stock']})")

    def _fill_log(self):
        sid = self.app.shipment_id
        rows = []
        for r in store.intake_log(self.app.con, sid, self.app.bag_id, 80) if sid else []:
            d = dict(r)
            d["time"] = (r["created_at"] or "")[11:]
            d["bag_no"] = r["bag_no"] or "—"
            rows.append(d)
        self.log.fill(rows)

    def _pick_shipment(self):
        self.app.shipment_id = self._sh_ids[self.sh_combo.current()]
        self.app.bag_id = None
        self.refresh()

    def _pick_bag(self):
        self.app.bag_id = self._bag_ids[self.bag_combo.current()]
        self._fill_log()

    def _pick_product(self):
        sel = self.products.curselection()
        if sel:
            self.open_product(self._product_ids[sel[0]])

    # ------------------------------------------------------------------ матрица
    def open_product(self, pid: int):
        self.product_id = pid
        m = store.product_matrix(self.app.con, pid)
        p = m["product"]
        self.mtitle.config(text=f"{_('3. Матрица')}: {p['style_code']} · {p['title']} ({p['category']})")
        cost = p["base_cost_fx"] or (store.declared_unit_price(self.app.con, self.app.shipment_id, p["category_id"])
                                     if self.app.shipment_id else 0)
        self.cost_var.set(f"{cost:g}" if cost else "")
        self.sizes = [(s["id"], s["code"]) for s in m["sizes"]]
        self.rows = [(c["id"], f"{c['code']} {c['name']}", c["hex"]) for c in m["colors"]]
        self._build_color_picker()
        self._build_grid()

    def _build_color_picker(self):
        for w in self.colors_frame.winfo_children():
            w.destroy()
        ttk.Label(self.colors_frame, text=_("Цвета") + " — " + _("нажмите, чтобы добавить строку"),
                  style="Muted.TLabel").grid(row=0, column=0, columnspan=8, sticky="w")
        self.color_buttons = {}
        for r, fam in enumerate(store.color_families(self.app.con), start=1):
            ttk.Label(self.colors_frame, text=fam["title"], width=16).grid(row=r, column=0, sticky="w")
            for c, col in enumerate(fam["colors"], start=1):
                b = tk.Button(self.colors_frame, text=f"{col['code']} {col['title']}", relief="groove", padx=4, pady=0,
                              command=lambda cid=col["id"], name=f"{col['code']} {col['title']}", hx=col["hex"]:
                              self.add_color(cid, name, hx))
                sw = tk.Label(self.colors_frame, bg=col["hex"], width=2, relief="solid", bd=1)
                sw.grid(row=r, column=c * 2 - 1, padx=(6, 0))
                b.grid(row=r, column=c * 2, sticky="w")
                self.color_buttons[col["id"]] = b

    def add_color(self, cid, name, hexv):
        if self.product_id is None:
            return
        if cid not in [r[0] for r in self.rows]:
            self.rows.append((cid, name, hexv))
            self._build_grid()
        first = self.cells.get((cid, self.sizes[0][0])) if self.sizes else None
        if first is not None:
            self._entries[(cid, self.sizes[0][0])].focus_set()

    def _build_grid(self):
        keep = {k: v.get() for k, v in self.cells.items()}
        for w in self.grid_frame.winfo_children():
            w.destroy()
        self.cells, self._entries, self._order = {}, {}, []
        ttk.Label(self.grid_frame, text=_("Цвет \\ размер"), style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        for j, (_sid, code) in enumerate(self.sizes, start=1):
            ttk.Label(self.grid_frame, text=code, width=5, anchor="center").grid(row=0, column=j)
        ttk.Label(self.grid_frame, text="Σ", width=5, anchor="center").grid(row=0, column=len(self.sizes) + 1)
        self.row_sums = {}
        for i, (cid, name, hexv) in enumerate(self.rows, start=1):
            cellf = ttk.Frame(self.grid_frame)
            cellf.grid(row=i, column=0, sticky="w")
            tk.Label(cellf, bg=hexv, width=2, relief="solid", bd=1).pack(side="left")
            ttk.Label(cellf, text=" " + name).pack(side="left")
            for j, (sid, _code) in enumerate(self.sizes, start=1):
                var = tk.StringVar(value=keep.get((cid, sid), ""))
                e = ttk.Entry(self.grid_frame, textvariable=var, width=5, justify="center", font=("Helvetica", 12))
                e.grid(row=i, column=j, padx=1, pady=1)
                var.trace_add("write", lambda *_a: self._recalc())
                e.bind("<Return>", lambda _e, k=(cid, sid): self._next(k, 1))
                e.bind("<Right>", lambda _e, k=(cid, sid): self._next(k, 1))
                e.bind("<Left>", lambda _e, k=(cid, sid): self._next(k, -1))
                e.bind("<Down>", lambda _e, k=(cid, sid): self._next(k, len(self.sizes)))
                e.bind("<Up>", lambda _e, k=(cid, sid): self._next(k, -len(self.sizes)))
                self.cells[(cid, sid)] = var
                self._entries[(cid, sid)] = e
                self._order.append((cid, sid))
            lbl = ttk.Label(self.grid_frame, text="0", width=5, anchor="center")
            lbl.grid(row=i, column=len(self.sizes) + 1)
            self.row_sums[cid] = lbl
        self._recalc()

    def _next(self, key, step):
        i = self._order.index(key) + step
        if 0 <= i < len(self._order):
            e = self._entries[self._order[i]]
            e.focus_set()
            e.select_range(0, "end")
        return "break"

    def _qty(self, var):
        try:
            return int(str(var.get()).strip() or 0)
        except ValueError:
            return 0

    def _recalc(self):
        total = 0
        for cid, lbl in self.row_sums.items():
            s = sum(self._qty(v) for (c, _s), v in self.cells.items() if c == cid)
            lbl.config(text=str(s))
            total += s
        self.total_var.set(f"Σ {total}")
        return total

    def set_qty(self, color_code: str, size_code: str, qty: int):
        """Ввод количества по кодам (для автоматизированных проверок и сценариев)."""
        cid = self.app.con.execute("SELECT id FROM colors WHERE code = ?", (color_code,)).fetchone()[0]
        sid = [s for s, c in self.sizes if c == size_code][0]
        if (cid, sid) not in self.cells:
            col = self.app.con.execute("SELECT code, name, hex FROM colors WHERE id = ?", (cid,)).fetchone()
            self.add_color(cid, f"{col['code']} {col['name']}", col["hex"])
        self.cells[(cid, sid)].set(str(qty))

    # ------------------------------------------------------------------ действия
    def create_model(self):
        f = self.model
        name, cat = f.get("name").strip(), self.cat_map.get(f.get("category"))
        if not (name and cat):
            error(_("Нужны название и категория"))
            return None
        sid = self.app.shipment_id
        cost = f.num("cost", 0) or (store.declared_unit_price(self.app.con, sid, cat) if sid else 0)
        try:
            supplier = store.shipment(self.app.con, sid)["supplier"] if sid else ""
            pid = store.create_product(self.app.con, name, cat, f.get("style_code"), supplier or "", cost,
                                       f.get("composition"))
        except Exception as e:  # noqa: BLE001
            error(_("Товар не создан: {e}", e=e))
            return None
        for k in ("name", "style_code", "cost", "composition"):
            f.set(k, "")
        self._fill_products()
        self.cells = {}
        self.open_product(pid)
        return pid

    def save(self, print_labels: bool = False):
        sid = self.app.shipment_id
        if not (sid and self.product_id):
            error(_("Выберите поставку") if not sid else _("Нужны название и категория"))
            return 0
        grid = {k: self._qty(v) for k, v in self.cells.items() if self._qty(v)}
        cost = self.cost_var.get().replace(",", ".").strip()
        if cost:
            store.update_product(self.app.con, self.product_id, base_cost_fx=float(cost))
        before = self.app.con.execute("SELECT COALESCE(MAX(id), 0) FROM intake_items").fetchone()[0]
        n = store.add_intake(self.app.con, sid, self.app.bag_id, self.product_id, grid, float(cost) if cost else None)
        self.app.say(_("Принято {n} шт.", n=n) if n else _("Ничего не введено"))
        for v in self.cells.values():
            v.set("")
        self._fill_bags()
        self._fill_log()
        self._fill_products()
        if print_labels and n:
            rows = self.app.con.execute("SELECT variant_id, SUM(qty) q FROM intake_items WHERE id > ? "
                                        "GROUP BY variant_id", (before,)).fetchall()
            self.app.tabs["labels"].set_selection({r["variant_id"]: r["q"] for r in rows})
            self.app.show("labels")
        return n

    def scan(self, code: str | None = None):
        code = (code or self.scan_var.get()).strip()
        self.scan_var.set("")
        sid = self.app.shipment_id
        if not (code and sid):
            return None
        try:
            v = store.add_scan(self.app.con, sid, self.app.bag_id, code)
            msg = f"✓ {v['sku']} — {v['name']}"
            ok = True
        except ValueError as e:
            msg, ok = f"✗ {e}", False
            self.bell()
        self.scan_log.insert(0, msg)
        self.scan_log.itemconfig(0, foreground="#1e7a3c" if ok else "#b3202a")
        self._fill_log()
        self._fill_bags()
        return ok

    def delete_line(self):
        iid = self.log.selected()
        if iid:
            store.delete_intake(self.app.con, int(iid))
            self._fill_log()
            self._fill_bags()

    def bag_done(self):
        if self.app.bag_id:
            store.set_bag_status(self.app.con, self.app.bag_id, "done")
            self._fill_bags()
