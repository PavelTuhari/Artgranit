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
        if not data.get('supplier_id') or not (data.get('items') or data.get('lines')):
            return {"success": False, "error": "SUPPLIER_ID and ITEMS/LINES are required"}
        if data.get('items') and not data.get('lines'):
            data['lines'] = data['items']
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

    # ---- Field Requests ----
    @staticmethod
    def get_field_requests(filters: Dict[str, Any] = None) -> Dict[str, Any]:
        return _safe_call(AgroStore.get_field_requests, filters)

    @staticmethod
    def get_field_request_by_id(request_id: int) -> Dict[str, Any]:
        return _safe_call(AgroStore.get_field_request_by_id, request_id)

    @staticmethod
    def create_field_request(data: Dict[str, Any]) -> Dict[str, Any]:
        if not data.get('lines'):
            return {"success": False, "error": "At least one line item is required"}
        return _safe_call(AgroStore.create_field_request, data)

    @staticmethod
    def update_field_request(data: Dict[str, Any]) -> Dict[str, Any]:
        return _safe_call(AgroStore.update_field_request, data)

    @staticmethod
    def approve_field_request(request_id: int, approved_by: str = None) -> Dict[str, Any]:
        return _safe_call(AgroStore.approve_field_request, request_id, approved_by)

    @staticmethod
    def cancel_field_request(request_id: int) -> Dict[str, Any]:
        return _safe_call(AgroStore.cancel_field_request, request_id)

    # ---- Batch Inspections ----
    @staticmethod
    def perform_batch_inspection(data: Dict[str, Any]) -> Dict[str, Any]:
        if not data.get('batch_id') or not data.get('profile_id'):
            return {"success": False, "error": "batch_id and profile_id are required"}
        return _safe_call(AgroStore.perform_batch_inspection, data)

    @staticmethod
    def get_batch_inspections(batch_id: int = None) -> Dict[str, Any]:
        return _safe_call(AgroStore.get_batch_inspections, batch_id)

    @staticmethod
    def get_batch_inspection_detail(inspection_id: int) -> Dict[str, Any]:
        return _safe_call(AgroStore.get_batch_inspection_detail, inspection_id)
