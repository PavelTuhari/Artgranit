#!/usr/bin/env python3
"""Быстрая проверка - использует тот же метод подключения что и приложение"""
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

print("Быстрая проверка данных кредитов...")
print("=" * 60)

try:
    from models.database import DatabaseModel
    from controllers.credit_controller import CreditController
    
    print("\n1. Тест подключения и простого запроса...")
    with DatabaseModel() as db:
        result = db.execute_query("SELECT COUNT(*) as cnt FROM CRED_PRODUCTS")
        products = result.get('data', [[0]])[0][0] if result.get('data') else 0
        print(f"   ✓ Товаров в БД: {products}")
        
        result = db.execute_query("SELECT COUNT(*) as cnt FROM CRED_PROGRAMS")
        programs = result.get('data', [[0]])[0][0] if result.get('data') else 0
        print(f"   ✓ Программ в БД: {programs}")
    
    print("\n2. Тест контроллера get_products()...")
    result = CreditController.get_products(limit=3)
    print(f"   Success: {result.get('success')}")
    print(f"   Data count: {len(result.get('data', []))}")
    if result.get('error'):
        print(f"   Error: {result.get('error')}")
    if result.get('data'):
        print(f"   ✓ Первый товар: {result['data'][0].get('name', 'N/A')}")
    
    print("\n3. Тест контроллера get_programs()...")
    result = CreditController.get_programs()
    print(f"   Success: {result.get('success')}")
    print(f"   Data count: {len(result.get('data', []))}")
    if result.get('error'):
        print(f"   Error: {result.get('error')}")
    if result.get('data'):
        print(f"   ✓ Первая программа: {result['data'][0].get('name', 'N/A')}")
    
    print("\n" + "=" * 60)
    print("✓ Проверка завершена!")
    
except Exception as e:
    print(f"\n✗ ОШИБКА: {e}")
    import traceback
    traceback.print_exc()
