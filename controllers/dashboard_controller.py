"""
Контроллер Dashboard
"""
from typing import Dict, Any, List
import sys
import os
import json
import glob

# Добавляем корневую директорию в путь
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from models.database import DatabaseModel


class DashboardController:
    """Класс для управления Dashboard"""
    
    @staticmethod
    def get_system_metrics() -> Dict[str, Any]:
        """Получает системные метрики сервера (не требует подключения к БД)"""
        try:
            import psutil
            import shutil
            
            # Память сервера
            memory = psutil.virtual_memory()
            memory_total_gb = memory.total / (1024 ** 3)
            memory_used_gb = memory.used / (1024 ** 3)
            memory_free_gb = memory.available / (1024 ** 3)
            memory_percent = memory.percent
            
            # Диск
            disk = shutil.disk_usage('/')
            disk_total_gb = disk.total / (1024 ** 3)
            disk_used_gb = disk.used / (1024 ** 3)
            disk_free_gb = disk.free / (1024 ** 3)
            disk_percent = (disk.used / disk.total * 100) if disk.total > 0 else 0
            
            return {
                "memory": {
                    "total_gb": round(memory_total_gb, 2),
                    "used_gb": round(memory_used_gb, 2),
                    "free_gb": round(memory_free_gb, 2),
                    "usage_percent": round(memory_percent, 2)
                },
                "disk": {
                    "total_gb": round(disk_total_gb, 2),
                    "used_gb": round(disk_used_gb, 2),
                    "free_gb": round(disk_free_gb, 2),
                    "usage_percent": round(disk_percent, 2)
                }
            }
        except ImportError:
            return {
                "memory": {
                    "total_gb": 0,
                    "used_gb": 0,
                    "free_gb": 0,
                    "usage_percent": 0
                },
                "disk": {
                    "total_gb": 0,
                    "used_gb": 0,
                    "free_gb": 0,
                    "usage_percent": 0
                },
                "error": "psutil not installed"
            }
        except Exception as e:
            return {
                "memory": {
                    "total_gb": 0,
                    "used_gb": 0,
                    "free_gb": 0,
                    "usage_percent": 0
                },
                "disk": {
                    "total_gb": 0,
                    "used_gb": 0,
                    "free_gb": 0,
                    "usage_percent": 0
                },
                "error": str(e)
            }
    
    @staticmethod
    def get_metric(metric_name: str) -> Dict[str, Any]:
        """Получает конкретную метрику"""
        # Системные метрики не требуют подключения к БД
        if metric_name == 'system':
            try:
                result = DashboardController.get_system_metrics()
                return {
                    "success": True,
                    "metric": metric_name,
                    "data": result,
                    "timestamp": __import__('datetime').datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e)
                }
        
        if metric_name == 'weather':
            # Погодный виджет (не требует подключения к БД)
            try:
                result = DashboardController.get_weather_info()
                return {
                    "success": True,
                    "metric": metric_name,
                    "data": result,
                    "timestamp": __import__('datetime').datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e)
                }
        
        if metric_name == 'departure_board':
            try:
                result = DashboardController.get_departure_board()
                return {
                    "success": True,
                    "metric": metric_name,
                    "data": result,
                    "timestamp": __import__('datetime').datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e)
                }
        
        # Остальные метрики требуют подключения к БД
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
                elif metric_name.startswith('custom_sql'):
                    # Для custom_sql виджетов нужны дополнительные параметры из конфига
                    # Это обрабатывается через отдельный endpoint
                    return {
                        "success": False,
                        "error": "Custom SQL widgets require widget configuration"
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
                    "top_sql": db.get_top_sql(5),
                    "system": DashboardController.get_system_metrics()
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
    
    @staticmethod
    def get_dashboards_list(project_slug: str = None) -> Dict[str, Any]:
        """Получает список доступных dashboard JSON файлов.
        Если задан project_slug — только дашборды, привязанные к проекту (из UNA_SHELL_PROJECTS.DASHBOARD_IDS)."""
        try:
            dashboards_dir = os.path.join(root_dir, 'dashboards')
            if not os.path.exists(dashboards_dir):
                return {
                    "success": False,
                    "error": "Dashboards directory not found",
                    "dashboards": []
                }
            
            allowed_ids = None
            if project_slug:
                try:
                    from models.shell_project import ShellProject
                    project = ShellProject.get_by_slug(project_slug)
                    if project and project.dashboard_id_list:
                        allowed_ids = set(project.dashboard_id_list)
                    elif project:
                        allowed_ids = set()
                except Exception:
                    allowed_ids = set()
            
            dashboard_files = glob.glob(os.path.join(dashboards_dir, 'dashboard_*.json'))
            dashboards_list = []
            
            for file_path in sorted(dashboard_files):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        dashboard_config = json.load(f)
                    
                    dashboard_id = dashboard_config.get('dashboard_id', '')
                    if allowed_ids is not None and dashboard_id not in allowed_ids:
                        continue
                    dashboard_name = dashboard_config.get('dashboard_name', 'Unknown')
                    dashboard_description = dashboard_config.get('dashboard_description', '')
                    
                    dashboards_list.append({
                        "dashboard_id": dashboard_id,
                        "dashboard_name": dashboard_name,
                        "dashboard_description": dashboard_description,
                        "widget_count": len(dashboard_config.get('widgets', []))
                    })
                except Exception as e:
                    continue
            
            return {
                "success": True,
                "dashboards": dashboards_list,
                "count": len(dashboards_list)
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "dashboards": [],
                "count": 0
            }
    
    @staticmethod
    def get_dashboard_config(dashboard_id: str) -> Dict[str, Any]:
        """Получает конфигурацию dashboard'а по ID"""
        try:
            dashboards_dir = os.path.join(root_dir, 'dashboards')
            dashboard_file = os.path.join(dashboards_dir, f'dashboard_{dashboard_id}.json')
            
            if not os.path.exists(dashboard_file):
                return {
                    "success": False,
                    "error": f"Dashboard {dashboard_id} not found"
                }
            
            with open(dashboard_file, 'r', encoding='utf-8') as f:
                dashboard_config = json.load(f)
            
            return {
                "success": True,
                "config": dashboard_config
            }
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"Invalid JSON in dashboard file: {str(e)}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    def execute_custom_sql(database_type: str, sql_query: str, connection_params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Выполняет произвольный SQL запрос к базе данных"""
        if not sql_query or not sql_query.strip():
            return {
                "success": False,
                "error": "SQL query is empty",
                "data": [],
                "columns": [],
                "rowcount": 0
            }
        
        connection_params = connection_params or {}
        
        try:
            if database_type.lower() == 'oracle':
                # Используем существующее подключение Oracle
                with DatabaseModel() as db:
                    return db.execute_query(sql_query)
            
            elif database_type.lower() == 'mysql':
                # Поддержка MySQL (требует pymysql)
                try:
                    import pymysql
                except ImportError:
                    return {
                        "success": False,
                        "error": "MySQL support requires pymysql package. Install: pip install pymysql",
                        "data": [],
                        "columns": [],
                        "rowcount": 0
                    }
                
                # Параметры подключения из connection_params
                host = connection_params.get('host', 'localhost')
                port = connection_params.get('port', 3306)
                user = connection_params.get('user', 'root')
                password = connection_params.get('password', '')
                database = connection_params.get('database', '')
                
                connection = pymysql.connect(
                    host=host,
                    port=port,
                    user=user,
                    password=password,
                    database=database,
                    cursorclass=pymysql.cursors.DictCursor
                )
                
                try:
                    with connection.cursor() as cursor:
                        cursor.execute(sql_query)
                        
                        result = {
                            "success": True,
                            "data": [],
                            "columns": [],
                            "rowcount": 0,
                            "message": ""
                        }
                        
                        if cursor.description:
                            result["columns"] = [desc[0] for desc in cursor.description]
                            rows = cursor.fetchall()
                            result["data"] = [list(row.values()) if isinstance(row, dict) else list(row) for row in rows]
                            result["rowcount"] = len(rows)
                        else:
                            result["message"] = "Query executed successfully"
                            result["rowcount"] = cursor.rowcount
                        
                        return result
                finally:
                    connection.close()
            
            else:
                return {
                    "success": False,
                    "error": f"Unsupported database type: {database_type}. Supported: oracle, mysql",
                    "data": [],
                    "columns": [],
                    "rowcount": 0
                }
                
        except Exception as e:
            import traceback
            return {
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc(),
                "data": [],
                "columns": [],
                "rowcount": 0
            }
    
    @staticmethod
    def get_weather_info() -> Dict[str, Any]:
        """Получает информацию о погоде: время, температура, состояние погоды"""
        from datetime import datetime
        
        try:
            # Получаем текущее время
            now = datetime.now()
            current_time = now.strftime("%H:%M:%S")
            current_date = now.strftime("%Y-%m-%d")
            
            # День недели на русском
            days_ru = {
                'Monday': 'Понедельник',
                'Tuesday': 'Вторник',
                'Wednesday': 'Среда',
                'Thursday': 'Четверг',
                'Friday': 'Пятница',
                'Saturday': 'Суббота',
                'Sunday': 'Воскресенье'
            }
            current_day = days_ru.get(now.strftime("%A"), now.strftime("%A"))
            
            # Получаем погоду (можно использовать OpenWeatherMap API или другой источник)
            # Для демо используем простой вариант - можно заменить на реальный API
            weather_data = DashboardController._fetch_weather()
            
            return {
                "success": True,
                "time": current_time,
                "date": current_date,
                "day": current_day,
                "temperature": weather_data.get("temperature", 0),
                "temperature_unit": "°C",
                "condition": weather_data.get("condition", "Неизвестно"),
                "condition_icon": weather_data.get("icon", "🌤️"),
                "location": weather_data.get("location", "Не указано"),
                "timestamp": now.strftime("%Y-%m-%d %H:%M:%S")
            }
        except Exception as e:
            import traceback
            return {
                "success": False,
                "error": str(e),
                "time": datetime.now().strftime("%H:%M:%S"),
                "date": datetime.now().strftime("%Y-%m-%d"),
                "temperature": 0,
                "temperature_unit": "°C",
                "condition": "Ошибка получения данных",
                "condition_icon": "❌"
            }
    
    @staticmethod
    def get_departure_board() -> Dict[str, Any]:
        """Табло отправлений автовокзала: данные из V_BUS_DEPARTURES_TODAY или mock при ошибке."""
        from datetime import datetime, timedelta
        
        now = datetime.now()
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    "SELECT ROUTE, DESTINATION, DEPARTURE_TIME, PLATFORM, GATE, STATUS FROM V_BUS_DEPARTURES_TODAY"
                )
            if not r.get("success") or not r.get("data"):
                raise ValueError(r.get("message", "No data"))
            cols = [c.upper() for c in (r.get("columns") or [])]
            departures = []
            for row in r["data"]:
                d = dict(zip(cols, row))
                departures.append({
                    "route": d.get("ROUTE") or "",
                    "destination": d.get("DESTINATION") or "",
                    "departure": d.get("DEPARTURE_TIME") or "",
                    "platform": d.get("PLATFORM") or "",
                    "gate": d.get("GATE") or "-",
                    "status": d.get("STATUS") or "Ожидание",
                })
            return {
                "title": "Табло отправлений",
                "current_time": now.strftime("%H:%M:%S"),
                "departures": departures,
            }
        except Exception:
            # fallback: mock
            departures = [
                {"route": "101", "destination": "Кишинэу", "departure": (now + timedelta(minutes=12)).strftime("%H:%M"), "platform": "3", "status": "Посадка", "gate": "A"},
                {"route": "205", "destination": "Бэлць", "departure": (now + timedelta(minutes=25)).strftime("%H:%M"), "platform": "1", "status": "Ожидание", "gate": "B"},
                {"route": "302", "destination": "Унгень", "departure": (now + timedelta(minutes=38)).strftime("%H:%M"), "platform": "2", "status": "Ожидание", "gate": "A"},
                {"route": "418", "destination": "Орхей", "departure": (now + timedelta(minutes=55)).strftime("%H:%M"), "platform": "4", "status": "Ожидание", "gate": "C"},
                {"route": "501", "destination": "Кагул", "departure": (now + timedelta(minutes=78)).strftime("%H:%M"), "platform": "1", "status": "Ожидание", "gate": "B"},
                {"route": "112", "destination": "Сорока", "departure": (now + timedelta(minutes=95)).strftime("%H:%M"), "platform": "2", "status": "Ожидание", "gate": "A"},
                {"route": "207", "destination": "Бендеры", "departure": (now + timedelta(minutes=120)).strftime("%H:%M"), "platform": "3", "status": "Ожидание", "gate": "C"},
            ]
            return {"title": "Табло отправлений", "current_time": now.strftime("%H:%M:%S"), "departures": departures}
    
    @staticmethod
    def _get_server_location() -> str:
        """Определяет город/регион, где запущен сервер"""
        # Сначала проверяем переменную окружения
        city = os.environ.get('WEATHER_CITY')
        if city:
            return city
        
        # Пытаемся определить по IP адресу сервера
        try:
            import urllib.request
            import json as json_lib
            
            # Используем бесплатный API для определения локации по IP
            try:
                with urllib.request.urlopen('http://ip-api.com/json/?fields=city,country', timeout=3) as response:
                    data = json_lib.loads(response.read().decode())
                    if data.get('city'):
                        return data['city']
            except:
                pass
            
            # Альтернативный способ - через ipinfo.io
            try:
                with urllib.request.urlopen('https://ipinfo.io/json', timeout=3) as response:
                    data = json_lib.loads(response.read().decode())
                    if data.get('city'):
                        return data['city']
            except:
                pass
        except:
            pass
        
        # Если не удалось определить, используем значение по умолчанию на основе часового пояса
        try:
            import time
            import datetime
            tz_name = time.tzname[0] if time.tzname else 'UTC'
            # Простая эвристика по часовому поясу
            if 'MSK' in tz_name or 'Europe/Moscow' in str(time.tzname):
                return 'Moscow'
            elif 'Europe' in str(time.tzname):
                return 'Frankfurt'  # По умолчанию для Европы
            elif 'America' in str(time.tzname):
                return 'New York'
            elif 'Asia' in str(time.tzname):
                return 'Tokyo'
        except:
            pass
        
        # Последний fallback
        return 'Moscow'
    
    @staticmethod
    def _fetch_weather() -> Dict[str, Any]:
        """Получает данные о погоде из внешнего API или возвращает демо-данные"""
        try:
            # Определяем город автоматически по локации сервера
            city = DashboardController._get_server_location()
            
            # Попытка получить погоду из OpenWeatherMap API (если настроен API ключ)
            api_key = os.environ.get('OPENWEATHER_API_KEY')
            
            # Сначала пытаемся получить реальную погоду через бесплатный API wttr.in
            try:
                import urllib.request
                import ssl
                import re
                
                # Используем wttr.in - бесплатный погодный API без ключа
                # Делаем два отдельных запроса для надежности
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
                
                # Создаем SSL контекст, который не проверяет сертификаты (для локального использования)
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                
                # Получаем температуру
                temp_url = f"https://wttr.in/{city}?format=%t"
                temp_req = urllib.request.Request(temp_url, headers=headers)
                with urllib.request.urlopen(temp_req, timeout=5, context=ssl_context) as response:
                    temp_text = response.read().decode('utf-8').strip()
                    # Парсим температуру (формат: +7°C или -5°C)
                    temp_match = re.search(r'([+-]?\d+)', temp_text)
                    if temp_match:
                        temp_c = int(temp_match.group(1))
                    else:
                        raise ValueError("Не удалось распарсить температуру")
                
                # Получаем состояние погоды
                condition_url = f"https://wttr.in/{city}?format=%C"
                condition_req = urllib.request.Request(condition_url, headers=headers)
                with urllib.request.urlopen(condition_req, timeout=5, context=ssl_context) as response:
                    condition_str = response.read().decode('utf-8').strip().lower()
                
                # Определяем состояние погоды по тексту
                # Проверяем более специфичные условия первыми
                condition_str_lower = condition_str.lower()
                
                if 'thunder' in condition_str_lower or 'storm' in condition_str_lower:
                    condition = 'Гроза'
                    icon = '⛈️'
                elif 'snow' in condition_str_lower:
                    condition = 'Снег'
                    icon = '❄️'
                elif 'rain' in condition_str_lower or 'shower' in condition_str_lower:
                    condition = 'Дождь'
                    icon = '🌧️'
                elif 'drizzle' in condition_str_lower:
                    # Если есть drizzle с туманом - показываем как облачно
                    if 'mist' in condition_str_lower or 'fog' in condition_str_lower:
                        condition = 'Облачно'
                        icon = '☁️'
                    else:
                        condition = 'Моросящий дождь'
                        icon = '🌦️'
                elif 'fog' in condition_str_lower or 'mist' in condition_str_lower:
                    condition = 'Туман'
                    icon = '🌫️'
                elif 'sun' in condition_str_lower or 'clear' in condition_str_lower or 'sunny' in condition_str_lower:
                    condition = 'Солнечно'
                    icon = '☀️'
                elif 'cloud' in condition_str_lower or 'overcast' in condition_str_lower or 'partly' in condition_str_lower:
                    condition = 'Облачно'
                    icon = '☁️'
                else:
                    # Если не удалось определить, используем общее состояние
                    condition = 'Облачно'
                    icon = '☁️'
                
                return {
                    "temperature": temp_c,
                    "condition": condition,
                    "icon": icon,
                    "location": city
                }
            except Exception as e:
                # Если wttr.in недоступен, пробуем другой метод
                pass
            
            # Попытка получить погоду из OpenWeatherMap API (если настроен API ключ)
            api_key = os.environ.get('OPENWEATHER_API_KEY')
            if api_key:
                try:
                    import urllib.request
                    import json as json_lib
                    
                    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric&lang=ru"
                    
                    with urllib.request.urlopen(url, timeout=5) as response:
                        data = json_lib.loads(response.read().decode())
                        
                        temp = round(data['main']['temp'])
                        condition_code = data['weather'][0]['main']
                        
                        # Преобразуем код погоды в читаемый формат
                        condition_map = {
                            'Clear': 'Солнечно',
                            'Clouds': 'Облачно',
                            'Rain': 'Дождь',
                            'Drizzle': 'Моросящий дождь',
                            'Thunderstorm': 'Гроза',
                            'Snow': 'Снег',
                            'Mist': 'Туман',
                            'Fog': 'Туман'
                        }
                        
                        condition = condition_map.get(condition_code, condition_code)
                        
                        # Выбираем иконку
                        icon_map = {
                            'Clear': '☀️',
                            'Clouds': '☁️',
                            'Rain': '🌧️',
                            'Drizzle': '🌦️',
                            'Thunderstorm': '⛈️',
                            'Snow': '❄️',
                            'Mist': '🌫️',
                            'Fog': '🌫️'
                        }
                        
                        icon = icon_map.get(condition_code, '🌤️')
                        
                        return {
                            "temperature": temp,
                            "condition": condition,
                            "icon": icon,
                            "location": city
                        }
                except Exception as e:
                    pass
            
            # Если все API недоступны, возвращаем базовые демо-данные
            return {
                "temperature": 20,
                "condition": "Данные недоступны",
                "icon": "🌤️",
                "location": city
            }
            
        except Exception as e:
            # В случае любой ошибки возвращаем демо-данные
            return {
                "temperature": 20,
                "condition": "Солнечно",
                "icon": "☀️",
                "location": "Неизвестно"
            }

