#!/usr/bin/env python3
"""SDA — демонстрационный набор данных.

Зачем отдельный скрипт, а не SQL-файл: данные заводятся ЧЕРЕЗ хранилище
модуля (`modules.sda.store`), поэтому набор заодно проверяет весь путь
вживую — расчёт режима точки, вывод тарифных категорий, запись в журнал,
фиксацию транзакции. SQL-скрипт проверил бы только сам себя.

Сеть подобрана так, чтобы на карте соответствия были видны все три режима
и остаток «без площади»: именно эта картина решает бюджет клиента.

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

# Магазин у порога и магазин заметно выше него: на карте должны разойтись.
UNITS = [
    ("R-012", "Magazin 12 — Botanica",      "bd. Dacia 45",        "Chișinău", 78.0,  "MAGAZIN"),
    ("R-031", "Magazin 31 — Rîșcani",       "str. Kiev 12",        "Chișinău", 94.5,  "MAGAZIN"),
    ("R-044", "Magazin 44 — Centru",        "str. Columna 104",    "Chișinău", 100.0, "MAGAZIN"),
    ("R-101", "Supermarket Ciocana",        "bd. Mircea cel Bătrân 8", "Chișinău", 460.0, "MAGAZIN"),
    ("R-102", "Supermarket Bălți",          "str. Ștefan cel Mare 21", "Bălți",    312.0, "MAGAZIN"),
    ("R-210", "Chioșc Piața Centrală",      "Piața Centrală, rând 4", "Chișinău", 22.0,  "CHIOSC"),
    ("R-211", "Taraba Piața Ungheni",       "Piața orașului",      "Ungheni",  16.0,  "TARABA"),
    ("R-305", "Punct Benzinărie Orhei",     "șos. Chișinăului 3",  "Orhei",   140.0, "BENZINARIE"),
    ("R-500", "Grill Cafe Centru",          "str. Pușkin 24",      "Chișinău",  85.0, "ALIMENTATIE_PUBLICA"),
    ("R-501", "Grill Cafe Ciocana",         "bd. Mircea cel Bătrân 8", "Chișinău", 60.0, "ALIMENTATIE_PUBLICA"),
    # Две точки без обмера — это и есть «инвентарь необходим» на карте.
    ("R-602", "Magazin 62 — Cahul",         "str. Independenței 7", "Cahul",   None,  "MAGAZIN"),
    ("R-603", "Magazin 63 — Soroca",        "str. Ștefan cel Mare 5", "Soroca", None,  "MAGAZIN"),
]

PACKS = [
    ("4840001000012", "Apă minerală, PET 1,5 l",  "Izvorul SRL",  "PLASTIC", "TRANSPARENT", "N", "N", 1.5,  38.0),
    ("4840001000029", "Apă potabilă, PET 0,5 l",  "Izvorul SRL",  "PLASTIC", "TRANSPARENT", "N", "N", 0.5,  22.0),
    ("4840002000015", "Suc de mere, PET 1 l",     "Livada SA",    "PLASTIC", "VERDE",       "N", "N", 1.0,  34.0),
    ("4840003000018", "Bere blondă, sticlă 0,5 l","Berăria SRL",  "STICLA",  None,          "N", "D", 0.5, 380.0),
    ("4840003000025", "Bere brună, sticlă 0,33 l","Berăria SRL",  "STICLA",  None,          "N", "D", 0.33,330.0),
    ("4840004000011", "Vin alb sec, sticlă 0,75 l","Vinăria SA",  "STICLA",  None,          "N", "N", 0.75,480.0),
    ("4840005000014", "Bere la doză, metal 0,5 l","Berăria SRL",  "METAL",   None,          "N", "N", 0.5,  14.0),
    ("4840005000021", "Energizant, metal 0,25 l", "Fresh SRL",    "METAL",   None,          "N", "N", 0.25, 11.0),
    ("4840006000017", "Ceai rece, PET cu barieră 0,5 l","Fresh SRL","PLASTIC","TRANSPARENT","D", "N", 0.5,  26.0),
]

# Величина депозита законом ещё не установлена — это учебное значение,
# заведённое периодом, как и положено: срок начала совпадает с датой
# пуска системы по закону 97/2024.
# Два периода подряд, без стыка и без дыры: так видно, что величина депозита
# живёт периодами, а не константой в коде. Первый — пилотный, до пуска
# системы; второй начинается в день, установленный законом 97/2024.
TARIFFS = [
    ("DEPOZIT", date(2026, 9, 1), date(2027, 1, 24),
     "Perioadă-pilot a rețelei (valoare demonstrativă)",
     [("*", None, None, 0.5)]),
    ("DEPOZIT", date(2027, 1, 25), None,
     "Ordin al ministrului mediului (valoare demonstrativă)",
     [("*", None, None, 1.0)]),
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
    res = SDAStore.save_partic({
        "idno": "1003600000000",
        "denumire": "Rețea de magazine (demo)",
        "contact_nume": "Responsabil SDA",
        "contact_tel": "+373 22 000 000",
        "contact_email": "sda@example.md",
        "vandut_an_ant": 412000,
        "estimare_an": 430000,
    }, USER)
    if not res["success"]:
        raise SystemExit(f"Участник: {res['message']}")
    partic_id = res["data"]["partic_id"]
    print(f"Участник: {partic_id}")

    for cod, den, adr, loc, mp, tip in UNITS:
        r = SDAStore.save_unit({
            "partic_id": partic_id, "cod_erp": cod, "denumire": den,
            "adresa": adr, "localitate": loc, "suprafata_mp": mp,
            "tip_amplasament": tip,
            "is_horeca": tip == "ALIMENTATIE_PUBLICA",
        }, USER)
        if not r["success"]:
            raise SystemExit(f"{den}: {r['message']}")
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
        # Пункты возврата — только там, где режим их требует.
        units = _q(db, "SELECT UNIT_ID, DENUMIRE FROM SDA_UNIT "
                       "WHERE PARTIC_ID = :p AND REGIM = 'A_PUNCT_PROPRIU'",
                   {"p": partic_id})
        for unit_id, den in units["data"]:
            _q(db, "INSERT INTO SDA_RETURN_POINT (UNIT_ID, TIP, ADRESA, DISTANTA_M, "
                   "ORAR, ACTIV_DIN) VALUES (:u, 'AUTOMAT', :a, 0, '08:00-21:00', :d)",
               {"u": unit_id, "a": den, "d": date(2026, 12, 1)})
            print(f"  punct de returnare (automat): {den}")
        db.connection.commit()

    m = SDAStore.compliance_map(partic_id)["data"]
    print(f"\nHarta: total {m['total']}, {m['by_regime']}, fără regim {m['unknown']}")
    for when in (date(2026, 10, 1), date(2027, 2, 1)):
        d = SDAStore.deposit_for_ean("4840003000018", when)
        print(f"Depozit sticla 0,5 l la {when}:",
              d["data"]["valoare_lei"] if d["success"] else d["message"])
    bad = SDAStore.deposit_for_ean("0000000000000", date(2027, 2, 1))
    print("EAN necunoscut ->", bad["message"])


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
