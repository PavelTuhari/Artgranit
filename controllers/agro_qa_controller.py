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
    def get_checklist_by_id(cl_id: int) -> Dict[str, Any]:
        return _safe_call(AgroStore.get_checklist_by_id, cl_id)

    @staticmethod
    def upsert_checklist(data: Dict[str, Any]) -> Dict[str, Any]:
        if not data.get('name'):
            return {"success": False, "error": "name required"}
        return _safe_call(AgroStore.upsert_checklist, data)

    @staticmethod
    def delete_checklist(cl_id: int) -> Dict[str, Any]:
        return _safe_call(AgroStore.delete_checklist, cl_id)

    @staticmethod
    def perform_check(data: Dict[str, Any]) -> Dict[str, Any]:
        if not data.get('batch_id') or not data.get('checklist_id'):
            return {"success": False, "error": "batch_id and checklist_id required"}
        return _safe_call(AgroStore.perform_check, data)

    @staticmethod
    def get_checks(batch_id: int = None) -> Dict[str, Any]:
        return _safe_call(AgroStore.get_checks, batch_id)

    @staticmethod
    def get_check_detail(check_id: int) -> Dict[str, Any]:
        return _safe_call(AgroStore.get_check_detail, check_id)

    @staticmethod
    def block_batch(batch_id: int, reason: str, blocked_by: str = None) -> Dict[str, Any]:
        if not reason:
            return {"success": False, "error": "reason required"}
        return _safe_call(AgroStore.block_batch, batch_id, reason, blocked_by)

    @staticmethod
    def unblock_batch(batch_id: int, unblocked_by: str = None, resolution: str = None) -> Dict[str, Any]:
        return _safe_call(AgroStore.unblock_batch, batch_id, unblocked_by, resolution)

    @staticmethod
    def get_batch_blocks(active_only: bool = True) -> Dict[str, Any]:
        return _safe_call(AgroStore.get_batch_blocks, active_only)

    @staticmethod
    def get_haccp_plans() -> Dict[str, Any]:
        return _safe_call(AgroStore.get_haccp_plans)

    @staticmethod
    def upsert_haccp_plan(data: Dict[str, Any]) -> Dict[str, Any]:
        if not data.get('plan_name'):
            return {"success": False, "error": "plan_name required"}
        return _safe_call(AgroStore.upsert_haccp_plan, data)

    @staticmethod
    def get_ccps(plan_id: int) -> Dict[str, Any]:
        return _safe_call(AgroStore.get_ccps, plan_id)

    @staticmethod
    def upsert_ccp(data: Dict[str, Any]) -> Dict[str, Any]:
        if not data.get('plan_id') or not data.get('ccp_name'):
            return {"success": False, "error": "plan_id and ccp_name required"}
        return _safe_call(AgroStore.upsert_ccp, data)

    @staticmethod
    def record_haccp_measurement(data: Dict[str, Any]) -> Dict[str, Any]:
        if not data.get('ccp_id') or data.get('measured_value') is None:
            return {"success": False, "error": "ccp_id and measured_value required"}
        return _safe_call(AgroStore.record_haccp_measurement, data)

    @staticmethod
    def get_haccp_deviations(date_from: str = None, date_to: str = None) -> Dict[str, Any]:
        return _safe_call(AgroStore.get_haccp_deviations, date_from, date_to)
