#!/usr/bin/env python3
"""SDA — демонстрационный набор данных.

Зачем отдельный скрипт, а не SQL-файл: данные заводятся ЧЕРЕЗ хранилище
модуля (`modules.sda.store`), поэтому набор заодно проверяет весь путь
вживую — расчёт режима точки, вывод тарифных категорий, запись в журнал,
фиксацию транзакции. SQL-скрипт проверил бы только сам себя.

Масштаб набора рассчитан на то, чтобы отчёты выглядели как отчёты реальной
сети, а не игрушки: около 45 точек в десяти с лишним населённых пунктах,
все границы порога площади (100/100,1 м² и 150/150,1 м²), несколько точек
без обмера («инвентарь необходим»), полный набор из семи категорий
администрирования a-g и пяти категорий обработки a-e, три вида тарифов
периодами без дыр и наложений, и — намеренно — два пункта возврата,
которых не хватает, плюс один уже истёкший: тестовый прогон, где всё
зелёное, ничего не доказывает.

    venv/bin/python modules/sda/scripts/sda_demo.py --yes
    venv/bin/python modules/sda/scripts/sda_demo.py --purge --yes
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from models.database import DatabaseModel          # noqa: E402
from modules.sda.store import SDAStore             # noqa: E402

USER = "demo"

# ── Участники ──────────────────────────────────────────────────────────
# Второй участник (producator) демонстрирует пункт 83 регламента: одна
# организация может числиться сразу в нескольких ролях.

PARTICS = [
    {
        "idno": "1003600000000",
        "denumire": "Rețea de magazine Nufărul (demo)",
        "contact_nume": "Responsabil SDA",
        "contact_tel": "+373 22 000 000",
        "contact_email": "sda@example.md",
        "vandut_an_ant": 1240000,
        "estimare_an": 1310000,
    },
    {
        "idno": "1003600000117",
        "denumire": "Producător de băuturi Izvorul (demo, dublu rol)",
        "contact_nume": "Responsabil producție",
        "contact_tel": "+373 22 111 222",
        "contact_email": "productie@example.md",
        "vandut_an_ant": 96000,
        "estimare_an": 105000,
    },
]

# ── Rețeaua de unități ───────────────────────────────────────────────────
# (cod_erp, denumire, adresă, localitate, m², tip_amplasament)
#
# Acoperă toate ramurile pragului, inclusiv granițele: 100,0/100,1 pentru
# MAGAZIN, 150,0/150,1 pentru CHIOSC/TARABA/BENZINARIE/ALIMENTATIE_PUBLICA.
# Trei-patru unități rămân fără suprafață — starea „inventar necesar".

UNITS = [
    # cod, denumire, adresă, localitate, m², tip_amplasament, is_horeca
    #
    # is_horeca e explicit, nu dedus din tip: o unitate ALIMENTATIE_PUBLICA
    # poate fi fie predare directă (HoReCa), fie clasificată după prag ca
    # oricare alt tip din grupul special — de-asta pragul de 150/150,1 m²
    # trebuie testat și pentru acest tip, nu doar pentru CHIOSC/TARABA.
    #
    # Chișinău
    ("R-012", "Magazin 12 — Botanica",        "bd. Dacia 45",              "Chișinău",  78.0,  "MAGAZIN", False),
    ("R-031", "Magazin 31 — Rîșcani",         "str. Kiev 12",              "Chișinău",  94.5,  "MAGAZIN", False),
    ("R-044", "Magazin 44 — Centru",          "str. Columna 104",          "Chișinău", 100.0,  "MAGAZIN", False),
    ("R-045", "Magazin 45 — Buiucani",        "str. Alba Iulia 90",        "Chișinău", 100.1,  "MAGAZIN", False),
    ("R-101", "Supermarket Ciocana",          "bd. Mircea cel Bătrân 8",   "Chișinău", 460.0,  "MAGAZIN", False),
    ("R-102", "Supermarket Poșta Veche",      "str. Calea Ieșilor 3",      "Chișinău", 610.0,  "MAGAZIN", False),
    ("R-210", "Chioșc Piața Centrală",        "Piața Centrală, rând 4",    "Chișinău",  22.0,  "CHIOSC", False),
    ("R-212", "Chioșc Sculeni",               "str. Sculeni 15",           "Chișinău", 150.0,  "CHIOSC", False),
    ("R-213", "Chioșc Ciocana Nouă",          "str. Mesager 9",            "Chișinău", 150.1,  "CHIOSC", False),
    ("R-305", "Benzinărie Chișinău Vest",     "șos. Hîncești 122",         "Chișinău", 149.5,  "BENZINARIE", False),
    ("R-500", "Grill Cafe Centru",            "str. Pușkin 24",            "Chișinău",  85.0,  "ALIMENTATIE_PUBLICA", True),
    ("R-501", "Grill Cafe Ciocana",           "bd. Mircea cel Bătrân 8",   "Chișinău",  60.0,  "ALIMENTATIE_PUBLICA", True),
    ("R-502", "Trattoria Centru",             "str. Ismail 33",            "Chișinău", 150.0,  "ALIMENTATIE_PUBLICA", False),
    ("R-507", "Restaurant Ismail",            "str. Ismail 40",            "Chișinău", 150.1,  "ALIMENTATIE_PUBLICA", False),
    ("R-604", "Magazin 64 — Telecentru",      "str. N. Costin 14",         "Chișinău",  None,  "MAGAZIN", False),
    # Bălți
    ("R-103", "Supermarket Bălți Centru",     "str. Ștefan cel Mare 21",   "Bălți",    312.0,  "MAGAZIN", False),
    ("R-104", "Magazin Bălți Nord",           "str. Decebal 5",            "Bălți",     88.0,  "MAGAZIN", False),
    ("R-214", "Taraba Piața Bălți",           "Piața orașului, rând 2",    "Bălți",     18.0,  "TARABA", False),
    ("R-306", "Benzinărie Bălți Est",         "str. Chișinăului 40",       "Bălți",    138.0,  "BENZINARIE", False),
    # Cahul
    ("R-602", "Magazin 62 — Cahul",           "str. Independenței 7",      "Cahul",     None,  "MAGAZIN", False),
    ("R-105", "Supermarket Cahul",            "str. Ștefan cel Mare 60",   "Cahul",    255.0,  "MAGAZIN", False),
    ("R-503", "Fast-food Cahul",              "str. Victoriei 12",         "Cahul",     72.0,  "ALIMENTATIE_PUBLICA", True),
    # Orhei
    ("R-307", "Benzinărie Orhei",             "șos. Chișinăului 3",        "Orhei",    140.0,  "BENZINARIE", False),
    ("R-046", "Magazin Orhei Centru",         "str. Vasile Mahu 8",        "Orhei",     65.0,  "MAGAZIN", False),
    # Ungheni
    ("R-211", "Taraba Piața Ungheni",         "Piața orașului",            "Ungheni",   16.0,  "TARABA", False),
    ("R-106", "Magazin Ungheni Gară",         "str. Națională 2",          "Ungheni",  190.0,  "MAGAZIN", False),
    # Soroca
    ("R-603", "Magazin 63 — Soroca",          "str. Ștefan cel Mare 5",    "Soroca",    None,  "MAGAZIN", False),
    ("R-107", "Magazin Soroca Centru",        "str. Independenței 20",     "Soroca",   210.0,  "MAGAZIN", False),
    # Comrat
    ("R-108", "Supermarket Comrat",           "str. Lenin 44",             "Comrat",   330.0,  "MAGAZIN", False),
    ("R-215", "Chioșc Comrat",                "str. Pobeda 11",            "Comrat",    30.0,  "CHIOSC", False),
    # Edineț
    ("R-109", "Magazin Edineț Centru",        "str. Independenței 33",     "Edineț",   150.0,  "MAGAZIN", False),
    ("R-504", "Cafenea Edineț",               "str. 31 August 6",          "Edineț",    95.0,  "ALIMENTATIE_PUBLICA", True),
    # Hîncești
    ("R-110", "Magazin Hîncești Centru",      "str. Mihalcea Hîncu 15",    "Hîncești", 175.0,  "MAGAZIN", False),
    ("R-308", "Benzinărie Hîncești",          "șos. Chișinăului 1",        "Hîncești", 151.0,  "BENZINARIE", False),
    # Căușeni
    ("R-111", "Magazin Căușeni Centru",       "str. Mateevici 9",          "Căușeni",   82.0,  "MAGAZIN", False),
    ("R-216", "Taraba Piața Căușeni",         "Piața orașului",            "Căușeni",   14.0,  "TARABA", False),
    # Strășeni
    ("R-112", "Supermarket Strășeni",         "str. Mihai Eminescu 18",    "Strășeni", 240.0,  "MAGAZIN", False),
    ("R-505", "Restaurant Strășeni",          "str. 31 August 40",         "Strășeni", 160.0,  "ALIMENTATIE_PUBLICA", False),
    # Drochia
    ("R-113", "Magazin Drochia Centru",       "str. 1 Mai 3",              "Drochia",  120.0,  "MAGAZIN", False),
    ("R-309", "Benzinărie Drochia",           "șos. Bălțiului 5",          "Drochia",  145.0,  "BENZINARIE", False),
    # Alte 6 pentru volum (mix de tipuri, fără puncte de returnare proprii)
    ("R-114", "Magazin Chișinău Râșcani 2",   "str. Alecu Russo 15",       "Chișinău",  91.0,  "MAGAZIN", False),
    ("R-115", "Magazin Bălți Sud",            "str. Bulgară 7",            "Bălți",     70.0,  "MAGAZIN", False),
    ("R-217", "Chioșc Orhei",                 "str. Vasile Mahu 20",       "Orhei",     45.0,  "CHIOSC", False),
    ("R-310", "Benzinărie Ungheni",           "șos. Națională 40",         "Ungheni",  132.0,  "BENZINARIE", False),
    ("R-506", "Bistro Comrat",                "str. Lenin 60",             "Comrat",    68.0,  "ALIMENTATIE_PUBLICA", True),
    ("R-605", "Magazin 65 — Strășeni",        "str. Ștefan cel Mare 2",    "Strășeni",  None,  "MAGAZIN", False),
]

# ── Registrul ambalajelor SD ─────────────────────────────────────────────
# (ean, denumire, producător, material, culoare, barieră_o2, reutilizabil,
#  volum_l, greutate_g)
#
# Acoperă toate cele șapte categorii de administrare (a-g) și toate cele
# cinci categorii de gestionare (a-e): PET transparent (a), PET colorat
# simplu — albastru/verde/maro (b), PET amestecat/HDPE (c), PET cu barieră
# de oxigen (d), metal (e), sticlă mare >0,5 l (f), sticlă mică ≤0,5 l (g).
# Greutățile sunt plauzibile pentru fiecare material: sticlă 0,5 l ≈ 380 g,
# PET 1,5 l ≈ 38 g, doză ≈ 14 g.

PACKS = [
    # cat_admin a — PET transparent
    ("4840001000012", "Apă minerală, PET 1,5 l",     "Izvorul SRL", "PLASTIC", "TRANSPARENT", "N", "N", 1.5,  38.0),
    ("4840001000029", "Apă potabilă, PET 0,5 l",     "Izvorul SRL", "PLASTIC", "TRANSPARENT", "N", "N", 0.5,  22.0),
    ("4840002000015", "Suc de mere, PET 1 l",        "Livada SA",   "PLASTIC", "TRANSPARENT", "N", "N", 1.0,  30.0),
    # cat_admin b — PET colorat simplu (albastru/verde/maro)
    ("4840002000022", "Apă minerală, PET albastru 1 l", "Izvorul SRL","PLASTIC","ALBASTRU",   "N", "N", 1.0,  32.0),
    ("4840002000039", "Suc de portocale, PET verde 1 l","Livada SA", "PLASTIC","VERDE",       "N", "N", 1.0,  34.0),
    ("4840002000046", "Cidru, PET maro 1 l",          "Livada SA",  "PLASTIC","MARO",         "N", "N", 1.0,  33.0),
    # cat_admin c — PET amestecat / HDPE
    ("4840002000053", "Băutură răcoritoare, PET mixt 2 l","Fresh SRL","PLASTIC","MIXT",       "N", "N", 2.0,  46.0),
    ("4840002000060", "Apă potabilă, HDPE 5 l",       "Izvorul SRL","PLASTIC", "ALB",         "N", "N", 3.0,  58.0),
    # cat_admin d — barieră de oxigen (bate culoarea)
    ("4840006000017", "Ceai rece, PET cu barieră 0,5 l","Fresh SRL","PLASTIC","TRANSPARENT",  "D", "N", 0.5,  26.0),
    ("4840006000024", "Suc concentrat, PET cu barieră 1 l","Livada SA","PLASTIC","VERDE",     "D", "N", 1.0,  36.0),
    # cat_admin e — metal
    ("4840005000014", "Bere la doză, metal 0,5 l",    "Berăria SRL","METAL",   None,          "N", "N", 0.5,  14.0),
    ("4840005000021", "Energizant, metal 0,25 l",     "Fresh SRL",  "METAL",   None,          "N", "N", 0.25, 11.0),
    ("4840005000038", "Cidru la doză, metal 0,33 l",  "Berăria SRL","METAL",   None,          "N", "N", 0.33, 13.0),
    # cat_admin f — sticlă mare (>0,5 l)
    ("4840004000011", "Vin alb sec, sticlă 0,75 l",   "Vinăria SA", "STICLA",  None,          "N", "N", 0.75, 480.0),
    ("4840004000028", "Vin roșu demisec, sticlă 0,75 l","Vinăria SA","STICLA",None,           "N", "N", 0.75, 490.0),
    ("4840003000032", "Bere blondă, sticlă 1 l",      "Berăria SRL","STICLA",  None,          "N", "N", 1.0,  520.0),
    # cat_admin g — sticlă mică (≤0,5 l)
    ("4840003000018", "Bere blondă, sticlă 0,5 l",    "Berăria SRL","STICLA",  None,          "N", "N", 0.5,  380.0),
    ("4840003000025", "Bere brună, sticlă 0,33 l",    "Berăria SRL","STICLA",  None,          "N", "N", 0.33, 330.0),
    ("4840003000049", "Cidru, sticlă 0,33 l",         "Livada SA",  "STICLA",  None,          "N", "N", 0.33, 320.0),
    # câteva reutilizabile — depozitul se calculează diferit pentru ele
    ("4840007000010", "Bere la halbă, sticlă reutilizabilă 0,5 l","Berăria SRL","STICLA",None,"N", "D", 0.5,  400.0),
    ("4840007000027", "Apă minerală, sticlă reutilizabilă 0,5 l","Izvorul SRL","STICLA",None, "N", "D", 0.5,  390.0),
    ("4840007000034", "Suc, PET reutilizabil 1 l",    "Livada SA",  "PLASTIC","TRANSPARENT",  "N", "D", 1.0,  55.0),
    # cîteva vinuri și băuturi suplimentare pentru volumul registrului
    ("4840004000035", "Vin spumant, sticlă 0,75 l",   "Vinăria SA", "STICLA",  None,          "N", "N", 0.75, 500.0),
    ("4840001000036", "Apă minerală, PET 2 l",        "Izvorul SRL","PLASTIC", "TRANSPARENT", "N", "N", 2.0,  46.0),
    ("4840005000045", "Bere IPA la doză, metal 0,5 l","Berăria SRL","METAL",   None,          "N", "N", 0.5,  14.5),
]

# ── Tarife ────────────────────────────────────────────────────────────
# Toate valorile sunt ilustrative: legea nu a fixat încă niciuna dintre ele.
#
# DEPOZIT: o perioadă-pilot (până în ajunul datei legale) și perioada
# legală care începe exact la 25.01.2027 — fără gol, fără suprapunere.
# ADMIN: câte o linie pentru fiecare categorie a-g.
# GESTIUNE: câte o linie pentru fiecare categorie a-e, pe metodă manuală
# și automată — costul de procesare diferă după metodă.

TARIFFS = [
    # Начало пилота — в прошлом, иначе на дашборде «тариф депозита
    # сегодня» пусто, и демонстрация показывает не работу системы,
    # а её отсутствие.
    ("DEPOZIT", date(2026, 6, 1), date(2027, 1, 24),
     "Perioadă-pilot a rețelei (valoare demonstrativă, legea nu a fixat-o încă)",
     [("*", None, None, 0.5)]),
    ("DEPOZIT", date(2027, 1, 25), None,
     "Ordin al ministrului mediului (valoare demonstrativă, legea nu a fixat-o încă)",
     [("*", None, None, 1.0)]),
    ("ADMIN", date(2027, 1, 25), None,
     "Schema de finanțare a Administratorului DRS (valori demonstrative)",
     [
        ("a", None, None, 0.08), ("b", None, None, 0.09), ("c", None, None, 0.10),
        ("d", None, None, 0.11), ("e", None, None, 0.07), ("f", None, None, 0.06),
        ("g", None, None, 0.05),
     ]),
    ("GESTIUNE", date(2027, 1, 25), None,
     "Schema de finanțare a Administratorului DRS (valori demonstrative)",
     [
        ("a", "MANUAL", None, 0.14), ("a", "AUTOMAT", None, 0.11),
        ("b", "MANUAL", None, 0.16), ("b", "AUTOMAT", None, 0.13),
        ("c", "MANUAL", None, 0.20), ("c", "AUTOMAT", None, 0.17),
        ("d", "MANUAL", None, 0.22), ("d", "AUTOMAT", None, 0.19),
        ("e", "MANUAL", None, 0.18), ("e", "AUTOMAT", None, 0.15),
     ]),
]


def _q(db, sql, params=None):
    r = db.execute_query(sql, params)
    if not r.get("success"):
        raise SystemExit(f"Ошибка: {r.get('message')}")
    return r


# Чистим по одной таблице, каждую своей транзакцией: на ADB длинная
# многотабличная транзакция ловила ORA-12860 (deadlock on sibling row lock)
# из-за параллельного DML. Порядок обратный ссылкам.
PURGE_ORDER = ("SDA_TARIFF_LINE", "SDA_TARIFF", "SDA_PACK_SKU", "SDA_PACK",
               "SDA_RVM", "SDA_RETURN_POINT", "SDA_UNIT", "SDA_PARTIC_ROL",
               "SDA_PARTIC", "SDA_EVENT_LOG")


def purge():
    for table in PURGE_ORDER:
        for attempt in (1, 2, 3):
            with DatabaseModel() as db:
                r = db.execute_query(f"DELETE FROM {table}")
                if r.get("success"):
                    db.connection.commit()
                    break
                if attempt == 3:
                    raise SystemExit(f"{table}: {r.get('message')}")
    print("Демонстрационные данные удалены.")


def seed():
    partic_ids = []
    for payload in PARTICS:
        res = SDAStore.save_partic(dict(payload), USER)
        if not res["success"]:
            raise SystemExit(f"Участник: {res['message']}")
        partic_id = res["data"]["partic_id"]
        partic_ids.append(partic_id)
        print(f"Участник: {partic_id} — {payload['denumire']}")

    main_partic_id = partic_ids[0]

    unit_ids = {}
    for cod, den, adr, loc, mp, tip, is_horeca in UNITS:
        r = SDAStore.save_unit({
            "partic_id": main_partic_id, "cod_erp": cod, "denumire": den,
            "adresa": adr, "localitate": loc, "suprafata_mp": mp,
            "tip_amplasament": tip,
            "is_horeca": is_horeca,
        }, USER)
        if not r["success"]:
            raise SystemExit(f"{den}: {r['message']}")
        unit_ids[cod] = r["data"]["unit_id"]
        print(f"  {cod:6} {str(mp or '—'):>6} m2  {tip:20} -> {r['data']['regim'] or 'FĂRĂ REGIM'}")

    for ean, den, prod, mat, cul, bar, reut, vol, gr in PACKS:
        r = SDAStore.save_pack({
            "ean": ean, "denumire": den, "producator": prod, "material": mat,
            "culoare": cul, "bariera_o2": bar, "reutilizabil": reut,
            "volum_l": vol, "greutate_g": gr, "sursa": "MANUAL",
        }, USER)
        if not r["success"]:
            raise SystemExit(f"{ean}: {r['message']}")
        print(f"  {ean}  {mat:8} {vol:>5} l  -> {r['data']['cat_admin']}/{r['data']['cat_gest']}")

    with DatabaseModel() as db:
        for tip, start, end, act, lines in TARIFFS:
            _q(db, "INSERT INTO SDA_TARIFF (TIP, DATA_START, DATA_END, ACT_NORMATIV) "
                   "VALUES (:tip, :d1, :d2, :act)",
               {"tip": tip, "d1": start, "d2": end, "act": act})
            tid = _q(db, "SELECT SEQ_SDA_TARIFF.CURRVAL FROM DUAL")["data"][0][0]
            for cat, met, reut, val in lines:
                _q(db, "INSERT INTO SDA_TARIFF_LINE (TARIFF_ID, CATEGORIE, METODA, "
                       "REUTILIZABIL, VALOARE_LEI) VALUES (:t, :c, :m, :r, :v)",
                   {"t": tid, "c": cat, "m": met, "r": reut, "v": val})
            print(f"  tarif {tip} de la {start}: {len(lines)} linii")

        # Puncte de returnare — doar acolo unde regimul le impune (regim A).
        # Lăsăm deliberat DOUĂ unități în regim A fără niciun punct, și unui
        # punct existent îi punem ACTIV_PANA în trecut: acestea sunt exact
        # stările pe care metrica de acoperire a tabloului de bord trebuie
        # să le detecteze. Fără ele, un demo complet verde n-ar dovedi nimic.
        units_a = _q(db, "SELECT UNIT_ID, DENUMIRE, COD_ERP FROM SDA_UNIT "
                         "WHERE PARTIC_ID = :p AND REGIM = 'A_PUNCT_PROPRIU' "
                         "ORDER BY DENUMIRE",
                     {"p": main_partic_id})["data"]

        # Ultimele două unități în regim A din listă rămân fără punct.
        without_point = {row[0] for row in units_a[-2:]} if len(units_a) >= 2 else set()
        point_ids = {}
        for idx, (unit_id, den, cod) in enumerate(units_a):
            if unit_id in without_point:
                print(f"  fără punct de returnare (demo — blochează dosarul): {den}")
                continue
            # Primul punct din listă e alocat cu ACTIV_PANA deja expirat:
            # tocmai starea pe care coverage-ul trebuie s-o excludă.
            expired = (idx == 0)
            activ_din = date(2026, 8, 1)
            activ_pana = date(2026, 12, 31) if expired else None
            tip_punct = "AUTOMAT" if idx % 3 == 0 else "MANUAL"
            _q(db, "INSERT INTO SDA_RETURN_POINT (UNIT_ID, TIP, ADRESA, DISTANTA_M, "
                   "ORAR, ACTIV_DIN, ACTIV_PANA) VALUES (:u, :t, :a, 0, "
                   "'08:00-21:00', :d1, :d2)",
               {"u": unit_id, "t": tip_punct, "a": den, "d1": activ_din, "d2": activ_pana})
            point_id = _q(db, "SELECT SEQ_SDA_RETURN_POINT.CURRVAL FROM DUAL")["data"][0][0]
            point_ids[unit_id] = point_id
            label = "EXPIRAT (demo)" if expired else "activ"
            print(f"  punct de returnare ({tip_punct}, {label}): {den}")

        # RVM-uri pe câteva puncte automate, cu ambii proprietari — schimbă
        # tariful de gestionare (pct. 14.14 j).
        automat_points = [pid for uid, pid in point_ids.items()
                          if _q(db, "SELECT TIP FROM SDA_RETURN_POINT WHERE POINT_ID = :p",
                                {"p": pid})["data"][0][0] == "AUTOMAT"]
        for i, pid in enumerate(automat_points[:4]):
            proprietar = "ADMINISTRATOR" if i % 2 == 0 else "COMERCIANT"
            _q(db, "INSERT INTO SDA_RVM (POINT_ID, MODEL, SERIA, PROPRIETAR, "
                   "DATA_INSTALARE, STARE) VALUES (:p, :m, :s, :o, :d, 'ACTIV')",
               {"p": pid, "m": "TOMRA T9", "s": f"RVM-{1000 + i}",
                "o": proprietar, "d": date(2026, 8, 15)})
            print(f"  RVM instalat pe punctul {pid} (proprietar {proprietar})")

        db.connection.commit()

    m = SDAStore.compliance_map(main_partic_id)["data"]
    print(f"\nHarta: total {m['total']}, {m['by_regime']}, fără regim {m['unknown']}")
    for when in (date(2026, 10, 1), date(2027, 2, 1)):
        d = SDAStore.deposit_for_ean("4840003000018", when)
        print(f"Depozit sticla 0,5 l la {when}:",
              d["data"]["valoare_lei"] if d["success"] else d["message"])
    bad = SDAStore.deposit_for_ean("0000000000000", date(2027, 2, 1))
    print("EAN necunoscut ->", bad["message"])

    dash = SDAStore.dashboard(main_partic_id)
    if dash["success"]:
        dd = dash["data"]
        print(f"\nTablou de bord: {dd['days_remaining']} zile până la {dd['deadline']}")
        print(f"  pregătire: {dd['readiness']['with_regim']}/{dd['readiness']['total']} "
              f"({dd['readiness']['pct']}%)")
        cov = dd["return_point_coverage"]
        print(f"  acoperire punct propriu: {cov['covered']}/{cov['total']}, "
              f"blocante: {[u['denumire'] for u in cov['blocking_units']]}")
        print(f"  registru: {dd['registry']['total']} ambalaje, "
              f"pe material {dd['registry']['by_material']}")
        print(f"  tarif depozit azi: {dd['tariff_state']['deposit']}")
        if dd["tariff_state"]["period_problems"]:
            print(f"  probleme perioade: {dd['tariff_state']['period_problems']}")
    else:
        print(f"\nTablou de bord: {dash['message']}")


def main():
    ap = argparse.ArgumentParser(description="SDA demo dataset")
    ap.add_argument("--purge", action="store_true", help="удалить демо-данные")
    ap.add_argument("--yes", action="store_true", help="выполнить (без него — только показать намерение)")
    args = ap.parse_args()
    if not args.yes:
        print("Без --yes ничего не делаю.")
        return
    if args.purge:
        purge()
        return
    seed()


if __name__ == "__main__":
    main()
