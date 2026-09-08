"""DML-testul procesului — portul lui RunDmlTest (uTestData.pas) pe Oracle.

RO: pentru fiecare entitate INSERT → SELECT → LIST → UPDATE → SELECT →
DELETE → COUNT, plus specificul: dedup clienti dupa IDNO, conversia
leadului, liniile comenzii + total + contare (vinzare −stoc, productie
+stoc, serviciu 0, a doua contare refuzata), sarcini (Готово <=> done),
proiecte (sumar), etapele (plitele nevide pe demo), doua (mutare) si cele
6 rapoarte. Ruleaza pe un chirias de test si lasa baza cum a gasit-o.
EN: DML self-test mirroring the prototype's RunDmlTest.
"""
from __future__ import annotations

from typing import Any, Dict, List

from modules.crm import process, reports
from modules.crm.entities import entity
from modules.crm.store_process import CrmData


def cleanup(data: CrmData) -> None:
    """RO: chiriasul tehnic porneste gol si ramine gol (si dupa un test intrerupt)."""
    for tbl in ("CRM_TASK", "CRM_ORDER", "CRM_PROJECT", "CRM_DEAL", "CRM_LEAD", "CRM_CONTACT",
                "CRM_ITEM", "CRM_CLIENT", "CRM_EVENT_LOG"):
        data.dml("DELETE FROM %s t WHERE %s" % (tbl, data.t.where()), data.t.params())


def run(data: CrmData) -> Dict[str, Any]:
    log: List[str] = []
    fails = 0
    cleanup(data)

    def check(cond: bool, what: str) -> None:
        nonlocal fails
        log.append(("[OK]   " if cond else "[FAIL] ") + what)
        if not cond:
            fails += 1

    def crud(key: str, name_field: str, ins: Dict[str, Any], upd: Dict[str, Any]) -> None:
        tbl = entity(key).table
        n0 = data.count(tbl)
        rid = data.insert(key, ins)
        check(rid > 0, "%s: INSERT -> id %d" % (key, rid))
        check(data.count(tbl) == n0 + 1, "%s: COUNT dupa INSERT = %d" % (key, n0 + 1))
        row = data.get(key, rid)
        check(bool(row) and row.get(name_field) == ins[name_field], "%s: SELECT dupa id intoarce valorile inserate" % key)
        check(len(data.list(key, q=ins[name_field])) >= 1, "%s: LIST cu filtru gaseste inregistrarea" % key)
        data.update(key, rid, upd)
        row = data.get(key, rid)
        check(bool(row) and row.get(name_field) == upd[name_field], "%s: UPDATE -> SELECT vede valorile noi" % key)
        data.delete(key, rid)
        check(data.get(key, rid) is None, "%s: DELETE -> SELECT dupa id e gol" % key)
        check(data.count(tbl) == n0, "%s: COUNT dupa DELETE revine la %d" % (key, n0))

    # ── clienti: dedup dupa IDNO ──
    idno = "1099900012345"
    n = data.count("CRM_CLIENT")
    cid = data.next_id("CRM_CLIENT")
    data.dml("INSERT INTO CRM_CLIENT (ID, IDNO, NAME, OWNER_KIND, OWNER_ID) VALUES (:id, :i, :n, :ok, :oi)",
             dict(data.t.params(), id=cid, i=idno, n="DML-TEST S.R.L."))
    check(data.count("CRM_CLIENT") == n + 1, "clients: INSERT +1")
    dup_msg = ""
    try:
        data.dml("INSERT INTO CRM_CLIENT (ID, IDNO, NAME, OWNER_KIND, OWNER_ID) VALUES (:id, :i, :n, :ok, :oi)",
                 dict(data.t.params(), id=data.next_id("CRM_CLIENT"), i=idno, n="DML-TEST S.R.L. (dup)"))
    except RuntimeError as e:
        dup_msg = str(e)
    check("ORA-00001" in dup_msg, "clients: al doilea INSERT cu acelasi IDNO e refuzat (UQ_CRM_CLIENT_IDNO)")
    check(data.count("CRM_CLIENT") == n + 1, "clients: COUNT ramine +1 (deduplicare dupa IDNO)")

    # ── contacte, leaduri + conversie ──
    crud("contacts", "name", {"name": "Тест Контактов", "client_id": cid, "position": "Бухгалтер", "phone": "+373 69 1", "email": "a@b.md"},
         {"name": "Тест Контактов (изм.)", "position": "Директор"})
    crud("leads", "name", {"name": "Лид Тестовый", "company": "Test Lead Co", "status": "Новый", "source": "Сайт"},
         {"name": "Лид Тестовый (изм.)", "status": "В работе", "source": "Звонок"})
    lead = data.insert("leads", {"name": "Конверт Лид", "company": "Convert Co SRL", "status": "В работе",
                                 "source": "Выставка", "phone": "+373 79 000-001", "email": "c@convert.md"})
    n = data.count("CRM_CLIENT")
    msg, new_cid = data.convert_lead(lead)
    check(new_cid > 0 and data.count("CRM_CLIENT") == n + 1, "leads: ConvertLead creeaza clientul (%s)" % msg)
    check((data.get("leads", lead) or {}).get("status") == "Конвертирован", "leads: statusul devine «Конвертирован»")
    msg2, _ = data.convert_lead(lead)
    check("уже" in msg2, "leads: a doua conversie e refuzata")
    data.delete("leads", lead)
    data.dml("DELETE FROM CRM_CLIENT WHERE ID = :c", {"c": new_cid})

    # ── oferte, nomenclator ──
    crud("deals", "title", {"title": "Сделка DML", "client_id": cid, "stage": "Новая", "amount": 1000, "close_date": "2026-12-31"},
         {"title": "Сделка DML (изм.)", "stage": "Переговоры", "amount": 2000})
    crud("items", "name", {"code": "DML-1", "name": "Товар DML", "kind": "Товар", "unit_": "шт", "price": 10, "stock": 5},
         {"name": "Товар DML (изм.)", "price": 12})

    # ── comenzi: linii, total, contare ──
    goods = data.insert("items", {"code": "DML-G", "name": "Товар для проводки", "kind": "Товар", "unit_": "шт", "price": 100, "stock": 10})
    prod = data.insert("items", {"code": "DML-P", "name": "Изделие для проводки", "kind": "Изделие", "unit_": "шт", "price": 500, "stock": 0})
    svc = data.insert("items", {"code": "DML-S", "name": "Услуга для проводки", "kind": "Услуга", "unit_": "час", "price": 50, "stock": 0})
    order = data.insert("orders", {"number": "DML-1", "client_id": cid, "kind": "Продажа", "status": "Черновик"})
    data.add_order_line(order, goods, 3, 100)
    data.add_order_line(order, svc, 2, 50)
    check(len(data.order_lines(order)) == 2, "orders: 2 linii adaugate")
    check(abs(float((data.get("orders", order) or {}).get("total") or 0) - 400) < 0.01, "orders: TOTAL = 3*100 + 2*50 = 400")
    check("только" in data.post_order(order), "orders: contarea in «Черновик» e refuzata")
    data.update("orders", order, {"status": "Выполнен"})
    check("списано" in data.post_order(order), "orders: vinzare -> «списано со склада»")
    check(abs(float((data.get("items", goods) or {}).get("stock") or 0) - 7) < 0.001, "items: stocul marfii 10 -> 7 dupa contare")
    check("уже" in data.post_order(order), "orders: a doua contare e refuzata")
    porder = data.insert("orders", {"number": "DML-2", "kind": "Производство", "status": "Оплачен"})
    data.add_order_line(porder, prod, 4, 500)
    check("оприходовано" in data.post_order(porder), "orders: productie -> «оприходовано»")
    check(abs(float((data.get("items", prod) or {}).get("stock") or 0) - 4) < 0.001, "items: stocul produsului 0 -> 4")
    sorder = data.insert("orders", {"number": "DML-3", "kind": "Услуга", "status": "Выполнен"})
    data.add_order_line(sorder, svc, 1, 50)
    check("услуги" in data.post_order(sorder), "orders: serviciu -> stocul neschimbat")
    lines = data.order_lines(order)
    data.delete_order_line(int(lines[0]["id"]))
    check(abs(float((data.get("orders", order) or {}).get("total") or 0) - 100) < 0.01, "orders: dupa stergerea liniei TOTAL = 100")
    for o in (order, porder, sorder):
        data.delete("orders", o)
    check(not data.rows("SELECT ID FROM CRM_ORDER_LINE WHERE ORDER_ID IN (:a, :b, :c)",
                        {"a": order, "b": porder, "c": sorder}),
          "orders: liniile pleaca odata cu comanda (ON DELETE CASCADE)")
    for it in (goods, prod, svc):
        data.delete("items", it)

    # ── sarcini: Готово <=> done ──
    task = data.insert("tasks", {"subject": "Задача DML", "due_at": "2026-01-01", "stage": "Новая"})
    data.set_task_done(task, True)
    row = data.get("tasks", task) or {}
    check(row.get("done") == 1 and row.get("stage") == "Готово", "tasks: SetTaskDone(True) -> done=1, stage=«Готово»")
    data.set_task_done(task, False)
    row = data.get("tasks", task) or {}
    check(row.get("done") == 0 and row.get("stage") == "В работе", "tasks: SetTaskDone(False) -> done=0, stage=«В работе»")
    data.update("tasks", task, {"stage": "Готово"})
    check((data.get("tasks", task) or {}).get("done") == 1, "tasks: UPDATE stage=«Готово» -> done=1")
    data.delete("tasks", task)

    # ── proiecte: sumar si stergere in cascada ──
    proj = data.insert("projects", {"name": "Проект DML", "client_id": cid, "kind": "Реклама", "status": "Договор",
                                    "budget": 1000, "due_date": "2026-12-31"})
    t1 = data.insert("tasks", {"subject": "Шаг 1", "project_id": proj, "stage": "Готово", "due_at": "2026-01-01", "hours_plan": 4, "hours_fact": 5})
    t2 = data.insert("tasks", {"subject": "Шаг 2", "project_id": proj, "stage": "В работе", "due_at": "2020-01-01", "hours_plan": 8})
    sm = data.project_summary(proj)
    check(sm["total"] == 2 and sm["done"] == 1 and sm["overdue"] == 1 and sm["progress"] == 50,
          "projects: sumar 2 sarcini / 1 gata / 1 intirziata / 50 %")
    data.delete("projects", proj)
    check(data.get("tasks", t1) is None and data.get("tasks", t2) is None, "projects: sarcinile pleaca cu proiectul")
    crud("projects", "name", {"name": "Проект DML 2", "kind": "Другое", "status": "Тендер", "due_date": "2026-12-31"},
         {"name": "Проект DML 2 (изм.)", "status": "Договор"})

    # ── etape, doua, rapoarte (pe datele chiriasului) ──
    stages = data.stages()
    check(len(stages) == 8, "workspace: 8 etape")
    for kind in process.BOARDS:
        b = data.board(kind)
        check(len(b["columns"]) == len(process.board_columns(kind)), "board %s: %d coloane" % (kind, len(b["columns"])))
    deal = data.insert("deals", {"title": "Сделка для доски", "stage": "Новая"})
    data.move_card("deals", deal, 3)
    check((data.get("deals", deal) or {}).get("stage") == "Выиграна", "board deals: mutarea in coloana 3 -> «Выиграна»")
    data.delete("deals", deal)
    for slug in reports.SLUGS:
        rep = reports.build(data, slug, "ro")
        check(len(rep["columns"]) > 0 and isinstance(rep["rows"], list), "report %s: se construieste (%d rinduri)" % (slug, len(rep["rows"])))
    data.dml("DELETE FROM CRM_CLIENT WHERE ID = :c", {"c": cid})
    return {"ok": fails == 0, "fails": fails, "log": log}
