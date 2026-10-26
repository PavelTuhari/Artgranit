#!/usr/bin/env python3
"""Сопоставить клиентов заново: OTRS, бухгалтерия UNI, схемы, точки → NMON_CLI_* (cloudbd).

    python modules/netmon/scripts/netmon_unify.py

Ручные правки (ORIGIN = manual) не перезаписываются. Занимает ~40 с.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

from modules.netmon import unify  # noqa: E402

if __name__ == "__main__":
    print(json.dumps(unify.run(), ensure_ascii=False, indent=1))
