"""
Контроллер Dashboard
"""
from typing import Dict, Any
import sys
import os

# Добавляем корневую директорию в путь
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from models.database import DatabaseModel


class DashboardController:
    """Класс для управления Dashboard"""
    
    @staticmethod
    def get_metric(metric_name: str) -> Dict[str, Any]:
        """Получает конкретную метрику"""
        try:
            with DatabaseModel() as db:
                metrics_map = {
                    'instance': db.get_instance_info,
                    'memory': db.get_memory_metrics,
                    'cpu': db.get_cpu_metrics,
                    'sessions': db.get_sessions_metrics,
                    'uptime': db.get_uptime,
                    'tablespaces': db.get_tablespaces,
                    'top_sql': lambda: db.get_top_sql(5)
                }
                
                if metric_name in metrics_map:
                    result = metrics_map[metric_name]()
                    return {
                        "success": True,
                        "metric": metric_name,
                        "data": result,
                        "timestamp": __import__('datetime').datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Unknown metric: {metric_name}"
                    }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    def get_all_metrics() -> Dict[str, Any]:
        """Получает все метрики"""
        result = {
            "success": False,
            "metrics": {},
            "timestamp": __import__('datetime').datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        try:
            with DatabaseModel() as db:
                result["metrics"] = {
                    "instance": db.get_instance_info(),
                    "memory": db.get_memory_metrics(),
                    "cpu": db.get_cpu_metrics(),
                    "sessions": db.get_sessions_metrics(),
                    "uptime": db.get_uptime(),
                    "tablespaces": db.get_tablespaces(),
                    "top_sql": db.get_top_sql(5)
                }
                
                # Database size (может требовать DBA прав)
                try:
                    with db.connection.cursor() as cursor:
                        cursor.execute("""
                            SELECT 
                                ROUND(SUM(bytes)/1024/1024/1024, 2) as total_size_gb,
                                ROUND(SUM(bytes - NVL(free_space, 0))/1024/1024/1024, 2) as used_size_gb,
                                ROUND(SUM(NVL(free_space, 0))/1024/1024/1024, 2) as free_size_gb
                            FROM (
                                SELECT SUM(bytes) as bytes, 0 as free_space 
                                FROM dba_data_files
                                UNION ALL
                                SELECT 0, SUM(bytes) 
                                FROM dba_free_space
                            )
                        """)
                        row = cursor.fetchone()
                        if row:
                            total = float(row[0]) if row[0] else 0
                            used = float(row[1]) if row[1] else 0
                            result["metrics"]["database_size"] = {
                                "total_gb": total,
                                "used_gb": used,
                                "free_gb": float(row[2]) if row[2] else 0,
                                "usage_percent": round((used / total * 100) if total > 0 else 0, 2)
                            }
                except:
                    try:
                        with db.connection.cursor() as cursor:
                            cursor.execute("""
                                SELECT 
                                    ROUND(SUM(bytes)/1024/1024/1024, 2) as total_size_gb
                                FROM user_segments
                            """)
                            row = cursor.fetchone()
                            if row:
                                total = float(row[0]) if row[0] else 0
                                result["metrics"]["database_size"] = {
                                    "total_gb": total,
                                    "used_gb": total,
                                    "free_gb": 0,
                                    "usage_percent": 0
                                }
                    except:
                        result["metrics"]["database_size"] = {
                            "total_gb": 0,
                            "used_gb": 0,
                            "free_gb": 0,
                            "usage_percent": 0
                        }
                
                result["success"] = True
        except Exception as e:
            result["error"] = str(e)
            import traceback
            result["traceback"] = traceback.format_exc()
        
        return result

