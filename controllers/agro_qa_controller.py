"""AGRO QA Controller -- checklists, checks, HACCP, batch blocks."""
from __future__ import annotations
from typing import Any, Dict, Optional
from models.agro_oracle_store import AgroStore


def _safe_call(fn, *args, **kwargs) -> Dict[str, Any]:
    """Call an AgroStore method; return a graceful error if not implemented yet."""
    try:
        return fn(*args, **kwargs)
    except (AttributeError, NotImplementedError):
        return {"success": False, "error": "Not implemented yet"}


class AgroQaController:
    """Handles QA operations: checklists, checks, HACCP plans, batch blocks."""

    @staticmethod
    def get_checklists(checklist_type: str = None) -> Dict[str, Any]:
        return _safe_call(AgroStore.get_checklists, checklist_type)

    @staticmethod
    def upsert_checklist(data: Dict[str, Any]) -> Dict[str, Any]:
        return _safe_call(AgroStore.upsert_checklist, data)

    @staticmethod
    def perform_check(data: Dict[str, Any]) -> Dict[str, Any]:
        return _safe_call(AgroStore.perform_check, data)

    @staticmethod
    def get_checks(batch_id: int) -> Dict[str, Any]:
        return _safe_call(AgroStore.get_checks, batch_id)

    @staticmethod
    def block_batch(batch_id: int, reason: str, blocked_by: str = None) -> Dict[str, Any]:
        return _safe_call(AgroStore.block_batch, batch_id, reason, blocked_by)

    @staticmethod
    def unblock_batch(batch_id: int, unblocked_by: str = None, resolution: str = None) -> Dict[str, Any]:
        return _safe_call(AgroStore.unblock_batch, batch_id, unblocked_by, resolution)

    @staticmethod
    def get_haccp_plans() -> Dict[str, Any]:
        return _safe_call(AgroStore.get_haccp_plans)

    @staticmethod
    def upsert_haccp_plan(data: Dict[str, Any]) -> Dict[str, Any]:
        return _safe_call(AgroStore.upsert_haccp_plan, data)

    @staticmethod
    def record_haccp_measurement(data: Dict[str, Any]) -> Dict[str, Any]:
        return _safe_call(AgroStore.record_haccp_measurement, data)

    @staticmethod
    def get_haccp_deviations(date_from: str = None, date_to: str = None) -> Dict[str, Any]:
        return _safe_call(AgroStore.get_haccp_deviations, date_from, date_to)
