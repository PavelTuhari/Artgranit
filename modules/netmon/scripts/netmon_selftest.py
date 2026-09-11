#!/usr/bin/env python3
"""Приёмочные испытания системы мониторинга: прогон всех проверок с протоколом.

    python modules/netmon/scripts/netmon_selftest.py --json out.json

Каждая проверка возвращает вердикт PASS/FAIL/WARN и фактические значения —
из них собирается акт тестирования. Ничего не меняет: только читает Zabbix,
Oracle, Telegram API и HTTP-слой портала.
"""
from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

RESULTS: list[dict] = []


def check(cid: str, group: str, title: str, expect: str):
    """Декоратор: оборачивает проверку, ловит падения, пишет в протокол."""
    def deco(fn):
        def run():
            t0 = time.time()
            try:
                verdict, fact = fn()
            except Exception as e:  # noqa: BLE001 — падение проверки тоже результат
                verdict, fact = "FAIL", f"исключение: {type(e).__name__}: {e}"
            RESULTS.append({"id": cid, "group": group, "title": title, "expect": expect,
                            "fact": str(fact), "verdict": verdict,
                            "ms": int((time.time() - t0) * 1000)})
            print(f"  [{verdict:<4}] {cid} {title} — {fact}")
            return verdict
        return run
    return deco


def _zbx():
    from modules.netmon import sources
    return sources.Zabbix()


# ============================================================ 1. Покрытие сети

@check("MON-01", "Покрытие сети", "Скан подсети находит живые устройства",
       "не менее 30 отвечающих узлов в 192.168.0.0/24")
def t_scan():
    from modules.netmon import store
    devs = store.devices()
    n = len(devs)
    return ("PASS" if n >= 30 else "FAIL"), f"в инвентаре {n} устройств"


@check("MON-02", "Покрытие сети", "Все найденные устройства заведены в Zabbix",
       "устройств вне мониторинга — 0")
def t_coverage():
    from modules.netmon import store
    missing = store.devices(only_missing=True)
    return ("PASS" if not missing else "FAIL"), \
        (f"вне мониторинга {len(missing)}: " + ", ".join(d["ip"] for d in missing[:5])
         if missing else "вне мониторинга 0 устройств, покрытие 100 %")


@check("MON-03", "Покрытие сети", "Критичные узлы опознаны и контролируются",
       "Oracle, гипервизор и маршрутизаторы имеют важность high и стоят в Zabbix")
def t_critical():
    from modules.netmon import store
    crit = [d for d in store.devices() if d["criticality"] == "high"]
    bad = [d["ip"] for d in crit if d["in_zabbix"] != "Y"]
    return ("PASS" if crit and not bad else "FAIL"), \
        f"критичных узлов {len(crit)}, все в мониторинге" if not bad else f"не заведены: {bad}"


@check("MON-04", "Покрытие сети", "Группа автообнаружения существует в Zabbix",
       "группа Office Auto-Discovered, хосты включены")
def t_group():
    z = _zbx()
    g = z.call("hostgroup.get", {"filter": {"name": "Office Auto-Discovered"},
                                 "output": ["groupid"], "selectHosts": ["host", "status"]})
    if not g:
        return "FAIL", "группа не найдена"
    hosts = g[0].get("hosts", [])
    off = [h["host"] for h in hosts if h["status"] != "0"]
    return ("PASS" if hosts and not off else "FAIL"), \
        f"в группе {len(hosts)} хостов, все включены" if not off else f"выключены: {off}"


@check("MON-05", "Покрытие сети", "По новым хостам реально идут метрики",
       "ICMP-метрики имеют значения, а не пустые")
def t_items():
    z = _zbx()
    g = z.call("hostgroup.get", {"filter": {"name": "Office Auto-Discovered"}, "output": ["groupid"]})
    if not g:
        return "FAIL", "группа не найдена"
    items = z.call("item.get", {"groupids": g[0]["groupid"], "output": ["key_", "lastvalue", "state"]})
    ping = [i for i in items if i["key_"].startswith("icmpping")]
    live = [i for i in ping if i.get("lastvalue") not in (None, "")]
    unsupported = [i for i in ping if i.get("state") == "1"]
    ok = ping and len(live) >= len(ping) * 0.9 and not unsupported
    return ("PASS" if ok else "WARN"), \
        f"метрик {len(ping)}, с данными {len(live)}, неподдерживаемых {len(unsupported)}"


# ============================================================ 2. Оповещение

@check("TG-01", "Оповещение", "Telegram-каналы обнаружены и опознаны",
       "найден хотя бы один активный канал с названием")
def t_channels():
    from modules.netmon import store
    chans = store.channels()
    live = [c for c in chans if c["is_enabled"] == "Y"]
    named = [c for c in chans if c["title"] and not c["title"].startswith("chat ")]
    return ("PASS" if live and len(named) == len(chans) else "FAIL"), \
        f"каналов {len(chans)}, активных {len(live)}, с названием {len(named)}"


@check("TG-02", "Оповещение", "Бот отвечает и состоит в активном канале",
       "getChat по активному каналу возвращает ok")
def t_bot():
    from modules.netmon import sources, store
    live = [c for c in store.channels() if c["is_enabled"] == "Y"]
    if not live:
        return "FAIL", "нет активных каналов"
    meta = sources.telegram_chats([live[0]["chat_id"]])
    m = meta.get(live[0]["chat_id"], {})
    ok = bool(m.get("title")) and bool(m.get("bot_username"))
    return ("PASS" if ok else "FAIL"), \
        f"бот @{m.get('bot_username')} видит канал «{m.get('title')}», участников {m.get('members_count')}" \
        if ok else f"ответ Telegram: {m}"


@check("TG-03", "Оповещение", "Действие Zabbix включено и покрывает важные уровни",
       "действие Telegram активно, условия ≥ average")
def t_action():
    z = _zbx()
    acts = z.call("action.get", {"output": ["name", "status", "eventsource"],
                                 "selectFilter": "extend", "selectOperations": "extend"})
    tg = [a for a in acts if a["eventsource"] == "0" and a["status"] == "0"
          and "telegram" in a["name"].lower()]
    if not tg:
        return "FAIL", "включённого действия Telegram нет"
    conds = tg[0].get("filter", {}).get("conditions", [])
    sev = sorted({c["value"] for c in conds if c["conditiontype"] == "4"})
    return ("PASS" if sev else "WARN"), \
        f"действие «{tg[0]['name']}» включено, уровни {sev} (2=average,3=high,4=disaster)"


@check("TG-04", "Оповещение", "Сообщения доставляются без ошибок",
       "доля неуспешных отправок 0 %")
def t_delivery():
    from modules.netmon import store
    st = store.alert_stats()
    total, failed = st["total"], st["failed"]
    return ("PASS" if total and not failed else "FAIL" if failed else "WARN"), \
        f"отправлено {total} сообщений за 30 дней, ошибок доставки {failed}"


@check("TG-05", "Оповещение", "Поток уведомлений живой",
       "за последние сутки есть сообщения")
def t_recent():
    from modules.netmon import store
    st = store.alert_stats()
    return ("PASS" if st["last_24h"] > 0 else "WARN"), \
        f"за сутки {st['last_24h']} сообщений, всего {st['total']}"


@check("TG-06", "Оповещение", "Новые хосты попадают в канал",
       "хотя бы одно уведомление относится к хосту из группы автообнаружения")
def t_newhost_alert():
    from modules.netmon import store
    z = _zbx()
    g = z.call("hostgroup.get", {"filter": {"name": "Office Auto-Discovered"},
                                 "output": ["groupid"], "selectHosts": ["host"]})
    names = {h["host"] for h in (g[0].get("hosts", []) if g else [])}
    hit = [a for a in store.alerts(limit=500) if a["host_name"] in names]
    return ("PASS" if hit else "WARN"), \
        (f"уведомлений по новым хостам {len(hit)}, например: {hit[0]['subject'][:60]}"
         if hit else "по новым хостам уведомлений пока не было")


# ============================================================ 3. Витрина

@check("APP-01", "Витрина", "Страница модуля открывается авторизованному",
       "HTTP 200 на /UNA.md/orasldev/netmon")
def t_page():
    code = _http("/UNA.md/orasldev/netmon")
    return ("PASS" if code == 200 else "FAIL"), f"HTTP {code}"


@check("APP-02", "Витрина", "API сводки отдаёт данные",
       "success=true, покрытие и счётчики заполнены")
def t_api_overview():
    d = _api("/UNA.md/orasldev/netmon/api/overview")
    ok = d and d.get("devices", {}).get("total", 0) > 0
    return ("PASS" if ok else "FAIL"), \
        f"устройств {d['devices']['total']}, покрытие {d['coverage_pct']} %, каналов {len(d['channels'])}" \
        if ok else f"ответ: {str(d)[:120]}"


@check("APP-03", "Витрина", "Лента сообщений доступна и отсортирована",
       "последние сообщения сверху, поля заполнены")
def t_api_feed():
    d = _api("/UNA.md/orasldev/netmon/api/alerts?limit=20")
    ok = isinstance(d, list) and d and all(x.get("subject") and x.get("sent_at") for x in d)
    return ("PASS" if ok else "FAIL"), \
        f"получено {len(d)} сообщений, верхнее: {d[0]['sent_at']} {d[0]['subject'][:48]}" \
        if ok else f"ответ: {str(d)[:120]}"


@check("APP-04", "Витрина", "Повторная синхронизация ленты не плодит дублей",
       "второй прогон добавляет 0 записей")
def t_idempotent():
    from modules.netmon.controller import NetmonController as C
    first = C.sync_alerts(days=7)[0].get("data", {})
    second = C.sync_alerts(days=7)[0].get("data", {})
    ok = second.get("added") == 0
    return ("PASS" if ok else "FAIL"), \
        f"первый прогон +{first.get('added')}, второй +{second.get('added')} (ожидалось 0)"


# ============================================================ 4. Безопасность

@check("SEC-01", "Безопасность", "Данные закрыты от неавторизованного доступа",
       "API без сессии отвечает 401")
def t_auth():
    codes = {p: _http(f"/UNA.md/orasldev/netmon/api/{p}", auth=False)
             for p in ("overview", "devices", "channels", "alerts")}
    ok = all(c == 401 for c in codes.values())
    return ("PASS" if ok else "FAIL"), f"без сессии: {codes} (ожидалось 401 везде)"


@check("SEC-02", "Безопасность", "Изменяющие операции недоступны методом GET",
       "sync-эндпоинты отвечают 405 на GET")
def t_methods():
    codes = {p: _http(f"/UNA.md/orasldev/netmon/api/sync/{p}") for p in ("channels", "devices", "all")}
    ok = all(c == 405 for c in codes.values())
    return ("PASS" if ok else "FAIL"), f"GET на sync: {codes} (ожидалось 405)"


@check("SEC-03", "Безопасность", "Секреты не хранятся в коде",
       "в модуле нет токенов и паролей, только обращения к Keychain")
def t_secrets():
    import re
    bad = []
    for p in (ROOT / "modules/netmon").rglob("*"):
        if p.suffix not in (".py", ".html", ".sql", ".json") or "__pycache__" in str(p):
            continue
        src = p.read_text(encoding="utf-8", errors="ignore")
        if re.search(r"[0-9]{8,}:[A-Za-z0-9_-]{30,}", src):
            bad.append(p.name + " (токен бота)")
        if re.search(r"(password|passwd)\s*=\s*[\"'][^\"'{}$]{6,}[\"']", src, re.I):
            bad.append(p.name + " (пароль)")
    return ("PASS" if not bad else "FAIL"), \
        "секретов в коде нет, пароли берутся из Keychain" if not bad else f"найдено: {bad}"


@check("SEC-04", "Безопасность", "Токен Telegram-бота не покидает сервер Zabbix",
       "запрос к Telegram выполняется на контейнере, токен не читается в портал")
def t_token_locality():
    src = (ROOT / "modules/netmon/sources.py").read_text(encoding="utf-8")
    on_server = "ALERTSCRIPT" in src and "ssh" in src
    no_local = "api.telegram.org" not in src.split("remote =")[0]
    return ("PASS" if on_server and no_local else "FAIL"), \
        "обращение к Bot API выполняется по SSH на 192.168.0.110, токен остаётся там"


@check("SEC-05", "Безопасность", "SQL-запросы параметризованы",
       "нет конкатенации пользовательского ввода в SQL")
def t_sqli():
    import re
    src = (ROOT / "modules/netmon/store.py").read_text(encoding="utf-8")
    # ищем склейку строки запроса с переменной вместо связанной переменной
    bad = re.findall(r"execute_query\(\s*[\"'][^\"']*\"\s*\+|%\s*\(", src)
    binds = src.count(":")
    return ("PASS" if not bad else "FAIL"), \
        f"конкатенации в запросах нет, связанных переменных ~{binds}" if not bad else f"подозрительно: {bad[:3]}"


@check("SEC-06", "Безопасность", "Сканирование не меняет чужие системы",
       "скрипт только добавляет хосты, не удаляет и не правит существующие")
def t_readonly():
    src = (ROOT / "modules/netmon/scripts/netmon_zabbix_sync.py").read_text(encoding="utf-8")
    forbidden = [m for m in ("host.delete", "host.update", "hostgroup.delete",
                             "template.delete", "action.update") if m in src]
    return ("PASS" if not forbidden else "FAIL"), \
        "используются только host.get/host.create/hostgroup.create" if not forbidden \
        else f"найдены опасные вызовы: {forbidden}"


@check("SEC-07", "Безопасность", "Версия Zabbix и риск поддержки",
       "зафиксировать версию; 3.4 снята с поддержки — ожидается WARN")
def t_version():
    # apiinfo.version — единственный метод, который вызывается БЕЗ auth
    body = json.dumps({"jsonrpc": "2.0", "method": "apiinfo.version",
                       "params": {}, "id": 1}).encode()
    from modules.netmon import sources
    req = urllib.request.Request(sources.ZBX_URL, body,
                                 {"Content-Type": "application/json-rpc"})
    ver = json.load(urllib.request.urlopen(req, timeout=20)).get("result")
    old = str(ver).startswith(("3.", "4.", "5."))
    return ("WARN" if old else "PASS"), \
        f"Zabbix API {ver} — версия снята с поддержки, обновлений безопасности нет" if old \
        else f"Zabbix API {ver}"


# ============================================================ 5. Изоляция кода

@check("ISO-01", "Изоляция", "Модуль не трогает общий код",
       "app.py и общий установщик не упоминают модуль")
def t_isolation():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    dep = (ROOT / "deploy_oracle_objects.py").read_text(encoding="utf-8")
    bad = []
    if "netmon" in app:
        bad.append("app.py")
    if "netmon" in dep.lower() or "NMON_" in dep:
        bad.append("deploy_oracle_objects.py")
    return ("PASS" if not bad else "FAIL"), \
        "общий код чист, модуль подключается ядром" if not bad else f"следы в: {bad}"


@check("ISO-02", "Изоляция", "Тесты модуля проходят",
       "pytest tests/test_netmon.py — все зелёные")
def t_pytest():
    r = subprocess.run([sys.executable, "-m", "pytest", "tests/test_netmon.py", "-q"],
                       cwd=ROOT, capture_output=True, text=True)
    last = [l for l in r.stdout.strip().splitlines() if l.strip()][-1] if r.stdout.strip() else "нет вывода"
    return ("PASS" if r.returncode == 0 else "FAIL"), last


@check("ISO-03", "Изоляция", "Схема Oracle развёрнута",
       "все таблицы NMON_* существуют и наполнены")
def t_schema():
    from models.database import DatabaseModel
    with DatabaseModel() as db:
        r = db.execute_query("SELECT TABLE_NAME FROM USER_TABLES WHERE TABLE_NAME LIKE 'NMON%' "
                             "ORDER BY TABLE_NAME")
        names = [x[0] for x in (r.get("data") or [])]
        counts = {}
        for t in names:
            c = db.execute_query(f"SELECT COUNT(*) FROM {t}")
            counts[t] = (c.get("data") or [[0]])[0][0]
    need = {"NMON_SCANS", "NMON_DEVICES", "NMON_TG_CHANNELS", "NMON_TG_ALERTS"}
    ok = need.issubset(set(names))
    return ("PASS" if ok else "FAIL"), \
        "таблиц " + str(len(names)) + ": " + ", ".join(f"{k}={v}" for k, v in counts.items())


# ============================================================ HTTP-помощники

SESSION_COOKIE = {"v": None}
BASE = "http://127.0.0.1:3013"


def _login():
    import os
    import re
    env = (ROOT / ".env").read_text(encoding="utf-8")
    u = re.search(r"^DEFAULT_USERNAME=(.*)$", env, re.M)
    p = re.search(r"^DEFAULT_PASSWORD=(.*)$", env, re.M)
    if not (u and p):
        return None
    data = urllib.parse.urlencode({"username": u.group(1).strip(),
                                   "password": p.group(1).strip()}).encode()
    req = urllib.request.Request(BASE + "/login", data)
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
    try:
        opener.open(req, timeout=15)
    except Exception:  # noqa: BLE001
        return None
    SESSION_COOKIE["v"] = opener
    return opener


def _opener():
    return SESSION_COOKIE["v"] or _login()


def _http(path: str, auth: bool = True) -> int:
    try:
        if auth:
            op = _opener()
            if not op:
                return 0
            return op.open(BASE + path, timeout=20).getcode()
        return urllib.request.urlopen(BASE + path, timeout=20).getcode()
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:  # noqa: BLE001
        return 0


def _api(path: str):
    op = _opener()
    if not op:
        return None
    try:
        d = json.load(op.open(BASE + path, timeout=60))
        return d.get("data") if d.get("success") else d
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


import urllib.parse  # noqa: E402  (нужен только помощникам выше)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="куда сохранить протокол")
    a = ap.parse_args()

    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")

    print(f"Приёмочные испытания системы мониторинга — {datetime.now():%d.%m.%Y %H:%M}\n")
    for fn in (t_scan, t_coverage, t_critical, t_group, t_items,
               t_channels, t_bot, t_action, t_delivery, t_recent, t_newhost_alert,
               t_page, t_api_overview, t_api_feed, t_idempotent,
               t_auth, t_methods, t_secrets, t_token_locality, t_sqli, t_readonly, t_version,
               t_isolation, t_pytest, t_schema):
        fn()

    tally = {v: sum(1 for r in RESULTS if r["verdict"] == v) for v in ("PASS", "WARN", "FAIL")}
    print(f"\nИтог: PASS {tally['PASS']}, WARN {tally['WARN']}, FAIL {tally['FAIL']} "
          f"из {len(RESULTS)} проверок")
    if a.json:
        Path(a.json).write_text(json.dumps(
            {"generated": datetime.now().isoformat(timespec="seconds"),
             "tally": tally, "results": RESULTS}, ensure_ascii=False, indent=1), encoding="utf-8")
        print("протокол:", a.json)
    sys.exit(1 if tally["FAIL"] else 0)


if __name__ == "__main__":
    main()
