"""
Контроллер SQL запросов
"""
from models.database import DatabaseModel
from typing import Dict, Any


class SQLController:
    """Класс для управления SQL запросами"""
    
    @staticmethod
    def execute(sql: str) -> Dict[str, Any]:
        """Выполняет SQL запрос"""
        if not sql or not sql.strip():
            return {
                "success": False,
                "message": "SQL запрос не может быть пустым"
            }
        
        try:
            with DatabaseModel() as db:
                return db.execute_query(sql)
        except Exception as e:
            return {
                "success": False,
                "message": str(e),
                "data": [],
                "columns": [],
                "rowcount": 0
            }

