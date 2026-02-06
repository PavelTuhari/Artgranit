"""
Модель для работы с базой данных Oracle.

Wallet: только .env. WALLET_DIR — путь к распакованной папке wallet (вне проекта).
Обновления кода не меняют логику подключения.
"""
import oracledb
import os
from typing import Optional, Dict, List, Any
from datetime import datetime
from config import Config


class DatabaseConnection:
    """Класс для управления подключениями к Oracle Database"""
    
    _pool: Optional[oracledb.ConnectionPool] = None
    _wallet_ok: bool = False
    
    @classmethod
    def _wallet_ready(cls) -> bool:
        """Проверка: WALLET_DIR существует (wallet вне проекта, задаётся в .env)."""
        if not (Config.WALLET_DIR and Config.WALLET_DIR.strip()):
            return False
        p = Config.WALLET_DIR.strip()
        if cls._wallet_ok and os.path.isdir(p):
            return True
        if os.path.isdir(p):
            cls._wallet_ok = True
            return True
        return False
    
    @classmethod
    def get_connection(cls) -> oracledb.Connection:
        """Получает подключение к базе данных"""
        if not cls._wallet_ready():
            raise Exception(
                "Wallet не найден. Задайте WALLET_DIR в .env (путь к папке wallet вне проекта)."
            )
        
        wallet_path = os.path.abspath(Config.WALLET_DIR.strip())
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
        
        if not cls._wallet_ready():
            raise Exception(
                "Wallet не найден. Задайте WALLET_DIR в .env (путь к папке wallet вне проекта)."
            )
        
        wallet_path = os.path.abspath(Config.WALLET_DIR.strip())
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
    
    def execute_query(self, sql: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Выполняет SQL запрос с опциональными параметрами"""
        result = {
            "success": False,
            "data": [],
            "columns": [],
            "rowcount": 0,
            "message": ""
        }
        
        try:
            with self.connection.cursor() as cursor:
                if params:
                    cursor.execute(sql, params)
                else:
                    cursor.execute(sql)
                
                if cursor.description:
                    result["columns"] = [desc[0] for desc in cursor.description]
                    # Не сохраняем типы колонок - они не нужны и не сериализуются в JSON
                
                rows = cursor.fetchall()
                # Обрабатываем CLOB и другие LOB типы
                processed_rows = []
                for row in rows:
                    processed_row = []
                    for idx, cell in enumerate(row):
                        # Проверяем, является ли значение CLOB или другим LOB объектом
                        if hasattr(cell, 'read'):
                            # Это LOB объект (CLOB, BLOB и т.д.)
                            try:
                                # В oracledb CLOB обычно автоматически преобразуется в строку при fetchall()
                                # Но если это LOB объект, читаем его содержимое
                                cell_value = cell.read()
                                
                                # Если это bytes (BLOB), декодируем
                                if isinstance(cell_value, bytes):
                                    try:
                                        cell_value = cell_value.decode('utf-8')
                                    except:
                                        import base64
                                        cell_value = base64.b64encode(cell_value).decode('utf-8')
                                
                                # Преобразуем в строку, если это не строка
                                if cell_value is None:
                                    cell_value = ''
                                elif not isinstance(cell_value, str):
                                    cell_value = str(cell_value)
                                
                                processed_row.append(cell_value)
                            except Exception as e:
                                # Если не удалось прочитать, пробуем преобразовать в строку
                                try:
                                    processed_row.append(str(cell))
                                except:
                                    processed_row.append(f"[CLOB read error: {str(e)}]")
                        else:
                            processed_row.append(cell)
                    processed_rows.append(processed_row)
                
                result["data"] = processed_rows
                result["rowcount"] = len(processed_rows)
                result["success"] = True
                result["message"] = f"QUERY_SUCCESS_ROWS:{len(processed_rows)}"
        except Exception as e:
            result["message"] = str(e)
            import traceback
            result["traceback"] = traceback.format_exc()
        
        return result
    
    def split_sql_commands(self, sql: str) -> list:
        """Разделяет SQL скрипт на отдельные команды по точке с запятой"""
        commands = []
        current_command = ""
        in_string = False
        string_char = None
        in_comment = False
        comment_type = None  # 'single' или 'multi'
        i = 0
        
        while i < len(sql):
            char = sql[i]
            next_char = sql[i + 1] if i + 1 < len(sql) else None
            
            # Обработка строк
            if not in_comment:
                if char in ("'", '"'):
                    # В Oracle строки могут содержать двойные кавычки для экранирования ('It''s test')
                    if not in_string:
                        in_string = True
                        string_char = char
                        current_command += char
                    elif char == string_char:
                        # Проверяем, не двойная ли это кавычка внутри строки
                        if i + 1 < len(sql) and sql[i + 1] == string_char:
                            # Двойная кавычка - экранирование
                            current_command += char + char
                            i += 2
                            continue
                        else:
                            # Закрытие строки
                            in_string = False
                            string_char = None
                            current_command += char
                    else:
                        current_command += char
                    i += 1
                    continue
            
            # Обработка комментариев
            if not in_string:
                if char == '-' and next_char == '-' and not in_comment:
                    in_comment = True
                    comment_type = 'single'
                    current_command += char
                    i += 1
                    continue
                elif char == '/' and next_char == '*' and not in_comment:
                    in_comment = True
                    comment_type = 'multi'
                    current_command += char
                    i += 1
                    continue
                elif in_comment and comment_type == 'single' and char == '\n':
                    in_comment = False
                    comment_type = None
                    current_command += char
                    i += 1
                    continue
                elif in_comment and comment_type == 'multi' and char == '*' and next_char == '/':
                    in_comment = False
                    comment_type = None
                    current_command += char
                    if next_char:
                        current_command += next_char
                    i += 2
                    continue
            
            # Если мы в комментарии или строке, просто добавляем символ
            if in_comment or in_string:
                current_command += char
                i += 1
                continue
            
            # Обработка точки с запятой (разделитель команд)
            if char == ';':
                current_command = current_command.strip()
                if current_command:
                    commands.append(current_command)
                current_command = ""
                i += 1
                continue
            
            current_command += char
            i += 1
        
        # Добавляем последнюю команду, если она есть
        current_command = current_command.strip()
        if current_command:
            commands.append(current_command)
        
        return commands
    
    def execute_script(self, sql_script: str) -> Dict[str, Any]:
        """Выполняет SQL скрипт (несколько команд)"""
        result = {
            "success": False,
            "message": "",
            "script_results": [],
            "total_commands": 0,
            "success_count": 0,
            "error_count": 0,
            "data": [],
            "columns": [],
            "rowcount": 0
        }
        
        # Разделяем скрипт на команды
        commands = self.split_sql_commands(sql_script)
        
        if not commands:
            result["message"] = "SQL скрипт не содержит команд"
            return result
        
        result["total_commands"] = len(commands)
        
        try:
            with self.connection.cursor() as cursor:
                last_select_result = None
                
                for idx, command in enumerate(commands, 1):
                    command = command.strip()
                    if not command:
                        continue
                    
                    command_result = {
                        "command_num": idx,
                        "command": command[:100] + "..." if len(command) > 100 else command,
                        "full_command": command,
                        "success": False,
                        "message": "",
                        "type": "UNKNOWN",
                        "rowcount": 0
                    }
                    
                    # Определяем тип команды
                    command_upper = command.upper().strip()
                    if command_upper.startswith('SELECT'):
                        command_result["type"] = "SELECT"
                    elif command_upper.startswith('INSERT'):
                        command_result["type"] = "INSERT"
                    elif command_upper.startswith('UPDATE'):
                        command_result["type"] = "UPDATE"
                    elif command_upper.startswith('DELETE'):
                        command_result["type"] = "DELETE"
                    elif command_upper.startswith('CREATE'):
                        command_result["type"] = "CREATE"
                    elif command_upper.startswith('ALTER'):
                        command_result["type"] = "ALTER"
                    elif command_upper.startswith('DROP'):
                        command_result["type"] = "DROP"
                    elif command_upper.startswith('COMMENT'):
                        command_result["type"] = "COMMENT"
                    else:
                        command_result["type"] = "OTHER"
                    
                    try:
                        # Выполняем команду
                        cursor.execute(command)
                        
                        # Если это SELECT, получаем данные
                        if cursor.description:
                            rows = cursor.fetchall()
                            command_result["rowcount"] = len(rows)
                            # Сохраняем данные SELECT для каждой команды
                            command_result["columns"] = [desc[0] for desc in cursor.description]
                            # Не сохраняем типы колонок - они не нужны и не сериализуются в JSON
                            
                            # Обрабатываем CLOB и другие LOB типы
                            processed_rows = []
                            for row in rows:
                                processed_row = []
                                for cell in row:
                                    # Проверяем, является ли значение CLOB или другим LOB объектом
                                    if hasattr(cell, 'read'):
                                        # Это LOB объект (CLOB, BLOB и т.д.)
                                        try:
                                            # В oracledb CLOB обычно автоматически преобразуется в строку при fetchall()
                                            # Но если это LOB объект, читаем его содержимое
                                            cell_value = cell.read()
                                            
                                            # Если это bytes (BLOB), декодируем
                                            if isinstance(cell_value, bytes):
                                                try:
                                                    cell_value = cell_value.decode('utf-8')
                                                except:
                                                    import base64
                                                    cell_value = base64.b64encode(cell_value).decode('utf-8')
                                            
                                            # Преобразуем в строку, если это не строка
                                            if cell_value is None:
                                                cell_value = ''
                                            elif not isinstance(cell_value, str):
                                                cell_value = str(cell_value)
                                            
                                            processed_row.append(cell_value)
                                        except Exception as e:
                                            # Если не удалось прочитать, пробуем преобразовать в строку
                                            try:
                                                processed_row.append(str(cell))
                                            except:
                                                processed_row.append(f"[CLOB read error: {str(e)}]")
                                    else:
                                        processed_row.append(cell)
                                processed_rows.append(processed_row)
                            
                            command_result["data"] = processed_rows
                            last_select_result = {
                                "columns": command_result["columns"],
                                "data": command_result["data"],
                                "rowcount": len(processed_rows)
                            }
                        else:
                            # Для DDL/DML команд
                            command_result["rowcount"] = cursor.rowcount if cursor.rowcount else 0
                        
                        # Коммитим транзакцию для каждой команды
                        self.connection.commit()
                        
                        command_result["success"] = True
                        if command_result["rowcount"] > 0:
                            # Используем ключ для перевода на клиенте
                            command_result["message"] = f"COMMAND_SUCCESS_ROWS:{command_result['rowcount']}"
                        else:
                            command_result["message"] = "COMMAND_SUCCESS"
                        
                        result["success_count"] += 1
                        
                    except Exception as e:
                        command_result["success"] = False
                        command_result["message"] = str(e)
                        result["error_count"] += 1
                    
                    result["script_results"].append(command_result)
                
                # Если была последняя SELECT команда, добавляем её данные в результат
                if last_select_result:
                    result["data"] = last_select_result["data"]
                    result["columns"] = last_select_result["columns"]
                    result["rowcount"] = last_select_result["rowcount"]
                
                # Общий результат - используем ключи для перевода на клиенте
                if result["error_count"] == 0:
                    result["success"] = True
                    result["message"] = f"ALL_COMMANDS_SUCCESS:{result['success_count']}:{result['total_commands']}"
                else:
                    result["success"] = result["error_count"] < result["total_commands"]
                    result["message"] = f"COMMANDS_PARTIAL:{result['success_count']}:{result['total_commands']}:{result['error_count']}"
                
        except Exception as e:
            result["message"] = f"SCRIPT_ERROR:{str(e)}"
            import traceback
            result["traceback"] = traceback.format_exc()
        
        return result
    
    def fetch_refcursor(self, plsql: str, bind_in: Dict[str, Any], out_key: str = "cur") -> List[Dict[str, Any]]:
        """Выполняет PL/SQL блок, в котором в :out_key присваивается SYS_REFCURSOR. Возвращает строки как list of dict."""
        with self.connection.cursor() as cursor:
            out = cursor.var(oracledb.DB_TYPE_CURSOR)
            binds = dict(bind_in)
            binds[out_key] = out
            cursor.execute(plsql, binds)
            rc = out.getvalue()
            if not rc:
                return []
            if not rc.description:
                return []
            columns = [d[0] for d in rc.description]
            rows = rc.fetchall()
            if not rows:
                return []
            result = [dict(zip(columns, row)) for row in rows]
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
        """Получает метрики памяти (SGA) с несколькими вариантами запросов"""
        try:
            with self.connection.cursor() as cursor:
                # Вариант 1: v$sga (самый быстрый)
                try:
                    cursor.execute("""
                        SELECT 
                            ROUND(SUM(CASE WHEN name = 'Total SGA' THEN value ELSE 0 END)/1024/1024/1024, 2) as total_gb,
                            ROUND(SUM(CASE WHEN name = 'Free SGA Memory Available' THEN value ELSE 0 END)/1024/1024/1024, 2) as free_gb
                        FROM v$sga
                    """)
                    row = cursor.fetchone()
                    if row and row[0] and row[0] > 0:
                        total = float(row[0])
                        free = float(row[1]) if row[1] else 0
                        used = total - free
                        return {
                            "total_gb": total,
                            "used_gb": used,
                            "free_gb": free,
                            "usage_percent": round((used / total * 100) if total > 0 else 0, 2)
                        }
                except:
                    pass
                
                # Вариант 2: v$sgainfo
                try:
                    cursor.execute("""
                        SELECT 
                            ROUND(SUM(CASE WHEN name = 'Total SGA' THEN bytes ELSE 0 END)/1024/1024/1024, 2) as total_gb,
                            ROUND(SUM(CASE WHEN name = 'Free SGA Memory Available' THEN bytes ELSE 0 END)/1024/1024/1024, 2) as free_gb
                        FROM v$sgainfo
                    """)
                    row = cursor.fetchone()
                    if row and row[0] and row[0] > 0:
                        total = float(row[0])
                        free = float(row[1]) if row[1] else 0
                        used = total - free
                        return {
                            "total_gb": total,
                            "used_gb": used,
                            "free_gb": free,
                            "usage_percent": round((used / total * 100) if total > 0 else 0, 2)
                        }
                except:
                    pass
                
                # Вариант 3: v$sgastat (приблизительная оценка)
                try:
                    cursor.execute("""
                        SELECT ROUND(SUM(bytes)/1024/1024/1024, 2) as total_gb
                        FROM v$sgastat
                    """)
                    row = cursor.fetchone()
                    if row and row[0] and row[0] > 0:
                        total = float(row[0])
                        # Приблизительно: 80% используется (для fallback)
                        used = total * 0.8
                        free = total * 0.2
                        return {
                            "total_gb": total,
                            "used_gb": round(used, 2),
                            "free_gb": round(free, 2),
                            "usage_percent": 80.0
                        }
                except:
                    pass
        except Exception as e:
            print(f"Error getting memory metrics: {e}")
        return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "usage_percent": 0}
    
    def get_cpu_metrics(self) -> Dict[str, Any]:
        """Получает метрики CPU с несколькими вариантами запросов"""
        try:
            with self.connection.cursor() as cursor:
                # Вариант 1: v$sysmetric (самый точный)
                try:
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
                    if row and row[0]:
                        return {"usage_percent": float(row[0])}
                except:
                    pass
                
                # Вариант 2: v$sysmetric_summary
                try:
                    cursor.execute("""
                        SELECT 
                            ROUND(AVG(VALUE)/100, 2) as cpu_usage_percent
                        FROM v$sysmetric_summary
                        WHERE metric_name = 'CPU Usage Per Sec'
                        AND group_id = 2
                    """)
                    row = cursor.fetchone()
                    if row and row[0]:
                        return {"usage_percent": float(row[0])}
                except:
                    pass
                
                # Вариант 3: v$osstat (если доступно)
                try:
                    cursor.execute("""
                        SELECT 
                            ROUND((busy_time / (busy_time + idle_time)) * 100, 2) as cpu_usage_percent
                        FROM (
                            SELECT 
                                SUM(CASE WHEN stat_name = 'BUSY_TIME' THEN value ELSE 0 END) as busy_time,
                                SUM(CASE WHEN stat_name = 'IDLE_TIME' THEN value ELSE 0 END) as idle_time
                            FROM v$osstat
                            WHERE stat_name IN ('BUSY_TIME', 'IDLE_TIME')
                        )
                    """)
                    row = cursor.fetchone()
                    if row and row[0]:
                        return {"usage_percent": float(row[0])}
                except:
                    pass
                
                # Вариант 4: Используем системные метрики через psutil (fallback)
                try:
                    import psutil
                    cpu_percent = psutil.cpu_percent(interval=1)
                    return {"usage_percent": round(cpu_percent, 2)}
                except:
                    pass
        except Exception as e:
            print(f"Error getting CPU metrics: {e}")
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
        """Получает топ SQL запросов (оптимизированная версия без полного sql_text)"""
        top_sql = []
        try:
            with self.connection.cursor() as cursor:
                # Оптимизированный запрос: НЕ берем полный sql_text для ускорения
                # Используем подзапрос с ROWNUM для правильной сортировки
                # sql_text исключен из запроса для ускорения - берем только первые 100 символов через SUBSTR
                cursor.execute(f"""
                    SELECT 
                        sql_id,
                        SUBSTR(sql_text, 1, 100) as sql_text,
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
                    # SQL уже обрезан через SUBSTR, но добавляем "..." для ясности
                    if sql_text and len(sql_text) >= 100:
                        sql_text = sql_text.rstrip() + "..."
                    top_sql.append({
                        "sql_id": row[0],
                        "sql_text": sql_text,
                        "executions": int(row[2]),
                        "elapsed_seconds": round(float(row[3]), 2) if row[3] else 0,
                        "cpu_seconds": round(float(row[4]), 2) if row[4] else 0
                    })
        except Exception as e:
            # В случае ошибки возвращаем пустой список
            print(f"Error getting top SQL: {e}")
            pass
        
        return top_sql

