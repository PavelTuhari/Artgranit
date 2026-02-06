#!/usr/bin/env python3
"""
Прямая проверка данных кредитов в БД - использует тот же метод подключения что и приложение
"""
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
from controllers.credit_controller import CreditController

print("=" * 60)
print("ПРЯМАЯ ПРОВЕРКА ДАННЫХ КРЕДИТОВ")
print("=" * 60)

try:
    with DatabaseModel() as db:
        # 1. Проверка таблиц
        print("\n1. ПРОВЕРКА ТАБЛИЦ:")
        result = db.execute_query("SELECT COUNT(*) as cnt FROM CRED_PRODUCTS")
        products_count = result.get('data', [[0]])[0][0] if result.get('data') else 0
        print(f"   CRED_PRODUCTS: {products_count} записей")
        
        result = db.execute_query("SELECT COUNT(*) as cnt FROM CRED_PROGRAMS")
        programs_count = result.get('data', [[0]])[0][0] if result.get('data') else 0
        print(f"   CRED_PROGRAMS: {programs_count} записей")
        
        # 2. Проверка представлений
        print("\n2. ПРОВЕРКА ПРЕДСТАВЛЕНИЙ:")
        result = db.execute_query("SELECT COUNT(*) as cnt FROM V_CRED_PRODUCTS")
        v_products_count = result.get('data', [[0]])[0][0] if result.get('data') else 0
        print(f"   V_CRED_PRODUCTS: {v_products_count} записей")
        
        result = db.execute_query("SELECT COUNT(*) as cnt FROM V_CRED_PROGRAMS")
        v_programs_count = result.get('data', [[0]])[0][0] if result.get('data') else 0
        print(f"   V_CRED_PROGRAMS: {v_programs_count} записей")
        
        # 3. Прямой запрос к представлениям
        if v_products_count > 0:
            print("\n3. ПРИМЕРЫ ТОВАРОВ ИЗ V_CRED_PRODUCTS:")
            result = db.execute_query("SELECT * FROM V_CRED_PRODUCTS WHERE ROWNUM <= 3")
            if result.get('data'):
                print(f"   Колонки: {result.get('columns', [])}")
                for i, row in enumerate(result['data'][:3], 1):
                    print(f"   Товар {i}: {dict(zip(result['columns'], row))}")
        
        if v_programs_count > 0:
            print("\n4. ПРИМЕРЫ ПРОГРАММ ИЗ V_CRED_PROGRAMS:")
            result = db.execute_query("SELECT * FROM V_CRED_PROGRAMS WHERE ROWNUM <= 3")
            if result.get('data'):
                print(f"   Колонки: {result.get('columns', [])}")
                for i, row in enumerate(result['data'][:3], 1):
                    print(f"   Программа {i}: {dict(zip(result['columns'], row))}")
        
        # 4. Тест пакета GET_PRODUCTS
        print("\n5. ТЕСТ CRED_OPERATOR_PKG.GET_PRODUCTS:")
        try:
            rows = db.fetch_refcursor(
                "BEGIN CRED_OPERATOR_PKG.GET_PRODUCTS(:search, :lim, :cur); END;",
                {"search": None, "lim": 3},
                "cur",
            )
            print(f"   Вернул {len(rows)} строк")
            if rows:
                print(f"   Колонки: {list(rows[0].keys())}")
                print(f"   Первая строка: {rows[0]}")
            else:
                print("   ⚠ ПУСТОЙ РЕЗУЛЬТАТ!")
        except Exception as e:
            print(f"   ✗ ОШИБКА: {e}")
            import traceback
            traceback.print_exc()
        
        # 5. Тест пакета GET_PROGRAMS
        print("\n6. ТЕСТ CRED_ADMIN_PKG.GET_PROGRAMS:")
        try:
            rows = db.fetch_refcursor(
                "BEGIN CRED_ADMIN_PKG.GET_PROGRAMS(:bank, :term, :active, :cur); END;",
                {"bank": None, "term": None, "active": None},
                "cur",
            )
            print(f"   Вернул {len(rows)} строк")
            if rows:
                print(f"   Колонки: {list(rows[0].keys())}")
                print(f"   Первая строка: {rows[0]}")
            else:
                print("   ⚠ ПУСТОЙ РЕЗУЛЬТАТ!")
        except Exception as e:
            print(f"   ✗ ОШИБКА: {e}")
            import traceback
            traceback.print_exc()
        
        # 6. Тест контроллера
        print("\n7. ТЕСТ CreditController.get_products():")
        result = CreditController.get_products(limit=3)
        print(f"   Success: {result.get('success')}")
        if result.get('error'):
            print(f"   Error: {result.get('error')}")
        print(f"   Data count: {len(result.get('data', []))}")
        if result.get('data'):
            print(f"   First item: {result['data'][0]}")
        else:
            print("   ⚠ ПУСТЫЕ ДАННЫЕ!")
        
        print("\n8. ТЕСТ CreditController.get_programs():")
        result = CreditController.get_programs()
        print(f"   Success: {result.get('success')}")
        if result.get('error'):
            print(f"   Error: {result.get('error')}")
        print(f"   Data count: {len(result.get('data', []))}")
        if result.get('data'):
            print(f"   First item: {result['data'][0]}")
        else:
            print("   ⚠ ПУСТЫЕ ДАННЫЕ!")
            
except Exception as e:
    print(f"\n✗ ОШИБКА: {e}")
    import traceback
    traceback.print_exc()
