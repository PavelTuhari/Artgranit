"""
Модель для работы с базой данных Oracle
"""
import oracledb
import zipfile
import os
from typing import Optional, Dict, List, Any
from datetime import datetime
from config import Config


class DatabaseConnection:
    """Класс для управления подключениями к Oracle Database"""
    
    _pool: Optional[oracledb.ConnectionPool] = None
    _wallet_extracted: bool = False
    
    @classmethod
    def extract_wallet(cls) -> bool:
        """Извлекает wallet из ZIP архива"""
        if cls._wallet_extracted and os.path.exists(Config.WALLET_DIR):
            return True
        
        try:
            if os.path.exists(Config.WALLET_DIR):
                cls._wallet_extracted = True
                return True
            
            if not os.path.exists(Config.WALLET_ZIP):
                return False
            
            with zipfile.ZipFile(Config.WALLET_ZIP, 'r') as zip_ref:
                zip_ref.extractall(Config.WALLET_DIR)
            
            cls._wallet_extracted = True
            return True
        except Exception as e:
            print(f"Ошибка при извлечении wallet: {str(e)}")
            return False
    
    @classmethod
    def get_connection(cls) -> oracledb.Connection:
        """Получает подключение к базе данных"""
        if not cls.extract_wallet():
            raise Exception("Не удалось извлечь wallet")
        
        wallet_path = os.path.abspath(Config.WALLET_DIR)
        wallet_pem = os.path.join(wallet_path, "ewallet.pem")
        
        if os.path.exists(wallet_pem):
            connection = oracledb.connect(
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                dsn=Config.CONNECT_STRING,
                wallet_location=wallet_path,
                wallet_password=Config.WALLET_PASSWORD
            )
        else:
            connection = oracledb.connect(
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                dsn=Config.CONNECT_STRING,
                config_dir=wallet_path
            )
        
        return connection
    
    @classmethod
    def get_pool(cls) -> oracledb.ConnectionPool:
        """Получает connection pool"""
        if cls._pool is not None:
            return cls._pool
        
        if not cls.extract_wallet():
            raise Exception("Не удалось извлечь wallet")
        
        wallet_path = os.path.abspath(Config.WALLET_DIR)
        wallet_pem = os.path.join(wallet_path, "ewallet.pem")
        
        if os.path.exists(wallet_pem):
            cls._pool = oracledb.create_pool(
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                dsn=Config.CONNECT_STRING,
                wallet_location=wallet_path,
                wallet_password=Config.WALLET_PASSWORD,
                min=1,
                max=5,
                increment=1
            )
        else:
            cls._pool = oracledb.create_pool(
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                dsn=Config.CONNECT_STRING,
                config_dir=wallet_path,
                min=1,
                max=5,
                increment=1
            )
        
        return cls._pool
    
    @classmethod
    def close_pool(cls):
        """Закрывает connection pool"""
        if cls._pool is not None:
            cls._pool.close()
            cls._pool = None


class DatabaseModel:
    """Модель для работы с данными базы данных"""
    
    def __init__(self):
        self.connection = None
    
    def __enter__(self):
        self.connection = DatabaseConnection.get_connection()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.connection:
            self.connection.close()
    
    def execute_query(self, sql: str) -> Dict[str, Any]:
        """Выполняет SQL запрос"""
        result = {
            "success": False,
            "data": [],
            "columns": [],
            "rowcount": 0,
            "message": ""
        }
        
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(sql)
                
                if cursor.description:
                    result["columns"] = [desc[0] for desc in cursor.description]
                
                rows = cursor.fetchall()
                result["data"] = [list(row) for row in rows]
                result["rowcount"] = len(rows)
                result["success"] = True
                result["message"] = f"Запрос выполнен успешно. Найдено строк: {len(rows)}"
        except Exception as e:
            result["message"] = str(e)
            import traceback
            result["traceback"] = traceback.format_exc()
        
        return result
    
    def get_instance_info(self) -> Dict[str, Any]:
        """Получает информацию об экземпляре БД"""
        with self.connection.cursor() as cursor:
            cursor.execute("""
                SELECT 
                    instance_name,
                    host_name,
                    version,
                    status,
                    database_status
                FROM v$instance
            """)
            row = cursor.fetchone()
            if row:
                return {
                    "instance_name": row[0],
                    "host_name": row[1],
                    "version": row[2],
                    "status": row[3],
                    "database_status": row[4]
                }
        return {}
    
    def get_memory_metrics(self) -> Dict[str, Any]:
        """Получает метрики памяти"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        ROUND(SUM(bytes)/1024/1024/1024, 2) as total_gb,
                        ROUND(SUM(bytes - NVL(free_space, 0))/1024/1024/1024, 2) as used_gb,
                        ROUND(SUM(NVL(free_space, 0))/1024/1024/1024, 2) as free_gb
                    FROM (
                        SELECT bytes, 0 as free_space FROM v$sgainfo WHERE name = 'Total SGA'
                        UNION ALL
                        SELECT 0, bytes FROM v$sgainfo WHERE name = 'Free SGA Memory Available'
                    )
                """)
                row = cursor.fetchone()
                if row:
                    total = float(row[0]) if row[0] else 0
                    used = float(row[1]) if row[1] else 0
                    return {
                        "total_gb": total,
                        "used_gb": used,
                        "free_gb": float(row[2]) if row[2] else 0,
                        "usage_percent": round((used / total * 100) if total > 0 else 0, 2)
                    }
        except:
            pass
        return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "usage_percent": 0}
    
    def get_cpu_metrics(self) -> Dict[str, Any]:
        """Получает метрики CPU"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        ROUND(VALUE/100, 2) as cpu_usage_percent
                    FROM v$sysmetric
                    WHERE metric_name = 'CPU Usage Per Sec'
                    AND group_id = 2
                    ORDER BY end_time DESC
                    FETCH FIRST 1 ROWS ONLY
                """)
                row = cursor.fetchone()
                if row:
                    return {"usage_percent": float(row[0]) if row[0] else 0}
        except:
            pass
        return {"usage_percent": 0}
    
    def get_sessions_metrics(self) -> Dict[str, Any]:
        """Получает метрики сессий"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_sessions,
                        COUNT(CASE WHEN status = 'ACTIVE' THEN 1 END) as active_sessions,
                        COUNT(CASE WHEN status = 'INACTIVE' THEN 1 END) as inactive_sessions
                    FROM v$session
                    WHERE username IS NOT NULL
                """)
                row = cursor.fetchone()
                if row:
                    return {
                        "total": int(row[0]),
                        "active": int(row[1]),
                        "inactive": int(row[2])
                    }
        except:
            pass
        return {"total": 0, "active": 0, "inactive": 0}
    
    def get_uptime(self) -> Dict[str, Any]:
        """Получает время работы БД"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        ROUND((SYSDATE - startup_time) * 24 * 60, 0) as uptime_minutes
                    FROM v$instance
                """)
                row = cursor.fetchone()
                if row:
                    uptime_minutes = int(row[0])
                    days = uptime_minutes // (24 * 60)
                    hours = (uptime_minutes % (24 * 60)) // 60
                    minutes = uptime_minutes % 60
                    return {
                        "days": days,
                        "hours": hours,
                        "minutes": minutes,
                        "total_minutes": uptime_minutes
                    }
        except:
            pass
        return {"days": 0, "hours": 0, "minutes": 0, "total_minutes": 0}
    
    def get_tablespaces(self) -> List[Dict[str, Any]]:
        """Получает информацию о табличных пространствах"""
        tablespaces = []
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        tablespace_name,
                        ROUND(total_mb, 2) as total_mb,
                        ROUND(used_mb, 2) as used_mb,
                        ROUND(free_mb, 2) as free_mb,
                        ROUND(used_percent, 2) as used_percent
                    FROM (
                        SELECT 
                            a.tablespace_name,
                            a.bytes/1024/1024 as total_mb,
                            (a.bytes - NVL(b.bytes, 0))/1024/1024 as used_mb,
                            NVL(b.bytes, 0)/1024/1024 as free_mb,
                            ((a.bytes - NVL(b.bytes, 0))/a.bytes)*100 as used_percent
                        FROM (
                            SELECT tablespace_name, SUM(bytes) as bytes
                            FROM dba_data_files
                            GROUP BY tablespace_name
                        ) a,
                        (
                            SELECT tablespace_name, SUM(bytes) as bytes
                            FROM dba_free_space
                            GROUP BY tablespace_name
                        ) b
                        WHERE a.tablespace_name = b.tablespace_name(+)
                    )
                    ORDER BY used_percent DESC
                """)
                for row in cursor.fetchall():
                    tablespaces.append({
                        "name": row[0],
                        "total_mb": float(row[1]),
                        "used_mb": float(row[2]),
                        "free_mb": float(row[3]),
                        "used_percent": float(row[4])
                    })
        except:
            # Fallback для пользователей без DBA прав
            try:
                with self.connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT 
                            tablespace_name,
                            ROUND(SUM(bytes)/1024/1024, 2) as total_mb
                        FROM user_segments
                        GROUP BY tablespace_name
                        ORDER BY total_mb DESC
                    """)
                    for row in cursor.fetchall():
                        tablespaces.append({
                            "name": row[0],
                            "total_mb": float(row[1]),
                            "used_mb": float(row[1]),
                            "free_mb": 0,
                            "used_percent": 100
                        })
            except:
                pass
        
        return tablespaces
    
    def get_top_sql(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Получает топ SQL запросов"""
        top_sql = []
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(f"""
                    SELECT 
                        sql_id,
                        sql_text,
                        executions,
                        elapsed_time/1000000 as elapsed_seconds,
                        cpu_time/1000000 as cpu_seconds
                    FROM (
                        SELECT sql_id, sql_text, executions, elapsed_time, cpu_time
                        FROM v$sqlarea
                        WHERE executions > 0
                        ORDER BY elapsed_time DESC
                    )
                    WHERE ROWNUM <= {limit}
                """)
                for row in cursor.fetchall():
                    sql_text = row[1] if row[1] else ""
                    top_sql.append({
                        "sql_id": row[0],
                        "sql_text": sql_text[:100] + "..." if len(sql_text) > 100 else sql_text,
                        "executions": int(row[2]),
                        "elapsed_seconds": round(float(row[3]), 2) if row[3] else 0,
                        "cpu_seconds": round(float(row[4]), 2) if row[4] else 0
                    })
        except:
            pass
        
        return top_sql

