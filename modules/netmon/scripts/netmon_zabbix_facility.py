#!/usr/bin/env python3
"""Заводит инженерное оборудование офиса в Zabbix.

    python modules/netmon/scripts/netmon_zabbix_facility.py            # завести и обновить
    python modules/netmon/scripts/netmon_zabbix_facility.py --dry-run  # только показать

Делает две разные вещи, потому что оборудование двух разных природ:

1. **Умные розетки** есть в сети — их Zabbix опрашивает сам: ICMP плюс
   проверка порта 6668 (живёт ли служба управления, а не только железка).
   Розетки уже были заведены прошлым сканом как «сетевое оборудование» —
   здесь они переименовываются и получают верный класс, без создания дублей.

2. **Кондиционеры, котёл, СКУД, лифт** в сеть не включены. Для них заводится
   хост-держатель `facility-metrics`: модуль считает, сколько дней осталось
   до регламентного обслуживания, и шлёт число в Zabbix. Просрочка
   становится обычной проблемой Zabbix и уходит в Telegram тем же путём,
   что и всё остальное.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

from modules.netmon import assets, facility as fac, sources, store  # noqa: E402

FACILITY_HOST = "facility-metrics"
FACILITY_GROUP = "Office Facility"
PLUG_TEMPLATE = "Template ICMP Ping"


def ensure_group(z, name: str) -> str:
    g = z.call("hostgroup.get", {"filter": {"name": name}, "output": ["groupid"]})
    return g[0]["groupid"] if g else z.call("hostgroup.create", {"name": name})["groupids"][0]


def plug_hosts(z, dry: bool) -> list[str]:
    """Розетки: верное имя, класс и проверка службы управления."""
    done = []
    gid = ensure_group(z, FACILITY_GROUP)
    tpl = z.call("template.get", {"filter": {"host": PLUG_TEMPLATE}, "output": ["templateid"]})
    tplid = tpl[0]["templateid"] if tpl else None

    for f in store.facilities(kind="smartplug"):
        ip = f["ip"]
        found = [h for h in z.call("host.get", {"output": ["hostid", "host"],
                                                "selectInterfaces": ["interfaceid", "ip"],
                                                "selectGroups": ["groupid"]})
                 if any(i["ip"] == ip for i in h.get("interfaces", []))]
        name = f"plug-{ip.rsplit('.', 1)[-1]}"
        descr = (f"Умная розетка Tuya, протокол 3.4 (порт 6668).\n"
                 f"Код в реестре оборудования: {f['code']}.\n"
                 f"Помещение: {f['room'] or 'не уточнено'}.\n"
                 f"Управление: панель netmon, вкладка «Оборудование офиса».")
        if dry:
            done.append(f"{name} ← {found[0]['host'] if found else 'создать'} ({ip})")
            continue

        if found:
            h = found[0]
            groups = [{"groupid": g["groupid"]} for g in h.get("groups", [])]
            if gid not in [g["groupid"] for g in h.get("groups", [])]:
                groups.append({"groupid": gid})
            z.call("host.update", {"hostid": h["hostid"], "host": name,
                                   "name": f"Умная розетка {ip}",
                                   "description": descr, "groups": groups})
            hostid, ifid = h["hostid"], h["interfaces"][0]["interfaceid"]
        else:
            created = z.call("host.create", {
                "host": name, "name": f"Умная розетка {ip}",
                "interfaces": [{"type": 1, "main": 1, "useip": 1, "ip": ip,
                                "dns": "", "port": "10050"}],
                "groups": [{"groupid": gid}],
                "templates": [{"templateid": tplid}] if tplid else [],
                "description": descr})
            hostid = created["hostids"][0]
            ifid = z.call("hostinterface.get", {"hostids": hostid,
                                                "output": ["interfaceid"]})[0]["interfaceid"]

        # проверка службы управления: порт открыт — розетка отвечает на команды
        key = "net.tcp.service[tcp,,6668]"
        if not z.call("item.get", {"hostids": hostid, "search": {"key_": key},
                                   "output": ["itemid"]}):
            z.call("item.create", {
                "name": "Служба управления Tuya (порт 6668)", "key_": key,
                "hostid": hostid, "type": 3, "value_type": 3, "interfaceid": ifid,
                "delay": 120, "history": "30d", "trends": "365d",
                "description": "1 — розетка принимает подключение и управляема, "
                               "0 — служба не отвечает, хотя узел может пинговаться."})
            trg = f"Умная розетка {ip}: служба управления не отвечает"
            if not z.call("trigger.get", {"filter": {"description": trg},
                                          "output": ["triggerid"]}):
                z.call("trigger.create", {
                    "description": trg, "priority": 2,
                    "expression": f"{{{name}:{key}.last()}}=0 and "
                                  f"{{{name}:{key}.nodata(10m)}}=0",
                    "comments": "Розетка в сети, но порт 6668 закрыт: питание "
                                "подано, а управление недоступно."})
        done.append(f"{name} ({ip})")
    return done


def facility_host(z, dry: bool) -> tuple[str, int]:
    """Хост-держатель для оборудования вне сети + элементы и триггеры."""
    gid = ensure_group(z, FACILITY_GROUP)
    ex = z.call("host.get", {"filter": {"host": FACILITY_HOST}, "output": ["hostid"]})
    if dry:
        return ("есть" if ex else "создать"), 0
    if ex:
        hostid = ex[0]["hostid"]
    else:
        hostid = z.call("host.create", {
            "host": FACILITY_HOST, "name": "Инженерное оборудование офиса",
            "interfaces": [{"type": 1, "main": 1, "useip": 1, "ip": "127.0.0.1",
                            "dns": "", "port": "10050"}],
            "groups": [{"groupid": gid}],
            "description": "Кондиционеры, котёл, контроль доступа, лифт — в сеть "
                           "не включены. Сроки обслуживания считает модуль netmon "
                           "и присылает сюда через zabbix_sender.",
        })["hostids"][0]

    created = 0
    for f in store.facilities():
        if f["kind"] == "smartplug":
            continue          # у розеток есть собственный хост с опросом
        key = f"facility.days[{f['code']}]"
        if z.call("item.get", {"hostids": hostid, "search": {"key_": key},
                               "output": ["itemid"]}):
            continue
        z.call("item.create", {
            "name": f"{f['name']}: дней до обслуживания", "key_": key,
            "hostid": hostid, "type": 2, "value_type": 3, "units": "дней",
            "history": "365d", "trends": "1095d",
            "description": f"Помещение: {f['room']}. Регламент: {f['service_days']} дней.\n"
                           f"Отрицательное значение — просрочка."})
        created += 1
        for desc, expr, prio in (
            (f"{f['name']}: обслуживание просрочено",
             f"{{{FACILITY_HOST}:{key}.last()}}<0", 3),
            (f"{f['name']}: обслуживание подходит (менее 7 дней)",
             f"{{{FACILITY_HOST}:{key}.last()}}>=0 and {{{FACILITY_HOST}:{key}.last()}}<7", 2),
        ):
            if not z.call("trigger.get", {"filter": {"description": desc},
                                          "output": ["triggerid"]}):
                z.call("trigger.create", {"description": desc, "expression": expr,
                                          "priority": prio,
                                          "comments": "Значение присылает модуль netmon "
                                                      "по журналу работ."})
    return ("создан" if not ex else "обновлён"), created


def facility_values() -> dict:
    """Сколько дней осталось до обслуживания каждого объекта.

    Берём самый срочный вид работ по объекту: если фильтры просрочены на 10
    дней, а осмотр только через месяц — показываем −10.
    """
    vals = {}
    today = date.today()
    for f in store.facilities():
        if f["kind"] == "smartplug":
            continue
        rules = fac.SERVICE_RULES.get(f["kind"], {})
        worst = None
        for work, days in rules.items():
            if not days:
                continue
            last = (f.get("last_works") or {}).get(work)
            if not last:
                worst = -999 if worst is None else min(worst, -999)
                continue
            left = (date.fromisoformat(last) + __import__("datetime").timedelta(days=days) - today).days
            worst = left if worst is None else min(worst, left)
        if worst is not None:
            vals[f"facility.days[{f['code']}]"] = worst
    return vals


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    z = sources.Zabbix()
    print("Умные розетки (опрашиваются Zabbix напрямую):")
    for line in plug_hosts(z, a.dry_run):
        print("  ", line)

    state, items = facility_host(z, a.dry_run)
    print(f"\nХост {FACILITY_HOST}: {state}, новых элементов {items}")

    if a.dry_run:
        print("\n--dry-run: значения не отправлялись")
        return

    vals = facility_values()
    print("\nСроки обслуживания:")
    for k, v in sorted(vals.items()):
        mark = "просрочено" if v < 0 else f"через {v} дн"
        print(f"   {k:<34} {v:>6}  {mark if v > -999 else 'работ не было'}")
    res = assets.push_to_zabbix(vals, host=FACILITY_HOST)
    print(f"\nотправлено в Zabbix: {res.get('sent')} значений, отказов {res.get('failed')}")


if __name__ == "__main__":
    main()
