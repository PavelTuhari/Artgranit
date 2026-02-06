"""
Контроллер SQL запросов
"""
from models.database import DatabaseModel
from typing import Dict, Any
import re


class SQLController:
    """Класс для управления SQL запросами"""
    
    @staticmethod
    def _is_multiple_commands(sql: str) -> bool:
        """Проверяет, содержит ли SQL несколько команд"""
        sql_clean = sql.strip()
        if not sql_clean:
            return False
        
        # Удаляем комментарии для проверки
        # Убираем однострочные комментарии
        sql_no_single_comments = re.sub(r'--.*?$', '', sql, flags=re.MULTILINE)
        # Убираем многострочные комментарии
        sql_no_comments = re.sub(r'/\*.*?\*/', '', sql_no_single_comments, flags=re.DOTALL)
        
        # Считаем точки с запятой (не внутри строк)
        semicolon_count = 0
        in_string = False
        string_char = None
        
        for i, char in enumerate(sql_no_comments):
            if char in ("'", '"') and (i == 0 or sql_no_comments[i - 1] != '\\'):
                if not in_string:
                    in_string = True
                    string_char = char
                elif char == string_char:
                    in_string = False
                    string_char = None
            elif not in_string and char == ';':
                semicolon_count += 1
        
        return semicolon_count > 0
    
    @staticmethod
    def execute(sql: str) -> Dict[str, Any]:
        """Выполняет SQL запрос или скрипт"""
        if not sql or not sql.strip():
            return {
                "success": False,
                "message": "SQL запрос не может быть пустым"
            }
        
        try:
            with DatabaseModel() as db:
                # Проверяем, является ли это скриптом (несколько команд)
                if SQLController._is_multiple_commands(sql):
                    return db.execute_script(sql)
                else:
                    return db.execute_query(sql)
        except Exception as e:
            return {
                "success": False,
                "message": str(e),
                "data": [],
                "columns": [],
                "rowcount": 0
            }

