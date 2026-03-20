#!/usr/bin/env python3
"""
Скрипт для проверки данных кредитов в БД
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models.database import DatabaseModel
from controllers.credit_controller import CreditController

def main():
    print("=" * 60)
    print("Проверка данных кредитов в БД")
    print("=" * 60)
    
    try:
        with DatabaseModel() as db:
            # Проверяем товары
            print("\n1. Проверка товаров (CRED_PRODUCTS):")
            result = db.execute_query("SELECT COUNT(*) as cnt FROM CRED_PRODUCTS")
            count = result.get('data', [[0]])[0][0] if result.get('data') else 0
            print(f"   Товаров в таблице: {count}")
            
            if count > 0:
                result = db.execute_query("SELECT * FROM CRED_PRODUCTS WHERE ROWNUM <= 3")
                print(f"   Примеры товаров: {len(result.get('data', []))} строк")
                if result.get('data'):
                    print(f"   Колонки: {result.get('columns', [])}")
            
            # Проверяем представление товаров
            print("\n2. Проверка представления V_CRED_PRODUCTS:")
            result = db.execute_query("SELECT COUNT(*) as cnt FROM V_CRED_PRODUCTS")
            count = result.get('data', [[0]])[0][0] if result.get('data') else 0
            print(f"   Товаров в представлении: {count}")
            
            # Проверяем программы
            print("\n3. Проверка программ (CRED_PROGRAMS):")
            result = db.execute_query("SELECT COUNT(*) as cnt FROM CRED_PROGRAMS")
            count = result.get('data', [[0]])[0][0] if result.get('data') else 0
            print(f"   Программ в таблице: {count}")
            
            if count > 0:
                result = db.execute_query("SELECT * FROM CRED_PROGRAMS WHERE ROWNUM <= 3")
                print(f"   Примеры программ: {len(result.get('data', []))} строк")
                if result.get('data'):
                    print(f"   Колонки: {result.get('columns', [])}")
            
            # Проверяем представление программ
            print("\n4. Проверка представления V_CRED_PROGRAMS:")
            result = db.execute_query("SELECT COUNT(*) as cnt FROM V_CRED_PROGRAMS")
            count = result.get('data', [[0]])[0][0] if result.get('data') else 0
            print(f"   Программ в представлении: {count}")
            
            # Тестируем пакет GET_PRODUCTS
            print("\n5. Тестирование CRED_OPERATOR_PKG.GET_PRODUCTS:")
            try:
                rows = db.fetch_refcursor(
                    "BEGIN CRED_OPERATOR_PKG.GET_PRODUCTS(:search, :lim, :cur); END;",
                    {"search": None, "lim": 3},
                    "cur",
                )
                print(f"   Вернул {len(rows)} строк")
                if rows:
                    print(f"   Колонки первой строки: {list(rows[0].keys())}")
                    print(f"   Первая строка: {rows[0]}")
            except Exception as e:
                print(f"   ОШИБКА: {e}")
                import traceback
                traceback.print_exc()
            
            # Тестируем пакет GET_PROGRAMS
            print("\n6. Тестирование CRED_ADMIN_PKG.GET_PROGRAMS:")
            try:
                rows = db.fetch_refcursor(
                    "BEGIN CRED_ADMIN_PKG.GET_PROGRAMS(:bank, :term, :active, :cur); END;",
                    {"bank": None, "term": None, "active": None},
                    "cur",
                )
                print(f"   Вернул {len(rows)} строк")
                if rows:
                    print(f"   Колонки первой строки: {list(rows[0].keys())}")
                    print(f"   Первая строка: {rows[0]}")
            except Exception as e:
                print(f"   ОШИБКА: {e}")
                import traceback
                traceback.print_exc()
            
            # Тестируем контроллер
            print("\n7. Тестирование CreditController.get_products():")
            result = CreditController.get_products(limit=3)
            print(f"   Success: {result.get('success')}")
            if result.get('error'):
                print(f"   Error: {result.get('error')}")
            print(f"   Data count: {len(result.get('data', []))}")
            if result.get('data'):
                print(f"   First item: {result['data'][0]}")
            
            print("\n8. Тестирование CreditController.get_programs():")
            result = CreditController.get_programs()
            print(f"   Success: {result.get('success')}")
            if result.get('error'):
                print(f"   Error: {result.get('error')}")
            print(f"   Data count: {len(result.get('data', []))}")
            if result.get('data'):
                print(f"   First item: {result['data'][0]}")
            
    except Exception as e:
        print(f"\nОШИБКА подключения: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
