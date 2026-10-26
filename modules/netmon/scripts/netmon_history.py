#!/usr/bin/env python3
"""Перенос истории подключений в Oracle: аудит входов баз и журналы SSH сервера баз.

    python modules/netmon/scripts/netmon_history.py     # перенести новое

Панель переносит сама при открытии вкладок (не чаще раза в 15 минут). Скрипт —
для ручного запуска и расписания: база хранит аудит 30 дней, журнал SSH —
4 недели, поэтому переносить нужно хотя бы раз в три недели, иначе часть
истории пропадёт безвозвратно.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

from modules.netmon import history  # noqa: E402

if __name__ == "__main__":
    print(json.dumps(history.import_all(), ensure_ascii=False, indent=1))
