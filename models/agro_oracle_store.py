"""AGRO module Oracle store — all AGRO_* table operations."""
from __future__ import annotations

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
