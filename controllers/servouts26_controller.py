"""ServOuts26 controller — HTTP handlers for the ServOuts26 CRM/SaaS module.

All methods are @staticmethod, read Flask request data and return
dict {success, data?/..., error?} — same contract as the other modules.
"""
from __future__ import annotations

from typing import Any, Dict

from flask import request

from models.servouts26_store import ServOuts26Store


class ServOuts26Controller:
    """Route handlers for ServOuts26 (servicii contabile, schema UNITEST)."""

    # ---------------- connection / dashboard ----------------

    @staticmethod
    def test_connection() -> Dict[str, Any]:
        return ServOuts26Store.test_connection()

    @staticmethod
    def get_dashboard() -> Dict[str, Any]:
        return ServOuts26Store.get_dashboard()

    # ---------------- nomenclator ----------------

    @staticmethod
    def get_univers() -> Dict[str, Any]:
        return ServOuts26Store.get_univers(
            tip=request.args.get("tip"),
            gr1=request.args.get("gr1"),
            arhiv=request.args.get("arhiv"),
            search=request.args.get("q"),
            limit=request.args.get("limit", 500),
        )

    @staticmethod
    def get_univers_filters() -> Dict[str, Any]:
        return ServOuts26Store.get_univers_filters()

    @staticmethod
    def get_univers_card(cod: int) -> Dict[str, Any]:
        return ServOuts26Store.get_univers_card(cod)

    @staticmethod
    def update_univers(cod: int) -> Dict[str, Any]:
        data = request.get_json(silent=True) or {}
        return ServOuts26Store.update_univers(cod, data)

    @staticmethod
    def archive_univers(cod: int) -> Dict[str, Any]:
        data = request.get_json(silent=True) or {}
        return ServOuts26Store.archive_univers(cod, data.get("value"))

    # ---------------- groups ----------------

    @staticmethod
    def get_groups() -> Dict[str, Any]:
        return ServOuts26Store.get_groups(request.args.get("codprice", type=int))

    @staticmethod
    def rename_group() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        if not d.get("codprice") or not d.get("codgrp"):
            return {"success": False, "error": "codprice and codgrp required"}
        return ServOuts26Store.rename_group(
            int(d["codprice"]), int(d["codgrp"]), d.get("grpname", ""))

    @staticmethod
    def merge_groups() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        for f in ("codprice", "src", "dst"):
            if not d.get(f):
                return {"success": False, "error": f"{f} required"}
        if int(d["src"]) == int(d["dst"]):
            return {"success": False, "error": "src and dst must differ"}
        return ServOuts26Store.merge_groups(
            int(d["codprice"]), int(d["src"]), int(d["dst"]))

    @staticmethod
    def get_systree() -> Dict[str, Any]:
        return ServOuts26Store.get_systree()

    # ---------------- orgs / clients ----------------

    @staticmethod
    def get_orgs() -> Dict[str, Any]:
        return ServOuts26Store.get_orgs(
            search=request.args.get("q"),
            limit=request.args.get("limit", 300))

    @staticmethod
    def get_org_card(cod: int) -> Dict[str, Any]:
        return ServOuts26Store.get_org_card(cod)

    # ---------------- pricelists ----------------

    @staticmethod
    def get_pricelists() -> Dict[str, Any]:
        return ServOuts26Store.get_pricelists()

    @staticmethod
    def get_prices() -> Dict[str, Any]:
        codprice = request.args.get("codprice", type=int)
        if not codprice:
            return {"success": False, "error": "codprice required"}
        return ServOuts26Store.get_prices(
            codprice,
            codgrp=request.args.get("codgrp", type=int),
            search=request.args.get("q"),
            limit=request.args.get("limit", 500))

    @staticmethod
    def update_price() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        for f in ("codprice", "codgrp", "sc", "datastart"):
            if not d.get(f):
                return {"success": False, "error": f"{f} required"}
        return ServOuts26Store.update_price(
            int(d["codprice"]), int(d["codgrp"]), int(d["sc"]),
            d["datastart"], d.get("prices") or {})

    @staticmethod
    def rollback_pricelist() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        if not d.get("codprice"):
            return {"success": False, "error": "codprice required"}
        return ServOuts26Store.rollback_pricelist(int(d["codprice"]))

    # ---------------- staging / import / mapping ----------------

    @staticmethod
    def get_staging() -> Dict[str, Any]:
        return ServOuts26Store.get_staging(request.args.get("limit", 500))

    @staticmethod
    def load_staging() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        return ServOuts26Store.load_staging(
            d.get("rows") or [], replace=bool(d.get("replace")))

    @staticmethod
    def clear_staging() -> Dict[str, Any]:
        return ServOuts26Store.clear_staging()

    @staticmethod
    def get_config() -> Dict[str, Any]:
        return ServOuts26Store.get_config()

    @staticmethod
    def run_step() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        if not d.get("step"):
            return {"success": False, "error": "step required"}
        return ServOuts26Store.run_step(d["step"], d.get("profile"))

    @staticmethod
    def get_profiles() -> Dict[str, Any]:
        return ServOuts26Store.get_profiles()

    @staticmethod
    def save_profile() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        return ServOuts26Store.save_profile(d.get("name"), d.get("params") or {})

    @staticmethod
    def delete_profile() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        if not d.get("name"):
            return {"success": False, "error": "name required"}
        return ServOuts26Store.delete_profile(d["name"])

    # ---------------- journal ----------------

    @staticmethod
    def get_journal() -> Dict[str, Any]:
        return ServOuts26Store.get_journal(
            only_module=request.args.get("all") != "1",
            search=request.args.get("q"),
            limit=request.args.get("limit", 200))
