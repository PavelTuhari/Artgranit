#!/usr/bin/env python3
"""Сверка комиссий кредитования с эталоном, снятым до интеграции Ultra.

Требование владельца 28.08.2026: после интеграции с Ultra API суммы комиссий
должны остаться прежними. Скрипт сравнивает текущие значения в Oracle с
таблицей из docs/Biro26/COMISIOANE_BASELINE.md и печатает расхождения.

Запуск:
    ./venv/bin/python scripts/check_comisioane.py
Код возврата 1, если что-то разошлось — годится для проверки после деплоя.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

BASELINE = ROOT / "docs" / "Biro26" / "COMISIOANE_BASELINE.md"


def read_baseline() -> dict[tuple[str, str], float]:
    """Из таблицы MD берём (организация, пакет) -> комиссия."""
    out: dict[tuple[str, str], float] = {}
    if not BASELINE.exists():
        return out
    for line in BASELINE.read_text(encoding="utf-8").splitlines():
        # | Орг | Пакет | 5% | 10% | **15%** |
        m = re.match(r"^\|\s*(.+?)\s*\|\s*(.+?)\s*\|.*\*\*([\d.,]+)%\*\*\s*\|$", line)
        if m:
            out[(m.group(1), m.group(2))] = float(m.group(3).replace(",", "."))
    return out


def read_current() -> dict[tuple[str, str], float]:
    from models.biro26_credit import Biro26Credit
    out: dict[tuple[str, str], float] = {}
    for o in (Biro26Credit.public_offers().get("data") or []):
        tm = float(o.get("transport_markup_pct") or 0)
        for pl in (o.get("plans") or []):
            out[(o["name"], pl["name"])] = float(pl.get("markup_pct") or 0) + tm
    return out


def main() -> int:
    base, cur = read_baseline(), read_current()
    if not base:
        print("Эталон не найден:", BASELINE)
        return 1

    changed = [(k, base[k], cur[k]) for k in base if k in cur and abs(base[k] - cur[k]) > 0.001]
    gone = [k for k in base if k not in cur]
    added = [k for k in cur if k not in base]

    if not (changed or gone or added):
        print(f"OK: все {len(base)} пакетов совпадают с эталоном.")
        return 0

    for (org, pl), was, now in changed:
        print(f"ИЗМЕНИЛАСЬ  {org} / {pl}: было {was:g}% -> стало {now:g}%")
    for org, pl in gone:
        print(f"ПРОПАЛ      {org} / {pl}")
    for org, pl in added:
        print(f"НОВЫЙ       {org} / {pl}: {cur[(org, pl)]:g}%")
    print("\nЕсли изменения намеренные — пересними эталон и опиши причину в коммите.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
