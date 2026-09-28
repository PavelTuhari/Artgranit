#!/usr/bin/env python3
"""
Простой скрипт для обновления только пакетов кредитов
Использует тот же подход, что и deploy_oracle_objects.py
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

# Импортируем функции из deploy_oracle_objects
from deploy_oracle_objects import _sql_blocks, _is_plsql_block, _split_ddl_dml
import re

def main():
    print("=" * 60)
    print("Обновление пакетов кредитов в БД")
    print("=" * 60)
    
    try:
        from models.database import DatabaseConnection
        conn = DatabaseConnection.get_connection()
        cursor = conn.cursor()
    except Exception as e:
        print(f"✗ Ошибка подключения: {e}")
        return
    
    files_to_update = [
        ("08_cred_admin_package.sql", "CRED_ADMIN_PKG"),
        ("09_cred_operator_package.sql", "CRED_OPERATOR_PKG"),
    ]
    
    ok = 0
    err = 0
    
    for filename, pkg_name in files_to_update:
        filepath = ROOT / "sql" / filename
        if not filepath.exists():
            print(f"\n✗ Файл {filename} не найден")
            continue
        
        print(f"\n📦 Обновление {pkg_name} из {filename}...")
        try:
            text = filepath.read_text(encoding="utf-8", errors="replace")
            blocks = _sql_blocks(text)
            print(f"   Найдено {len(blocks)} блоков")
            
            for bi, block in enumerate(blocks, 1):
                block = re.sub(r"\s*/\s*$", "", block.strip())
                if not block:
                    continue
                
                try:
                    if _is_plsql_block(block):
                        cursor.execute(block)
                        conn.commit()
                        ok += 1
                        print(f"   ✓ Блок {bi} выполнен")
                    else:
                        # DDL/DML - разбиваем на отдельные команды
                        for stmt in _split_ddl_dml(block):
                            stmt = stmt.strip()
                            if not stmt:
                                continue
                            cursor.execute(stmt)
                            conn.commit()
                            ok += 1
                except Exception as e:
                    err += 1
                    print(f"   ✗ Ошибка в блоке {bi}: {e}")
                    # Продолжаем выполнение
            
            print(f"   ✓ {pkg_name} обновлен")
        except Exception as e:
            print(f"   ✗ Ошибка чтения файла: {e}")
            err += 1
    
    if cursor:
        try:
            cursor.close()
        except:
            pass
    if conn:
        try:
            conn.close()
        except:
            pass
    
    print(f"\n{'='*60}")
    print(f"Готово. Успешно: {ok}, ошибок: {err}.")
    if err == 0:
        print("✓ Все пакеты обновлены успешно!")
    else:
        print("⚠ Некоторые ошибки при обновлении. Проверьте вывод выше.")

if __name__ == '__main__':
    main()
