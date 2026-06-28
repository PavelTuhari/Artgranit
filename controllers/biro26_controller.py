"""Biro26 module controller — thin HTTP handlers.

All methods @staticmethod, return {success, data?/output?, error?}.
Destructive package operations (import/archive/rollback/merge/prepare/assign)
mutate the live OfficePlus ERP; the UI gates them behind confirmation.
"""
from __future__ import annotations

from typing import Any, Dict

from flask import request

from models.biro26_oracle_store import Biro26Store, G_PARAMS


class Biro26Controller:

    # -- connection / mapping ----------------------------------------
    @staticmethod
    def connection_test() -> Dict[str, Any]:
        return Biro26Store.test_connection()

    @staticmethod
    def get_profiles() -> Dict[str, Any]:
        return Biro26Store.get_profiles()

    @staticmethod
    def get_profile(profile_id: int) -> Dict[str, Any]:
        return Biro26Store.get_profile(profile_id)

    @staticmethod
    def create_profile() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        if not d.get("name"):
            return {"success": False, "error": "name is required"}
        params = {k: v for k, v in (d.get("params") or {}).items() if k in G_PARAMS}
        return Biro26Store.create_profile(d["name"], d.get("codprice", 1), params)

    @staticmethod
    def update_profile(profile_id: int) -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        params = {k: v for k, v in (d.get("params") or {}).items() if k in G_PARAMS}
        return Biro26Store.update_profile(profile_id, params, d.get("codprice"))

    @staticmethod
    def activate_profile(profile_id: int) -> Dict[str, Any]:
        return Biro26Store.activate_profile(profile_id)

    @staticmethod
    def list_g_params() -> Dict[str, Any]:
        return {"success": True, "data": G_PARAMS}

    # -- source feed --------------------------------------------------
    @staticmethod
    def get_goods() -> Dict[str, Any]:
        a = request.args
        return Biro26Store.get_goods(
            search=a.get("search"), brand=a.get("brand"),
            furnizor=a.get("furnizor"), status=a.get("status"),
            limit=a.get("limit", 200, type=int), offset=a.get("offset", 0, type=int))

    @staticmethod
    def goods_brands() -> Dict[str, Any]:
        return Biro26Store.goods_brands()

    @staticmethod
    def goods_count() -> Dict[str, Any]:
        return Biro26Store.goods_count()

    @staticmethod
    def validate_input() -> Dict[str, Any]:
        return Biro26Store.validate_input()

    @staticmethod
    def prepare_input() -> Dict[str, Any]:
        return Biro26Store.prepare_input()

    @staticmethod
    def assign_keys() -> Dict[str, Any]:
        return Biro26Store.assign_keys()

    # -- dictionary ---------------------------------------------------
    @staticmethod
    def get_univers() -> Dict[str, Any]:
        a = request.args
        return Biro26Store.get_univers(
            search=a.get("search"), gr1=a.get("gr1"), arhiv=a.get("arhiv"),
            limit=a.get("limit", 200, type=int), offset=a.get("offset", 0, type=int))

    @staticmethod
    def get_univers_card(cod: int) -> Dict[str, Any]:
        return Biro26Store.get_univers_card(cod)

    @staticmethod
    def import_univers() -> Dict[str, Any]:
        return Biro26Store.import_univers()

    @staticmethod
    def archive_univers() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        isarhiv = str(d.get("isarhiv", "1"))
        if isarhiv == "2":
            return {"success": False, "error": "ISARHIV='2' is blocked by trigger"}
        return Biro26Store.archive_univers(isarhiv)

    @staticmethod
    def fix_confusables() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        return Biro26Store.fix_denumirea_confusables(d.get("cod"))

    # -- groups / suppliers / categories -----------------------------
    @staticmethod
    def get_groups() -> Dict[str, Any]:
        return Biro26Store.get_groups(request.args.get("codprice", 1, type=int))

    @staticmethod
    def update_group() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        for k in ("codprice", "codgrp", "grpname"):
            if k not in d:
                return {"success": False, "error": f"{k} is required"}
        return Biro26Store.update_group(d["codprice"], d["codgrp"], d["grpname"])

    @staticmethod
    def import_groups() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        return Biro26Store.import_groups(d.get("codprice", 1))

    @staticmethod
    def merge_groups() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        for k in ("codprice", "src_codgrp", "dst_codgrp"):
            if k not in d:
                return {"success": False, "error": f"{k} is required"}
        return Biro26Store.merge_groups(d["codprice"], d["src_codgrp"], d["dst_codgrp"])

    @staticmethod
    def get_categories() -> Dict[str, Any]:
        return Biro26Store.get_categories()

    @staticmethod
    def get_suppliers() -> Dict[str, Any]:
        a = request.args
        return Biro26Store.get_suppliers(
            search=a.get("search"),
            limit=a.get("limit", 200, type=int), offset=a.get("offset", 0, type=int))

    @staticmethod
    def get_furnizori() -> Dict[str, Any]:
        return Biro26Store.get_furnizori()

    # -- price list ---------------------------------------------------
    @staticmethod
    def get_prices() -> Dict[str, Any]:
        a = request.args
        return Biro26Store.get_prices(
            codprice=a.get("codprice", 1, type=int),
            codgrp=a.get("codgrp", type=int),
            limit=a.get("limit", 200, type=int), offset=a.get("offset", 0, type=int))

    @staticmethod
    def get_dates() -> Dict[str, Any]:
        return Biro26Store.get_dates(request.args.get("codprice", 1, type=int))

    @staticmethod
    def update_price() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        for k in ("codprice", "codgrp", "sc", "datastart"):
            if k not in d:
                return {"success": False, "error": f"{k} is required"}
        return Biro26Store.update_price(
            d["codprice"], d["codgrp"], d["sc"], d["datastart"],
            d.get("pretv"), d.get("pretv1"), d.get("pretv2"))

    @staticmethod
    def import_dates() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        return Biro26Store.import_dates(d.get("codprice", 1), d.get("data"))

    @staticmethod
    def import_prices() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        return Biro26Store.import_prices(
            d.get("codprice", 1), d.get("date_start"), d.get("date_end"))

    @staticmethod
    def rollback_pricelist() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        return Biro26Store.rollback_pricelist(d.get("codprice", 1))
