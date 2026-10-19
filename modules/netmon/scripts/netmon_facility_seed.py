#!/usr/bin/env python3
"""Первичное заполнение реестра инженерного оборудования офиса.

    python modules/netmon/scripts/netmon_facility_seed.py

Заводит то, что выявлено обследованием 12.09.2026: четыре кондиционера по
комнатам, котёл, систему контроля доступа, кнопку лифта и четыре умные
розетки. Повторный запуск безопасен — объекты обновляются по коду, журнал
работ и фотографии не трогаются.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

from modules.netmon import facility, store  # noqa: E402


def main() -> None:
    created = updated = 0
    for f in facility.SEED:
        if store.upsert_facility(f):
            created += 1
        else:
            updated += 1
    print(f"оборудование: заведено {created}, обновлено {updated}")
    s = store.facility_stats()
    print(f"всего в реестре: {s['total']}")
    for kind, n in sorted(s["by_kind"].items()):
        print(f"   {facility.KIND_TITLE.get(kind, kind):<28} {n}")


if __name__ == "__main__":
    main()
