"""Biro26 module controller — thin HTTP handlers.

All methods @staticmethod, return {success, data?/output?, error?}.
Destructive package operations (import/archive/rollback/merge/prepare/assign)
mutate the live OfficePlus ERP; the UI gates them behind confirmation.
"""
from __future__ import annotations

from typing import Any, Dict

from flask import request

from models.biro26_oracle_store import Biro26Store, G_PARAMS
from models.biro26_sources import Biro26Sources
from models import biro26_ai


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

    # -- sources (any SELECT) ----------------------------------------
    @staticmethod
    def list_sources() -> Dict[str, Any]:
        return Biro26Sources.list_sources()

    @staticmethod
    def sample_select() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        return Biro26Sources.sample(d.get("sql", ""), d.get("limit", 20))

    @staticmethod
    def create_source() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        if not d.get("name") or not d.get("sql"):
            return {"success": False, "error": "name and sql are required"}
        md = d.get("md")
        md_path = None
        if md:
            import os as _os
            sd = _os.path.join(_os.path.dirname(__file__), "..", "docs", "Biro26", "sources")
            _os.makedirs(sd, exist_ok=True)
            md_path = f"docs/Biro26/sources/{d['name']}.md"
            with open(_os.path.join(sd, f"{d['name']}.md"), "w", encoding="utf-8") as f:
                f.write(md)
        return Biro26Sources.create_source(d["name"], d["sql"], md_path)

    @staticmethod
    def ai_draft_md() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        s = Biro26Sources.sample(d.get("sql", ""), 10)
        if not s.get("success"):
            return s
        md = biro26_ai.draft_source_md(d.get("name", "source"), s["columns"], s["data"])
        return {"success": True, "data": {"md": md, "columns": s["columns"]}}

    @staticmethod
    def ai_suggest_mapping() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        s = Biro26Sources.sample(d.get("sql", ""), 10)
        if not s.get("success"):
            return s
        r = biro26_ai.suggest_mapping(s["columns"], s["data"], d.get("md", ""))
        r["columns"] = s["columns"]
        return r

    @staticmethod
    def source_columns() -> Dict[str, Any]:
        return Biro26Store.source_columns(request.args.get("source", "BIRO26_GOODS"))

    @staticmethod
    def source_sample() -> Dict[str, Any]:
        return Biro26Store.source_sample(
            request.args.get("source", "BIRO26_GOODS"),
            request.args.get("limit", 20, type=int))

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
    def import_images() -> Dict[str, Any]:
        return Biro26Store.import_images()

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
    def get_pricelists() -> Dict[str, Any]:
        return Biro26Store.get_pricelists()

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

    # -- stock balances (UN$SOLD.GET_SOLDT) ---------------------------
    @staticmethod
    def calc_stock() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        if not d.get("data_doc"):
            return {"success": False, "error": "data_doc is required"}
        return Biro26Store.calc_stock(
            d["data_doc"], d.get("dep_filter", ""),
            d.get("cont_filter"), d.get("pfilt"))

    @staticmethod
    def get_latest_stock_calc() -> Dict[str, Any]:
        return Biro26Store.get_latest_stock_calc()

    @staticmethod
    def get_stock_items() -> Dict[str, Any]:
        a = request.args
        return Biro26Store.get_stock_items(
            limit=a.get("limit", 500, type=int), offset=a.get("offset", 0, type=int))

    @staticmethod
    def get_products_stock() -> Dict[str, Any]:
        a = request.args
        return Biro26Store.get_products_stock(
            search=a.get("search"), gr1=a.get("gr1"),
            brand=a.get("brand"), categorie=a.get("categorie"),
            grupa=a.get("grupa"), price_date=a.get("price_date"),
            price_min=a.get("price_min", type=float),
            price_max=a.get("price_max", type=float),
            limit=a.get("limit", 200, type=int), offset=a.get("offset", 0, type=int))

    # ── price periods on Marfă/Stoc (y_ai_BIRO26.set_price/del_price) ──
    @staticmethod
    def product_price_history() -> Dict[str, Any]:
        sc = request.args.get("sc", type=int)
        if not sc:
            return {"success": False, "error": "sc is required"}
        return Biro26Store.get_price_history(
            sc, request.args.get("codprice", 1, type=int))

    @staticmethod
    def product_price_set() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        if not d.get("sc") or not d.get("date"):
            return {"success": False, "error": "sc and date are required"}

        def num(k):
            v = d.get(k)
            if v in (None, ""):
                return None
            try:
                return float(v)
            except (TypeError, ValueError):
                return None
        return Biro26Store.set_product_price(
            int(d["sc"]), str(d["date"]), retail1=num("retail1"),
            angro=num("angro"), ionline=num("ionline"),
            codprice=int(d.get("codprice") or 1))

    @staticmethod
    def product_price_delete() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        if not d.get("sc") or not d.get("date"):
            return {"success": False, "error": "sc and date are required"}
        return Biro26Store.delete_price_period(
            int(d["sc"]), str(d["date"]), codprice=int(d.get("codprice") or 1))

    @staticmethod
    def get_product_tree() -> Dict[str, Any]:
        return Biro26Store.get_product_tree()

    @staticmethod
    def update_product(cod: int) -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        return Biro26Store.update_product(
            cod, univers=d.get("univers"), goods=d.get("goods"),
            image=d.get("image"), bc_add=d.get("bc_add"), bc_remove=d.get("bc_remove"))

    @staticmethod
    def tree_rename() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        for k in ("level", "old", "new"):
            if not d.get(k):
                return {"success": False, "error": f"{k} is required"}
        return Biro26Store.rename_tree_node(d["level"], d["old"], d["new"], d.get("grupa"))

    @staticmethod
    def tree_move() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        for k in ("grupa", "categorie", "new_grupa"):
            if not d.get(k):
                return {"success": False, "error": f"{k} is required"}
        return Biro26Store.move_tree_categorie(d["grupa"], d["categorie"], d["new_grupa"])

    @staticmethod
    def get_product_brands() -> Dict[str, Any]:
        return Biro26Store.get_product_brands()

    @staticmethod
    def get_product_categories() -> Dict[str, Any]:
        return Biro26Store.get_product_categories()

    # -- web-shop (public page: self-registration + invoices) ---------
    # Password hashing: pbkdf2-sha256, format "pbkdf2$<salt-hex>$<hash-hex>".

    @staticmethod
    def _hash_pwd(pwd: str) -> str:
        import hashlib, os as _os, binascii
        salt = _os.urandom(16)
        dk = hashlib.pbkdf2_hmac("sha256", pwd.encode(), salt, 100000)
        return "pbkdf2$" + binascii.hexlify(salt).decode() + "$" + binascii.hexlify(dk).decode()

    @staticmethod
    def _check_pwd(pwd: str, stored: str) -> bool:
        import hashlib, binascii, hmac
        try:
            _, salt_hex, hash_hex = (stored or "").split("$")
            dk = hashlib.pbkdf2_hmac("sha256", pwd.encode(),
                                     binascii.unhexlify(salt_hex), 100000)
            return hmac.compare_digest(binascii.hexlify(dk).decode(), hash_hex)
        except Exception:
            return False

    @staticmethod
    def shop_register() -> Dict[str, Any]:
        from flask import session
        d = request.get_json(silent=True) or {}
        email = (d.get("email") or "").strip().lower()
        name = (d.get("full_name") or "").strip()
        pwd = d.get("password") or ""
        if not email or "@" not in email or not name or len(pwd) < 6:
            return {"success": False,
                    "error": "email, full_name and password (min 6) are required"}
        exists = Biro26Store.shop_client_by_email(email)
        if exists.get("data"):
            return {"success": False, "error": "email already registered"}
        r = Biro26Store.shop_register_client(
            email, name, d.get("phone") or "", Biro26Controller._hash_pwd(pwd))
        if r.get("success"):
            session["biro26_client"] = {"id": r["data"]["client_id"],
                                        "univers_cod": r["data"]["univers_cod"],
                                        "email": email, "name": name}
        return r

    @staticmethod
    def shop_login() -> Dict[str, Any]:
        from flask import session
        d = request.get_json(silent=True) or {}
        r = Biro26Store.shop_client_by_email(d.get("email") or "")
        c = r.get("data")
        if not c or not Biro26Controller._check_pwd(d.get("password") or "", c["pwd_hash"]):
            return {"success": False, "error": "invalid email or password"}
        session["biro26_client"] = {"id": c["id"], "univers_cod": c["univers_cod"],
                                    "email": c["email"], "name": c["full_name"]}
        return {"success": True, "data": {"name": c["full_name"], "email": c["email"]}}

    @staticmethod
    def shop_logout() -> Dict[str, Any]:
        from flask import session
        session.pop("biro26_client", None)
        return {"success": True}

    @staticmethod
    def shop_me() -> Dict[str, Any]:
        from flask import session
        c = session.get("biro26_client")
        return {"success": True,
                "data": {"name": c["name"], "email": c["email"]} if c else None}

    @staticmethod
    def shop_invoice() -> Dict[str, Any]:
        from flask import session
        d = request.get_json(silent=True) or {}
        items = d.get("items") or []
        c = session.get("biro26_client")
        if c:
            client_cod = c["univers_cod"]
        elif d.get("client_cod") and session.get("username"):
            # RO/EN: back-office operator may issue for an explicit client COD
            client_cod = int(d["client_cod"])
        else:
            return {"success": False, "error": "login required"}
        clean = []
        for it in items:
            try:
                cod, qty, price = int(it["cod"]), float(it["qty"]), float(it.get("price") or 0)
            except Exception:
                return {"success": False, "error": "bad item format"}
            if qty <= 0:
                return {"success": False, "error": "qty must be > 0"}
            clean.append({"cod": cod, "qty": qty, "price": price,
                          "name": str(it.get("name") or "")[:180]})
        # RO/EN: public client -> authoritative server-side prices only;
        #        operator -> server price fills items sent without a price
        need = [it["cod"] for it in clean] if c else \
               [it["cod"] for it in clean if it["price"] <= 0]
        if need:
            pr = Biro26Store.shop_prices_for(need)
            if not pr.get("success"):
                return pr
            for it in clean:
                if c or it["price"] <= 0:
                    it["price"] = pr["data"].get(it["cod"], 0)
        return Biro26Store.shop_create_invoice(client_cod, clean)
