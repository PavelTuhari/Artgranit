#!/usr/bin/env python3
"""
Проверка данных через работающее приложение (если оно запущено)
Использует HTTP API вместо прямого подключения к БД
"""
import sys
import requests
import json

BASE_URL = "http://localhost:3003"

def check_api():
    """Проверяет данные через API"""
    print("Проверка данных через API приложения...")
    print("=" * 60)
    print(f"URL: {BASE_URL}")
    print("(Убедитесь, что приложение запущено на localhost:3003)")
    print()
    
    # Нужна авторизация, но можно проверить структуру ответа
    try:
        # Попытка получить данные (может вернуть 401, но структура ответа будет видна)
        response = requests.get(
            f"{BASE_URL}/api/credit-operator/products?limit=3",
            timeout=5
        )
        print(f"Status: {response.status_code}")
        if response.status_code == 401:
            print("⚠ Требуется авторизация (это нормально)")
            print("   Для полной проверки нужно авторизоваться в браузере")
        elif response.status_code == 200:
            data = response.json()
            print(f"✓ Success: {data.get('success')}")
            print(f"✓ Data count: {len(data.get('data', []))}")
            if data.get('data'):
                print(f"✓ First product: {data['data'][0].get('name', 'N/A')}")
        else:
            print(f"Response: {response.text[:200]}")
    except requests.exceptions.ConnectionError:
        print("✗ Не удалось подключиться к приложению")
        print("   Убедитесь, что приложение запущено:")
        print("   python3 app.py")
    except Exception as e:
        print(f"✗ Ошибка: {e}")
    
    print("\n" + "=" * 60)
    print("Рекомендация: Проверьте данные через браузер:")
    print(f"  {BASE_URL}/UNA.md/orasldev/credit-operator")
    print(f"  {BASE_URL}/UNA.md/orasldev/credit-admin")

if __name__ == '__main__':
    check_api()
