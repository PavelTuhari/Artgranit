"""Подключения клиентов к базам cloudbd и clouddev — чистые правила, без базы.

Кто подключён, видно по сессиям Oracle (V$SESSION): схема клиента, компьютер,
пользователь Windows, программа, модуль. По программе понятно, что это за
подключение:

  * база магазина — локальный Oracle точки ходит в центр по DB-link:
    программа «oracle@<сервер точки>» или ORACLE.EXE;
  * касса, меню, весы — UAMenu.exe, UNAScales.exe, кассы автовокзала gara*;
  * настольный UniAcc — UniacCLNT.exe, uniConf.exe: бухгалтерия или учёт
    клиента прямо в бэк-офисе; в модуле сессии — логин пользователя UniAcc;
  * сайт и интеграции — php-fpm, node, python, JDBC;
  * наши специалисты — домен UNAMD, Toad, sqlplus, SQL Developer.

Клиент — это схема без служебного хвоста: SIGMA_BK, SIGMA_WEB, SIGMA_SALES
относятся к клиенту SIGMA. Группа клиента:

  * магазинники — есть база магазина, касса или весы;
  * прямые бэки — работают в настольном UniAcc, магазинов нет;
  * веб и интеграции — только сайт и обмены;
  * наши — служебные схемы и подключения только наших специалистов.

Тип, закреплённый в справочнике NMON_CLIENT, важнее определённого по
подключениям: клиент без подключений иначе не определится.
"""
from __future__ import annotations

import re

KINDS = ("shop", "back", "web", "internal")
KIND_TITLES = {"shop": "Магазинники", "back": "Прямые бэки", "web": "Веб и интеграции",
               "internal": "Наши и служебные"}

# Вид отдельного подключения
CONN_TITLES = {
    "shop_db": "база магазина",
    "pos": "касса / меню",
    "scales": "весы",
    "desktop": "UniAcc",
    "web": "сайт / обмен",
    "staff": "наш специалист",
    "link": "связь наших баз",
    "other": "другое",
}

# Схемы, которые не клиенты
INTERNAL_SCHEMAS = {
    "SYS", "SYSTEM", "DBSNMP", "SYSMAN", "OUTLN", "XDB", "ANONYMOUS", "CTXSYS",
    "OTRS", "XWIKI", "TICKETS", "TICKETS_WS", "UNI", "HARUZ", "HARUZDAR2018",
}

# Служебные хвосты схем одного клиента
_SUFFIX = re.compile(r"_(BK|TEST|SALES|SCALES|WEB|UN4EXT|READONLY|HR|POS|EXT)$")

# Наши машины и инструменты
_STAFF_MACHINE = re.compile(r"^(UNAMD\\|PTS-MACBOOK)", re.I)
_STAFF_PROGRAM = re.compile(r"(toad|sqlplus|sql developer|sqldeveloper|plsqldev|dbeaver|"
                            r"python@pts-macbook)", re.I)
_OUR_SERVER = re.compile(r"^oracle@cloudbd\.internal", re.I)


def client_key(schema: str | None) -> str:
    s = (schema or "").strip().upper()
    return _SUFFIX.sub("", s) or s


def uniacc_login(module: str | None) -> str | None:
    """«UniAcc-Client Nrusu 5.77.1.21 07.10.2026» → «Nrusu»."""
    m = re.match(r"UniAcc-Client\s+(\S+)", module or "")
    return m.group(1) if m else None


def uniacc_version(module: str | None) -> str | None:
    m = re.search(r"\b(\d+\.\d+\.\d+\.\d+)\b", module or "")
    return m.group(1) if m else None


def conn_kind(program: str | None, machine: str | None = None) -> str:
    p = (program or "").strip()
    pl = p.lower()
    if _STAFF_MACHINE.match(machine or "") or _STAFF_PROGRAM.search(p):
        return "staff"
    if _OUR_SERVER.match(p):
        return "link"
    if pl.startswith("oracle@") or pl == "oracle.exe":
        return "shop_db"
    if pl.startswith(("uamenu", "gara", "pos")):
        return "pos"
    if pl.startswith("unascales"):
        return "scales"
    if pl.startswith("uniacclnt") or pl.startswith("uniconf"):
        return "desktop"
    if re.search(r"php|index\.php|node@|next-server|python|jdbc|java|httpd|apache", pl):
        return "web"
    return "other"


def point_name(c: dict) -> str:
    """Где это подключение: для базы магазина — сервер точки, иначе компьютер."""
    m = (c.get("machine") or "").strip()
    if c.get("kind") == "shop_db":
        prog = c.get("program") or ""
        hm = re.match(r"oracle@(\S+)", prog, re.I)
        return hm.group(1) if hm else m
    return m.split("\\")[-1] if "\\" in m else m


TEST_DBS = {"clouddev"}       # тестовая база: клиенты оттуда — не боевые


def auto_kind(conns: list[dict], key: str) -> str:
    if key in INTERNAL_SCHEMAS:
        return "internal"
    if conns and all(c.get("db") in TEST_DBS for c in conns):
        return "internal"     # виден только в тестовой базе
    kinds = {c["kind"] for c in conns}
    if kinds & {"shop_db", "pos", "scales"}:
        return "shop"
    if "desktop" in kinds:
        return "back"
    if "web" in kinds:
        return "web"
    return "internal"     # только наши специалисты или связь наших баз


def classify(sessions: list[dict]) -> list[dict]:
    """Сессии → подключения с видом, точкой и логином UniAcc."""
    out = []
    for s in sessions:
        c = dict(s)
        c["schema"] = (s.get("schema") or "").upper()
        c["client"] = client_key(c["schema"])
        c["kind"] = conn_kind(s.get("program"), s.get("machine"))
        c["kind_title"] = CONN_TITLES[c["kind"]]
        c["login"] = uniacc_login(s.get("module"))
        c["version"] = uniacc_version(s.get("module"))
        c["point"] = point_name(c)
        out.append(c)
    return out


def group(conns: list[dict], registry: dict[str, dict] | None = None,
          known_kinds: dict[str, str] | None = None) -> dict:
    """Подключения → клиенты по группам. Клиенты из справочника без
    подключений тоже показываются — в своей группе, с нулём подключений."""
    registry = registry or {}
    clients: dict[str, dict] = {}
    for c in conns:
        cl = clients.setdefault(c["client"], {"client": c["client"], "conns": []})
        cl["conns"].append(c)
    for key in registry:
        clients.setdefault(key, {"client": key, "conns": []})

    for key, cl in clients.items():
        conns_ = cl["conns"]
        reg = registry.get(key) or {}
        cl["auto_kind"] = auto_kind(conns_, key)
        # сейчас подключены только наши — тип берём из истории клиента (унификация)
        known = (known_kinds or {}).get(key)
        if cl["auto_kind"] == "internal" and known in ("shop", "back", "web") and key not in INTERNAL_SCHEMAS \
                and not all(c.get("db") in TEST_DBS for c in conns_):
            cl["auto_kind"] = known
        cl["kind"] = reg.get("kind") or cl["auto_kind"]
        cl["pinned"] = bool(reg.get("kind"))
        cl["title"] = reg.get("title")
        cl["note"] = reg.get("note")
        cl["schemas"] = sorted({c["schema"] for c in conns_})
        cl["dbs"] = sorted({c["db"] for c in conns_ if c.get("db")})
        cl["test_only"] = bool(conns_) and all(c.get("db") in TEST_DBS for c in conns_)
        cl["sessions"] = len(conns_)
        cl["active"] = sum(1 for c in conns_ if c.get("status") == "ACTIVE")
        cl["shops"] = sorted({c["point"] for c in conns_ if c["kind"] in ("shop_db", "pos", "scales")})
        cl["workplaces"] = sorted({c["point"] for c in conns_ if c["kind"] == "desktop"})
        cl["users"] = sorted({c["login"] for c in conns_ if c.get("login") and c["kind"] == "desktop"})
        cl["by_kind"] = {}
        for c in conns_:
            cl["by_kind"][c["kind"]] = cl["by_kind"].get(c["kind"], 0) + 1
        idle = [c.get("idle_sec") for c in conns_ if c["kind"] != "staff" and c.get("idle_sec") is not None]
        cl["min_idle_sec"] = min(idle) if idle else None
        cl["conns"] = sorted(conns_, key=lambda c: (c["kind"], c["point"] or "", c.get("idle_sec") or 0))

    groups = {k: [] for k in KINDS}
    for cl in clients.values():
        groups[cl["kind"]].append(cl)
    for k in groups:
        groups[k].sort(key=lambda c: (-c["sessions"], c["client"]))
    summary = {
        "clients": {k: len(v) for k, v in groups.items()},
        "shops_online": sum(len(c["shops"]) for c in groups["shop"]),
        "workplaces_online": sum(len(c["workplaces"]) for c in clients.values() if c["kind"] != "internal"),
        "users_online": sum(len(c["users"]) for c in clients.values() if c["kind"] != "internal"),
        "sessions": len(conns),
        "staff_sessions": sum(1 for c in conns if c["kind"] == "staff"),
    }
    return {"groups": groups, "summary": summary, "titles": KIND_TITLES}
