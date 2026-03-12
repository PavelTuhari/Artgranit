"""AGRO Field Controller -- purchases, barcodes, crates, offline sync."""
from __future__ import annotations
from typing import Any, Dict, List
from models.agro_oracle_store import AgroStore


def _safe_call(fn, *args, **kwargs) -> Dict[str, Any]:
    """Call an AgroStore method; return a graceful error if not implemented yet."""
    try:
        return fn(*args, **kwargs)
    except (AttributeError, NotImplementedError):
        return {"success": False, "error": "Not implemented yet"}


class AgroFieldController:
    """Handles field-level operations: purchases, barcodes, crates, offline sync."""

    @staticmethod
    def generate_barcodes(count: int, barcode_type: str = "EAN13") -> Dict[str, Any]:
        return _safe_call(AgroStore.generate_barcodes, count, barcode_type)

    @staticmethod
    def scan_crate(barcode: str) -> Dict[str, Any]:
        return _safe_call(AgroStore.scan_crate, barcode)

    @staticmethod
    def register_crate(data: Dict[str, Any]) -> Dict[str, Any]:
        return _safe_call(AgroStore.register_crate, data)

    @staticmethod
    def get_purchases(filters: Dict[str, Any] = None) -> Dict[str, Any]:
        return _safe_call(AgroStore.get_purchases, filters)

    @staticmethod
    def create_purchase(data: Dict[str, Any]) -> Dict[str, Any]:
        if not data.get('supplier_id') or not data.get('items'):
            return {"success": False, "error": "SUPPLIER_ID and ITEMS are required"}
        return _safe_call(AgroStore.create_purchase, data)

    @staticmethod
    def get_purchase_by_id(doc_id: int) -> Dict[str, Any]:
        return _safe_call(AgroStore.get_purchase_by_id, doc_id)

    @staticmethod
    def update_purchase(data: Dict[str, Any]) -> Dict[str, Any]:
        return _safe_call(AgroStore.update_purchase, data)

    @staticmethod
    def confirm_purchase(doc_id: int) -> Dict[str, Any]:
        return _safe_call(AgroStore.confirm_purchase, doc_id)

    @staticmethod
    def cancel_purchase(doc_id: int) -> Dict[str, Any]:
        return _safe_call(AgroStore.cancel_purchase, doc_id)

    @staticmethod
    def sync_offline_queue(queue: List[Dict[str, Any]]) -> Dict[str, Any]:
        return _safe_call(AgroStore.sync_offline_queue, queue)

    @staticmethod
    def get_sync_references() -> Dict[str, Any]:
        return _safe_call(AgroStore.get_sync_references)

    @staticmethod
    def get_barcode_print_batch(barcode_ids: List[int]) -> Dict[str, Any]:
        return _safe_call(AgroStore.get_barcode_print_batch, barcode_ids)
