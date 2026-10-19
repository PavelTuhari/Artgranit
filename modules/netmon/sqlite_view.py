"""Чтение SQLite для просмотрщика — без окон, проверяется тестами.

Окна — modules/netmon/scripts/otrs_ai_browser.py. Здесь только запросы:
список таблиц, страница таблицы с поиском и сортировкой, произвольный SQL,
сборка заявки целиком для базы OTRS (otrs_ai.sqlite).

База открывается ТОЛЬКО НА ЧТЕНИЕ (URI mode=ro): из просмотрщика её нельзя
испортить ни кнопкой, ни запросом в консоли.
"""
from __future__ import annotations

import csv
import re
import sqlite3
import time
from pathlib import Path

PAGE = 500


def _q(name: str) -> str:
    """Имя таблицы или столбца в кавычках — безопасно для любых символов."""
    return '"' + name.replace('"', '""') + '"'


class Db:
    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser()
        if not self.path.exists():
            raise FileNotFoundError(self.path)
        self.con = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True, check_same_thread=False)
        # LIKE в SQLite не различает регистр только для латиницы — для поиска
        # по русским и румынским текстам нужна своя функция.
        self.con.create_function("ulower", 1, lambda s: s.lower() if isinstance(s, str) else s,
                                 deterministic=True)

    def close(self) -> None:
        self.con.close()

    # ------------------------------------------------------------- структура

    def objects(self) -> list[dict]:
        rows = self.con.execute("SELECT name, type FROM sqlite_master WHERE type IN ('table','view') "
                                "AND name NOT LIKE 'sqlite_%' ORDER BY type, name").fetchall()
        out = []
        for name, kind in rows:
            try:
                n = self.con.execute(f"SELECT COUNT(*) FROM {_q(name)}").fetchone()[0]
            except sqlite3.Error:
                n = None
            out.append({"name": name, "type": kind, "rows": n})
        return out

    def columns(self, table: str) -> list[str]:
        return [r[1] for r in self.con.execute(f"PRAGMA table_info({_q(table)})")]

    def has(self, *tables: str) -> bool:
        names = {o["name"] for o in self.objects()}
        return all(t in names for t in tables)

    # ------------------------------------------------------- страница таблицы

    def page(self, table: str, search: str = "", order: str | None = None, desc: bool = False,
             offset: int = 0, limit: int = PAGE) -> dict:
        cols = self.columns(table)
        where, args = "", []
        if search.strip():
            # каждое слово должно встретиться хотя бы в одном столбце
            parts = []
            for word in search.lower().split():
                parts.append("(" + " OR ".join(f"ulower(CAST({_q(c)} AS TEXT)) LIKE ?" for c in cols) + ")")
                args += [f"%{word}%"] * len(cols)
            where = " WHERE " + " AND ".join(parts)
        order_sql = ""
        if order and order in cols:
            order_sql = f" ORDER BY {_q(order)} {'DESC' if desc else 'ASC'}"
        total = self.con.execute(f"SELECT COUNT(*) FROM {_q(table)}{where}", args).fetchone()[0]
        rows = self.con.execute(f"SELECT * FROM {_q(table)}{where}{order_sql} LIMIT ? OFFSET ?",
                                args + [limit, offset]).fetchall()
        return {"columns": cols, "rows": rows, "total": total, "offset": offset, "limit": limit}

    # ---------------------------------------------------------------- SQL

    def run_sql(self, sql: str, limit: int = 5000) -> dict:
        t = time.time()
        cur = self.con.execute(sql)
        cols = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchmany(limit + 1) if cols else []
        more = len(rows) > limit
        return {"columns": cols, "rows": rows[:limit], "more": more,
                "ms": round((time.time() - t) * 1000)}

    @staticmethod
    def to_csv(path: str | Path, columns: list[str], rows: list) -> int:
        with open(path, "w", newline="", encoding="utf-8-sig") as f:   # BOM — чтобы Excel понял UTF-8
            w = csv.writer(f)
            w.writerow(columns)
            w.writerows(rows)
        return len(rows)

    # ------------------------------------------------------- заявка OTRS

    def find_ticket(self, key: str) -> list[dict]:
        """Номер, id или слова из названия → подходящие заявки."""
        key = key.strip()
        if not key:
            return []
        if re.fullmatch(r"\d+", key):
            rows = self.con.execute("SELECT id, tn, title FROM tickets WHERE tn = ? OR id = ? LIMIT 50",
                                    [key, int(key)]).fetchall()
            if rows:
                return [{"id": r[0], "tn": r[1], "title": r[2]} for r in rows]
        rows = self.con.execute("SELECT id, tn, title FROM tickets WHERE ulower(title) LIKE ? "
                                "ORDER BY changed DESC LIMIT 200", [f"%{key.lower()}%"]).fetchall()
        return [{"id": r[0], "tn": r[1], "title": r[2]} for r in rows]

    def ticket(self, ticket_id: int) -> dict | None:
        c = self.con
        c.row_factory = sqlite3.Row
        try:
            t = c.execute("""SELECT t.*, s.name state, q.name queue, p.name priority, u.login owner,
                                    trim(u.first_name || ' ' || u.last_name) owner_name
                               FROM tickets t LEFT JOIN states s ON s.id = t.state_id
                               LEFT JOIN queues q ON q.id = t.queue_id LEFT JOIN priorities p ON p.id = t.priority_id
                               LEFT JOIN users u ON u.id = t.owner_id WHERE t.id = ?""", [ticket_id]).fetchone()
            if not t:
                return None
            facts = c.execute("SELECT * FROM ticket_facts WHERE ticket_id = ?", [ticket_id]).fetchone()
            thread = c.execute("""SELECT a.id, a.created, st.name sender, at.name type, a.a_from, a.a_to,
                                         a.subject, a.body_text, a.body_truncated, a.secrets_masked,
                                         u.login author,
                                         (SELECT group_concat(filename, ', ') FROM attachments x
                                           WHERE x.article_id = a.id) files
                                    FROM articles a LEFT JOIN sender_types st ON st.id = a.sender_type_id
                                    LEFT JOIN article_types at ON at.id = a.type_id
                                    LEFT JOIN users u ON u.id = a.created_by
                                   WHERE a.ticket_id = ? ORDER BY a.created, a.id""", [ticket_id]).fetchall()
            history = c.execute("""SELECT h.created, ht.name type, h.name, u.login who
                                     FROM history h LEFT JOIN history_types ht ON ht.id = h.history_type_id
                                     LEFT JOIN users u ON u.id = h.created_by
                                    WHERE h.ticket_id = ? ORDER BY h.created, h.id""", [ticket_id]).fetchall()
            work = c.execute("""SELECT w.started, u.login who, e.name_ru event, w.seconds, w.comment
                                  FROM work_log w LEFT JOIN users u ON u.id = w.user_id
                                  LEFT JOIN work_events e ON e.id = w.event_id
                                 WHERE w.ticket_id = ? AND COALESCE(w.deleted, 0) = 0
                                 ORDER BY w.started""", [ticket_id]).fetchall()
            return {"ticket": dict(t), "facts": dict(facts) if facts else {},
                    "thread": [dict(r) for r in thread], "history": [dict(r) for r in history],
                    "work": [dict(r) for r in work]}
        finally:
            c.row_factory = None


def cell(v, width: int = 200) -> str:
    """Значение для ячейки таблицы: одной строкой и не длиннее width."""
    if v is None:
        return "∅"
    s = str(v).replace("\r\n", " ⏎ ").replace("\n", " ⏎ ").replace("\t", " ")
    return s if len(s) <= width else s[:width - 1] + "…"
