#!/usr/bin/env python3
"""Тестовый скрипт для проверки метрик Oracle"""
from models.database import DatabaseModel

print("Testing Oracle metrics...")
print("=" * 50)

with DatabaseModel() as db:
    # Тест памяти
    print("\n1. Memory Metrics:")
    with db.connection.cursor() as cursor:
        # Проверяем доступные значения в v$sgainfo
        cursor.execute("SELECT name, bytes/1024/1024/1024 as gb FROM v$sgainfo ORDER BY name")
        rows = cursor.fetchall()
        print(f"   Available SGA info entries: {len(rows)}")
        for row in rows[:5]:
            print(f"     {row[0]}: {row[1]:.2f} GB")
        
        # Проверяем Total SGA
        cursor.execute("SELECT name, bytes/1024/1024/1024 as gb FROM v$sgainfo WHERE name = 'Total SGA'")
        total_row = cursor.fetchone()
        print(f"   Total SGA: {total_row}")
        
        # Проверяем Free SGA
        cursor.execute("SELECT name, bytes/1024/1024/1024 as gb FROM v$sgainfo WHERE name = 'Free SGA Memory Available'")
        free_row = cursor.fetchone()
        print(f"   Free SGA: {free_row}")
    
    # Тест CPU
    print("\n2. CPU Metrics:")
    with db.connection.cursor() as cursor:
        # Проверяем доступные метрики CPU
        cursor.execute("""
            SELECT DISTINCT metric_name 
            FROM v$sysmetric 
            WHERE metric_name LIKE '%CPU%' 
            ORDER BY metric_name
        """)
        cpu_metrics = cursor.fetchall()
        print(f"   Available CPU metrics: {len(cpu_metrics)}")
        for metric in cpu_metrics[:3]:
            print(f"     {metric[0]}")
        
        # Проверяем текущую метрику
        cursor.execute("""
            SELECT metric_name, VALUE, group_id
            FROM v$sysmetric 
            WHERE metric_name LIKE '%CPU%'
            ORDER BY end_time DESC
            FETCH FIRST 3 ROWS ONLY
        """)
        cpu_rows = cursor.fetchall()
        print(f"   Current CPU metrics:")
        for row in cpu_rows:
            print(f"     {row[0]}: {row[1]} (group_id: {row[2]})")
    
    # Тест метода get_memory_metrics
    print("\n3. get_memory_metrics() result:")
    mem_result = db.get_memory_metrics()
    print(f"   {mem_result}")
    
    # Тест метода get_cpu_metrics
    print("\n4. get_cpu_metrics() result:")
    cpu_result = db.get_cpu_metrics()
    print(f"   {cpu_result}")

print("\n" + "=" * 50)
print("Test completed.")

