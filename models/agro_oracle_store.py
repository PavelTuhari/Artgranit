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
    "AGRO_ITEM_VARIETIES",
    "AGRO_ACCEPTANCE_PROFILES",
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
    # 12. AGRO_ITEM_VARIETIES
    # ==================================================================

    @staticmethod
    def get_item_varieties(
        item_id: Optional[int] = None, active_only: bool = False
    ) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                sql = """SELECT v.*, i.CODE AS ITEM_CODE, i.NAME_RU AS ITEM_NAME_RU
                         FROM AGRO_ITEM_VARIETIES v
                         JOIN AGRO_ITEMS i ON i.ID = v.ITEM_ID"""
                params: Dict[str, Any] = {}
                conditions: List[str] = []
                if item_id:
                    conditions.append("v.ITEM_ID = :item_id")
                    params["item_id"] = item_id
                if active_only:
                    conditions.append("v.ACTIVE = 'Y'")
                if conditions:
                    sql += " WHERE " + " AND ".join(conditions)
                sql += " ORDER BY i.NAME_RU, v.NAME_RU"
                r = db.execute_query(sql, params or None)
                return {"success": True, "data": _norm_rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_item_variety(record_id: int) -> Dict[str, Any]:
        return AgroStore._get_by_id("AGRO_ITEM_VARIETIES", record_id)

    @staticmethod
    def upsert_item_variety(data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                params = {
                    "item_id": data.get("item_id"),
                    "code": data.get("code"),
                    "name_ru": data.get("name_ru"),
                    "name_ro": data.get("name_ro"),
                    "min_calibre_mm": data.get("min_calibre_mm"),
                    "min_brix": data.get("min_brix"),
                    "shelf_life_days": data.get("shelf_life_days"),
                    "optimal_temp_min": data.get("optimal_temp_min"),
                    "optimal_temp_max": data.get("optimal_temp_max"),
                    "color_coverage_pct": data.get("color_coverage_pct"),
                    "notes": data.get("notes"),
                    "active": data.get("active", "Y"),
                }
                if data.get("id"):
                    params["id"] = data["id"]
                    db.execute_query(
                        """UPDATE AGRO_ITEM_VARIETIES
                              SET ITEM_ID = :item_id, CODE = :code,
                                  NAME_RU = :name_ru, NAME_RO = :name_ro,
                                  MIN_CALIBRE_MM = :min_calibre_mm, MIN_BRIX = :min_brix,
                                  SHELF_LIFE_DAYS = :shelf_life_days,
                                  OPTIMAL_TEMP_MIN = :optimal_temp_min,
                                  OPTIMAL_TEMP_MAX = :optimal_temp_max,
                                  COLOR_COVERAGE_PCT = :color_coverage_pct,
                                  NOTES = :notes, ACTIVE = :active
                            WHERE ID = :id""",
                        params,
                    )
                else:
                    db.execute_query(
                        """INSERT INTO AGRO_ITEM_VARIETIES
                                  (ID, ITEM_ID, CODE, NAME_RU, NAME_RO,
                                   MIN_CALIBRE_MM, MIN_BRIX, SHELF_LIFE_DAYS,
                                   OPTIMAL_TEMP_MIN, OPTIMAL_TEMP_MAX,
                                   COLOR_COVERAGE_PCT, NOTES, ACTIVE)
                           VALUES (AGRO_ITEM_VARIETIES_SEQ.NEXTVAL,
                                   :item_id, :code, :name_ru, :name_ro,
                                   :min_calibre_mm, :min_brix, :shelf_life_days,
                                   :optimal_temp_min, :optimal_temp_max,
                                   :color_coverage_pct, :notes, :active)""",
                        params,
                    )
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def delete_item_variety(record_id: int) -> Dict[str, Any]:
        return AgroStore._delete("AGRO_ITEM_VARIETIES", record_id)

    # ==================================================================
    # 13. AGRO_ACCEPTANCE_PROFILES
    # ==================================================================

    @staticmethod
    def get_acceptance_profiles(active_only: bool = False) -> Dict[str, Any]:
        return AgroStore._get_all("AGRO_ACCEPTANCE_PROFILES", active_only, "NAME_RU")

    @staticmethod
    def get_acceptance_profile(record_id: int) -> Dict[str, Any]:
        return AgroStore._get_by_id("AGRO_ACCEPTANCE_PROFILES", record_id)

    @staticmethod
    def upsert_acceptance_profile(data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                params = {
                    "code": data.get("code"),
                    "name_ru": data.get("name_ru"),
                    "name_ro": data.get("name_ro"),
                    "customer_id": data.get("customer_id"),
                    "required_class": data.get("required_class", "I"),
                    "allow_class_ii": data.get("allow_class_ii", "N"),
                    "min_calibre_mm": data.get("min_calibre_mm"),
                    "max_below_min_pct": data.get("max_below_min_pct"),
                    "max_mixed_size_pct": data.get("max_mixed_size_pct"),
                    "max_minor_defects_pct": data.get("max_minor_defects_pct"),
                    "max_serious_defects_pct": data.get("max_serious_defects_pct"),
                    "min_brix": data.get("min_brix"),
                    "temp_min_c": data.get("temp_min_c"),
                    "temp_max_c": data.get("temp_max_c"),
                    "lab_req": data.get("lab_req", "N"),
                    "phyto_req": data.get("phyto_req", "N"),
                    "trace_req": data.get("trace_req", "N"),
                    "pack_req": data.get("pack_req", "N"),
                    "label_req": data.get("label_req", "N"),
                    "max_actives": data.get("max_actives"),
                    "max_single_residue_pct_mrl": data.get("max_single_residue_pct_mrl"),
                    "max_total_residue_pct": data.get("max_total_residue_pct"),
                    "max_glyphosate_pct_mrl": data.get("max_glyphosate_pct_mrl"),
                    "accept_min_score": data.get("accept_min_score", 85),
                    "active": data.get("active", "Y"),
                }
                if data.get("id"):
                    params["id"] = data["id"]
                    db.execute_query(
                        """UPDATE AGRO_ACCEPTANCE_PROFILES
                              SET CODE = :code, NAME_RU = :name_ru, NAME_RO = :name_ro,
                                  CUSTOMER_ID = :customer_id, REQUIRED_CLASS = :required_class,
                                  ALLOW_CLASS_II = :allow_class_ii,
                                  MIN_CALIBRE_MM = :min_calibre_mm,
                                  MAX_BELOW_MIN_PCT = :max_below_min_pct,
                                  MAX_MIXED_SIZE_PCT = :max_mixed_size_pct,
                                  MAX_MINOR_DEFECTS_PCT = :max_minor_defects_pct,
                                  MAX_SERIOUS_DEFECTS_PCT = :max_serious_defects_pct,
                                  MIN_BRIX = :min_brix,
                                  TEMP_MIN_C = :temp_min_c, TEMP_MAX_C = :temp_max_c,
                                  LAB_REQ = :lab_req, PHYTO_REQ = :phyto_req,
                                  TRACE_REQ = :trace_req, PACK_REQ = :pack_req,
                                  LABEL_REQ = :label_req,
                                  MAX_ACTIVES = :max_actives,
                                  MAX_SINGLE_RESIDUE_PCT_MRL = :max_single_residue_pct_mrl,
                                  MAX_TOTAL_RESIDUE_PCT = :max_total_residue_pct,
                                  MAX_GLYPHOSATE_PCT_MRL = :max_glyphosate_pct_mrl,
                                  ACCEPT_MIN_SCORE = :accept_min_score,
                                  ACTIVE = :active
                            WHERE ID = :id""",
                        params,
                    )
                else:
                    db.execute_query(
                        """INSERT INTO AGRO_ACCEPTANCE_PROFILES
                                  (ID, CODE, NAME_RU, NAME_RO, CUSTOMER_ID,
                                   REQUIRED_CLASS, ALLOW_CLASS_II,
                                   MIN_CALIBRE_MM, MAX_BELOW_MIN_PCT, MAX_MIXED_SIZE_PCT,
                                   MAX_MINOR_DEFECTS_PCT, MAX_SERIOUS_DEFECTS_PCT,
                                   MIN_BRIX, TEMP_MIN_C, TEMP_MAX_C,
                                   LAB_REQ, PHYTO_REQ, TRACE_REQ, PACK_REQ, LABEL_REQ,
                                   MAX_ACTIVES, MAX_SINGLE_RESIDUE_PCT_MRL,
                                   MAX_TOTAL_RESIDUE_PCT, MAX_GLYPHOSATE_PCT_MRL,
                                   ACCEPT_MIN_SCORE, ACTIVE)
                           VALUES (AGRO_ACCEPTANCE_PROFILES_SEQ.NEXTVAL,
                                   :code, :name_ru, :name_ro, :customer_id,
                                   :required_class, :allow_class_ii,
                                   :min_calibre_mm, :max_below_min_pct, :max_mixed_size_pct,
                                   :max_minor_defects_pct, :max_serious_defects_pct,
                                   :min_brix, :temp_min_c, :temp_max_c,
                                   :lab_req, :phyto_req, :trace_req, :pack_req, :label_req,
                                   :max_actives, :max_single_residue_pct_mrl,
                                   :max_total_residue_pct, :max_glyphosate_pct_mrl,
                                   :accept_min_score, :active)""",
                        params,
                    )
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def delete_acceptance_profile(record_id: int) -> Dict[str, Any]:
        return AgroStore._delete("AGRO_ACCEPTANCE_PROFILES", record_id)

    # ==================================================================
    # 14. AGRO_FIELD_REQUESTS (header + lines)
    # ==================================================================

    @staticmethod
    def get_field_requests(
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                sql = """SELECT fr.*,
                                s.NAME   AS SUPPLIER_NAME,
                                w.NAME   AS WAREHOUSE_NAME,
                                ap.NAME_RU AS PROFILE_NAME,
                                (SELECT COUNT(*) FROM AGRO_FIELD_REQUEST_LINES frl
                                 WHERE frl.REQUEST_ID = fr.ID) AS LINE_COUNT,
                                (SELECT SUM(frl.EXPECTED_QTY_KG) FROM AGRO_FIELD_REQUEST_LINES frl
                                 WHERE frl.REQUEST_ID = fr.ID) AS TOTAL_EXPECTED_KG
                         FROM AGRO_FIELD_REQUESTS fr
                         LEFT JOIN AGRO_SUPPLIERS s ON s.ID = fr.SUPPLIER_ID
                         LEFT JOIN AGRO_WAREHOUSES w ON w.ID = fr.WAREHOUSE_ID
                         LEFT JOIN AGRO_ACCEPTANCE_PROFILES ap ON ap.ID = fr.PROFILE_ID
                         WHERE 1=1"""
                params: Dict[str, Any] = {}
                if filters:
                    if filters.get("status"):
                        sql += " AND fr.STATUS = :status"
                        params["status"] = filters["status"]
                    if filters.get("supplier_id"):
                        sql += " AND fr.SUPPLIER_ID = :supplier_id"
                        params["supplier_id"] = filters["supplier_id"]
                    if filters.get("date_from"):
                        sql += " AND fr.REQUEST_DATE >= TO_DATE(:date_from, 'YYYY-MM-DD')"
                        params["date_from"] = filters["date_from"]
                    if filters.get("date_to"):
                        sql += " AND fr.REQUEST_DATE <= TO_DATE(:date_to, 'YYYY-MM-DD')"
                        params["date_to"] = filters["date_to"]
                sql += " ORDER BY fr.REQUEST_DATE DESC, fr.ID DESC"
                r = db.execute_query(sql, params or None)
                return {"success": True, "data": _norm_rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_field_request_by_id(request_id: int) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                rh = db.execute_query(
                    """SELECT fr.*,
                              s.NAME   AS SUPPLIER_NAME,
                              w.NAME   AS WAREHOUSE_NAME,
                              ap.NAME_RU AS PROFILE_NAME
                       FROM AGRO_FIELD_REQUESTS fr
                       LEFT JOIN AGRO_SUPPLIERS s ON s.ID = fr.SUPPLIER_ID
                       LEFT JOIN AGRO_WAREHOUSES w ON w.ID = fr.WAREHOUSE_ID
                       LEFT JOIN AGRO_ACCEPTANCE_PROFILES ap ON ap.ID = fr.PROFILE_ID
                       WHERE fr.ID = :id""",
                    {"id": request_id},
                )
                headers = _norm_rows(rh)
                if not headers:
                    return {"success": False, "error": "Request not found"}
                rl = db.execute_query(
                    """SELECT frl.*,
                              i.CODE AS ITEM_CODE, i.NAME_RU AS ITEM_NAME_RU,
                              v.CODE AS VARIETY_CODE, v.NAME_RU AS VARIETY_NAME_RU
                       FROM AGRO_FIELD_REQUEST_LINES frl
                       JOIN AGRO_ITEMS i ON i.ID = frl.ITEM_ID
                       LEFT JOIN AGRO_ITEM_VARIETIES v ON v.ID = frl.VARIETY_ID
                       WHERE frl.REQUEST_ID = :id
                       ORDER BY frl.ID""",
                    {"id": request_id},
                )
                lines = _norm_rows(rl)
                return {
                    "success": True,
                    "data": {"header": headers[0], "lines": lines},
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def create_field_request(data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                r_seq = db.execute_query(
                    "SELECT AGRO_FIELD_REQUESTS_SEQ.NEXTVAL AS SEQ_VAL FROM DUAL", None
                )
                req_id = int(_norm_rows(r_seq)[0]["seq_val"])
                today_str = datetime.now().strftime("%Y%m%d")
                req_number = data.get("request_number") or f"REQ-{today_str}-{req_id:04d}"
                req_date = data.get("request_date") or datetime.now().strftime("%Y-%m-%d")

                db.execute_query(
                    """INSERT INTO AGRO_FIELD_REQUESTS
                              (ID, REQUEST_NUMBER, REQUEST_DATE, EXPECTED_DATE,
                               SUPPLIER_ID, WAREHOUSE_ID, PROFILE_ID,
                               STATUS, NOTES, CREATED_BY)
                       VALUES (:id, :request_number, TO_DATE(:request_date, 'YYYY-MM-DD'),
                               TO_DATE(:expected_date, 'YYYY-MM-DD'),
                               :supplier_id, :warehouse_id, :profile_id,
                               :status, :notes, :created_by)""",
                    {
                        "id": req_id,
                        "request_number": req_number,
                        "request_date": req_date,
                        "expected_date": data.get("expected_date"),
                        "supplier_id": data.get("supplier_id"),
                        "warehouse_id": data.get("warehouse_id"),
                        "profile_id": data.get("profile_id"),
                        "status": data.get("status", "draft"),
                        "notes": data.get("notes"),
                        "created_by": data.get("created_by"),
                    },
                )
                for ln in data.get("lines", []):
                    db.execute_query(
                        """INSERT INTO AGRO_FIELD_REQUEST_LINES
                                  (ID, REQUEST_ID, ITEM_ID, VARIETY_ID,
                                   EXPECTED_QTY_KG, PRICE_LIMIT_PER_KG, NOTES)
                           VALUES (AGRO_FIELD_REQUEST_LINES_SEQ.NEXTVAL, :request_id,
                                   :item_id, :variety_id,
                                   :expected_qty_kg, :price_limit_per_kg, :notes)""",
                        {
                            "request_id": req_id,
                            "item_id": ln.get("item_id"),
                            "variety_id": ln.get("variety_id"),
                            "expected_qty_kg": ln.get("expected_qty_kg"),
                            "price_limit_per_kg": ln.get("price_limit_per_kg"),
                            "notes": ln.get("notes"),
                        },
                    )
                db.connection.commit()
                return {"success": True, "data": {"request_id": req_id, "request_number": req_number}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def update_field_request(data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                req_id = data["id"]
                db.execute_query(
                    """UPDATE AGRO_FIELD_REQUESTS
                          SET REQUEST_DATE = TO_DATE(:request_date, 'YYYY-MM-DD'),
                              EXPECTED_DATE = TO_DATE(:expected_date, 'YYYY-MM-DD'),
                              SUPPLIER_ID = :supplier_id, WAREHOUSE_ID = :warehouse_id,
                              PROFILE_ID = :profile_id, NOTES = :notes
                        WHERE ID = :id AND STATUS = 'draft'""",
                    {
                        "id": req_id,
                        "request_date": data.get("request_date"),
                        "expected_date": data.get("expected_date"),
                        "supplier_id": data.get("supplier_id"),
                        "warehouse_id": data.get("warehouse_id"),
                        "profile_id": data.get("profile_id"),
                        "notes": data.get("notes"),
                    },
                )
                db.execute_query(
                    "DELETE FROM AGRO_FIELD_REQUEST_LINES WHERE REQUEST_ID = :id",
                    {"id": req_id},
                )
                for ln in data.get("lines", []):
                    db.execute_query(
                        """INSERT INTO AGRO_FIELD_REQUEST_LINES
                                  (ID, REQUEST_ID, ITEM_ID, VARIETY_ID,
                                   EXPECTED_QTY_KG, PRICE_LIMIT_PER_KG, NOTES)
                           VALUES (AGRO_FIELD_REQUEST_LINES_SEQ.NEXTVAL, :request_id,
                                   :item_id, :variety_id,
                                   :expected_qty_kg, :price_limit_per_kg, :notes)""",
                        {
                            "request_id": req_id,
                            "item_id": ln.get("item_id"),
                            "variety_id": ln.get("variety_id"),
                            "expected_qty_kg": ln.get("expected_qty_kg"),
                            "price_limit_per_kg": ln.get("price_limit_per_kg"),
                            "notes": ln.get("notes"),
                        },
                    )
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def approve_field_request(request_id: int, approved_by: Optional[str] = None) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                db.execute_query(
                    """UPDATE AGRO_FIELD_REQUESTS
                          SET STATUS = 'approved', APPROVED_BY = :approved_by,
                              APPROVED_AT = SYSTIMESTAMP
                        WHERE ID = :id AND STATUS = 'draft'""",
                    {"id": request_id, "approved_by": approved_by},
                )
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def cancel_field_request(request_id: int) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                db.execute_query(
                    """UPDATE AGRO_FIELD_REQUESTS
                          SET STATUS = 'cancelled'
                        WHERE ID = :id AND STATUS IN ('draft', 'approved')""",
                    {"id": request_id},
                )
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ==================================================================
    # 15. AGRO_BATCH_INSPECTIONS — acceptance scoring engine
    # ==================================================================

    # Scoring weights per procurement standards
    _SCORING_WEIGHTS = {
        "CLASS_OK": 10, "CALIBRE_OK": 8, "BELOW_MIN_OK": 5,
        "MINOR_OK": 8, "SERIOUS_OK": 15, "MIXED_OK": 4,
        "BRIX_OK": 5, "TEMP_OK": 10, "LAB_OK": 8,
        "PHYTO_OK": 4, "TRACE_OK": 6, "PACK_OK": 3,
        "LABEL_OK": 2, "ACTIVES_OK": 2, "SINGLE_RESIDUE_OK": 2,
        "TOTAL_RESIDUE_OK": 2, "GLYPHOSATE_OK": 1,
    }
    _CRITICAL_CHECKS = {"CLASS_OK", "SERIOUS_OK", "TEMP_OK", "LAB_OK", "PHYTO_OK", "TRACE_OK"}

    @staticmethod
    def _class_to_num(cls_str: str) -> int:
        return {"Extra": 3, "I": 2, "II": 1}.get(cls_str, 0)

    @staticmethod
    def perform_batch_inspection(data: Dict[str, Any]) -> Dict[str, Any]:
        """Run acceptance inspection with weighted scoring engine."""
        try:
            with DatabaseModel() as db:
                batch_id = data["batch_id"]
                profile_id = data["profile_id"]
                m = data.get("measurements", {})
                freshness = float(data.get("freshness_score", 0))

                # Load profile thresholds
                rp = db.execute_query(
                    "SELECT * FROM AGRO_ACCEPTANCE_PROFILES WHERE ID = :id",
                    {"id": profile_id},
                )
                prows = _norm_rows(rp)
                if not prows:
                    return {"success": False, "error": "Profile not found"}
                prof = prows[0]

                # Build checks list: (code, label, measured, threshold, is_pass, is_critical, weight)
                checks: List[Dict[str, Any]] = []

                def _add_check(code: str, label: str, measured, threshold, is_pass: bool):
                    is_crit = code in AgroStore._CRITICAL_CHECKS
                    weight = AgroStore._SCORING_WEIGHTS.get(code, 0)
                    checks.append({
                        "code": code, "label": label,
                        "measured": str(measured) if measured is not None else "",
                        "threshold": str(threshold) if threshold is not None else "",
                        "is_pass": is_pass, "is_critical": is_crit, "weight": weight,
                    })

                # 1. Class
                declared = m.get("quality_class", "I")
                req = prof.get("required_class", "I")
                _add_check("CLASS_OK", "Товарный класс", declared, f">= {req}",
                           AgroStore._class_to_num(declared) >= AgroStore._class_to_num(req))

                # 2. Calibre
                cal = m.get("calibre_avg_mm")
                min_cal = prof.get("min_calibre_mm")
                _add_check("CALIBRE_OK", "Калибр средний", cal, f">= {min_cal}",
                           float(cal or 0) >= float(min_cal or 0) if cal is not None and min_cal else True)

                # 3. Below minimum %
                bm = m.get("below_min_pct")
                max_bm = prof.get("max_below_min_pct")
                _add_check("BELOW_MIN_OK", "Ниже мин. калибра %", bm, f"<= {max_bm}",
                           float(bm or 0) <= float(max_bm or 100) if bm is not None else True)

                # 4. Minor defects
                minor = m.get("minor_defects_pct")
                max_minor = prof.get("max_minor_defects_pct")
                _add_check("MINOR_OK", "Мелкие дефекты %", minor, f"<= {max_minor}",
                           float(minor or 0) <= float(max_minor or 100) if minor is not None else True)

                # 5. Serious defects
                serious = m.get("serious_defects_pct")
                max_ser = prof.get("max_serious_defects_pct")
                _add_check("SERIOUS_OK", "Серьёзные дефекты %", serious, f"<= {max_ser}",
                           float(serious or 0) <= float(max_ser or 100) if serious is not None else True)

                # 6. Mixed size
                mixed = m.get("mixed_size_pct")
                max_mix = prof.get("max_mixed_size_pct")
                _add_check("MIXED_OK", "Разнородность размера %", mixed, f"<= {max_mix}",
                           float(mixed or 0) <= float(max_mix or 100) if mixed is not None else True)

                # 7. Brix
                brix = m.get("brix")
                min_brix = prof.get("min_brix")
                _add_check("BRIX_OK", "Brix (сахаристость)", brix, f">= {min_brix}",
                           float(brix or 0) >= float(min_brix or 0) if brix is not None and min_brix else True)

                # 8. Temperature
                temp = m.get("temp_c")
                t_min = prof.get("temp_min_c")
                t_max = prof.get("temp_max_c")
                temp_pass = True
                if temp is not None and t_min is not None and t_max is not None:
                    temp_pass = float(t_min) <= float(temp) <= float(t_max)
                _add_check("TEMP_OK", "Температура C", temp, f"{t_min}-{t_max}°C", temp_pass)

                # 9-13. Document checks
                for code, label, field, req_field in [
                    ("LAB_OK", "Лабораторный отчёт", "has_lab", "lab_req"),
                    ("PHYTO_OK", "Фитосанитарный", "has_phyto", "phyto_req"),
                    ("TRACE_OK", "Прослеживаемость", "has_trace", "trace_req"),
                    ("PACK_OK", "Упаковка", "has_pack", "pack_req"),
                    ("LABEL_OK", "Маркировка", "has_label", "label_req"),
                ]:
                    has_doc = m.get(field, False)
                    required = prof.get(req_field, "N") == "Y"
                    _add_check(code, label, "Да" if has_doc else "Нет",
                               "Требуется" if required else "Не требуется",
                               has_doc or not required)

                # 14-17. Pesticide checks
                actives = m.get("actives_count")
                max_act = prof.get("max_actives")
                _add_check("ACTIVES_OK", "Акт. вещества (кол-во)", actives, f"<= {max_act}",
                           int(actives or 0) <= int(max_act or 999) if actives is not None and max_act else True)

                sr = m.get("single_residue_pct_mrl")
                max_sr = prof.get("max_single_residue_pct_mrl")
                _add_check("SINGLE_RESIDUE_OK", "Макс. остаток % MRL", sr, f"<= {max_sr}",
                           float(sr or 0) <= float(max_sr or 100) if sr is not None and max_sr else True)

                tr = m.get("total_residue_pct")
                max_tr = prof.get("max_total_residue_pct")
                _add_check("TOTAL_RESIDUE_OK", "Общий индекс остатков %", tr, f"<= {max_tr}",
                           float(tr or 0) <= float(max_tr or 100) if tr is not None and max_tr else True)

                gly = m.get("glyphosate_pct_mrl")
                max_gly = prof.get("max_glyphosate_pct_mrl")
                _add_check("GLYPHOSATE_OK", "Глифосат % MRL", gly, f"<= {max_gly}",
                           float(gly or 0) <= float(max_gly or 100) if gly is not None and max_gly else True)

                # Calculate score
                total_score = freshness  # Freshness contributes 0-5 directly
                critical_fails = 0
                all_pass = True
                for chk in checks:
                    if chk["is_pass"]:
                        chk["score_contribution"] = chk["weight"]
                    else:
                        chk["score_contribution"] = 0
                        all_pass = False
                        if chk["is_critical"]:
                            critical_fails += 1
                    total_score += chk["score_contribution"]

                # Decision
                accept_min = float(prof.get("accept_min_score", 85))
                if critical_fails > 0:
                    decision = "REJECT"
                elif all_pass:
                    decision = "ACCEPT"
                elif total_score >= accept_min:
                    decision = "ACCEPT_WITH_SORTING"
                else:
                    decision = "REJECT"

                # Insert inspection header
                r_seq = db.execute_query(
                    "SELECT AGRO_BATCH_INSPECTIONS_SEQ.NEXTVAL AS SEQ_VAL FROM DUAL", None
                )
                insp_id = int(_norm_rows(r_seq)[0]["seq_val"])

                db.execute_query(
                    """INSERT INTO AGRO_BATCH_INSPECTIONS
                              (ID, BATCH_ID, PROFILE_ID, VARIETY_ID, INSPECTION_DATE,
                               INSPECTOR, TOTAL_SCORE, CRITICAL_FAILS, DECISION,
                               FRESHNESS_SCORE, NOTES)
                       VALUES (:id, :batch_id, :profile_id, :variety_id,
                               TRUNC(SYSDATE), :inspector,
                               :total_score, :critical_fails, :decision,
                               :freshness_score, :notes)""",
                    {
                        "id": insp_id,
                        "batch_id": batch_id,
                        "profile_id": profile_id,
                        "variety_id": data.get("variety_id"),
                        "inspector": data.get("inspector"),
                        "total_score": round(total_score, 2),
                        "critical_fails": critical_fails,
                        "decision": decision,
                        "freshness_score": freshness,
                        "notes": data.get("notes"),
                    },
                )

                # Insert check values
                for chk in checks:
                    db.execute_query(
                        """INSERT INTO AGRO_BATCH_INSPECTION_VALUES
                                  (ID, INSPECTION_ID, PARAM_CODE, PARAM_LABEL,
                                   MEASURED_VALUE, THRESHOLD_VALUE,
                                   IS_PASS, IS_CRITICAL, WEIGHT, SCORE_CONTRIBUTION)
                           VALUES (AGRO_BATCH_INSPECTION_VALUES_SEQ.NEXTVAL,
                                   :inspection_id, :param_code, :param_label,
                                   :measured_value, :threshold_value,
                                   :is_pass, :is_critical, :weight, :score_contribution)""",
                        {
                            "inspection_id": insp_id,
                            "param_code": chk["code"],
                            "param_label": chk["label"],
                            "measured_value": chk["measured"],
                            "threshold_value": chk["threshold"],
                            "is_pass": "Y" if chk["is_pass"] else "N",
                            "is_critical": "Y" if chk["is_critical"] else "N",
                            "weight": chk["weight"],
                            "score_contribution": chk["score_contribution"],
                        },
                    )

                # If REJECT, block the batch
                if decision == "REJECT":
                    db.execute_query(
                        """INSERT INTO AGRO_BATCH_BLOCKS
                                  (ID, BATCH_ID, BLOCK_REASON, BLOCKED_BY)
                           VALUES (AGRO_BATCH_BLOCKS_SEQ.NEXTVAL,
                                   :batch_id, :reason, :blocked_by)""",
                        {
                            "batch_id": batch_id,
                            "reason": f"Inspection #{insp_id}: REJECT (score={round(total_score, 2)}, critical_fails={critical_fails})",
                            "blocked_by": data.get("inspector"),
                        },
                    )
                    db.execute_query(
                        "UPDATE AGRO_BATCHES SET STATUS = 'blocked' WHERE ID = :id",
                        {"id": batch_id},
                    )

                db.connection.commit()
                return {
                    "success": True,
                    "data": {
                        "inspection_id": insp_id,
                        "total_score": round(total_score, 2),
                        "critical_fails": critical_fails,
                        "decision": decision,
                        "checks": checks,
                    },
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_batch_inspections(batch_id: Optional[int] = None) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                sql = """SELECT bi.*, b.BATCH_NUMBER, i.NAME_RU AS ITEM_NAME,
                                ap.NAME_RU AS PROFILE_NAME
                         FROM AGRO_BATCH_INSPECTIONS bi
                         JOIN AGRO_BATCHES b ON b.ID = bi.BATCH_ID
                         JOIN AGRO_ITEMS i ON i.ID = b.ITEM_ID
                         JOIN AGRO_ACCEPTANCE_PROFILES ap ON ap.ID = bi.PROFILE_ID"""
                params: Dict[str, Any] = {}
                if batch_id:
                    sql += " WHERE bi.BATCH_ID = :batch_id"
                    params["batch_id"] = batch_id
                sql += " ORDER BY bi.INSPECTION_DATE DESC, bi.ID DESC"
                r = db.execute_query(sql, params or None)
                return {"success": True, "data": _norm_rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_batch_inspection_detail(inspection_id: int) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                rh = db.execute_query(
                    """SELECT bi.*, b.BATCH_NUMBER, i.NAME_RU AS ITEM_NAME,
                              ap.NAME_RU AS PROFILE_NAME,
                              v.NAME_RU AS VARIETY_NAME
                       FROM AGRO_BATCH_INSPECTIONS bi
                       JOIN AGRO_BATCHES b ON b.ID = bi.BATCH_ID
                       JOIN AGRO_ITEMS i ON i.ID = b.ITEM_ID
                       JOIN AGRO_ACCEPTANCE_PROFILES ap ON ap.ID = bi.PROFILE_ID
                       LEFT JOIN AGRO_ITEM_VARIETIES v ON v.ID = bi.VARIETY_ID
                       WHERE bi.ID = :id""",
                    {"id": inspection_id},
                )
                headers = _norm_rows(rh)
                if not headers:
                    return {"success": False, "error": "Inspection not found"}
                rv = db.execute_query(
                    """SELECT * FROM AGRO_BATCH_INSPECTION_VALUES
                       WHERE INSPECTION_ID = :id ORDER BY ID""",
                    {"id": inspection_id},
                )
                values = _norm_rows(rv)
                return {
                    "success": True,
                    "data": {"header": headers[0], "values": values},
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

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
                today_str = datetime.now().strftime("%Y%m%d")
                doc_number = data.get("doc_number") or f"PUR-{today_str}-{doc_id:04d}"

                doc_date = data.get("doc_date") or datetime.now().strftime("%Y-%m-%d")

                hdr_params = {
                    "id": doc_id,
                    "doc_number": doc_number,
                    "doc_date": doc_date,
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
                    "field_request_id": data.get("field_request_id"),
                }
                db.execute_query(
                    """INSERT INTO AGRO_PURCHASE_DOCS
                              (ID, DOC_NUMBER, DOC_DATE, SUPPLIER_ID, WAREHOUSE_ID,
                               VEHICLE_ID, CURRENCY_ID, STATUS,
                               TOTAL_GROSS_KG, TOTAL_NET_KG, TOTAL_AMOUNT,
                               ADVANCE_AMOUNT, TRANSFER_AMOUNT, E_FACTURA_REF,
                               ADDITIONAL_COSTS, NOTES, CREATED_BY, FIELD_REQUEST_ID)
                       VALUES (:id, :doc_number, TO_DATE(:doc_date, 'YYYY-MM-DD'),
                               :supplier_id, :warehouse_id,
                               :vehicle_id, :currency_id, :status,
                               :total_gross_kg, :total_net_kg, :total_amount,
                               :advance_amount, :transfer_amount, :e_factura_ref,
                               :additional_costs, :notes, :created_by, :field_request_id)""",
                    hdr_params,
                )

                for ln in lines:
                    db.execute_query(
                        """INSERT INTO AGRO_PURCHASE_LINES
                                  (ID, PURCHASE_DOC_ID, ITEM_ID, VARIETY_ID, PALLETS,
                                   CRATES_COUNT, GROSS_WEIGHT_KG, TARE_WEIGHT_KG,
                                   NET_WEIGHT_KG, PRICE_PER_KG, AMOUNT, NOTES)
                           VALUES (AGRO_PURCHASE_LINES_SEQ.NEXTVAL, :purchase_doc_id,
                                   :item_id, :variety_id, :pallets, :crates_count,
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
                return {"success": True, "data": {"doc_id": doc_id, "doc_number": doc_number}}
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
                                  (ID, PURCHASE_DOC_ID, ITEM_ID, VARIETY_ID, PALLETS,
                                   CRATES_COUNT, GROSS_WEIGHT_KG, TARE_WEIGHT_KG,
                                   NET_WEIGHT_KG, PRICE_PER_KG, AMOUNT, NOTES)
                           VALUES (AGRO_PURCHASE_LINES_SEQ.NEXTVAL, :purchase_doc_id,
                                   :item_id, :variety_id, :pallets, :crates_count,
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

                # Execute entire confirmation in a single PL/SQL block
                # to minimize Oracle round trips (critical for remote DB).
                plsql = """
                DECLARE
                    v_batch_id   NUMBER;
                    v_batch_num  VARCHAR2(100);
                    v_net_kg     NUMBER;
                    v_amount     NUMBER;
                    v_shelf_days NUMBER;
                    v_today      VARCHAR2(8) := TO_CHAR(SYSDATE, 'YYYYMMDD');
                    v_total_gross NUMBER := 0;
                    v_total_net   NUMBER := 0;
                    v_total_amt   NUMBER := 0;
                BEGIN
                    FOR ln IN (
                        SELECT pl.ID, pl.ITEM_ID, pl.GROSS_WEIGHT_KG,
                               NVL(pl.TARE_WEIGHT_KG, 0) AS TARE_WEIGHT_KG,
                               NVL(pl.PRICE_PER_KG, 0)   AS PRICE_PER_KG,
                               ai.SHELF_LIFE_DAYS
                        FROM AGRO_PURCHASE_LINES pl
                        LEFT JOIN AGRO_ITEMS ai ON ai.ID = pl.ITEM_ID
                        WHERE pl.PURCHASE_DOC_ID = :doc_id
                          AND pl.ITEM_ID IS NOT NULL
                          AND pl.GROSS_WEIGHT_KG IS NOT NULL
                        ORDER BY pl.ID
                    ) LOOP
                        v_net_kg := ln.GROSS_WEIGHT_KG - ln.TARE_WEIGHT_KG;
                        v_amount := ROUND(v_net_kg * ln.PRICE_PER_KG, 2);

                        UPDATE AGRO_PURCHASE_LINES
                           SET NET_WEIGHT_KG = v_net_kg, AMOUNT = v_amount
                         WHERE ID = ln.ID;

                        v_total_gross := v_total_gross + ln.GROSS_WEIGHT_KG;
                        v_total_net   := v_total_net   + v_net_kg;
                        v_total_amt   := v_total_amt   + v_amount;

                        SELECT AGRO_BATCHES_SEQ.NEXTVAL INTO v_batch_id FROM DUAL;
                        v_batch_num := 'B-' || v_today || '-' || LPAD(v_batch_id, 4, '0');

                        v_shelf_days := ln.SHELF_LIFE_DAYS;

                        INSERT INTO AGRO_BATCHES
                            (ID, BATCH_NUMBER, PURCHASE_LINE_ID, ITEM_ID,
                             WAREHOUSE_ID, INITIAL_QTY_KG, CURRENT_QTY_KG,
                             STATUS, EXPIRY_DATE)
                        VALUES
                            (v_batch_id, v_batch_num, ln.ID, ln.ITEM_ID,
                             :warehouse_id, v_net_kg, v_net_kg,
                             'active',
                             CASE WHEN v_shelf_days IS NOT NULL
                                  THEN SYSTIMESTAMP + v_shelf_days
                             END);

                        INSERT INTO AGRO_STOCK_MOVEMENTS
                            (ID, BATCH_ID, MOVEMENT_TYPE,
                             TO_WAREHOUSE_ID, QTY_KG, DOC_REF)
                        VALUES
                            (AGRO_STOCK_MOVEMENTS_SEQ.NEXTVAL, v_batch_id,
                             'receipt', :warehouse_id, v_net_kg,
                             'PD-' || :doc_id);
                    END LOOP;

                    UPDATE AGRO_PURCHASE_DOCS
                       SET STATUS = 'confirmed',
                           CONFIRMED_AT = SYSTIMESTAMP,
                           TOTAL_GROSS_KG = v_total_gross,
                           TOTAL_NET_KG   = v_total_net,
                           TOTAL_AMOUNT   = v_total_amt
                     WHERE ID = :doc_id;
                END;
                """
                db.execute_query(plsql, {
                    "doc_id": doc_id,
                    "warehouse_id": warehouse_id,
                })
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
                sql += " ORDER BY ITEM_NAME_RU, WAREHOUSE_NAME"
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
                    """SELECT b.*, i.NAME_RU AS ITEM_NAME, i.CODE AS ITEM_CODE,
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
                       LEFT JOIN AGRO_SALES_LINES sl ON ba.SALES_LINE_ID = sl.ID
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
                               :cell, :temp, :hum, :o2, :co2, :src, :sensor, :created_by)""",
                    {
                        "cell": cell_id,
                        "temp": data.get("temperature_c"),
                        "hum": data.get("humidity_pct"),
                        "o2": data.get("o2_pct"),
                        "co2": data.get("co2_pct"),
                        "src": data.get("reading_source", "manual"),
                        "sensor": data.get("sensor_id"),
                        "created_by": data.get("recorded_by"),
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
                sql = """SELECT pt.*, b.BATCH_NUMBER, i.NAME_RU AS ITEM_NAME
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
                r_seq = db.execute_query(
                    "SELECT AGRO_PROCESSING_TASKS_SEQ.NEXTVAL AS NID FROM DUAL", {})
                new_id = _norm_rows(r_seq)[0]["nid"]
                db.execute_query(
                    """INSERT INTO AGRO_PROCESSING_TASKS
                       (ID, BATCH_ID, TASK_TYPE, DESCRIPTION, ASSIGNED_TO, INPUT_QTY_KG, NOTES)
                       VALUES (:tid,
                               :bid, :ttype, :descr, :assigned, :input_qty, :notes)""",
                    {
                        "tid": new_id,
                        "bid": batch_id,
                        "ttype": task_type,
                        "descr": data.get("description"),
                        "assigned": data.get("assigned_to"),
                        "input_qty": data.get("input_qty_kg"),
                        "notes": data.get("notes"),
                    },
                )
                db.connection.commit()
                return {"success": True, "data": {"id": int(new_id)}}
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
                    """SELECT sl.*, i.NAME_RU AS ITEM_NAME, i.CODE AS ITEM_CODE
                       FROM AGRO_SALES_LINES sl
                       LEFT JOIN AGRO_ITEMS i ON sl.ITEM_ID = i.ID
                       WHERE sl.SALES_DOC_ID = :did ORDER BY sl.ID""",
                    {"did": doc_id},
                )
                lines = _norm_rows(r2)

                r3 = db.execute_query(
                    """SELECT ba.*, b.BATCH_NUMBER, b.CURRENT_QTY_KG
                       FROM AGRO_BATCH_ALLOCATIONS ba
                       JOIN AGRO_BATCHES b ON ba.BATCH_ID = b.ID
                       JOIN AGRO_SALES_LINES sl ON ba.SALES_LINE_ID = sl.ID
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
                               :veh, :cur, 0, 'draft', :notes, :created_by)""",
                    {
                        "id": new_id, "dnum": doc_number,
                        "cust": customer_id, "wh": warehouse_id,
                        "veh": data.get("vehicle_id"), "cur": data.get("currency_id"),
                        "notes": data.get("notes"), "created_by": data.get("created_by"),
                    },
                )

                total_amount = Decimal("0")
                for line in data.get("lines", []):
                    qty = Decimal(str(line.get("qty_kg", 0)))
                    price = Decimal(str(line.get("price_per_kg", 0)))
                    amount = (qty * price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    total_amount += amount

                    db.execute_query(
                        """INSERT INTO AGRO_SALES_LINES
                           (ID, SALES_DOC_ID, ITEM_ID, GROSS_WEIGHT_KG, NET_WEIGHT_KG,
                            PRICE_PER_KG, AMOUNT)
                           VALUES (AGRO_SALES_LINES_SEQ.NEXTVAL,
                                   :did, :iid, :gross_kg, :net_kg, :price, :amt)""",
                        {
                            "did": new_id, "iid": line.get("item_id"),
                            "gross_kg": float(qty), "net_kg": float(qty),
                            "price": float(price), "amt": float(amount),
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
                    "SELECT ID AS LINE_ID, ITEM_ID, NET_WEIGHT_KG AS QTY_KG FROM AGRO_SALES_LINES WHERE SALES_DOC_ID = :did",
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
                                i.NAME_RU AS ITEM_NAME, i.CODE AS ITEM_CODE,
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
                    "SELECT AGRO_EXPORT_DECLS_SEQ.NEXTVAL AS NID FROM DUAL", {}
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

    # ------------------------------------------------------------------
    # QA & HACCP
    # ------------------------------------------------------------------

    @staticmethod
    def get_checklists(checklist_type: str = None) -> Dict[str, Any]:
        """List QA checklists with item counts."""
        try:
            with DatabaseModel() as db:
                sql = """
                    SELECT c.ID, c.CODE, c.NAME_RU, c.NAME_RO, c.CHECKLIST_TYPE, c.ACTIVE,
                           (SELECT COUNT(*) FROM AGRO_QA_CHECKLIST_ITEMS ci WHERE ci.CHECKLIST_ID = c.ID) AS ITEM_COUNT
                    FROM AGRO_QA_CHECKLISTS c
                """
                params: Dict[str, Any] = {}
                if checklist_type:
                    sql += " WHERE c.CHECKLIST_TYPE = :ctype"
                    params["ctype"] = checklist_type
                sql += " ORDER BY c.NAME_RU"
                r = db.execute_query(sql, params)
                return {"success": True, "data": _norm_rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_checklist_by_id(cl_id: int) -> Dict[str, Any]:
        """Get checklist header + items."""
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    "SELECT * FROM AGRO_QA_CHECKLISTS WHERE ID = :cid",
                    {"cid": cl_id})
                rows = _norm_rows(r)
                if not rows:
                    return {"success": False, "error": "Checklist not found"}
                checklist = rows[0]
                r2 = db.execute_query(
                    "SELECT * FROM AGRO_QA_CHECKLIST_ITEMS WHERE CHECKLIST_ID = :cid ORDER BY ITEM_ORDER",
                    {"cid": cl_id})
                checklist["items"] = _norm_rows(r2)
                return {"success": True, "data": checklist}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def upsert_checklist(data: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update checklist + items."""
        try:
            with DatabaseModel() as db:
                cl_id = data.get("id")
                if cl_id:
                    db.execute_query(
                        """UPDATE AGRO_QA_CHECKLISTS SET CODE=:code, NAME_RU=:name_ru, NAME_RO=:name_ro,
                           CHECKLIST_TYPE=:ctype, ACTIVE=:active WHERE ID=:cid""",
                        {"cid": cl_id, "code": data.get("code", ""),
                         "name_ru": data.get("name") or data.get("name_ru", ""),
                         "name_ro": data.get("name_ro", ""),
                         "ctype": data.get("checklist_type", "incoming"),
                         "active": data.get("active", "Y")})
                else:
                    code = data.get("code") or f"CL-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    r_seq = db.execute_query(
                        "SELECT AGRO_QA_CHECKLISTS_SEQ.NEXTVAL AS ID FROM DUAL")
                    cl_id = int(_norm_rows(r_seq)[0]["id"])
                    db.execute_query(
                        """INSERT INTO AGRO_QA_CHECKLISTS (ID, CODE, NAME_RU, NAME_RO, CHECKLIST_TYPE, ACTIVE)
                           VALUES (:cid, :code, :name_ru, :name_ro, :ctype, :active)""",
                        {"cid": cl_id, "code": code,
                         "name_ru": data.get("name") or data.get("name_ru", ""),
                         "name_ro": data.get("name_ro", ""),
                         "ctype": data.get("checklist_type", "incoming"),
                         "active": data.get("active", "Y")})

                # Sync items
                items = data.get("items", [])
                if items:
                    db.execute_query(
                        "DELETE FROM AGRO_QA_CHECKLIST_ITEMS WHERE CHECKLIST_ID = :cid",
                        {"cid": cl_id})
                    for idx, item in enumerate(items):
                        db.execute_query(
                            """INSERT INTO AGRO_QA_CHECKLIST_ITEMS
                               (CHECKLIST_ID, ITEM_ORDER, PARAMETER_NAME_RU, PARAMETER_NAME_RO,
                                VALUE_TYPE, MIN_VALUE, MAX_VALUE, CHOICES, IS_CRITICAL)
                               VALUES (:cid, :sort, :pname_ru, :pname_ro,
                                :vtype, :minv, :maxv, :choices, :crit)""",
                            {"cid": cl_id, "sort": idx + 1,
                             "pname_ru": item.get("parameter_name_ru") or item.get("param_name", ""),
                             "pname_ro": item.get("parameter_name_ro", ""),
                             "vtype": item.get("value_type", "boolean"),
                             "minv": item.get("min_value"),
                             "maxv": item.get("max_value"),
                             "choices": item.get("choices", ""),
                             "crit": item.get("is_critical", "N")})
                db.connection.commit()
                return {"success": True, "data": {"id": cl_id}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def delete_checklist(cl_id: int) -> Dict[str, Any]:
        """Delete checklist and its items."""
        try:
            with DatabaseModel() as db:
                db.execute_query(
                    "DELETE FROM AGRO_QA_CHECKLIST_ITEMS WHERE CHECKLIST_ID = :cid",
                    {"cid": cl_id})
                db.execute_query(
                    "DELETE FROM AGRO_QA_CHECKLISTS WHERE ID = :cid",
                    {"cid": cl_id})
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def perform_check(data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute QA check: create check + values, auto-evaluate, auto-block on fail."""
        try:
            batch_id = data.get("batch_id")
            checklist_id = data.get("checklist_id")
            values = data.get("values", [])
            if not batch_id or not checklist_id:
                return {"success": False, "error": "batch_id and checklist_id required"}

            with DatabaseModel() as db:
                # Get checklist items to know criticality
                r = db.execute_query(
                    "SELECT ID, PARAMETER_NAME_RU, IS_CRITICAL FROM AGRO_QA_CHECKLIST_ITEMS WHERE CHECKLIST_ID = :cid ORDER BY ITEM_ORDER",
                    {"cid": checklist_id})
                cl_items = _norm_rows(r)
                critical_map = {it["id"]: it["is_critical"] for it in cl_items}

                # Determine result
                result = "pass"
                has_critical_fail = False
                has_non_critical_fail = False
                for v in values:
                    if v.get("is_compliant") == "N":
                        item_id = v.get("checklist_item_id")
                        if critical_map.get(item_id) == "Y":
                            has_critical_fail = True
                        else:
                            has_non_critical_fail = True

                if has_critical_fail:
                    result = "fail"
                elif has_non_critical_fail:
                    result = "conditional"

                # Pre-fetch check ID from sequence
                r_seq = db.execute_query(
                    "SELECT AGRO_QA_CHECKS_SEQ.NEXTVAL AS ID FROM DUAL")
                check_id = int(_norm_rows(r_seq)[0]["id"])

                # Insert check header
                db.execute_query(
                    """INSERT INTO AGRO_QA_CHECKS
                       (ID, BATCH_ID, CHECKLIST_ID, CHECK_DATE, RESULT, INSPECTOR, NOTES)
                       VALUES (:chk_id, :bid, :clid, TRUNC(SYSDATE), :result, :inspector, :notes)""",
                    {"chk_id": check_id, "bid": batch_id, "clid": checklist_id,
                     "result": result,
                     "inspector": data.get("checked_by") or data.get("inspector", "inspector"),
                     "notes": data.get("notes", "")})

                # Insert values
                for v in values:
                    db.execute_query(
                        """INSERT INTO AGRO_QA_CHECK_VALUES
                           (CHECK_ID, CHECKLIST_ITEM_ID, VALUE, IS_COMPLIANT)
                           VALUES (:chk, :cli, :val, :comp)""",
                        {"chk": check_id, "cli": v.get("checklist_item_id"),
                         "val": v.get("value") or v.get("actual_value", ""),
                         "comp": v.get("is_compliant", "Y")})

                # Auto-block on fail
                if result == "fail":
                    reason = f"QA check #{check_id} failed — critical non-compliance"
                    db.execute_query(
                        """INSERT INTO AGRO_BATCH_BLOCKS (BATCH_ID, REASON, BLOCKED_BY)
                           VALUES (:bid, :reason, :created_by)""",
                        {"bid": batch_id, "reason": reason,
                         "created_by": data.get("checked_by", "qa_system")})
                    db.execute_query(
                        """UPDATE AGRO_BATCHES SET STATUS='blocked',
                           BLOCKED_BY=:blocked_by, BLOCK_REASON=:reason WHERE ID=:bid""",
                        {"bid": batch_id, "reason": reason,
                         "blocked_by": data.get("checked_by", "qa_system")})

                db.connection.commit()
                return {"success": True, "data": {"check_id": check_id, "result": result}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_checks(batch_id: int = None) -> Dict[str, Any]:
        """Get QA check history, optionally filtered by batch."""
        try:
            with DatabaseModel() as db:
                sql = """
                    SELECT c.ID, c.BATCH_ID, c.CHECKLIST_ID, c.CHECK_DATE,
                           c.INSPECTOR, c.RESULT, c.NOTES, c.CREATED_AT,
                           b.BATCH_NUMBER, cl.NAME_RU AS CHECKLIST_NAME
                    FROM AGRO_QA_CHECKS c
                    LEFT JOIN AGRO_BATCHES b ON b.ID = c.BATCH_ID
                    LEFT JOIN AGRO_QA_CHECKLISTS cl ON cl.ID = c.CHECKLIST_ID
                """
                params: Dict[str, Any] = {}
                if batch_id:
                    sql += " WHERE c.BATCH_ID = :bid"
                    params["bid"] = batch_id
                sql += " ORDER BY c.CREATED_AT DESC"
                r = db.execute_query(sql, params)
                return {"success": True, "data": _norm_rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_check_detail(check_id: int) -> Dict[str, Any]:
        """Get check header + values."""
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    """SELECT c.*, b.BATCH_NUMBER, cl.NAME_RU AS CHECKLIST_NAME
                       FROM AGRO_QA_CHECKS c
                       LEFT JOIN AGRO_BATCHES b ON b.ID = c.BATCH_ID
                       LEFT JOIN AGRO_QA_CHECKLISTS cl ON cl.ID = c.CHECKLIST_ID
                       WHERE c.ID = :cid""",
                    {"cid": check_id})
                rows = _norm_rows(r)
                if not rows:
                    return {"success": False, "error": "Check not found"}
                check = rows[0]
                r2 = db.execute_query(
                    """SELECT v.*, ci.PARAMETER_NAME_RU, ci.PARAMETER_NAME_RO,
                              ci.VALUE_TYPE, ci.MIN_VALUE, ci.MAX_VALUE, ci.IS_CRITICAL
                       FROM AGRO_QA_CHECK_VALUES v
                       LEFT JOIN AGRO_QA_CHECKLIST_ITEMS ci ON ci.ID = v.CHECKLIST_ITEM_ID
                       WHERE v.CHECK_ID = :cid
                       ORDER BY ci.ITEM_ORDER""",
                    {"cid": check_id})
                check["values"] = _norm_rows(r2)
                return {"success": True, "data": check}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def block_batch(batch_id: int, reason: str, blocked_by: str = None) -> Dict[str, Any]:
        """Block a batch — insert block record and update batch status."""
        try:
            with DatabaseModel() as db:
                db.execute_query(
                    """INSERT INTO AGRO_BATCH_BLOCKS (BATCH_ID, REASON, BLOCKED_BY)
                       VALUES (:bid, :reason, :created_by)""",
                    {"bid": batch_id, "reason": reason, "created_by": blocked_by or "operator"})
                db.execute_query(
                    """UPDATE AGRO_BATCHES SET STATUS='blocked',
                       BLOCKED_BY=:blocked_by, BLOCK_REASON=:reason WHERE ID=:bid""",
                    {"bid": batch_id, "reason": reason, "blocked_by": blocked_by or "operator"})
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def unblock_batch(batch_id: int, unblocked_by: str = None, resolution: str = None) -> Dict[str, Any]:
        """Unblock a batch — close block record and restore batch status."""
        try:
            with DatabaseModel() as db:
                db.execute_query(
                    """UPDATE AGRO_BATCH_BLOCKS SET UNBLOCKED_BY=:unblocked_by,
                       UNBLOCKED_AT=SYSTIMESTAMP, RESOLUTION_NOTES=:notes
                       WHERE BATCH_ID=:bid AND UNBLOCKED_AT IS NULL""",
                    {"bid": batch_id, "unblocked_by": unblocked_by or "operator", "notes": resolution or ""})
                db.execute_query(
                    """UPDATE AGRO_BATCHES SET STATUS='active',
                       BLOCKED_BY=NULL, BLOCK_REASON=NULL WHERE ID=:bid""",
                    {"bid": batch_id})
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_batch_blocks(active_only: bool = True) -> Dict[str, Any]:
        """List batch blocks with batch info."""
        try:
            with DatabaseModel() as db:
                sql = """
                    SELECT bb.ID, bb.BATCH_ID, bb.REASON, bb.BLOCKED_BY,
                           bb.BLOCKED_AT, bb.UNBLOCKED_BY, bb.UNBLOCKED_AT,
                           bb.RESOLUTION_NOTES,
                           b.BATCH_NUMBER, i.NAME_RU AS ITEM_NAME
                    FROM AGRO_BATCH_BLOCKS bb
                    LEFT JOIN AGRO_BATCHES b ON b.ID = bb.BATCH_ID
                    LEFT JOIN AGRO_ITEMS i ON i.ID = b.ITEM_ID
                """
                if active_only:
                    sql += " WHERE bb.UNBLOCKED_AT IS NULL"
                sql += " ORDER BY bb.BLOCKED_AT DESC"
                r = db.execute_query(sql)
                return {"success": True, "data": _norm_rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_haccp_plans() -> Dict[str, Any]:
        """List HACCP plans."""
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    """SELECT h.ID, h.CODE, h.NAME_RU, h.NAME_RO, h.PROCESS_STAGE, h.ACTIVE,
                           (SELECT COUNT(*) FROM AGRO_HACCP_CCPS c WHERE c.PLAN_ID = h.ID) AS CCP_COUNT
                       FROM AGRO_HACCP_PLANS h ORDER BY h.NAME_RU""")
                return {"success": True, "data": _norm_rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def upsert_haccp_plan(data: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update HACCP plan."""
        try:
            with DatabaseModel() as db:
                plan_id = data.get("id")
                name_ru = data.get("plan_name") or data.get("name_ru", "")
                if plan_id:
                    db.execute_query(
                        """UPDATE AGRO_HACCP_PLANS SET CODE=:code, NAME_RU=:name_ru, NAME_RO=:name_ro,
                           PROCESS_STAGE=:stage, ACTIVE=:active WHERE ID=:pid""",
                        {"pid": plan_id, "code": data.get("code", ""),
                         "name_ru": name_ru, "name_ro": data.get("name_ro", ""),
                         "stage": data.get("process_stage", ""),
                         "active": data.get("active", "Y")})
                else:
                    code = data.get("code") or f"HACCP-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                    r_seq = db.execute_query(
                        "SELECT AGRO_HACCP_PLANS_SEQ.NEXTVAL AS ID FROM DUAL")
                    plan_id = int(_norm_rows(r_seq)[0]["id"])
                    db.execute_query(
                        """INSERT INTO AGRO_HACCP_PLANS (ID, CODE, NAME_RU, NAME_RO, PROCESS_STAGE, ACTIVE)
                           VALUES (:pid, :code, :name_ru, :name_ro, :stage, :active)""",
                        {"pid": plan_id, "code": code,
                         "name_ru": name_ru, "name_ro": data.get("name_ro", ""),
                         "stage": data.get("process_stage", ""),
                         "active": data.get("active", "Y")})
                db.connection.commit()
                return {"success": True, "data": {"id": plan_id}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_ccps(plan_id: int) -> Dict[str, Any]:
        """Get CCPs for a HACCP plan."""
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    "SELECT * FROM AGRO_HACCP_CCPS WHERE PLAN_ID = :pid ORDER BY CCP_NUMBER",
                    {"pid": plan_id})
                return {"success": True, "data": _norm_rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def upsert_ccp(data: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update a CCP."""
        try:
            with DatabaseModel() as db:
                ccp_id = data.get("id")
                if ccp_id:
                    db.execute_query(
                        """UPDATE AGRO_HACCP_CCPS SET CCP_NUMBER=:num, HAZARD_TYPE=:htype,
                           HAZARD_DESCRIPTION=:haz, CRITICAL_LIMIT_MIN=:clim_min,
                           CRITICAL_LIMIT_MAX=:clim_max,
                           MONITORING_FREQUENCY=:mon, CORRECTIVE_ACTION=:corr
                           WHERE ID=:cid""",
                        {"cid": ccp_id, "num": data.get("ccp_number", ""),
                         "htype": data.get("hazard_type", "biological"),
                         "haz": data.get("hazard_description", ""),
                         "clim_min": data.get("critical_limit_min"),
                         "clim_max": data.get("critical_limit_max"),
                         "mon": data.get("monitoring_frequency", ""),
                         "corr": data.get("corrective_action", "")})
                else:
                    r_seq = db.execute_query(
                        "SELECT AGRO_HACCP_CCPS_SEQ.NEXTVAL AS ID FROM DUAL")
                    ccp_id = int(_norm_rows(r_seq)[0]["id"])
                    db.execute_query(
                        """INSERT INTO AGRO_HACCP_CCPS
                           (ID, PLAN_ID, CCP_NUMBER, HAZARD_TYPE, HAZARD_DESCRIPTION,
                            CRITICAL_LIMIT_MIN, CRITICAL_LIMIT_MAX,
                            MONITORING_FREQUENCY, CORRECTIVE_ACTION)
                           VALUES (:ccp_id, :pid, :num, :htype, :haz, :clim_min, :clim_max, :mon, :corr)""",
                        {"ccp_id": ccp_id,
                         "pid": data["plan_id"], "num": data.get("ccp_number", ""),
                         "htype": data.get("hazard_type", "biological"),
                         "haz": data.get("hazard_description", ""),
                         "clim_min": data.get("critical_limit_min"),
                         "clim_max": data.get("critical_limit_max"),
                         "mon": data.get("monitoring_frequency", ""),
                         "corr": data.get("corrective_action", "")})
                db.connection.commit()
                return {"success": True, "data": {"id": ccp_id}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def record_haccp_measurement(data: Dict[str, Any]) -> Dict[str, Any]:
        """Record HACCP measurement, evaluate if within limits."""
        try:
            ccp_id = data.get("ccp_id")
            measured_value = data.get("measured_value")
            if not ccp_id or measured_value is None:
                return {"success": False, "error": "ccp_id and measured_value required"}

            with DatabaseModel() as db:
                # Get critical limits for evaluation
                r = db.execute_query(
                    "SELECT CRITICAL_LIMIT_MIN, CRITICAL_LIMIT_MAX FROM AGRO_HACCP_CCPS WHERE ID = :cid",
                    {"cid": ccp_id})
                ccp_rows = _norm_rows(r)
                is_within = "Y"
                if ccp_rows:
                    try:
                        meas_val = float(measured_value)
                        cmin = ccp_rows[0].get("critical_limit_min")
                        cmax = ccp_rows[0].get("critical_limit_max")
                        if cmin is not None and meas_val < float(cmin):
                            is_within = "N"
                        if cmax is not None and meas_val > float(cmax):
                            is_within = "N"
                    except (ValueError, TypeError):
                        pass  # Non-numeric limits — manual evaluation

                db.execute_query(
                    """INSERT INTO AGRO_HACCP_RECORDS
                       (CCP_ID, BATCH_ID, MEASURED_VALUE, IS_WITHIN_LIMITS,
                        DEVIATION_NOTES, CORRECTIVE_ACTION_TAKEN, RECORDED_BY)
                       VALUES (:cid, :bid, :val, :within, :dev, :corr, :created_by)""",
                    {"cid": ccp_id, "bid": data.get("batch_id"),
                     "val": float(measured_value), "within": is_within,
                     "dev": data.get("deviation_notes", ""),
                     "corr": data.get("corrective_action", ""),
                     "created_by": data.get("recorded_by", "operator")})
                db.connection.commit()
                return {"success": True, "data": {"is_within_limits": is_within}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_haccp_deviations(date_from: str = None, date_to: str = None) -> Dict[str, Any]:
        """Get HACCP records where IS_WITHIN_LIMITS = 'N'."""
        try:
            with DatabaseModel() as db:
                sql = """
                    SELECT r.ID, r.CCP_ID, r.BATCH_ID, r.MEASURED_VALUE,
                           r.DEVIATION_NOTES, r.CORRECTIVE_ACTION_TAKEN,
                           r.RECORDED_BY, r.RECORDED_AT,
                           c.CCP_NUMBER, c.HAZARD_DESCRIPTION,
                           c.CRITICAL_LIMIT_MIN, c.CRITICAL_LIMIT_MAX,
                           b.BATCH_NUMBER
                    FROM AGRO_HACCP_RECORDS r
                    LEFT JOIN AGRO_HACCP_CCPS c ON c.ID = r.CCP_ID
                    LEFT JOIN AGRO_BATCHES b ON b.ID = r.BATCH_ID
                    WHERE r.IS_WITHIN_LIMITS = 'N'
                """
                params: Dict[str, Any] = {}
                if date_from:
                    sql += " AND r.RECORDED_AT >= TO_DATE(:df, 'YYYY-MM-DD')"
                    params["df"] = date_from
                if date_to:
                    sql += " AND r.RECORDED_AT < TO_DATE(:dt, 'YYYY-MM-DD') + 1"
                    params["dt"] = date_to
                sql += " ORDER BY r.RECORDED_AT DESC"
                r = db.execute_query(sql, params)
                return {"success": True, "data": _norm_rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------
    # REPORTS
    # ------------------------------------------------------------------

    @staticmethod
    def report_purchases(date_from: str = None, date_to: str = None,
                         supplier_id: str = None, item_id: str = None) -> Dict[str, Any]:
        """Purchase report from AGRO_V_PURCHASES view."""
        try:
            with DatabaseModel() as db:
                sql = "SELECT * FROM AGRO_V_PURCHASES WHERE 1=1"
                params: Dict[str, Any] = {}
                if date_from:
                    sql += " AND DOC_DATE >= TO_DATE(:df, 'YYYY-MM-DD')"
                    params["df"] = date_from
                if date_to:
                    sql += " AND DOC_DATE <= TO_DATE(:dt, 'YYYY-MM-DD')"
                    params["dt"] = date_to
                if supplier_id:
                    sql += " AND SUPPLIER_ID = :sid"
                    params["sid"] = int(supplier_id)
                if item_id:
                    sql += " AND ITEM_ID = :iid"
                    params["iid"] = int(item_id)
                sql += " ORDER BY DOC_DATE DESC"
                r = db.execute_query(sql, params)
                return {"success": True, "data": _norm_rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def report_sales(date_from: str = None, date_to: str = None,
                     customer_id: str = None, item_id: str = None) -> Dict[str, Any]:
        """Sales report from AGRO_V_SALES view."""
        try:
            with DatabaseModel() as db:
                sql = "SELECT * FROM AGRO_V_SALES WHERE 1=1"
                params: Dict[str, Any] = {}
                if date_from:
                    sql += " AND DOC_DATE >= TO_DATE(:df, 'YYYY-MM-DD')"
                    params["df"] = date_from
                if date_to:
                    sql += " AND DOC_DATE <= TO_DATE(:dt, 'YYYY-MM-DD')"
                    params["dt"] = date_to
                if customer_id:
                    sql += " AND CUSTOMER_ID = :cid"
                    params["cid"] = int(customer_id)
                if item_id:
                    sql += " AND ITEM_ID = :iid"
                    params["iid"] = int(item_id)
                sql += " ORDER BY DOC_DATE DESC"
                r = db.execute_query(sql, params)
                return {"success": True, "data": _norm_rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def report_mass_balance(date_from: str = None, date_to: str = None,
                            warehouse_id: str = None, item_id: str = None) -> Dict[str, Any]:
        """Mass balance report from AGRO_V_MASS_BALANCE view."""
        try:
            with DatabaseModel() as db:
                sql = "SELECT * FROM AGRO_V_MASS_BALANCE WHERE 1=1"
                params: Dict[str, Any] = {}
                if warehouse_id:
                    sql += " AND WAREHOUSE_ID = :wid"
                    params["wid"] = int(warehouse_id)
                if item_id:
                    sql += " AND ITEM_ID = :iid"
                    params["iid"] = int(item_id)
                r = db.execute_query(sql, params)
                return {"success": True, "data": _norm_rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def report_stock(warehouse_id: str = None, item_id: str = None) -> Dict[str, Any]:
        """Current stock report from AGRO_V_STOCK_BALANCE view."""
        try:
            with DatabaseModel() as db:
                sql = "SELECT * FROM AGRO_V_STOCK_BALANCE WHERE 1=1"
                params: Dict[str, Any] = {}
                if warehouse_id:
                    sql += " AND WAREHOUSE_ID = :wid"
                    params["wid"] = int(warehouse_id)
                if item_id:
                    sql += " AND ITEM_ID = :iid"
                    params["iid"] = int(item_id)
                sql += " ORDER BY ITEM_NAME_RU, WAREHOUSE_NAME"
                r = db.execute_query(sql, params)
                return {"success": True, "data": _norm_rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def report_expiry(days_ahead: str = "30", warehouse_id: str = None) -> Dict[str, Any]:
        """Batches expiring within N days."""
        try:
            with DatabaseModel() as db:
                sql = """
                    SELECT b.ID, b.BATCH_NUMBER, b.EXPIRY_DATE, b.CURRENT_QTY_KG, b.STATUS,
                           i.NAME_RU AS ITEM_NAME, w.NAME AS WAREHOUSE_NAME,
                           ROUND(b.EXPIRY_DATE - SYSDATE) AS DAYS_REMAINING
                    FROM AGRO_BATCHES b
                    LEFT JOIN AGRO_ITEMS i ON i.ID = b.ITEM_ID
                    LEFT JOIN AGRO_WAREHOUSES w ON w.ID = b.WAREHOUSE_ID
                    WHERE b.EXPIRY_DATE IS NOT NULL
                      AND b.EXPIRY_DATE <= SYSDATE + :days
                      AND b.STATUS != 'depleted'
                """
                params: Dict[str, Any] = {"days": int(days_ahead)}
                if warehouse_id:
                    sql += " AND b.WAREHOUSE_ID = :wid"
                    params["wid"] = int(warehouse_id)
                sql += " ORDER BY b.EXPIRY_DATE ASC"
                r = db.execute_query(sql, params)
                return {"success": True, "data": _norm_rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def export_report(report_type: str, fmt: str, filters: Dict[str, Any]) -> bytes:
        """Generate report file. Returns bytes for download."""
        import io
        method = getattr(AgroStore, f'report_{report_type}', None)
        if not method:
            return None
        data = method(**filters)
        if not data.get('success'):
            return None

        rows = data['data']
        if fmt == 'csv':
            import csv
            output = io.StringIO()
            if rows:
                writer = csv.DictWriter(output, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            return output.getvalue().encode('utf-8')

        elif fmt == 'xlsx':
            try:
                from openpyxl import Workbook
                wb = Workbook()
                ws = wb.active
                ws.title = report_type
                if rows:
                    ws.append(list(rows[0].keys()))
                    for row in rows:
                        ws.append([str(v) if v is not None else '' for v in row.values()])
                buf = io.BytesIO()
                wb.save(buf)
                return buf.getvalue()
            except ImportError:
                return None

        return None
