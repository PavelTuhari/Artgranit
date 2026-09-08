"""Stratul de date al procesului CRM (portul lui TCrmData pe Oracle OfficePlus).

RO: CRUD generic dupa descrierile din entities.py, etapele, doua, liniile
comenzii, proiectele, conversia leadului si contarea comenzii — toate cu
chiriasul (OWNER_KIND/OWNER_ID) in fiecare SQL. Acelasi transport ca restul
modulelor ERP (`Biro26DB`, worker thick). Datele: DATE in baza, yyyy-mm-dd
in API (TO_CHAR / TO_DATE explicit, nu ne bazam pe NLS). Numerele goale
sint NULL, nu '' (lectia SQLite din prototip ramine valabila).
EN: TCrmData port: generic CRUD, stages, boards, order lines, posting.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from models.biro26_db import Biro26DB
from models.biro26_oracle_store import _rows

from modules.crm import process
from modules.crm.entities import (BOOL, DATE, ENUM, LOOKUPS, LOOKUP_TABLE, NUMERIC,
                                  READONLY, Entity, entity)
from modules.crm.tenant import Tenant


def _num(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        return float(str(v).replace(",", ".").replace(" ", ""))
    except ValueError:
        return None


def _date(v: Any) -> Optional[str]:
    s = (str(v) if v is not None else "").strip()
    return s[:10] if s else None


class CrmData:
    def __init__(self, tenant: Tenant, db: Optional[Biro26DB] = None):
        self.t = tenant
        self.db = db or Biro26DB()

    # ── utilitare ────────────────────────────────────────────────────────
    def rows(self, sql: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        return _rows(self.db.execute_query(sql, params or {}))

    def scalar(self, sql: str, params: Optional[Dict[str, Any]] = None) -> Any:
        r = self.db.execute_query(sql, params or {})
        data = r.get("data") or []
        if not r.get("success"):
            raise RuntimeError(r.get("message") or "eroare SQL")
        return (data[0][0] if data and data[0] else None)

    def dml(self, sql: str, params: Optional[Dict[str, Any]] = None) -> None:
        r = self.db.execute_dml(sql, params or {})
        if not r.get("success"):
            raise RuntimeError(r.get("message") or "eroare DML")

    def next_id(self, table: str) -> int:
        return int(self.scalar("SELECT %s_SEQ.NEXTVAL FROM dual" % table))

    def count(self, table: str, where: str = "", params: Optional[Dict[str, Any]] = None) -> int:
        # RO: aliasul t e obligatoriu — conditiile etapelor si preseturilor sint pe «t.»
        sql = "SELECT COUNT(*) FROM %s t WHERE %s" % (table, self.t.where())
        if where:
            sql += " AND (%s)" % where
        return int(self.scalar(sql, dict(self.t.params(), **(params or {}))) or 0)

    # ── CRUD generic (List / Get / Insert / Update / Delete) ─────────────
    def _select_cols(self, e: Entity) -> str:
        cols = ["t.ID"]
        for f in e.fields:
            c = "t." + f.column
            if f.kind == DATE:
                cols.append("TO_CHAR(%s,'YYYY-MM-DD') AS %s" % (c, f.column))
            else:
                cols.append("%s AS %s" % (c, f.column))
            if f.kind in LOOKUPS:
                lt, ld = LOOKUP_TABLE[f.kind]
                cols.append("(SELECT x.%s FROM %s x WHERE x.ID = %s) AS %s__DISP" % (ld, lt, c, f.column))
        return ", ".join(cols)

    def _row_out(self, e: Entity, r: Dict[str, Any]) -> Dict[str, Any]:
        out: Dict[str, Any] = {"id": int(r["id"])}
        for f in e.fields:
            v = r.get(f.column.lower())
            if f.kind == BOOL:
                v = 1 if v in (1, "1", True) else 0
            elif f.kind in NUMERIC or f.kind == READONLY:
                v = float(v) if v not in (None, "") else None
            elif f.kind in LOOKUPS:
                v = int(v) if v not in (None, "") else None
                out[f.name + "__disp"] = r.get(f.column.lower() + "__disp") or ""
            out[f.name] = v
        return out

    def list(self, key: str, q: str = "", extra_where: str = "",
             extra_params: Optional[Dict[str, Any]] = None, limit: int = 500) -> List[Dict[str, Any]]:
        e = entity(key)
        params: Dict[str, Any] = dict(self.t.params(), **(extra_params or {}))
        where = self.t.where()
        if q and e.search:
            parts = " OR ".join("UPPER(t.%s) LIKE :q" % e.field(n).column for n in e.search)
            where += " AND (%s)" % parts
            params["q"] = "%" + q.strip().upper() + "%"
        if extra_where:
            where += " AND (%s)" % extra_where
        params["lim"] = max(1, min(int(limit), 2000))
        sql = ("SELECT * FROM (SELECT %s FROM %s t WHERE %s ORDER BY %s) WHERE ROWNUM <= :lim"
               % (self._select_cols(e), e.table, where, e.order_by))
        return [self._row_out(e, r) for r in self.rows(sql, params)]

    def get(self, key: str, rid: int) -> Optional[Dict[str, Any]]:
        rows = self.list(key, extra_where="t.ID = :rid", extra_params={"rid": int(rid)}, limit=1)
        return rows[0] if rows else None

    def _bind(self, f, value: Any) -> Tuple[str, Any]:
        """RO: expresia SQL + valoarea bindului pentru un cimp (NULL corect tipat)."""
        p = ":p_" + f.name
        if f.kind == DATE:
            return "TO_DATE(%s,'YYYY-MM-DD')" % p, _date(value)
        if f.kind in NUMERIC:
            return p, _num(value)
        if f.kind in LOOKUPS:
            return p, (int(value) if value not in (None, "", 0, "0") else None)
        if f.kind == BOOL:
            return p, (1 if value in (1, "1", True, "true") else 0)
        if f.kind == ENUM:
            v = (value or "").strip() or process.resolve_default(f.default)
            if not process.enum_ok(f.enum, v):
                raise ValueError("%s: valoare in afara listei (%s)" % (f.name, v))
            return p, v
        return p, ((str(value) if value is not None else "")[:2000] or None)

    def _validate(self, e: Entity, values: Dict[str, Any]) -> None:
        for f in e.writable():
            v = values.get(f.name)
            if f.required and f.kind not in (ENUM, BOOL) and (v is None or str(v).strip() == ""):
                if f.default:
                    values[f.name] = process.resolve_default(f.default)
                else:
                    raise ValueError("%s: cimp obligatoriu" % f.name)

    def insert(self, key: str, values: Dict[str, Any]) -> int:
        e = entity(key)
        values = dict(values or {})
        for f in e.writable():          # RO: implicitele prototipului (today, today+14, enumerari)
            if values.get(f.name) in (None, "") and f.default:
                values[f.name] = process.resolve_default(f.default)
        self._validate(e, values)
        rid = self.next_id(e.table)
        if key == "clients" and not str(values.get("idno") or "").strip():
            # RO: IDNO e UNIC si NOT NULL; clientul fara IDNO primeste codul tehnic «M-<id>»
            values["idno"] = "M-%d" % rid
        cols, exprs = ["ID", "OWNER_KIND", "OWNER_ID"], [":rid", ":ok", ":oi"]
        params: Dict[str, Any] = dict(self.t.params(), rid=rid)
        for f in e.writable():
            expr, val = self._bind(f, values.get(f.name))
            cols.append(f.column)
            exprs.append(expr)
            params["p_" + f.name] = val
        self.dml("INSERT INTO %s (%s) VALUES (%s)" % (e.table, ", ".join(cols), ", ".join(exprs)), params)
        if key == "tasks":
            self._sync_task_done(rid)
        return rid

    def update(self, key: str, rid: int, values: Dict[str, Any]) -> None:
        e = entity(key)
        current = self.get(key, rid)
        if not current:
            raise LookupError("inregistrare inexistenta")
        merged = dict(current)
        merged.update({k: v for k, v in (values or {}).items() if k in {f.name for f in e.fields}})
        self._validate(e, merged)
        sets, params = [], dict(self.t.params(), rid=int(rid))
        for f in e.writable():
            expr, val = self._bind(f, merged.get(f.name))
            sets.append("%s = %s" % (f.column, expr))
            params["p_" + f.name] = val
        self.dml("UPDATE %s t SET %s WHERE t.ID = :rid AND %s" % (e.table, ", ".join(sets), self.t.where()), params)
        if key == "tasks":
            # RO: etapa si «executat» sint o singura stare (Update din prototip)
            self.dml("UPDATE CRM_TASK SET DONE = CASE WHEN STAGE = :g THEN 1 ELSE 0 END WHERE ID = :i",
                     {"g": "Готово", "i": int(rid)})

    def delete(self, key: str, rid: int) -> None:
        e = entity(key)
        if not self.get(key, rid):
            raise LookupError("inregistrare inexistenta")
        p = dict(self.t.params(), rid=int(rid))
        if key == "projects":
            # RO: sarcinile proiectului pleaca cu el; comenzile ramin, legatura se scoate
            self.dml("DELETE FROM CRM_TASK t WHERE t.PROJECT_ID = :rid AND %s" % self.t.where(), p)
            self.dml("UPDATE CRM_ORDER t SET PROJECT_ID = NULL WHERE t.PROJECT_ID = :rid AND %s" % self.t.where(), p)
        self.dml("DELETE FROM %s t WHERE t.ID = :rid AND %s" % (e.table, self.t.where()), p)

    def lookup_pairs(self, kind: str) -> List[Dict[str, Any]]:
        lt, ld = LOOKUP_TABLE[kind]
        return self.rows("SELECT t.ID, t.%s AS D FROM %s t WHERE %s ORDER BY t.%s" % (ld, lt, self.t.where(), ld),
                         self.t.params())

    # ── sarcini si proiecte ──────────────────────────────────────────────
    def _sync_task_done(self, task_id: int) -> None:
        self.dml("UPDATE CRM_TASK SET DONE = CASE WHEN STAGE = :g THEN 1 ELSE NVL(DONE,0) END, "
                 "STAGE = CASE WHEN NVL(DONE,0) = 1 AND NVL(STAGE,'x') <> :g THEN :g ELSE STAGE END "
                 "WHERE ID = :i", {"g": "Готово", "i": int(task_id)})

    def set_task_done(self, task_id: int, done: bool) -> None:
        p = dict(self.t.params(), i=int(task_id), g="Готово", w="В работе")
        if done:
            self.dml("UPDATE CRM_TASK t SET DONE = 1, STAGE = :g WHERE t.ID = :i AND %s" % self.t.where(), p)
        else:
            self.dml("UPDATE CRM_TASK t SET DONE = 0, STAGE = CASE WHEN STAGE = :g THEN :w ELSE STAGE END "
                     "WHERE t.ID = :i AND %s" % self.t.where(), p)

    def project_summary(self, project_id: int) -> Dict[str, Any]:
        r = self.rows(
            "SELECT COUNT(*) N, SUM(CASE WHEN DONE = 1 THEN 1 ELSE 0 END) D, "
            "SUM(CASE WHEN DONE = 0 AND DUE_AT IS NOT NULL AND DUE_AT < TRUNC(SYSDATE) THEN 1 ELSE 0 END) O, "
            "NVL(SUM(HOURS_PLAN),0) HP, NVL(SUM(HOURS_FACT),0) HF FROM CRM_TASK t "
            "WHERE t.PROJECT_ID = :p AND %s" % self.t.where(), dict(self.t.params(), p=int(project_id)))
        s = r[0] if r else {}
        total = int(s.get("n") or 0)
        done = int(s.get("d") or 0)
        return {"total": total, "done": done, "overdue": int(s.get("o") or 0),
                "hours_plan": float(s.get("hp") or 0), "hours_fact": float(s.get("hf") or 0),
                "progress": int(round(done * 100 / total)) if total else 0}

    # ── liniile comenzii ─────────────────────────────────────────────────
    def order_lines(self, order_id: int) -> List[Dict[str, Any]]:
        return self.rows(
            "SELECT l.ID, l.ITEM_ID, i.NAME AS ITEM_NAME, i.UNIT_, l.QTY, l.PRICE, l.LINE_SUM AS \"SUM\" "
            "FROM CRM_ORDER_LINE l JOIN CRM_ORDER t ON t.ID = l.ORDER_ID "
            "LEFT JOIN CRM_ITEM i ON i.ID = l.ITEM_ID WHERE l.ORDER_ID = :o AND %s ORDER BY l.ID" % self.t.where(),
            dict(self.t.params(), o=int(order_id)))

    def add_order_line(self, order_id: int, item_id: int, qty: float, price: float) -> int:
        if not self.get("orders", order_id):
            raise LookupError("comanda inexistenta")
        lid = self.next_id("CRM_ORDER_LINE")
        self.dml("INSERT INTO CRM_ORDER_LINE (ID, ORDER_ID, ITEM_ID, QTY, PRICE, LINE_SUM) "
                 "VALUES (:id, :o, :i, :q, :p, :s)",
                 {"id": lid, "o": int(order_id), "i": int(item_id), "q": float(qty), "p": float(price),
                  "s": round(float(qty) * float(price), 2)})
        self.recalc_order_total(order_id)
        return lid

    def delete_order_line(self, line_id: int) -> None:
        oid = self.scalar("SELECT l.ORDER_ID FROM CRM_ORDER_LINE l JOIN CRM_ORDER t ON t.ID = l.ORDER_ID "
                          "WHERE l.ID = :l AND %s" % self.t.where(), dict(self.t.params(), l=int(line_id)))
        if not oid:
            raise LookupError("linie inexistenta")
        self.dml("DELETE FROM CRM_ORDER_LINE WHERE ID = :l", {"l": int(line_id)})
        self.recalc_order_total(int(oid))

    def recalc_order_total(self, order_id: int) -> float:
        total = float(self.scalar("SELECT NVL(SUM(LINE_SUM),0) FROM CRM_ORDER_LINE WHERE ORDER_ID = :o",
                                  {"o": int(order_id)}) or 0)
        self.dml("UPDATE CRM_ORDER SET TOTAL = :t WHERE ID = :o", {"t": total, "o": int(order_id)})
        return total

    def post_order(self, order_id: int) -> str:
        """RO: PostOrder — vinzarea scade stocul, productia il creste, o singura data."""
        o = self.get("orders", order_id)
        if not o:
            return "заказ не найден"
        posted = self.scalar("SELECT POSTED FROM CRM_ORDER WHERE ID = :o", {"o": int(order_id)})
        if int(posted or 0) == 1:
            return "уже проведён"
        if not process.post_allowed(o.get("status")):
            return "проводится только со статусом «Выполнен» или «Оплачен»"
        lines = self.order_lines(order_id)
        if not lines:
            return "нет строк"
        sign = process.post_sign(o.get("kind"))
        for ln in lines:
            if sign:
                self.dml("UPDATE CRM_ITEM SET STOCK = NVL(STOCK,0) + :d WHERE ID = :i",
                         {"d": sign * float(ln["qty"] or 0), "i": int(ln["item_id"])})
        self.dml("UPDATE CRM_ORDER SET POSTED = 1 WHERE ID = :o", {"o": int(order_id)})
        n = len(lines)
        return {-1: "списано со склада по %d строкам" % n,
                1: "оприходовано изделий по %d строкам" % n}.get(sign, "услуги — остатки без изменений")

    # ── lead -> client ───────────────────────────────────────────────────
    def convert_lead(self, lead_id: int) -> Tuple[str, int]:
        """RO: ConvertLead — clientul se creeaza din lead (fara card de registru;
        ACC-01 din TZ il completeaza ulterior prin Contragenti)."""
        ld = self.get("leads", lead_id)
        if not ld:
            return "лид не найден", 0
        if ld.get("status") == "Конвертирован":
            return "уже конвертирован", int(ld.get("client_id") or 0)
        name = ld.get("company") or ld.get("name") or ""
        cid = self.next_id("CRM_CLIENT")
        # RO: IDNO unic in CRM_CLIENT — leadul fara IDNO primeste un cod tehnic «L-<id>»
        self.dml("INSERT INTO CRM_CLIENT (ID, IDNO, NAME, SOURCE, OWNER_KIND, OWNER_ID, CLIENT_TYPE, PHONE, EMAIL, "
                 "CONTACT_PERSON) VALUES (:id, :idno, :n, 'lead', :ok, :oi, :ct, :ph, :em, :cp)",
                 dict(self.t.params(), id=cid, idno="L-%d" % cid, n=name[:400], ct="Клиент",
                      ph=(ld.get("phone") or "")[:60] or None, em=(ld.get("email") or "")[:120] or None,
                      cp=(ld.get("name") or "")[:200] or None))
        self.dml("UPDATE CRM_LEAD SET STATUS = :s, CLIENT_ID = :c WHERE ID = :i",
                 {"s": "Конвертирован", "c": cid, "i": int(lead_id)})
        return "создан клиент «%s»" % name, cid

    # ── etapele procesului (StageInfo) ────────────────────────────────────
    def stage_info(self, stage: str) -> Dict[str, Any]:
        tbl, col = process.STAGE_TABLE[stage], process.STAGE_SUM_COL[stage]
        w, p = process.stage_where(stage)
        ow, op = process.overdue_where(stage)
        base = dict(self.t.params())
        cnt = self.scalar("SELECT COUNT(*) FROM %s t WHERE %s AND (%s)" % (tbl, self.t.where(), w), dict(base, **p))
        tot = self.scalar("SELECT NVL(SUM(t.%s),0) FROM %s t WHERE %s AND (%s)" % (col, tbl, self.t.where(), w), dict(base, **p))
        ocnt = self.scalar("SELECT COUNT(*) FROM %s t WHERE %s AND (%s)" % (tbl, self.t.where(), ow), dict(base, **op))
        osum = self.scalar("SELECT NVL(SUM(t.%s),0) FROM %s t WHERE %s AND (%s)" % (col, tbl, self.t.where(), ow), dict(base, **op))
        i = process.STAGES.index(stage)
        return {"stage": stage, "index": i, "title": process.STAGE_TITLES[i], "hint": process.STAGE_HINTS[i],
                "table": "deals" if tbl == "CRM_DEAL" else "orders", "count": int(cnt or 0),
                "sum": float(tot or 0), "overdue": int(ocnt or 0), "overdue_sum": float(osum or 0)}

    def stages(self) -> List[Dict[str, Any]]:
        return [self.stage_info(s) for s in process.STAGES]

    # ── doua ─────────────────────────────────────────────────────────────
    def board(self, kind: str, project_id: int = 0) -> Dict[str, Any]:
        cols = process.board_columns(kind)
        out = []
        for i, title in enumerate(cols):
            w, p = process.board_column_where(kind, i, project_id)
            out.append({"col": i, "title": title, "color": process.BOARD_COLORS[kind][i],
                        "cards": self._board_cards(kind, w, dict(self.t.params(), **p))})
        return {"kind": kind, "columns": out}

    def _board_cards(self, kind: str, where: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        tw = self.t.where()
        if kind == "orders":
            sql = ("SELECT t.ID, t.DOC_NO AS A, NVL(c.NAME,' ') AS B, NVL(t.TOTAL,0) AS AMT, NVL(t.PAID,0) AS PAID, "
                   "TO_CHAR(t.DUE_DATE,'YYYY-MM-DD') AS DUE, t.KIND AS K, ' ' AS EXTRA "
                   "FROM CRM_ORDER t LEFT JOIN CRM_CLIENT c ON c.ID = t.CLIENT_ID WHERE %s AND (%s) "
                   "ORDER BY t.DUE_DATE, t.ID" % (tw, where))
        elif kind == "deals":
            sql = ("SELECT t.ID, t.TITLE AS A, NVL(c.NAME,' ') AS B, NVL(t.AMOUNT,0) AS AMT, 0 AS PAID, "
                   "TO_CHAR(t.CLOSE_DATE,'YYYY-MM-DD') AS DUE, t.STAGE AS K, ' ' AS EXTRA "
                   "FROM CRM_DEAL t LEFT JOIN CRM_CLIENT c ON c.ID = t.CLIENT_ID WHERE %s AND (%s) "
                   "ORDER BY t.CLOSE_DATE, t.ID" % (tw, where))
        elif kind == "projects":
            sql = ("SELECT t.ID, t.NAME AS A, NVL(c.NAME,' ') AS B, NVL(t.BUDGET,0) AS AMT, "
                   "NVL(t.PREPAID,0) + NVL(t.PAID,0) AS PAID, TO_CHAR(t.DUE_DATE,'YYYY-MM-DD') AS DUE, t.KIND AS K, "
                   "(SELECT COUNT(*) FROM CRM_TASK x WHERE x.PROJECT_ID = t.ID) || '/' || "
                   "(SELECT COUNT(*) FROM CRM_TASK x WHERE x.PROJECT_ID = t.ID AND x.DONE = 1) AS EXTRA "
                   "FROM CRM_PROJECT t LEFT JOIN CRM_CLIENT c ON c.ID = t.CLIENT_ID WHERE %s AND (%s) "
                   "ORDER BY t.DUE_DATE, t.ID" % (tw, where))
        elif kind == "project_tasks":
            sql = ("SELECT t.ID, t.SUBJECT AS A, NVL(p.NAME,' ') AS B, 0 AS AMT, 0 AS PAID, "
                   "TO_CHAR(t.DUE_AT,'YYYY-MM-DD') AS DUE, NVL(t.PRIORITY,' ') AS K, NVL(t.ASSIGNEE,' ') AS EXTRA "
                   "FROM CRM_TASK t LEFT JOIN CRM_PROJECT p ON p.ID = t.PROJECT_ID WHERE %s AND (%s) "
                   "ORDER BY NVL(t.SEQ,0), t.DUE_AT, t.ID" % (tw, where))
        else:
            sql = ("SELECT t.ID, t.SUBJECT AS A, NVL(c.NAME,' ') AS B, 0 AS AMT, 0 AS PAID, "
                   "TO_CHAR(t.DUE_AT,'YYYY-MM-DD') AS DUE, t.KIND AS K, NVL(t.ASSIGNEE,' ') AS EXTRA "
                   "FROM CRM_TASK t LEFT JOIN CRM_CLIENT c ON c.ID = t.CLIENT_ID WHERE %s AND (%s) "
                   "ORDER BY t.DUE_AT, t.ID" % (tw, where))
        cards = []
        for r in self.rows(sql, params):
            cards.append({"id": int(r["id"]), "title": (r.get("a") or "").strip(),
                          "subtitle": (r.get("b") or "").strip(), "amount": float(r.get("amt") or 0),
                          "paid": float(r.get("paid") or 0), "due": r.get("due") or "",
                          "kind": (r.get("k") or "").strip(), "extra": (r.get("extra") or "").strip()})
        return cards

    def move_card(self, kind: str, rid: int, col: int) -> None:
        """RO: singurul punct de schimbare a etapei de pe doua (MoveBoardCard)."""
        sets, p = process.board_move_sql(kind, int(col))
        tbl = process.BOARD_TABLE[kind]
        params = dict(self.t.params(), **p, rid=int(rid))
        self.dml("UPDATE %s t SET %s WHERE t.ID = :rid AND %s" % (tbl, sets, self.t.where()), params)

    # ── statistici pentru pagina de start ────────────────────────────────
    def counts(self) -> Dict[str, int]:
        out = {}
        for key in ("contacts", "leads", "deals", "items", "orders", "tasks", "projects"):
            out[key] = self.count(entity(key).table)
        out["clients"] = self.count("CRM_CLIENT")
        out["order_lines"] = int(self.scalar(
            "SELECT COUNT(*) FROM CRM_ORDER_LINE l JOIN CRM_ORDER t ON t.ID = l.ORDER_ID WHERE %s" % self.t.where(),
            self.t.params()) or 0)
        return out
