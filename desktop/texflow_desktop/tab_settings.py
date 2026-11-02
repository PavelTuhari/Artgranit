"""Вкладка «Настройки»: язык, магазин и цены, термоэтикетка, принтеры, лист A4."""
from __future__ import annotations

from tkinter import ttk

from texflow import i18n, store
from texflow.i18n import _

from .widgets import Form


class SettingsTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=12)
        self.app = app
        langs = [i18n.LANG_NAMES[l] for l in i18n.LANGS]
        groups = [
            (_("Язык"), [("ui_lang", _("Язык интерфейса по умолчанию"), "combo", langs),
                         ("label_lang", _("Язык названий цветов на этикетке"), "combo", langs)]),
            (_("Магазин и цены"), [("brand", _("Бренд на этикетке")), ("currency", _("Валюта продажи")),
                                   ("vat_pct", _("НДС, %")), ("prices_include_vat", _("Цены с НДС"), "check"),
                                   ("round_step", _("Шаг округления (10 → …9.90)")),
                                   ("round_ending", _("Хвост цены (0.1 → .90, 0.01 → .99, 0 → ровно)")),
                                   ("min_markup_pct", _("Минимальная наценка, %")),
                                   ("ean_prefix", _("Префикс внутреннего EAN (20–29…)"))]),
            (_("Термоэтикетка (Zebra / TSC / PDF-рулон)"),
             [("label_dpi", "DPI", "combo", ["203", "300", "600"]), ("label_gap_mm", _("Зазор, мм")),
              ("label_width_mm", _("Ширина, мм")), ("label_height_mm", _("Высота, мм")),
              ("printer_zpl", _("Принтер Zebra (ZPL)")), ("printer_tspl", _("Принтер TSC (TSPL)")),
              ("zpl_font", _("Шрифт кириллицы ZPL (на принтере)")), ("tspl_font", _("Шрифт кириллицы TSPL"))]),
            (_("Лист A4 (обычный принтер)"),
             [("sheet_cols", _("Колонок")), ("sheet_rows", _("Строк")), ("sheet_label_w_mm", _("Ширина этикетки, мм")),
              ("sheet_label_h_mm", _("Высота, мм")), ("sheet_margin_left_mm", _("Отступ слева, мм")),
              ("sheet_margin_top_mm", _("Отступ сверху, мм")), ("sheet_border", _("Рамка"), "check")]),
        ]
        self.forms = []
        for r, (title, fields) in enumerate(groups):
            lf = ttk.LabelFrame(self, text=title, padding=8)
            lf.grid(row=r // 2, column=r % 2, sticky="nsew", padx=4, pady=4)
            f = Form(lf, fields, cols=1)
            f.pack(fill="x")
            self.forms.append(f)
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        ttk.Button(self, text=_("Сохранить"), style="Accent.TButton", command=self.save).grid(
            row=2, column=1, sticky="e", pady=8)
        ttk.Label(self, text=_("Размер новой этикетки по умолчанию; размер печати задаёт шаблон в редакторе этикеток."),
                  style="Muted.TLabel").grid(row=2, column=0, sticky="w")
        self.refresh()

    def refresh(self):
        st = store.settings(self.app.con)
        names = {l: i18n.LANG_NAMES[l] for l in i18n.LANGS}
        for f in self.forms:
            for key in f.vars:
                if key in ("ui_lang", "label_lang"):
                    f.set(key, names.get(st.get(key, "ru"), names["ru"]))
                elif key in ("prices_include_vat", "sheet_border"):
                    f.vars[key].set(st.get(key) == "1")
                else:
                    f.set(key, st.get(key, ""))

    def save(self):
        inv = {v: k for k, v in i18n.LANG_NAMES.items()}
        vals = {}
        for f in self.forms:
            for key, var in f.vars.items():
                v = var.get()
                if key in ("ui_lang", "label_lang"):
                    v = inv.get(v, "ru")
                elif key in ("prices_include_vat", "sheet_border"):
                    v = "1" if v else "0"
                vals[key] = v
        store.save_settings(self.app.con, vals)
        self.app.say(_("Настройки сохранены"))
        if vals["ui_lang"] != i18n.current_lang():
            self.app.set_language(vals["ui_lang"])
