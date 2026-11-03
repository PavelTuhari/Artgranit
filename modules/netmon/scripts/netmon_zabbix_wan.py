#!/usr/bin/env python3
"""Каналы интернета офиса и OTRS — на мониторинг Zabbix.

    python modules/netmon/scripts/netmon_zabbix_wan.py            # завести
    python modules/netmon/scripts/netmon_zabbix_wan.py --dry-run  # только показать

Случай 03.11.2026: у провайдера МТС перестал отвечать шлюз 93.115.136.17.
Кабель в порту маршрутизатора был, адрес 93.115.136.18 на нём был, весь
трафик офиса сам ушёл на второй канал Orange — изнутри всё работало. А снаружи
пропало всё, что смотрит на адрес МТС: OpenVPN (проброс UDP 1194 только на
нём), L2TP у тех, кому выдан этот адрес, otrs.una.md и xwiki.una.md (DNS на
адрес МТС). Шлюз Orange был в Zabbix, шлюза МТС — нет, поэтому падение
никто не заметил.

Что заводится (повторный запуск ничего не дублирует):

1. Хост «GW MTC» (93.115.136.17) в группе IPs с шаблоном Template ICMP Ping —
   так же, как уже есть «GW Orange» (195.22.241.125). Шлюз стоит в подсети,
   подключённой к маршрутизатору напрямую, поэтому проверка изнутри честно
   показывает, жив ли канал провайдера.
2. Триггеры с объяснением, что ломается: «канал МТС не работает» (высокий) и
   «оба канала не работают» (катастрофа).
3. Хост «otrs.una.md» в группе Domains — как xwiki.una.md: Template Web (страница
   отвечает) и Template SSL Check (срок сертификата) и сценарий «OTRS» со
   страницей входа.

Проверки выполняет сам сервер Zabbix — cron не нужен.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

from modules.netmon import sources  # noqa: E402

GW = {"mtc": ("93.115.136.17", "GW MTC"), "orange": ("195.22.241.125", "GW Orange")}
OTRS = "otrs.una.md"
OTRS_STEP = {"name": "Вход", "url": f"https://{OTRS}/otrs/index.pl", "required": "OTRS",
             "status_codes": "200", "timeout": "20s"}
MTC_BROKEN = ("Снаружи недоступно всё, что смотрит на адрес МТС 93.115.136.18: OpenVPN (проброс UDP 1194 "
              "только на нём), L2TP/PPTP у тех, кому выдан этот адрес, otrs.una.md, xwiki.una.md, vpn.una.md, "
              "ns1.una.md. Внутри офиса всё работает — трафик уходит через Orange. Звонить в МТС; пока канал "
              "лежит — входить через Orange 195.22.241.126.")


def one(z, method: str, params: dict):
    r = z.call(method, params)
    return r[0] if r else None


def ensure_gw(z, ip: str, name: str) -> str:
    h = one(z, "host.get", {"filter": {"host": ip}, "output": ["hostid"]})
    if h:
        return ip
    group = one(z, "hostgroup.get", {"filter": {"name": "IPs"}, "output": ["groupid"]})
    tpl = one(z, "template.get", {"filter": {"host": "Template ICMP Ping"}, "output": ["templateid"]})
    z.call("host.create", {"host": ip, "name": name, "groups": [{"groupid": group["groupid"]}],
                           "templates": [{"templateid": tpl["templateid"]}],
                           "interfaces": [{"type": 1, "main": 1, "useip": 1, "ip": ip, "dns": "", "port": "10050"}],
                           "description": "Шлюз провайдера на стороне офиса. Не отвечает — канал провайдера лежит."})
    print(f"  создан хост {name} ({ip})")
    return ip


def ensure_trigger(z, desc: str, expr: str, prio: int, comments: str) -> None:
    if not one(z, "trigger.get", {"filter": {"description": desc}, "output": ["triggerid"]}):
        z.call("trigger.create", {"description": desc, "expression": expr, "priority": prio, "comments": comments})
        print(f"  создан триггер «{desc}»")


def ensure_otrs(z) -> None:
    h = one(z, "host.get", {"filter": {"host": OTRS}, "output": ["hostid"]})
    if h:
        hid = h["hostid"]
    else:
        group = one(z, "hostgroup.get", {"filter": {"name": "Domains"}, "output": ["groupid"]})
        tpls = z.call("template.get", {"filter": {"host": ["Template Web", "Template SSL Check"]}, "output": ["templateid"]})
        hid = z.call("host.create", {
            "host": OTRS, "name": OTRS, "groups": [{"groupid": group["groupid"]}],
            "templates": [{"templateid": t["templateid"]} for t in tpls],
            "interfaces": [{"type": 1, "main": 1, "useip": 0, "ip": "127.0.0.1", "dns": OTRS, "port": "10050"}],
            "macros": [{"macro": "{$SSL_HOST}", "value": OTRS}, {"macro": "{$SSL_PORT}", "value": "443"}],
            "description": "Заявки OTRS https://otrs.una.md/otrs/index.pl — сервер 192.168.0.51, снаружи через "
                           "nginx 192.168.0.148."})["hostids"][0]
        print(f"  создан хост {OTRS}")
    if not one(z, "httptest.get", {"hostids": hid, "filter": {"name": "OTRS"}, "output": ["httptestid"]}):
        z.call("httptest.create", {"name": "OTRS", "hostid": hid, "delay": "60s", "retries": 2, "agent": "Zabbix",
                                   "steps": [{**OTRS_STEP, "no": 1, "follow_redirects": 1}]})
        print("  создан веб-сценарий «OTRS»")
    ensure_trigger(z, f"OTRS {OTRS} не открывается",
                   f"{{{OTRS}:web.test.fail[OTRS].last()}}<>0 and {{{OTRS}:web.test.fail[OTRS].min(3m)}}<>0", 4,
                   "Страница входа OTRS не отвечает три минуты подряд. Проверить сервер 192.168.0.51 (apache, "
                   "база cloudbd) и nginx на 192.168.0.148.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    print("· шлюзы провайдеров: GW MTC 93.115.136.17 (новый), GW Orange 195.22.241.125 (есть) — ICMP")
    print("· триггеры: канал МТС не работает; оба канала не работают")
    print(f"· {OTRS}: Template Web + SSL Check + сценарий «OTRS»")
    if a.dry_run:
        print("--dry-run: в Zabbix ничего не создано")
        return
    z = sources.Zabbix()
    mtc = ensure_gw(z, *GW["mtc"])
    orange = ensure_gw(z, *GW["orange"])
    ensure_trigger(z, "Канал интернета МТС не работает (шлюз 93.115.136.17)",
                   f"{{{mtc}:icmpping.max(3m)}}=0", 4, MTC_BROKEN)
    ensure_trigger(z, "Офис без интернета: не работают оба канала, МТС и Orange",
                   f"{{{mtc}:icmpping.max(3m)}}=0 and {{{orange}:icmpping.max(3m)}}=0", 5,
                   "Не отвечают шлюзы обоих провайдеров. Проверить маршрутизатор 192.168.0.101 и звонить провайдерам.")
    ensure_otrs(z)
    print("готово")


if __name__ == "__main__":
    main()
