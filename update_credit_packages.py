#!/usr/bin/env python3
"""
Скрипт для обновления только пакетов кредитов в БД
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models.database import DatabaseModel
import re

def _is_plsql_block(block: str) -> bool:
    """Проверяет, что блок — PL/SQL (package, trigger, anonymous block)."""
    u = block.upper()
    if "CREATE OR REPLACE PACKAGE" in u:
        return True
    if "CREATE OR REPLACE TRIGGER" in u:
        return True
    if "CREATE OR REPLACE PROCEDURE" in u or "CREATE OR REPLACE FUNCTION" in u:
        return True
    if re.search(r"\bBEGIN\b", u) and re.search(r"\bEND\s*;", u):
        return True
    return False

def read_sql_file(filepath):
    """Читает SQL файл и разбивает на блоки по / на отдельной строке"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Разбиваем на блоки по / на отдельной строке (SQL*Plus style)
    import re
    normalized = content.replace("\r\n", "\n").strip()
    parts = re.split(r"\n\s*/\s*\n", normalized)
    blocks = [p.strip() for p in parts if p.strip() and not p.strip().startswith('--')]
    
    return blocks

def main():
    print("=" * 60)
    print("Обновление пакетов кредитов в БД")
    print("=" * 60)
    
    try:
        with DatabaseModel() as db:
            # Обновляем пакет админки
            print("\n1. Обновление CRED_ADMIN_PKG...")
            admin_file = 'sql/08_cred_admin_package.sql'
            if os.path.exists(admin_file):
                blocks = read_sql_file(admin_file)
                print(f"   Найдено {len(blocks)} блоков")
                for i, block in enumerate(blocks, 1):
                    try:
                        # Убираем завершающий /
                        block = re.sub(r'\s*/\s*$', '', block.strip())
                        if block:
                            with db.connection.cursor() as cursor:
                                cursor.execute(block)
                            print(f"   Блок {i} выполнен успешно")
                    except Exception as e:
                        print(f"   Ошибка в блоке {i}: {e}")
                db.connection.commit()
                print("   ✓ CRED_ADMIN_PKG обновлен")
            else:
                print(f"   ✗ Файл {admin_file} не найден")
            
            # Обновляем пакет оператора
            print("\n2. Обновление CRED_OPERATOR_PKG...")
            operator_file = 'sql/09_cred_operator_package.sql'
            if os.path.exists(operator_file):
                blocks = read_sql_file(operator_file)
                print(f"   Найдено {len(blocks)} блоков")
                for i, block in enumerate(blocks, 1):
                    try:
                        # Убираем завершающий / если есть
                        block = re.sub(r'\s*/\s*$', '', block.strip())
                        if not block or block.startswith('--'):
                            continue
                        # Для PL/SQL блоков убираем завершающий / из конца
                        if _is_plsql_block(block):
                            block = re.sub(r'\s*/\s*$', '', block)
                        print(f"   Выполняю блок {i}/{len(blocks)}...")
                        with db.connection.cursor() as cursor:
                            cursor.execute(block)
                        print(f"   ✓ Блок {i} выполнен успешно")
                    except Exception as e:
                        print(f"   ✗ Ошибка в блоке {i}: {e}")
                        # Продолжаем выполнение других блоков
                db.connection.commit()
                print("   ✓ CRED_OPERATOR_PKG обновлен")
            else:
                print(f"   ✗ Файл {operator_file} не найден")
            
            # Проверяем результат
            print("\n3. Проверка обновленных пакетов...")
            result = CreditController.get_programs()
            print(f"   GET_PROGRAMS: {len(result.get('data', []))} программ")
            
            result = CreditController.get_products(limit=3)
            print(f"   GET_PRODUCTS: {len(result.get('data', []))} товаров")
            
            print("\n✓ Обновление завершено!")
            
    except Exception as e:
        print(f"\n✗ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    from controllers.credit_controller import CreditController
    main()
