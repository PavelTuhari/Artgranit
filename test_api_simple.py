#!/usr/bin/env python3
"""Простой тест API - использует тот же метод подключения что и приложение"""
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

# Теперь импортируем все остальное
print("Тест контроллера кредитов...")
print("=" * 60)

try:
    from controllers.credit_controller import CreditController
    
    print("\n1. Тест get_products():")
    result = CreditController.get_products(limit=5)
    print(f"   Success: {result.get('success')}")
    print(f"   Error: {result.get('error', 'None')}")
    print(f"   Data count: {len(result.get('data', []))}")
    if result.get('data'):
        print(f"   First item keys: {list(result['data'][0].keys())}")
        print(f"   First item sample: {dict(list(result['data'][0].items())[:3])}")
    else:
        print("   ⚠ ПУСТЫЕ ДАННЫЕ!")
        if result.get('error'):
            print(f"   Ошибка: {result['error']}")
    
    print("\n2. Тест get_programs():")
    result = CreditController.get_programs()
    print(f"   Success: {result.get('success')}")
    print(f"   Error: {result.get('error', 'None')}")
    print(f"   Data count: {len(result.get('data', []))}")
    if result.get('data'):
        print(f"   First item keys: {list(result['data'][0].keys())}")
        print(f"   First item sample: {dict(list(result['data'][0].items())[:3])}")
    else:
        print("   ⚠ ПУСТЫЕ ДАННЫЕ!")
        if result.get('error'):
            print(f"   Ошибка: {result['error']}")
            
except Exception as e:
    print(f"\n✗ ОШИБКА: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
