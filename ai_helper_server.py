#!/usr/bin/env python3
"""
AI Helper для сервера (без Selenium)
Использует заглушку для генерации SQL скриптов создания таблиц Oracle
"""
from typing import Dict, Any


def generate_table_sql_stub(description: str) -> str:
    """
    Генерирует SQL скрипт для создания таблицы Oracle на основе описания
    (Заглушка для серверного режима без Selenium)
    
    Args:
        description: Описание таблицы на русском или английском
        
    Returns:
        SQL скрипт для создания таблицы Oracle
    """
    # Извлекаем имя таблицы из описания
    table_name = "NEW_TABLE"
    description_lower = description.lower()
    
    # Пытаемся найти имя таблицы в описании
    words = description.split()
    for i, word in enumerate(words):
        if word.lower() in ["таблица", "table", "таблицу", "таблицы"]:
            if i + 1 < len(words):
                table_name = words[i + 1].upper().replace(",", "").replace(".", "")
                break
    
    # Пытаемся извлечь поля из описания
    columns = []
    
    # Ищем упоминания полей
    if "поля" in description_lower or "fields" in description_lower or "columns" in description_lower:
        # Простой парсинг: ищем паттерны типа "id (число)", "name (строка)"
        import re
        field_patterns = re.findall(r'(\w+)\s*\([^)]+\)', description, re.IGNORECASE)
        if field_patterns:
            for field in field_patterns[:10]:  # Максимум 10 полей
                field_lower = field.lower()
                if field_lower in ['id', 'идентификатор']:
                    columns.append("    ID NUMBER PRIMARY KEY")
                elif field_lower in ['name', 'имя', 'название']:
                    columns.append("    NAME VARCHAR2(100) NOT NULL")
                elif field_lower in ['email', 'почта']:
                    columns.append("    EMAIL VARCHAR2(255)")
                elif 'дата' in field_lower or 'date' in field_lower:
                    columns.append("    CREATED_DATE DATE DEFAULT SYSDATE")
                else:
                    columns.append(f"    {field.upper()} VARCHAR2(100)")
    
    # Если не нашли поля, используем стандартный набор
    if not columns:
        columns = [
            "    ID NUMBER PRIMARY KEY",
            "    NAME VARCHAR2(100) NOT NULL",
            "    DESCRIPTION VARCHAR2(500)",
            "    CREATED_DATE DATE DEFAULT SYSDATE",
            "    STATUS VARCHAR2(20) DEFAULT 'ACTIVE'"
        ]
    
    # Формируем SQL
    sql = f"""-- Generated SQL for: {description}
-- ⚠️ Server mode: This is a template generated without AI.
-- Please review and modify the SQL script as needed.

CREATE TABLE {table_name} (
{',\\n'.join(columns)}
);

-- Add indexes if needed
CREATE INDEX IDX_{table_name}_NAME ON {table_name}(NAME);

-- Add comments
COMMENT ON TABLE {table_name} IS '{description}';
"""
    
    # Добавляем комментарии к колонкам
    for col in columns:
        col_name = col.split()[0]  # Первое слово - имя колонки
        sql += f"COMMENT ON COLUMN {table_name}.{col_name} IS 'Auto-generated column';\n"
    
    return sql


def generate_table_sql(description: str, use_ai: bool = False) -> Dict[str, Any]:
    """
    Генерирует SQL скрипт для создания таблицы Oracle на основе описания
    
    Args:
        description: Описание таблицы (на русском или английском)
        use_ai: Игнорируется на сервере (всегда используется заглушка)
        
    Returns:
        Словарь с результатом:
        {
            "success": bool,
            "sql": str,  # SQL скрипт
            "error": str  # Сообщение об ошибке (если success=False)
        }
    """
    if not description or not description.strip():
        return {
            "success": False,
            "error": "Описание таблицы не может быть пустым"
        }
    
    try:
        sql = generate_table_sql_stub(description)
        return {
            "success": True,
            "sql": sql,
            "note": "Generated using server stub (Selenium not available on server)"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Error generating SQL: {str(e)}"
        }


def is_ai_available() -> bool:
    """
    Проверяет, доступен ли ИИ (всегда False на сервере)
    
    Returns:
        False (ИИ недоступен на сервере)
    """
    return False


# Для совместимости с основным ai_helper.py
IS_SERVER = True

