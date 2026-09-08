"""Regulile procesului «de la contract la bani» — pure, fara baza de date.

RO: portul lui StageWhere / OverdueWhere (uCrmData.pas:536-579), al
coloanelor de kanban si al lui MoveBoardCard (uBoardCards.pas) pe SQL
Oracle. Fiecare functie intoarce (fragment SQL cu alias `t`, binduri) —
valorile canonice ale enumerarilor NU se scriu in textul SQL, ci se leaga
ca parametri (CL8MSWIN1251 + text chirilic = doar prin binduri).
Etapele sint 8 stari care se exclud reciproc si NU se stocheaza: se
calculeaza din cimpurile ofertei / comenzii. Schimbarea etapei pe doua are
un singur punct: `board_move_sql` (MoveBoardCard din prototip).
EN: pure SQL builders for stages, boards and board moves (Oracle dialect).
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from modules.crm.entities import ENUMS

Where = Tuple[str, Dict[str, object]]

# ── cele 8 etape (TStage) ─────────────────────────────────────────────────
STAGES: List[str] = ["deal_offer", "deal_talks", "deal_won", "await_advance",
                     "in_work", "ready_to_ship", "await_payment", "closed"]
STAGE_TABLE = {s: ("CRM_DEAL" if s.startswith("deal_") else "CRM_ORDER") for s in STAGES}
STAGE_SUM_COL = {s: ("AMOUNT" if s.startswith("deal_") else "TOTAL") for s in STAGES}
# titluri / explicatii canonice (STAGE_TITLES / STAGE_HINTS); traducerea: lang.json enums.stage_title/hint
STAGE_TITLES = ["Предложение", "Переговоры", "Готово к заказу", "Ожидает аванс",
                "В работе / производство", "Готово к отгрузке", "Отгружено — ждём оплату", "Закрыто"]
STAGE_HINTS = ["КП отправлено клиенту", "Согласование условий", "Сделка выиграна — оформить заказ",
               "Заказ подтверждён, аванс не поступил", "Аванс есть, идёт исполнение",
               "Исполнен, отгрузка не оформлена", "Отгружен, оплата не закрыта",
               "Отгружен и полностью оплачен"]

_NOT_CANCELLED = "t.STATUS <> :st_cancel AND "


def stage_where(stage: str) -> Where:
    """RO: conditia etapei (StageWhere). Aliasul `t` e obligatoriu."""
    p: Dict[str, object] = {}
    if stage == "deal_offer":
        return "t.STAGE = :st", {"st": "Предложение"}
    if stage == "deal_talks":
        return "t.STAGE = :st", {"st": "Переговоры"}
    if stage == "deal_won":
        return "t.STAGE = :st", {"st": "Выиграна"}
    p["st_cancel"] = "Отменён"
    if stage == "await_advance":
        p["st_conf"] = "Подтверждён"
        return _NOT_CANCELLED + "t.STATUS = :st_conf AND NVL(t.ADVANCE,0) <= 0", p
    if stage == "in_work":
        p.update(st_conf="Подтверждён", st_work="В работе")
        return _NOT_CANCELLED + "t.STATUS IN (:st_conf, :st_work) AND NVL(t.ADVANCE,0) > 0", p
    if stage == "ready_to_ship":
        p.update(st_done="Выполнен", st_paid="Оплачен")
        return _NOT_CANCELLED + "t.STATUS IN (:st_done, :st_paid) AND t.SHIP_DATE IS NULL", p
    if stage == "await_payment":
        return _NOT_CANCELLED + "t.SHIP_DATE IS NOT NULL AND NVL(t.PAID,0) < NVL(t.TOTAL,0)", p
    if stage == "closed":
        return _NOT_CANCELLED + "t.SHIP_DATE IS NOT NULL AND NVL(t.PAID,0) >= NVL(t.TOTAL,0)", p
    return "1=1", {}


def overdue_where(stage: str) -> Where:
    """RO: intirzie = termenul in trecut, etapa neinchisa (OverdueWhere)."""
    sql, p = stage_where(stage)
    if stage.startswith("deal_"):
        return sql + " AND t.CLOSE_DATE IS NOT NULL AND t.CLOSE_DATE < TRUNC(SYSDATE)", p
    if stage == "closed":
        return sql + " AND 1=0", p
    return sql + " AND t.DUE_DATE IS NOT NULL AND t.DUE_DATE < TRUNC(SYSDATE)", p


# ── doua (kanban) ─────────────────────────────────────────────────────────
BOARDS = ("orders", "deals", "tasks", "projects", "project_tasks")
BOARD_TABLE = {"orders": "CRM_ORDER", "deals": "CRM_DEAL", "tasks": "CRM_TASK",
               "projects": "CRM_PROJECT", "project_tasks": "CRM_TASK"}
# RO: culorile coloanelor (uBoardCards.pas:79-96) — hex pentru web
_BLUE, _AMBER, _GREEN, _VIOLET, _GRAY, _RED, _TEAL = (
    "#5589ca", "#e09b2e", "#2a9a4c", "#8a66b0", "#969696", "#ad4846", "#2b8fa2")
BOARD_COLORS = {
    "orders":        [_AMBER, _BLUE, _GREEN, _VIOLET, _GRAY],
    "deals":         [_TEAL, _BLUE, _AMBER, _GREEN, _RED],
    "tasks":         [_RED, _AMBER, _BLUE, _GREEN],
    "projects":      [_TEAL, _BLUE, _AMBER, _VIOLET, _AMBER, _GREEN, _VIOLET, _GRAY, _RED],
    "project_tasks": [_TEAL, _BLUE, _AMBER, _VIOLET, _GREEN],
}
TASK_COLS = ["Просрочено", "Сегодня", "Позже", "Выполнено"]      # kanban.task_cols


def board_columns(kind: str) -> List[str]:
    """RO: titlurile canonice ale coloanelor; front-ul le traduce pozitional."""
    if kind == "orders":
        return STAGE_TITLES[3:8]
    if kind == "deals":
        return list(ENUMS["deal_stage"])
    if kind == "projects":
        return list(ENUMS["project_status"])
    if kind == "project_tasks":
        return list(ENUMS["task_stage"])
    return list(TASK_COLS)


def board_column_where(kind: str, col: int, project_id: int = 0) -> Where:
    """RO: BoardColumnWhere — conditia unei coloane."""
    if kind == "orders":
        return stage_where(STAGES[3 + col])
    if kind == "deals":
        return "t.STAGE = :bc", {"bc": ENUMS["deal_stage"][col]}
    if kind == "projects":
        return "t.STATUS = :bc", {"bc": ENUMS["project_status"][col]}
    if kind == "project_tasks":
        sql, p = "t.STAGE = :bc", {"bc": ENUMS["task_stage"][col]}
        if project_id > 0:
            return sql + " AND t.PROJECT_ID = :bp", dict(p, bp=int(project_id))
        return sql + " AND NVL(t.PROJECT_ID,0) > 0", p
    # tasks dupa termen
    return {0: "t.DONE = 0 AND t.DUE_AT < TRUNC(SYSDATE)",
            1: "t.DONE = 0 AND t.DUE_AT = TRUNC(SYSDATE)",
            2: "t.DONE = 0 AND t.DUE_AT > TRUNC(SYSDATE)"}.get(col, "t.DONE = 1"), {}


def board_move_sql(kind: str, col: int) -> Tuple[str, Dict[str, object]]:
    """RO: MoveBoardCard — SINGURUL loc care schimba etapa de pe doua. Intoarce
    partea SET a unui UPDATE (fara WHERE) si bindurile ei. Pentru comenzi se
    pun exact cimpurile din care se calculeaza etapele (StageWhere)."""
    cols = board_columns(kind)
    if not 0 <= col < len(cols):
        raise ValueError("coloana in afara doua")
    if kind == "orders":
        if col == 0:
            return "STATUS = :s, ADVANCE = 0, PAID = 0, SHIP_DATE = NULL", {"s": "Подтверждён"}
        if col == 1:
            return ("STATUS = :s, ADVANCE = CASE WHEN NVL(ADVANCE,0) <= 0 THEN ROUND(NVL(TOTAL,0)*0.3,2) "
                    "ELSE ADVANCE END, SHIP_DATE = NULL", {"s": "В работе"})
        if col == 2:
            return "STATUS = :s, SHIP_DATE = NULL", {"s": "Выполнен"}
        if col == 3:
            return ("STATUS = :s, SHIP_DATE = NVL(SHIP_DATE, TRUNC(SYSDATE)), "
                    "PAID = CASE WHEN NVL(PAID,0) >= NVL(TOTAL,0) THEN ROUND(NVL(TOTAL,0)*0.5,2) ELSE NVL(PAID,0) END",
                    {"s": "Выполнен"})
        return ("STATUS = :s, SHIP_DATE = NVL(SHIP_DATE, TRUNC(SYSDATE)), PAID = NVL(TOTAL,0)",
                {"s": "Оплачен"})
    if kind == "deals":
        return "STAGE = :s", {"s": cols[col]}
    if kind == "projects":
        return "STATUS = :s", {"s": cols[col]}
    if kind == "project_tasks":
        # «Готово» <=> done = 1 (SetTaskStage)
        return "STAGE = :s, DONE = :d", {"s": cols[col], "d": 1 if col == len(cols) - 1 else 0}
    # tasks dupa termen: mutam termenul, ultima coloana = executat
    if col == 3:
        return "DONE = 1, STAGE = :s", {"s": "Готово"}
    due = {0: -1, 1: 0, 2: 7}[col]
    return ("DONE = 0, STAGE = CASE WHEN STAGE = :sd THEN :sw ELSE STAGE END, "
            "DUE_AT = TRUNC(SYSDATE) + :dd", {"sd": "Готово", "sw": "В работе", "dd": due})


# ── valori, validari ──────────────────────────────────────────────────────
def resolve_default(s: str) -> str:
    """RO: 'today' / 'today+N' -> data; altfel valoarea ca atare (ResolveDefault)."""
    if s.startswith("today"):
        try:
            n = int(s[5:] or 0)
        except ValueError:
            n = 0
        return (date.today() + timedelta(days=n)).isoformat()
    return s


def enum_ok(enum: str, value: Optional[str]) -> bool:
    return not enum or value in ENUMS.get(enum, [])


def post_sign(kind: Optional[str]) -> int:
    """RO: PostOrder — vinzarea scade stocul, productia il creste, serviciile 0."""
    return {"Продажа": -1, "Производство": 1}.get(kind or "", 0)


def post_allowed(status: Optional[str]) -> bool:
    return status in ("Выполнен", "Оплачен")


def done_steps_for(status: str) -> int:
    """RO: citi pasi ai proiectului sint gata la etapa data (DoneStepsFor)."""
    return {"Тендер": 0, "Договор": 1, "Аванс": 2, "Дизайн": 3, "Производство": 6,
            "Сдача": 9, "Оплата": 10, "Закрыт": 11}.get(status, 1)
