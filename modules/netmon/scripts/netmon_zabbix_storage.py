#!/usr/bin/env python3
"""Заводит в Zabbix наблюдение за дисками сервера баз данных и за OpenVPN.

    python modules/netmon/scripts/netmon_zabbix_storage.py            # завести и отправить
    python modules/netmon/scripts/netmon_zabbix_storage.py --dry-run  # только показать

Оба раздела появились по итогам аудита UPNET 2021 и закрывают одну и ту же
беду — «проблему видно только когда уже поздно».

**Диски.** На cloudbd стоит аппаратный контроллер LSI 3108: система видит
четыре логических тома, а не восемь физических дисков. Поэтому штатная
проверка `smartctl /dev/sda` отвечает «OK» даже при сдохшем диске в
зеркале, а `/proc/mdstat` пуст. Значения снимаются с самого контроллера
через `MegaCli64` и шлются трапперами: состояние томов, число дисков не в
строю, предсказания отказа, температура, батарея кэша, заполнение разделов.

**OpenVPN.** Через него идёт вся удалённая работа с офисом. Следим за
службой, числом подключённых и числом действующих сертификатов: рост
последнего без ведома администратора означает выданный и забытый доступ
во всю плоскую сеть.

Значения шлёт `zabbix_sender`; расписание — cron, как у остальных сборщиков.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

from modules.netmon import assets, mikrotik as mt, openvpn as ov, sources, storage as st  # noqa: E402

GROUP = "Infrastructure Health"
ST_HOST = "cloudbd-storage"
VPN_HOST = "office-openvpn"
MT_HOST = "office-mikrotik"

# Элементы держателя показателей дисков.
# ВАЖНО: value_type 0 (float), а не 3 (unsigned). На unsigned Zabbix молча
# превращает отрицательное значение в 0 — на этом уже попадались с
# просрочкой обслуживания, где «минус десять дней» становилось нулём.
ST_ITEMS = [
    ("raid.volumes.bad", "RAID: томов не в норме", "",
     "Сколько логических томов контроллера не в состоянии Optimal. "
     "Больше нуля — зеркало неполно или разрушено."),
    ("raid.disks.bad", "RAID: физических дисков не в строю", "",
     "Диски за контроллером, чьё состояние не Online. Это единственный "
     "способ узнать об отказе: система такого диска не видит вовсе."),
    ("raid.disks.predictive", "RAID: предсказаний отказа диска", "",
     "Контроллер считает, что диск скоро умрёт. Менять до отказа, пока "
     "зеркало целое и данные можно перестроить."),
    ("raid.disks.errors", "RAID: ошибок чтения на дисках", "",
     "Суммарный счётчик ошибок чтения. Важен рост, а не само значение."),
    ("raid.temp.max", "RAID: температура самого горячего диска", "°C",
     "Рабочий предел дисков — 60 °C. 45 °C и выше — проверить вентиляцию."),
    ("raid.bbu.ok", "RAID: батарея кэша в порядке", "",
     "1 — Optimal, 0 — неисправна. При неисправной батарее контроллер "
     "отключает отложенную запись, и база резко замедляется, а в логах "
     "Oracle причины не видно."),
    ("raid.redundancy", "RAID: избыточность есть", "",
     "1 — все тома зеркалированы. 0 — отказ одного диска означает потерю тома."),
    ("disk.fullest", "Разделы: самый заполненный", "%",
     "Oracle при нехватке места под архивные журналы останавливает запись."),
    ("storage.findings.crit", "Диски: опасных замечаний", "",
     "Сколько находок уровня «опасно» на вкладке «Диски сервера БД»."),
]

VPN_ITEMS = [
    ("vpn.service.up", "OpenVPN: служба работает", "",
     "1 — active. Ноль означает, что удалённая работа с офисом невозможна "
     "полностью: ни SSH, ни бэк-офис, ни база."),
    ("vpn.clients.online", "OpenVPN: подключено клиентов", "",
     "Сколько сотрудников сейчас в туннеле."),
    ("vpn.certs.valid", "OpenVPN: действующих сертификатов", "",
     "Каждый сертификат открывает всю плоскую сеть целиком (аудит 2021, "
     "п. 2.1.8). Рост без ведома администратора — повод для разбора."),
    ("vpn.certs.revoked", "OpenVPN: отозванных сертификатов", "", ""),
    ("vpn.revocation.works", "OpenVPN: отзыв доступа действует", "",
     "1 — служба перечитывает список отзыва. 0 — отзыв не действует ни для "
     "кого: сертификат помечается отозванным, а человек продолжает "
     "подключаться. Тихая поломка, снаружи неотличимая от исправной работы."),
]

# Пороги. Для дисков «больше нуля» — уже проблема, поэтому severity высокая:
# резервных копий базы нет, второй отказ в том же зеркале означает потерю данных.
ST_TRIGGERS = [
    ("raid.volumes.bad", ">0", 5, "Том RAID на cloudbd не в состоянии Optimal",
     "Зеркало неполно или разрушено. Резервных копий базы нет — менять диск "
     "немедленно. Что именно: MegaCli64 -LDInfo -Lall -aALL"),
    ("raid.disks.bad", ">0", 5, "Диск за контроллером cloudbd вышел из строя",
     "Зеркало держится на одном диске. Штатный smartctl этого не покажет: "
     "система видит только тома. MegaCli64 -PDList -aALL"),
    ("raid.disks.predictive", ">0", 4, "Контроллер cloudbd предсказывает отказ диска",
     "Заменить, не дожидаясь отказа, пока зеркало целое."),
    ("raid.bbu.ok", "=0", 4, "Батарея кэша контроллера cloudbd неисправна",
     "Контроллер отключит отложенную запись — база резко замедлится без "
     "видимой причины в логах Oracle."),
    ("raid.redundancy", "=0", 5, "На cloudbd пропала избыточность дисков",
     "Отказ одного диска означает потерю тома. Резервных копий нет."),
    ("raid.temp.max", ">=55", 3, "Диски cloudbd перегреваются",
     "Проверить вентиляторы корпуса и пыль в отсеке дисков."),
    ("disk.fullest", ">=92", 4, "Раздел на cloudbd почти заполнен",
     "Расчистить или перенести. Для /db это остановка записи Oracle."),
]

VPN_TRIGGERS = [
    ("vpn.revocation.works", "=0", 5, "Отзыв доступа OpenVPN не действует",
     "Служба не может прочитать список отзыва и работает со списком, "
     "загруженным при запуске. Отозванные сертификаты продолжают пускать "
     "в сеть. Проверить путь crl-verify и права по всему пути к файлу."),
    ("vpn.service.up", "=0", 5, "Служба OpenVPN в офисе остановлена",
     "Удалённая работа с офисом невозможна полностью. "
     "systemctl status openvpn-server@server на 192.168.0.200"),
]


MT_ITEMS = [
    ("mt.ppp.online", "MikroTik: VPN-сессий сейчас", "", "PPP-сессии на главном маршрутизаторе."),
    ("mt.ppp.pptp", "MikroTik: из них по PPTP", "",
     "PPTP защищён MS-CHAPv2, который взламывается перебором. Цель — ноль."),
    ("mt.ppp.enabled", "MikroTik: включённых учёток VPN", "",
     "Рост без ведома администратора — повод для разбора: каждая учётка — вход в сеть."),
    ("mt.ppp.never", "MikroTik: включённых учёток, ни разу не входивших", "", ""),
    ("mt.cpu", "MikroTik: загрузка ЦП", "%", ""),
]

MT_TRIGGERS = [
    ("mt.cpu", ">=90", 3, "Маршрутизатор MikroTik загружен на 90 % и больше",
     "Это шлюз всей сети: при перегрузке тормозит всё. /tool profile на маршрутизаторе."),
]


def ensure_group(z, name: str) -> str:
    g = z.call("hostgroup.get", {"filter": {"name": name}, "output": ["groupid"]})
    return g[0]["groupid"] if g else z.call("hostgroup.create", {"name": name})["groupids"][0]


def ensure_host(z, host: str, visible: str, ip: str, gid: str, descr: str) -> str:
    ex = z.call("host.get", {"filter": {"host": host}, "output": ["hostid"]})
    if ex:
        return ex[0]["hostid"]
    return z.call("host.create", {
        "host": host, "name": visible,
        "interfaces": [{"type": 1, "main": 1, "useip": 1, "ip": ip,
                        "dns": "", "port": "10050"}],
        "groups": [{"groupid": gid}], "description": descr})["hostids"][0]


def ensure_items(z, hostid: str, items: list[tuple]) -> int:
    created = 0
    for key, name, units, descr in items:
        if z.call("item.get", {"hostids": hostid, "filter": {"key_": key},
                               "output": ["itemid"]}):
            continue
        z.call("item.create", {
            "name": name, "key_": key, "hostid": hostid,
            "type": 2, "value_type": 0, "units": units,
            "history": "180d", "trends": "1095d", "description": descr})
        created += 1
    return created


def ensure_triggers(z, host: str, triggers: list[tuple]) -> int:
    created = 0
    for key, cond, sev, descr, comment in triggers:
        if z.call("trigger.get", {"filter": {"description": descr},
                                  "output": ["triggerid"]}):
            continue
        z.call("trigger.create", {
            "description": descr, "priority": sev,
            "expression": f"{{{host}:{key}.last()}}{cond}",
            "comments": comment})
        created += 1
    return created


def storage_values(d: dict) -> dict:
    s = st.summary(d)
    phys = d.get("physical", [])
    return {
        "raid.volumes.bad": s["volumes"] - s["volumes_ok"],
        "raid.disks.bad": s["disks"] - s["disks_ok"],
        "raid.disks.predictive": sum(x["predictive"] for x in phys),
        "raid.disks.errors": sum(x["media_errors"] for x in phys),
        "raid.temp.max": s["temp_max"] or 0,
        "raid.bbu.ok": 1 if d.get("controller", {}).get("bbu_ok") else 0,
        "raid.redundancy": 1 if s["redundancy"] else 0,
        "disk.fullest": s["fullest"],
        "storage.findings.crit": s["crit"],
    }


def vpn_values(d: dict) -> dict:
    s = ov.summary(d)
    return {
        "vpn.service.up": 1 if s["running"] else 0,
        "vpn.clients.online": s["online"],
        "vpn.certs.valid": s["certs_valid"],
        "vpn.certs.revoked": s["certs_revoked"],
        "vpn.revocation.works": 1 if s["revocation_works"] else 0,
    }


def mikrotik_values(d: dict) -> dict:
    s = mt.summary(d)
    return {"mt.ppp.online": s["online"], "mt.ppp.pptp": s["online_pptp"],
            "mt.ppp.enabled": s["enabled"], "mt.ppp.never": s["never_logged"],
            "mt.cpu": s["cpu_load"] or 0}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", choices=("storage", "vpn", "mikrotik"), help="только один раздел")
    a = ap.parse_args()

    todo = ("storage", "vpn", "mikrotik") if not a.only else (a.only,)
    data: dict[str, dict] = {}

    if "storage" in todo:
        d = st.collect()
        data["storage"] = d
        s = st.summary(d)
        print(f"Диски {d['host_name']}: контроллер {s['controller']}, "
              f"томов {s['volumes_ok']}/{s['volumes']}, дисков {s['disks_ok']}/{s['disks']}, "
              f"батарея {s['bbu']}, горячее всего {s['temp_max']} °C, "
              f"самый полный раздел {s['fullest']} %")
        for f in d["findings"]:
            print(f"   [{f['level']}] {f['title']}")

    if "vpn" in todo:
        d = ov.status()
        data["vpn"] = d
        s = ov.summary(d)
        print(f"OpenVPN {ov.HOST}: служба {'работает' if s['running'] else 'ОСТАНОВЛЕНА'}, "
              f"в сети {s['online']}, доступов {s['certs_valid']}, "
              f"отозвано {s['certs_revoked']}")

    if "mikrotik" in todo:
        d = mt.status()
        data["mikrotik"] = d
        s = mt.summary(d)
        print(f"MikroTik {mt.HOST}: в сети {s['online']} (PPTP {s['online_pptp']}), "
              f"включено учёток {s['enabled']}, ЦП {s['cpu_load']} %")

    if a.dry_run:
        for k, d in data.items():
            vals = {"storage": storage_values, "vpn": vpn_values, "mikrotik": mikrotik_values}[k](d)
            print(f"\n{k}: значения к отправке")
            for key, v in vals.items():
                print(f"   {key:<28} {v}")
        print("\n--dry-run: в Zabbix ничего не создано")
        return

    z = sources.Zabbix()
    gid = ensure_group(z, GROUP)
    sent_total = 0

    if "storage" in data:
        hostid = ensure_host(
            z, ST_HOST, "Диски сервера баз данных cloudbd", st.HOST, gid,
            "Держатель показателей аппаратного RAID сервера cloudbd.\n"
            "Значения снимает модуль netmon через MegaCli64 на самом сервере.\n"
            "ЗАЧЕМ ТАК: система видит только логические тома контроллера, "
            "поэтому smartctl /dev/sda отвечает OK даже при сдохшем диске в "
            "зеркале, а /proc/mdstat пуст. Разбор: docs/Netmon/STORAGE.md")
        n = ensure_items(z, hostid, ST_ITEMS)
        t = ensure_triggers(z, ST_HOST, ST_TRIGGERS)
        print(f"\n{ST_HOST}: новых элементов {n}, новых триггеров {t}")
        res = assets.push_to_zabbix(storage_values(data["storage"]), host=ST_HOST)
        print(f"   отправлено {res.get('sent')}, отказов {res.get('failed')}")
        sent_total += res.get("sent", 0)

    if "vpn" in data:
        hostid = ensure_host(
            z, VPN_HOST, "OpenVPN офиса", ov.HOST, gid,
            f"Сервер удалённого доступа в офисную сеть, виртуальная машина "
            f"{ov.VM_ID}, снаружи {ov.PUBLIC_ENDPOINT}.\n"
            "Через него идёт вся удалённая работа. Каждый выданный сертификат "
            "открывает всю плоскую сеть целиком — замечание аудита 2021, "
            "п. 2.1.8. Разбор: docs/Netmon/OPENVPN.md")
        n = ensure_items(z, hostid, VPN_ITEMS)
        t = ensure_triggers(z, VPN_HOST, VPN_TRIGGERS)
        print(f"\n{VPN_HOST}: новых элементов {n}, новых триггеров {t}")
        res = assets.push_to_zabbix(vpn_values(data["vpn"]), host=VPN_HOST)
        print(f"   отправлено {res.get('sent')}, отказов {res.get('failed')}")
        sent_total += res.get("sent", 0)

    if "mikrotik" in data:
        hostid = ensure_host(
            z, MT_HOST, "MikroTik офиса — VPN", mt.HOST, gid,
            "Главный маршрутизатор офиса, шлюз всей сети. Держатель показателей VPN: "
            "сессии PPP, доля PPTP, число включённых учёток. Значения снимает модуль "
            "netmon по SSH. Разбор: docs/Netmon/MIKROTIK.md")
        n = ensure_items(z, hostid, MT_ITEMS)
        t = ensure_triggers(z, MT_HOST, MT_TRIGGERS)
        print(f"\n{MT_HOST}: новых элементов {n}, новых триггеров {t}")
        res = assets.push_to_zabbix(mikrotik_values(data["mikrotik"]), host=MT_HOST)
        print(f"   отправлено {res.get('sent')}, отказов {res.get('failed')}")
        sent_total += res.get("sent", 0)

    print(f"\nвсего отправлено значений: {sent_total}")


if __name__ == "__main__":
    main()
