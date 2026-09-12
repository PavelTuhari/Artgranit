#!/usr/bin/env python3
"""Сбор учётных данных инфраструктуры в macOS Keychain и защищённый локальный файл.

    python modules/netmon/scripts/netmon_vault.py --collect     # найти и показать (без значений)
    python modules/netmon/scripts/netmon_vault.py --to-keychain # разложить по Keychain
    python modules/netmon/scripts/netmon_vault.py --to-file ~/Documents/infra-passwords.md

Источники: записи, уже лежащие в Keychain, и описания виртуальных машин на
гипервизоре, где администраторы годами писали «Auth: root/пароль».

Файл создаётся с правами 600 и НИКОГДА не попадает в репозиторий: путь по
умолчанию — вне проекта. Значения паролей в консоль не печатаются.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

# Записи Keychain, заведённые в ходе работ по мониторингу.
# (account, service, что это, к чему относится)
KNOWN = [
    ("Admin", "zabbix-web", "Веб-интерфейс и API Zabbix", "http://192.168.0.110/zabbix"),
    ("root", "zabbix34-ct", "Контейнер CT 101 с Zabbix, SSH", "192.168.0.110"),
    ("root", "proxmox3-ssh", "Гипервизор PROXMOX3, SSH и веб", "192.168.0.149:8006"),
    ("otrs", "oracle-cloudbd-otrs", "Схема OTRS в Oracle cloudbd", "orange.una.md:4024"),
    ("tickets", "oracle-cloudbd-tickets", "Схема TICKETS в Oracle cloudbd", "orange.una.md:4024"),
    ("haruzdar2018", "oracle-cloudbd-haruzdar2018", "Схема HARUZDAR2018 в Oracle", "orange.una.md:4024"),
    ("uni", "oracle-cloudbd-uni", "Схема UNI в Oracle cloudbd", "orange.una.md:4024"),
    ("garabta", "oracle-cloudbd-garabta", "Схема GARABTA в Oracle", "orange.una.md:4024"),
    ("garabta_cont", "oracle-cloudbd-garabta_cont", "Схема GARABTA_CONT", "orange.una.md:4024"),
    ("valorenergy", "oracle-cloudbd-valorenergy", "Схема VALORENERGY", "orange.una.md:4024"),
    ("dorimax", "oracle-cloudbd-dorimax", "Схема DORIMAX", "orange.una.md:4024"),
    ("helios24", "oracle-cloudbd-helios24", "Схема HELIOS24", "orange.una.md:4024"),
]

# Записи типа internet-password (SSH к хостам)
KNOWN_INTERNET = [
    ("root", "192.168.0.51", "Сервер OTRS, SSH", "192.168.0.51:22"),
    ("root", "192.168.0.24", "Сервер Oracle cloudbd, SSH", "192.168.0.24:22"),
    ("ubuntu", "192.168.0.250", "Внутренняя площадка магазина", "192.168.0.250:8001"),
]


def kc_get(account: str, service: str, internet: bool = False) -> str | None:
    cmd = ["security", "find-internet-password" if internet else "find-generic-password",
           "-a", account, "-s", service, "-w"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None


def kc_set(account: str, service: str, password: str, label: str, internet: bool = False) -> bool:
    cmd = ["security", "add-internet-password" if internet else "add-generic-password",
           "-a", account, "-s", service, "-l", label, "-w", password, "-U"]
    if internet:
        cmd += ["-P", "22", "-r", "ssh "]
    return subprocess.run(cmd, capture_output=True, text=True).returncode == 0


def from_proxmox() -> list[dict]:
    """Учётные данные, записанные администраторами в описаниях виртуальных машин.

    На PROXMOX3 таких машин 18. Пары встречаются в двух формах:
    «Auth: root/пароль» и просто «admin/пароль» отдельной строкой.
    """
    from modules.netmon import proxmox
    out = []
    data = proxmox._ssh(proxmox._COLLECT.replace("NODE", proxmox.PVE_NODE))
    sec = proxmox._split_sections(data)
    pair = re.compile(r"([\w.@-]{2,24})\s*/\s*(\S{4,})")
    for key, text in sec.items():
        m = re.match(r"^CONFIG (qemu|lxc) (\d+)$", key)
        if not m:
            continue
        kind, vmid = m.group(1), m.group(2)
        cfg = proxmox._parse_config(text)
        descr = proxmox._unescape_description(cfg.get("description", ""))
        name = cfg.get("name") or cfg.get("hostname") or f"{kind}-{vmid}"
        ip = ""
        for line in descr.splitlines():
            mi = re.match(r"^\s*IP\s*[:=]\s*([0-9.]+)", line, re.I)
            if mi:
                ip = mi.group(1)
        for line in descr.splitlines():
            low = line.lower()
            hit = pair.search(line)
            if not hit:
                continue
            # отсекаем ложные срабатывания: даты, пути, размеры
            if re.match(r"^\s*\d", hit.group(1)) or "/" in hit.group(2)[:2]:
                continue
            out.append({
                "source": f"описание {kind} {vmid}",
                "system": name,
                "host": ip,
                "login": hit.group(1),
                "password": hit.group(2),
                "note": ("подписано «Auth»" if "auth" in low else "без подписи, в тексте"),
            })
    return out


def collect() -> dict:
    found = {"keychain": [], "proxmox": []}
    for account, service, what, where in KNOWN:
        if kc_get(account, service):
            found["keychain"].append({"account": account, "service": service,
                                      "what": what, "where": where, "kind": "generic"})
    for account, service, what, where in KNOWN_INTERNET:
        if kc_get(account, service, internet=True):
            found["keychain"].append({"account": account, "service": service,
                                      "what": what, "where": where, "kind": "internet"})
    try:
        found["proxmox"] = from_proxmox()
    except Exception as e:  # noqa: BLE001
        print(f"  Proxmox недоступен ({str(e)[:70]}), продолжаю без него")
    return found


def to_keychain(found: dict) -> int:
    """Переносит найденные на гипервизоре пары в Keychain.

    Имя записи: pve-<имя машины>. Существующие записи из KNOWN не трогаем.
    """
    saved = 0
    for c in found["proxmox"]:
        service = "pve-" + re.sub(r"[^\w.-]", "-", c["system"]).lower()[:40]
        label = f"{c['system']} ({c['host'] or 'без IP'}) — {c['source']}"
        if kc_set(c["login"], service, c["password"], label):
            saved += 1
    return saved


def to_file(found: dict, path: Path) -> None:
    """Единый справочник учётных данных. Права 600, вне репозитория."""
    lines = [
        "# Учётные данные инфраструктуры Unisim",
        "",
        f"Собрано автоматически {datetime.now():%d.%m.%Y %H:%M} "
        "(`modules/netmon/scripts/netmon_vault.py`).",
        "",
        "> **Файл содержит пароли в открытом виде.** Права доступа 600, лежит вне",
        "> репозитория. Не копировать в проект, не пересылать, не класть в облако.",
        "> Первоисточник — macOS Keychain; этот файл нужен как бумажная копия на",
        "> случай потери доступа к Keychain.",
        "",
        "## 1. Записи в macOS Keychain",
        "",
        "| Система | Где | Логин | Пароль | Как достать из Keychain |",
        "|---|---|---|---|---|",
    ]
    for k in sorted(found["keychain"], key=lambda x: x["what"]):
        pw = kc_get(k["account"], k["service"], k["kind"] == "internet") or ""
        cmd = ("security find-internet-password" if k["kind"] == "internet"
               else "security find-generic-password")
        lines.append(f"| {k['what']} | `{k['where']}` | `{k['account']}` | `{pw}` | "
                     f"`{cmd} -a {k['account']} -s {k['service']} -w` |")

    lines += ["", "## 2. Найдено в описаниях виртуальных машин на PROXMOX3", "",
              "Администраторы записывали доступы прямо в поле «описание» гостя. "
              "Эти пары перенесены в Keychain под именами `pve-<имя машины>`.", "",
              "| Машина | IP | Логин | Пароль | Где записано |", "|---|---|---|---|---|"]
    for c in sorted(found["proxmox"], key=lambda x: x["system"]):
        lines.append(f"| {c['system']} | `{c['host'] or '—'}` | `{c['login']}` | "
                     f"`{c['password']}` | {c['source']}, {c['note']} |")

    lines += [
        "", "## 3. Что с этим делать", "",
        "1. **Убрать пароли из описаний виртуальных машин на гипервизоре.** Их видит",
        "   каждый, у кого есть доступ к веб-интерфейсу Proxmox, и они попадают в",
        "   резервные копии конфигурации. Описание оставить, пароли — вырезать.",
        "2. **Сменить пароли, которые лежали открыто** — считать их скомпрометированными.",
        "3. **Пароль базы Zabbix** сейчас `zabbix` (словарный). При миграции на новый",
        "   сервер задать случайный.",
        "4. Хранить первоисточником Keychain, этот файл обновлять командой выше.",
        "",
        f"Всего записей: Keychain — {len(found['keychain'])}, "
        f"из описаний на гипервизоре — {len(found['proxmox'])}.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    os.chmod(path, 0o600)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--collect", action="store_true", help="найти и показать сводку")
    ap.add_argument("--to-keychain", action="store_true", help="перенести найденное в Keychain")
    ap.add_argument("--to-file", help="записать справочник (вне репозитория!)")
    a = ap.parse_args()

    print("Сбор учётных данных инфраструктуры\n")
    found = collect()
    print(f"  в Keychain уже есть: {len(found['keychain'])} записей")
    for k in found["keychain"]:
        print(f"     {k['what']:<44} {k['account']}@{k['service']}")
    print(f"  в описаниях машин на PROXMOX3: {len(found['proxmox'])} пар")
    for c in found["proxmox"]:
        print(f"     {c['system']:<24} {c['host']:<16} логин {c['login']} ({c['note']})")

    if a.to_keychain:
        n = to_keychain(found)
        print(f"\nперенесено в Keychain: {n} записей (имена pve-<машина>)")

    if a.to_file:
        p = Path(os.path.expanduser(a.to_file))
        if str(p).startswith(str(ROOT)):
            sys.exit(f"✗ {p} внутри репозитория — файл с паролями туда класть нельзя")
        to_file(found, p)
        print(f"\nсправочник записан: {p} (права 600, {p.stat().st_size // 1024 or 1} КБ)")


if __name__ == "__main__":
    main()
