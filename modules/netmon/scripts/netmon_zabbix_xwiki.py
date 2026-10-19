#!/usr/bin/env python3
"""Ставит вики https://xwiki.una.md на мониторинг Zabbix.

    python modules/netmon/scripts/netmon_zabbix_xwiki.py            # завести
    python modules/netmon/scripts/netmon_zabbix_xwiki.py --dry-run  # только показать

Что было до этого: сервер вики 192.168.0.15 (хост «xwiki», Windows Server
2003, GlassFish 3.1.1 + Java 1.7) стоял на агенте — процессор, память,
диски. Самого сайта в мониторинге не было: GlassFish мог зависнуть при
живой машине, и никто бы не узнал.

Что заводится (повторный запуск ничего не дублирует):

1. Хост сайта «xwiki.una.md» в группе Domains — так же, как
   nufarul.eminescu.md: шаблон Template Web (страница отвечает 200) и
   Template SSL Check (срок сертификата).
2. На нём веб-сценарий «XWiki» из двух шагов — главная страница вики (в
   ответе должна быть метка XWiki, а не заглушка nginx) и встроенный поиск
   вики (он ходит в базу cloudbd, значит проверяет и её). Триггеры: вики не
   открывается; вики отвечает медленнее 5 секунд.
3. На сервере вики — простая проверка порта GlassFish 8080 из Zabbix и
   триггер, если порт не отвечает: так видно, что упал именно сервер
   приложений, а не сеть или nginx.

Веб-сценарии выполняет сам сервер Zabbix — расписания cron не нужно.
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

SITE = "xwiki.una.md"
SITE_URL = f"https://{SITE}"
SERVER_HOST = "amd64"              # техническое имя хоста сервера вики в Zabbix
SERVER_IP = "192.168.0.15"
GLASSFISH_PORT = 8080
SCENARIO = "XWiki"
STEPS = [
    {"name": "Главная", "url": f"{SITE_URL}/bin/view/UNA/WebHome",
     "required": 'name="wiki" content="xwiki"', "status_codes": "200", "timeout": "15s"},
    {"name": "Поиск", "url": f"{SITE_URL}/bin/view/Main/Search?text=una",
     "required": "", "status_codes": "200", "timeout": "20s"},
]
SLOW_SEC = 5
SERVER_DESCR = (f"Сервер вики {SITE_URL}: Windows Server 2003, GlassFish 3.1.1 (Java 1.7), "
                f"порт приложения {GLASSFISH_PORT}. Снаружи — через nginx на 192.168.0.148.\n"
                "База вики — схема XWIKI в Oracle cloudbd (192.168.0.24).\n"
                "Мониторинг сайта — хост xwiki.una.md (modules/netmon/scripts/netmon_zabbix_xwiki.py).")


def plan() -> list[str]:
    return [
        f"хост {SITE}: группа Domains, шаблоны Template Web + Template SSL Check",
        f"веб-сценарий «{SCENARIO}»: " + "; ".join(f"{s['name']} — {s['url']}" for s in STEPS),
        f"триггер: вики не открывается; вики отвечает дольше {SLOW_SEC} с",
        f"сервер {SERVER_HOST} ({SERVER_IP}): проверка порта GlassFish {GLASSFISH_PORT} и триггер",
    ]


def one(z, method: str, params: dict):
    r = z.call(method, params)
    return r[0] if r else None


def ensure_site_host(z) -> str:
    h = one(z, "host.get", {"filter": {"host": SITE}, "output": ["hostid"]})
    if h:
        return h["hostid"]
    group = one(z, "hostgroup.get", {"filter": {"name": "Domains"}, "output": ["groupid"]})
    tpls = z.call("template.get", {"filter": {"host": ["Template Web", "Template SSL Check"]},
                                   "output": ["templateid"]})
    hid = z.call("host.create", {
        "host": SITE, "name": SITE,
        "groups": [{"groupid": group["groupid"]}],
        "templates": [{"templateid": t["templateid"]} for t in tpls],
        "interfaces": [{"type": 1, "main": 1, "useip": 0, "ip": "127.0.0.1", "dns": SITE, "port": "10050"}],
        "macros": [{"macro": "{$SSL_HOST}", "value": SITE}, {"macro": "{$SSL_PORT}", "value": "443"}],
        "description": f"Вики компании {SITE_URL}. Сервер — хост «xwiki» ({SERVER_IP})."})["hostids"][0]
    print(f"  создан хост {SITE}")
    return hid


def ensure_scenario(z, hostid: str) -> None:
    if not one(z, "httptest.get", {"hostids": hostid, "filter": {"name": SCENARIO}, "output": ["httptestid"]}):
        z.call("httptest.create", {
            "name": SCENARIO, "hostid": hostid, "delay": "60s", "retries": 2, "agent": "Zabbix",
            "steps": [{**s, "no": i + 1, "follow_redirects": 1} for i, s in enumerate(STEPS)]})
        print(f"  создан веб-сценарий «{SCENARIO}»")
    triggers = [
        (f"Вики {SITE} не открывается",
         f"{{{SITE}:web.test.fail[{SCENARIO}].last()}}<>0 and {{{SITE}:web.test.fail[{SCENARIO}].min(3m)}}<>0",
         4, "Главная страница или поиск вики не отвечают три минуты подряд. Проверить хост «xwiki» "
            f"({SERVER_IP}): жив ли GlassFish на порту {GLASSFISH_PORT} и есть ли место на дисках."),
        (f"Вики {SITE} отвечает медленно",
         f"{{{SITE}:web.test.time[{SCENARIO},{STEPS[0]['name']},resp].avg(5m)}}>{SLOW_SEC}",
         2, f"Главная страница вики открывается дольше {SLOW_SEC} с в среднем за 5 минут."),
    ]
    for desc, expr, prio, comments in triggers:
        if not one(z, "trigger.get", {"filter": {"description": desc}, "output": ["triggerid"]}):
            z.call("trigger.create", {"description": desc, "expression": expr, "priority": prio,
                                      "comments": comments})
            print(f"  создан триггер «{desc}»")


def ensure_server_checks(z) -> None:
    h = one(z, "host.get", {"filter": {"host": SERVER_HOST}, "output": ["hostid", "description"],
                            "selectInterfaces": ["interfaceid", "ip", "type"]})
    if not h:
        print(f"  ! хоста {SERVER_HOST} нет в Zabbix — проверка порта не заведена")
        return
    if not (h.get("description") or "").strip():
        z.call("host.update", {"hostid": h["hostid"], "description": SERVER_DESCR})
        print(f"  описание хоста {SERVER_HOST} заполнено")
    key = f"net.tcp.service[tcp,,{GLASSFISH_PORT}]"
    if not one(z, "item.get", {"hostids": h["hostid"], "filter": {"key_": key}, "output": ["itemid"]}):
        agent_if = next(i for i in h["interfaces"] if i["type"] == "1")
        z.call("item.create", {
            "name": f"GlassFish (XWiki): порт {GLASSFISH_PORT}", "key_": key, "hostid": h["hostid"],
            "type": 3, "value_type": 3, "delay": "60s", "interfaceid": agent_if["interfaceid"],
            "history": "30d", "trends": "365d",
            "description": "1 — сервер приложений с вики принимает соединения, 0 — нет."})
        print(f"  создана проверка {key}")
    desc = f"GlassFish с вики не отвечает на порту {GLASSFISH_PORT} ({SERVER_IP})"
    if not one(z, "trigger.get", {"filter": {"description": desc}, "output": ["triggerid"]}):
        z.call("trigger.create", {
            "description": desc, "priority": 4,
            "expression": f"{{{SERVER_HOST}:{key}.max(3m)}}=0",
            "comments": "Машина жива, но сервер приложений с вики не принимает соединения. "
                        "Перезапустить службу GlassFish на 192.168.0.15; при ошибке записи — "
                        "сначала освободить место на дисках C: и D:."})
        print(f"  создан триггер «{desc}»")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    for line in plan():
        print("·", line)
    if a.dry_run:
        print("--dry-run: в Zabbix ничего не создано")
        return
    z = sources.Zabbix()
    hostid = ensure_site_host(z)
    ensure_scenario(z, hostid)
    ensure_server_checks(z)
    print("готово")


if __name__ == "__main__":
    main()
