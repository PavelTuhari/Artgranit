"""AEI module controller — HTTP request handlers for AEI routes.

All methods are @staticmethod, receive Flask request data,
return dict {success, data?, error?}.
"""
from __future__ import annotations

from typing import Any, Dict

from flask import request, session

from models.aei_oracle_store import AEIStore


class AEIController:
    """Route handlers for AEI (Asociații de Economii și Împrumut) module."""

    # ----------------------------------------------------------------
    # DASHBOARD
    # ----------------------------------------------------------------

    @staticmethod
    def get_dashboard() -> Dict[str, Any]:
        return AEIStore.get_dashboard_stats()

    # ----------------------------------------------------------------
    # MEMBERS
    # ----------------------------------------------------------------

    @staticmethod
    def get_members() -> Dict[str, Any]:
        status = request.args.get("status")
        return AEIStore.get_members(status=status)

    @staticmethod
    def get_member(member_id: int) -> Dict[str, Any]:
        return AEIStore.get_member(member_id)

    @staticmethod
    def upsert_member() -> Dict[str, Any]:
        data = request.get_json(silent=True) or {}
        if not data.get("last_name"):
            return {"success": False, "error": "last_name is required"}
        result = AEIStore.upsert_member(data)
        if result.get("success"):
            AEIStore.log_event(
                "MEMBER_UPSERT",
                source_table="AEI_MEMBERS",
                source_id=data.get("member_id"),
                user_name=session.get("username"),
                description=f"Upsert member: {data.get('last_name')} {data.get('first_name')}"
            )
        return result

    @staticmethod
    def delete_member(member_id: int) -> Dict[str, Any]:
        result = AEIStore.delete_member(member_id)
        if result.get("success"):
            AEIStore.log_event("MEMBER_DEACTIVATE", "AEI_MEMBERS", member_id,
                               session.get("username"), f"Deactivated member id={member_id}")
        return result

    # ----------------------------------------------------------------
    # DEPOSITS
    # ----------------------------------------------------------------

    @staticmethod
    def get_deposits() -> Dict[str, Any]:
        status = request.args.get("status")
        member_id = request.args.get("member_id", type=int)
        return AEIStore.get_deposits(status=status, member_id=member_id)

    @staticmethod
    def get_deposit(deposit_id: int) -> Dict[str, Any]:
        return AEIStore.get_deposit(deposit_id)

    @staticmethod
    def upsert_deposit() -> Dict[str, Any]:
        data = request.get_json(silent=True) or {}
        required = ["member_id", "contract_no", "sign_date", "start_date", "end_date", "principal"]
        missing = [f for f in required if not data.get(f)]
        if missing:
            return {"success": False, "error": f"Required: {', '.join(missing)}"}
        result = AEIStore.upsert_deposit(data)
        if result.get("success"):
            AEIStore.log_event(
                "DEPOSIT_UPSERT", "AEI_DEPOSITS",
                data.get("deposit_id"), session.get("username"),
                f"Contract {data.get('contract_no')} — {data.get('principal')} {data.get('currency','MDL')}"
            )
        return result

    @staticmethod
    def get_deposit_flows(deposit_id: int) -> Dict[str, Any]:
        return AEIStore.get_deposit_flows(deposit_id)

    # ----------------------------------------------------------------
    # LOANS
    # ----------------------------------------------------------------

    @staticmethod
    def get_loans() -> Dict[str, Any]:
        status = request.args.get("status")
        member_id = request.args.get("member_id", type=int)
        return AEIStore.get_loans(status=status, member_id=member_id)

    @staticmethod
    def upsert_loan() -> Dict[str, Any]:
        data = request.get_json(silent=True) or {}
        required = ["member_id", "contract_no", "sign_date", "disbursement_date", "end_date",
                    "principal", "interest_rate", "term_months"]
        missing = [f for f in required if not data.get(f)]
        if missing:
            return {"success": False, "error": f"Required: {', '.join(missing)}"}
        result = AEIStore.upsert_loan(data)
        if result.get("success"):
            AEIStore.log_event(
                "LOAN_UPSERT", "AEI_LOANS",
                data.get("loan_id"), session.get("username"),
                f"Credit {data.get('contract_no')} — {data.get('principal')} {data.get('currency','MDL')}"
            )
        return result

    # ----------------------------------------------------------------
    # JOURNAL
    # ----------------------------------------------------------------

    @staticmethod
    def get_journal() -> Dict[str, Any]:
        return AEIStore.get_journal(
            date_from=request.args.get("date_from"),
            date_to=request.args.get("date_to"),
            account=request.args.get("account"),
            source_type=request.args.get("source_type"),
        )

    @staticmethod
    def insert_journal_entry() -> Dict[str, Any]:
        data = request.get_json(silent=True) or {}
        required = ["entry_date", "debit_account", "credit_account", "amount"]
        missing = [f for f in required if not data.get(f)]
        if missing:
            return {"success": False, "error": f"Required: {', '.join(missing)}"}
        data["created_by"] = session.get("username", "system")
        return AEIStore.insert_journal_entry(data)

    # ----------------------------------------------------------------
    # ACCOUNTS & SETTINGS
    # ----------------------------------------------------------------

    @staticmethod
    def get_accounts() -> Dict[str, Any]:
        return AEIStore.get_accounts()

    @staticmethod
    def get_settings() -> Dict[str, Any]:
        return AEIStore.get_settings()

    @staticmethod
    def update_setting() -> Dict[str, Any]:
        data = request.get_json(silent=True) or {}
        key = data.get("key")
        value = data.get("value", "")
        if not key:
            return {"success": False, "error": "key is required"}
        return AEIStore.set_setting(key, value)
