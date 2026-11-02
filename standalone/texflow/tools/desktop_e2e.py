#!/usr/bin/env python3
"""Сквозной прогон нативного приложения TexFlow Desktop со скриншотами.

Запуск (нужен X-дисплей; на сервере — Xvfb):
    xvfb-run -a -s "-screen 0 1360x860x24" python tools/desktop_e2e.py docs/html
Каждый шаг: действие через виджеты (как оператор) → проверка → скриншот окна.
Итог: <вывод>/desktop_results.json и <вывод>/img/desk_*.jpg
"""
from __future__ import annotations

import io
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, "desktop")]
OUT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "docs", "html"))
IMG = os.path.join(OUT, "img")
os.makedirs(IMG, exist_ok=True)
for f in os.listdir(IMG):
    if f.startswith("desk_"):
        os.remove(os.path.join(IMG, f))
TMP = tempfile.mkdtemp(prefix="texflow-desk-")
os.environ["TEXFLOW_HOME"] = TMP

import tkinter as tk  # noqa: E402

from texflow import i18n, label_templates as LT, store  # noqa: E402
from texflow_desktop import (app as app_mod, label_editor, tab_catalog, tab_exchange, tab_labels,  # noqa: E402
                             tab_pricing, tab_settings, tab_shipments, tab_sort, widgets)

DIALOGS: list[str] = []
for m in (widgets, tab_shipments, tab_sort, tab_pricing, tab_catalog, tab_labels, label_editor, tab_exchange,
          tab_settings, app_mod):
    for name in ("error", "info"):
        if hasattr(m, name):
            setattr(m, name, lambda msg, title="TexFlow", _n=name: DIALOGS.append(f"{_n}: {msg}"))
    if hasattr(m, "ask"):
        m.ask = lambda msg, title="TexFlow": True
ANSWERS: list = []
for m in (widgets, label_editor, tab_labels, tab_pricing):
    if hasattr(m, "ask_string"):
        m.ask_string = lambda parent, title, prompt, initial="": ANSWERS.pop(0) if ANSWERS else initial

results, shot_no = [], [0]
APP: app_mod.App | None = None


def snap(name: str) -> str:
    APP.update()
    time.sleep(0.25)
    APP.update()
    shot_no[0] += 1
    fname = f"desk_{shot_no[0]:02d}_{name}.jpg"
    subprocess.run(["import", "-window", "root", "-quality", "85", os.path.join(IMG, fname)], check=True)
    return fname


def step(sid, lang, title, expected):
    def deco(fn):
        t0 = time.time()
        rec = {"id": sid, "lang": lang, "title": title, "expected": expected, "actual": "", "status": "PASS",
               "images": [], "ms": 0}
        try:
            DIALOGS.clear()
            r = fn(rec)
            rec["actual"] = r or ""
        except Exception as e:  # noqa: BLE001
            rec["status"] = "FAIL"
            rec["actual"] = f"ОШИБКА: {e} | {traceback.format_exc().splitlines()[-3:]}"
            try:
                rec["images"].append(snap(sid.lower() + "_fail"))
            except Exception:  # noqa: BLE001
                pass
        rec["ms"] = int((time.time() - t0) * 1000)
        results.append(rec)
        print(rec["status"], sid, title, flush=True)
        return fn
    return deco


def must(cond, msg):
    if not cond:
        raise AssertionError(msg)


def ui_texts(widget) -> list[str]:
    """Все подписи интерфейса (кнопки, метки, рамки, вкладки), без пользовательских данных в таблицах."""
    out = []
    try:
        if isinstance(widget, tk.Menu):
            for i in range((widget.index("end") or -1) + 1):
                try:
                    out.append(widget.entrycget(i, "label"))
                except tk.TclError:
                    pass
        else:
            out.append(str(widget.cget("text")))
    except tk.TclError:
        pass
    cls = widget.winfo_class()
    if cls == "TNotebook":
        out += [widget.tab(t, "text") for t in widget.tabs()]
    if cls == "Treeview":
        out += [widget.heading(c, "text") for c in widget["columns"]]
    for ch in widget.winfo_children():
        out += ui_texts(ch)
    return out


def fake_printer():
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    got = {}

    def run():
        c, _ = srv.accept()
        buf = b""
        while chunk := c.recv(4096):
            buf += chunk
        got["data"] = buf
        c.close()
        srv.close()
    threading.Thread(target=run, daemon=True).start()
    return srv.getsockname()[1], got


def main():
    global APP
    APP = app_mod.App(os.path.join(TMP, "desk.db"), "ru")
    APP.geometry("1360x860+0+0")
    errors = []
    APP.report_callback_exception = lambda *a: errors.append("".join(traceback.format_exception(*a)))
    APP.update()
    con = APP.con

    @step("D01", "ru", "Запуск нативного приложения на пустой базе",
          "Окно с 8 вкладками, меню, переключатель RU/RO/EN; база создана в папке данных пользователя")
    def _(r):
        tabs = [APP.nb.tab(t, "text") for t in APP.nb.tabs()]
        must(len(tabs) == 8, tabs)
        must(os.path.exists(APP.db_file), "нет базы")
        r["images"].append(snap("start"))
        return "Вкладки: " + " · ".join(tabs)

    @step("D02", "ru", "Новая поставка", "Поставка TR-DESK-01 создана, 2 мешка, курс 17.8")
    def _(r):
        t = APP.tabs["shipments"]
        t.new_form.set_many({"code": "TR-DESK-01", "supplier": "Istanbul Tekstil", "fx_rate": "17.8", "bags": "2"})
        r["images"].append(snap("shipment_form"))
        t.btn_create.invoke()
        must(t.list.count() == 1 and t.bags.count() == 2, f"поставок {t.list.count()}, мешков {t.bags.count()}")
        return APP.status.get()

    @step("D03", "ru", "Упаковочный лист из Excel (.xlsx)",
          "7 строк загружены из xlsx, мешков стало 4, сверка показывает недостачу по всем категориям")
    def _(r):
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        import csv
        with open(os.path.join(ROOT, "samples", "packing_list_tr.csv"), encoding="utf-8") as f:
            for row in csv.reader(f, delimiter=";"):
                ws.append([float(x) if re.fullmatch(r"\d+(\.\d+)?", x) else x for x in row])
        path = os.path.join(TMP, "packing.xlsx")
        wb.save(path)
        t = APP.tabs["shipments"]
        res = t.import_packing(path)
        must(res["lines"] == 7 and t.bags.count() == 4, res)
        t.costs.set_many({"freight": "4500", "customs": "1200", "broker": "800"})
        t.btn_save.invoke()
        r["images"].append(snap("shipment_loaded"))
        return APP.status.get()

    @step("D04", "ru", "Разбор мешка: новая модель и матрица цвет × размер",
          "Модель создана, закупка 2.1 из листа, 3 цвета в матрице, итог 60, запись 60 шт. (8 вариантов) в мешок №1")
    def _(r):
        APP.bag_id = store.bags(con, 1)[0]["id"]
        APP.show("sort")
        t = APP.tabs["sort"]
        t.model.set("name", "Футболка базовая оверсайз")
        t.model.widgets["category"].set([k for k in t.cat_map if "(TSH)" in k][0])
        t.model.set("composition", "100% хлопок")
        pid = t.create_model()
        must(pid and t.cost_var.get() == "2.1", f"закупка {t.cost_var.get()}")
        for color, sizes in (("001", {"S": 5, "M": 8, "L": 7}), ("800", {"S": 6, "M": 10, "L": 8}),
                             ("710", {"M": 9, "L": 7})):
            for size, q in sizes.items():
                t.set_qty(color, size, q)
        must(t.total_var.get() == "Σ 60", t.total_var.get())
        r["images"].append(snap("matrix"))
        n = t.save()
        must(n == 60 and t.log.count() == 8, f"принято {n}, строк журнала {t.log.count()}")
        r["images"].append(snap("intake_log"))
        return f"{t.total_var.get()} → {APP.status.get()}"

    @step("D05", "ru", "Сканер: повторная вещь и неизвестный код",
          "Известный EAN добавляет +1 шт. (✓, зелёный), неизвестный — ✗ и сигнал, без записи")
    def _(r):
        t = APP.tabs["sort"]
        ean = store.variants(con, 1)[0]["ean13"]
        must(t.scan(ean) is True, "скан EAN")
        must(t.scan("2999999999999") is False, "неизвестный код принят")
        must(t.log.count() == 9, t.log.count())
        r["images"].append(snap("scanner"))
        return " / ".join(t.scan_log.get(0, "end"))

    @step("D06", "ru", "Цены: предложение, своя цена, запись в карточки",
          "Цена предложена с окончанием .90; своя цена 199.90 записывается в карточку")
    def _(r):
        APP.show("pricing")
        t = APP.tabs["pricing"]
        must(t.table.count() == 1 and t.rows[0]["price"] % 10 > 9, t.rows)
        t.own_price("1", 199.9)
        r["images"].append(snap("pricing"))
        must(t.apply() == 1, "не записано")
        must(store.product(con, 1)["retail_price"] == 199.9, "цена")
        return f"предложено {t.rows[0]['price_t']}, записано 199.90"

    @step("D07", "ru", "Каталог: карточка, переводы RO/EN, фиксация цены",
          "Название и состав сохранены на RO/EN, цена зафиксирована")
    def _(r):
        APP.show("catalog")
        t = APP.tabs["catalog"]
        t.list.select(1)
        t.open("1")
        t.form.set_many({"name_ro": "Tricou basic oversize", "name_en": "Basic oversize T-shirt",
                         "composition_ro": "100% bumbac", "composition_en": "100% cotton"})
        t.form.vars["price_locked"].set(True)
        t.save()
        p = store.product(con, 1)
        must(p["name_ro"] == "Tricou basic oversize" and p["price_locked"] == 1, dict(p))
        must(t.variants.count() == 8, t.variants.count())
        r["images"].append(snap("catalog"))
        return APP.status.get()

    @step("D08", "ru", "Редактор этикеток: открыть стандартный шаблон",
          "Холст показывает этикетку 58×40 с данными, 8 элементов в списке")
    def _(r):
        APP.show("editor")
        ed = APP.tabs["editor"]
        ed.open_template(LT.load(con).id)
        ed.set_preview(store.variants(con, 1)[0]["ean13"])
        must(ed.el_list.size() == 8, ed.el_list.size())
        must(len(APP.tabs["editor"].canvas.find_all()) > 50, "холст пуст")
        r["images"].append(snap("editor_open"))
        return f"{ed.tpl.name}: {ed.el_list.size()} элементов"

    @step("D09", "ru", "Редактор: новый шаблон, элементы, перетаскивание мышью, свойства",
          "Создан шаблон «Бирка 50×30»; добавлены текст, CODE128, рамка; текст перетащен мышью на 5 мм; "
          "свойства (шрифт, жирный, выравнивание) применены; сохранено в базе")
    def _(r):
        ed = APP.tabs["editor"]
        ANSWERS.append("Бирка 50×30")
        tid = ed.new_template()
        ed.w_var.set("50")
        ed.h_var.set("30")
        for e in list(ed.tpl.elements):
            ed.select(0)
            ed.remove()
        i = ed.add("text")
        ed.props["text"].set("{brand} · {size}")
        ed.props["font_mm"].set("4")
        ed.bold_var.set(True)
        ed._prop_changed("bold")
        ed.align_var.set("C")
        ed._prop_changed("align")
        ed.props["w_mm"].set("46")
        j = ed.add("barcode")
        ed.sym_var.set("CODE128")
        ed._prop_changed("symbology")
        for k, v in (("x_mm", "3"), ("y_mm", "12"), ("w_mm", "44"), ("h_mm", "14")):
            ed.props[k].set(v)
        ed.add("box")
        for k, v in (("x_mm", "1"), ("y_mm", "1"), ("w_mm", "48"), ("h_mm", "28")):
            ed.props[k].set(v)
        # перетаскивание текста мышью: нажать на элемент, протащить на 5 мм вправо и вниз
        ed.select(None)
        APP.update()
        ox, oy = ed.origin()
        e = ed.tpl.elements[i]
        x0, y0 = ox + (e.x_mm + 3) * ed.scale, oy + (e.y_mm + 1.5) * ed.scale
        ed.canvas.event_generate("<Button-1>", x=int(x0), y=int(y0))
        must(ed.sel == i, f"выделение {ed.sel}")
        ed.canvas.event_generate("<B1-Motion>", x=int(x0 + 5 * ed.scale), y=int(y0 + 5 * ed.scale))
        ed.canvas.event_generate("<ButtonRelease-1>", x=int(x0 + 5 * ed.scale), y=int(y0 + 5 * ed.scale))
        must((e.x_mm, e.y_mm) == (7.0, 7.0), f"после перетаскивания x={e.x_mm} y={e.y_mm}")
        ed.canvas.event_generate("<Up>")
        ed.nudge(0, -SNAP_BACK)
        r["images"].append(snap("editor_new"))
        ed.save()
        back = LT.load(con, tid)
        must([x.kind for x in back.elements] == ["text", "barcode", "box"], [x.kind for x in back.elements])
        must(back.elements[0].bold and back.elements[0].align == "C" and back.elements[1].symbology == "CODE128",
             LT.to_dict(back))
        must((back.width_mm, back.height_mm) == (50, 30), (back.width_mm, back.height_mm))
        return f"x,y текста после мыши и стрелок: {back.elements[0].x_mm:g}, {back.elements[0].y_mm:g}; " \
               f"сохранено {len(back.elements)} элемента"


    @step("D10", "ru", "Редактор: экспорт и импорт шаблона JSON, пробный PDF, код ZPL/TSPL",
          "JSON выгружен и загружен как копия; пробный PDF 50×30 мм; окно кода содержит ^BCN (CODE128) и BOX")
    def _(r):
        ed = APP.tabs["editor"]
        path = os.path.join(TMP, "tpl.json")
        ed.export_json(path)
        tid = ed.import_json(path)
        must(tid and LT.load(con, tid).name.endswith("(2)"), "импорт")
        pdf = ed.test_pdf(open_file=False)
        must(b"/MediaBox [ 0 0 141.7323 85.03937 ]" in open(pdf, "rb").read(), "размер PDF")
        win = ed.show_code()
        code = win.winfo_children()[0].get("1.0", "end")
        must("^BCN" in code and "BOX " in code, code[:200])
        win.geometry("+380+60")
        r["images"].append(snap("editor_code"))
        win.destroy()
        return "JSON → копия шаблона; PDF 141.7×85.0 pt; ZPL+TSPL показаны"

    @step("D11", "ru", "Этикетки: выбор принятых штук, шаблон, PDF, ZPL, TSPL в файл",
          "Выбрано 61 этикетка; файлы PDF-рулон (шаблон «Бирка»), PDF A4, ZPL, TSPL сохранены и корректны")
    def _(r):
        APP.show("labels")
        t = APP.tabs["labels"]
        t.sh_combo.current(0)
        t._fill_bags()
        t.take_received()
        must(sum(t.selection.values()) == 61, sum(t.selection.values()))
        names = list(t.tpl_combo["values"])
        t.tpl_combo.current([i for i, n in enumerate(names) if n.startswith("Бирка 50×30 (")][0])
        t.preview()
        out = {}
        for i, fmt in enumerate(tab_labels.FORMATS):
            t.fmt_combo.current(i)
            out[fmt] = t.save_file(os.path.join(TMP, f"labels.{fmt}"))
        must(open(out["pdf_roll"], "rb").read(4) == b"%PDF", "pdf")
        z = open(out["zpl"], encoding="utf-8").read()
        must(z.count("^XA") == 8 and "^BCN" in z, "zpl")
        must("PRINT 1," in open(out["tspl"], encoding="utf-8").read(), "tspl")
        subprocess.run(["pdftoppm", "-png", "-r", "200", "-f", "1", "-l", "1", "-singlefile", out["pdf_roll"],
                        os.path.join(IMG, "desk_label_custom")], check=True)
        r["images"].append(snap("labels"))
        r["images"].append("desk_label_custom.png")
        return f"{t.summary.cget('text')}; файлы: " + ", ".join(os.path.basename(p) for p in out.values())

    @step("D12", "ru", "Этикетки: печать на сетевой принтер (TCP 9100)",
          "Принтер получает ZPL-задание, в журнале печати статус ok")
    def _(r):
        t = APP.tabs["labels"]
        port, got = fake_printer()
        t.fmt_combo.current(2)
        t.target_var.set(f"tcp://127.0.0.1:{port}")
        ok = t.print_target()
        time.sleep(0.3)
        must(ok and got.get("data", b"").startswith(b"^XA"), f"ok={ok} байт={len(got.get('data', b''))}")
        job = con.execute("SELECT status, message FROM label_jobs ORDER BY id DESC").fetchone()
        must(job["status"] == "ok", dict(job))
        return f"{APP.status.get()}; принтер получил {len(got['data'])} байт"

    @step("D13", "ru", "Excel / CSV: выгрузка полного отчёта и CSV",
          "Книга Excel со всеми листами и CSV каталога сохранены; EAN-13 в Excel — текст")
    def _(r):
        APP.show("exchange")
        t = APP.tabs["exchange"]
        t.open_var.set(False)
        t.ds_combo.current(0)
        x = t.export("xlsx", os.path.join(TMP, "full.xlsx"))
        t.ds_combo.current(1)
        c = t.export("csv", os.path.join(TMP, "catalog.csv"))
        from openpyxl import load_workbook
        wb = load_workbook(x)
        must(len(wb.sheetnames) == 7, wb.sheetnames)
        must(open(c, encoding="utf-8-sig").readline().startswith("Артикул;"), "csv")
        shutil.copy(x, os.path.join(OUT, "sample_full_report.xlsx"))
        r["images"].append(snap("exchange"))
        return "Листы: " + ", ".join(wb.sheetnames)

    @step("D14", "ru", "Excel: правка цен в Excel и загрузка обратно, загрузка каталога",
          "Цена из Excel записана (зафиксированная — тоже, по явному значению); каталог из Excel создал модель, "
          "варианты и приёмку")
    def _(r):
        t = APP.tabs["exchange"]
        t.ds_combo.current(t.ds_keys.index("prices"))
        p = t.export("xlsx", os.path.join(TMP, "prices.xlsx"))
        from openpyxl import Workbook, load_workbook
        wb = load_workbook(p)
        ws = wb.active
        head = [c.value for c in ws[1]]
        ws.cell(2, head.index("Цена") + 1).value = 249.9
        wb.save(p)
        res = t.do_import(p, "prices")
        must(res["updated"] == 1 and store.product(con, 1)["retail_price"] == 249.9, res)
        wb = Workbook()
        ws = wb.active
        ws.append(["Артикул", "Название", "Название RO", "Категория", "Код цвета", "Размер", "Кол-во", "Закупка (валюта)"])
        ws.append(["JNS0100", "Джинсы mom fit", "Blugi mom fit", "JNS", "400", "28", 6, 7.8])
        ws.append(["JNS0100", "Джинсы mom fit", "", "JNS", "400", "30", 4, 7.8])
        cp = os.path.join(TMP, "catalog_in.xlsx")
        wb.save(cp)
        t.ish_combo.current(1)
        res = t.do_import(cp, "catalog")
        must((res["products"], res["variants"], res["received"]) == (1, 2, 10), res)
        r["images"].append(snap("exchange_import"))
        return f"цены: {res}"

    @step("D15", "ru", "Настройки: язык этикетки румынский",
          "Сохранено; на этикетке цвет «Alb», название «Tricou basic oversize»")
    def _(r):
        APP.show("settings")
        t = APP.tabs["settings"]
        for f in t.forms:
            if "label_lang" in f.vars:
                f.set("label_lang", i18n.LANG_NAMES["ro"])
        t.save()
        lb = store.label_rows(con, {1: 1})[0]
        must((lb.color, lb.name) == ("Alb", "Tricou basic oversize"), (lb.color, lb.name))
        r["images"].append(snap("settings"))
        return f"{lb.name} · {lb.color} · {lb.composition}"

    for sid, lang in (("D16", "ro"), ("D17", "en")):
        @step(sid, lang, f"Все вкладки на {'румынском' if lang == 'ro' else 'английском'}",
              "Переключение языка перестраивает окно; на 8 вкладках, в меню и заголовках таблиц нет кириллицы")
        def _(r, lang=lang):
            APP.set_language(lang)
            bad = []
            for key in app_mod.TAB_KEYS:
                APP.show(key)
                texts = ui_texts(APP)
                cyr = [t for t in texts if re.search("[А-Яа-яЁё]", t) and t not in ("Русский",)]
                if cyr:
                    bad.append(f"{key}: {cyr[:3]}")
                r["images"].append(snap(f"{lang}_{key}"))
            must(not bad, bad)
            return "Вкладки: " + " · ".join(APP.nb.tab(t, "text") for t in APP.nb.tabs())

    @step("D18", "ru", "Ошибки Tk за весь прогон", "Необработанных исключений в обработчиках событий нет")
    def _(r):
        APP.set_language("ru")
        must(not errors, "\n".join(errors)[:1500])
        return "Ошибок: 0"

    APP.destroy()
    import platform
    meta = {"python": platform.python_version(), "tk": str(tk.TkVersion), "os": f"{platform.system()} {platform.release()}"}
    with open(os.path.join(OUT, "desktop_results.json"), "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "results": results}, f, ensure_ascii=False, indent=1)
    failed = sum(r["status"] != "PASS" for r in results)
    print(f"\nDESKTOP: {len(results) - failed}/{len(results)} PASS")
    shutil.rmtree(TMP, ignore_errors=True)
    return 1 if failed else 0


SNAP_BACK = 0.5

if __name__ == "__main__":
    sys.exit(main())
