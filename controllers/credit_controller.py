"""
Контроллер кредитов: админка и интерфейс оператора.
Использует пакеты CRED_ADMIN_PKG, CRED_OPERATOR_PKG и таблицы/вью в Oracle.
"""
from typing import Dict, Any, List, Optional
import sys
import os

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from models.database import DatabaseModel
import oracledb


class CreditController:
    """API для админки кредитов и интерфейса оператора."""

    @staticmethod
    def _rows_to_list(rows: List[Dict[str, Any]], keys_lower: bool = True) -> List[Dict[str, Any]]:
        """Преобразует строки из БД в список словарей с нормализованными ключами"""
        out = []
        for r in rows:
            if not r:
                continue
            if keys_lower:
                # Преобразуем ключи в нижний регистр
                normalized = {}
                for k, v in r.items():
                    if k:
                        normalized[k.lower()] = v
                out.append(normalized)
            else:
                out.append(dict(r))
        return out

    # ---------- Админка ----------

    @staticmethod
    def get_programs(bank: Optional[str] = None, term: Optional[int] = None, active: Optional[str] = None) -> Dict[str, Any]:
        """Получает программы - использует прямой SQL как табло рейсов"""
        try:
            with DatabaseModel() as db:
                # Используем прямой SQL запрос (как в табло рейсов)
                sql = """SELECT p.ID, p.NAME, b.NAME AS BANK_NAME, p.BANK_ID, p.TERM_MONTHS, 
                                p.RATE_PCT, p.FIRST_PAYMENT_PCT, p.MIN_SUM, p.MAX_SUM, 
                                p.COMMISSION_PCT, p.ACTIVE, p.NOTES
                         FROM CRED_PROGRAMS p
                         JOIN CRED_BANKS b ON b.ID = p.BANK_ID
                         WHERE 1=1"""
                params = {}
                
                if bank:
                    sql += " AND UPPER(b.NAME) LIKE '%' || UPPER(:bank) || '%'"
                    params["bank"] = bank
                if term:
                    sql += " AND p.TERM_MONTHS = :term"
                    params["term"] = term
                if active:
                    sql += " AND p.ACTIVE = :active"
                    params["active"] = active
                
                sql += " ORDER BY p.NAME"
                
                r = db.execute_query(sql, params if params else None)
                
                if not r.get("success") or not r.get("data"):
                    return {"success": False, "error": r.get("message", "No data"), "data": []}
                
                # Преобразуем данные как в табло рейсов
                cols = [c.upper() for c in (r.get("columns") or [])]
                normalized_data = []
                for row in r.get("data", []):
                    d = dict(zip(cols, row))
                    active_val = d.get("ACTIVE")
                    is_active = (active_val == "Y" or active_val == 1 or active_val == "1") if active_val is not None else False
                    normalized = {
                        "id": d.get("ID") or 0,
                        "program_id": d.get("ID") or 0,
                        "name": d.get("NAME") or "",
                        "program_name": d.get("NAME") or "",
                        "bank_id": int(d.get("BANK_ID") or 0) if d.get("BANK_ID") else None,
                        "bank_name": str(d.get("BANK_NAME") or ""),
                        "term_months": int(d.get("TERM_MONTHS") or 0),
                        "rate_pct": float(d.get("RATE_PCT") or 0),
                        "first_payment_pct": int(d.get("FIRST_PAYMENT_PCT") or 0),
                        "min_amount": int(d.get("MIN_SUM") or 0),
                        "min_sum": int(d.get("MIN_SUM") or 0),
                        "max_amount": int(d.get("MAX_SUM") or 0),
                        "max_sum": int(d.get("MAX_SUM") or 0),
                        "commission_pct": float(d.get("COMMISSION_PCT") or 0),
                        "active": "Y" if is_active else "N",
                        "is_active": 1 if is_active else 0,
                        "notes": str(d.get("NOTES") or ""),
                    }
                    normalized_data.append(normalized)
                return {"success": True, "data": normalized_data}
        except Exception as e:
            import traceback
            print(f"Error in get_programs: {e}")
            print(traceback.format_exc())
            return {"success": False, "error": str(e), "data": []}

    @staticmethod
    def get_program_by_id(program_id: int) -> Dict[str, Any]:
        """Получает программу по ID - использует прямой SQL как табло рейсов"""
        try:
            with DatabaseModel() as db:
                # Используем прямой SQL запрос (как в табло рейсов)
                sql = """SELECT p.ID, p.NAME, b.NAME AS BANK_NAME, p.BANK_ID, p.TERM_MONTHS, 
                                p.RATE_PCT, p.FIRST_PAYMENT_PCT, p.MIN_SUM, p.MAX_SUM, 
                                p.COMMISSION_PCT, p.ACTIVE, p.NOTES
                         FROM CRED_PROGRAMS p
                         JOIN CRED_BANKS b ON b.ID = p.BANK_ID
                         WHERE p.ID = :id"""
                
                print(f"Executing get_program_by_id for ID: {program_id}")
                r = db.execute_query(sql, {"id": program_id})
                print(f"Query result: success={r.get('success')}, data_count={len(r.get('data', []))}")
                
                if not r.get("success"):
                    error_msg = r.get("message", "Database query failed")
                    return {"success": False, "error": error_msg, "data": None}
                
                if not r.get("data") or len(r.get("data", [])) == 0:
                    return {"success": False, "error": "Program not found", "data": None}
                
                # Преобразуем данные как в табло рейсов
                cols = [c.upper() for c in (r.get("columns") or [])]
                if not cols:
                    return {"success": False, "error": "No columns in result", "data": None}
                
                row = r.get("data", [])[0]
                if not row:
                    return {"success": False, "error": "Empty row data", "data": None}
                
                d = dict(zip(cols, row))
                
                active_val = d.get("ACTIVE")
                is_active = (active_val == "Y" or active_val == 1 or active_val == "1") if active_val is not None else False
                
                normalized = {
                    "id": d.get("ID") or 0,
                    "program_id": d.get("ID") or 0,
                    "name": d.get("NAME") or "",
                    "program_name": d.get("NAME") or "",
                    "bank_id": int(d.get("BANK_ID") or 0) if d.get("BANK_ID") else None,
                    "bank_name": str(d.get("BANK_NAME") or ""),
                    "term_months": int(d.get("TERM_MONTHS") or 0),
                    "rate_pct": float(d.get("RATE_PCT") or 0),
                    "first_payment_pct": int(d.get("FIRST_PAYMENT_PCT") or 0),
                    "min_amount": int(d.get("MIN_SUM") or 0),
                    "min_sum": int(d.get("MIN_SUM") or 0),
                    "max_amount": int(d.get("MAX_SUM") or 0),
                    "max_sum": int(d.get("MAX_SUM") or 0),
                    "commission_pct": float(d.get("COMMISSION_PCT") or 0),
                    "active": "Y" if is_active else "N",
                    "is_active": 1 if is_active else 0,
                    "notes": str(d.get("NOTES") or ""),
                }
                return {"success": True, "data": normalized}
        except Exception as e:
            import traceback
            print(f"Error in get_program_by_id: {e}")
            print(traceback.format_exc())
            return {"success": False, "error": str(e), "data": None}

    @staticmethod
    def upsert_program(p: Dict[str, Any]) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                with db.connection.cursor() as cur:
                    pid = cur.var(oracledb.NUMBER)
                    pid.setvalue(0, int(p.get("id") or 0))
                    # Поддерживаем оба варианта названий полей
                    min_amount = p.get("min_amount") or p.get("min_sum") or 1000
                    max_amount = p.get("max_amount") or p.get("max_sum") or 100000
                    program_name = p.get("program_name") or p.get("name") or ""
                    cur.callproc(
                        "CRED_ADMIN_PKG.UPSERT_PROGRAM",
                        [
                            pid,
                            program_name,
                            int(p.get("bank_id")),
                            int(p.get("term_months")),
                            float(p.get("rate_pct", 0) or 0),
                            int(p.get("first_payment_pct", 0) or 0),
                            int(min_amount),
                            int(max_amount),
                            float(p.get("commission_pct", 0) or 0),
                            "Y" if p.get("active", True) else "N",
                            p.get("notes") or None,
                        ],
                    )
                    out_id = pid.getvalue()
                    if isinstance(out_id, (list, tuple)):
                        out_id = out_id[0] if out_id else None
            return {"success": True, "id": out_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def delete_program(program_id: int) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                with db.connection.cursor() as cur:
                    cur.callproc("CRED_ADMIN_PKG.DELETE_PROGRAM", [program_id])
                db.connection.commit()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_banks() -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                r = db.execute_query("SELECT ID, CODE, NAME FROM CRED_BANKS ORDER BY NAME")
            if not r.get("success") or not r.get("columns"):
                return {"success": False, "error": r.get("message", "No data"), "data": []}
            cols = [c.upper() for c in r["columns"]]
            data = [dict(zip(cols, row)) for row in (r.get("data") or [])]
            return {"success": True, "data": [{"id": d["ID"], "code": d["CODE"], "name": d["NAME"]} for d in data]}
        except Exception as e:
            return {"success": False, "error": str(e), "data": []}

    @staticmethod
    def get_categories() -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                r = db.execute_query("SELECT ID, NAME FROM CRED_CATEGORIES ORDER BY NAME")
            if not r.get("success") or not r.get("columns"):
                return {"success": False, "error": r.get("message", "No data"), "data": []}
            cols = [c.upper() for c in r["columns"]]
            data = [dict(zip(cols, row)) for row in (r.get("data") or [])]
            return {"success": True, "data": [{"id": d["ID"], "name": d["NAME"]} for d in data]}
        except Exception as e:
            return {"success": False, "error": str(e), "data": []}

    @staticmethod
    def get_brands() -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                r = db.execute_query("SELECT ID, NAME FROM CRED_BRANDS ORDER BY NAME")
            if not r.get("success") or not r.get("columns"):
                return {"success": False, "error": r.get("message", "No data"), "data": []}
            cols = [c.upper() for c in r["columns"]]
            data = [dict(zip(cols, row)) for row in (r.get("data") or [])]
            return {"success": True, "data": [{"id": d["ID"], "name": d["NAME"]} for d in data]}
        except Exception as e:
            return {"success": False, "error": str(e), "data": []}

    @staticmethod
    def get_matrix() -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                rows = db.fetch_refcursor(
                    "BEGIN CRED_ADMIN_PKG.GET_MATRIX(:cur); END;",
                    {},
                    "cur",
                )
            return {"success": True, "data": CreditController._rows_to_list(rows)}
        except Exception as e:
            return {"success": False, "error": str(e), "data": []}

    @staticmethod
    def set_matrix_row(program_id: int, category_id: int, enabled: bool) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                with db.connection.cursor() as cur:
                    cur.callproc(
                        "CRED_ADMIN_PKG.SET_MATRIX_ROW",
                        [program_id, category_id, 1 if enabled else 0],
                    )
                db.connection.commit()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_matrix_products(
        program_id: int,
        category_id: int,
        search: Optional[str] = None,
        limit: int = 500,
    ) -> Dict[str, Any]:
        """Товары категории с флагом linked для программы. Фильтр по наименованию."""
        try:
            with DatabaseModel() as db:
                sql = """
                    SELECT * FROM (
                        SELECT p.ID, p.NAME, p.ARTICLE, p.PRICE,
                               CASE WHEN pp.PRODUCT_ID IS NOT NULL THEN 1 ELSE 0 END AS LINKED
                        FROM CRED_PRODUCTS p
                        LEFT JOIN CRED_PROGRAM_PRODUCTS pp
                          ON pp.PROGRAM_ID = :program_id AND pp.PRODUCT_ID = p.ID
                        WHERE p.CATEGORY_ID = :category_id
                """
                params: Dict[str, Any] = {"program_id": program_id, "category_id": category_id, "lim": limit}
                if search and search.strip():
                    sql += " AND (UPPER(p.NAME) LIKE '%' || UPPER(:search) || '%' OR UPPER(NVL(p.ARTICLE,'')) LIKE '%' || UPPER(:search) || '%')"
                    params["search"] = search.strip()
                sql += " ORDER BY p.NAME ) WHERE ROWNUM <= :lim"
                r = db.execute_query(sql, params)
                if not r.get("success") or not r.get("columns"):
                    return {"success": False, "error": r.get("message", "No data"), "data": []}
                cols = [c.upper() for c in (r.get("columns") or [])]
                data = []
                for row in (r.get("data") or []):
                    d = dict(zip(cols, row))
                    data.append({
                        "id": d.get("ID"),
                        "name": d.get("NAME") or "",
                        "article": d.get("ARTICLE") or "",
                        "price": float(d.get("PRICE") or 0),
                        "linked": bool(d.get("LINKED")),
                    })
                return {"success": True, "data": data}
        except Exception as e:
            return {"success": False, "error": str(e), "data": []}

    @staticmethod
    def set_matrix_products(
        program_id: int,
        category_id: int,
        product_ids: List[int],
    ) -> Dict[str, Any]:
        """Задать конкретные товары для пары программа × категория."""
        try:
            with DatabaseModel() as db:
                with db.connection.cursor() as cur:
                    cur.execute("""
                        DELETE FROM CRED_PROGRAM_PRODUCTS
                        WHERE PROGRAM_ID = :pid AND PRODUCT_ID IN (
                            SELECT ID FROM CRED_PRODUCTS WHERE CATEGORY_ID = :cid
                        )
                    """, {"pid": program_id, "cid": category_id})
                    for pid in product_ids:
                        if not pid:
                            continue
                        cur.execute(
                            """INSERT INTO CRED_PROGRAM_PRODUCTS (PROGRAM_ID, PRODUCT_ID)
                               SELECT :pid, :prod FROM DUAL
                               WHERE EXISTS (SELECT 1 FROM CRED_PRODUCTS WHERE ID = :prod AND CATEGORY_ID = :cid)
                            """,
                            {"pid": program_id, "prod": int(pid), "cid": category_id},
                        )
                db.connection.commit()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ---------- Pivot "Кредитный портфель Бомба" ----------

    @staticmethod
    def get_pivot_meta() -> Dict[str, Any]:
        """Категории с количеством товаров, банки с программами для пивота."""
        try:
            with DatabaseModel() as db:
                r = db.execute_query("""
                    SELECT c.ID, c.NAME, (SELECT COUNT(*) FROM CRED_PRODUCTS p WHERE p.CATEGORY_ID = c.ID) AS CNT
                    FROM CRED_CATEGORIES c ORDER BY c.NAME
                """)
                if not r.get("success") or not r.get("columns"):
                    return {"success": False, "error": r.get("message", "No data"), "categories": [], "banks": []}
                cols = [x.upper() for x in (r.get("columns") or [])]
                categories = [{"id": row[0], "name": row[1], "product_count": row[2]} for row in (r.get("data") or [])]

                r2 = db.execute_query("SELECT ID, CODE, NAME FROM CRED_BANKS ORDER BY NAME")
                banks_rows = r2.get("data") or []
                r3 = db.execute_query("""
                    SELECT p.ID, p.NAME, p.BANK_ID, p.TERM_MONTHS, p.RATE_PCT, p.MIN_SUM, p.MAX_SUM, p.ACTIVE
                    FROM CRED_PROGRAMS p ORDER BY p.BANK_ID, p.TERM_MONTHS, p.ID
                """)
                prog_cols = [x.upper() for x in (r3.get("columns") or [])]
                programs = []
                for row in (r3.get("data") or []):
                    d = dict(zip(prog_cols, row))
                    programs.append({
                        "id": d.get("ID"), "name": d.get("NAME"), "bank_id": d.get("BANK_ID"),
                        "term_months": d.get("TERM_MONTHS"), "rate_pct": d.get("RATE_PCT"),
                        "min_sum": d.get("MIN_SUM"), "max_sum": d.get("MAX_SUM"), "active": d.get("ACTIVE"),
                    })

                banks = []
                for (bid, code, bname) in banks_rows:
                    progs = [x for x in programs if x["bank_id"] == bid]
                    banks.append({"id": bid, "code": code, "name": bname, "programs": progs})

            return {"success": True, "categories": categories, "banks": banks}
        except Exception as e:
            return {"success": False, "error": str(e), "categories": [], "banks": []}

    @staticmethod
    def get_pivot_matrix() -> Dict[str, Any]:
        """Матрица категория × программа: список { category_id, program_id, enabled }."""
        try:
            with DatabaseModel() as db:
                r = db.execute_query("""
                    SELECT c.ID AS CATEGORY_ID, p.ID AS PROGRAM_ID,
                           CASE WHEN pc.PROGRAM_ID IS NOT NULL THEN 1 ELSE 0 END AS ENABLED
                    FROM CRED_CATEGORIES c
                    CROSS JOIN CRED_PROGRAMS p
                    LEFT JOIN CRED_PROGRAM_CATEGORIES pc ON pc.CATEGORY_ID = c.ID AND pc.PROGRAM_ID = p.ID
                    WHERE p.ACTIVE = 'Y'
                """)
                if not r.get("success") or not r.get("data"):
                    return {"success": True, "data": []}
                cols = [x.upper() for x in (r.get("columns") or [])]
                data = [dict(zip(cols, row)) for row in r["data"]]
                return {"success": True, "data": [
                    {"category_id": x["CATEGORY_ID"], "program_id": x["PROGRAM_ID"], "enabled": bool(x["ENABLED"])}
                    for x in data
                ]}
        except Exception as e:
            return {"success": False, "error": str(e), "data": []}

    @staticmethod
    def get_pivot_products(
        category_ids: Optional[List[int]] = None,
        search: Optional[str] = None,
        limit: int = 500,
    ) -> Dict[str, Any]:
        """Товары для пивота с фильтром по категориям и поиску."""
        try:
            with DatabaseModel() as db:
                sql = """
                    SELECT * FROM (
                        SELECT v.ID, v.NAME, v.ARTICLE, v.PRICE, v.CATEGORY_ID, v.CATEGORY_NAME, v.BRAND_NAME
                        FROM V_CRED_PRODUCTS v
                        WHERE 1=1
                """
                params: Dict[str, Any] = {"lim": limit}
                if category_ids:
                    ids = [int(x) for x in category_ids if isinstance(x, (int, str)) and str(x).isdigit()]
                    if ids:
                        placeholders = ",".join([f":c{i}" for i in range(len(ids))])
                        sql += f" AND v.CATEGORY_ID IN ({placeholders})"
                        for i, v in enumerate(ids):
                            params[f"c{i}"] = v
                if search and search.strip():
                    sql += " AND (UPPER(v.NAME) LIKE '%' || UPPER(:search) || '%' OR UPPER(NVL(v.ARTICLE,'')) LIKE '%' || UPPER(:search) || '%')"
                    params["search"] = search.strip()
                sql += " ORDER BY v.CATEGORY_NAME, v.NAME ) WHERE ROWNUM <= :lim"
                r = db.execute_query(sql, params)
                if not r.get("success") or not r.get("columns"):
                    return {"success": False, "error": r.get("message", "No data"), "data": []}
                cols = [x.upper() for x in (r.get("columns") or [])]
                data = []
                for row in (r.get("data") or []):
                    d = dict(zip(cols, row))
                    data.append({
                        "id": d.get("ID"), "name": d.get("NAME"), "article": d.get("ARTICLE"),
                        "price": float(d.get("PRICE") or 0), "category_id": d.get("CATEGORY_ID"),
                        "category_name": d.get("CATEGORY_NAME"), "brand_name": d.get("BRAND_NAME"),
                    })
                return {"success": True, "data": data}
        except Exception as e:
            return {"success": False, "error": str(e), "data": []}

    # ---------- Оператор ----------

    @staticmethod
    def get_products(search: Optional[str] = None, barcode: Optional[str] = None, limit: int = 10) -> Dict[str, Any]:
        """Получает товары - использует прямой SQL как табло рейсов"""
        try:
            with DatabaseModel() as db:
                # Используем прямой SQL запрос к представлению (как в табло рейсов)
                if barcode:
                    # Поиск по штрихкоду
                    sql = "SELECT ID, NAME, ARTICLE, BARCODE, PRICE, CATEGORY_ID, CATEGORY_NAME, BRAND_ID, BRAND_NAME, IMG_URL FROM V_CRED_PRODUCTS WHERE BARCODE = :barcode"
                    r = db.execute_query(sql, {"barcode": barcode})
                elif search:
                    # Поиск по тексту - используем ROWNUM для совместимости
                    sql = """SELECT * FROM (
                               SELECT ID, NAME, ARTICLE, BARCODE, PRICE, CATEGORY_ID, CATEGORY_NAME, BRAND_ID, BRAND_NAME, IMG_URL 
                               FROM V_CRED_PRODUCTS 
                               WHERE UPPER(NAME) LIKE '%' || UPPER(:search) || '%' 
                                  OR UPPER(NVL(ARTICLE,'')) LIKE '%' || UPPER(:search) || '%'
                               ORDER BY PRICE DESC
                             ) WHERE ROWNUM <= :lim"""
                    r = db.execute_query(sql, {"search": search, "lim": limit})
                else:
                    # Все товары - используем ROWNUM для совместимости
                    sql = """SELECT * FROM (
                               SELECT ID, NAME, ARTICLE, BARCODE, PRICE, CATEGORY_ID, CATEGORY_NAME, BRAND_ID, BRAND_NAME, IMG_URL 
                               FROM V_CRED_PRODUCTS 
                               ORDER BY PRICE DESC
                             ) WHERE ROWNUM <= :lim"""
                    r = db.execute_query(sql, {"lim": limit})
                
                if not r.get("success") or not r.get("data"):
                    return {"success": False, "error": r.get("message", "No data"), "data": []}
                
                # Преобразуем данные как в табло рейсов
                cols = [c.upper() for c in (r.get("columns") or [])]
                normalized_data = []
                for row in r.get("data", []):
                    d = dict(zip(cols, row))
                    normalized = {
                        "id": d.get("ID") or 0,
                        "product_id": d.get("ID") or 0,
                        "name": d.get("NAME") or "",
                        "product_name": d.get("NAME") or "",
                        "price": float(d.get("PRICE") or 0),
                        "barcode": str(d.get("BARCODE") or ""),
                        "img_url": str(d.get("IMG_URL") or ""),
                        "category_name": str(d.get("CATEGORY_NAME") or ""),
                        "brand_name": str(d.get("BRAND_NAME") or ""),
                    }
                    normalized_data.append(normalized)
                
                return {"success": True, "data": normalized_data}
        except Exception as e:
            import traceback
            print(f"Error in get_products: {e}")
            print(traceback.format_exc())
            return {"success": False, "error": str(e), "data": []}

    @staticmethod
    def get_product_by_id(product_id: int) -> Dict[str, Any]:
        """Получает товар по ID - использует прямой SQL как табло рейсов"""
        try:
            with DatabaseModel() as db:
                sql = "SELECT ID, NAME, ARTICLE, BARCODE, PRICE, CATEGORY_ID, CATEGORY_NAME, BRAND_ID, BRAND_NAME, IMG_URL FROM V_CRED_PRODUCTS WHERE ID = :id"
                r = db.execute_query(sql, {"id": product_id})
                
                if not r.get("success") or not r.get("data"):
                    return {"success": False, "error": "Product not found", "data": None}
                
                cols = [c.upper() for c in (r.get("columns") or [])]
                row = r.get("data", [])[0]
                d = dict(zip(cols, row))
                
                normalized = {
                    "id": d.get("ID") or 0,
                    "product_id": d.get("ID") or 0,
                    "name": d.get("NAME") or "",
                    "product_name": d.get("NAME") or "",
                    "price": float(d.get("PRICE") or 0),
                    "barcode": str(d.get("BARCODE") or ""),
                    "img_url": str(d.get("IMG_URL") or ""),
                    "category_name": str(d.get("CATEGORY_NAME") or ""),
                    "brand_name": str(d.get("BRAND_NAME") or ""),
                }
                return {"success": True, "data": normalized}
        except Exception as e:
            import traceback
            print(f"Error in get_product_by_id: {e}")
            print(traceback.format_exc())
            return {"success": False, "error": str(e), "data": None}

    @staticmethod
    def get_programs_for_product(product_id: int) -> Dict[str, Any]:
        """Получает программы для товара - использует прямой SQL как табло рейсов"""
        try:
            with DatabaseModel() as db:
                # Логика из пакета: проверяем категорию, цену и исключенные бренды
                sql = """SELECT
                            p.ID, p.NAME, p.TERM_MONTHS, p.RATE_PCT, p.FIRST_PAYMENT_PCT,
                            p.MIN_SUM, p.MAX_SUM, b.NAME AS BANK_NAME
                         FROM CRED_PROGRAMS p
                         JOIN CRED_BANKS b ON b.ID = p.BANK_ID
                         JOIN CRED_PRODUCTS pr ON pr.ID = :product_id
                         JOIN CRED_PROGRAM_CATEGORIES pc ON pc.PROGRAM_ID = p.ID AND pc.CATEGORY_ID = pr.CATEGORY_ID
                         WHERE p.ACTIVE = 'Y'
                           AND pr.PRICE BETWEEN p.MIN_SUM AND p.MAX_SUM
                           AND (pr.BRAND_ID IS NULL OR NOT EXISTS (
                             SELECT 1 FROM CRED_PROGRAM_EXCLUDED_BRANDS eb
                             WHERE eb.PROGRAM_ID = p.ID AND eb.BRAND_ID = pr.BRAND_ID
                           ))
                         ORDER BY p.TERM_MONTHS DESC"""
                
                r = db.execute_query(sql, {"product_id": product_id})
                
                if not r.get("success") or not r.get("data"):
                    return {"success": True, "data": []}
                
                cols = [c.upper() for c in (r.get("columns") or [])]
                normalized_data = []
                for row in r.get("data", []):
                    d = dict(zip(cols, row))
                    normalized = {
                        "id": d.get("ID") or 0,
                        "program_id": d.get("ID") or 0,
                        "name": d.get("NAME") or "",
                        "program_name": d.get("NAME") or "",
                        "term_months": int(d.get("TERM_MONTHS") or 0),
                        "first_payment_pct": int(d.get("FIRST_PAYMENT_PCT") or 0),
                        "rate_pct": float(d.get("RATE_PCT") or 0),
                        "min_sum": int(d.get("MIN_SUM") or 0),
                        "max_sum": int(d.get("MAX_SUM") or 0),
                        "bank_name": str(d.get("BANK_NAME") or ""),
                    }
                    normalized_data.append(normalized)
                return {"success": True, "data": normalized_data}
        except Exception as e:
            import traceback
            print(f"Error in get_programs_for_product: {e}")
            print(traceback.format_exc())
            return {"success": False, "error": str(e), "data": []}

    @staticmethod
    def create_application(
        product_id: int,
        program_id: int,
        client_fio: str,
        client_phone: str,
        client_idn: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                with db.connection.cursor() as cur:
                    app_id = cur.var(oracledb.NUMBER)
                    status = cur.var(str, 100)
                    approved = cur.var(oracledb.NUMBER)
                    reason = cur.var(str, 500)
                    cur.callproc(
                        "CRED_OPERATOR_PKG.CREATE_APPLICATION",
                        [
                            int(product_id),
                            int(program_id),
                            client_fio,
                            client_phone,
                            client_idn or None,
                            app_id,
                            status,
                            approved,
                            reason,
                        ],
                    )
                    def _v(v):
                        x = v.getvalue()
                        return (x[0] if isinstance(x, (list, tuple)) and x else x) if x is not None else None
                    return {
                        "success": True,
                        "app_id": _v(app_id),
                        "status": _v(status),
                        "approved_amount": _v(approved),
                        "rejection_reason": _v(reason),
                    }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_recent_applications(limit: int = 5) -> Dict[str, Any]:
        """Получает последние заявки - использует прямой SQL как табло рейсов"""
        try:
            with DatabaseModel() as db:
                # Используем представление V_CRED_APPLICATIONS_RECENT
                sql = """SELECT * FROM (
                           SELECT ID, PRODUCT_NAME, PROGRAM_NAME, CLIENT_FIO, STATUS, CREATED_TIME 
                           FROM V_CRED_APPLICATIONS_RECENT
                           ORDER BY CREATED_AT DESC
                         ) WHERE ROWNUM <= :lim"""
                
                r = db.execute_query(sql, {"lim": limit})
                
                if not r.get("success") or not r.get("data"):
                    return {"success": True, "data": []}
                
                cols = [c.upper() for c in (r.get("columns") or [])]
                normalized_data = []
                for row in r.get("data", []):
                    d = dict(zip(cols, row))
                    normalized = {
                        "application_id": d.get("ID") or 0,
                        "id": d.get("ID") or 0,
                        "product_name": str(d.get("PRODUCT_NAME") or ""),
                        "program_name": str(d.get("PROGRAM_NAME") or ""),
                        "client_fio": str(d.get("CLIENT_FIO") or ""),
                        "application_status": str(d.get("STATUS") or "pending"),
                        "status": str(d.get("STATUS") or "pending"),
                        "created_time": str(d.get("CREATED_TIME") or ""),
                    }
                    normalized_data.append(normalized)
                return {"success": True, "data": normalized_data}
        except Exception as e:
            import traceback
            print(f"Error in get_recent_applications: {e}")
            print(traceback.format_exc())
            return {"success": False, "error": str(e), "data": []}

    # ---------- Настраиваемые отчёты ----------

    @staticmethod
    def get_reports() -> Dict[str, Any]:
        """Список отчётов из CRED_REPORTS."""
        try:
            with DatabaseModel() as db:
                rows = db.fetch_refcursor(
                    "BEGIN CRED_REPORTS_PKG.GET_REPORTS(:cur); END;",
                    {},
                    "cur",
                )
            return {"success": True, "data": CreditController._rows_to_list(rows)}
        except Exception as e:
            err = str(e)
            if "PLS-00201" in err or "must be declared" in err or "CRED_REPORTS_PKG" in err:
                return {
                    "success": False,
                    "error": "Пакет CRED_REPORTS_PKG не создан. Выполните: python deploy_oracle_objects.py",
                    "data": [],
                }
            return {"success": False, "error": err, "data": []}

    @staticmethod
    def get_report_params(report_id: int) -> Dict[str, Any]:
        """Параметры отчёта из CRED_REPORT_PARAMS."""
        try:
            with DatabaseModel() as db:
                rows = db.fetch_refcursor(
                    "BEGIN CRED_REPORTS_PKG.GET_REPORT_PARAMS(:rid, :cur); END;",
                    {"rid": report_id},
                    "cur",
                )
            return {"success": True, "data": CreditController._rows_to_list(rows)}
        except Exception as e:
            err = str(e)
            if "PLS-00201" in err or "must be declared" in err or "CRED_REPORTS_PKG" in err:
                return {
                    "success": False,
                    "error": "Выполните: python deploy_oracle_objects.py",
                    "data": [],
                }
            return {"success": False, "error": err, "data": []}

    @staticmethod
    def execute_report(report_id: int, params: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнить отчёт с параметрами. Использует прямой SQL (без PL/SQL ref cursor)."""
        try:
            with DatabaseModel() as db:
                # Получаем код отчёта
                rcfg = db.execute_query(
                    "SELECT CODE FROM CRED_REPORTS WHERE ID = :rid AND ENABLED = 'Y'",
                    {"rid": report_id},
                )
                if not rcfg.get("success") or not rcfg.get("data"):
                    return {"success": False, "error": "Отчёт не найден", "data": []}
                code = rcfg["data"][0][0] if rcfg["data"] else None
                p = params or {}

                qparams: Dict[str, Any] = {}
                if code == "APP_BY_STATUS":
                    sql = """
                        SELECT a.ID, a.CLIENT_FIO, a.CLIENT_PHONE, a.STATUS, a.APPROVED_AMOUNT, a.CREATED_AT,
                               p.NAME AS PRODUCT_NAME, pr.NAME AS PROGRAM_NAME, b.NAME AS BANK_NAME
                        FROM CRED_APPLICATIONS a
                        JOIN CRED_PRODUCTS p ON a.PRODUCT_ID = p.ID
                        JOIN CRED_PROGRAMS pr ON a.PROGRAM_ID = pr.ID
                        JOIN CRED_BANKS b ON pr.BANK_ID = b.ID
                        WHERE 1=1
                    """
                    if p.get("status"):
                        sql += " AND a.STATUS = :status"
                        qparams["status"] = str(p["status"])
                    if p.get("date_from"):
                        sql += " AND TRUNC(a.CREATED_AT) >= TRUNC(TO_DATE(:dt_from, 'YYYY-MM-DD'))"
                        qparams["dt_from"] = str(p["date_from"])[:10]
                    if p.get("date_to"):
                        sql += " AND TRUNC(a.CREATED_AT) <= TRUNC(TO_DATE(:dt_to, 'YYYY-MM-DD'))"
                        qparams["dt_to"] = str(p["date_to"])[:10]
                    sql += " ORDER BY a.CREATED_AT DESC"

                elif code == "PROGS_BY_BANK":
                    sql = """
                        SELECT pr.ID, pr.NAME, b.NAME AS BANK_NAME, pr.TERM_MONTHS, pr.RATE_PCT,
                               pr.MIN_SUM, pr.MAX_SUM, pr.ACTIVE,
                               (SELECT COUNT(*) FROM CRED_APPLICATIONS a WHERE a.PROGRAM_ID = pr.ID) AS APP_COUNT
                        FROM CRED_PROGRAMS pr
                        JOIN CRED_BANKS b ON pr.BANK_ID = b.ID
                        WHERE (:bid IS NULL OR pr.BANK_ID = :bid)
                        ORDER BY b.NAME, pr.TERM_MONTHS, pr.ID
                    """
                    bid = p.get("bank_id")
                    try:
                        qparams["bid"] = int(bid) if bid else None
                    except (TypeError, ValueError):
                        qparams["bid"] = None

                else:
                    return {"success": False, "error": f"Неизвестный отчёт: {code}", "data": []}

                res = db.execute_query(sql, qparams)
                if not res.get("success"):
                    return {"success": False, "error": res.get("message", "Ошибка запроса"), "data": []}
                cols = [c.upper() for c in (res.get("columns") or [])]
                rows = res.get("data") or []
                data = [dict(zip(cols, row)) for row in rows]
                return {"success": True, "data": CreditController._rows_to_list(data)}
        except Exception as e:
            return {"success": False, "error": str(e), "data": []}

    @staticmethod
    def get_report_by_id(report_id: int) -> Dict[str, Any]:
        """Получить отчёт по ID (включая TEMPLATE_HTML)."""
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    "SELECT ID, CODE, NAME, DESCRIPTION, TEMPLATE_TYPE, TEMPLATE_HTML, ENABLED FROM CRED_REPORTS WHERE ID = :rid",
                    {"rid": report_id},
                )
            if not r.get("success") or not r.get("data"):
                return {"success": False, "error": "Отчёт не найден", "data": None}
            cols = [c.upper() for c in (r.get("columns") or [])]
            row = r["data"][0]
            d = dict(zip(cols, row))
            return {"success": True, "data": CreditController._rows_to_list([d])[0]}
        except Exception as e:
            return {"success": False, "error": str(e), "data": None}

    @staticmethod
    def update_report_template(report_id: int, name: Optional[str] = None, description: Optional[str] = None, template_html: Optional[str] = None) -> Dict[str, Any]:
        """Обновить шаблон/метаданные отчёта."""
        try:
            with DatabaseModel() as db:
                updates = []
                params: Dict[str, Any] = {"rid": report_id}
                if name is not None:
                    updates.append("NAME = :name")
                    params["name"] = name
                if description is not None:
                    updates.append("DESCRIPTION = :desc")
                    params["desc"] = description
                if template_html is not None:
                    updates.append("TEMPLATE_HTML = :th")
                    params["th"] = template_html
                if not updates:
                    return {"success": True}
                sql = "UPDATE CRED_REPORTS SET " + ", ".join(updates) + ", UPDATED_AT = SYSTIMESTAMP WHERE ID = :rid"
                with db.connection.cursor() as cur:
                    cur.execute(sql, params)
                db.connection.commit()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
