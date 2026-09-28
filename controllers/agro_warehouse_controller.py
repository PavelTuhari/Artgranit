"""AGRO Warehouse Controller -- stock, movements, readings, tasks."""
from __future__ import annotations
from typing import Any, Dict, Optional
from models.agro_oracle_store import AgroStore


def _safe_call(fn, *args, **kwargs) -> Dict[str, Any]:
    """Call an AgroStore method; return a graceful error if not implemented yet."""
    try:
        return fn(*args, **kwargs)
    except (AttributeError, NotImplementedError):
        return {"success": False, "error": "Not implemented yet"}


class AgroWarehouseController:
    """Handles warehouse operations: stock, movements, sensor readings, processing tasks."""

    @staticmethod
    def get_stock_balance(filters: Dict[str, Any] = None) -> Dict[str, Any]:
        return _safe_call(AgroStore.get_stock_balance, filters)

    @staticmethod
    def get_batch_by_id(batch_id: int) -> Dict[str, Any]:
        return _safe_call(AgroStore.get_batch_by_id, batch_id)

    @staticmethod
    def get_batch_history(batch_id: int) -> Dict[str, Any]:
        return _safe_call(AgroStore.get_batch_history, batch_id)

    @staticmethod
    def create_movement(data: Dict[str, Any]) -> Dict[str, Any]:
        if not data.get('movement_type') or not data.get('batch_id'):
            return {"success": False, "error": "MOVEMENT_TYPE and BATCH_ID are required"}
        return _safe_call(AgroStore.create_movement, data)

    @staticmethod
    def receive_crates(data: Dict[str, Any]) -> Dict[str, Any]:
        return _safe_call(AgroStore.receive_crates, data)

    @staticmethod
    def get_readings(cell_id: int, date_from: str = None, date_to: str = None) -> Dict[str, Any]:
        return _safe_call(AgroStore.get_readings, cell_id, date_from, date_to)

    @staticmethod
    def add_reading(data: Dict[str, Any]) -> Dict[str, Any]:
        return _safe_call(AgroStore.add_reading, data)

    @staticmethod
    def get_alerts(acknowledged: Optional[bool] = None) -> Dict[str, Any]:
        return _safe_call(AgroStore.get_alerts, acknowledged)

    @staticmethod
    def acknowledge_alert(alert_id: int, user: str = None) -> Dict[str, Any]:
        return _safe_call(AgroStore.acknowledge_alert, alert_id, user)

    @staticmethod
    def get_processing_tasks(filters: Dict[str, Any] = None) -> Dict[str, Any]:
        return _safe_call(AgroStore.get_processing_tasks, filters)

    @staticmethod
    def create_processing_task(data: Dict[str, Any]) -> Dict[str, Any]:
        return _safe_call(AgroStore.create_processing_task, data)

    @staticmethod
    def update_task_status(task_id: int, status: str,
                           output_qty: float = None, waste_qty: float = None) -> Dict[str, Any]:
        return _safe_call(AgroStore.update_task_status, task_id, status, output_qty, waste_qty)
