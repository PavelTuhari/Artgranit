"""Cele 6 rapoarte ale prototipului (uReports.pas) pe Oracle, per chirias.

RO: process (etapele cu sume si intirzieri), receivables (creante),
sales_by_client, funnel (pilnia ofertelor), stock (stocul nomenclatorului),
projects (proiectele cu bani si sarcini). Rezultatul e un tabel simplu
{title, subtitle, columns, rows, totals} — front-ul il arata si il da ca
CSV; titlurile coloanelor vin in limba ceruta (ro/ru/en) de aici, ca sa nu
dubleze traducerile in trei clienti.
EN: the six prototype reports as plain tables, localized captions.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

from modules.crm import process
from modules.crm.store_process import CrmData

SLUGS = ("process", "receivables", "sales_by_client", "funnel", "stock", "projects", "by_person")

# RO: titluri + coloane in 3 limbi (rusa = canonic din prototip)
_T: Dict[str, Dict[str, Dict[str, Any]]] = {
    "process": {
        "ru": {"title": "Процесс исполнения заказов",
               "sub": "Состояние на %s. Просрочка — срок исполнения в прошлом, этап не закрыт.",
               "cols": ["Этап процесса", "Что означает", "Кол-во", "Сумма, MDL", "Запаздывает", "Сумма просрочки, MDL"],
               "total": "Итого по заказам"},
        "ro": {"title": "Procesul de executare a comenzilor",
               "sub": "Starea la %s. Intirziere — termenul in trecut, etapa neinchisa.",
               "cols": ["Etapa procesului", "Ce inseamna", "Nr.", "Suma, MDL", "Intirzie", "Suma intirziata, MDL"],
               "total": "Total comenzi"},
        "en": {"title": "Order fulfilment process",
               "sub": "As of %s. Overdue — due date in the past, stage not closed.",
               "cols": ["Process stage", "Meaning", "Count", "Amount, MDL", "Overdue", "Overdue amount, MDL"],
               "total": "Orders total"}},
    "receivables": {
        "ru": {"title": "Дебиторская задолженность", "sub": "Отгруженные заказы с непогашенной оплатой на %s",
               "cols": ["Заказ", "Клиент", "Отгружен", "Срок оплаты", "Итого, MDL", "Оплачено, MDL", "Долг, MDL", "Просрочка, дн."],
               "total": "Итого"},
        "ro": {"title": "Creante", "sub": "Comenzi livrate cu plata neinchisa la %s",
               "cols": ["Comanda", "Client", "Livrat", "Termen plata", "Total, MDL", "Platit, MDL", "Datorie, MDL", "Intirziere, zile"],
               "total": "Total"},
        "en": {"title": "Receivables", "sub": "Shipped orders with outstanding payment as of %s",
               "cols": ["Order", "Client", "Shipped", "Due", "Total, MDL", "Paid, MDL", "Debt, MDL", "Overdue, days"],
               "total": "Total"}},
    "sales_by_client": {
        "ru": {"title": "Продажи по клиентам", "sub": "Все заказы, кроме отменённых, на %s",
               "cols": ["Клиент", "IDNO", "Заказов", "Сумма, MDL", "Оплачено, MDL", "Долг, MDL", "Последний заказ"],
               "total": "Итого"},
        "ro": {"title": "Vinzari pe clienti", "sub": "Toate comenzile, fara cele anulate, la %s",
               "cols": ["Client", "IDNO", "Comenzi", "Suma, MDL", "Platit, MDL", "Datorie, MDL", "Ultima comanda"],
               "total": "Total"},
        "en": {"title": "Sales by client", "sub": "All orders except cancelled, as of %s",
               "cols": ["Client", "IDNO", "Orders", "Amount, MDL", "Paid, MDL", "Debt, MDL", "Last order"],
               "total": "Total"}},
    "funnel": {
        "ru": {"title": "Воронка сделок", "sub": "Сделки по этапам на %s",
               "cols": ["Этап", "Сделок", "Сумма, MDL", "Средний чек, MDL", "Ближайшее закрытие"], "total": "Итого"},
        "ro": {"title": "Pilnia ofertelor", "sub": "Ofertele pe etape la %s",
               "cols": ["Etapa", "Oferte", "Suma, MDL", "Medie, MDL", "Cea mai apropiata inchidere"], "total": "Total"},
        "en": {"title": "Sales funnel", "sub": "Deals by stage as of %s",
               "cols": ["Stage", "Deals", "Amount, MDL", "Average, MDL", "Nearest close"], "total": "Total"}},
    "stock": {
        "ru": {"title": "Остатки номенклатуры", "sub": "Товары и изделия (услуги не имеют остатка) на %s",
               "cols": ["Код", "Наименование", "Вид", "Ед.", "Цена, MDL", "Остаток", "Стоимость, MDL"], "total": "Итого"},
        "ro": {"title": "Stocul nomenclatorului", "sub": "Marfuri si produse (serviciile nu au stoc) la %s",
               "cols": ["Cod", "Denumire", "Tip", "U.M.", "Pret, MDL", "Stoc", "Valoare, MDL"], "total": "Total"},
        "en": {"title": "Stock", "sub": "Goods and products (services have no stock) as of %s",
               "cols": ["Code", "Name", "Kind", "Unit", "Price, MDL", "Stock", "Value, MDL"], "total": "Total"}},
    "by_person": {
        "ru": {"title": "По сотрудникам", "sub": "Проекты и задачи по ответственным на %s",
               "cols": ["Сотрудник", "Проектов", "Бюджет, MDL", "Получено, MDL", "Долг, MDL",
                        "Задач", "Готово", "Просрочено", "Часы план", "Часы факт"], "total": "ИТОГО"},
        "ro": {"title": "Pe angajati", "sub": "Proiecte si sarcini pe responsabili la %s",
               "cols": ["Angajat", "Proiecte", "Buget, MDL", "Incasat, MDL", "Datorie, MDL",
                        "Sarcini", "Gata", "Intirziate", "Ore plan", "Ore fapt"], "total": "TOTAL"},
        "en": {"title": "By employee", "sub": "Projects and tasks by owner as of %s",
               "cols": ["Employee", "Projects", "Budget, MDL", "Received, MDL", "Debt, MDL",
                        "Tasks", "Done", "Overdue", "Hours plan", "Hours fact"], "total": "TOTAL"}},
    "projects": {
        "ru": {"title": "Проекты", "sub": "Состояние на %s. Долг = бюджет − аванс − оплата (для незакрытых и не проигранных).",
               "cols": ["Проект", "Клиент", "Этап", "Тендер", "Бюджет, MDL", "Аванс, %", "Аванс, MDL", "Оплачено, MDL",
                        "Долг, MDL", "Задач", "Готово", "Просрочено", "Сдача"], "total": "Итого"},
        "ro": {"title": "Proiecte", "sub": "Starea la %s. Datoria = buget − avans − plata (proiecte neinchise, nepierdute).",
               "cols": ["Proiect", "Client", "Etapa", "Licitatie", "Buget, MDL", "Avans, %", "Avans, MDL", "Platit, MDL",
                        "Datorie, MDL", "Sarcini", "Gata", "Intirziate", "Predare"], "total": "Total"},
        "en": {"title": "Projects", "sub": "As of %s. Debt = budget − advance − paid (open, not lost).",
               "cols": ["Project", "Client", "Stage", "Tender", "Budget, MDL", "Advance, %", "Advance, MDL", "Paid, MDL",
                        "Debt, MDL", "Tasks", "Done", "Overdue", "Delivery"], "total": "Total"}},
}


def _t(slug: str, lang: str) -> Dict[str, Any]:
    return _T[slug].get(lang) or _T[slug]["ro"]


def _f(v: Any) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def persons(data: CrmData) -> List[str]:
    """RO: cine poate fi ales in raport: responsabilii de proiecte si executantii
    de sarcini care chiar apar in date (nu tot personalul)."""
    tw, tp = data.t.where(), data.t.params()
    rows = data.rows(
        "SELECT DISTINCT TRIM(t.MANAGER) P FROM CRM_PROJECT t WHERE %s AND TRIM(t.MANAGER) IS NOT NULL "
        "UNION SELECT DISTINCT TRIM(t.ASSIGNEE) FROM CRM_TASK t WHERE %s AND TRIM(t.ASSIGNEE) IS NOT NULL "
        "ORDER BY 1" % (tw, tw), dict(tp))
    return [r["p"] for r in rows if (r.get("p") or "").strip()]


def build(data: CrmData, slug: str, lang: str = "ro", person: str = "") -> Dict[str, Any]:
    """RO: `person` — raportul pe o singura persoana; gol = pe toti, cu total."""
    if slug not in SLUGS:
        raise KeyError("raport necunoscut: %s" % slug)
    t = _t(slug, lang)
    today = date.today().isoformat()
    who = (person or "").strip()
    out: Dict[str, Any] = {"slug": slug, "title": t["title"],
                           "subtitle": (t["sub"] % today) + (" | %s" % who if who else ""),
                           "columns": t["cols"], "rows": [], "totals": [], "person": who}
    tw, tp = data.t.where(), data.t.params()

    if slug == "process":
        cnt = over = 0
        tot = 0.0
        for s in process.STAGES:
            i = data.stage_info(s)
            out["rows"].append([i["title"], i["hint"], i["count"], i["sum"],
                                i["overdue"] or "", i["overdue_sum"] if i["overdue"] else ""])
            if i["table"] == "orders":
                cnt += i["count"]
                over += i["overdue"]
                tot += i["sum"]
        out["totals"] = [t["total"], "", cnt, tot, over, ""]

    elif slug == "receivables":
        rows = data.rows(
            "SELECT t.DOC_NO, NVL(c.NAME,'-') AS CLIENT, TO_CHAR(t.SHIP_DATE,'YYYY-MM-DD') SHIP, "
            "TO_CHAR(t.DUE_DATE,'YYYY-MM-DD') DUE, NVL(t.TOTAL,0) TOTAL, NVL(t.PAID,0) PAID, "
            "TRUNC(SYSDATE) - t.DUE_DATE AS OVERDUE FROM CRM_ORDER t LEFT JOIN CRM_CLIENT c ON c.ID = t.CLIENT_ID "
            "WHERE %s AND t.STATUS <> :cancel AND t.SHIP_DATE IS NOT NULL AND NVL(t.PAID,0) < NVL(t.TOTAL,0) "
            "ORDER BY OVERDUE DESC NULLS LAST, t.TOTAL DESC" % tw, dict(tp, cancel="Отменён"))
        s = 0.0
        for r in rows:
            debt = _f(r["total"]) - _f(r["paid"])
            s += debt
            days = int(_f(r.get("overdue"))) if r.get("due") else 0
            out["rows"].append([r["doc_no"], r["client"], r.get("ship") or "", r.get("due") or "",
                                _f(r["total"]), _f(r["paid"]), debt, days if days > 0 else ""])
        out["totals"] = [t["total"], "%d" % len(rows), "", "", "", "", s, ""]

    elif slug == "sales_by_client":
        rows = data.rows(
            "SELECT NVL(c.NAME,'(-)') AS CLIENT, NVL(c.IDNO,' ') AS IDNO, COUNT(t.ID) CNT, NVL(SUM(t.TOTAL),0) TOTAL, "
            "NVL(SUM(t.PAID),0) PAID, TO_CHAR(MAX(t.ORDER_DATE),'YYYY-MM-DD') LAST_DATE "
            "FROM CRM_ORDER t LEFT JOIN CRM_CLIENT c ON c.ID = t.CLIENT_ID WHERE %s AND t.STATUS <> :cancel "
            "GROUP BY t.CLIENT_ID, c.NAME, c.IDNO ORDER BY TOTAL DESC" % tw, dict(tp, cancel="Отменён"))
        s = p = 0.0
        for r in rows:
            s += _f(r["total"])
            p += _f(r["paid"])
            out["rows"].append([r["client"], (r["idno"] or "").strip(), int(r["cnt"]), _f(r["total"]), _f(r["paid"]),
                                _f(r["total"]) - _f(r["paid"]), r.get("last_date") or ""])
        out["totals"] = [t["total"], "", len(rows), s, p, s - p, ""]

    elif slug == "funnel":
        rows = data.rows(
            "SELECT t.STAGE, COUNT(*) CNT, NVL(SUM(t.AMOUNT),0) TOTAL, TO_CHAR(MIN(t.CLOSE_DATE),'YYYY-MM-DD') NEAREST "
            "FROM CRM_DEAL t WHERE %s GROUP BY t.STAGE ORDER BY TOTAL DESC" % tw, tp)
        s, n = 0.0, 0
        for r in rows:
            c = int(r["cnt"])
            s += _f(r["total"])
            n += c
            out["rows"].append([r["stage"], c, _f(r["total"]), _f(r["total"]) / max(1, c), r.get("nearest") or ""])
        out["totals"] = [t["total"], n, s, s / max(1, n), ""]

    elif slug == "stock":
        rows = data.rows(
            "SELECT t.CODE, t.NAME, t.KIND, t.UNIT_, NVL(t.PRICE,0) PRICE, NVL(t.STOCK,0) STOCK, "
            "NVL(t.PRICE,0) * NVL(t.STOCK,0) VAL FROM CRM_ITEM t WHERE %s AND NVL(t.KIND,' ') <> :svc "
            "ORDER BY VAL DESC, t.NAME" % tw, dict(tp, svc="Услуга"))
        s = 0.0
        for r in rows:
            s += _f(r["val"])
            out["rows"].append([r.get("code") or "", r["name"], r.get("kind") or "", r.get("unit_") or "",
                                _f(r["price"]), _f(r["stock"]), _f(r["val"])])
        out["totals"] = [t["total"], "%d" % len(rows), "", "", "", "", s]

    elif slug == "projects":
        rows = data.rows(
            "SELECT t.ID, t.NAME, NVL(c.NAME,'-') AS CLIENT, t.STATUS, NVL(t.TENDER_NO,' ') TENDER, NVL(t.BUDGET,0) BUDGET, "
            "NVL(t.PREPAY_PCT,0) PCT, NVL(t.PREPAID,0) PREPAID, NVL(t.PAID,0) PAID, TO_CHAR(t.DUE_DATE,'YYYY-MM-DD') DUE "
            "FROM CRM_PROJECT t LEFT JOIN CRM_CLIENT c ON c.ID = t.CLIENT_ID WHERE %s%s "
            "ORDER BY CASE t.STATUS WHEN :closed THEN 2 WHEN :lost THEN 3 ELSE 1 END, t.DUE_DATE"
            % (tw, " AND TRIM(t.MANAGER) = :who" if who else ""),
            dict(tp, closed="Закрыт", lost="Проигран", **({"who": who} if who else {})))
        sb = sp = sd = 0.0
        over_all = 0
        for r in rows:
            st = r.get("status") or ""
            b, pre, pd = _f(r["budget"]), _f(r["prepaid"]), _f(r["paid"])
            debt = 0.0 if st in ("Закрыт", "Проигран") else max(0.0, b - pre - pd)
            sm = data.project_summary(int(r["id"]))
            out["rows"].append([r["name"], r["client"], st, (r["tender"] or "").strip(), b, int(round(_f(r["pct"]))),
                                pre, pd, debt if debt > 0 else "", sm["total"], sm["done"],
                                sm["overdue"] or "", r.get("due") or ""])
            if st != "Проигран":
                sb += b
                sp += pre + pd
                sd += debt
            over_all += sm["overdue"]
        out["totals"] = [t["total"], "%d" % len(rows), "", "", sb, "", "", sp, sd, "", "", over_all, ""]
    elif slug == "by_person":
        # RO: doua surse cu responsabil: proiectele (MANAGER) si sarcinile
        #     (ASSIGNEE). Le unim pe nume si adaugam rindul de total, ca sa se
        #     poata citi si «pe o persoana», si «pe toti».
        pw = " AND TRIM(t.MANAGER) = :who" if who else ""
        proj = data.rows(
            "SELECT TRIM(t.MANAGER) P, COUNT(*) N, NVL(SUM(t.BUDGET),0) B, "
            "NVL(SUM(NVL(t.PREPAID,0) + NVL(t.PAID,0)),0) GOT, "
            "NVL(SUM(CASE WHEN t.STATUS IN (:closed, :lost) THEN 0 "
            "     ELSE GREATEST(NVL(t.BUDGET,0) - NVL(t.PREPAID,0) - NVL(t.PAID,0), 0) END),0) DEBT "
            "FROM CRM_PROJECT t WHERE %s AND TRIM(t.MANAGER) IS NOT NULL%s "
            "GROUP BY TRIM(t.MANAGER)" % (tw, pw),
            dict(tp, closed="Закрыт", lost="Проигран", **({"who": who} if who else {})))
        tw2 = " AND TRIM(t.ASSIGNEE) = :who" if who else ""
        task = data.rows(
            "SELECT TRIM(t.ASSIGNEE) P, COUNT(*) N, SUM(CASE WHEN t.DONE = 1 THEN 1 ELSE 0 END) D, "
            "SUM(CASE WHEN t.DONE = 0 AND t.DUE_AT IS NOT NULL AND t.DUE_AT < TRUNC(SYSDATE) THEN 1 ELSE 0 END) O, "
            "NVL(SUM(t.HOURS_PLAN),0) HP, NVL(SUM(t.HOURS_FACT),0) HF "
            "FROM CRM_TASK t WHERE %s AND TRIM(t.ASSIGNEE) IS NOT NULL%s "
            "GROUP BY TRIM(t.ASSIGNEE)" % (tw, tw2),
            dict(tp, **({"who": who} if who else {})))
        agg: Dict[str, Dict[str, float]] = {}
        for r in proj:
            a = agg.setdefault(r["p"], {})
            a.update(projects=int(r["n"] or 0), budget=_f(r["b"]), got=_f(r["got"]), debt=_f(r["debt"]))
        for r in task:
            a = agg.setdefault(r["p"], {})
            a.update(tasks=int(r["n"] or 0), done=int(r["d"] or 0), over=int(r["o"] or 0),
                     hp=_f(r["hp"]), hf=_f(r["hf"]))
        tot = {k: 0.0 for k in ("projects", "budget", "got", "debt", "tasks", "done", "over", "hp", "hf")}
        for name in sorted(agg):
            a = agg[name]
            row = [name, int(a.get("projects", 0)), a.get("budget", 0.0), a.get("got", 0.0), a.get("debt", 0.0),
                   int(a.get("tasks", 0)), int(a.get("done", 0)), int(a.get("over", 0)) or "",
                   a.get("hp", 0.0), a.get("hf", 0.0)]
            out["rows"].append(row)
            for k in tot:
                tot[k] += a.get(k, 0) or 0
        out["totals"] = [t["total"], int(tot["projects"]), tot["budget"], tot["got"], tot["debt"],
                         int(tot["tasks"]), int(tot["done"]), int(tot["over"]) or "", tot["hp"], tot["hf"]]
    return out



def to_csv(rep: Dict[str, Any]) -> str:
    """RO: CSV cu ; (Excel din RM), BOM UTF-8 pentru diacritice/chirilica."""
    def cell(v: Any) -> str:
        if isinstance(v, float):
            return ("%.2f" % v).replace(".", ",")
        return '"%s"' % str(v).replace('"', '""') if isinstance(v, str) and (";" in v or '"' in v) else str(v)
    lines: List[str] = [rep["title"], rep["subtitle"], ";".join(rep["columns"])]
    lines += [";".join(cell(v) for v in row) for row in rep["rows"]]
    if rep.get("totals"):
        lines.append(";".join(cell(v) for v in rep["totals"]))
    return "﻿" + "\n".join(lines) + "\n"
