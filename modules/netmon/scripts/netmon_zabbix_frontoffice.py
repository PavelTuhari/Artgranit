#!/usr/bin/env python3
"""Заводит фронт-офисы баз cloudbd и clouddev в Zabbix.

    python modules/netmon/scripts/netmon_zabbix_frontoffice.py            # завести и отправить
    python modules/netmon/scripts/netmon_zabbix_frontoffice.py --dry-run  # только показать

Создаёт по одному хосту на базу (`cloudbd-db`, `clouddev-db`) и на каждом —
элемент на фронт-офис: сколько у него сейчас сессий. Ноль сессий в рабочее
время означает, что торговая точка не подключается: база жива, а магазин
уже не работает. Обычный мониторинг сервера такого не показывает.

Значения шлёт `zabbix_sender`; расписание — через cron или вручную после
изменений.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

from modules.netmon import assets, frontoffice as fo, sources  # noqa: E402

GROUP = "Front Office"
# Порог: фронт-офис, у которого сессий не было дольше этого времени в рабочие
# часы, считается остановленным. 30 минут — чтобы перезагрузка кассы не давала
# ложную тревогу.
NODATA_MIN = 30


def ensure_group(z, name: str) -> str:
    g = z.call("hostgroup.get", {"filter": {"name": name}, "output": ["groupid"]})
    return g[0]["groupid"] if g else z.call("hostgroup.create", {"name": name})["groupids"][0]


def ensure_host(z, db: dict, gid: str) -> str:
    host = f"{db['name']}-db"
    ex = z.call("host.get", {"filter": {"host": host}, "output": ["hostid"]})
    if ex:
        return ex[0]["hostid"]
    descr = (f"База Oracle {db['name']} на сервере {fo.DB_HOST_NAME} ({fo.DB_HOST}).\n"
             f"Держатель показателей фронт-офисов: по одному элементу на схему.\n"
             f"Значения присылает модуль netmon (sqlplus / as sysdba на сервере).")
    return z.call("host.create", {
        "host": host, "name": f"Фронт-офисы базы {db['name']}",
        "interfaces": [{"type": 1, "main": 1, "useip": 1, "ip": fo.DB_HOST,
                        "dns": "", "port": "10050"}],
        "groups": [{"groupid": gid}], "description": descr})["hostids"][0]


def ensure_items(z, host: str, hostid: str, db_name: str, fronts: list[dict]) -> int:
    created = 0
    # общее состояние базы
    for key, name, units in (
        (f"db.sessions[{db_name}]", f"База {db_name}: всего сессий", ""),
        (f"db.fronts[{db_name}]", f"База {db_name}: работающих фронт-офисов", ""),
        (f"db.uptime[{db_name}]", f"База {db_name}: время работы", "дней"),
    ):
        if z.call("item.get", {"hostids": hostid, "search": {"key_": key},
                               "output": ["itemid"]}):
            continue
        z.call("item.create", {"name": name, "key_": key, "hostid": hostid,
                               "type": 2, "value_type": 0, "units": units,
                               "history": "90d", "trends": "1095d"}, )
        created += 1

    for f in fronts:
        key = f"frontoffice.sessions[{f['schema']}]"
        if z.call("item.get", {"hostids": hostid, "search": {"key_": key},
                               "output": ["itemid"]}):
            continue
        z.call("item.create", {
            "name": f"Фронт-офис {f['schema']}: сессий", "key_": key,
            "hostid": hostid, "type": 2, "value_type": 0,
            "history": "90d", "trends": "1095d",
            "description": f"Число подключений схемы {f['schema']} к базе {db_name}.\n"
                           f"Ноль в рабочее время — торговая точка не работает."})
        created += 1
        desc = f"Фронт-офис {f['schema']} ({db_name}) не подключается"
        if not z.call("trigger.get", {"filter": {"description": desc},
                                      "output": ["triggerid"]}):
            z.call("trigger.create", {
                "description": desc, "priority": 3,
                "expression": f"{{{host}:{key}.last()}}=0 and "
                              f"{{{host}:{key}.nodata({NODATA_MIN}m)}}=0",
                "comments": "База работает, но схема этой точки не имеет ни одной "
                            "сессии. Проверить связь с магазином и его сервер."})
    return created


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    data = fo.collect()
    s = fo.summary(data)
    print(f"Сервер {data['host_name']} ({data['host']})")
    for db in data["databases"]:
        print(f"  {db['name']}: {db['status']}, ап {db['uptime_days']} дн, "
              f"сессий {db['sessions']}")
    print(f"Фронт-офисов: {s['fronts']}, из них с активными сессиями: {s['fronts_alive']}")

    if a.dry_run:
        for f in data["fronts"]:
            print(f"   {f['db']:<10} {f['schema']:<24} {f['sessions']}")
        print("\n--dry-run: в Zabbix ничего не создано")
        return

    z = sources.Zabbix()
    gid = ensure_group(z, GROUP)
    values: dict[str, int] = {}
    for db in data["databases"]:
        hostid = ensure_host(z, db, gid)
        host = f"{db['name']}-db"
        fronts = [f for f in data["fronts"] if f["db"] == db["name"]]
        n = ensure_items(z, host, hostid, db["name"], fronts)
        print(f"\n{host}: новых элементов {n}, фронт-офисов {len(fronts)}")
        values[host] = {
            f"db.sessions[{db['name']}]": db["sessions"],
            f"db.fronts[{db['name']}]": len(fronts),
            f"db.uptime[{db['name']}]": db["uptime_days"] or 0,
            **{f"frontoffice.sessions[{f['schema']}]": f["sessions"] for f in fronts},
        }

    total = 0
    for host, vals in values.items():
        res = assets.push_to_zabbix(vals, host=host)
        print(f"   {host}: отправлено {res.get('sent')}, отказов {res.get('failed')}")
        total += res.get("sent", 0)
    print(f"\nвсего отправлено значений: {total}")


if __name__ == "__main__":
    main()
