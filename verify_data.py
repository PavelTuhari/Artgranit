#!/usr/bin/env python3
"""
Быстрая проверка данных и API - использует тот же метод подключения что и приложение
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

print("Проверка данных кредитов...")
print("=" * 60)

# 1. Проверка через прямой SQL
try:
    from models.database import DatabaseModel
    with DatabaseModel() as db:
        # Товары
        result = db.execute_query("SELECT COUNT(*) as cnt FROM CRED_PRODUCTS")
        products = result.get('data', [[0]])[0][0] if result.get('data') else 0
        print(f"1. Товаров в CRED_PRODUCTS: {products}")
        
        # Программы
        result = db.execute_query("SELECT COUNT(*) as cnt FROM CRED_PROGRAMS")
        programs = result.get('data', [[0]])[0][0] if result.get('data') else 0
        print(f"2. Программ в CRED_PROGRAMS: {programs}")
        
        # Представления
        result = db.execute_query("SELECT COUNT(*) as cnt FROM V_CRED_PRODUCTS")
        v_products = result.get('data', [[0]])[0][0] if result.get('data') else 0
        print(f"3. Товаров в V_CRED_PRODUCTS: {v_products}")
        
        result = db.execute_query("SELECT COUNT(*) as cnt FROM V_CRED_PROGRAMS")
        v_programs = result.get('data', [[0]])[0][0] if result.get('data') else 0
        print(f"4. Программ в V_CRED_PROGRAMS: {v_programs}")
        
        if products == 0:
            print("\n⚠ ТОВАРОВ НЕТ! Загрузите демо-данные:")
            print("   python3 deploy_oracle_objects.py")
        
        if programs == 0:
            print("\n⚠ ПРОГРАММ НЕТ! Загрузите демо-данные:")
            print("   python3 deploy_oracle_objects.py")
        
        # Тест пакета
        if products > 0:
            print("\n5. Тест GET_PRODUCTS:")
            try:
                rows = db.fetch_refcursor(
                    "BEGIN CRED_OPERATOR_PKG.GET_PRODUCTS(:search, :lim, :cur); END;",
                    {"search": None, "lim": 3},
                    "cur",
                )
                print(f"   Результат: {len(rows)} строк")
                if rows:
                    print(f"   ✓ Пакет работает! Ключи: {list(rows[0].keys())}")
                else:
                    print("   ✗ Пакет вернул пустой результат!")
            except Exception as e:
                print(f"   ✗ Ошибка пакета: {e}")
        
        if programs > 0:
            print("\n6. Тест GET_PROGRAMS:")
            try:
                rows = db.fetch_refcursor(
                    "BEGIN CRED_ADMIN_PKG.GET_PROGRAMS(:bank, :term, :active, :cur); END;",
                    {"bank": None, "term": None, "active": None},
                    "cur",
                )
                print(f"   Результат: {len(rows)} строк")
                if rows:
                    print(f"   ✓ Пакет работает! Ключи: {list(rows[0].keys())}")
                else:
                    print("   ✗ Пакет вернул пустой результат!")
            except Exception as e:
                print(f"   ✗ Ошибка пакета: {e}")
        
        # Тест контроллера
        print("\n7. Тест контроллера:")
        from controllers.credit_controller import CreditController
        
        result = CreditController.get_products(limit=3)
        print(f"   get_products(): success={result.get('success')}, count={len(result.get('data', []))}")
        if result.get('error'):
            print(f"   Error: {result.get('error')}")
        
        result = CreditController.get_programs()
        print(f"   get_programs(): success={result.get('success')}, count={len(result.get('data', []))}")
        if result.get('error'):
            print(f"   Error: {result.get('error')}")
            
except Exception as e:
    print(f"\n✗ ОШИБКА: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
