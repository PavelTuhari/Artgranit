#!/usr/bin/env python3
"""
Загрузка демо-данных для кредитов
"""
import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.chdir(ROOT)

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from deploy_oracle_objects import _sql_blocks, _is_plsql_block, _split_ddl_dml
import re

def main():
    print("=" * 60)
    print("Загрузка демо-данных для кредитов")
    print("=" * 60)
    
    try:
        from models.database import DatabaseConnection
        conn = DatabaseConnection.get_connection()
        cursor = conn.cursor()
    except Exception as e:
        print(f"✗ Ошибка подключения: {e}")
        return
    
    # Проверяем, есть ли уже данные
    print("\n1. Проверка существующих данных...")
    try:
        cursor.execute("SELECT COUNT(*) FROM CRED_PRODUCTS")
        products_count = cursor.fetchone()[0]
        print(f"   Товаров: {products_count}")
        
        cursor.execute("SELECT COUNT(*) FROM CRED_PROGRAMS")
        programs_count = cursor.fetchone()[0]
        print(f"   Программ: {programs_count}")
        
        if products_count > 0 and programs_count > 0:
            print("\n⚠ Данные уже есть в БД!")
            response = input("Перезагрузить демо-данные? (y/n): ")
            if response.lower() != 'y':
                print("Отменено.")
                return
            # Удаляем старые данные (правильный порядок - сначала зависимые)
            print("\n2. Удаление старых данных...")
            try:
                cursor.execute("DELETE FROM CRED_APPLICATIONS")
                conn.commit()
                cursor.execute("DELETE FROM CRED_PROGRAM_EXCLUDED_BRANDS")
                conn.commit()
                cursor.execute("DELETE FROM CRED_PROGRAM_CATEGORIES")
                conn.commit()
                cursor.execute("DELETE FROM CRED_PRODUCTS")
                conn.commit()
                cursor.execute("DELETE FROM CRED_PROGRAMS")
                conn.commit()
                cursor.execute("DELETE FROM CRED_BRANDS")
                conn.commit()
                cursor.execute("DELETE FROM CRED_CATEGORIES")
                conn.commit()
                cursor.execute("DELETE FROM CRED_BANKS")
                conn.commit()
                print("   ✓ Старые данные удалены")
            except Exception as e:
                print(f"   ⚠ Ошибка удаления (может быть нормально): {e}")
                conn.rollback()
    except Exception as e:
        print(f"   Ошибка проверки: {e}")
    
    # Загружаем демо-данные
    print("\n3. Загрузка демо-данных...")
    demo_file = ROOT / "sql" / "10_demo_data.sql"
    if not demo_file.exists():
        print(f"✗ Файл {demo_file} не найден")
        return
    
    text = demo_file.read_text(encoding="utf-8", errors="replace")
    blocks = _sql_blocks(text)
    print(f"   Найдено {len(blocks)} блоков")
    
    ok = 0
    err = 0
    
    for bi, block in enumerate(blocks, 1):
        block = re.sub(r"\s*/\s*$", "", block.strip())
        if not block or block.startswith('--'):
            continue
        
        try:
            if _is_plsql_block(block):
                cursor.execute(block)
                conn.commit()
                ok += 1
            else:
                for stmt in _split_ddl_dml(block):
                    stmt = stmt.strip()
                    if not stmt or stmt.startswith('--'):
                        continue
                    cursor.execute(stmt)
                    conn.commit()
                    ok += 1
            print(f"   ✓ Блок {bi} выполнен")
        except Exception as e:
            err += 1
            # Игнорируем ошибки дублирования (если данные уже есть)
            if "ORA-00001" in str(e) or "unique constraint" in str(e).lower():
                print(f"   ⚠ Блок {bi}: данные уже существуют (пропуск)")
            else:
                print(f"   ✗ Ошибка в блоке {bi}: {e}")
    
    # Проверяем результат
    print("\n4. Проверка загруженных данных...")
    cursor.execute("SELECT COUNT(*) FROM CRED_PRODUCTS")
    products_count = cursor.fetchone()[0]
    print(f"   Товаров: {products_count}")
    
    cursor.execute("SELECT COUNT(*) FROM CRED_PROGRAMS")
    programs_count = cursor.fetchone()[0]
    print(f"   Программ: {programs_count}")
    
    cursor.execute("SELECT COUNT(*) FROM CRED_BANKS")
    banks_count = cursor.fetchone()[0]
    print(f"   Банков: {banks_count}")
    
    if cursor:
        cursor.close()
    if conn:
        conn.close()
    
    print(f"\n{'='*60}")
    print(f"Готово. Успешно: {ok}, ошибок: {err}.")
    if products_count > 0 and programs_count > 0:
        print("✓ Демо-данные загружены успешно!")
    else:
        print("⚠ Данные не загружены. Проверьте ошибки выше.")

if __name__ == '__main__':
    main()
