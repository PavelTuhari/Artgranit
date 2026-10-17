#!/usr/bin/env python3
"""Просмотрщик SQLite — настольное окно (Tkinter), для базы заявок OTRS и любой другой.

    python modules/netmon/scripts/otrs_ai_browser.py                       # ~/.netmon/otrs_ai/otrs_ai.sqlite
    python modules/netmon/scripts/otrs_ai_browser.py /путь/к/базе.sqlite

Запускать питоном проекта (/Users/pt/Projects.AI/Artgranit/venv/bin/python):
в нём есть Tkinter, а в питоне Homebrew — нет.

Вкладки:
  Таблица — постранично, поиск по всем столбцам (регистр не важен, кириллица
            тоже), сортировка щелчком по заголовку, все поля строки снизу;
  Заявка  — для базы OTRS: признаки, переписка по порядку, история, журнал
            работ, кнопка «Открыть в OTRS»;
  SQL     — свой запрос (⌘↵), результат, выгрузка в CSV.

База открывается ТОЛЬКО НА ЧТЕНИЕ — испортить её отсюда нельзя.
Работа с базой — modules/netmon/sqlite_view.py.

Клавиши: ⌘O — открыть базу, ⌘F — поиск, ⌘↵ — выполнить SQL,
⌘C — копировать выбранные строки (через табуляцию, вставляются в Excel).
"""
from __future__ import annotations

import sys
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from modules.netmon.sqlite_view import PAGE, Db, cell  # noqa: E402

DEFAULT_DB = Path.home() / ".netmon" / "otrs_ai" / "otrs_ai.sqlite"
MOD = "Command" if sys.platform == "darwin" else "Control"
SENDER_TAG = {"customer": "customer", "agent": "agent", "system": "system"}


class Grid(ttk.Frame):
    """Таблица с прокруткой в обе стороны и сортировкой по заголовку."""

    def __init__(self, master, on_sort=None, on_select=None, height=20):
        super().__init__(master)
        self.tree = ttk.Treeview(self, show="headings", height=height, selectmode="extended")
        ys = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        xs = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        xs.grid(row=1, column=0, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.on_sort, self.on_select = on_sort, on_select
        self.columns, self.rows = [], []
        self.tree.tag_configure("odd", background="#f4f6f8")
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._selected())
        self.tree.bind(f"<{MOD}-c>", lambda e: self.copy())
        self.tree.bind("<Double-1>", self._double)

    def show(self, columns, rows, sort_col=None, desc=False):
        self.columns, self.rows = list(columns), list(rows)
        self.tree.delete(*self.tree.get_children())
        self.tree["columns"] = [str(i) for i in range(len(columns))]
        font_w = 7
        for i, c in enumerate(columns):
            arrow = (" ▼" if desc else " ▲") if c == sort_col else ""
            sample = [len(cell(r[i], 60)) for r in rows[:50]]
            w = min(max(len(c) + 3, max(sample, default=4)) * font_w + 16, 420)
            self.tree.heading(str(i), text=c + arrow, anchor="w",
                              command=(lambda col=c: self.on_sort(col)) if self.on_sort else "")
            self.tree.column(str(i), width=w, minwidth=40, stretch=False, anchor="w")
        for n, r in enumerate(rows):
            self.tree.insert("", "end", iid=str(n), values=[cell(v) for v in r], tags=("odd",) if n % 2 else ())

    def selected_rows(self):
        return [self.rows[int(i)] for i in self.tree.selection()]

    def _selected(self):
        sel = self.selected_rows()
        if sel and self.on_select:
            self.on_select(dict(zip(self.columns, sel[0])))

    def _double(self, event):
        """Двойной щелчок по ссылке — открыть в браузере."""
        col = self.tree.identify_column(event.x)
        row = self.tree.identify_row(event.y)
        if not col or not row:
            return
        v = self.rows[int(row)][int(col[1:]) - 1]
        if isinstance(v, str) and v.startswith(("http://", "https://")):
            webbrowser.open(v)

    def copy(self):
        sel = self.selected_rows()
        if not sel:
            return
        text = "\t".join(self.columns) + "\n" + "\n".join(
            "\t".join("" if v is None else str(v).replace("\t", " ").replace("\n", " ") for v in r) for r in sel)
        self.clipboard_clear()
        self.clipboard_append(text)


def text_box(master, height=10, wrap="word"):
    frame = ttk.Frame(master)
    t = tk.Text(frame, height=height, wrap=wrap, relief="flat", padx=10, pady=8,
                font=("Menlo", 12) if sys.platform == "darwin" else ("Consolas", 10))
    s = ttk.Scrollbar(frame, orient="vertical", command=t.yview)
    t.configure(yscrollcommand=s.set)
    t.pack(side="left", fill="both", expand=True)
    s.pack(side="right", fill="y")
    return frame, t


class App(tk.Tk):
    def __init__(self, path: Path | None):
        super().__init__()
        self.title("Просмотр SQLite")
        self.geometry("1400x860")
        self.minsize(900, 560)
        try:
            ttk.Style(self).theme_use("aqua" if sys.platform == "darwin" else "clam")
        except tk.TclError:
            pass
        self.db: Db | None = None
        self.table = None
        self.sort_col, self.sort_desc, self.offset = None, False, 0
        self._build()
        if path and Path(path).expanduser().exists():
            self.open_db(Path(path).expanduser())
        else:
            self.after(200, self.ask_open)

    # ------------------------------------------------------------ разметка

    def _build(self):
        bar = ttk.Frame(self, padding=(10, 8))
        bar.pack(fill="x")
        ttk.Button(bar, text="Открыть базу…", command=self.ask_open).pack(side="left")
        self.path_lbl = ttk.Label(bar, text="база не открыта", foreground="#6d6e6f")
        self.path_lbl.pack(side="left", padx=12)
        ttk.Label(bar, text="🔒 только чтение", foreground="#5da283").pack(side="right")

        pan = ttk.PanedWindow(self, orient="horizontal")
        pan.pack(fill="both", expand=True, padx=10, pady=(0, 6))

        left = ttk.Frame(pan, width=260)
        ttk.Label(left, text="Таблицы и представления", font=("", 12, "bold")).pack(anchor="w", pady=(0, 4))
        self.objs = ttk.Treeview(left, columns=("rows",), show="tree headings", height=30)
        self.objs.heading("#0", text="Имя", anchor="w")
        self.objs.heading("rows", text="Строк", anchor="e")
        self.objs.column("#0", width=180)
        self.objs.column("rows", width=70, anchor="e")
        self.objs.pack(fill="both", expand=True)
        self.objs.bind("<<TreeviewSelect>>", lambda e: self._pick_object())
        pan.add(left, weight=0)

        self.nb = ttk.Notebook(pan)
        pan.add(self.nb, weight=1)
        self._tab_table()
        self._tab_ticket()
        self._tab_sql()

        self.status = ttk.Label(self, text="", padding=(10, 2, 10, 6), foreground="#6d6e6f")
        self.status.pack(fill="x")
        self.bind_all(f"<{MOD}-o>", lambda e: self.ask_open())
        self.bind_all(f"<{MOD}-f>", lambda e: (self.nb.select(0), self.search.focus_set()))

    def _tab_table(self):
        tab = ttk.Frame(self.nb, padding=8)
        self.nb.add(tab, text="Таблица")
        top = ttk.Frame(tab)
        top.pack(fill="x", pady=(0, 6))
        ttk.Label(top, text="Поиск:").pack(side="left")
        self.search = ttk.Entry(top, width=50)
        self.search.pack(side="left", padx=6)
        self.search.bind("<Return>", lambda e: self.load_page(0))
        ttk.Button(top, text="Найти", command=lambda: self.load_page(0)).pack(side="left")
        ttk.Button(top, text="Сброс", command=self._reset_search).pack(side="left", padx=4)
        ttk.Button(top, text="▶", width=3, command=lambda: self.load_page(self.offset + PAGE)).pack(side="right")
        self.page_lbl = ttk.Label(top, text="")
        self.page_lbl.pack(side="right", padx=8)
        ttk.Button(top, text="◀", width=3, command=lambda: self.load_page(max(self.offset - PAGE, 0))).pack(side="right")
        ttk.Button(top, text="В CSV…", command=self._table_csv).pack(side="right", padx=8)

        split = ttk.PanedWindow(tab, orient="vertical")
        split.pack(fill="both", expand=True)
        self.grid_tbl = Grid(split, on_sort=self._sort, on_select=self._show_record)
        split.add(self.grid_tbl, weight=3)
        rec, self.record = text_box(split, height=10)
        split.add(rec, weight=1)
        self.record.tag_configure("key", foreground="#4573d2", font=("Menlo", 12, "bold"))

    def _tab_ticket(self):
        tab = ttk.Frame(self.nb, padding=8)
        self.nb.add(tab, text="Заявка")
        top = ttk.Frame(tab)
        top.pack(fill="x", pady=(0, 6))
        ttk.Label(top, text="Номер, id или слова из названия:").pack(side="left")
        self.tkey = ttk.Entry(top, width=40)
        self.tkey.pack(side="left", padx=6)
        self.tkey.bind("<Return>", lambda e: self.find_ticket())
        ttk.Button(top, text="Найти", command=self.find_ticket).pack(side="left")
        self.otrs_btn = ttk.Button(top, text="Открыть в OTRS", state="disabled")
        self.otrs_btn.pack(side="right")

        split = ttk.PanedWindow(tab, orient="horizontal")
        split.pack(fill="both", expand=True)
        lst = ttk.Frame(split)
        self.found = ttk.Treeview(lst, columns=("tn", "title"), show="headings")
        self.found.heading("tn", text="Номер", anchor="w")
        self.found.heading("title", text="Название", anchor="w")
        self.found.column("tn", width=130)
        self.found.column("title", width=260)
        self.found.pack(fill="both", expand=True)
        self.found.bind("<<TreeviewSelect>>", lambda e: self._pick_ticket())
        split.add(lst, weight=1)

        right = ttk.Notebook(split)
        split.add(right, weight=3)
        f1, self.t_thread = text_box(right)
        f2, self.t_hist = text_box(right, wrap="none")
        f3, self.t_work = text_box(right)
        right.add(f1, text="Переписка")
        right.add(f2, text="История")
        right.add(f3, text="Журнал работ")
        for t in (self.t_thread, self.t_hist, self.t_work):
            t.tag_configure("h1", font=("", 15, "bold"), spacing3=4)
            t.tag_configure("dim", foreground="#6d6e6f")
            t.tag_configure("key", foreground="#4573d2")
            t.tag_configure("customer", foreground="#ffffff", background="#4573d2")
            t.tag_configure("agent", foreground="#ffffff", background="#5da283")
            t.tag_configure("system", foreground="#ffffff", background="#9ca6af")
            t.tag_configure("note", foreground="#1e1f21", background="#f1bd6c")
            t.tag_configure("warn", foreground="#f06a6a")

    def _tab_sql(self):
        tab = ttk.Frame(self.nb, padding=8)
        self.nb.add(tab, text="SQL")
        top = ttk.Frame(tab)
        top.pack(fill="x")
        frame, self.sql = text_box(top, height=7, wrap="none")
        frame.pack(fill="x", expand=True)
        self.sql.insert("1.0", "SELECT board_list, count(*) AS n\n  FROM ticket_facts\n GROUP BY 1\n ORDER BY 2 DESC;")
        self.sql.bind(f"<{MOD}-Return>", lambda e: (self.run_sql(), "break")[1])
        btns = ttk.Frame(tab)
        btns.pack(fill="x", pady=6)
        ttk.Button(btns, text="Выполнить  ⌘↵", command=self.run_sql).pack(side="left")
        ttk.Button(btns, text="В CSV…", command=self._sql_csv).pack(side="left", padx=6)
        self.sql_lbl = ttk.Label(btns, text="база только на чтение: INSERT/UPDATE/DELETE не пройдут",
                                 foreground="#6d6e6f")
        self.sql_lbl.pack(side="left", padx=10)
        self.grid_sql = Grid(tab)
        self.grid_sql.pack(fill="both", expand=True)
        self.sql_result = None

    # ------------------------------------------------------------ база

    def ask_open(self):
        p = filedialog.askopenfilename(title="Открыть базу SQLite",
                                       initialdir=str(DEFAULT_DB.parent if DEFAULT_DB.parent.exists() else Path.home()),
                                       filetypes=[("SQLite", "*.sqlite *.db *.sqlite3"), ("Все файлы", "*")])
        if p:
            self.open_db(Path(p))

    def open_db(self, path: Path):
        try:
            db = Db(path)
            objs = db.objects()
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Не открылась", f"{path}\n\n{e}")
            return
        if self.db:
            self.db.close()
        self.db = db
        self.title(f"Просмотр SQLite — {path.name}")
        self.path_lbl.config(text=str(path))
        self.objs.delete(*self.objs.get_children())
        for kind, title in (("table", "Таблицы"), ("view", "Представления")):
            parent = self.objs.insert("", "end", text=title, open=True, values=("",))
            for o in objs:
                if o["type"] == kind:
                    self.objs.insert(parent, "end", iid=o["name"], text=o["name"],
                                     values=("" if o["rows"] is None else f"{o['rows']:,}".replace(",", " "),))
        has_tickets = db.has("tickets", "articles", "history")
        self.nb.tab(1, state="normal" if has_tickets else "disabled")
        first = "tickets" if has_tickets else next((o["name"] for o in objs if o["type"] == "table"), None)
        if first:
            self.objs.selection_set(first)
            self.objs.see(first)
        meta = ""
        if db.has("meta"):
            m = dict(db.run_sql("SELECT key, value FROM meta")["rows"])
            meta = f" · выгружено {m.get('exported_at', '?')}, окно {m.get('months', '?')} мес."
        self.status.config(text=f"{len(objs)} объектов{meta}")

    def _pick_object(self):
        sel = self.objs.selection()
        if not sel or not self.db or sel[0] in ("", None) or not self.objs.parent(sel[0]):
            return
        self.table = sel[0]
        self.sort_col, self.sort_desc = None, False
        self.nb.select(0)
        self.load_page(0)

    def _reset_search(self):
        self.search.delete(0, "end")
        self.load_page(0)

    def _sort(self, col):
        self.sort_desc = (not self.sort_desc) if self.sort_col == col else False
        self.sort_col = col
        self.load_page(0)

    def load_page(self, offset: int):
        if not self.db or not self.table:
            return
        try:
            p = self.db.page(self.table, self.search.get(), self.sort_col, self.sort_desc, offset)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Ошибка запроса", str(e))
            return
        if offset and offset >= p["total"]:
            return
        self.offset = offset
        self.grid_tbl.show(p["columns"], p["rows"], self.sort_col, self.sort_desc)
        last = min(offset + len(p["rows"]), p["total"])
        self.page_lbl.config(text=f"{offset + 1 if p['total'] else 0}–{last} из {p['total']:,}".replace(",", " "))
        self.record.delete("1.0", "end")
        self.status.config(text=f"{self.table}: {p['total']:,} строк".replace(",", " ")
                                + (f" по запросу «{self.search.get()}»" if self.search.get().strip() else ""))

    def _show_record(self, rec: dict):
        self.record.delete("1.0", "end")
        for k, v in rec.items():
            self.record.insert("end", f"{k}: ", "key")
            self.record.insert("end", ("∅" if v is None else str(v)) + "\n")

    def _table_csv(self):
        if not self.db or not self.table:
            return
        p = filedialog.asksaveasfilename(defaultextension=".csv", initialfile=f"{self.table}.csv")
        if not p:
            return
        res = self.db.page(self.table, self.search.get(), self.sort_col, self.sort_desc, 0, limit=10**9)
        n = Db.to_csv(p, res["columns"], res["rows"])
        self.status.config(text=f"в CSV выгружено {n} строк: {p}")

    # ------------------------------------------------------------- заявка

    def find_ticket(self):
        if not self.db:
            return
        rows = self.db.find_ticket(self.tkey.get())
        self.found.delete(*self.found.get_children())
        for r in rows:
            self.found.insert("", "end", iid=str(r["id"]), values=(r["tn"], cell(r["title"], 80)))
        if rows:
            self.found.selection_set(str(rows[0]["id"]))
        self.status.config(text=f"найдено заявок: {len(rows)}")

    def _pick_ticket(self):
        sel = self.found.selection()
        if sel:
            self.show_ticket(int(sel[0]))

    def show_ticket(self, tid: int):
        d = self.db.ticket(tid)
        if not d:
            return
        t, f = d["ticket"], d["facts"]
        self.otrs_btn.config(state="normal", command=lambda: webbrowser.open(t["url"]))
        x = self.t_thread
        x.delete("1.0", "end")
        x.insert("end", f"{t['title']}\n", "h1")
        x.insert("end", f"#{t['tn']} · {t['state']} · {t['queue']} · владелец {t['owner']} · "
                        f"клиент {t['customer_id'] or '—'}\n", "dim")
        if f:
            x.insert("end", f"список: {f.get('board_list')} · ход за: {f.get('waiting_on')} · "
                            f"первый ответ {f.get('first_reply_hours')} ч · возвратов {f.get('returns_to_owner')} · "
                            f"исполнители {f.get('executors') or '—'} · работы {f.get('work_hours')} ч\n", "key")
        x.insert("end", "\n")
        for a in d["thread"]:
            note = a["type"] and a["type"].startswith("note")
            x.insert("end", f" {a['sender']}{' · заметка' if note else ''} ", "note" if note else SENDER_TAG.get(a["sender"], "system"))
            x.insert("end", f"  {a['created']}  {a['author'] or a['a_from'] or ''}\n", "dim")
            if a["subject"]:
                x.insert("end", a["subject"] + "\n", "key")
            x.insert("end", (a["body_text"] or "").strip() + "\n")
            if a["files"]:
                x.insert("end", f"📎 {a['files']}\n", "dim")
            if a["body_truncated"]:
                x.insert("end", "… письмо обрезано при выгрузке\n", "warn")
            x.insert("end", "\n")
        h = self.t_hist
        h.delete("1.0", "end")
        for r in d["history"]:
            h.insert("end", f"{r['created']}  ", "dim")
            h.insert("end", f"{r['type']:<22} ", "key")
            h.insert("end", f"{r['who'] or '':<14} {r['name'] or ''}\n")
        w = self.t_work
        w.delete("1.0", "end")
        total = 0
        for r in d["work"]:
            total += r["seconds"] or 0
            w.insert("end", f"{r['started']}  ", "dim")
            w.insert("end", f"{r['who'] or '':<14} {(r['seconds'] or 0) / 3600:>5.2f} ч  ", "key")
            w.insert("end", f"{r['event'] or ''}\n   {r['comment'] or ''}\n")
        w.insert("1.0", f"Всего: {total / 3600:.2f} ч, записей {len(d['work'])}\n\n", "h1")
        self.status.config(text=f"заявка #{t['tn']}: писем {len(d['thread'])}, истории {len(d['history'])}, "
                                f"работ {len(d['work'])}")

    # ---------------------------------------------------------------- SQL

    def run_sql(self):
        if not self.db:
            return
        sql = self.sql.get("1.0", "end").strip()
        try:
            r = self.db.run_sql(sql)
        except Exception as e:  # noqa: BLE001
            self.sql_lbl.config(text=f"ошибка: {e}", foreground="#f06a6a")
            return
        self.sql_result = r
        self.grid_sql.show(r["columns"], r["rows"])
        self.sql_lbl.config(foreground="#6d6e6f",
                            text=f"{len(r['rows'])} строк{' (показаны первые)' if r['more'] else ''} за {r['ms']} мс")

    def _sql_csv(self):
        if not self.sql_result:
            return
        p = filedialog.asksaveasfilename(defaultextension=".csv", initialfile="query.csv")
        if p:
            n = Db.to_csv(p, self.sql_result["columns"], self.sql_result["rows"])
            self.sql_lbl.config(text=f"в CSV выгружено {n} строк")


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB
    App(path).mainloop()


if __name__ == "__main__":
    main()
