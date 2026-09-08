"""Generatorul de date demo — portul lui SeedDemo (uTestData.pas) per chirias.

RO: aceleasi firme, contacte, leaduri, oferte, nomenclator, comenzi cu
linii si contare, sarcini, proiecte cu pasi si comenzi de productie ca in
prototip, ca toate plitele tabloului de lucru sa fie nevide (AGENTS.md §1
al prototipului). Idempotent: ce exista (dupa IDNO / cod / titlu) se sare.
Contoarele se intorc ca in seed.log: clienti 17, contacte 20, leaduri 12,
oferte 22, nomenclator 21, comenzi 23 (linii 41), sarcini 24, proiecte 10
(sarcini de proiect 100).
EN: demo data generator mirroring the prototype's seed, per tenant.
"""
from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any, Dict, List

from modules.crm import process
from modules.crm.entities import ENUMS
from modules.crm.store_process import CrmData

COMPANIES = [
    ("1003600116460", "CENTRUL DE ELABORARE UNISIM-SOFT S.R.L.", "Societate cu raspundere limitata", "mun. Chisinau, str. Alba-Iulia 75/B", "TUHARI PAVEL [Administrator]", "Партнёр", "+373 22 590-100", "office@unisim.md"),
    ("1017600018242", "Societatea cu Raspundere Limitata ALFA-VIS COM", "Societate cu raspundere limitata", "mun. Chisinau, sec. Centru, str. Alecsandri Vasile, 80", "BUBIS YEVGENY [Administrator]", "Клиент", "+373 22 123-456", "office@alfa-vis.md"),
    ("1002600021871", "AGRO-PRIM S.R.L.", "Societate cu raspundere limitata", "r-l Ialoveni, s. Costesti, str. Stefan cel Mare 12", "POPESCU ION [Administrator]", "Клиент", "+373 79 111-222", "ion@agro-prim.md"),
    ("1004600045213", "MOLDTEHNICA S.A.", "Societate pe actiuni", "mun. Chisinau, bd. Dacia 49/3", "RUSU ANDREI [Director]", "Поставщик", "+373 22 771-234", "sales@moldtehnica.md"),
    ("1008600009874", "PANIFICATIE BALTI S.R.L.", "Societate cu raspundere limitata", "mun. Balti, str. Decebal 101", "CEBAN MARIA [Administrator]", "Клиент", "+373 231 22-333", "panificatie@balti.md"),
    ("1011600032557", "VINARIA CAHUL S.R.L.", "Societate cu raspundere limitata", "or. Cahul, str. Stefan cel Mare 8", "MUNTEANU VASILE [Administrator]", "Клиент", "+373 299 33-444", "export@vinaria-cahul.md"),
    ("1013600001988", "ELECTROMONTAJ-SERVICE S.R.L.", "Societate cu raspundere limitata", "mun. Chisinau, str. Uzinelor 21", "GROSU DUMITRU [Administrator]", "Поставщик", "+373 22 470-111", "info@electromontaj.md"),
    ("1015600078123", "I.I. CROITORU TATIANA", "Intreprindere individuala", "or. Orhei, str. Vasile Lupu 33", "CROITORU TATIANA [Fondator]", "Клиент", "+373 235 21-100", "tatiana.croitoru@mail.md"),
    ("1016600054321", "LOGISTIC-TRANS GRUP S.R.L.", "Societate cu raspundere limitata", "mun. Chisinau, str. Muncesti 271", "LUNGU SERGIU [Administrator]", "Партнёр", "+373 22 522-900", "dispatch@logistic-trans.md"),
    ("1018600011200", "FARM-PLUS S.R.L.", "Societate cu raspundere limitata", "mun. Chisinau, str. Ismail 98", "CIOBANU ELENA [Administrator]", "Клиент", "+373 22 210-321", "farm-plus@mail.md"),
    ("1019600093456", "METAL-CONSTRUCT S.R.L.", "Societate cu raspundere limitata", "mun. Chisinau, str. Petricani 19", "BOTNARI VICTOR [Administrator]", "Клиент", "+373 22 440-505", "office@metal-construct.md"),
    ("1020600024680", "IT-SOLUTIONS MOLDOVA S.R.L.", "Societate cu raspundere limitata", "mun. Chisinau, str. Puskin 47", "CODREANU ALEXANDRU [Administrator]", "Партнёр", "+373 22 888-777", "hello@itsolutions.md"),
    ("1021600036912", "MOBILA-DESIGN S.R.L.", "Societate cu raspundere limitata", "mun. Chisinau, str. Industriala 40", "SIRBU LILIANA [Administrator]", "Клиент", "+373 22 610-202", "sales@mobila-design.md"),
    ("1022600048135", "AUTO-SERVICE EXPRESS S.R.L.", "Societate cu raspundere limitata", "mun. Balti, str. Stefan cel Mare 180", "ROTARU IGOR [Administrator]", "Клиент", "+373 231 44-555", "service@auto-express.md"),
    ("1023600059246", "GOSPODARIA TARANEASCA SPICUL", "Gospodarie taraneasca", "r-l Cahul, s. Manta", "BURLACU PETRU [Fondator]", "Клиент", "+373 299 55-666", ""),
]
PARTNERS = [
    ("1010600044123", "GRAVURA.MD S.R.L.", "Societate cu raspundere limitata", "mun. Chisinau, str. Uzinelor 19", "ROSCA DENIS [Administrator]", "Партнёр", "+373 22 000-111", "office@gravura.md"),
    ("1009600037654", "BM PUBLIC S.R.L.", "Societate cu raspundere limitata", "mun. Chisinau, str. Calea Iesilor 10", "BOTNARI MARIN [Administrator]", "Партнёр", "+373 22 000-222", "office@bmpublic.md"),
]
CONTACT_NAMES = ["Ion Popescu", "Maria Ceban", "Andrei Rusu", "Elena Ciobanu", "Victor Botnari", "Liliana Sirbu",
                 "Igor Rotaru", "Alexandru Codreanu", "Tatiana Croitoru", "Sergiu Lungu", "Dumitru Grosu",
                 "Vasile Munteanu", "Natalia Gutu", "Oleg Turcanu", "Ana Moraru", "Pavel Tuhari"]
POSITIONS = ["Директор", "Главный бухгалтер", "Менеджер по закупкам", "Технический директор", "Логист", "Коммерческий директор"]
LEAD_COMPANIES = ["Brutaria Codru SRL", "Ferma Eco-Lapte", "Salon Auto Nord", "Clinica Dental-Plus", "Hotel Nistru",
                  "Tipografia Grafic-Art", "Pescaria Dunarea", "Apicultura Moldova", "Scoala de soferi Start",
                  "Cafeneaua Tucano", "Atelier Textil Lux", "Serviciul IT Nord"]
LEAD_PERSONS = ["Radu Cojocaru", "Diana Bejan", "Mihai Ursu", "Cristina Postolachi", "Valeriu Chirila", "Irina Frunza",
                "Grigore Tibirna", "Svetlana Rosca", "Nicolae Damian", "Olga Cazacu", "Eugen Bivol", "Larisa Stratan"]
ITEMS = [
    ("T-001", "Насос дозирующий ND-25", "Товар", "шт", 12500, 5), ("T-002", "Фильтр тонкой очистки FT-10", "Товар", "шт", 840, 40),
    ("T-003", "Труба ПВХ 50 мм", "Товар", "м", 95, 320), ("T-004", "Кабель ВВГ 3x2.5", "Товар", "м", 38, 900),
    ("T-005", "Контроллер PLC-200", "Товар", "шт", 6900, 4), ("T-006", "Датчик уровня LS-3", "Товар", "шт", 1450, 12),
    ("T-007", "Мука пшеничная в/с", "Товар", "кг", 9.5, 2500), ("T-008", "Масло подсолнечное рафин.", "Товар", "л", 31, 600),
    ("S-001", "Монтаж и пусконаладка", "Услуга", "час", 350, 0), ("S-002", "Сервисное обслуживание (выезд)", "Услуга", "услуга", 900, 0),
    ("S-003", "Проектирование", "Услуга", "час", 500, 0), ("S-004", "Доставка по Кишинёву", "Услуга", "услуга", 250, 0),
    ("S-005", "Консультация бухгалтера", "Услуга", "час", 400, 0), ("P-001", "Установка дозирования УД-1", "Изделие", "компл", 42000, 0),
    ("P-002", "Шкаф управления ШУ-2", "Изделие", "шт", 18500, 1), ("P-003", "Хлеб «Домашний» 0,6 кг", "Изделие", "шт", 14, 0),
    ("P-004", "Стол офисный СО-120", "Изделие", "шт", 3200, 3), ("P-005", "Ворота металлические 3x2", "Изделие", "компл", 15800, 0),
]
DEAL_TITLES = ["Поставка дозирующей установки", "Автоматизация линии розлива", "Шкафы управления для цеха",
               "Сервисный контракт на год", "Мебель для офиса", "Ворота и ограждение склада",
               "Хлебопекарная линия — модернизация", "Проект электроснабжения", "Поставка кабеля и щитов",
               "Консалтинг по учёту", "Доставка продукции сетям", "Датчики уровня для резервуаров"]
TASK_SUBJECTS = ["Позвонить по оплате заказа", "Отправить коммерческое предложение", "Встреча: согласование ТЗ",
                 "Выезд на объект — замеры", "Согласовать график поставки", "Подготовить договор",
                 "Напомнить об акте выполненных работ", "Презентация продукции", "Уточнить реквизиты", "Контроль отгрузки"]
PROJECTS = [
    ("Панно с логотипом на стену 3x1,5 м (акрил, подсветка)", 11, "Реклама", "Производство", "T-2026-014", 48000, 50, -20, 10, "Ion Popescu", "Тендер IT-Solutions: панно в холле офиса. Производство — партнёр BM PUBLIC."),
    ("Таблички с выжигом поздравлений, дуб, 200 шт. (юбилей)", 3, "Гравировка", "Дизайн", "T-2026-021", 36000, 0, -7, 21, "Maria Ceban", "Без аванса: по условиям тендера оплата после сдачи. Выжиг и лазер — партнёр GRAVURA.MD."),
    ("Гравировка подарочных ручек и ежедневников, 500 шт.", 5, "Сувениры", "Закрыт", "", 22500, 30, -60, -25, "Ion Popescu", "Без тендера, прямой заказ. Сдан и оплачен полностью."),
    ("Световой короб на фасад магазина 4x1 м", 12, "Реклама", "Проигран", "T-2026-009", 61000, 40, -30, 5, "Ion Popescu", "Тендер проигран по цене — заявка сохранена для следующего раза."),
    ("Брендирование автомобиля доставки (плёнка, логотип)", 4, "Реклама", "Аванс", "T-2026-027", 18900, 50, -3, 14, "Ion Popescu", "Договор подписан, ждём аванс 50 % — работы начнутся после поступления."),
    ("Деревянные медали с гравировкой для марафона, 1 200 шт.", 9, "Сувениры", "Оплата", "T-2026-016", 54000, 30, -35, -2, "Maria Ceban", "Сдано по акту, ждём остаток оплаты 70 %. Гравировка — GRAVURA.MD."),
    ("Выставочный стенд Moldexpo 6x3 м с панно и подсветкой", 10, "Монтаж", "Производство", "T-2026-019", 96000, 50, -25, -3, "Victor Botnari", "Запаздывает: срок сдачи прошёл, конструкция ещё в производстве. Монтаж — BM PUBLIC."),
    ("Панно-табличка ресторана из дуба с логотипом (лазер)", 7, "Гравировка", "Договор", "", 9800, 50, 0, 18, "Andrei Rusu", "Прямой заказ, договор на подписи; аванс 50 %."),
    ("Наградные доски и кубки с гравировкой (конкурс)", 0, "Сувениры", "Тендер", "T-2026-031", 27000, 30, 2, 40, "Maria Ceban", "Заявка подана, вскрытие предложений через 5 дней."),
    ("Вывеска и панно на входе (композит + объёмные буквы)", 2, "Реклама", "Сдача", "T-2026-012", 74500, 50, -40, 1, "Victor Botnari", "Смонтировано, назначена приёмка и подписание акта."),
]
PROJECT_STEPS = [("Подготовка тендерной заявки", "Ion Popescu", 4), ("Договор и спецификация", "Ion Popescu", 3),
                 ("Счёт на аванс и контроль оплаты", "Elena Ciobanu", 1), ("Дизайн-макет", "Maria Ceban", 8),
                 ("Согласование макета с клиентом", "Ion Popescu", 2), ("Закупка материалов", "Victor Botnari", 3),
                 ("Производство", "Andrei Rusu", 16), ("Контроль качества", "Andrei Rusu", 2),
                 ("Монтаж / доставка", "Victor Botnari", 6), ("Сдача работ и акт", "Ion Popescu", 1),
                 ("Итоговый счёт и закрытие оплаты", "Elena Ciobanu", 1)]
PROJECT_ITEMS = [("P-101", "Панно с логотипом (изделие под заказ)", "Изделие", "шт", 1, 0),
                 ("P-102", "Табличка с гравировкой / выжигом, дерево", "Изделие", "шт", 1, 0),
                 ("P-103", "Стенд выставочный (изделие под заказ)", "Изделие", "компл", 1, 0)]


def _d(days: int) -> str:
    return (date.today() + timedelta(days=days)).isoformat()


def _production_step(kind: str):
    return {"Реклама": ("Резка ЧПУ, сборка панно, покраска", "Victor Botnari", 24),
            "Гравировка": ("Лазерная гравировка и выжиг", "Andrei Rusu", 16),
            "Сувениры": ("Гравировка партии и упаковка", "Andrei Rusu", 20),
            "Монтаж": ("Изготовление конструкции стенда", "Victor Botnari", 40)}.get(kind, ("Производство", "Andrei Rusu", 16))


def _client(data: CrmData, c, contact: str, stats: Dict[str, int]) -> int:
    """RO: clientul intra prin aceeasi cale ca SDK-ul (dedup dupa IDNO)."""
    idno, name, form, addr, admin, ctype, phone, email = c
    r = data.rows("SELECT ID FROM CRM_CLIENT t WHERE t.IDNO = :i AND %s" % data.t.where(), dict(data.t.params(), i=idno))
    if r:
        return int(r[0]["id"])
    cid = data.next_id("CRM_CLIENT")
    data.dml("INSERT INTO CRM_CLIENT (ID, IDNO, NAME, REG_DATE, LEGAL_FORM, IS_LIQUIDATED, ADDRESS, MANAGERS, SOURCE, "
             "OWNER_KIND, OWNER_ID, CLIENT_TYPE, PHONE, EMAIL, CONTACT_PERSON) VALUES "
             "(:id, :idno, :n, :reg, :lf, 0, :addr, :mgr, 'seed', :ok, :oi, :ct, :ph, :em, :cp)",
             dict(data.t.params(), id=cid, idno=idno, n=name, reg="01.01.2015", lf=form, addr=addr, mgr=admin,
                  ct=ctype, ph=phone or None, em=email or None, cp=contact))
    stats["clients"] += 1
    return cid


def _exists(data: CrmData, table: str, col: str, value: Any) -> bool:
    return data.count(table, "t.%s = :v" % col, {"v": value}) > 0


def run(data: CrmData) -> Dict[str, int]:
    st = {k: 0 for k in ("clients", "contacts", "leads", "deals", "items", "orders", "lines", "tasks",
                         "projects", "project_tasks")}
    client_ids = [_client(data, c, CONTACT_NAMES[i % len(CONTACT_NAMES)], st) for i, c in enumerate(COMPANIES)]

    # contacte — cite 2 la primii 10 clienti
    for i in range(10):
        for j in range(2):
            n = (i * 2 + j) % len(CONTACT_NAMES)
            if data.count("CRM_CONTACT", "t.NAME = :n AND t.CLIENT_ID = :c", {"n": CONTACT_NAMES[n], "c": client_ids[i]}):
                continue
            data.insert("contacts", {"name": CONTACT_NAMES[n], "client_id": client_ids[i],
                                     "position": POSITIONS[(i + j) % len(POSITIONS)],
                                     "phone": "+373 6%d %03d-%03d" % (i % 10, 100 + i * 7, 200 + j * 33),
                                     "email": CONTACT_NAMES[n].lower().replace(" ", ".") + "@example.md",
                                     "notes": "Основной контакт" if j == 0 else ""})
            st["contacts"] += 1

    # leaduri — toate statusurile si sursele
    for i, comp in enumerate(LEAD_COMPANIES):
        if _exists(data, "CRM_LEAD", "COMPANY", comp):
            continue
        data.insert("leads", {"name": LEAD_PERSONS[i], "company": comp, "status": ENUMS["lead_status"][i % 4],
                              "source": ENUMS["lead_source"][i % 6],
                              "phone": "+373 7%d %03d-%03d" % (i % 10, 300 + i * 5, 400 + i * 9),
                              "email": "contact%d@%s.md" % (i + 1, comp.replace(" ", "")[:8].lower()),
                              "notes": "Первичный интерес: " + DEAL_TITLES[i % len(DEAL_TITLES)]})
        st["leads"] += 1

    # oferte — pe toate etapele, sume 5 000 … 250 000
    for i, title in enumerate(DEAL_TITLES):
        if _exists(data, "CRM_DEAL", "TITLE", title):
            continue
        data.insert("deals", {"title": title, "client_id": client_ids[(i * 3) % len(client_ids)],
                              "stage": ENUMS["deal_stage"][i % 5], "amount": 5000 + i * 21000,
                              "close_date": _d(7 + i * 6), "notes": "Договор подписан" if i % 5 == 3 else ""})
        st["deals"] += 1

    # nomenclator
    item_ids: List[int] = []
    item_prices: List[float] = []
    for code, name, kind, unit, price, stock in ITEMS:
        r = data.rows("SELECT ID FROM CRM_ITEM t WHERE t.CODE = :c AND %s" % data.t.where(), dict(data.t.params(), c=code))
        if r:
            iid = int(r[0]["id"])
        else:
            iid = data.insert("items", {"code": code, "name": name, "kind": kind, "unit_": unit, "price": price,
                                        "vat": 20, "stock": stock, "notes": ""})
            st["items"] += 1
        item_ids.append(iid)
        item_prices.append(float(price))

    # comenzi — 18: vinzare / serviciu / productie, toate statusurile, 1–3 linii
    for i in range(18):
        num = "%04d" % (i + 1)
        if _exists(data, "CRM_ORDER", "DOC_NO", num):
            continue
        kind = ENUMS["order_kind"][i % 3]
        status = ENUMS["order_status"][i % 6]
        oid = data.insert("orders", {"number": num, "order_date": _d(-40 + i * 2),
                                     "client_id": None if kind == "Производство" else client_ids[(i * 5) % len(client_ids)],
                                     "kind": kind, "status": status,
                                     "due_date": _d(-40 + i * 2 + (5 if i % 4 == 1 else 25)),
                                     "notes": "Срочный" if i % 4 == 0 else ""})
        st["orders"] += 1
        for j in range(i % 3 + 1):
            n = ((i + j) % 8) if kind == "Продажа" else (8 + (i + j) % 5 if kind == "Услуга" else 13 + (i + j) % 5)
            data.add_order_line(oid, item_ids[n], 1 + (i + j) % 4, item_prices[n])
            st["lines"] += 1
        if status in ("Выполнен", "Оплачен"):
            data.post_order(oid)
        total = float(data.scalar("SELECT NVL(TOTAL,0) FROM CRM_ORDER WHERE ID = :o", {"o": oid}) or 0)
        upd = "UPDATE CRM_ORDER SET %s WHERE ID = :o"
        if status == "Подтверждён":
            data.dml(upd % "ADVANCE = :a", {"a": 0 if (i // 6) % 2 == 0 else round(total * 0.3, 2), "o": oid})
        elif status == "В работе":
            data.dml(upd % "ADVANCE = :a", {"a": round(total * 0.5, 2), "o": oid})
        elif status == "Выполнен":
            if i // 6 == 0:
                data.dml(upd % "ADVANCE = :a", {"a": round(total * 0.4, 2), "o": oid})
            else:
                data.dml(upd % "ADVANCE = :a, PAID = :p, SHIP_DATE = TO_DATE(:s,'YYYY-MM-DD')",
                         {"a": round(total * 0.4, 2), "p": round(total * 0.4, 2), "s": _d(-40 + i * 2 + 20), "o": oid})
        elif status == "Оплачен":
            data.dml(upd % "ADVANCE = :a, PAID = :p, SHIP_DATE = TO_DATE(:s,'YYYY-MM-DD')",
                     {"a": round(total * 0.5, 2), "p": total, "s": _d(-40 + i * 2 + 15), "o": oid})

    # sarcini — 24: intirziate, azi, viitoare, o parte executate
    deal_ids = [d["id"] for d in data.list("deals", limit=100)]
    deal_ids.sort()
    for i in range(24):
        subj = "%s #%d" % (TASK_SUBJECTS[i % 10], i + 1)
        if _exists(data, "CRM_TASK", "SUBJECT", subj):
            continue
        data.insert("tasks", {"subject": subj, "kind": ENUMS["task_kind"][i % 3], "due_at": _d(-6 + i),
                              "client_id": client_ids[(i * 7) % len(client_ids)],
                              "deal_id": deal_ids[i % 12] if (i % 3 == 0 and deal_ids) else None,
                              "done": 1 if i < 4 else 0, "stage": "Готово" if i < 4 else "Новая", "notes": ""})
        st["tasks"] += 1

    # proiecte: parteneri, produse, proiecte cu licitatii, pasi, comenzi de productie
    for i, c in enumerate(PARTNERS):
        _client(data, c, c[4], st)
    pitem_ids = {}
    for code, name, kind, unit, price, stock in PROJECT_ITEMS:
        r = data.rows("SELECT ID FROM CRM_ITEM t WHERE t.CODE = :c AND %s" % data.t.where(), dict(data.t.params(), c=code))
        if r:
            pitem_ids[code] = int(r[0]["id"])
        else:
            pitem_ids[code] = data.insert("items", {"code": code, "name": name, "kind": kind, "unit_": unit,
                                                    "price": price, "vat": 20, "stock": stock,
                                                    "notes": "Изделие по проекту: цена в строке заказа"})
            st["items"] += 1
    for i, ps in enumerate(PROJECTS):
        name, cidx, kind, status, tender, budget, pct, start_off, due_off, manager, notes = ps
        if _exists(data, "CRM_PROJECT", "NAME", name):
            continue
        cid = client_ids[cidx]
        prepaid = paid = 0.0
        if process.done_steps_for(status) >= 2 and status != "Проигран":
            prepaid = round(budget * pct / 100)
        if status == "Закрыт":
            paid = budget - prepaid
        pid = data.insert("projects", {"name": name, "client_id": cid, "kind": kind, "status": status,
                                       "tender_no": tender, "tender_deadline": _d(start_off + 5) if tender else None,
                                       "budget": budget, "prepay_pct": pct, "prepaid": prepaid, "paid": paid,
                                       "start_date": _d(start_off), "due_date": _d(due_off), "manager": manager,
                                       "notes": notes})
        st["projects"] += 1
        dt = "Тендер: " + name
        if not _exists(data, "CRM_DEAL", "TITLE", dt):
            data.insert("deals", {"title": dt, "client_id": cid,
                                  "stage": "Предложение" if status == "Тендер" else ("Проиграна" if status == "Проигран" else "Выиграна"),
                                  "amount": budget, "close_date": _d(start_off + 5),
                                  "notes": ("Тендер " + tender) if tender else "Прямой заказ"})
            st["deals"] += 1
        done_n = process.done_steps_for(status)
        cursor, prev, step_n = start_off, 0, 0
        for j, (subj, who, hours) in enumerate(PROJECT_STEPS):
            if j == 2 and pct == 0:
                continue
            if status == "Проигран" and j > 1:
                break
            if j == 6:
                subj, who, hours = _production_step(kind)
            days = max(1, math.ceil(hours / 8))
            step_n += 1
            if step_n <= done_n:
                stage = "Готово"
            elif step_n == done_n + 1:
                stage = "Ожидание" if status == "Проигран" else "В работе"
            else:
                stage = "Новая"
            prio = "Высокий" if j == 6 else ("Низкий" if j == 7 else "Обычный")
            if stage == "В работе" and cursor + days - 1 < 0:
                prio = "Срочно"
            tid = data.insert("tasks", {"subject": subj, "project_id": pid, "stage": stage, "priority": prio,
                                        "assignee": who, "kind": "Встреча" if j == 4 else "Задача",
                                        "plan_start": _d(cursor), "due_at": _d(cursor + days - 1),
                                        "hours_plan": hours, "hours_fact": round(hours * 1.1) if stage == "Готово" else None,
                                        "seq": step_n, "depends_on": prev or None, "client_id": cid,
                                        "done": 1 if stage == "Готово" else 0,
                                        "notes": "Аванс %d %% от %d MDL" % (pct, budget) if j == 2 else ""})
            st["project_tasks"] += 1
            prev = tid
            cursor += days
        if status in ("Производство", "Сдача", "Оплата", "Закрыт"):
            num = "PR-%d" % (1001 + i)
            if not _exists(data, "CRM_ORDER", "DOC_NO", num):
                ostatus = "В работе" if status == "Производство" else ("Оплачен" if status == "Закрыт" else "Выполнен")
                oid = data.insert("orders", {"number": num, "order_date": _d(start_off), "client_id": cid,
                                             "project_id": pid, "kind": "Производство", "status": ostatus,
                                             "due_date": _d(due_off), "notes": "По проекту: " + name})
                code = "P-101" if kind == "Реклама" else ("P-103" if kind == "Монтаж" else "P-102")
                data.add_order_line(oid, pitem_ids[code], 1, budget)
                st["orders"] += 1
                st["lines"] += 1
                if ostatus != "В работе":
                    data.post_order(oid)
                data.dml("UPDATE CRM_ORDER SET ADVANCE = :a, PAID = :p, SHIP_DATE = TO_DATE(:s,'YYYY-MM-DD') WHERE ID = :o",
                         {"a": prepaid, "p": paid, "s": _d(due_off) if status in ("Оплата", "Закрыт") else None, "o": oid})
    return st


def text(st: Dict[str, int]) -> str:
    return ("clienti %(clients)d, contacte %(contacts)d, leaduri %(leads)d, oferte %(deals)d, nomenclator %(items)d, "
            "comenzi %(orders)d (linii %(lines)d), sarcini %(tasks)d, proiecte %(projects)d "
            "(sarcini de proiect %(project_tasks)d)" % st)
