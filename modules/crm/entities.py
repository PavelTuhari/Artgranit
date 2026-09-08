"""Descrierile entitatilor CRM — portul lui `InitDefs` din uCrmData.pas.

RO: o tabela = o descriere; paginile web si API-ul se construiesc din ele,
deci un sectiune noua = o descriere noua, nu un ecran nou (regula
prototipului). Valorile enumerarilor sint CANONICE (in rusa, ca in
prototip) si se scriu asa in baza; traducerea e pozitionala, in lang.json.
`name` = numele din prototip (API/JSON), `col` = coloana Oracle (difera
doar acolo unde Oracle nu permite numele: number, sum, position).
EN: entity metadata (fields, enums, lookups) mirroring the Delphi prototype.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ── enumerari canonice (uCrmData.pas:146-161) ─────────────────────────────
ENUMS: Dict[str, List[str]] = {
    "client_type":    ["Клиент", "Поставщик", "Партнёр"],
    "project_kind":   ["Реклама", "Гравировка", "Сувениры", "Монтаж", "Другое"],
    "project_status": ["Тендер", "Договор", "Аванс", "Дизайн", "Производство",
                       "Сдача", "Оплата", "Закрыт", "Проигран"],
    "task_stage":     ["Новая", "В работе", "Ожидание", "Проверка", "Готово"],
    "task_priority":  ["Низкий", "Обычный", "Высокий", "Срочно"],
    "lead_status":    ["Новый", "В работе", "Конвертирован", "Отказ"],
    "lead_source":    ["Сайт", "Звонок", "Рекомендация", "Выставка", "Реклама", "Другое"],
    "deal_stage":     ["Новая", "Предложение", "Переговоры", "Выиграна", "Проиграна"],
    "item_kind":      ["Товар", "Услуга", "Изделие"],
    "unit":           ["шт", "час", "кг", "м", "м2", "л", "компл", "услуга"],
    "order_kind":     ["Продажа", "Услуга", "Производство"],
    "order_status":   ["Черновик", "Подтверждён", "В работе", "Выполнен", "Оплачен", "Отменён"],
    "task_kind":      ["Задача", "Звонок", "Встреча"],
}

# tipurile de cimp (TFieldKind)
TEXT, MEMO, NUMBER, MONEY, DATE, ENUM, BOOL, READONLY = (
    "text", "memo", "number", "money", "date", "enum", "bool", "readonly")
LOOKUP_CLIENT, LOOKUP_DEAL, LOOKUP_ITEM, LOOKUP_PROJECT = (
    "lookup_client", "lookup_deal", "lookup_item", "lookup_project")
LOOKUPS = (LOOKUP_CLIENT, LOOKUP_DEAL, LOOKUP_ITEM, LOOKUP_PROJECT)
NUMERIC = (NUMBER, MONEY)

# RO: tabela si coloana de afisare pentru fiecare lookup (LookupTable din prototip)
LOOKUP_TABLE: Dict[str, Tuple[str, str]] = {
    LOOKUP_CLIENT:  ("CRM_CLIENT", "NAME"),
    LOOKUP_DEAL:    ("CRM_DEAL", "TITLE"),
    LOOKUP_ITEM:    ("CRM_ITEM", "NAME"),
    LOOKUP_PROJECT: ("CRM_PROJECT", "NAME"),
}


@dataclass
class Field:
    name: str                       # numele din prototip / API
    caption: str                    # eticheta canonica (ru), tradusa in lang.json col.*
    kind: str
    width: int = 0                  # latimea in lista; 0 = nu se arata in lista
    required: bool = False
    enum: str = ""                  # numele listei din ENUMS
    default: str = ""               # 'today', 'today+14', valoare literala
    col: Optional[str] = None       # coloana Oracle, daca difera de name

    @property
    def column(self) -> str:
        return (self.col or self.name).upper()

    @property
    def values(self) -> List[str]:
        return ENUMS.get(self.enum, []) if self.kind == ENUM else []


@dataclass
class Entity:
    key: str                        # contacts | leads | ...
    table: str                      # CRM_CONTACT | ...
    title: str                      # canonic (ru); nav.* in lang.json
    fields: List[Field]
    order_by: str                   # coloane Oracle
    search: List[str] = field(default_factory=list)   # nume de cimpuri (API)

    def field(self, name: str) -> Optional[Field]:
        for f in self.fields:
            if f.name == name:
                return f
        return None

    def writable(self) -> List[Field]:
        return [f for f in self.fields if f.kind != READONLY]


def F(name, caption, kind, width=0, required=False, enum="", default="", col=None) -> Field:  # noqa: N802
    return Field(name, caption, kind, width, required, enum, default, col)


ENTITIES: Dict[str, Entity] = {
    "contacts": Entity("contacts", "CRM_CONTACT", "Контакты", [
        F("name", "Имя", TEXT, 220, True),
        F("client_id", "Клиент", LOOKUP_CLIENT, 240),
        F("position", "Должность", TEXT, 140, col="JOB_TITLE"),
        F("phone", "Телефон", TEXT, 120),
        F("email", "E-mail", TEXT, 160),
        F("notes", "Заметки", MEMO),
    ], "t.NAME", ["name", "phone", "email", "position"]),

    "leads": Entity("leads", "CRM_LEAD", "Лиды", [
        F("name", "Имя", TEXT, 180, True),
        F("company", "Компания", TEXT, 200),
        F("status", "Статус", ENUM, 110, True, "lead_status", "Новый"),
        F("source", "Источник", ENUM, 110, False, "lead_source", "Сайт"),
        F("phone", "Телефон", TEXT, 120),
        F("email", "E-mail", TEXT, 150),
        F("notes", "Заметки", MEMO),
    ], "t.ID DESC", ["name", "company", "phone", "email"]),

    "deals": Entity("deals", "CRM_DEAL", "Сделки", [
        F("title", "Название", TEXT, 240, True),
        F("client_id", "Клиент", LOOKUP_CLIENT, 220),
        F("stage", "Этап", ENUM, 110, True, "deal_stage", "Новая"),
        F("amount", "Сумма, MDL", MONEY, 110),
        F("close_date", "Закрытие", DATE, 100),
        F("notes", "Заметки", MEMO),
    ], "t.ID DESC", ["title"]),

    "items": Entity("items", "CRM_ITEM", "Номенклатура", [
        F("code", "Код", TEXT, 80),
        F("name", "Наименование", TEXT, 260, True),
        F("kind", "Вид", ENUM, 90, True, "item_kind", "Товар"),
        F("unit_", "Ед.", ENUM, 60, True, "unit", "шт"),
        F("price", "Цена, MDL", MONEY, 100),
        F("vat", "НДС, %", NUMBER, 70, False, "", "20"),
        F("stock", "Остаток", NUMBER, 80, False, "", "0"),
        F("notes", "Описание", MEMO),
    ], "t.NAME", ["code", "name"]),

    "orders": Entity("orders", "CRM_ORDER", "Заказы", [
        F("number", "№", TEXT, 60, True, col="DOC_NO"),
        F("order_date", "Дата", DATE, 85, True, "", "today"),
        F("client_id", "Клиент", LOOKUP_CLIENT, 190),
        F("project_id", "Проект", LOOKUP_PROJECT, 150),
        F("kind", "Вид", ENUM, 100, True, "order_kind", "Продажа"),
        F("status", "Статус", ENUM, 100, True, "order_status", "Черновик"),
        F("total", "Итого, MDL", READONLY, 90),
        F("advance", "Аванс", MONEY, 80),
        F("paid", "Оплачено", MONEY, 85),
        F("due_date", "Срок", DATE, 85, False, "", "today+14"),
        F("ship_date", "Отгружен", DATE, 85),
        F("notes", "Примечание", MEMO),
    ], "t.ID DESC", ["number"]),

    "tasks": Entity("tasks", "CRM_TASK", "Календарь", [
        F("subject", "Тема", TEXT, 220, True),
        F("project_id", "Проект", LOOKUP_PROJECT, 170),
        F("stage", "Этап", ENUM, 90, True, "task_stage", "Новая"),
        F("priority", "Приоритет", ENUM, 80, True, "task_priority", "Обычный"),
        F("assignee", "Исполнитель", TEXT, 120),
        F("kind", "Вид", ENUM, 80, True, "task_kind", "Задача"),
        F("plan_start", "Начало", DATE, 85, False, "", "today"),
        F("due_at", "Срок", DATE, 85, True, "", "today"),
        F("hours_plan", "Часы план", NUMBER, 70),
        F("hours_fact", "Часы факт", NUMBER, 70),
        F("seq", "№ в проекте", NUMBER, 60),
        F("depends_on", "После задачи №", NUMBER, 0),
        F("client_id", "Клиент", LOOKUP_CLIENT, 160),
        F("deal_id", "Сделка", LOOKUP_DEAL, 0),
        F("done", "Выполнено", BOOL, 80),
        F("notes", "Заметки", MEMO),
    ], "t.DONE, t.DUE_AT, t.SEQ", ["subject", "assignee"]),

    "projects": Entity("projects", "CRM_PROJECT", "Проекты", [
        F("name", "Проект", TEXT, 260, True),
        F("client_id", "Клиент", LOOKUP_CLIENT, 170),
        F("kind", "Вид", ENUM, 90, True, "project_kind", "Реклама"),
        F("status", "Этап", ENUM, 100, True, "project_status", "Тендер"),
        F("tender_no", "Тендер №", TEXT, 90),
        F("tender_deadline", "Срок тендера", DATE, 0),
        F("budget", "Бюджет, MDL", MONEY, 100),
        F("prepay_pct", "Аванс, %", NUMBER, 60, False, "", "0"),
        F("prepaid", "Аванс получен", MONEY, 95),
        F("paid", "Оплачено", MONEY, 90),
        F("start_date", "Начало", DATE, 85, False, "", "today"),
        F("due_date", "Сдача", DATE, 85, True, "", "today+30"),
        F("manager", "Менеджер", TEXT, 110),
        F("notes", "Описание", MEMO),
    ], "t.ID DESC", ["name", "tender_no", "manager"]),
}


def entity(key: str) -> Entity:
    if key not in ENTITIES:
        raise KeyError("entitate necunoscuta: %s" % key)
    return ENTITIES[key]


def as_json(e: Entity) -> Dict:
    """RO: descrierea pentru front (construieste lista si editorul din ea)."""
    return {
        "key": e.key, "title": e.title, "search": e.search,
        "fields": [{"name": f.name, "caption": f.caption, "kind": f.kind, "width": f.width,
                    "required": f.required, "enum": f.enum, "values": f.values,
                    "default": f.default} for f in e.fields],
    }
