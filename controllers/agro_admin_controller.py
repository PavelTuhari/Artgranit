"""AGRO Admin Controller -- references, settings, reports."""
from __future__ import annotations
from typing import Any, Dict
from models.agro_oracle_store import AgroStore


class AgroAdminController:
    """Handles admin API requests: references CRUD, settings, reports."""

    # ---- Suppliers ----
    @staticmethod
    def get_suppliers(active_only: bool = False) -> Dict[str, Any]:
        return AgroStore.get_suppliers(active_only)

    @staticmethod
    def upsert_supplier(data: Dict[str, Any]) -> Dict[str, Any]:
        if not data.get('code') or not data.get('name'):
            return {"success": False, "error": "CODE and NAME are required"}
        return AgroStore.upsert_supplier(data)

    @staticmethod
    def delete_supplier(record_id: int) -> Dict[str, Any]:
        return AgroStore.delete_supplier(record_id)

    # ---- Customers ----
    @staticmethod
    def get_customers(active_only: bool = False) -> Dict[str, Any]:
        return AgroStore.get_customers(active_only)

    @staticmethod
    def upsert_customer(data: Dict[str, Any]) -> Dict[str, Any]:
        if not data.get('code') or not data.get('name'):
            return {"success": False, "error": "CODE and NAME are required"}
        return AgroStore.upsert_customer(data)

    @staticmethod
    def delete_customer(record_id: int) -> Dict[str, Any]:
        return AgroStore.delete_customer(record_id)

    # ---- Warehouses ----
    @staticmethod
    def get_warehouses(active_only: bool = False) -> Dict[str, Any]:
        return AgroStore.get_warehouses(active_only)

    @staticmethod
    def upsert_warehouse(data: Dict[str, Any]) -> Dict[str, Any]:
        if not data.get('code') or not data.get('name'):
            return {"success": False, "error": "CODE and NAME are required"}
        return AgroStore.upsert_warehouse(data)

    @staticmethod
    def delete_warehouse(record_id: int) -> Dict[str, Any]:
        return AgroStore.delete_warehouse(record_id)

    # ---- Storage Cells ----
    @staticmethod
    def get_storage_cells(warehouse_id: int = None) -> Dict[str, Any]:
        return AgroStore.get_storage_cells(warehouse_id)

    @staticmethod
    def upsert_storage_cell(data: Dict[str, Any]) -> Dict[str, Any]:
        if not data.get('warehouse_id') or not data.get('code'):
            return {"success": False, "error": "WAREHOUSE_ID and CODE are required"}
        return AgroStore.upsert_storage_cell(data)

    @staticmethod
    def delete_storage_cell(record_id: int) -> Dict[str, Any]:
        return AgroStore.delete_storage_cell(record_id)

    # ---- Items ----
    @staticmethod
    def get_items(active_only: bool = False) -> Dict[str, Any]:
        return AgroStore.get_items(active_only)

    @staticmethod
    def upsert_item(data: Dict[str, Any]) -> Dict[str, Any]:
        if not data.get('code') or not data.get('name_ru'):
            return {"success": False, "error": "CODE and NAME_RU are required"}
        return AgroStore.upsert_item(data)

    @staticmethod
    def delete_item(record_id: int) -> Dict[str, Any]:
        return AgroStore.delete_item(record_id)

    # ---- Packaging Types ----
    @staticmethod
    def get_packaging_types(active_only: bool = False) -> Dict[str, Any]:
        return AgroStore.get_packaging_types(active_only)

    @staticmethod
    def upsert_packaging_type(data: Dict[str, Any]) -> Dict[str, Any]:
        if not data.get('code') or not data.get('name_ru'):
            return {"success": False, "error": "CODE and NAME_RU are required"}
        return AgroStore.upsert_packaging_type(data)

    @staticmethod
    def delete_packaging_type(record_id: int) -> Dict[str, Any]:
        return AgroStore.delete_packaging_type(record_id)

    # ---- Vehicles ----
    @staticmethod
    def get_vehicles(active_only: bool = False) -> Dict[str, Any]:
        return AgroStore.get_vehicles(active_only)

    @staticmethod
    def upsert_vehicle(data: Dict[str, Any]) -> Dict[str, Any]:
        if not data.get('plate_number'):
            return {"success": False, "error": "PLATE_NUMBER is required"}
        return AgroStore.upsert_vehicle(data)

    @staticmethod
    def delete_vehicle(record_id: int) -> Dict[str, Any]:
        return AgroStore.delete_vehicle(record_id)

    # ---- Currencies ----
    @staticmethod
    def get_currencies(active_only: bool = False) -> Dict[str, Any]:
        return AgroStore.get_currencies(active_only)

    @staticmethod
    def upsert_currency(data: Dict[str, Any]) -> Dict[str, Any]:
        if not data.get('code'):
            return {"success": False, "error": "CODE is required"}
        return AgroStore.upsert_currency(data)

    @staticmethod
    def delete_currency(record_id: int) -> Dict[str, Any]:
        return AgroStore.delete_currency(record_id)

    # ---- Exchange Rates ----
    @staticmethod
    def get_exchange_rates() -> Dict[str, Any]:
        return AgroStore.get_exchange_rates()

    @staticmethod
    def upsert_exchange_rate(data: Dict[str, Any]) -> Dict[str, Any]:
        if not data.get('from_currency') or not data.get('to_currency') \
                or data.get('rate') is None or not data.get('rate_date'):
            return {"success": False, "error": "FROM_CURRENCY, TO_CURRENCY, RATE and RATE_DATE are required"}
        return AgroStore.upsert_exchange_rate(data)

    @staticmethod
    def delete_exchange_rate(record_id: int) -> Dict[str, Any]:
        return AgroStore.delete_exchange_rate(record_id)

    # ---- Formula Params ----
    @staticmethod
    def get_formula_params() -> Dict[str, Any]:
        return AgroStore.get_formula_params()

    @staticmethod
    def upsert_formula_param(data: Dict[str, Any]) -> Dict[str, Any]:
        if not data.get('param_name'):
            return {"success": False, "error": "PARAM_NAME is required"}
        return AgroStore.upsert_formula_param(data)

    @staticmethod
    def delete_formula_param(record_id: int) -> Dict[str, Any]:
        return AgroStore.delete_formula_param(record_id)

    # ---- Module Config ----
    @staticmethod
    def get_module_config() -> Dict[str, Any]:
        return AgroStore.get_module_config()

    @staticmethod
    def upsert_module_config(data: Dict[str, Any]) -> Dict[str, Any]:
        if not data.get('config_key'):
            return {"success": False, "error": "CONFIG_KEY is required"}
        return AgroStore.upsert_module_config(data)

    @staticmethod
    def delete_module_config(record_id: int) -> Dict[str, Any]:
        return AgroStore.delete_module_config(record_id)
