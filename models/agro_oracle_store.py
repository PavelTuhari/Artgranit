"""AGRO module Oracle store — all AGRO_* table operations."""
from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN, ROUND_UP
from typing import Any, Dict, List, Optional

from models.database import DatabaseModel


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _norm_rows(r: Dict, keys_lower: bool = True) -> List[Dict]:
    """Convert {success, columns, data} to list of dicts."""
    if not r.get("success") or not r.get("data"):
        return []
    cols = r["columns"]
    if keys_lower:
        cols = [c.lower() for c in cols]
    return [dict(zip(cols, row)) for row in r["data"]]


_ALLOWED_TABLES = {
    "AGRO_SUPPLIERS",
    "AGRO_CUSTOMERS",
    "AGRO_WAREHOUSES",
    "AGRO_STORAGE_CELLS",
    "AGRO_ITEMS",
    "AGRO_PACKAGING_TYPES",
    "AGRO_VEHICLES",
    "AGRO_CURRENCIES",
    "AGRO_EXCHANGE_RATES",
    "AGRO_FORMULA_PARAMS",
    "AGRO_MODULE_CONFIG",
}


class AgroStore:
    """Master-data CRUD for 11 AGRO reference tables."""

    # ------------------------------------------------------------------
    # Generic private helpers (table name validated against whitelist)
    # ------------------------------------------------------------------

    @staticmethod
    def _get_all(
        table: str,
        active_only: bool = False,
        order_by: str = "ID",
    ) -> Dict[str, Any]:
        if table not in _ALLOWED_TABLES:
            return {"success": False, "error": f"Table {table} is not allowed"}
        try:
            with DatabaseModel() as db:
                sql = f"SELECT * FROM {table}"
                params: Dict[str, Any] = {}
                if active_only:
                    sql += " WHERE ACTIVE = :active"
                    params["active"] = "Y"
                sql += f" ORDER BY {order_by}"
                r = db.execute_query(sql, params or None)
                return {"success": True, "data": _norm_rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def _get_by_id(table: str, record_id: int) -> Dict[str, Any]:
        if table not in _ALLOWED_TABLES:
            return {"success": False, "error": f"Table {table} is not allowed"}
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    f"SELECT * FROM {table} WHERE ID = :id", {"id": record_id}
                )
                rows = _norm_rows(r)
                if rows:
                    return {"success": True, "data": rows[0]}
                return {"success": False, "error": "Not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def _delete(table: str, record_id: int) -> Dict[str, Any]:
        if table not in _ALLOWED_TABLES:
            return {"success": False, "error": f"Table {table} is not allowed"}
        try:
            with DatabaseModel() as db:
                db.execute_query(
                    f"DELETE FROM {table} WHERE ID = :id", {"id": record_id}
                )
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ==================================================================
    # 1. AGRO_SUPPLIERS
    # ==================================================================

    @staticmethod
    def get_suppliers(active_only: bool = False) -> Dict[str, Any]:
        return AgroStore._get_all("AGRO_SUPPLIERS", active_only, "NAME")

    @staticmethod
    def get_supplier(record_id: int) -> Dict[str, Any]:
        return AgroStore._get_by_id("AGRO_SUPPLIERS", record_id)

    @staticmethod
    def upsert_supplier(data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                params = {
                    "code": data.get("code"),
                    "name": data.get("name"),
                    "country": data.get("country"),
                    "tax_id": data.get("tax_id"),
                    "contact_phone": data.get("contact_phone"),
                    "contact_email": data.get("contact_email"),
                    "address": data.get("address"),
                    "active": data.get("active", "Y"),
                }
                if data.get("id"):
                    params["id"] = data["id"]
                    db.execute_query(
                        """UPDATE AGRO_SUPPLIERS
                              SET CODE = :code, NAME = :name, COUNTRY = :country,
                                  TAX_ID = :tax_id, CONTACT_PHONE = :contact_phone,
                                  CONTACT_EMAIL = :contact_email, ADDRESS = :address,
                                  ACTIVE = :active
                            WHERE ID = :id""",
                        params,
                    )
                else:
                    db.execute_query(
                        """INSERT INTO AGRO_SUPPLIERS
                                  (ID, CODE, NAME, COUNTRY, TAX_ID,
                                   CONTACT_PHONE, CONTACT_EMAIL, ADDRESS, ACTIVE)
                           VALUES (AGRO_SUPPLIERS_SEQ.NEXTVAL, :code, :name, :country, :tax_id,
                                   :contact_phone, :contact_email, :address, :active)""",
                        params,
                    )
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def delete_supplier(record_id: int) -> Dict[str, Any]:
        return AgroStore._delete("AGRO_SUPPLIERS", record_id)

    # ==================================================================
    # 2. AGRO_CUSTOMERS
    # ==================================================================

    @staticmethod
    def get_customers(active_only: bool = False) -> Dict[str, Any]:
        return AgroStore._get_all("AGRO_CUSTOMERS", active_only, "NAME")

    @staticmethod
    def get_customer(record_id: int) -> Dict[str, Any]:
        return AgroStore._get_by_id("AGRO_CUSTOMERS", record_id)

    @staticmethod
    def upsert_customer(data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                params = {
                    "code": data.get("code"),
                    "name": data.get("name"),
                    "country": data.get("country"),
                    "tax_id": data.get("tax_id"),
                    "contact_phone": data.get("contact_phone"),
                    "contact_email": data.get("contact_email"),
                    "address": data.get("address"),
                    "customer_type": data.get("customer_type", "domestic"),
                    "active": data.get("active", "Y"),
                }
                if data.get("id"):
                    params["id"] = data["id"]
                    db.execute_query(
                        """UPDATE AGRO_CUSTOMERS
                              SET CODE = :code, NAME = :name, COUNTRY = :country,
                                  TAX_ID = :tax_id, CONTACT_PHONE = :contact_phone,
                                  CONTACT_EMAIL = :contact_email, ADDRESS = :address,
                                  CUSTOMER_TYPE = :customer_type, ACTIVE = :active
                            WHERE ID = :id""",
                        params,
                    )
                else:
                    db.execute_query(
                        """INSERT INTO AGRO_CUSTOMERS
                                  (ID, CODE, NAME, COUNTRY, TAX_ID,
                                   CONTACT_PHONE, CONTACT_EMAIL, ADDRESS,
                                   CUSTOMER_TYPE, ACTIVE)
                           VALUES (AGRO_CUSTOMERS_SEQ.NEXTVAL, :code, :name, :country, :tax_id,
                                   :contact_phone, :contact_email, :address,
                                   :customer_type, :active)""",
                        params,
                    )
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def delete_customer(record_id: int) -> Dict[str, Any]:
        return AgroStore._delete("AGRO_CUSTOMERS", record_id)

    # ==================================================================
    # 3. AGRO_WAREHOUSES
    # ==================================================================

    @staticmethod
    def get_warehouses(active_only: bool = False) -> Dict[str, Any]:
        return AgroStore._get_all("AGRO_WAREHOUSES", active_only, "NAME")

    @staticmethod
    def get_warehouse(record_id: int) -> Dict[str, Any]:
        return AgroStore._get_by_id("AGRO_WAREHOUSES", record_id)

    @staticmethod
    def upsert_warehouse(data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                params = {
                    "code": data.get("code"),
                    "name": data.get("name"),
                    "warehouse_type": data.get("warehouse_type", "cold_storage"),
                    "address": data.get("address"),
                    "capacity_kg": data.get("capacity_kg"),
                    "active": data.get("active", "Y"),
                }
                if data.get("id"):
                    params["id"] = data["id"]
                    db.execute_query(
                        """UPDATE AGRO_WAREHOUSES
                              SET CODE = :code, NAME = :name,
                                  WAREHOUSE_TYPE = :warehouse_type,
                                  ADDRESS = :address, CAPACITY_KG = :capacity_kg,
                                  ACTIVE = :active
                            WHERE ID = :id""",
                        params,
                    )
                else:
                    db.execute_query(
                        """INSERT INTO AGRO_WAREHOUSES
                                  (ID, CODE, NAME, WAREHOUSE_TYPE, ADDRESS,
                                   CAPACITY_KG, ACTIVE)
                           VALUES (AGRO_WAREHOUSES_SEQ.NEXTVAL, :code, :name,
                                   :warehouse_type, :address, :capacity_kg, :active)""",
                        params,
                    )
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def delete_warehouse(record_id: int) -> Dict[str, Any]:
        return AgroStore._delete("AGRO_WAREHOUSES", record_id)

    # ==================================================================
    # 4. AGRO_STORAGE_CELLS
    # ==================================================================

    @staticmethod
    def get_storage_cells(active_only: bool = False) -> Dict[str, Any]:
        return AgroStore._get_all("AGRO_STORAGE_CELLS", active_only, "CODE")

    @staticmethod
    def get_storage_cell(record_id: int) -> Dict[str, Any]:
        return AgroStore._get_by_id("AGRO_STORAGE_CELLS", record_id)

    @staticmethod
    def get_storage_cells_by_warehouse(
        warehouse_id: int, active_only: bool = False
    ) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                sql = "SELECT * FROM AGRO_STORAGE_CELLS WHERE WAREHOUSE_ID = :warehouse_id"
                params: Dict[str, Any] = {"warehouse_id": warehouse_id}
                if active_only:
                    sql += " AND ACTIVE = :active"
                    params["active"] = "Y"
                sql += " ORDER BY CODE"
                r = db.execute_query(sql, params)
                return {"success": True, "data": _norm_rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def upsert_storage_cell(data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                params = {
                    "warehouse_id": data.get("warehouse_id"),
                    "code": data.get("code"),
                    "name": data.get("name"),
                    "cell_type": data.get("cell_type", "chamber"),
                    "temp_min": data.get("temp_min"),
                    "temp_max": data.get("temp_max"),
                    "humidity_min": data.get("humidity_min"),
                    "humidity_max": data.get("humidity_max"),
                    "capacity_kg": data.get("capacity_kg"),
                    "active": data.get("active", "Y"),
                }
                if data.get("id"):
                    params["id"] = data["id"]
                    db.execute_query(
                        """UPDATE AGRO_STORAGE_CELLS
                              SET WAREHOUSE_ID = :warehouse_id, CODE = :code,
                                  NAME = :name, CELL_TYPE = :cell_type,
                                  TEMP_MIN = :temp_min, TEMP_MAX = :temp_max,
                                  HUMIDITY_MIN = :humidity_min, HUMIDITY_MAX = :humidity_max,
                                  CAPACITY_KG = :capacity_kg, ACTIVE = :active
                            WHERE ID = :id""",
                        params,
                    )
                else:
                    db.execute_query(
                        """INSERT INTO AGRO_STORAGE_CELLS
                                  (ID, WAREHOUSE_ID, CODE, NAME, CELL_TYPE,
                                   TEMP_MIN, TEMP_MAX, HUMIDITY_MIN, HUMIDITY_MAX,
                                   CAPACITY_KG, ACTIVE)
                           VALUES (AGRO_STORAGE_CELLS_SEQ.NEXTVAL, :warehouse_id, :code,
                                   :name, :cell_type, :temp_min, :temp_max,
                                   :humidity_min, :humidity_max, :capacity_kg, :active)""",
                        params,
                    )
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def delete_storage_cell(record_id: int) -> Dict[str, Any]:
        return AgroStore._delete("AGRO_STORAGE_CELLS", record_id)

    # ==================================================================
    # 5. AGRO_ITEMS
    # ==================================================================

    @staticmethod
    def get_items(active_only: bool = False) -> Dict[str, Any]:
        return AgroStore._get_all("AGRO_ITEMS", active_only, "NAME_RU")

    @staticmethod
    def get_item(record_id: int) -> Dict[str, Any]:
        return AgroStore._get_by_id("AGRO_ITEMS", record_id)

    @staticmethod
    def upsert_item(data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                params = {
                    "code": data.get("code"),
                    "name_ru": data.get("name_ru"),
                    "name_ro": data.get("name_ro"),
                    "item_group": data.get("item_group", "fruit"),
                    "unit": data.get("unit", "kg"),
                    "default_tare_kg": data.get("default_tare_kg", 0),
                    "shelf_life_days": data.get("shelf_life_days"),
                    "optimal_temp_min": data.get("optimal_temp_min"),
                    "optimal_temp_max": data.get("optimal_temp_max"),
                    "active": data.get("active", "Y"),
                }
                if data.get("id"):
                    params["id"] = data["id"]
                    db.execute_query(
                        """UPDATE AGRO_ITEMS
                              SET CODE = :code, NAME_RU = :name_ru, NAME_RO = :name_ro,
                                  ITEM_GROUP = :item_group, UNIT = :unit,
                                  DEFAULT_TARE_KG = :default_tare_kg,
                                  SHELF_LIFE_DAYS = :shelf_life_days,
                                  OPTIMAL_TEMP_MIN = :optimal_temp_min,
                                  OPTIMAL_TEMP_MAX = :optimal_temp_max,
                                  ACTIVE = :active
                            WHERE ID = :id""",
                        params,
                    )
                else:
                    db.execute_query(
                        """INSERT INTO AGRO_ITEMS
                                  (ID, CODE, NAME_RU, NAME_RO, ITEM_GROUP, UNIT,
                                   DEFAULT_TARE_KG, SHELF_LIFE_DAYS,
                                   OPTIMAL_TEMP_MIN, OPTIMAL_TEMP_MAX, ACTIVE)
                           VALUES (AGRO_ITEMS_SEQ.NEXTVAL, :code, :name_ru, :name_ro,
                                   :item_group, :unit, :default_tare_kg,
                                   :shelf_life_days, :optimal_temp_min,
                                   :optimal_temp_max, :active)""",
                        params,
                    )
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def delete_item(record_id: int) -> Dict[str, Any]:
        return AgroStore._delete("AGRO_ITEMS", record_id)

    # ==================================================================
    # 6. AGRO_PACKAGING_TYPES
    # ==================================================================

    @staticmethod
    def get_packaging_types(active_only: bool = False) -> Dict[str, Any]:
        return AgroStore._get_all("AGRO_PACKAGING_TYPES", active_only, "NAME_RU")

    @staticmethod
    def get_packaging_type(record_id: int) -> Dict[str, Any]:
        return AgroStore._get_by_id("AGRO_PACKAGING_TYPES", record_id)

    @staticmethod
    def upsert_packaging_type(data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                params = {
                    "code": data.get("code"),
                    "name_ru": data.get("name_ru"),
                    "name_ro": data.get("name_ro"),
                    "tare_weight_kg": data.get("tare_weight_kg", 0),
                    "capacity_kg": data.get("capacity_kg"),
                    "active": data.get("active", "Y"),
                }
                if data.get("id"):
                    params["id"] = data["id"]
                    db.execute_query(
                        """UPDATE AGRO_PACKAGING_TYPES
                              SET CODE = :code, NAME_RU = :name_ru, NAME_RO = :name_ro,
                                  TARE_WEIGHT_KG = :tare_weight_kg,
                                  CAPACITY_KG = :capacity_kg, ACTIVE = :active
                            WHERE ID = :id""",
                        params,
                    )
                else:
                    db.execute_query(
                        """INSERT INTO AGRO_PACKAGING_TYPES
                                  (ID, CODE, NAME_RU, NAME_RO,
                                   TARE_WEIGHT_KG, CAPACITY_KG, ACTIVE)
                           VALUES (AGRO_PACKAGING_TYPES_SEQ.NEXTVAL, :code, :name_ru,
                                   :name_ro, :tare_weight_kg, :capacity_kg, :active)""",
                        params,
                    )
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def delete_packaging_type(record_id: int) -> Dict[str, Any]:
        return AgroStore._delete("AGRO_PACKAGING_TYPES", record_id)

    # ==================================================================
    # 7. AGRO_VEHICLES
    # ==================================================================

    @staticmethod
    def get_vehicles(active_only: bool = False) -> Dict[str, Any]:
        return AgroStore._get_all("AGRO_VEHICLES", active_only, "PLATE_NUMBER")

    @staticmethod
    def get_vehicle(record_id: int) -> Dict[str, Any]:
        return AgroStore._get_by_id("AGRO_VEHICLES", record_id)

    @staticmethod
    def upsert_vehicle(data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                params = {
                    "plate_number": data.get("plate_number"),
                    "vehicle_type": data.get("vehicle_type", "truck"),
                    "driver_name": data.get("driver_name"),
                    "active": data.get("active", "Y"),
                }
                if data.get("id"):
                    params["id"] = data["id"]
                    db.execute_query(
                        """UPDATE AGRO_VEHICLES
                              SET PLATE_NUMBER = :plate_number,
                                  VEHICLE_TYPE = :vehicle_type,
                                  DRIVER_NAME = :driver_name, ACTIVE = :active
                            WHERE ID = :id""",
                        params,
                    )
                else:
                    db.execute_query(
                        """INSERT INTO AGRO_VEHICLES
                                  (ID, PLATE_NUMBER, VEHICLE_TYPE, DRIVER_NAME, ACTIVE)
                           VALUES (AGRO_VEHICLES_SEQ.NEXTVAL, :plate_number,
                                   :vehicle_type, :driver_name, :active)""",
                        params,
                    )
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def delete_vehicle(record_id: int) -> Dict[str, Any]:
        return AgroStore._delete("AGRO_VEHICLES", record_id)

    # ==================================================================
    # 8. AGRO_CURRENCIES
    # ==================================================================

    @staticmethod
    def get_currencies(active_only: bool = False) -> Dict[str, Any]:
        return AgroStore._get_all("AGRO_CURRENCIES", active_only, "CODE")

    @staticmethod
    def get_currency(record_id: int) -> Dict[str, Any]:
        return AgroStore._get_by_id("AGRO_CURRENCIES", record_id)

    @staticmethod
    def upsert_currency(data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                params = {
                    "code": data.get("code"),
                    "name": data.get("name"),
                    "symbol": data.get("symbol"),
                    "active": data.get("active", "Y"),
                }
                if data.get("id"):
                    params["id"] = data["id"]
                    db.execute_query(
                        """UPDATE AGRO_CURRENCIES
                              SET CODE = :code, NAME = :name, SYMBOL = :symbol,
                                  ACTIVE = :active
                            WHERE ID = :id""",
                        params,
                    )
                else:
                    db.execute_query(
                        """INSERT INTO AGRO_CURRENCIES
                                  (ID, CODE, NAME, SYMBOL, ACTIVE)
                           VALUES (AGRO_CURRENCIES_SEQ.NEXTVAL, :code, :name,
                                   :symbol, :active)""",
                        params,
                    )
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def delete_currency(record_id: int) -> Dict[str, Any]:
        return AgroStore._delete("AGRO_CURRENCIES", record_id)

    # ==================================================================
    # 9. AGRO_EXCHANGE_RATES  (no ACTIVE column)
    # ==================================================================

    @staticmethod
    def get_exchange_rates(
        from_currency: Optional[str] = None,
        to_currency: Optional[str] = None,
        rate_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return exchange rates with optional filters.

        ``rate_date`` format: ``YYYY-MM-DD``.
        """
        try:
            with DatabaseModel() as db:
                sql = "SELECT * FROM AGRO_EXCHANGE_RATES WHERE 1=1"
                params: Dict[str, Any] = {}
                if from_currency:
                    sql += " AND FROM_CURRENCY = :from_currency"
                    params["from_currency"] = from_currency
                if to_currency:
                    sql += " AND TO_CURRENCY = :to_currency"
                    params["to_currency"] = to_currency
                if rate_date:
                    sql += " AND RATE_DATE = TO_DATE(:rate_date, 'YYYY-MM-DD')"
                    params["rate_date"] = rate_date
                sql += " ORDER BY RATE_DATE DESC, ID DESC"
                r = db.execute_query(sql, params or None)
                return {"success": True, "data": _norm_rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_exchange_rate(record_id: int) -> Dict[str, Any]:
        return AgroStore._get_by_id("AGRO_EXCHANGE_RATES", record_id)

    @staticmethod
    def upsert_exchange_rate(data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                params = {
                    "from_currency": data.get("from_currency"),
                    "to_currency": data.get("to_currency"),
                    "rate": data.get("rate"),
                    "rate_date": data.get("rate_date"),
                    "source": data.get("source"),
                }
                if data.get("id"):
                    params["id"] = data["id"]
                    db.execute_query(
                        """UPDATE AGRO_EXCHANGE_RATES
                              SET FROM_CURRENCY = :from_currency,
                                  TO_CURRENCY = :to_currency,
                                  RATE = :rate,
                                  RATE_DATE = TO_DATE(:rate_date, 'YYYY-MM-DD'),
                                  SOURCE = :source
                            WHERE ID = :id""",
                        params,
                    )
                else:
                    db.execute_query(
                        """INSERT INTO AGRO_EXCHANGE_RATES
                                  (ID, FROM_CURRENCY, TO_CURRENCY, RATE, RATE_DATE, SOURCE)
                           VALUES (AGRO_EXCHANGE_RATES_SEQ.NEXTVAL, :from_currency,
                                   :to_currency, :rate,
                                   TO_DATE(:rate_date, 'YYYY-MM-DD'), :source)""",
                        params,
                    )
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def delete_exchange_rate(record_id: int) -> Dict[str, Any]:
        return AgroStore._delete("AGRO_EXCHANGE_RATES", record_id)

    # ==================================================================
    # 10. AGRO_FORMULA_PARAMS  (ITEM_ID nullable — NULL = global default)
    # ==================================================================

    @staticmethod
    def get_formula_params(
        active_only: bool = False, item_id: Optional[int] = None
    ) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                sql = "SELECT * FROM AGRO_FORMULA_PARAMS WHERE 1=1"
                params: Dict[str, Any] = {}
                if active_only:
                    sql += " AND ACTIVE = :active"
                    params["active"] = "Y"
                if item_id is not None:
                    sql += " AND ITEM_ID = :item_id"
                    params["item_id"] = item_id
                sql += " ORDER BY PARAM_NAME"
                r = db.execute_query(sql, params or None)
                return {"success": True, "data": _norm_rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_formula_param(record_id: int) -> Dict[str, Any]:
        return AgroStore._get_by_id("AGRO_FORMULA_PARAMS", record_id)

    @staticmethod
    def upsert_formula_param(data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                params = {
                    "item_id": data.get("item_id"),
                    "param_name": data.get("param_name"),
                    "param_value": data.get("param_value"),
                    "active": data.get("active", "Y"),
                }
                if data.get("id"):
                    params["id"] = data["id"]
                    db.execute_query(
                        """UPDATE AGRO_FORMULA_PARAMS
                              SET ITEM_ID = :item_id, PARAM_NAME = :param_name,
                                  PARAM_VALUE = :param_value, ACTIVE = :active
                            WHERE ID = :id""",
                        params,
                    )
                else:
                    db.execute_query(
                        """INSERT INTO AGRO_FORMULA_PARAMS
                                  (ID, ITEM_ID, PARAM_NAME, PARAM_VALUE, ACTIVE)
                           VALUES (AGRO_FORMULA_PARAMS_SEQ.NEXTVAL, :item_id,
                                   :param_name, :param_value, :active)""",
                        params,
                    )
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def delete_formula_param(record_id: int) -> Dict[str, Any]:
        return AgroStore._delete("AGRO_FORMULA_PARAMS", record_id)

    # ==================================================================
    # 11. AGRO_MODULE_CONFIG  (no ACTIVE column)
    # ==================================================================

    @staticmethod
    def get_module_configs(config_group: Optional[str] = None) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                sql = "SELECT * FROM AGRO_MODULE_CONFIG"
                params: Dict[str, Any] = {}
                if config_group:
                    sql += " WHERE CONFIG_GROUP = :config_group"
                    params["config_group"] = config_group
                sql += " ORDER BY CONFIG_KEY"
                r = db.execute_query(sql, params or None)
                return {"success": True, "data": _norm_rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_module_config(record_id: int) -> Dict[str, Any]:
        return AgroStore._get_by_id("AGRO_MODULE_CONFIG", record_id)

    @staticmethod
    def get_module_config_by_key(config_key: str) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    "SELECT * FROM AGRO_MODULE_CONFIG WHERE CONFIG_KEY = :config_key",
                    {"config_key": config_key},
                )
                rows = _norm_rows(r)
                if rows:
                    return {"success": True, "data": rows[0]}
                return {"success": False, "error": "Not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def upsert_module_config(data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                params = {
                    "config_key": data.get("config_key"),
                    "config_value": data.get("config_value"),
                    "config_group": data.get("config_group"),
                    "description": data.get("description"),
                }
                if data.get("id"):
                    params["id"] = data["id"]
                    db.execute_query(
                        """UPDATE AGRO_MODULE_CONFIG
                              SET CONFIG_KEY = :config_key, CONFIG_VALUE = :config_value,
                                  CONFIG_GROUP = :config_group, DESCRIPTION = :description
                            WHERE ID = :id""",
                        params,
                    )
                else:
                    db.execute_query(
                        """INSERT INTO AGRO_MODULE_CONFIG
                                  (ID, CONFIG_KEY, CONFIG_VALUE, CONFIG_GROUP, DESCRIPTION)
                           VALUES (AGRO_MODULE_CONFIG_SEQ.NEXTVAL, :config_key,
                                   :config_value, :config_group, :description)""",
                        params,
                    )
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def delete_module_config(record_id: int) -> Dict[str, Any]:
        return AgroStore._delete("AGRO_MODULE_CONFIG", record_id)

    # ==================================================================
    # 12. Barcode & Crate Operations
    # ==================================================================

    @staticmethod
    def generate_barcodes(
        count: int, barcode_type: str = "internal"
    ) -> Dict[str, Any]:
        """Generate *count* barcodes with format AGRO-YYYYMMDD-NNNNNN."""
        try:
            with DatabaseModel() as db:
                today_str = datetime.now().strftime("%Y%m%d")
                barcodes: List[str] = []
                for _ in range(count):
                    # Get next sequence value
                    r = db.execute_query(
                        "SELECT AGRO_BARCODES_SEQ.NEXTVAL AS SEQ_VAL FROM DUAL",
                        None,
                    )
                    rows = _norm_rows(r)
                    seq_val = int(rows[0]["seq_val"])
                    barcode = f"AGRO-{today_str}-{seq_val:06d}"
                    db.execute_query(
                        """INSERT INTO AGRO_BARCODES
                                  (ID, BARCODE, BARCODE_TYPE, PRINTED, ASSIGNED)
                           VALUES (:id, :barcode, :barcode_type, 'N', 'N')""",
                        {
                            "id": seq_val,
                            "barcode": barcode,
                            "barcode_type": barcode_type,
                        },
                    )
                    barcodes.append(barcode)
                db.connection.commit()
                return {"success": True, "data": barcodes}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_barcode_print_batch(
        barcode_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """Return barcodes for label printing and mark them as PRINTED."""
        try:
            with DatabaseModel() as db:
                if barcode_ids:
                    # Build bind-variable list for IN clause
                    binds: Dict[str, Any] = {}
                    placeholders = []
                    for idx, bid in enumerate(barcode_ids):
                        key = f"id_{idx}"
                        binds[key] = bid
                        placeholders.append(f":{key}")
                    in_clause = ", ".join(placeholders)
                    sql = f"SELECT * FROM AGRO_BARCODES WHERE ID IN ({in_clause}) ORDER BY ID"
                    r = db.execute_query(sql, binds)
                else:
                    r = db.execute_query(
                        "SELECT * FROM AGRO_BARCODES WHERE PRINTED = :printed ORDER BY ID",
                        {"printed": "N"},
                    )
                rows = _norm_rows(r)
                # Mark as printed
                if barcode_ids:
                    binds_upd: Dict[str, Any] = {}
                    ph_upd = []
                    for idx, bid in enumerate(barcode_ids):
                        key = f"id_{idx}"
                        binds_upd[key] = bid
                        ph_upd.append(f":{key}")
                    in_upd = ", ".join(ph_upd)
                    db.execute_query(
                        f"UPDATE AGRO_BARCODES SET PRINTED = 'Y' WHERE ID IN ({in_upd})",
                        binds_upd,
                    )
                else:
                    db.execute_query(
                        "UPDATE AGRO_BARCODES SET PRINTED = 'Y' WHERE PRINTED = :printed",
                        {"printed": "N"},
                    )
                db.connection.commit()
                return {"success": True, "data": rows}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def scan_crate(barcode: str) -> Dict[str, Any]:
        """Look up barcode and return associated crate data if any."""
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    """SELECT b.ID AS BARCODE_ID, b.BARCODE, b.BARCODE_TYPE,
                              b.PRINTED, b.ASSIGNED, b.BATCH_ID,
                              c.ID AS CRATE_ID, c.EXTERNAL_BARCODE,
                              c.PACKAGING_TYPE_ID, c.GROSS_WEIGHT_KG,
                              c.TARE_WEIGHT_KG, c.NET_WEIGHT_KG, c.STATUS
                       FROM AGRO_BARCODES b
                       LEFT JOIN AGRO_CRATES c ON c.BARCODE_ID = b.ID
                       WHERE b.BARCODE = :barcode""",
                    {"barcode": barcode},
                )
                rows = _norm_rows(r)
                if rows:
                    return {"success": True, "data": rows[0]}
                # Try external barcode on crates
                r2 = db.execute_query(
                    """SELECT c.ID AS CRATE_ID, c.BARCODE_ID, c.EXTERNAL_BARCODE,
                              c.PACKAGING_TYPE_ID, c.GROSS_WEIGHT_KG,
                              c.TARE_WEIGHT_KG, c.NET_WEIGHT_KG, c.STATUS
                       FROM AGRO_CRATES c
                       WHERE c.EXTERNAL_BARCODE = :barcode""",
                    {"barcode": barcode},
                )
                rows2 = _norm_rows(r2)
                if rows2:
                    return {"success": True, "data": rows2[0]}
                return {"success": True, "data": None, "message": "New barcode"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def register_crate(data: Dict[str, Any]) -> Dict[str, Any]:
        """Register a new crate with optional barcode assignment."""
        try:
            with DatabaseModel() as db:
                gross = data.get("gross_weight_kg")
                tare = data.get("tare_weight_kg")
                net = data.get("net_weight_kg")
                if gross is not None and tare is not None and net is None:
                    net = float(gross) - float(tare)
                params = {
                    "barcode_id": data.get("barcode_id"),
                    "external_barcode": data.get("external_barcode"),
                    "packaging_type_id": data.get("packaging_type_id"),
                    "gross_weight_kg": gross,
                    "tare_weight_kg": tare,
                    "net_weight_kg": net,
                    "status": data.get("status", "empty"),
                }
                db.execute_query(
                    """INSERT INTO AGRO_CRATES
                              (ID, BARCODE_ID, EXTERNAL_BARCODE, PACKAGING_TYPE_ID,
                               GROSS_WEIGHT_KG, TARE_WEIGHT_KG, NET_WEIGHT_KG, STATUS)
                       VALUES (AGRO_CRATES_SEQ.NEXTVAL, :barcode_id, :external_barcode,
                               :packaging_type_id, :gross_weight_kg, :tare_weight_kg,
                               :net_weight_kg, :status)""",
                    params,
                )
                # Mark barcode as assigned if provided
                if data.get("barcode_id"):
                    db.execute_query(
                        "UPDATE AGRO_BARCODES SET ASSIGNED = 'Y' WHERE ID = :id",
                        {"id": data["barcode_id"]},
                    )
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ==================================================================
    # 13. Purchase Documents & Batches
    # ==================================================================

    @staticmethod
    def get_purchases(
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Query AGRO_V_PURCHASES with optional filters."""
        try:
            with DatabaseModel() as db:
                sql = "SELECT * FROM AGRO_V_PURCHASES WHERE 1=1"
                params: Dict[str, Any] = {}
                if filters:
                    if filters.get("date_from"):
                        sql += " AND DOC_DATE >= TO_DATE(:date_from, 'YYYY-MM-DD')"
                        params["date_from"] = filters["date_from"]
                    if filters.get("date_to"):
                        sql += " AND DOC_DATE <= TO_DATE(:date_to, 'YYYY-MM-DD')"
                        params["date_to"] = filters["date_to"]
                    if filters.get("supplier_id"):
                        sql += " AND DOC_ID IN (SELECT ID FROM AGRO_PURCHASE_DOCS WHERE SUPPLIER_ID = :supplier_id)"
                        params["supplier_id"] = filters["supplier_id"]
                    if filters.get("status"):
                        sql += " AND STATUS = :status"
                        params["status"] = filters["status"]
                sql += " ORDER BY DOC_DATE DESC, DOC_ID DESC"
                r = db.execute_query(sql, params or None)
                return {"success": True, "data": _norm_rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_purchase_by_id(doc_id: int) -> Dict[str, Any]:
        """Get purchase header with JOINed names and all lines."""
        try:
            with DatabaseModel() as db:
                # Header
                rh = db.execute_query(
                    """SELECT pd.*,
                              s.NAME   AS SUPPLIER_NAME,
                              w.NAME   AS WAREHOUSE_NAME,
                              v.PLATE_NUMBER AS VEHICLE_PLATE,
                              cur.CODE AS CURRENCY_CODE
                       FROM AGRO_PURCHASE_DOCS pd
                       JOIN AGRO_SUPPLIERS       s   ON s.ID   = pd.SUPPLIER_ID
                       JOIN AGRO_WAREHOUSES      w   ON w.ID   = pd.WAREHOUSE_ID
                       LEFT JOIN AGRO_VEHICLES   v   ON v.ID   = pd.VEHICLE_ID
                       LEFT JOIN AGRO_CURRENCIES cur ON cur.ID = pd.CURRENCY_ID
                       WHERE pd.ID = :doc_id""",
                    {"doc_id": doc_id},
                )
                headers = _norm_rows(rh)
                if not headers:
                    return {"success": False, "error": "Purchase document not found"}
                # Lines
                rl = db.execute_query(
                    """SELECT pl.*,
                              i.NAME_RU AS ITEM_NAME_RU,
                              i.NAME_RO AS ITEM_NAME_RO,
                              i.CODE    AS ITEM_CODE
                       FROM AGRO_PURCHASE_LINES pl
                       JOIN AGRO_ITEMS i ON i.ID = pl.ITEM_ID
                       WHERE pl.PURCHASE_DOC_ID = :doc_id
                       ORDER BY pl.ID""",
                    {"doc_id": doc_id},
                )
                lines = _norm_rows(rl)
                return {
                    "success": True,
                    "data": {"header": headers[0], "lines": lines},
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def _calc_line_net_amount(line: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate NET_WEIGHT_KG and AMOUNT for a purchase line."""
        gross = line.get("gross_weight_kg")
        tare = line.get("tare_weight_kg")
        net = line.get("net_weight_kg")
        price = line.get("price_per_kg")
        if gross is not None and tare is not None and net is None:
            net = float(gross) - float(tare)
        amount = line.get("amount")
        if net is not None and price is not None and amount is None:
            amount = round(float(net) * float(price), 2)
        return {**line, "net_weight_kg": net, "amount": amount}

    @staticmethod
    def create_purchase(data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert purchase header + lines, calculating totals."""
        try:
            with DatabaseModel() as db:
                lines_raw = data.get("lines", [])
                lines = [AgroStore._calc_line_net_amount(ln) for ln in lines_raw]

                total_gross = sum(
                    float(ln.get("gross_weight_kg") or 0) for ln in lines
                )
                total_net = sum(
                    float(ln.get("net_weight_kg") or 0) for ln in lines
                )
                total_amount = sum(
                    float(ln.get("amount") or 0) for ln in lines
                )

                # Get next doc ID
                r_seq = db.execute_query(
                    "SELECT AGRO_PURCHASE_DOCS_SEQ.NEXTVAL AS SEQ_VAL FROM DUAL",
                    None,
                )
                doc_id = int(_norm_rows(r_seq)[0]["seq_val"])

                hdr_params = {
                    "id": doc_id,
                    "doc_number": data.get("doc_number"),
                    "doc_date": data.get("doc_date"),
                    "supplier_id": data.get("supplier_id"),
                    "warehouse_id": data.get("warehouse_id"),
                    "vehicle_id": data.get("vehicle_id"),
                    "currency_id": data.get("currency_id"),
                    "status": data.get("status", "draft"),
                    "total_gross_kg": total_gross,
                    "total_net_kg": total_net,
                    "total_amount": total_amount,
                    "advance_amount": data.get("advance_amount", 0),
                    "transfer_amount": data.get("transfer_amount", 0),
                    "e_factura_ref": data.get("e_factura_ref"),
                    "additional_costs": data.get("additional_costs", 0),
                    "notes": data.get("notes"),
                    "created_by": data.get("created_by"),
                }
                db.execute_query(
                    """INSERT INTO AGRO_PURCHASE_DOCS
                              (ID, DOC_NUMBER, DOC_DATE, SUPPLIER_ID, WAREHOUSE_ID,
                               VEHICLE_ID, CURRENCY_ID, STATUS,
                               TOTAL_GROSS_KG, TOTAL_NET_KG, TOTAL_AMOUNT,
                               ADVANCE_AMOUNT, TRANSFER_AMOUNT, E_FACTURA_REF,
                               ADDITIONAL_COSTS, NOTES, CREATED_BY)
                       VALUES (:id, :doc_number, TO_DATE(:doc_date, 'YYYY-MM-DD'),
                               :supplier_id, :warehouse_id,
                               :vehicle_id, :currency_id, :status,
                               :total_gross_kg, :total_net_kg, :total_amount,
                               :advance_amount, :transfer_amount, :e_factura_ref,
                               :additional_costs, :notes, :created_by)""",
                    hdr_params,
                )

                for ln in lines:
                    db.execute_query(
                        """INSERT INTO AGRO_PURCHASE_LINES
                                  (ID, PURCHASE_DOC_ID, ITEM_ID, PALLETS,
                                   CRATES_COUNT, GROSS_WEIGHT_KG, TARE_WEIGHT_KG,
                                   NET_WEIGHT_KG, PRICE_PER_KG, AMOUNT, NOTES)
                           VALUES (AGRO_PURCHASE_LINES_SEQ.NEXTVAL, :purchase_doc_id,
                                   :item_id, :pallets, :crates_count,
                                   :gross_weight_kg, :tare_weight_kg,
                                   :net_weight_kg, :price_per_kg, :amount, :notes)""",
                        {
                            "purchase_doc_id": doc_id,
                            "item_id": ln.get("item_id"),
                            "pallets": ln.get("pallets", 0),
                            "crates_count": ln.get("crates_count", 0),
                            "gross_weight_kg": ln.get("gross_weight_kg"),
                            "tare_weight_kg": ln.get("tare_weight_kg"),
                            "net_weight_kg": ln.get("net_weight_kg"),
                            "price_per_kg": ln.get("price_per_kg"),
                            "amount": ln.get("amount"),
                            "notes": ln.get("notes"),
                        },
                    )
                db.connection.commit()
                return {"success": True, "data": {"doc_id": doc_id}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def update_purchase(data: Dict[str, Any]) -> Dict[str, Any]:
        """Update purchase header, delete old lines, insert new lines."""
        try:
            with DatabaseModel() as db:
                doc_id = data["id"]
                lines_raw = data.get("lines", [])
                lines = [AgroStore._calc_line_net_amount(ln) for ln in lines_raw]

                total_gross = sum(
                    float(ln.get("gross_weight_kg") or 0) for ln in lines
                )
                total_net = sum(
                    float(ln.get("net_weight_kg") or 0) for ln in lines
                )
                total_amount = sum(
                    float(ln.get("amount") or 0) for ln in lines
                )

                hdr_params = {
                    "id": doc_id,
                    "doc_number": data.get("doc_number"),
                    "doc_date": data.get("doc_date"),
                    "supplier_id": data.get("supplier_id"),
                    "warehouse_id": data.get("warehouse_id"),
                    "vehicle_id": data.get("vehicle_id"),
                    "currency_id": data.get("currency_id"),
                    "total_gross_kg": total_gross,
                    "total_net_kg": total_net,
                    "total_amount": total_amount,
                    "advance_amount": data.get("advance_amount", 0),
                    "transfer_amount": data.get("transfer_amount", 0),
                    "e_factura_ref": data.get("e_factura_ref"),
                    "additional_costs": data.get("additional_costs", 0),
                    "notes": data.get("notes"),
                }
                db.execute_query(
                    """UPDATE AGRO_PURCHASE_DOCS
                          SET DOC_NUMBER = :doc_number,
                              DOC_DATE = TO_DATE(:doc_date, 'YYYY-MM-DD'),
                              SUPPLIER_ID = :supplier_id,
                              WAREHOUSE_ID = :warehouse_id,
                              VEHICLE_ID = :vehicle_id,
                              CURRENCY_ID = :currency_id,
                              TOTAL_GROSS_KG = :total_gross_kg,
                              TOTAL_NET_KG = :total_net_kg,
                              TOTAL_AMOUNT = :total_amount,
                              ADVANCE_AMOUNT = :advance_amount,
                              TRANSFER_AMOUNT = :transfer_amount,
                              E_FACTURA_REF = :e_factura_ref,
                              ADDITIONAL_COSTS = :additional_costs,
                              NOTES = :notes
                        WHERE ID = :id""",
                    hdr_params,
                )

                # Delete old lines (CASCADE would handle batches only if not yet created)
                db.execute_query(
                    "DELETE FROM AGRO_PURCHASE_LINES WHERE PURCHASE_DOC_ID = :doc_id",
                    {"doc_id": doc_id},
                )

                for ln in lines:
                    db.execute_query(
                        """INSERT INTO AGRO_PURCHASE_LINES
                                  (ID, PURCHASE_DOC_ID, ITEM_ID, PALLETS,
                                   CRATES_COUNT, GROSS_WEIGHT_KG, TARE_WEIGHT_KG,
                                   NET_WEIGHT_KG, PRICE_PER_KG, AMOUNT, NOTES)
                           VALUES (AGRO_PURCHASE_LINES_SEQ.NEXTVAL, :purchase_doc_id,
                                   :item_id, :pallets, :crates_count,
                                   :gross_weight_kg, :tare_weight_kg,
                                   :net_weight_kg, :price_per_kg, :amount, :notes)""",
                        {
                            "purchase_doc_id": doc_id,
                            "item_id": ln.get("item_id"),
                            "pallets": ln.get("pallets", 0),
                            "crates_count": ln.get("crates_count", 0),
                            "gross_weight_kg": ln.get("gross_weight_kg"),
                            "tare_weight_kg": ln.get("tare_weight_kg"),
                            "net_weight_kg": ln.get("net_weight_kg"),
                            "price_per_kg": ln.get("price_per_kg"),
                            "amount": ln.get("amount"),
                            "notes": ln.get("notes"),
                        },
                    )
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def confirm_purchase(doc_id: int) -> Dict[str, Any]:
        """Validate and confirm a purchase document, creating batches and stock movements."""
        try:
            with DatabaseModel() as db:
                # --- Load header ---
                rh = db.execute_query(
                    "SELECT * FROM AGRO_PURCHASE_DOCS WHERE ID = :doc_id",
                    {"doc_id": doc_id},
                )
                headers = _norm_rows(rh)
                if not headers:
                    return {"success": False, "error": "Document not found"}
                hdr = headers[0]

                if hdr.get("status") != "draft":
                    return {
                        "success": False,
                        "error": f"Cannot confirm document with status '{hdr.get('status')}'",
                    }

                # --- Validation ---
                errors: List[str] = []
                if not hdr.get("doc_date"):
                    errors.append("DOC_DATE is required")
                if not hdr.get("supplier_id"):
                    errors.append("SUPPLIER_ID is required")
                if not hdr.get("warehouse_id"):
                    errors.append("WAREHOUSE_ID is required")

                rl = db.execute_query(
                    "SELECT * FROM AGRO_PURCHASE_LINES WHERE PURCHASE_DOC_ID = :doc_id ORDER BY ID",
                    {"doc_id": doc_id},
                )
                lines = _norm_rows(rl)
                valid_lines = [
                    ln
                    for ln in lines
                    if ln.get("item_id") and ln.get("gross_weight_kg")
                ]
                if not valid_lines:
                    errors.append(
                        "At least one line with ITEM_ID and GROSS_WEIGHT_KG is required"
                    )
                if errors:
                    return {"success": False, "error": "; ".join(errors)}

                warehouse_id = hdr["warehouse_id"]
                today_str = datetime.now().strftime("%Y%m%d")

                total_gross = 0.0
                total_net = 0.0
                total_amount = 0.0

                for ln in valid_lines:
                    # Recalculate net weight via Q-Net formula
                    gross_kg = float(ln.get("gross_weight_kg") or 0)
                    tare_kg = float(ln.get("tare_weight_kg") or 0)
                    net_kg = gross_kg - tare_kg if tare_kg else gross_kg
                    price = float(ln.get("price_per_kg") or 0)
                    amount = round(net_kg * price, 2)

                    # Update line with recalculated values
                    db.execute_query(
                        """UPDATE AGRO_PURCHASE_LINES
                              SET NET_WEIGHT_KG = :net_kg,
                                  AMOUNT = :amount
                            WHERE ID = :line_id""",
                        {
                            "net_kg": net_kg,
                            "amount": amount,
                            "line_id": ln["id"],
                        },
                    )

                    total_gross += gross_kg
                    total_net += net_kg
                    total_amount += amount

                    # --- Create batch ---
                    r_bseq = db.execute_query(
                        "SELECT AGRO_BATCHES_SEQ.NEXTVAL AS SEQ_VAL FROM DUAL",
                        None,
                    )
                    batch_id = int(_norm_rows(r_bseq)[0]["seq_val"])
                    batch_number = f"B-{today_str}-{batch_id:04d}"

                    # Look up shelf life from AGRO_ITEMS
                    r_item = db.execute_query(
                        "SELECT SHELF_LIFE_DAYS FROM AGRO_ITEMS WHERE ID = :item_id",
                        {"item_id": ln["item_id"]},
                    )
                    item_rows = _norm_rows(r_item)
                    shelf_days = (
                        int(item_rows[0]["shelf_life_days"])
                        if item_rows and item_rows[0].get("shelf_life_days")
                        else None
                    )

                    batch_params: Dict[str, Any] = {
                        "id": batch_id,
                        "batch_number": batch_number,
                        "purchase_line_id": ln["id"],
                        "item_id": ln["item_id"],
                        "warehouse_id": warehouse_id,
                        "initial_qty_kg": net_kg,
                        "current_qty_kg": net_kg,
                        "status": "active",
                    }

                    if shelf_days is not None:
                        db.execute_query(
                            """INSERT INTO AGRO_BATCHES
                                      (ID, BATCH_NUMBER, PURCHASE_LINE_ID, ITEM_ID,
                                       WAREHOUSE_ID, INITIAL_QTY_KG, CURRENT_QTY_KG,
                                       STATUS, EXPIRY_DATE)
                               VALUES (:id, :batch_number, :purchase_line_id, :item_id,
                                       :warehouse_id, :initial_qty_kg, :current_qty_kg,
                                       :status, SYSTIMESTAMP + :shelf_days)""",
                            {**batch_params, "shelf_days": shelf_days},
                        )
                    else:
                        db.execute_query(
                            """INSERT INTO AGRO_BATCHES
                                      (ID, BATCH_NUMBER, PURCHASE_LINE_ID, ITEM_ID,
                                       WAREHOUSE_ID, INITIAL_QTY_KG, CURRENT_QTY_KG,
                                       STATUS)
                               VALUES (:id, :batch_number, :purchase_line_id, :item_id,
                                       :warehouse_id, :initial_qty_kg, :current_qty_kg,
                                       :status)""",
                            batch_params,
                        )

                    # --- Create stock movement (receipt) ---
                    db.execute_query(
                        """INSERT INTO AGRO_STOCK_MOVEMENTS
                                  (ID, BATCH_ID, MOVEMENT_TYPE,
                                   TO_WAREHOUSE_ID, QTY_KG, DOC_REF)
                           VALUES (AGRO_STOCK_MOVEMENTS_SEQ.NEXTVAL, :batch_id,
                                   'receipt', :warehouse_id, :qty_kg, :doc_ref)""",
                        {
                            "batch_id": batch_id,
                            "warehouse_id": warehouse_id,
                            "qty_kg": net_kg,
                            "doc_ref": f"PD-{doc_id}",
                        },
                    )

                # --- Update header totals and status ---
                db.execute_query(
                    """UPDATE AGRO_PURCHASE_DOCS
                          SET STATUS = 'confirmed',
                              CONFIRMED_AT = SYSTIMESTAMP,
                              TOTAL_GROSS_KG = :total_gross,
                              TOTAL_NET_KG = :total_net,
                              TOTAL_AMOUNT = :total_amount
                        WHERE ID = :doc_id""",
                    {
                        "total_gross": total_gross,
                        "total_net": total_net,
                        "total_amount": total_amount,
                        "doc_id": doc_id,
                    },
                )
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def cancel_purchase(doc_id: int) -> Dict[str, Any]:
        """Cancel a purchase document (only if status is draft)."""
        try:
            with DatabaseModel() as db:
                rh = db.execute_query(
                    "SELECT STATUS FROM AGRO_PURCHASE_DOCS WHERE ID = :doc_id",
                    {"doc_id": doc_id},
                )
                rows = _norm_rows(rh)
                if not rows:
                    return {"success": False, "error": "Document not found"}
                if rows[0]["status"] != "draft":
                    return {
                        "success": False,
                        "error": "Only draft documents can be cancelled",
                    }
                db.execute_query(
                    "UPDATE AGRO_PURCHASE_DOCS SET STATUS = 'cancelled' WHERE ID = :doc_id",
                    {"doc_id": doc_id},
                )
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ==================================================================
    # Q-Net / Suma calculation helpers
    # ==================================================================

    @staticmethod
    def calc_qnet_suma(
        item_id: Optional[int],
        gross_kg: float,
        crates_count: int,
        price_per_kg: float,
    ) -> Dict[str, Any]:
        """Calculate Q-Net and Suma using AGRO_FORMULA_PARAMS.

        Q-Net = Q-Brut - (Crates x Tare)
        Suma  = Q-Net  x Price

        Tare comes from item-specific formula param or global default.
        Rounding per rounding_mode / rounding_precision params.
        """
        try:
            with DatabaseModel() as db:
                # Look up tare — item-specific first, then global
                tare_per_crate = 0.0
                rounding_mode = "half_up"
                rounding_precision = 2

                def _get_param(
                    p_item_id: Optional[int], name: str
                ) -> Optional[str]:
                    sql = (
                        "SELECT PARAM_VALUE FROM AGRO_FORMULA_PARAMS "
                        "WHERE PARAM_NAME = :pname AND ACTIVE = 'Y'"
                    )
                    params: Dict[str, Any] = {"pname": name}
                    if p_item_id is not None:
                        sql += " AND ITEM_ID = :item_id"
                        params["item_id"] = p_item_id
                    else:
                        sql += " AND ITEM_ID IS NULL"
                    r = db.execute_query(sql, params)
                    rows = _norm_rows(r)
                    return rows[0]["param_value"] if rows else None

                # Tare
                val = None
                if item_id is not None:
                    val = _get_param(item_id, "tare_per_crate")
                if val is None:
                    val = _get_param(None, "tare_per_crate")
                if val is not None:
                    tare_per_crate = float(val)

                # Rounding mode
                rm = None
                if item_id is not None:
                    rm = _get_param(item_id, "rounding_mode")
                if rm is None:
                    rm = _get_param(None, "rounding_mode")
                if rm:
                    rounding_mode = rm

                # Rounding precision
                rp = None
                if item_id is not None:
                    rp = _get_param(item_id, "rounding_precision")
                if rp is None:
                    rp = _get_param(None, "rounding_precision")
                if rp is not None:
                    rounding_precision = int(rp)

                qnet = gross_kg - (crates_count * tare_per_crate)
                suma = qnet * price_per_kg

                # Apply rounding
                mode_map = {
                    "half_up": ROUND_HALF_UP,
                    "down": ROUND_DOWN,
                    "up": ROUND_UP,
                }
                dec_mode = mode_map.get(rounding_mode, ROUND_HALF_UP)
                quantize_str = f"1.{'0' * rounding_precision}"
                qnet_rounded = float(
                    Decimal(str(qnet)).quantize(
                        Decimal(quantize_str), rounding=dec_mode
                    )
                )
                suma_rounded = float(
                    Decimal(str(suma)).quantize(
                        Decimal(quantize_str), rounding=dec_mode
                    )
                )

                return {
                    "success": True,
                    "data": {
                        "gross_kg": gross_kg,
                        "crates_count": crates_count,
                        "tare_per_crate": tare_per_crate,
                        "total_tare": crates_count * tare_per_crate,
                        "net_kg": qnet_rounded,
                        "price_per_kg": price_per_kg,
                        "amount": suma_rounded,
                        "rounding_mode": rounding_mode,
                        "rounding_precision": rounding_precision,
                    },
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ==================================================================
    # Sync / Offline support
    # ==================================================================

    @staticmethod
    def get_sync_references() -> Dict[str, Any]:
        """Return all active reference data for offline cache."""
        try:
            result: Dict[str, Any] = {}
            ref_tables = {
                "suppliers": ("AGRO_SUPPLIERS", "NAME"),
                "customers": ("AGRO_CUSTOMERS", "NAME"),
                "warehouses": ("AGRO_WAREHOUSES", "NAME"),
                "items": ("AGRO_ITEMS", "NAME_RU"),
                "packaging_types": ("AGRO_PACKAGING_TYPES", "NAME_RU"),
                "vehicles": ("AGRO_VEHICLES", "PLATE_NUMBER"),
                "currencies": ("AGRO_CURRENCIES", "CODE"),
            }
            with DatabaseModel() as db:
                for key, (table, order) in ref_tables.items():
                    r = db.execute_query(
                        f"SELECT * FROM {table} WHERE ACTIVE = :active ORDER BY {order}",
                        {"active": "Y"},
                    )
                    result[key] = _norm_rows(r)
            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def sync_offline_queue(queue: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Process a list of offline operations, deduplicating by client_uuid.

        Each item in *queue* should have:
          - client_uuid: unique operation ID from the client
          - event_type: operation type (e.g. 'create_purchase', 'register_crate')
          - payload: dict with operation data
        """
        try:
            synced = 0
            conflicts: List[Dict[str, Any]] = []
            with DatabaseModel() as db:
                for op in queue:
                    client_uuid = op.get("client_uuid")
                    event_type = op.get("event_type", "")
                    payload = op.get("payload", {})

                    # Dedup: check if this client_uuid was already processed
                    if client_uuid:
                        r_check = db.execute_query(
                            """SELECT COUNT(*) AS CNT FROM AGRO_EVENT_LOG
                               WHERE EVENT_TYPE = :etype
                                 AND PAYLOAD LIKE :uuid_pattern""",
                            {
                                "etype": f"sync_{event_type}",
                                "uuid_pattern": f"%{client_uuid}%",
                            },
                        )
                        check_rows = _norm_rows(r_check)
                        if check_rows and int(check_rows[0].get("cnt", 0)) > 0:
                            conflicts.append(
                                {
                                    "client_uuid": client_uuid,
                                    "reason": "already_processed",
                                }
                            )
                            continue

                    # Log the event
                    event_payload = json.dumps(
                        {"client_uuid": client_uuid, **payload},
                        default=str,
                    )
                    db.execute_query(
                        """INSERT INTO AGRO_EVENT_LOG
                                  (ID, EVENT_TYPE, ENTITY_TYPE, ENTITY_ID, PAYLOAD)
                           VALUES (AGRO_EVENT_LOG_SEQ.NEXTVAL, :etype,
                                   :entity_type, :entity_id, :payload)""",
                        {
                            "etype": f"sync_{event_type}",
                            "entity_type": payload.get("entity_type"),
                            "entity_id": payload.get("entity_id"),
                            "payload": event_payload,
                        },
                    )

                    # Dispatch operation
                    try:
                        if event_type == "create_purchase":
                            AgroStore.create_purchase(payload)
                        elif event_type == "register_crate":
                            AgroStore.register_crate(payload)
                        elif event_type == "update_purchase":
                            AgroStore.update_purchase(payload)
                        # Additional event types can be added here
                        synced += 1
                    except Exception as op_err:
                        conflicts.append(
                            {
                                "client_uuid": client_uuid,
                                "reason": str(op_err),
                            }
                        )

                db.connection.commit()
            return {
                "success": True,
                "synced": synced,
                "conflicts": conflicts,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------
    # Warehouse — Stock & Movements
    # ------------------------------------------------------------------

    @staticmethod
    def get_stock_balance(filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Query AGRO_V_STOCK_BALANCE view with optional filters."""
        try:
            with DatabaseModel() as db:
                sql = "SELECT * FROM AGRO_V_STOCK_BALANCE WHERE 1=1"
                params: Dict[str, Any] = {}
                if filters:
                    if filters.get("warehouse_id"):
                        sql += " AND WAREHOUSE_ID = :wh_id"
                        params["wh_id"] = filters["warehouse_id"]
                    if filters.get("item_id"):
                        sql += " AND ITEM_ID = :item_id"
                        params["item_id"] = filters["item_id"]
                    if filters.get("status"):
                        sql += " AND STATUS = :status"
                        params["status"] = filters["status"]
                sql += " ORDER BY ITEM_NAME, WAREHOUSE_NAME"
                r = db.execute_query(sql, params)
                return {"success": True, "data": _norm_rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_batch_by_id(batch_id: int) -> Dict[str, Any]:
        """Get batch with full details: movements, QA checks, allocations."""
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    """SELECT b.*, i.NAME AS ITEM_NAME, i.CODE AS ITEM_CODE,
                              w.NAME AS WAREHOUSE_NAME, c.CODE AS CELL_CODE
                       FROM AGRO_BATCHES b
                       LEFT JOIN AGRO_ITEMS i ON b.ITEM_ID = i.ID
                       LEFT JOIN AGRO_WAREHOUSES w ON b.WAREHOUSE_ID = w.ID
                       LEFT JOIN AGRO_STORAGE_CELLS c ON b.CELL_ID = c.ID
                       WHERE b.ID = :bid""",
                    {"bid": batch_id},
                )
                rows = _norm_rows(r)
                if not rows:
                    return {"success": False, "error": "Batch not found"}
                batch = rows[0]

                r2 = db.execute_query(
                    """SELECT * FROM AGRO_STOCK_MOVEMENTS
                       WHERE BATCH_ID = :bid ORDER BY CREATED_AT DESC""",
                    {"bid": batch_id},
                )
                movements = _norm_rows(r2)

                r3 = db.execute_query(
                    """SELECT qc.*, cl.NAME_RU AS CHECKLIST_NAME
                       FROM AGRO_QA_CHECKS qc
                       LEFT JOIN AGRO_QA_CHECKLISTS cl ON qc.CHECKLIST_ID = cl.ID
                       WHERE qc.BATCH_ID = :bid ORDER BY qc.CREATED_AT DESC""",
                    {"bid": batch_id},
                )
                qa_checks = _norm_rows(r3)

                r4 = db.execute_query(
                    """SELECT ba.*, sl.ITEM_ID, sl.QTY_KG AS LINE_QTY
                       FROM AGRO_BATCH_ALLOCATIONS ba
                       LEFT JOIN AGRO_SALES_DOC_LINES sl ON ba.SALES_LINE_ID = sl.ID
                       WHERE ba.BATCH_ID = :bid ORDER BY ba.CREATED_AT DESC""",
                    {"bid": batch_id},
                )
                allocations = _norm_rows(r4)

                return {
                    "success": True,
                    "data": {
                        "batch": batch,
                        "movements": movements,
                        "qa_checks": qa_checks,
                        "allocations": allocations,
                    },
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_batch_history(batch_id: int) -> Dict[str, Any]:
        """Timeline of all events for a batch."""
        try:
            with DatabaseModel() as db:
                sql = """
                    SELECT 'movement' AS EVENT_TYPE, MOVEMENT_TYPE AS DETAIL,
                           QTY_KG, REASON AS DESCRIPTION, CREATED_AT AS EVENT_TIME
                    FROM AGRO_STOCK_MOVEMENTS WHERE BATCH_ID = :bid
                    UNION ALL
                    SELECT 'qa_check', RESULT, NULL,
                           NOTES, CREATED_AT
                    FROM AGRO_QA_CHECKS WHERE BATCH_ID = :bid
                    UNION ALL
                    SELECT 'block', 'blocked', NULL,
                           REASON, BLOCKED_AT
                    FROM AGRO_BATCH_BLOCKS WHERE BATCH_ID = :bid
                    UNION ALL
                    SELECT 'unblock', 'unblocked', NULL,
                           RESOLUTION_NOTES, UNBLOCKED_AT
                    FROM AGRO_BATCH_BLOCKS WHERE BATCH_ID = :bid AND UNBLOCKED_AT IS NOT NULL
                    ORDER BY EVENT_TIME DESC
                """
                r = db.execute_query(sql, {"bid": batch_id})
                return {"success": True, "data": _norm_rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def create_movement(data: Dict[str, Any]) -> Dict[str, Any]:
        """Create stock movement (transfer, receipt, shipment, etc.)."""
        try:
            batch_id = data.get("batch_id")
            movement_type = data.get("movement_type", "transfer")
            qty_kg = float(data.get("qty_kg", 0))
            if not batch_id or qty_kg <= 0:
                return {"success": False, "error": "batch_id and qty_kg > 0 required"}

            valid_types = ("receipt", "transfer", "processing", "shipment", "adjustment", "loss")
            if movement_type not in valid_types:
                return {"success": False, "error": f"Invalid movement_type: {movement_type}"}

            with DatabaseModel() as db:
                r = db.execute_query(
                    "SELECT CURRENT_QTY_KG FROM AGRO_BATCHES WHERE ID = :bid",
                    {"bid": batch_id},
                )
                rows = _norm_rows(r)
                if not rows:
                    return {"success": False, "error": "Batch not found"}

                current_qty = float(rows[0].get("current_qty_kg", 0))
                if movement_type in ("transfer", "shipment", "loss", "processing") and qty_kg > current_qty:
                    return {
                        "success": False,
                        "error": f"Insufficient qty: have {current_qty:.3f}, requested {qty_kg:.3f}",
                    }

                db.execute_query(
                    """INSERT INTO AGRO_STOCK_MOVEMENTS
                       (ID, BATCH_ID, MOVEMENT_TYPE, FROM_WAREHOUSE_ID, FROM_CELL_ID,
                        TO_WAREHOUSE_ID, TO_CELL_ID, QTY_KG, REASON, DOC_REF, CREATED_BY)
                       VALUES (AGRO_STOCK_MOVEMENTS_SEQ.NEXTVAL,
                               :bid, :mtype, :fwh, :fcell, :twh, :tcell,
                               :qty, :reason, :doc_ref, :created_by)""",
                    {
                        "bid": batch_id,
                        "mtype": movement_type,
                        "fwh": data.get("from_warehouse_id"),
                        "fcell": data.get("from_cell_id"),
                        "twh": data.get("to_warehouse_id"),
                        "tcell": data.get("to_cell_id"),
                        "qty": qty_kg,
                        "reason": data.get("reason"),
                        "doc_ref": data.get("doc_ref"),
                        "created_by": data.get("created_by"),
                    },
                )

                if movement_type in ("transfer", "shipment", "loss", "processing"):
                    db.execute_query(
                        "UPDATE AGRO_BATCHES SET CURRENT_QTY_KG = CURRENT_QTY_KG - :qty WHERE ID = :bid",
                        {"qty": qty_kg, "bid": batch_id},
                    )

                if movement_type == "transfer" and data.get("to_warehouse_id"):
                    upd_sql = "UPDATE AGRO_BATCHES SET WAREHOUSE_ID = :twh"
                    upd_params: Dict[str, Any] = {"twh": data["to_warehouse_id"], "bid": batch_id}
                    if data.get("to_cell_id"):
                        upd_sql += ", CELL_ID = :tcell"
                        upd_params["tcell"] = data["to_cell_id"]
                    upd_sql += " WHERE ID = :bid"
                    db.execute_query(upd_sql, upd_params)

                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def receive_crates(data: Dict[str, Any]) -> Dict[str, Any]:
        """Receive crates at warehouse, update status to accepted."""
        try:
            crate_ids = data.get("crate_ids", [])
            warehouse_id = data.get("warehouse_id")
            cell_id = data.get("cell_id")
            if not crate_ids:
                return {"success": False, "error": "crate_ids required"}

            with DatabaseModel() as db:
                for cid in crate_ids:
                    db.execute_query(
                        "UPDATE AGRO_BATCH_CRATES SET STATUS = 'accepted' WHERE ID = :cid",
                        {"cid": cid},
                    )
                    if warehouse_id:
                        db.execute_query(
                            """UPDATE AGRO_BATCHES SET WAREHOUSE_ID = :wh, CELL_ID = :cell
                               WHERE ID = (SELECT BATCH_ID FROM AGRO_BATCH_CRATES WHERE ID = :cid)""",
                            {"wh": warehouse_id, "cell": cell_id, "cid": cid},
                        )
                db.connection.commit()
                return {"success": True, "updated": len(crate_ids)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------
    # Warehouse — Temperature / Readings
    # ------------------------------------------------------------------

    @staticmethod
    def get_readings(cell_id: int = None, date_from: str = None, date_to: str = None) -> Dict[str, Any]:
        """Get storage readings with optional cell and date filters."""
        try:
            with DatabaseModel() as db:
                sql = """SELECT sr.*, sc.CODE AS CELL_CODE, sc.NAME AS CELL_NAME,
                                w.NAME AS WAREHOUSE_NAME
                         FROM AGRO_STORAGE_READINGS sr
                         JOIN AGRO_STORAGE_CELLS sc ON sr.CELL_ID = sc.ID
                         JOIN AGRO_WAREHOUSES w ON sc.WAREHOUSE_ID = w.ID
                         WHERE 1=1"""
                params: Dict[str, Any] = {}
                if cell_id:
                    sql += " AND sr.CELL_ID = :cell_id"
                    params["cell_id"] = cell_id
                if date_from:
                    sql += " AND sr.RECORDED_AT >= TO_TIMESTAMP(:dfrom, 'YYYY-MM-DD')"
                    params["dfrom"] = date_from
                if date_to:
                    sql += " AND sr.RECORDED_AT < TO_TIMESTAMP(:dto, 'YYYY-MM-DD') + 1"
                    params["dto"] = date_to
                sql += " ORDER BY sr.RECORDED_AT DESC"
                r = db.execute_query(sql, params)
                return {"success": True, "data": _norm_rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def add_reading(data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert reading and check thresholds. Create alert if out of range."""
        try:
            cell_id = data.get("cell_id")
            if not cell_id:
                return {"success": False, "error": "cell_id required"}

            with DatabaseModel() as db:
                db.execute_query(
                    """INSERT INTO AGRO_STORAGE_READINGS
                       (ID, CELL_ID, TEMPERATURE_C, HUMIDITY_PCT, O2_PCT, CO2_PCT,
                        READING_SOURCE, SENSOR_ID, RECORDED_BY)
                       VALUES (AGRO_STORAGE_READINGS_SEQ.NEXTVAL,
                               :cell, :temp, :hum, :o2, :co2, :src, :sensor, :by)""",
                    {
                        "cell": cell_id,
                        "temp": data.get("temperature_c"),
                        "hum": data.get("humidity_pct"),
                        "o2": data.get("o2_pct"),
                        "co2": data.get("co2_pct"),
                        "src": data.get("reading_source", "manual"),
                        "sensor": data.get("sensor_id"),
                        "by": data.get("recorded_by"),
                    },
                )

                r_id = db.execute_query(
                    "SELECT AGRO_STORAGE_READINGS_SEQ.CURRVAL AS RID FROM DUAL", {}
                )
                reading_id = _norm_rows(r_id)[0]["rid"] if _norm_rows(r_id) else None

                r_cell = db.execute_query(
                    "SELECT TEMP_MIN, TEMP_MAX, HUMIDITY_MIN, HUMIDITY_MAX FROM AGRO_STORAGE_CELLS WHERE ID = :cell",
                    {"cell": cell_id},
                )
                cell_info = _norm_rows(r_cell)
                alerts: List = []

                if cell_info:
                    ci = cell_info[0]
                    temp = data.get("temperature_c")
                    hum = data.get("humidity_pct")

                    if temp is not None:
                        temp = float(temp)
                        if ci.get("temp_max") is not None and temp > float(ci["temp_max"]):
                            alerts.append(("temp_high", float(ci["temp_max"]), temp))
                        elif ci.get("temp_min") is not None and temp < float(ci["temp_min"]):
                            alerts.append(("temp_low", float(ci["temp_min"]), temp))

                    if hum is not None:
                        hum_val = float(hum)
                        if ci.get("humidity_max") is not None and hum_val > float(ci["humidity_max"]):
                            alerts.append(("humidity", float(ci["humidity_max"]), hum_val))
                        elif ci.get("humidity_min") is not None and hum_val < float(ci["humidity_min"]):
                            alerts.append(("humidity", float(ci["humidity_min"]), hum_val))

                for alert_type, threshold, actual in alerts:
                    db.execute_query(
                        """INSERT INTO AGRO_STORAGE_ALERTS
                           (ID, CELL_ID, READING_ID, ALERT_TYPE, THRESHOLD_VALUE, ACTUAL_VALUE)
                           VALUES (AGRO_STORAGE_ALERTS_SEQ.NEXTVAL,
                                   :cell, :rid, :atype, :thresh, :actual)""",
                        {"cell": cell_id, "rid": reading_id, "atype": alert_type,
                         "thresh": threshold, "actual": actual},
                    )

                db.connection.commit()
                return {
                    "success": True,
                    "data": {
                        "reading_id": reading_id,
                        "alerts": [{"type": a[0], "threshold": a[1], "actual": a[2]} for a in alerts],
                    },
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_alerts(acknowledged: str = None) -> Dict[str, Any]:
        """List storage alerts. Filter by acknowledged status."""
        try:
            with DatabaseModel() as db:
                sql = """SELECT sa.*, sc.CODE AS CELL_CODE, sc.NAME AS CELL_NAME,
                                w.NAME AS WAREHOUSE_NAME
                         FROM AGRO_STORAGE_ALERTS sa
                         JOIN AGRO_STORAGE_CELLS sc ON sa.CELL_ID = sc.ID
                         JOIN AGRO_WAREHOUSES w ON sc.WAREHOUSE_ID = w.ID
                         WHERE 1=1"""
                params: Dict[str, Any] = {}
                if acknowledged:
                    sql += " AND sa.ACKNOWLEDGED = :ack"
                    params["ack"] = acknowledged
                sql += " ORDER BY sa.CREATED_AT DESC"
                r = db.execute_query(sql, params)
                return {"success": True, "data": _norm_rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def acknowledge_alert(alert_id: int, user: str) -> Dict[str, Any]:
        """Mark alert as acknowledged."""
        try:
            with DatabaseModel() as db:
                db.execute_query(
                    """UPDATE AGRO_STORAGE_ALERTS
                       SET ACKNOWLEDGED = 'Y', ACKNOWLEDGED_BY = :usr, ACKNOWLEDGED_AT = SYSTIMESTAMP
                       WHERE ID = :aid""",
                    {"aid": alert_id, "usr": user},
                )
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------
    # Warehouse — Processing Tasks
    # ------------------------------------------------------------------

    @staticmethod
    def get_processing_tasks(filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """List processing tasks with batch info."""
        try:
            with DatabaseModel() as db:
                sql = """SELECT pt.*, b.BATCH_NUMBER, i.NAME AS ITEM_NAME
                         FROM AGRO_PROCESSING_TASKS pt
                         JOIN AGRO_BATCHES b ON pt.BATCH_ID = b.ID
                         LEFT JOIN AGRO_ITEMS i ON b.ITEM_ID = i.ID
                         WHERE 1=1"""
                params: Dict[str, Any] = {}
                if filters:
                    if filters.get("status"):
                        sql += " AND pt.STATUS = :status"
                        params["status"] = filters["status"]
                    if filters.get("batch_id"):
                        sql += " AND pt.BATCH_ID = :bid"
                        params["bid"] = filters["batch_id"]
                    if filters.get("task_type"):
                        sql += " AND pt.TASK_TYPE = :ttype"
                        params["ttype"] = filters["task_type"]
                sql += " ORDER BY pt.ID DESC"
                r = db.execute_query(sql, params)
                return {"success": True, "data": _norm_rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def create_processing_task(data: Dict[str, Any]) -> Dict[str, Any]:
        """Create processing task linked to batch."""
        try:
            batch_id = data.get("batch_id")
            task_type = data.get("task_type", "sorting")
            if not batch_id:
                return {"success": False, "error": "batch_id required"}

            with DatabaseModel() as db:
                db.execute_query(
                    """INSERT INTO AGRO_PROCESSING_TASKS
                       (ID, BATCH_ID, TASK_TYPE, DESCRIPTION, ASSIGNED_TO, INPUT_QTY_KG, NOTES)
                       VALUES (AGRO_PROCESSING_TASKS_SEQ.NEXTVAL,
                               :bid, :ttype, :descr, :assigned, :input_qty, :notes)""",
                    {
                        "bid": batch_id,
                        "ttype": task_type,
                        "descr": data.get("description"),
                        "assigned": data.get("assigned_to"),
                        "input_qty": data.get("input_qty_kg"),
                        "notes": data.get("notes"),
                    },
                )
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def update_task_status(
        task_id: int, status: str,
        output_qty: float = None, waste_qty: float = None,
    ) -> Dict[str, Any]:
        """Update task status. On completion, adjust batch qty for waste."""
        try:
            valid = ("pending", "in_progress", "completed", "cancelled")
            if status not in valid:
                return {"success": False, "error": f"Invalid status: {status}"}

            with DatabaseModel() as db:
                r = db.execute_query(
                    "SELECT BATCH_ID FROM AGRO_PROCESSING_TASKS WHERE ID = :tid",
                    {"tid": task_id},
                )
                rows = _norm_rows(r)
                if not rows:
                    return {"success": False, "error": "Task not found"}
                batch_id = rows[0]["batch_id"]

                upd = "UPDATE AGRO_PROCESSING_TASKS SET STATUS = :st"
                params: Dict[str, Any] = {"st": status, "tid": task_id}

                if output_qty is not None:
                    upd += ", OUTPUT_QTY_KG = :oqty"
                    params["oqty"] = output_qty
                if waste_qty is not None:
                    upd += ", WASTE_QTY_KG = :wqty"
                    params["wqty"] = waste_qty
                if status == "in_progress":
                    upd += ", STARTED_AT = SYSTIMESTAMP"
                if status == "completed":
                    upd += ", COMPLETED_AT = SYSTIMESTAMP"
                upd += " WHERE ID = :tid"

                db.execute_query(upd, params)

                if status == "completed" and waste_qty and waste_qty > 0:
                    db.execute_query(
                        "UPDATE AGRO_BATCHES SET CURRENT_QTY_KG = CURRENT_QTY_KG - :waste WHERE ID = :bid",
                        {"waste": waste_qty, "bid": batch_id},
                    )

                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------
    # Sales & Export — Documents
    # ------------------------------------------------------------------

    @staticmethod
    def get_sales_docs(filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """List sales documents with customer/warehouse joins."""
        try:
            with DatabaseModel() as db:
                sql = """SELECT sd.*, c.NAME AS CUSTOMER_NAME, c.CODE AS CUSTOMER_CODE,
                                w.NAME AS WAREHOUSE_NAME, cur.CODE AS CURRENCY_CODE
                         FROM AGRO_SALES_DOCS sd
                         LEFT JOIN AGRO_CUSTOMERS c ON sd.CUSTOMER_ID = c.ID
                         LEFT JOIN AGRO_WAREHOUSES w ON sd.WAREHOUSE_ID = w.ID
                         LEFT JOIN AGRO_CURRENCIES cur ON sd.CURRENCY_ID = cur.ID
                         WHERE 1=1"""
                params: Dict[str, Any] = {}
                if filters:
                    if filters.get("status"):
                        sql += " AND sd.STATUS = :status"
                        params["status"] = filters["status"]
                    if filters.get("customer_id"):
                        sql += " AND sd.CUSTOMER_ID = :cust_id"
                        params["cust_id"] = filters["customer_id"]
                    if filters.get("date_from"):
                        sql += " AND sd.DOC_DATE >= TO_DATE(:dfrom, 'YYYY-MM-DD')"
                        params["dfrom"] = filters["date_from"]
                    if filters.get("date_to"):
                        sql += " AND sd.DOC_DATE <= TO_DATE(:dto, 'YYYY-MM-DD')"
                        params["dto"] = filters["date_to"]
                sql += " ORDER BY sd.CREATED_AT DESC"
                r = db.execute_query(sql, params)
                return {"success": True, "data": _norm_rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_sales_doc_by_id(doc_id: int) -> Dict[str, Any]:
        """Get sales doc header + lines + allocations."""
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    """SELECT sd.*, c.NAME AS CUSTOMER_NAME,
                              w.NAME AS WAREHOUSE_NAME, cur.CODE AS CURRENCY_CODE
                       FROM AGRO_SALES_DOCS sd
                       LEFT JOIN AGRO_CUSTOMERS c ON sd.CUSTOMER_ID = c.ID
                       LEFT JOIN AGRO_WAREHOUSES w ON sd.WAREHOUSE_ID = w.ID
                       LEFT JOIN AGRO_CURRENCIES cur ON sd.CURRENCY_ID = cur.ID
                       WHERE sd.ID = :did""",
                    {"did": doc_id},
                )
                docs = _norm_rows(r)
                if not docs:
                    return {"success": False, "error": "Sales doc not found"}

                r2 = db.execute_query(
                    """SELECT sl.*, i.NAME AS ITEM_NAME, i.CODE AS ITEM_CODE
                       FROM AGRO_SALES_DOC_LINES sl
                       LEFT JOIN AGRO_ITEMS i ON sl.ITEM_ID = i.ID
                       WHERE sl.SALES_DOC_ID = :did ORDER BY sl.ID""",
                    {"did": doc_id},
                )
                lines = _norm_rows(r2)

                r3 = db.execute_query(
                    """SELECT ba.*, b.BATCH_NUMBER, b.CURRENT_QTY_KG
                       FROM AGRO_BATCH_ALLOCATIONS ba
                       JOIN AGRO_BATCHES b ON ba.BATCH_ID = b.ID
                       JOIN AGRO_SALES_DOC_LINES sl ON ba.SALES_LINE_ID = sl.ID
                       WHERE sl.SALES_DOC_ID = :did ORDER BY ba.ID""",
                    {"did": doc_id},
                )
                allocations = _norm_rows(r3)

                return {
                    "success": True,
                    "data": {"doc": docs[0], "lines": lines, "allocations": allocations},
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def create_sales_doc(data: Dict[str, Any]) -> Dict[str, Any]:
        """Create sales document with lines."""
        try:
            customer_id = data.get("customer_id")
            warehouse_id = data.get("warehouse_id")
            if not customer_id or not warehouse_id:
                return {"success": False, "error": "customer_id and warehouse_id required"}

            with DatabaseModel() as db:
                r_seq = db.execute_query(
                    "SELECT AGRO_SALES_DOCS_SEQ.NEXTVAL AS NID FROM DUAL", {}
                )
                new_id = _norm_rows(r_seq)[0]["nid"]
                today = datetime.now().strftime("%Y%m%d")
                doc_number = f"SALE-{today}-{int(new_id):04d}"

                db.execute_query(
                    """INSERT INTO AGRO_SALES_DOCS
                       (ID, DOC_NUMBER, DOC_DATE, CUSTOMER_ID, WAREHOUSE_ID,
                        VEHICLE_ID, CURRENCY_ID, TOTAL_AMOUNT, STATUS, NOTES, CREATED_BY)
                       VALUES (:id, :dnum, TRUNC(SYSDATE), :cust, :wh,
                               :veh, :cur, 0, 'draft', :notes, :by)""",
                    {
                        "id": new_id, "dnum": doc_number,
                        "cust": customer_id, "wh": warehouse_id,
                        "veh": data.get("vehicle_id"), "cur": data.get("currency_id"),
                        "notes": data.get("notes"), "by": data.get("created_by"),
                    },
                )

                total_amount = Decimal("0")
                for line in data.get("lines", []):
                    qty = Decimal(str(line.get("qty_kg", 0)))
                    price = Decimal(str(line.get("price_per_kg", 0)))
                    amount = (qty * price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    total_amount += amount

                    db.execute_query(
                        """INSERT INTO AGRO_SALES_DOC_LINES
                           (ID, SALES_DOC_ID, ITEM_ID, QTY_KG, PRICE_PER_KG, AMOUNT, NOTES)
                           VALUES (AGRO_SALES_DOC_LINES_SEQ.NEXTVAL,
                                   :did, :iid, :qty, :price, :amt, :notes)""",
                        {
                            "did": new_id, "iid": line.get("item_id"),
                            "qty": float(qty), "price": float(price),
                            "amt": float(amount), "notes": line.get("notes"),
                        },
                    )

                if total_amount > 0:
                    db.execute_query(
                        "UPDATE AGRO_SALES_DOCS SET TOTAL_AMOUNT = :amt WHERE ID = :id",
                        {"amt": float(total_amount), "id": new_id},
                    )

                db.connection.commit()
                return {"success": True, "id": int(new_id), "doc_number": doc_number}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def confirm_sales_doc(doc_id: int) -> Dict[str, Any]:
        """Confirm sales doc: validate stock, check blocks, allocate via FIFO."""
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    "SELECT ID AS LINE_ID, ITEM_ID, QTY_KG FROM AGRO_SALES_DOC_LINES WHERE SALES_DOC_ID = :did",
                    {"did": doc_id},
                )
                lines = _norm_rows(r)
                if not lines:
                    return {"success": False, "error": "No lines in document"}

                r_doc = db.execute_query(
                    "SELECT WAREHOUSE_ID, STATUS FROM AGRO_SALES_DOCS WHERE ID = :did",
                    {"did": doc_id},
                )
                doc_rows = _norm_rows(r_doc)
                if not doc_rows:
                    return {"success": False, "error": "Document not found"}
                if doc_rows[0].get("status") != "draft":
                    return {"success": False, "error": "Only draft docs can be confirmed"}
                wh_id = doc_rows[0].get("warehouse_id")

                for line in lines:
                    item_id = line["item_id"]
                    needed = float(line["qty_kg"])
                    line_id = line["line_id"]

                    sql = """SELECT ID, CURRENT_QTY_KG FROM AGRO_BATCHES
                             WHERE ITEM_ID = :iid AND STATUS = 'active' AND CURRENT_QTY_KG > 0"""
                    p: Dict[str, Any] = {"iid": item_id}
                    if wh_id:
                        sql += " AND WAREHOUSE_ID = :wh"
                        p["wh"] = wh_id
                    sql += " ORDER BY RECEIVED_AT ASC"
                    r_batches = db.execute_query(sql, p)
                    batches = _norm_rows(r_batches)

                    remaining = needed
                    for batch in batches:
                        if remaining <= 0:
                            break
                        alloc = min(float(batch["current_qty_kg"]), remaining)
                        db.execute_query(
                            """INSERT INTO AGRO_BATCH_ALLOCATIONS
                               (ID, SALES_LINE_ID, BATCH_ID, ALLOCATED_QTY_KG, ALLOCATION_METHOD)
                               VALUES (AGRO_BATCH_ALLOCATIONS_SEQ.NEXTVAL, :sl, :bid, :qty, 'fifo')""",
                            {"sl": line_id, "bid": batch["id"], "qty": alloc},
                        )
                        db.execute_query(
                            "UPDATE AGRO_BATCHES SET CURRENT_QTY_KG = CURRENT_QTY_KG - :qty WHERE ID = :bid",
                            {"qty": alloc, "bid": batch["id"]},
                        )
                        db.execute_query(
                            """INSERT INTO AGRO_STOCK_MOVEMENTS
                               (ID, BATCH_ID, MOVEMENT_TYPE, QTY_KG, DOC_REF)
                               VALUES (AGRO_STOCK_MOVEMENTS_SEQ.NEXTVAL, :bid, 'shipment', :qty, :ref)""",
                            {"bid": batch["id"], "qty": alloc, "ref": f"SALE-DOC-{doc_id}"},
                        )
                        remaining -= alloc

                    if remaining > 0:
                        db.connection.rollback()
                        return {"success": False, "error": f"Insufficient stock for item {item_id}: {remaining:.3f} kg short"}

                db.execute_query(
                    "UPDATE AGRO_SALES_DOCS SET STATUS = 'confirmed', CONFIRMED_AT = SYSTIMESTAMP WHERE ID = :did",
                    {"did": doc_id},
                )
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_available_stock(item_id: int = None, warehouse_id: int = None) -> Dict[str, Any]:
        """Get available (non-blocked) batches for sale."""
        try:
            with DatabaseModel() as db:
                sql = """SELECT b.ID, b.BATCH_NUMBER, b.CURRENT_QTY_KG, b.RECEIVED_AT,
                                i.NAME AS ITEM_NAME, i.CODE AS ITEM_CODE,
                                w.NAME AS WAREHOUSE_NAME
                         FROM AGRO_BATCHES b
                         JOIN AGRO_ITEMS i ON b.ITEM_ID = i.ID
                         LEFT JOIN AGRO_WAREHOUSES w ON b.WAREHOUSE_ID = w.ID
                         WHERE b.STATUS = 'active' AND b.CURRENT_QTY_KG > 0"""
                params: Dict[str, Any] = {}
                if item_id:
                    sql += " AND b.ITEM_ID = :iid"
                    params["iid"] = item_id
                if warehouse_id:
                    sql += " AND b.WAREHOUSE_ID = :wh"
                    params["wh"] = warehouse_id
                sql += " ORDER BY b.RECEIVED_AT ASC"
                r = db.execute_query(sql, params)
                return {"success": True, "data": _norm_rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def allocate_batches(
        sales_line_id: int, item_id: int, qty_kg: float,
        warehouse_id: int = None, method: str = "fifo",
    ) -> Dict[str, Any]:
        """Allocate batches to sales line using FIFO."""
        try:
            with DatabaseModel() as db:
                sql = """SELECT ID, CURRENT_QTY_KG FROM AGRO_BATCHES
                         WHERE ITEM_ID = :iid AND STATUS = 'active' AND CURRENT_QTY_KG > 0"""
                params: Dict[str, Any] = {"iid": item_id}
                if warehouse_id:
                    sql += " AND WAREHOUSE_ID = :wh"
                    params["wh"] = warehouse_id
                sql += " ORDER BY RECEIVED_AT ASC"
                r = db.execute_query(sql, params)
                batches = _norm_rows(r)

                remaining = qty_kg
                allocations: List = []
                for batch in batches:
                    if remaining <= 0:
                        break
                    alloc = min(float(batch["current_qty_kg"]), remaining)
                    db.execute_query(
                        """INSERT INTO AGRO_BATCH_ALLOCATIONS
                           (ID, SALES_LINE_ID, BATCH_ID, ALLOCATED_QTY_KG, ALLOCATION_METHOD)
                           VALUES (AGRO_BATCH_ALLOCATIONS_SEQ.NEXTVAL, :sl, :bid, :qty, :method)""",
                        {"sl": sales_line_id, "bid": batch["id"], "qty": alloc, "method": method},
                    )
                    remaining -= alloc
                    allocations.append({"batch_id": batch["id"], "qty": alloc})

                if remaining > 0:
                    db.connection.rollback()
                    return {"success": False, "error": f"Insufficient stock: {remaining:.3f} kg short"}

                db.connection.commit()
                return {"success": True, "data": allocations}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------
    # Sales — Export Declarations
    # ------------------------------------------------------------------

    @staticmethod
    def create_export_decl(data: Dict[str, Any]) -> Dict[str, Any]:
        """Create export declaration linked to sales doc."""
        try:
            sales_doc_id = data.get("sales_doc_id")
            if not sales_doc_id:
                return {"success": False, "error": "sales_doc_id required"}

            with DatabaseModel() as db:
                r_seq = db.execute_query(
                    "SELECT AGRO_EXPORT_DECLARATIONS_SEQ.NEXTVAL AS NID FROM DUAL", {}
                )
                new_id = _norm_rows(r_seq)[0]["nid"]
                today = datetime.now().strftime("%Y%m%d")
                decl_number = f"EXP-{today}-{int(new_id):04d}"

                db.execute_query(
                    """INSERT INTO AGRO_EXPORT_DECLARATIONS
                       (ID, SALES_DOC_ID, DECL_NUMBER, DESTINATION_COUNTRY,
                        CUSTOMS_CODE, TRANSPORT_CONDITIONS,
                        PHYTO_CERT_NUMBER, VET_CERT_NUMBER, NOTES)
                       VALUES (:id, :sdid, :dnum, :country,
                               :customs, :transport, :phyto, :vet, :notes)""",
                    {
                        "id": new_id, "sdid": sales_doc_id, "dnum": decl_number,
                        "country": data.get("destination_country"),
                        "customs": data.get("customs_code"),
                        "transport": data.get("transport_conditions"),
                        "phyto": data.get("phyto_cert_number"),
                        "vet": data.get("vet_cert_number"),
                        "notes": data.get("notes"),
                    },
                )
                db.connection.commit()
                return {"success": True, "id": int(new_id), "decl_number": decl_number}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_export_decl(decl_id: int) -> Dict[str, Any]:
        """Get export declaration with sales doc info."""
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    """SELECT ed.*, sd.DOC_NUMBER AS SALES_DOC_NUMBER, c.NAME AS CUSTOMER_NAME
                       FROM AGRO_EXPORT_DECLARATIONS ed
                       JOIN AGRO_SALES_DOCS sd ON ed.SALES_DOC_ID = sd.ID
                       LEFT JOIN AGRO_CUSTOMERS c ON sd.CUSTOMER_ID = c.ID
                       WHERE ed.ID = :did""",
                    {"did": decl_id},
                )
                rows = _norm_rows(r)
                if not rows:
                    return {"success": False, "error": "Declaration not found"}
                return {"success": True, "data": rows[0]}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def update_export_decl(data: Dict[str, Any]) -> Dict[str, Any]:
        """Update export declaration fields."""
        try:
            decl_id = data.get("id")
            if not decl_id:
                return {"success": False, "error": "id required"}

            with DatabaseModel() as db:
                fields = []
                params: Dict[str, Any] = {"did": decl_id}
                for col in ("destination_country", "customs_code", "transport_conditions",
                            "phyto_cert_number", "vet_cert_number", "notes"):
                    if col in data:
                        fields.append(f"{col.upper()} = :{col}")
                        params[col] = data[col]
                if not fields:
                    return {"success": False, "error": "No fields to update"}

                sql = f"UPDATE AGRO_EXPORT_DECLARATIONS SET {', '.join(fields)} WHERE ID = :did"
                db.execute_query(sql, params)
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
