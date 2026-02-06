"""
Контроллер Nufarul: админка и интерфейс оператора приёма заказов в зале.
Химчистка: заказы, услуги, статусы, печать штрихкодов.
"""
from typing import Dict, Any, List, Optional
import sys
import os

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from models.database import DatabaseModel


def _norm_rows(r: Dict[str, Any], keys_lower: bool = True) -> List[Dict[str, Any]]:
    """Преобразует result execute_query в список словарей с нижними ключами."""
    if not r.get("success") or not r.get("columns"):
        return []
    cols = [c.upper() for c in (r.get("columns") or [])]
    out = []
    for row in r.get("data") or []:
        d = dict(zip(cols, row))
        if keys_lower:
            d = {k.lower(): v for k, v in d.items() if k}
        out.append(d)
    return out


class NufarulController:
    """API для админки Nufarul и интерфейса оператора приёма заказов."""

    # ---------- Админка: услуги ----------

    # Порядок групп (как на странице заказов nufarul.com)
    GROUP_ORDER = (
        "delivery", "dry_cleaning", "carpets", "pillows_cleaning",
        "laundry", "leather_dyeing", "conditions", "silicone_pillows",
    )
    GROUP_LABELS_RU = {
        "delivery": "ДОСТАВКА ЗАКАЗОВ",
        "dry_cleaning": "ХИМЧИСТКА (текстиль, кожа, шубы, др.)",
        "carpets": "ХИМЧИСТКА КОВРОВ",
        "pillows_cleaning": "Химчистка подушек с заменой наперника",
        "laundry": "СТИРКА БЕЛЬЯ",
        "leather_dyeing": "КРАШЕНИЕ ИЗДЕЛИЙ ИЗ КОЖИ",
        "conditions": "Условия предоставления услуг химчистки и прачечной",
        "silicone_pillows": "ПРОДАЖА ПОДУШЕК ИЗ СИЛИКОНА (ПО ПРЕДВ. ЗАКАЗУ)",
    }
    GROUP_LABELS_RO = {
        "delivery": "LIVRAREA COMANDELOR",
        "dry_cleaning": "CURĂȚARE CHIMICĂ (textile, piele, blănuri, altele)",
        "carpets": "CURĂȚARE COVORE",
        "pillows_cleaning": "Curățare perne cu înlocuire față",
        "laundry": "SPĂLARE RĂFE",
        "leather_dyeing": "VOPSEALĂ ARTICOLE DIN PIELE",
        "conditions": "Condiții de prestare a serviciilor de curățare chimică și spălătorie",
        "silicone_pillows": "VÂNZARE PERNE DIN SILICON (LA COMANDA PREALABILĂ)",
    }
    GROUP_LABELS_EN = {
        "delivery": "ORDER DELIVERY",
        "dry_cleaning": "DRY CLEANING (textiles, leather, furs, etc.)",
        "carpets": "CARPET CLEANING",
        "pillows_cleaning": "Pillow cleaning with pillowcase replacement",
        "laundry": "LAUNDRY",
        "leather_dyeing": "LEATHER DYING",
        "conditions": "Terms of dry cleaning and laundry services",
        "silicone_pillows": "SILICONE PILLOW SALES (BY PRE-ORDER)",
    }

    @staticmethod
    def get_services(active_only: bool = False) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                order_cases = " ".join(
                    f"WHEN '{g}' THEN {i}" for i, g in enumerate(NufarulController.GROUP_ORDER)
                )
                order_sql = f" ORDER BY CASE NVL(SERVICE_GROUP, 'dry_cleaning') {order_cases} ELSE 99 END, NAME"
                params = {}
                where = " AND ACTIVE = 'Y'" if active_only else ""
                sql_with_en = f"""SELECT ID, NAME AS NAME_RU, NAME_RO, NAME_EN, PRICE, UNIT, ACTIVE, NOTES, CREATED_AT, SERVICE_GROUP
                         FROM NUF_SERVICES WHERE 1=1{where}{order_sql}"""
                try:
                    r = db.execute_query(sql_with_en, params)
                    rows = _norm_rows(r)
                except Exception as col_err:
                    err_msg = str(col_err).upper()
                    if "NAME_EN" in err_msg or "INVALID IDENTIFIER" in err_msg:
                        sql_no_en = f"""SELECT ID, NAME AS NAME_RU, NAME_RO, PRICE, UNIT, ACTIVE, NOTES, CREATED_AT, SERVICE_GROUP
                                 FROM NUF_SERVICES WHERE 1=1{where}{order_sql}"""
                        r = db.execute_query(sql_no_en, params)
                        rows = _norm_rows(r)
                        for row in rows:
                            row["name_en"] = None
                    else:
                        raise
                return {
                    "success": True,
                    "data": rows,
                    "group_labels_ru": NufarulController.GROUP_LABELS_RU,
                    "group_labels_ro": NufarulController.GROUP_LABELS_RO,
                    "group_labels_en": NufarulController.GROUP_LABELS_EN,
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "data": [],
                "group_labels_ru": {},
                "group_labels_ro": {},
                "group_labels_en": {},
            }

    @staticmethod
    def get_service_by_id(service_id: int) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                try:
                    r = db.execute_query(
                        "SELECT ID, NAME AS NAME_RU, NAME_RO, NAME_EN, PRICE, UNIT, ACTIVE, NOTES, SERVICE_GROUP FROM NUF_SERVICES WHERE ID = :id",
                        {"id": service_id},
                    )
                except Exception as col_err:
                    err_msg = str(col_err).upper()
                    if "NAME_EN" in err_msg or "INVALID IDENTIFIER" in err_msg:
                        r = db.execute_query(
                            "SELECT ID, NAME AS NAME_RU, NAME_RO, PRICE, UNIT, ACTIVE, NOTES, SERVICE_GROUP FROM NUF_SERVICES WHERE ID = :id",
                            {"id": service_id},
                        )
                    else:
                        raise
                rows = _norm_rows(r)
                data = rows[0] if rows else None
                if data and "name_en" not in data:
                    data["name_en"] = None
                return {"success": True, "data": data}
        except Exception as e:
            return {"success": False, "error": str(e), "data": None}

    @staticmethod
    def upsert_service(data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                sid = data.get("id") or 0
                name_ru = (data.get("name_ru") or data.get("name") or "").strip() or (data.get("name_ro") or "").strip() or (data.get("name_en") or "").strip() or "—"
                name_ro = (data.get("name_ro") or name_ru).strip()
                name_en = (data.get("name_en") or "").strip() or None
                price = float(data.get("price") or 0)
                unit = (data.get("unit") or "buc").strip() or "buc"
                active = "Y" if data.get("active", True) else "N"
                notes = (data.get("notes") or "").strip() or None
                service_group = (data.get("service_group") or data.get("serviceGroup") or "dry_cleaning").strip() or None
                def _run_upsert(with_en: bool) -> None:
                    if sid:
                        if with_en:
                            sql = """UPDATE NUF_SERVICES SET NAME = :name_ru, NAME_RO = :name_ro, NAME_EN = :name_en, PRICE = :price,
                                     UNIT = :unit, ACTIVE = :active, NOTES = :notes, SERVICE_GROUP = :service_group, UPDATED_AT = SYSTIMESTAMP
                                     WHERE ID = :id"""
                            db.execute_query(sql, {"id": sid, "name_ru": name_ru, "name_ro": name_ro, "name_en": name_en, "price": price, "unit": unit, "active": active, "notes": notes, "service_group": service_group})
                        else:
                            sql = """UPDATE NUF_SERVICES SET NAME = :name_ru, NAME_RO = :name_ro, PRICE = :price,
                                     UNIT = :unit, ACTIVE = :active, NOTES = :notes, SERVICE_GROUP = :service_group, UPDATED_AT = SYSTIMESTAMP
                                     WHERE ID = :id"""
                            db.execute_query(sql, {"id": sid, "name_ru": name_ru, "name_ro": name_ro, "price": price, "unit": unit, "active": active, "notes": notes, "service_group": service_group})
                    else:
                        if with_en:
                            sql = """INSERT INTO NUF_SERVICES (NAME, NAME_RO, NAME_EN, PRICE, UNIT, ACTIVE, NOTES, SERVICE_GROUP)
                                     VALUES (:name_ru, :name_ro, :name_en, :price, :unit, :active, :notes, :service_group)"""
                            db.execute_query(sql, {"name_ru": name_ru, "name_ro": name_ro, "name_en": name_en, "price": price, "unit": unit, "active": active, "notes": notes, "service_group": service_group})
                        else:
                            sql = """INSERT INTO NUF_SERVICES (NAME, NAME_RO, PRICE, UNIT, ACTIVE, NOTES, SERVICE_GROUP)
                                     VALUES (:name_ru, :name_ro, :price, :unit, :active, :notes, :service_group)"""
                            db.execute_query(sql, {"name_ru": name_ru, "name_ro": name_ro, "price": price, "unit": unit, "active": active, "notes": notes, "service_group": service_group})
                try:
                    _run_upsert(with_en=True)
                except Exception as col_err:
                    err_msg = str(col_err).upper()
                    if "NAME_EN" in err_msg or "INVALID IDENTIFIER" in err_msg:
                        _run_upsert(with_en=False)
                    else:
                        raise
                db.connection.commit()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def delete_service(service_id: int) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                db.execute_query("DELETE FROM NUF_SERVICES WHERE ID = :id", {"id": service_id})
                db.connection.commit()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ---------- Админка: статусы ----------

    @staticmethod
    def get_statuses() -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    "SELECT ID, CODE, NAME_RO, NAME_RU, SORT_ORDER FROM NUF_ORDER_STATUSES ORDER BY SORT_ORDER, ID"
                )
                return {"success": True, "data": _norm_rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e), "data": []}

    # ---------- Админка: заказы (список, фильтры) ----------

    @staticmethod
    def get_orders(
        status_id: Optional[int] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 200,
    ) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                sql = """
                    SELECT * FROM (
                        SELECT o.ID, o.ORDER_NUMBER, o.BARCODE, o.CLIENT_NAME, o.CLIENT_PHONE,
                               o.STATUS_ID, s.CODE AS STATUS_CODE, s.NAME_RO AS STATUS_NAME,
                               o.TOTAL_AMOUNT, o.NOTES, o.CREATED_AT
                        FROM NUF_ORDERS o
                        JOIN NUF_ORDER_STATUSES s ON s.ID = o.STATUS_ID
                        WHERE 1=1
                """
                params = {"lim": limit}
                if status_id is not None:
                    sql += " AND o.STATUS_ID = :status_id"
                    params["status_id"] = status_id
                if date_from:
                    sql += " AND TRUNC(o.CREATED_AT) >= TRUNC(TO_DATE(:dt_from, 'YYYY-MM-DD'))"
                    params["dt_from"] = str(date_from)[:10]
                if date_to:
                    sql += " AND TRUNC(o.CREATED_AT) <= TRUNC(TO_DATE(:dt_to, 'YYYY-MM-DD'))"
                    params["dt_to"] = str(date_to)[:10]
                if search and search.strip():
                    sql += " AND (UPPER(o.ORDER_NUMBER) LIKE '%' || UPPER(:search) || '%' OR UPPER(o.CLIENT_NAME) LIKE '%' || UPPER(:search) || '%' OR o.BARCODE = :search2)"
                    params["search"] = search.strip()
                    params["search2"] = search.strip()
                sql += " ORDER BY o.CREATED_AT DESC ) WHERE ROWNUM <= :lim"
                r = db.execute_query(sql, params)
                return {"success": True, "data": _norm_rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e), "data": []}

    @staticmethod
    def get_order_by_id(order_id: int) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    """SELECT o.ID, o.ORDER_NUMBER, o.BARCODE, o.CLIENT_NAME, o.CLIENT_PHONE,
                              o.STATUS_ID, s.CODE AS STATUS_CODE, s.NAME_RO AS STATUS_NAME,
                              o.TOTAL_AMOUNT, o.NOTES, o.CREATED_AT, o.UPDATED_AT
                       FROM NUF_ORDERS o
                       JOIN NUF_ORDER_STATUSES s ON s.ID = o.STATUS_ID
                       WHERE o.ID = :id""",
                    {"id": order_id},
                )
                rows = _norm_rows(r)
                order = rows[0] if rows else None
                if not order:
                    return {"success": False, "error": "Order not found", "data": None}
                # Позиции заказа
                r2 = db.execute_query(
                    """SELECT i.ID, i.SERVICE_ID, sv.NAME AS SERVICE_NAME, i.QTY, i.PRICE, i.AMOUNT, i.NOTES
                       FROM NUF_ORDER_ITEMS i
                       JOIN NUF_SERVICES sv ON sv.ID = i.SERVICE_ID
                       WHERE i.ORDER_ID = :oid ORDER BY i.ID""",
                    {"oid": order_id},
                )
                order["items"] = _norm_rows(r2)
                return {"success": True, "data": order}
        except Exception as e:
            return {"success": False, "error": str(e), "data": None}

    @staticmethod
    def get_order_by_barcode(barcode: str) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    "SELECT ID FROM NUF_ORDERS WHERE BARCODE = :barcode",
                    {"barcode": (barcode or "").strip()},
                )
                rows = r.get("data") or []
                if not rows:
                    return {"success": False, "error": "Order not found", "data": None}
                order_id = rows[0][0]
                return NufarulController.get_order_by_id(int(order_id))
        except Exception as e:
            return {"success": False, "error": str(e), "data": None}

    @staticmethod
    def update_order_status(order_id: int, status_id: int) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                db.execute_query(
                    "UPDATE NUF_ORDERS SET STATUS_ID = :sid, UPDATED_AT = SYSTIMESTAMP WHERE ID = :id",
                    {"id": order_id, "sid": status_id},
                )
                db.connection.commit()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ---------- Оператор: создание заказа ----------

    @staticmethod
    def create_order(
        client_name: str,
        client_phone: str,
        items: List[Dict[str, Any]],
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Создаёт заказ и позиции. Генерирует ORDER_NUMBER и BARCODE."""
        try:
            with DatabaseModel() as db:
                # Номер заказа: год + последовательность
                r_seq = db.execute_query(
                    "SELECT NUF_ORDER_NUM_SEQ.NEXTVAL AS NX FROM DUAL"
                )
                if not r_seq.get("success") or not r_seq.get("data"):
                    return {"success": False, "error": "Could not generate order number"}
                seq_val = r_seq["data"][0][0]
                r_yr = db.execute_query("SELECT TO_CHAR(SYSDATE,'YYYY') AS Y FROM DUAL")
                year = r_yr["data"][0][0] if r_yr.get("data") else "2026"
                order_number = f"{year}-{str(seq_val).zfill(5)}"
                barcode = order_number  # или отдельная генерация EAN/Code128

                # Статус "Принят"
                r_st = db.execute_query("SELECT ID FROM NUF_ORDER_STATUSES WHERE CODE = 'received'")
                if not r_st.get("data"):
                    return {"success": False, "error": "Status 'received' not found"}
                status_id = r_st["data"][0][0]

                total = 0
                for it in items:
                    qty = float(it.get("qty") or 1)
                    price = float(it.get("price") or 0)
                    total += qty * price

                db.execute_query(
                    """INSERT INTO NUF_ORDERS (ORDER_NUMBER, BARCODE, CLIENT_NAME, CLIENT_PHONE, STATUS_ID, TOTAL_AMOUNT, NOTES)
                       VALUES (:onum, :barcode, :cname, :cphone, :sid, :total, :notes)""",
                    {
                        "onum": order_number,
                        "barcode": barcode,
                        "cname": (client_name or "").strip(),
                        "cphone": (client_phone or "").strip(),
                        "sid": status_id,
                        "total": round(total, 2),
                        "notes": (notes or "").strip() or None,
                    },
                )
                r_oid = db.execute_query("SELECT ID FROM NUF_ORDERS WHERE ORDER_NUMBER = :onum", {"onum": order_number})
                order_id = r_oid["data"][0][0] if r_oid.get("data") else None
                if not order_id:
                    db.connection.rollback()
                    return {"success": False, "error": "Could not get new order ID"}

                for it in items:
                    service_id = int(it.get("service_id") or 0)
                    qty = float(it.get("qty") or 1)
                    price = float(it.get("price") or 0)
                    amount = round(qty * price, 2)
                    db.execute_query(
                        """INSERT INTO NUF_ORDER_ITEMS (ORDER_ID, SERVICE_ID, QTY, PRICE, AMOUNT)
                           VALUES (:oid, :sid, :qty, :price, :amount)""",
                        {"oid": order_id, "sid": service_id, "qty": qty, "price": price, "amount": amount},
                    )

                db.connection.commit()
                return {
                    "success": True,
                    "order_id": order_id,
                    "order_number": order_number,
                    "barcode": barcode,
                    "total_amount": round(total, 2),
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_recent_orders(limit: int = 20) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    """SELECT * FROM (
                        SELECT o.ID, o.ORDER_NUMBER, o.BARCODE, o.CLIENT_NAME, o.CLIENT_PHONE,
                               s.CODE AS STATUS_CODE, s.NAME_RO AS STATUS_NAME,
                               o.TOTAL_AMOUNT, o.CREATED_AT,
                               TO_CHAR(o.CREATED_AT, 'YYYY-MM-DD HH24:MI') AS CREATED_TIME
                        FROM NUF_ORDERS o
                        JOIN NUF_ORDER_STATUSES s ON s.ID = o.STATUS_ID
                        ORDER BY o.CREATED_AT DESC
                    ) WHERE ROWNUM <= :lim""",
                    {"lim": limit},
                )
                return {"success": True, "data": _norm_rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e), "data": []}

    # ---------- Отчётность (базовая) ----------

    @staticmethod
    def report_orders_by_day(date_from: Optional[str] = None, date_to: Optional[str] = None) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                sql = """
                    SELECT TRUNC(o.CREATED_AT) AS ORDER_DATE,
                           COUNT(*) AS CNT,
                           SUM(o.TOTAL_AMOUNT) AS TOTAL
                    FROM NUF_ORDERS o
                    WHERE 1=1
                """
                params = {}
                if date_from:
                    sql += " AND TRUNC(o.CREATED_AT) >= TRUNC(TO_DATE(:dt_from, 'YYYY-MM-DD'))"
                    params["dt_from"] = str(date_from)[:10]
                if date_to:
                    sql += " AND TRUNC(o.CREATED_AT) <= TRUNC(TO_DATE(:dt_to, 'YYYY-MM-DD'))"
                    params["dt_to"] = str(date_to)[:10]
                sql += " GROUP BY TRUNC(o.CREATED_AT) ORDER BY ORDER_DATE DESC"
                r = db.execute_query(sql, params)
                return {"success": True, "data": _norm_rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e), "data": []}
