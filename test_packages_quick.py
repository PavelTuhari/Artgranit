#!/usr/bin/env python3
"""Быстрый тест пакетов - использует тот же метод подключения что и приложение"""
import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.chdir(ROOT)

# Загружаем .env ПЕРЕД импортом config
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from models.database import DatabaseModel

print("Тест пакетов...")
try:
    with DatabaseModel() as db:
        # Тест GET_PRODUCTS
        print("\n1. GET_PRODUCTS:")
        rows = db.fetch_refcursor(
            "BEGIN CRED_OPERATOR_PKG.GET_PRODUCTS(:search, :lim, :cur); END;",
            {"search": None, "lim": 3},
            "cur",
        )
        print(f"   Строк: {len(rows)}")
        if rows:
            print(f"   Ключи: {list(rows[0].keys())}")
            print(f"   Первая строка: {dict(list(rows[0].items())[:5])}")
        
        # Тест GET_PROGRAMS
        print("\n2. GET_PROGRAMS:")
        rows = db.fetch_refcursor(
            "BEGIN CRED_ADMIN_PKG.GET_PROGRAMS(:bank, :term, :active, :cur); END;",
            {"bank": None, "term": None, "active": None},
            "cur",
        )
        print(f"   Строк: {len(rows)}")
        if rows:
            print(f"   Ключи: {list(rows[0].keys())}")
            print(f"   Первая строка: {dict(list(rows[0].items())[:5])}")
except Exception as e:
    print(f"Ошибка: {e}")
    import traceback
    traceback.print_exc()
