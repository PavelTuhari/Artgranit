#!/usr/bin/env python3
"""Сервисы офиса — через оба канала: если МТС лежит, всё работает через Orange.

    python modules/netmon/scripts/netmon_wan_failover.py --dry-run   # показать, что будет сделано
    python modules/netmon/scripts/netmon_wan_failover.py             # сделать
    python modules/netmon/scripts/netmon_wan_failover.py --rollback  # убрать всё добавленное

Владелец 03.11.2026 после аварии МТС: «сделай, чтобы всё работало
универсально и прозрачно: если МТС не работает, всё работает через Orange».

На маршрутизаторе 192.168.0.101 пробросы портов были почти все только на
адресах МТС (93.115.136.18–22). Здесь для каждого из них, где порт на адресе
Orange 195.22.241.126 свободен, добавляется такой же проброс на Orange.
У Orange один адрес, у МТС пять: что на одном порту разных адресов МТС
(HTTPS разных сайтов) — разводится по имени через nginx на 192.168.0.148,
не здесь. Ответы уходят через тот канал, через который пришёл запрос, —
это делают уже стоящие правила mangle (Orange_connection → orange_route_mark).

Перед изменениями сохраняется полная выгрузка конфигурации на самом
маршрутизаторе (файл netmon-before-failover-ДАТА.rsc). Все добавленные
правила помечены FAILOVER_TAG — откат одной командой (--rollback).
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from modules.netmon import mikrotik as mt  # noqa: E402

ORANGE_IP = "195.22.241.126"
FAILOVER_TAG = "FAILOVER-ORANGE"
# Не зеркалить: файловый ресурс в интернет и порты, занятые на Orange другим
NEVER = {("tcp", "445")}


def plan(nat: list[dict]) -> tuple[list[dict], list[dict]]:
    """Пробросы МТС → что добавить на Orange и что не получится (порт занят)."""
    active = [r for r in nat if r.get("disabled") != "true"]
    on_orange = {(r.get("protocol"), r.get("dst-port")): r for r in active if r.get("dst-address") == ORANGE_IP}
    add, conflict, seen = [], [], set()
    for r in active:
        if not (r.get("dst-address") or "").startswith("93.115.136."):
            continue
        key = (r.get("protocol"), r.get("dst-port"))
        if not key[1] or key in NEVER or key in seen:
            continue            # проброс «всех портов» и запрещённое — мимо
        seen.add(key)
        other = on_orange.get(key)
        if other:
            if other.get("to-addresses") != r.get("to-addresses"):
                conflict.append({**r, "busy_by": other.get("to-addresses"), "busy_comment": other.get("comment")})
            continue
        add.append(r)
    return add, conflict


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--rollback", action="store_true")
    a = ap.parse_args()
    with mt.Session() as s:
        if a.rollback:
            n = s.count("/ip firewall nat", f'comment~"{FAILOVER_TAG}"')
            print(f"правил с меткой {FAILOVER_TAG}: {n}")
            if not a.dry_run and n > 0:
                s.run(f'/ip firewall nat remove [find comment~"{FAILOVER_TAG}"]')
                print("удалены")
            return
        nat = s.rows("/ip firewall nat", ["dst-address", "protocol", "dst-port", "to-addresses", "to-ports",
                                          "disabled", "comment"], "action=dst-nat")
        add, conflict = plan(nat)
        for r in add:
            print(f"+ {ORANGE_IP} {r['protocol']} {r['dst-port']} -> {r['to-addresses']}:{r['to-ports']}"
                  f"  ({(r.get('comment') or '').strip(' ;')[:50]})")
        for r in conflict:
            print(f"! {r['protocol']} {r['dst-port']} -> {r['to-addresses']}: на Orange порт занят "
                  f"({r['busy_by']}, {(r.get('busy_comment') or '')[:40]})")
        if a.dry_run:
            print("--dry-run: ничего не изменено")
            return
        stamp = datetime.now().strftime("%Y%m%d-%H%M")
        s.run(f"/export file=netmon-before-failover-{stamp}", timeout=120)
        print(f"выгрузка конфигурации: netmon-before-failover-{stamp}.rsc на маршрутизаторе")
        for r in add:
            to_port = f" to-ports={r['to-ports']}" if r.get("to-ports") else ""
            comment = f"{FAILOVER_TAG} {datetime.now():%d.%m.%Y} mirror of {r['dst-address']} " \
                      f"{(r.get('comment') or '').strip(' ;')[:40]}".replace('"', "'")
            s.run(f'/ip firewall nat add chain=dstnat dst-address={ORANGE_IP} protocol={r["protocol"]} '
                  f'dst-port={r["dst-port"]} action=dst-nat to-addresses={r["to-addresses"]}{to_port} '
                  f'comment="{comment}"')
        print(f"добавлено правил: {s.count('/ip firewall nat', f'comment~\"{FAILOVER_TAG}\"')}")


if __name__ == "__main__":
    main()
