"""
Контроллер документации дашбордов.
Генерирует документацию по виджетам и DDL/DML скрипты для Oracle объектов.
"""
from typing import Dict, Any, List, Optional
import os
import json
from pathlib import Path


class DocumentationController:
    """Базовый контроллер документации дашбордов"""
    
    DASHBOARDS_DIR = Path(__file__).parent.parent / "dashboards"
    SQL_DIR = Path(__file__).parent.parent / "sql"
    
    @staticmethod
    def get_dashboard_config(dashboard_id: str) -> Optional[Dict[str, Any]]:
        """Загружает конфигурацию дашборда"""
        config_path = DocumentationController.DASHBOARDS_DIR / f"dashboard_{dashboard_id}.json"
        if not config_path.exists():
            return None
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None
    
    @staticmethod
    def get_dashboard_documentation(dashboard_id: str) -> Dict[str, Any]:
        """Генерирует документацию по всем виджетам дашборда"""
        config = DocumentationController.get_dashboard_config(dashboard_id)
        if not config:
            return {
                "success": False,
                "error": f"Dashboard {dashboard_id} not found",
                "data": None
            }
        
        widgets_docs = []
        for widget in config.get("widgets", []):
            widget_doc = {
                "widget_id": widget.get("widget_id"),
                "title": widget.get("title"),
                "description": widget.get("description", ""),
                "widget_type": widget.get("widget_type", "metric"),
                "metric_name": widget.get("metric_name"),
                "class_name": widget.get("class_name"),
                "method_name": widget.get("method_name"),
                "embed_url": widget.get("embed_url"),
                "position": widget.get("position"),
                "size": widget.get("size"),
            }
            
            # Дополнительная информация в зависимости от типа
            if widget.get("widget_type") == "embed":
                widget_doc["embed_info"] = {
                    "url": widget.get("embed_url"),
                    "type": "Встроенная HTML-страница"
                }
            elif widget.get("widget_type") == "custom_sql":
                widget_doc["sql_info"] = {
                    "type": "Пользовательский SQL-запрос"
                }
            else:
                widget_doc["metric_info"] = {
                    "class": widget.get("class_name"),
                    "method": widget.get("method_name"),
                    "type": "Метрика из контроллера"
                }
            
            widgets_docs.append(widget_doc)
        
        return {
            "success": True,
            "data": {
                "dashboard_id": dashboard_id,
                "dashboard_name": config.get("dashboard_name"),
                "dashboard_description": config.get("dashboard_description"),
                "widgets": widgets_docs,
                "metadata": config.get("metadata", {})
            }
        }
    
    @staticmethod
    def get_ddl_script(dashboard_id: str) -> Dict[str, Any]:
        """Генерирует DDL скрипт для всех Oracle объектов, используемых дашбордом"""
        config = DocumentationController.get_dashboard_config(dashboard_id)
        if not config:
            return {
                "success": False,
                "error": f"Dashboard {dashboard_id} not found",
                "script": ""
            }
        
        # Определяем какие SQL файлы нужны на основе виджетов
        sql_files = []
        widgets = config.get("widgets", [])
        
        # Проверяем типы виджетов
        has_bus = False
        has_cred = False
        
        for widget in widgets:
            metric_name = widget.get("metric_name", "")
            widget_type = widget.get("widget_type", "")
            embed_url = widget.get("embed_url", "")
            
            if metric_name == "departure_board" or "bus" in embed_url.lower():
                has_bus = True
            if "credit" in embed_url.lower() or "cred" in metric_name.lower():
                has_cred = True
        
        # Формируем список SQL файлов
        if has_bus:
            sql_files.extend([
                "01_bus_tables.sql",
                "02_bus_views.sql",
                "03_bus_triggers.sql",
                "04_bus_package.sql"
            ])
        
        if has_cred:
            sql_files.extend([
                "05_cred_tables.sql",
                "06_cred_views.sql",
                "07_cred_triggers.sql",
                "08_cred_admin_package.sql",
                "09_cred_operator_package.sql",
                "11_cred_program_products.sql",
                "12_cred_reports.sql",
            ])
        
        # Читаем SQL файлы
        ddl_content = []
        ddl_content.append(f"-- DDL скрипт для дашборда {config.get('dashboard_name', dashboard_id)}")
        ddl_content.append(f"-- Dashboard ID: {dashboard_id}")
        ddl_content.append(f"-- Сгенерировано автоматически")
        ddl_content.append("")
        
        for sql_file in sql_files:
            sql_path = DocumentationController.SQL_DIR / sql_file
            if sql_path.exists():
                ddl_content.append(f"-- ========================================")
                ddl_content.append(f"-- {sql_file}")
                ddl_content.append(f"-- ========================================")
                ddl_content.append("")
                try:
                    with open(sql_path, 'r', encoding='utf-8') as f:
                        ddl_content.append(f.read())
                    ddl_content.append("")
                except Exception as e:
                    ddl_content.append(f"-- Ошибка чтения {sql_file}: {str(e)}")
                    ddl_content.append("")
        
        if not sql_files:
            ddl_content.append("-- Этот дашборд не требует Oracle объектов")
            ddl_content.append("-- Все виджеты используют системные метрики или встроенные страницы")
        
        return {
            "success": True,
            "script": "\n".join(ddl_content),
            "files_included": sql_files
        }
    
    @staticmethod
    def get_dml_script(dashboard_id: str) -> Dict[str, Any]:
        """Генерирует DML скрипт с демо-данными для дашборда"""
        config = DocumentationController.get_dashboard_config(dashboard_id)
        if not config:
            return {
                "success": False,
                "error": f"Dashboard {dashboard_id} not found",
                "script": ""
            }
        
        # Определяем нужен ли demo_data.sql
        sql_files = []
        widgets = config.get("widgets", [])
        
        has_bus = False
        has_cred = False
        
        for widget in widgets:
            metric_name = widget.get("metric_name", "")
            embed_url = widget.get("embed_url", "")
            
            if metric_name == "departure_board" or "bus" in embed_url.lower():
                has_bus = True
            if "credit" in embed_url.lower() or "cred" in metric_name.lower():
                has_cred = True
        
        if has_bus or has_cred:
            sql_files.append("10_demo_data.sql")
        
        # Читаем demo_data.sql
        dml_content = []
        dml_content.append(f"-- DML скрипт (демо-данные) для дашборда {config.get('dashboard_name', dashboard_id)}")
        dml_content.append(f"-- Dashboard ID: {dashboard_id}")
        dml_content.append(f"-- Сгенерировано автоматически")
        dml_content.append("")
        dml_content.append("-- ВНИМАНИЕ: Этот скрипт содержит демонстрационные данные.")
        dml_content.append("-- Выполняйте только после успешного выполнения DDL скрипта.")
        dml_content.append("")
        
        for sql_file in sql_files:
            sql_path = DocumentationController.SQL_DIR / sql_file
            if sql_path.exists():
                dml_content.append(f"-- ========================================")
                dml_content.append(f"-- {sql_file}")
                dml_content.append(f"-- ========================================")
                dml_content.append("")
                try:
                    with open(sql_path, 'r', encoding='utf-8') as f:
                        dml_content.append(f.read())
                    dml_content.append("")
                except Exception as e:
                    dml_content.append(f"-- Ошибка чтения {sql_file}: {str(e)}")
                    dml_content.append("")
        
        if not sql_files:
            dml_content.append("-- Этот дашборд не требует демо-данных")
        
        return {
            "success": True,
            "script": "\n".join(dml_content),
            "files_included": sql_files
        }
    
    @staticmethod
    def get_all_dashboards_list() -> Dict[str, Any]:
        """Возвращает список всех доступных дашбордов"""
        dashboards = []
        for config_file in sorted(DocumentationController.DASHBOARDS_DIR.glob("dashboard_*.json")):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                dashboards.append({
                    "dashboard_id": config.get("dashboard_id"),
                    "dashboard_name": config.get("dashboard_name"),
                    "dashboard_description": config.get("dashboard_description")
                })
            except Exception:
                continue
        
        return {
            "success": True,
            "data": dashboards
        }
