"""
Контроллер для работы с объектами базы данных
"""
from typing import Dict, Any
import sys
import os

# Добавляем корневую директорию в путь
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from models.database import DatabaseModel


class ObjectsController:
    """Класс для управления объектами базы данных"""
    
    @staticmethod
    def get_schemas() -> Dict[str, Any]:
        """Получает список доступных схем"""
        try:
            with DatabaseModel() as db:
                with db.connection.cursor() as cursor:
                    # Сначала получаем текущего пользователя
                    cursor.execute("SELECT USER FROM DUAL")
                    current_user = cursor.fetchone()[0]
                    
                    schemas = [{"name": current_user, "display_name": current_user}]
                    
                    # Пробуем получить схемы из all_tables (более надежный способ)
                    try:
                        cursor.execute("""
                            SELECT DISTINCT owner
                            FROM all_tables
                            WHERE owner NOT IN ('SYS', 'SYSTEM', 'XS$NULL', 'LBACSYS', 'OUTLN', 
                                                'GSMADMIN_INTERNAL', 'DIP', 'ORACLE_OCM', 'DBSNMP', 
                                                'DBSFWUSER', 'APPQOSSYS')
                            AND owner = UPPER(owner)
                            ORDER BY owner
                        """)
                        
                        for row in cursor.fetchall():
                            schema_name = row[0]
                            # Добавляем только если еще нет в списке
                            if not any(s['name'] == schema_name for s in schemas):
                                schemas.append({
                                    "name": schema_name,
                                    "display_name": schema_name
                                })
                    except Exception as e2:
                        # Если all_tables не доступен, используем только текущего пользователя
                        print(f"Could not get schemas from all_tables: {e2}")
                    
                    return {
                        "success": True,
                        "schemas": schemas,
                        "count": len(schemas)
                    }
        except Exception as e:
            # Последний fallback: возвращаем только текущего пользователя
            try:
                with DatabaseModel() as db:
                    with db.connection.cursor() as cursor:
                        cursor.execute("SELECT USER FROM DUAL")
                        current_user = cursor.fetchone()[0]
                        return {
                            "success": True,
                            "schemas": [{"name": current_user, "display_name": current_user}],
                            "count": 1
                        }
            except Exception as e2:
                return {
                    "success": False,
                    "error": f"{str(e)} / {str(e2)}",
                    "schemas": [],
                    "count": 0
                }
    
    @staticmethod
    def get_tables(schema: str = None) -> Dict[str, Any]:
        """Получает список таблиц для указанной схемы"""
        try:
            with DatabaseModel() as db:
                with db.connection.cursor() as cursor:
                    if schema:
                        # Используем ALL_TABLES с фильтром по owner
                        cursor.execute("""
                            SELECT 
                                owner,
                                table_name,
                                tablespace_name,
                                num_rows,
                                last_analyzed
                            FROM all_tables
                            WHERE owner = :schema
                            ORDER BY table_name
                        """, {"schema": schema.upper()})
                    else:
                        # Используем USER_TABLES для текущего пользователя
                        cursor.execute("""
                            SELECT 
                                table_name,
                                tablespace_name,
                                num_rows,
                                last_analyzed
                            FROM user_tables
                            ORDER BY table_name
                        """)
                    
                    tables = []
                    for row in cursor.fetchall():
                        if schema:
                            tables.append({
                                "name": row[1],
                                "schema": row[0],
                                "tablespace": row[2],
                                "num_rows": int(row[3]) if row[3] else 0,
                                "last_analyzed": row[4].strftime("%Y-%m-%d %H:%M:%S") if row[4] else None
                            })
                        else:
                            tables.append({
                                "name": row[0],
                                "tablespace": row[1],
                                "num_rows": int(row[2]) if row[2] else 0,
                                "last_analyzed": row[3].strftime("%Y-%m-%d %H:%M:%S") if row[3] else None
                            })
                    return {
                        "success": True,
                        "type": "tables",
                        "schema": schema,
                        "objects": tables,
                        "count": len(tables)
                    }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "objects": [],
                "type": "tables",
                "count": 0
            }
    
    @staticmethod
    def get_views(schema: str = None) -> Dict[str, Any]:
        """Получает список представлений для указанной схемы"""
        try:
            with DatabaseModel() as db:
                with db.connection.cursor() as cursor:
                    if schema:
                        cursor.execute("""
                            SELECT 
                                owner,
                                view_name,
                                text_length,
                                read_only
                            FROM all_views
                            WHERE owner = :schema
                            ORDER BY view_name
                        """, {"schema": schema.upper()})
                    else:
                        cursor.execute("""
                            SELECT 
                                view_name,
                                text_length,
                                read_only
                            FROM user_views
                            ORDER BY view_name
                        """)
                    
                    views = []
                    for row in cursor.fetchall():
                        if schema:
                            views.append({
                                "name": row[1],
                                "schema": row[0],
                                "text_length": int(row[2]) if row[2] else 0,
                                "read_only": row[3] if len(row) > 3 else None
                            })
                        else:
                            views.append({
                                "name": row[0],
                                "text_length": int(row[1]) if row[1] else 0,
                                "read_only": row[2] if len(row) > 2 else None
                            })
                    return {
                        "success": True,
                        "type": "views",
                        "schema": schema,
                        "objects": views,
                        "count": len(views)
                    }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "objects": [],
                "type": "views",
                "count": 0
            }
    
    @staticmethod
    def get_procedures(schema: str = None) -> Dict[str, Any]:
        """Получает список процедур для указанной схемы"""
        try:
            with DatabaseModel() as db:
                with db.connection.cursor() as cursor:
                    if schema:
                        # Используем all_objects для получения статуса
                        cursor.execute("""
                            SELECT DISTINCT
                                p.owner,
                                p.object_name,
                                p.procedure_name,
                                o.status
                            FROM all_procedures p
                            LEFT JOIN all_objects o ON p.owner = o.owner 
                                AND p.object_name = o.object_name 
                                AND o.object_type = 'PROCEDURE'
                            WHERE p.owner = :schema
                            AND p.object_type = 'PROCEDURE'
                            ORDER BY p.object_name, p.procedure_name
                        """, {"schema": schema.upper()})
                    else:
                        # Используем user_objects для получения статуса
                        cursor.execute("""
                            SELECT DISTINCT
                                p.object_name,
                                p.procedure_name,
                                o.status
                            FROM user_procedures p
                            LEFT JOIN user_objects o ON p.object_name = o.object_name 
                                AND o.object_type = 'PROCEDURE'
                            WHERE p.object_type = 'PROCEDURE'
                            ORDER BY p.object_name, p.procedure_name
                        """)
                    
                    procedures = []
                    for row in cursor.fetchall():
                        if schema:
                            procedures.append({
                                "name": row[2] if row[2] else row[1],
                                "schema": row[0],
                                "object_name": row[1],
                                "status": row[3] if len(row) > 3 and row[3] else None
                            })
                        else:
                            procedures.append({
                                "name": row[1] if row[1] else row[0],
                                "object_name": row[0],
                                "status": row[2] if len(row) > 2 and row[2] else None
                            })
                    return {
                        "success": True,
                        "type": "procedures",
                        "schema": schema,
                        "objects": procedures,
                        "count": len(procedures)
                    }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "objects": [],
                "type": "procedures",
                "count": 0
            }
    
    @staticmethod
    def get_functions(schema: str = None) -> Dict[str, Any]:
        """Получает список функций для указанной схемы"""
        try:
            with DatabaseModel() as db:
                with db.connection.cursor() as cursor:
                    if schema:
                        # Используем all_objects для получения статуса
                        cursor.execute("""
                            SELECT DISTINCT
                                p.owner,
                                p.object_name,
                                p.procedure_name,
                                o.status
                            FROM all_procedures p
                            LEFT JOIN all_objects o ON p.owner = o.owner 
                                AND p.object_name = o.object_name 
                                AND o.object_type = 'FUNCTION'
                            WHERE p.owner = :schema
                            AND p.object_type = 'FUNCTION'
                            ORDER BY p.object_name, p.procedure_name
                        """, {"schema": schema.upper()})
                    else:
                        # Используем user_objects для получения статуса
                        cursor.execute("""
                            SELECT DISTINCT
                                p.object_name,
                                p.procedure_name,
                                o.status
                            FROM user_procedures p
                            LEFT JOIN user_objects o ON p.object_name = o.object_name 
                                AND o.object_type = 'FUNCTION'
                            WHERE p.object_type = 'FUNCTION'
                            ORDER BY p.object_name, p.procedure_name
                        """)
                    
                    functions = []
                    for row in cursor.fetchall():
                        if schema:
                            functions.append({
                                "name": row[2] if row[2] else row[1],
                                "schema": row[0],
                                "object_name": row[1],
                                "status": row[3] if len(row) > 3 and row[3] else None
                            })
                        else:
                            functions.append({
                                "name": row[1] if row[1] else row[0],
                                "object_name": row[0],
                                "status": row[2] if len(row) > 2 and row[2] else None
                            })
                    return {
                        "success": True,
                        "type": "functions",
                        "schema": schema,
                        "objects": functions,
                        "count": len(functions)
                    }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "objects": [],
                "type": "functions",
                "count": 0
            }
    
    @staticmethod
    def get_packages(schema: str = None) -> Dict[str, Any]:
        """Получает список пакетов для указанной схемы"""
        try:
            with DatabaseModel() as db:
                with db.connection.cursor() as cursor:
                    if schema:
                        cursor.execute("""
                            SELECT 
                                owner,
                                object_name,
                                status
                            FROM all_objects
                            WHERE owner = :schema
                            AND object_type = 'PACKAGE'
                            ORDER BY object_name
                        """, {"schema": schema.upper()})
                    else:
                        cursor.execute("""
                            SELECT 
                                object_name,
                                status
                            FROM user_objects
                            WHERE object_type = 'PACKAGE'
                            ORDER BY object_name
                        """)
                    
                    packages = []
                    for row in cursor.fetchall():
                        if schema:
                            packages.append({
                                "name": row[1],
                                "schema": row[0],
                                "status": row[2] if len(row) > 2 else None
                            })
                        else:
                            packages.append({
                                "name": row[0],
                                "status": row[1] if len(row) > 1 else None
                            })
                    return {
                        "success": True,
                        "type": "packages",
                        "schema": schema,
                        "objects": packages,
                        "count": len(packages)
                    }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "objects": [],
                "type": "packages",
                "count": 0
            }
    
    @staticmethod
    def get_sequences(schema: str = None) -> Dict[str, Any]:
        """Получает список последовательностей для указанной схемы"""
        try:
            with DatabaseModel() as db:
                with db.connection.cursor() as cursor:
                    if schema:
                        cursor.execute("""
                            SELECT 
                                sequence_owner,
                                sequence_name,
                                min_value,
                                max_value,
                                increment_by,
                                last_number
                            FROM all_sequences
                            WHERE sequence_owner = :schema
                            ORDER BY sequence_name
                        """, {"schema": schema.upper()})
                    else:
                        cursor.execute("""
                            SELECT 
                                sequence_name,
                                min_value,
                                max_value,
                                increment_by,
                                last_number
                            FROM user_sequences
                            ORDER BY sequence_name
                        """)
                    
                    sequences = []
                    for row in cursor.fetchall():
                        if schema:
                            sequences.append({
                                "name": row[1],
                                "schema": row[0],
                                "min_value": int(row[2]) if row[2] else None,
                                "max_value": int(row[3]) if row[3] else None,
                                "increment_by": int(row[4]) if row[4] else None,
                                "last_number": int(row[5]) if row[5] else None
                            })
                        else:
                            sequences.append({
                                "name": row[0],
                                "min_value": int(row[1]) if row[1] else None,
                                "max_value": int(row[2]) if row[2] else None,
                                "increment_by": int(row[3]) if row[3] else None,
                                "last_number": int(row[4]) if row[4] else None
                            })
                    return {
                        "success": True,
                        "type": "sequences",
                        "schema": schema,
                        "objects": sequences,
                        "count": len(sequences)
                    }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "objects": [],
                "type": "sequences",
                "count": 0
            }
    
    @staticmethod
    def get_synonyms(schema: str = None) -> Dict[str, Any]:
        """Получает список синонимов для указанной схемы"""
        try:
            with DatabaseModel() as db:
                with db.connection.cursor() as cursor:
                    if schema:
                        cursor.execute("""
                            SELECT 
                                owner,
                                synonym_name,
                                table_owner,
                                table_name
                            FROM all_synonyms
                            WHERE owner = :schema
                            ORDER BY synonym_name
                        """, {"schema": schema.upper()})
                    else:
                        cursor.execute("""
                            SELECT 
                                synonym_name,
                                table_owner,
                                table_name
                            FROM user_synonyms
                            ORDER BY synonym_name
                        """)
                    
                    synonyms = []
                    for row in cursor.fetchall():
                        if schema:
                            synonyms.append({
                                "name": row[1],
                                "schema": row[0],
                                "table_owner": row[2],
                                "table_name": row[3]
                            })
                        else:
                            synonyms.append({
                                "name": row[0],
                                "table_owner": row[1],
                                "table_name": row[2]
                            })
                    return {
                        "success": True,
                        "type": "synonyms",
                        "schema": schema,
                        "objects": synonyms,
                        "count": len(synonyms)
                    }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "objects": [],
                "type": "synonyms",
                "count": 0
            }
    
    @staticmethod
    def get_indexes(schema: str = None) -> Dict[str, Any]:
        """Получает список индексов для указанной схемы"""
        try:
            with DatabaseModel() as db:
                with db.connection.cursor() as cursor:
                    if schema:
                        cursor.execute("""
                            SELECT 
                                owner,
                                index_name,
                                table_name,
                                index_type,
                                uniqueness
                            FROM all_indexes
                            WHERE owner = :schema
                            ORDER BY index_name
                        """, {"schema": schema.upper()})
                    else:
                        cursor.execute("""
                            SELECT 
                                index_name,
                                table_name,
                                index_type,
                                uniqueness
                            FROM user_indexes
                            ORDER BY index_name
                        """)
                    
                    indexes = []
                    for row in cursor.fetchall():
                        if schema:
                            indexes.append({
                                "name": row[1],
                                "schema": row[0],
                                "table_name": row[2],
                                "index_type": row[3],
                                "uniqueness": row[4]
                            })
                        else:
                            indexes.append({
                                "name": row[0],
                                "table_name": row[1],
                                "index_type": row[2],
                                "uniqueness": row[3]
                            })
                    return {
                        "success": True,
                        "type": "indexes",
                        "schema": schema,
                        "objects": indexes,
                        "count": len(indexes)
                    }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "objects": [],
                "type": "indexes",
                "count": 0
            }
    
    @staticmethod
    def get_triggers(schema: str = None) -> Dict[str, Any]:
        """Получает список триггеров для указанной схемы"""
        try:
            with DatabaseModel() as db:
                with db.connection.cursor() as cursor:
                    if schema:
                        cursor.execute("""
                            SELECT 
                                owner,
                                trigger_name,
                                table_name,
                                trigger_type,
                                status
                            FROM all_triggers
                            WHERE owner = :schema
                            ORDER BY trigger_name
                        """, {"schema": schema.upper()})
                    else:
                        cursor.execute("""
                            SELECT 
                                trigger_name,
                                table_name,
                                trigger_type,
                                status
                            FROM user_triggers
                            ORDER BY trigger_name
                        """)
                    
                    triggers = []
                    for row in cursor.fetchall():
                        if schema:
                            triggers.append({
                                "name": row[1],
                                "schema": row[0],
                                "table_name": row[2],
                                "trigger_type": row[3],
                                "status": row[4] if len(row) > 4 else None
                            })
                        else:
                            triggers.append({
                                "name": row[0],
                                "table_name": row[1],
                                "trigger_type": row[2],
                                "status": row[3] if len(row) > 3 else None
                            })
                    return {
                        "success": True,
                        "type": "triggers",
                        "schema": schema,
                        "objects": triggers,
                        "count": len(triggers)
                    }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "objects": [],
                "type": "triggers",
                "count": 0
            }
    
    @staticmethod
    def get_types(schema: str = None) -> Dict[str, Any]:
        """Получает список типов для указанной схемы"""
        try:
            with DatabaseModel() as db:
                with db.connection.cursor() as cursor:
                    if schema:
                        cursor.execute("""
                            SELECT 
                                owner,
                                type_name,
                                typecode
                            FROM all_types
                            WHERE owner = :schema
                            ORDER BY type_name
                        """, {"schema": schema.upper()})
                    else:
                        cursor.execute("""
                            SELECT 
                                type_name,
                                typecode
                            FROM user_types
                            ORDER BY type_name
                        """)
                    
                    types = []
                    for row in cursor.fetchall():
                        if schema:
                            types.append({
                                "name": row[1],
                                "schema": row[0],
                                "typecode": row[2]
                            })
                        else:
                            types.append({
                                "name": row[0],
                                "typecode": row[1]
                            })
                    return {
                        "success": True,
                        "type": "types",
                        "schema": schema,
                        "objects": types,
                        "count": len(types)
                    }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "objects": [],
                "type": "types",
                "count": 0
            }
    
    @staticmethod
    def get_materialized_views(schema: str = None) -> Dict[str, Any]:
        """Получает список материализованных представлений для указанной схемы"""
        try:
            with DatabaseModel() as db:
                with db.connection.cursor() as cursor:
                    if schema:
                        cursor.execute("""
                            SELECT 
                                owner,
                                mview_name,
                                refresh_mode,
                                refresh_method,
                                build_mode
                            FROM all_mviews
                            WHERE owner = :schema
                            ORDER BY mview_name
                        """, {"schema": schema.upper()})
                    else:
                        cursor.execute("""
                            SELECT 
                                mview_name,
                                refresh_mode,
                                refresh_method,
                                build_mode
                            FROM user_mviews
                            ORDER BY mview_name
                        """)
                    
                    mviews = []
                    for row in cursor.fetchall():
                        if schema:
                            mviews.append({
                                "name": row[1],
                                "schema": row[0],
                                "refresh_mode": row[2],
                                "refresh_method": row[3],
                                "build_mode": row[4] if len(row) > 4 else None
                            })
                        else:
                            mviews.append({
                                "name": row[0],
                                "refresh_mode": row[1],
                                "refresh_method": row[2],
                                "build_mode": row[3] if len(row) > 3 else None
                            })
                    return {
                        "success": True,
                        "type": "materialized_views",
                        "schema": schema,
                        "objects": mviews,
                        "count": len(mviews)
                    }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "objects": [],
                "type": "materialized_views",
                "count": 0
            }
