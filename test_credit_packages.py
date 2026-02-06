#!/usr/bin/env python3
"""Тест кредитных пакетов - использует тот же метод подключения что и приложение"""
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

print("=" * 60)
print("ТЕСТ КРЕДИТНЫХ ПАКЕТОВ")
print("=" * 60)

try:
    from models.database import DatabaseModel
    
    # 1. Проверка данных в таблицах
    print("\n1. Проверка данных в таблицах:")
    with DatabaseModel() as db:
        result = db.execute_query("SELECT COUNT(*) as cnt FROM CRED_PRODUCTS")
        products_count = result.get('data', [[0]])[0][0] if result.get('data') else 0
        print(f"   CRED_PRODUCTS: {products_count} записей")
        
        result = db.execute_query("SELECT COUNT(*) as cnt FROM CRED_PROGRAMS")
        programs_count = result.get('data', [[0]])[0][0] if result.get('data') else 0
        print(f"   CRED_PROGRAMS: {programs_count} записей")
        
        # 2. Проверка представлений
        print("\n2. Проверка представлений:")
        result = db.execute_query("SELECT COUNT(*) as cnt FROM V_CRED_PRODUCTS")
        v_products = result.get('data', [[0]])[0][0] if result.get('data') else 0
        print(f"   V_CRED_PRODUCTS: {v_products} записей")
        
        result = db.execute_query("SELECT COUNT(*) as cnt FROM V_CRED_PROGRAMS")
        v_programs = result.get('data', [[0]])[0][0] if result.get('data') else 0
        print(f"   V_CRED_PROGRAMS: {v_programs} записей")
        
        # 3. Прямой SQL запрос к представлению (как в табло рейсов)
        print("\n3. Прямой SQL запрос к V_CRED_PRODUCTS (как в табло рейсов):")
        result = db.execute_query("SELECT * FROM V_CRED_PRODUCTS WHERE ROWNUM <= 3")
        if result.get('data'):
            print(f"   ✓ Получено {len(result['data'])} строк")
            print(f"   Колонки: {result.get('columns', [])}")
            for i, row in enumerate(result['data'][:2], 1):
                print(f"   Строка {i}: {dict(zip(result['columns'], row))}")
        else:
            print("   ✗ Нет данных!")
        
        # 4. Тест пакета GET_PRODUCTS
        print("\n4. Тест CRED_OPERATOR_PKG.GET_PRODUCTS:")
        try:
            rows = db.fetch_refcursor(
                "BEGIN CRED_OPERATOR_PKG.GET_PRODUCTS(:search, :lim, :cur); END;",
                {"search": None, "lim": 3},
                "cur",
            )
            print(f"   Результат: {len(rows)} строк")
            if rows:
                print(f"   ✓ Пакет работает! Ключи: {list(rows[0].keys())}")
                print(f"   Первая строка: {dict(list(rows[0].items())[:5])}")
            else:
                print("   ✗ Пакет вернул пустой результат!")
        except Exception as e:
            print(f"   ✗ Ошибка пакета: {e}")
            import traceback
            traceback.print_exc()
        
        # 5. Тест пакета GET_PROGRAMS
        print("\n5. Тест CRED_ADMIN_PKG.GET_PROGRAMS:")
        try:
            rows = db.fetch_refcursor(
                "BEGIN CRED_ADMIN_PKG.GET_PROGRAMS(:bank, :term, :active, :cur); END;",
                {"bank": None, "term": None, "active": None},
                "cur",
            )
            print(f"   Результат: {len(rows)} строк")
            if rows:
                print(f"   ✓ Пакет работает! Ключи: {list(rows[0].keys())}")
                print(f"   Первая строка: {dict(list(rows[0].items())[:5])}")
            else:
                print("   ✗ Пакет вернул пустой результат!")
        except Exception as e:
            print(f"   ✗ Ошибка пакета: {e}")
            import traceback
            traceback.print_exc()
        
        # 6. Тест контроллера
        print("\n6. Тест CreditController.get_products():")
        from controllers.credit_controller import CreditController
        result = CreditController.get_products(limit=3)
        print(f"   Success: {result.get('success')}")
        print(f"   Data count: {len(result.get('data', []))}")
        if result.get('error'):
            print(f"   Error: {result.get('error')}")
        if result.get('data'):
            print(f"   ✓ Первый товар: {result['data'][0].get('name', 'N/A')}")
        else:
            print("   ✗ ПУСТЫЕ ДАННЫЕ!")
            
except Exception as e:
    print(f"\n✗ ОШИБКА: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
