"""Regulile alertelor «tranzactii nefinisate si datorii» — pure, fara baza.

RO: cerinta proprietarului (08.09.2026): «de adaugat notificari pe telegram
cu tranzactiile nefinisate si cu datorii». O «tranzactie nefinisata» = o
comanda care sta intr-o etapa in care nu ar trebui sa stea (asteapta avans,
executata dar nelivrata, livrata dar neplatita, contabilizarea nefacuta) sau
o oferta / un proiect cu termenul depasit. «Datorie» = livrat si neplatit,
sau proiect cu buget neacoperit de avans si plati.

Aici sint doar regulile: ce tipuri exista, cit de grave sint, cum se cheama
o alerta (cheia de deduplicare), cum arata textul in ro/ru/en si cind o
alerta deja trimisa se trimite din nou. Interogarile si trimiterea sint in
`notify.py`; asa regulile se pot testa fara Oracle si fara bot.
EN: pure rules for the unfinished-transaction and debt alerts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, Iterable, List, Optional

# ── tipurile de alerta ────────────────────────────────────────────────────
# RO: ordinea = ordinea in mesaj; `sev` 2 = rosu (bani sau termen depasit),
#     1 = galben (atentie), 0 = informativ.
KINDS: Dict[str, Dict[str, Any]] = {
    "debt":           {"sev": 2, "icon": "!!", "table": "orders"},    # livrat, neplatit
    "overdue_work":   {"sev": 2, "icon": "!!", "table": "orders"},    # in lucru, termen depasit
    "await_advance":  {"sev": 1, "icon": "!",  "table": "orders"},    # confirmat, fara avans
    "ready_to_ship":  {"sev": 1, "icon": "!",  "table": "orders"},    # executat, nelivrat
    "unposted":       {"sev": 1, "icon": "!",  "table": "orders"},    # executat/platit, necontabilizat
    "project_debt":   {"sev": 2, "icon": "!!", "table": "projects"},  # proiect: buget neacoperit
    "deal_stale":     {"sev": 0, "icon": "..", "table": "deals"},     # oferta cu data de inchidere trecuta
    "due_soon":       {"sev": 0, "icon": "..", "table": "orders"},    # termenul vine in N zile
}
ALL_KINDS = tuple(KINDS)

TEXTS: Dict[str, Dict[str, str]] = {
    "ro": {
        "title": "CRM %s — tranzactii nefinisate si datorii",
        "as_of": "Stare la %s",
        "nothing": "Nimic de raportat: fara datorii si fara comenzi blocate.",
        "total": "TOTAL de incasat: %s MDL (%d pozitii)",
        "more": "... si inca %d",
        "debt": "Datorie: comanda %s, %s — %s MDL neplatiti din %s%s",
        "overdue_work": "Termen depasit: comanda %s, %s — %s MDL, %s (%d zile)",
        "await_advance": "Asteapta avans: comanda %s, %s — %s MDL, confirmata pe %s",
        "ready_to_ship": "Gata de livrare, nelivrata: comanda %s, %s — %s MDL, termen %s",
        "unposted": "Necontabilizata: comanda %s, %s — %s MDL, status %s",
        "project_debt": "Proiect neacoperit: %s, %s — ramin %s MDL din %s, predare %s",
        "deal_stale": "Oferta fara miscare: %s, %s — %s MDL, inchidere planificata %s",
        "due_soon": "Termen apropiat: comanda %s, %s — %s MDL, scade pe %s (%d zile)",
        "overdue_days": ", intirziere %d zile",
    },
    "ru": {
        "title": "CRM %s — незавершённые сделки и долги",
        "as_of": "Состояние на %s",
        "nothing": "Сообщать нечего: долгов и зависших заказов нет.",
        "total": "ИТОГО к получению: %s MDL (%d позиций)",
        "more": "... и ещё %d",
        "debt": "Долг: заказ %s, %s — не оплачено %s MDL из %s%s",
        "overdue_work": "Просрочен срок: заказ %s, %s — %s MDL, %s (%d дней)",
        "await_advance": "Ожидает аванс: заказ %s, %s — %s MDL, подтверждён %s",
        "ready_to_ship": "Готов к отгрузке, не отгружен: заказ %s, %s — %s MDL, срок %s",
        "unposted": "Не проведён: заказ %s, %s — %s MDL, статус %s",
        "project_debt": "Проект не закрыт деньгами: %s, %s — осталось %s MDL из %s, сдача %s",
        "deal_stale": "Сделка без движения: %s, %s — %s MDL, плановое закрытие %s",
        "due_soon": "Близкий срок: заказ %s, %s — %s MDL, истекает %s (%d дней)",
        "overdue_days": ", просрочка %d дней",
    },
    "en": {
        "title": "CRM %s — unfinished transactions and debts",
        "as_of": "As of %s",
        "nothing": "Nothing to report: no debts, no stuck orders.",
        "total": "TOTAL receivable: %s MDL (%d items)",
        "more": "... and %d more",
        "debt": "Debt: order %s, %s — %s MDL unpaid of %s%s",
        "overdue_work": "Overdue: order %s, %s — %s MDL, %s (%d days)",
        "await_advance": "Awaiting advance: order %s, %s — %s MDL, confirmed on %s",
        "ready_to_ship": "Ready, not shipped: order %s, %s — %s MDL, due %s",
        "unposted": "Not posted: order %s, %s — %s MDL, status %s",
        "project_debt": "Project not covered: %s, %s — %s MDL left of %s, delivery %s",
        "deal_stale": "Stale deal: %s, %s — %s MDL, planned close %s",
        "due_soon": "Due soon: order %s, %s — %s MDL, due %s (%d days)",
        "overdue_days": ", %d days late",
    },
}
KIND_TITLES: Dict[str, Dict[str, str]] = {
    "ro": {"debt": "DATORII", "overdue_work": "TERMENE DEPASITE", "await_advance": "ASTEAPTA AVANS",
           "ready_to_ship": "GATA, NELIVRATE", "unposted": "NECONTABILIZATE", "project_debt": "PROIECTE NEACOPERITE",
           "deal_stale": "OFERTE FARA MISCARE", "due_soon": "TERMENE APROPIATE"},
    "ru": {"debt": "ДОЛГИ", "overdue_work": "ПРОСРОЧЕННЫЕ СРОКИ", "await_advance": "ОЖИДАЮТ АВАНС",
           "ready_to_ship": "ГОТОВЫ, НЕ ОТГРУЖЕНЫ", "unposted": "НЕ ПРОВЕДЕНЫ", "project_debt": "ПРОЕКТЫ БЕЗ ПОКРЫТИЯ",
           "deal_stale": "СДЕЛКИ БЕЗ ДВИЖЕНИЯ", "due_soon": "БЛИЖАЙШИЕ СРОКИ"},
    "en": {"debt": "DEBTS", "overdue_work": "OVERDUE", "await_advance": "AWAITING ADVANCE",
           "ready_to_ship": "READY, NOT SHIPPED", "unposted": "NOT POSTED", "project_debt": "PROJECTS UNCOVERED",
           "deal_stale": "STALE DEALS", "due_soon": "DUE SOON"},
}
# RO: doar aceste tipuri se aduna in «TOTAL de incasat» (bani pe care ii asteptam)
MONEY_KINDS = ("debt", "project_debt")
MAX_LINES_PER_KIND = 10          # in mesaj; restul se numara in «... si inca N»
TG_LIMIT = 3800                  # Telegram taie la 4096; lasam loc de coada


@dataclass
class Alert:
    kind: str
    ref_id: int
    title: str                    # numarul comenzii / denumirea proiectului sau ofertei
    client: str
    amount: float = 0.0           # suma alertei (datoria, valoarea blocata)
    total: float = 0.0            # suma documentului
    due: str = ""                 # yyyy-mm-dd
    days: int = 0                 # zile de intirziere (+) sau pina la termen (-)
    status: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> str:
        return "%s:%d" % (self.kind, self.ref_id)

    @property
    def sev(self) -> int:
        return KINDS[self.kind]["sev"]

    @property
    def table(self) -> str:
        return KINDS[self.kind]["table"]

    def as_dict(self) -> Dict[str, Any]:
        return {"kind": self.kind, "key": self.key, "ref_id": self.ref_id, "title": self.title,
                "client": self.client, "amount": self.amount, "total": self.total, "due": self.due,
                "days": self.days, "status": self.status, "sev": self.sev, "table": self.table}


def money(v: float) -> str:
    """RO: 12345.6 -> «12,345.60» (fara spatii, ca sa nu se rupa in Telegram)."""
    return "{:,.2f}".format(float(v or 0))


def days_late(due: Optional[str], today: Optional[date] = None) -> int:
    """RO: zile de intirziere fata de termen; negativ = termenul e in viitor."""
    if not due:
        return 0
    try:
        y, m, d = (int(x) for x in str(due)[:10].split("-"))
    except (ValueError, TypeError):
        return 0
    return ((today or date.today()) - date(y, m, d)).days


def enabled_kinds(cfg: Dict[str, Any]) -> List[str]:
    """RO: lista din setari (virgula) sau toate; necunoscutele se ignora."""
    raw = str(cfg.get("kinds") or "").strip()
    if not raw:
        return list(ALL_KINDS)
    want = [k.strip() for k in raw.split(",") if k.strip()]
    return [k for k in ALL_KINDS if k in want]


def should_resend(sent: Optional[Dict[str, Any]], amount: float, quiet_days: int,
                  today: Optional[date] = None) -> bool:
    """RO: aceeasi alerta se retrimite daca a trecut perioada de liniste SAU
    daca suma s-a schimbat (datoria a crescut / s-a platit partial)."""
    if not sent:
        return True
    prev = sent.get("amount")
    if prev is None or abs(float(prev) - float(amount or 0)) >= 0.01:
        return True
    last = sent.get("sent_at")
    if not last:
        return True
    return days_late(str(last)[:10], today) >= max(0, int(quiet_days or 0))


def _line(a: Alert, lang: str) -> str:
    t = TEXTS.get(lang) or TEXTS["ro"]
    icon = KINDS[a.kind]["icon"]
    if a.kind == "debt":
        tail = (t["overdue_days"] % a.days) if a.days > 0 else ""
        body = t["debt"] % (a.title, a.client, money(a.amount), money(a.total), tail)
    elif a.kind == "overdue_work":
        body = t["overdue_work"] % (a.title, a.client, money(a.total), a.due, a.days)
    elif a.kind == "await_advance":
        body = t["await_advance"] % (a.title, a.client, money(a.total), a.due or "-")
    elif a.kind == "ready_to_ship":
        body = t["ready_to_ship"] % (a.title, a.client, money(a.total), a.due or "-")
    elif a.kind == "unposted":
        body = t["unposted"] % (a.title, a.client, money(a.total), a.status)
    elif a.kind == "project_debt":
        body = t["project_debt"] % (a.title, a.client, money(a.amount), money(a.total), a.due or "-")
    elif a.kind == "deal_stale":
        body = t["deal_stale"] % (a.title, a.client, money(a.total), a.due or "-")
    else:                                                       # due_soon
        body = t["due_soon"] % (a.title, a.client, money(a.total), a.due, -a.days)
    return "%s %s" % (icon, body)


def render(alerts: Iterable[Alert], lang: str = "ro", tenant: str = "OfficePlus",
           today: Optional[date] = None, url: str = "") -> str:
    """RO: mesajul pentru Telegram — text simplu (fara parse_mode: numele
    firmelor contin `_`, `*`, `(`, iar Markdown-ul ar refuza mesajul)."""
    t = TEXTS.get(lang) or TEXTS["ro"]
    items = sorted(alerts, key=lambda a: (-a.sev, -a.amount, a.kind, a.ref_id))
    head = [t["title"] % tenant, t["as_of"] % (today or date.today()).isoformat(), ""]
    if not items:
        return "\n".join(head + [t["nothing"]])
    money_sum = sum(a.amount for a in items if a.kind in MONEY_KINDS)
    money_cnt = sum(1 for a in items if a.kind in MONEY_KINDS)
    if money_cnt:
        head.append(t["total"] % (money(money_sum), money_cnt))
        head.append("")
    body: List[str] = []
    for kind in ALL_KINDS:
        group = [a for a in items if a.kind == kind]
        if not group:
            continue
        body.append("%s (%d):" % (KIND_TITLES.get(lang, KIND_TITLES["ro"])[kind], len(group)))
        for a in group[:MAX_LINES_PER_KIND]:
            body.append("  " + _line(a, lang))
        if len(group) > MAX_LINES_PER_KIND:
            body.append("  " + t["more"] % (len(group) - MAX_LINES_PER_KIND))
        body.append("")
    text = "\n".join(head + body).rstrip()
    if url:
        text += "\n" + url
    if len(text) > TG_LIMIT:                                    # RO: taiem pe rind intreg
        cut = text[:TG_LIMIT].rsplit("\n", 1)[0]
        text = cut + "\n" + (t["more"] % max(1, len(items) - cut.count("\n")))
    return text
