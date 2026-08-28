#!/usr/bin/env python3
"""Sincronizarea catalogului Ultra -> tamponul BIRO26_GOODS (CLI / cron).

Rulare din radacina proiectului:
    python3 modules/partner/scripts/ultra_sync.py            # incremental
    python3 modules/partner/scripts/ultra_sync.py --full     # tot catalogul
Cron sugerat (o data pe ora, incremental):
    17 * * * * cd /home/ubuntu/artgranit && ./venv/bin/python \
        modules/partner/scripts/ultra_sync.py >> /tmp/ultra_sync.log 2>&1
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, ROOT)

from modules.partner.ultra import UltraClient  # noqa: E402

if __name__ == "__main__":
    result = UltraClient.from_settings().sync(full="--full" in sys.argv)
    print(result)
    sys.exit(0 if result.get("success") else 1)
