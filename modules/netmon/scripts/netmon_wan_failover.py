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
# Не зеркалить: файловый ресурс и веб-консоль Proxmox в интернет не открывать
NEVER = {("tcp", "445"), ("tcp", "8081")}
# Пробросы на Orange, которые больше не нужны и освобождают порт для una.md.
# Почта garileauto.md (25/143/587 → 172.29.0.23): владелец 03.11.2026 — «не
# актуально, можно открыть для почты una.md». Выключаются, а не удаляются:
# --rollback включает их обратно.
RETIRED = {"172.29.0.23"}


def ports(spec: str | None) -> set[str]:
    """«8081,443» или «1000-1010» → множество; диапазон берётся как одна метка."""
    return {x.strip() for x in (spec or "").split(",") if x.strip()}


def plan(nat: list[dict]) -> tuple[list[dict], list[dict]]:
    """Пробросы МТС → что добавить на Orange и что не получится (порт занят).

    Сверка по пересечению портов, а не по строке: правило «8081,443» на МТС
    задело бы HTTPS, который на Orange уже ведёт на nginx 192.168.0.148."""
    active = [r for r in nat if r.get("disabled") != "true"]
    busy: dict[tuple[str, str], dict] = {}
    for r in active:
        if r.get("dst-address") == ORANGE_IP and r.get("to-addresses") not in RETIRED:
            for port in ports(r.get("dst-port")):
                busy[(r.get("protocol"), port)] = r
    add, conflict = [], []
    for r in active:
        if not (r.get("dst-address") or "").startswith("93.115.136."):
            continue
        want = {(r.get("protocol"), port) for port in ports(r.get("dst-port"))}
        if not want or want & NEVER:
            continue            # проброс «всех портов» и запрещённое — мимо
        taken = [busy[k] for k in sorted(want) if k in busy]
        same = all(o.get("to-addresses") == r.get("to-addresses") for o in taken)
        if taken and not same:
            conflict.append({**r, "busy_by": taken[0].get("to-addresses"), "busy_comment": taken[0].get("comment")})
            continue
        if taken:
            continue            # уже есть на Orange
        for k in want:
            busy[k] = r         # второй такой же проброс с другого адреса МТС не добавлять
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
            for to in RETIRED:
                where = f'where dst-address="{ORANGE_IP}" and to-addresses="{to}" and disabled=yes'
                print(f"выключенных пробросов на {to}: {s.count('/ip firewall nat', where)}")
                if not a.dry_run:
                    s.run(f"/ip firewall nat enable [find {where}]")
            return
        nat = s.rows("/ip firewall nat", ["dst-address", "protocol", "dst-port", "to-addresses", "to-ports",
                                          "disabled", "comment"], "action=dst-nat")
        add, conflict = plan(nat)
        retire = [r for r in nat if r.get("dst-address") == ORANGE_IP and r.get("to-addresses") in RETIRED
                  and r.get("disabled") != "true"]
        for r in retire:
            print(f"- {ORANGE_IP} {r['protocol']} {r['dst-port']} -> {r['to-addresses']}: выключить "
                  f"({(r.get('comment') or '').strip()[:40]})")
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
        for to in RETIRED:
            s.run(f'/ip firewall nat disable [find where dst-address="{ORANGE_IP}" and to-addresses="{to}"]')
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
