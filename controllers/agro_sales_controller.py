"""AGRO Sales Controller -- shipments, export, batch allocation."""
from __future__ import annotations
from typing import Any, Dict, Optional
from models.agro_oracle_store import AgroStore


def _safe_call(fn, *args, **kwargs) -> Dict[str, Any]:
    """Call an AgroStore method; return a graceful error if not implemented yet."""
    try:
        return fn(*args, **kwargs)
    except (AttributeError, NotImplementedError):
        return {"success": False, "error": "Not implemented yet"}


class AgroSalesController:
    """Handles sales operations: shipments, export declarations, batch allocation."""

    @staticmethod
    def get_sales_docs(filters: Dict[str, Any] = None) -> Dict[str, Any]:
        return _safe_call(AgroStore.get_sales_docs, filters)

    @staticmethod
    def get_sales_doc_by_id(doc_id: int) -> Dict[str, Any]:
        return _safe_call(AgroStore.get_sales_doc_by_id, doc_id)

    @staticmethod
    def create_sales_doc(data: Dict[str, Any]) -> Dict[str, Any]:
        if not data.get('customer_id') or not data.get('warehouse_id'):
            return {"success": False, "error": "customer_id and warehouse_id required"}
        return _safe_call(AgroStore.create_sales_doc, data)

    @staticmethod
    def confirm_sales_doc(doc_id: int) -> Dict[str, Any]:
        return _safe_call(AgroStore.confirm_sales_doc, doc_id)

    @staticmethod
    def allocate_batches(data: Dict[str, Any]) -> Dict[str, Any]:
        sales_line_id = data.get('sales_line_id')
        item_id = data.get('item_id')
        qty_kg = data.get('qty_kg')
        if not sales_line_id or not item_id or not qty_kg:
            return {"success": False, "error": "sales_line_id, item_id, qty_kg required"}
        return _safe_call(
            AgroStore.allocate_batches,
            sales_line_id, item_id, float(qty_kg),
            data.get('warehouse_id'), data.get('method', 'fifo'),
        )

    @staticmethod
    def get_available_stock(item_id: int = None, warehouse_id: int = None) -> Dict[str, Any]:
        return _safe_call(AgroStore.get_available_stock, item_id, warehouse_id)

    @staticmethod
    def create_export_decl(data: Dict[str, Any]) -> Dict[str, Any]:
        if not data.get('sales_doc_id'):
            return {"success": False, "error": "sales_doc_id required"}
        return _safe_call(AgroStore.create_export_decl, data)

    @staticmethod
    def get_export_decl(decl_id: int) -> Dict[str, Any]:
        return _safe_call(AgroStore.get_export_decl, decl_id)

    @staticmethod
    def update_export_decl(data: Dict[str, Any]) -> Dict[str, Any]:
        return _safe_call(AgroStore.update_export_decl, data)
