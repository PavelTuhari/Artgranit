"""Встроенный редактор этикеток.

Холст в масштабе, элементы перетаскиваются мышью, угол-маркер меняет размер, стрелки двигают
выделенный элемент (Shift — точнее). Справа — список элементов и их свойства. Шаблон сохраняется
в базе и сразу доступен для печати в ZPL, TSPL и PDF; экспорт и импорт шаблона — JSON.
"""
from __future__ import annotations

import json
import os
import tempfile
import tkinter as tk
from tkinter import filedialog, ttk

from texflow import label_templates as LT, store
from texflow.i18n import _

from . import label_canvas, paths
from .widgets import ask, ask_string, error

FIELD_TOKENS = ["{brand}", "{name}", "{color}", "{size}", "{price}", "{price_value}", "{currency}", "{sku}",
                "{ean13}", "{style}", "{composition}", "{origin}"]
SNAP = 0.5


class LabelEditor(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=8)
        self.app = app
        self.tpl: LT.Template | None = None
        self.sel: int | None = None
        self.scale = 8.0
        self.dirty = False
        self._drag = None
        self._loading = False
        self.preview_label = LT.sample_label()
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # ------------------------------ слева: шаблоны
        left = ttk.Frame(self, width=260)
        left.grid(row=0, column=0, sticky="nsw", padx=(0, 8))
        ttk.Label(left, text=_("Шаблоны"), style="H.TLabel").pack(anchor="w")
        self.tpl_list = tk.Listbox(left, height=8, exportselection=False)
        self.tpl_list.pack(fill="x")
        self.tpl_list.bind("<<ListboxSelect>>", lambda _e: self._pick_template())
        for text, cmd in ((_("Новый шаблон"), self.new_template), (_("Копия"), self.duplicate),
                          (_("По умолчанию"), self.make_default), (_("Удалить"), self.delete_template),
                          (_("Экспорт JSON"), self.export_json), (_("Импорт JSON"), self.import_json)):
            ttk.Button(left, text=text, command=cmd).pack(fill="x", pady=1)
        box = ttk.LabelFrame(left, text=_("Этикетка"), padding=6)
        box.pack(fill="x", pady=(8, 0))
        self.name_var, self.w_var, self.h_var = tk.StringVar(), tk.StringVar(), tk.StringVar()
        for label, var in ((_("Название"), self.name_var), (_("Ширина, мм"), self.w_var), (_("Высота, мм"), self.h_var)):
            ttk.Label(box, text=label).pack(anchor="w")
            e = ttk.Entry(box, textvariable=var)
            e.pack(fill="x")
            var.trace_add("write", lambda *_a: self._apply_size())
        ttk.Button(left, text=_("Сохранить шаблон"), style="Accent.TButton", command=self.save).pack(fill="x", pady=(8, 2))
        self.dirty_lbl = ttk.Label(left, text="", style="Bad.TLabel")
        self.dirty_lbl.pack(anchor="w")
        pv = ttk.LabelFrame(left, text=_("Данные для предпросмотра"), padding=6)
        pv.pack(fill="x", pady=(8, 0))
        self.pv_var = tk.StringVar()
        pe = ttk.Entry(pv, textvariable=self.pv_var)
        pe.pack(fill="x")
        pe.bind("<Return>", lambda _e: self.set_preview(self.pv_var.get()))
        ttk.Label(pv, text=_("EAN-13 / SKU и Enter"), style="Muted.TLabel").pack(anchor="w")
        ttk.Button(pv, text=_("Пробный PDF"), command=self.test_pdf).pack(fill="x", pady=(6, 1))
        ttk.Button(pv, text=_("Показать ZPL / TSPL"), command=self.show_code).pack(fill="x", pady=1)

        # ------------------------------ центр: холст
        mid = ttk.Frame(self)
        mid.grid(row=0, column=1, sticky="nsew")
        mid.rowconfigure(1, weight=1)
        mid.columnconfigure(0, weight=1)
        zb = ttk.Frame(mid)
        zb.grid(row=0, column=0, sticky="ew")
        for text, cmd in (("Text", lambda: self.add("text")), (_("Штрихкод"), lambda: self.add("barcode")),
                          (_("Рамка"), lambda: self.add("box")), (_("Линия"), lambda: self.add("line"))):
            ttk.Button(zb, text="+ " + text, command=cmd).pack(side="left", padx=1)
        ttk.Button(zb, text="−", width=3, command=lambda: self.zoom(0.8)).pack(side="right")
        ttk.Button(zb, text="+", width=3, command=lambda: self.zoom(1.25)).pack(side="right")
        self.grid_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(zb, text=_("Сетка 5 мм"), variable=self.grid_var, command=self.redraw).pack(side="right", padx=8)
        self.canvas = tk.Canvas(mid, background="#ecebe7", highlightthickness=0)
        self.canvas.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        self.canvas.bind("<Button-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._motion)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.canvas.bind("<Configure>", lambda _e: self.redraw())
        for key, dx, dy in (("Left", -1, 0), ("Right", 1, 0), ("Up", 0, -1), ("Down", 0, 1)):
            self.canvas.bind(f"<{key}>", lambda _e, dx=dx, dy=dy: self.nudge(dx * SNAP, dy * SNAP))
            self.canvas.bind(f"<Shift-{key}>", lambda _e, dx=dx, dy=dy: self.nudge(dx * 0.1, dy * 0.1))
        self.canvas.bind("<Delete>", lambda _e: self.remove())
        self.pos = ttk.Label(mid, text="", style="Muted.TLabel")
        self.pos.grid(row=2, column=0, sticky="w")

        # ------------------------------ справа: элементы и свойства
        right = ttk.Frame(self, width=320)
        right.grid(row=0, column=2, sticky="nse", padx=(8, 0))
        ttk.Label(right, text=_("Элементы"), style="H.TLabel").pack(anchor="w")
        self.el_list = tk.Listbox(right, height=10, exportselection=False, width=40)
        self.el_list.pack(fill="x")
        self.el_list.bind("<<ListboxSelect>>", lambda _e: self._pick_element())
        rb = ttk.Frame(right)
        rb.pack(fill="x", pady=2)
        ttk.Button(rb, text="▲", width=3, command=lambda: self.move_order(-1)).pack(side="left")
        ttk.Button(rb, text="▼", width=3, command=lambda: self.move_order(1)).pack(side="left")
        ttk.Button(rb, text=_("Удалить"), command=self.remove).pack(side="right")
        pr = ttk.LabelFrame(right, text=_("Свойства"), padding=6)
        pr.pack(fill="x", pady=(6, 0))
        self.props = {}
        rows = [("text", _("Текст / поле")), ("x_mm", "X, mm"), ("y_mm", "Y, mm"), ("w_mm", _("Ширина, мм")),
                ("h_mm", _("Высота, мм")), ("font_mm", _("Шрифт, мм")), ("thickness", _("Толщина линии, мм"))]
        for key, label in rows:
            ttk.Label(pr, text=label).pack(anchor="w")
            var = tk.StringVar()
            ttk.Entry(pr, textvariable=var).pack(fill="x")
            var.trace_add("write", lambda *_a, k=key: self._prop_changed(k))
            self.props[key] = var
        self.token = ttk.Combobox(pr, values=FIELD_TOKENS, state="readonly")
        self.token.pack(fill="x", pady=(4, 0))
        self.token.bind("<<ComboboxSelected>>", lambda _e: self._insert_token())
        ttk.Label(pr, text=_("вставить поле в текст"), style="Muted.TLabel").pack(anchor="w")
        self.bold_var = tk.BooleanVar()
        ttk.Checkbutton(pr, text=_("Жирный"), variable=self.bold_var,
                        command=lambda: self._prop_changed("bold")).pack(anchor="w", pady=(4, 0))
        al = ttk.Frame(pr)
        al.pack(fill="x")
        self.align_var = tk.StringVar(value="L")
        for code, label in (("L", "⯇"), ("C", "≡"), ("R", "⯈")):
            ttk.Radiobutton(al, text=label, value=code, variable=self.align_var,
                            command=lambda: self._prop_changed("align")).pack(side="left")
        self.sym_var = tk.StringVar(value="EAN13")
        sy = ttk.Frame(pr)
        sy.pack(fill="x")
        for code in ("EAN13", "CODE128"):
            ttk.Radiobutton(sy, text=code, value=code, variable=self.sym_var,
                            command=lambda: self._prop_changed("symbology")).pack(side="left")
        self.refresh()

    # ================================================================== шаблоны
    def refresh(self):
        self._templates = LT.list_templates(self.app.con)
        self.tpl_list.delete(0, "end")
        for t in self._templates:
            self.tpl_list.insert("end", ("★ " if t["is_default"] else "   ") + f"{t['name']}  {t['width_mm']:g}×{t['height_mm']:g}")
        if self.tpl is None and self._templates:
            self.open_template(self._templates[0]["id"])
        elif self.tpl and self.tpl.id:
            ids = [t["id"] for t in self._templates]
            if self.tpl.id in ids:
                self.tpl_list.selection_clear(0, "end")
                self.tpl_list.selection_set(ids.index(self.tpl.id))
        self.redraw()

    def _pick_template(self):
        sel = self.tpl_list.curselection()
        if not sel:
            return
        tid = self._templates[sel[0]]["id"]
        if self.tpl and tid == self.tpl.id:
            return
        if self.dirty and not ask(_("Есть несохранённые изменения. Открыть другой шаблон без сохранения?")):
            return
        self.open_template(tid)

    def open_template(self, tid: int):
        self.tpl = LT.load(self.app.con, tid)
        self.sel = None
        self._loading = True
        self.name_var.set(self.tpl.name)
        self.w_var.set(f"{self.tpl.width_mm:g}")
        self.h_var.set(f"{self.tpl.height_mm:g}")
        self._loading = False
        self._set_dirty(False)
        self._fill_elements()
        self._fit_scale()
        self.redraw()
        ids = [t["id"] for t in self._templates]
        if tid in ids:
            self.tpl_list.selection_clear(0, "end")
            self.tpl_list.selection_set(ids.index(tid))

    def new_template(self):
        name = ask_string(self, _("Новый шаблон"), _("Название"), _("Новый шаблон"))
        if not name:
            return
        st = store.settings(self.app.con)
        t = LT.Template(name, float(st.get("label_width_mm", 58)), float(st.get("label_height_mm", 40)),
                        [LT.Element("text", "{name}", x_mm=2, y_mm=2, w_mm=30, h_mm=4, font_mm=3.5, bold=True),
                         LT.Element("barcode", "{ean13}", "EAN13", x_mm=2, y_mm=10, w_mm=34, h_mm=12)])
        try:
            tid = LT.save(self.app.con, t)
        except Exception as e:  # noqa: BLE001
            error(e)
            return
        self.refresh()
        self.open_template(tid)
        return tid

    def duplicate(self):
        if not self.tpl:
            return
        name = ask_string(self, _("Копия"), _("Название"), self.tpl.name + " (2)")
        if name:
            try:
                tid = LT.duplicate(self.app.con, self.tpl.id, name)
            except Exception as e:  # noqa: BLE001
                error(e)
                return
            self.refresh()
            self.open_template(tid)

    def make_default(self):
        if self.tpl and self.tpl.id:
            LT.set_default(self.app.con, self.tpl.id)
            self.app.say(_("Шаблон по умолчанию: {name}", name=self.tpl.name))
            self.refresh()

    def delete_template(self):
        if self.tpl and self.tpl.id and ask(_("Удалить шаблон {name}?", name=self.tpl.name)):
            try:
                LT.delete(self.app.con, self.tpl.id)
            except ValueError as e:
                error(e)
                return
            self.tpl = None
            self.refresh()

    def save(self):
        if not self.tpl:
            return None
        try:
            tid = LT.save(self.app.con, self.tpl)
        except Exception as e:  # noqa: BLE001
            error(e)
            return None
        self._set_dirty(False)
        self.app.say(_("Шаблон сохранён: {name}", name=self.tpl.name))
        self.refresh()
        return tid

    def export_json(self, path: str | None = None):
        if not self.tpl:
            return
        path = path or filedialog.asksaveasfilename(defaultextension=".json", initialfile=f"{self.tpl.name}.json",
                                                    filetypes=[("JSON", "*.json")])
        if path:
            d = LT.to_dict(self.tpl)
            d.pop("id", None)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=1)
            self.app.say(path)

    def import_json(self, path: str | None = None):
        path = path or filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not path:
            return None
        try:
            with open(path, encoding="utf-8") as f:
                t = LT.from_dict(json.load(f))
            t.id, t.is_default = None, False
            names = {x["name"] for x in LT.list_templates(self.app.con)}
            while t.name in names:
                t.name += " (2)"
            tid = LT.save(self.app.con, t)
        except Exception as e:  # noqa: BLE001
            error(e)
            return None
        self.refresh()
        self.open_template(tid)
        return tid

    def _apply_size(self):
        if self._loading or not self.tpl:
            return
        try:
            self.tpl.width_mm = float(self.w_var.get().replace(",", "."))
            self.tpl.height_mm = float(self.h_var.get().replace(",", "."))
        except ValueError:
            return
        self.tpl.name = self.name_var.get()
        self._set_dirty(True)
        self.redraw()

    def _set_dirty(self, v: bool):
        self.dirty = v
        self.dirty_lbl.config(text=_("есть несохранённые изменения") if v else "")

    # ================================================================== элементы
    def _fill_elements(self):
        self.el_list.delete(0, "end")
        names = {"text": "T", "barcode": "|||", "box": "▭", "line": "—"}
        for e in self.tpl.elements if self.tpl else []:
            label = e.text if e.kind in ("text", "barcode") else f"{e.w_mm:g}×{e.h_mm:g}"
            self.el_list.insert("end", f"{names[e.kind]:>3}  {label}")
        if self.sel is not None and self.tpl and self.sel < len(self.tpl.elements):
            self.el_list.selection_set(self.sel)
        self._load_props()

    def _pick_element(self):
        sel = self.el_list.curselection()
        self.sel = sel[0] if sel else None
        self._load_props()
        self.redraw()

    def select(self, idx: int | None):
        self.sel = idx
        self.el_list.selection_clear(0, "end")
        if idx is not None:
            self.el_list.selection_set(idx)
        self._load_props()
        self.redraw()

    def add(self, kind: str):
        if not self.tpl:
            return None
        defaults = {"text": LT.Element("text", "{name}", x_mm=2, y_mm=2, w_mm=min(30, self.tpl.width_mm - 4), h_mm=4,
                                       font_mm=3),
                    "barcode": LT.Element("barcode", "{ean13}", "EAN13", x_mm=2, y_mm=2, w_mm=min(34, self.tpl.width_mm - 4),
                                          h_mm=12),
                    "box": LT.Element("box", x_mm=2, y_mm=2, w_mm=12, h_mm=8),
                    "line": LT.Element("line", x_mm=2, y_mm=2, w_mm=min(30, self.tpl.width_mm - 4), h_mm=0)}
        self.tpl.elements.append(defaults[kind])
        self._set_dirty(True)
        self.sel = len(self.tpl.elements) - 1
        self._fill_elements()
        self.redraw()
        return self.sel

    def remove(self):
        if self.tpl and self.sel is not None:
            del self.tpl.elements[self.sel]
            self.sel = None
            self._set_dirty(True)
            self._fill_elements()
            self.redraw()

    def move_order(self, step: int):
        if not self.tpl or self.sel is None:
            return
        j = self.sel + step
        if 0 <= j < len(self.tpl.elements):
            els = self.tpl.elements
            els[self.sel], els[j] = els[j], els[self.sel]
            self.sel = j
            self._set_dirty(True)
            self._fill_elements()
            self.redraw()

    def nudge(self, dx: float, dy: float):
        e = self._current()
        if e:
            e.x_mm = round(max(0, e.x_mm + dx), 2)
            e.y_mm = round(max(0, e.y_mm + dy), 2)
            self._set_dirty(True)
            self._load_props()
            self.redraw()
        return "break"

    def _current(self):
        if self.tpl and self.sel is not None and self.sel < len(self.tpl.elements):
            return self.tpl.elements[self.sel]
        return None

    def _load_props(self):
        e = self._current()
        self._loading = True
        for key, var in self.props.items():
            var.set("" if e is None else (getattr(e, key) if key == "text" else f"{getattr(e, key):g}"))
        self.bold_var.set(bool(e and e.bold))
        self.align_var.set(e.align if e else "L")
        self.sym_var.set(e.symbology if e else "EAN13")
        self._loading = False

    def _prop_changed(self, key: str):
        e = self._current()
        if self._loading or not e:
            return
        if key == "text":
            e.text = self.props["text"].get()
        elif key == "bold":
            e.bold = self.bold_var.get()
        elif key == "align":
            e.align = self.align_var.get()
        elif key == "symbology":
            e.symbology = self.sym_var.get()
            if e.symbology == "EAN13" and "{ean13}" not in e.text:
                e.text = "{ean13}"
            elif e.symbology == "CODE128" and e.text == "{ean13}":
                e.text = "{sku}"
            self._load_props()
        else:
            try:
                setattr(e, key, float(self.props[key].get().replace(",", ".")))
            except ValueError:
                return
        self._set_dirty(True)
        idx = self.sel
        self._fill_elements_light(idx)
        self.redraw()

    def _fill_elements_light(self, idx):
        e = self.tpl.elements[idx]
        names = {"text": "T", "barcode": "|||", "box": "▭", "line": "—"}
        label = e.text if e.kind in ("text", "barcode") else f"{e.w_mm:g}×{e.h_mm:g}"
        self.el_list.delete(idx)
        self.el_list.insert(idx, f"{names[e.kind]:>3}  {label}")
        self.el_list.selection_set(idx)

    def _insert_token(self):
        e = self._current()
        if e and e.kind in ("text", "barcode"):
            tok = self.token.get()
            self.props["text"].set(tok if e.kind == "barcode" else (e.text + (" " if e.text else "") + tok))

    # ================================================================== холст
    def _fit_scale(self):
        if not self.tpl:
            return
        cw = max(400, self.canvas.winfo_width() or 700)
        ch = max(300, self.canvas.winfo_height() or 500)
        self.scale = max(3.0, min(14.0, (cw - 60) / self.tpl.width_mm, (ch - 60) / self.tpl.height_mm))

    def zoom(self, k: float):
        self.scale = max(2.0, min(30.0, self.scale * k))
        self.redraw()

    def origin(self):
        return 30, 30

    def redraw(self):
        c = self.canvas
        c.delete("all")
        if not self.tpl:
            return
        ox, oy = self.origin()
        label_canvas.draw(c, self.tpl, self.preview_label, self.scale, ox, oy, element_tags=True)
        s = self.scale
        if self.grid_var.get():
            for mm in range(5, int(self.tpl.width_mm) + 1, 5):
                c.create_line(ox + mm * s, oy, ox + mm * s, oy + self.tpl.height_mm * s, fill="#d8e4f5", tags=("grid",))
            for mm in range(5, int(self.tpl.height_mm) + 1, 5):
                c.create_line(ox, oy + mm * s, ox + self.tpl.width_mm * s, oy + mm * s, fill="#d8e4f5", tags=("grid",))
            c.tag_lower("grid", "el0") if c.find_withtag("el0") else None
        e = self._current()
        if e:
            x0, y0 = ox + e.x_mm * s, oy + e.y_mm * s
            x1, y1 = ox + (e.x_mm + max(e.w_mm, 0.5)) * s, oy + (e.y_mm + max(e.h_mm, 0.5)) * s
            c.create_rectangle(x0 - 1, y0 - 1, x1 + 1, y1 + 1, outline="#1f6feb", dash=(4, 2), tags=("sel",))
            c.create_rectangle(x1 - 4, y1 - 4, x1 + 4, y1 + 4, fill="#1f6feb", outline="white", tags=("handle",))
            self.pos.config(text=f"x {e.x_mm:g}  y {e.y_mm:g}  w {e.w_mm:g}  h {e.h_mm:g} mm")
        else:
            self.pos.config(text=f"{self.tpl.width_mm:g} × {self.tpl.height_mm:g} mm · {_('щёлкните элемент')}")

    def _to_mm(self, x, y):
        ox, oy = self.origin()
        return (x - ox) / self.scale, (y - oy) / self.scale

    def hit(self, mx: float, my: float) -> int | None:
        """Индекс верхнего элемента под точкой (мм)."""
        if not self.tpl:
            return None
        for i in range(len(self.tpl.elements) - 1, -1, -1):
            e = self.tpl.elements[i]
            pad = 0.8
            if e.x_mm - pad <= mx <= e.x_mm + max(e.w_mm, 0.5) + pad and e.y_mm - pad <= my <= e.y_mm + max(e.h_mm, 0.5) + pad:
                return i
        return None

    def _press(self, ev):
        self.canvas.focus_set()
        mx, my = self._to_mm(ev.x, ev.y)
        e = self._current()
        if e:
            hx, hy = e.x_mm + max(e.w_mm, 0.5), e.y_mm + max(e.h_mm, 0.5)
            if abs(mx - hx) * self.scale <= 6 and abs(my - hy) * self.scale <= 6:
                self._drag = ("resize", mx, my, e.w_mm, e.h_mm)
                return
        idx = self.hit(mx, my)
        self.select(idx)
        if idx is not None:
            e = self.tpl.elements[idx]
            self._drag = ("move", mx, my, e.x_mm, e.y_mm)

    def _motion(self, ev):
        e = self._current()
        if not (self._drag and e):
            return
        mx, my = self._to_mm(ev.x, ev.y)
        mode, sx, sy, a, b = self._drag
        snap = lambda v: round(v / SNAP) * SNAP  # noqa: E731
        if mode == "move":
            e.x_mm = max(0.0, snap(a + mx - sx))
            e.y_mm = max(0.0, snap(b + my - sy))
        else:
            e.w_mm = max(0.0 if e.kind == "line" else 1.0, snap(a + mx - sx))
            e.h_mm = max(0.0 if e.kind == "line" else 1.0, snap(b + my - sy))
        self._set_dirty(True)
        self._load_props()
        self.redraw()

    def _release(self, _ev):
        self._drag = None

    # ================================================================== предпросмотр
    def set_preview(self, code: str):
        code = (code or "").strip()
        if not code:
            self.preview_label = LT.sample_label()
        else:
            v = store.variant_by_ean(self.app.con, code)
            if not v:
                error(_("штрихкод {code} не найден", code=code))
                return
            self.preview_label = store.label_rows(self.app.con, {v["id"]: 1})[0]
        self.redraw()

    def test_pdf(self, open_file: bool = True) -> str | None:
        if not self.tpl:
            return None
        data = LT.to_pdf_roll(self.tpl, [self.preview_label])
        path = os.path.join(tempfile.gettempdir(), "texflow_template_preview.pdf")
        with open(path, "wb") as f:
            f.write(data)
        if open_file:
            paths.open_path(path)
        return path

    def show_code(self):
        if not self.tpl:
            return
        st = store.settings(self.app.con)
        dpi = int(float(st.get("label_dpi", 203)))
        z = LT.to_zpl(self.tpl, [self.preview_label], dpi, st.get("zpl_font", ""))
        t = LT.to_tspl(self.tpl, [self.preview_label], dpi, float(st.get("label_gap_mm", 2)), st.get("tspl_font", ""))
        win = tk.Toplevel(self)
        win.title(f"ZPL / TSPL — {self.tpl.name}")
        txt = tk.Text(win, width=100, height=36, font=("Courier", 10))
        txt.pack(fill="both", expand=True)
        txt.insert("1.0", "; ZPL (Zebra)\n" + z + "\n; TSPL (TSC)\n" + t.replace("\r\n", "\n"))
        return win
