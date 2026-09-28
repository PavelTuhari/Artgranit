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

    # ---------------- shop (public front-office) ----------------

    @staticmethod
    def _hash_pwd(pwd: str) -> str:
        import hashlib, os as _os, binascii
        salt = _os.urandom(16)
        dk = hashlib.pbkdf2_hmac("sha256", pwd.encode(), salt, 100000)
        return ("pbkdf2$" + binascii.hexlify(salt).decode()
                + "$" + binascii.hexlify(dk).decode())

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
    def shop_catalog() -> Dict[str, Any]:
        return ServOuts26Store.shop_catalog()

    @staticmethod
    def shop_register() -> Dict[str, Any]:
        import re
        from flask import session
        d = request.get_json(silent=True) or {}
        email = (d.get("email") or "").strip().lower()
        name = (d.get("full_name") or "").strip()
        phone = (d.get("phone") or "").strip()
        address = (d.get("address") or "").strip()
        is_company = bool(d.get("is_company"))
        idno = (d.get("idno") or "").strip()
        pwd = d.get("password") or ""
        if not name:
            return {"success": False, "error": "Nume/Denumire este obligatoriu"}
        if not email or "@" not in email:
            return {"success": False, "error": "E-mail valid este obligatoriu"}
        if not phone:
            return {"success": False, "error": "Telefonul este obligatoriu"}
        if is_company and not re.match(r"^\d{13}$", idno):
            return {"success": False,
                    "error": "IDNO (13 cifre) este obligatoriu pentru persoane juridice"}
        if len(pwd) < 6:
            return {"success": False, "error": "Parola: minim 6 caractere"}
        if ServOuts26Store.shop_client_by_email(email).get("data"):
            return {"success": False, "error": "email already registered"}
        r = ServOuts26Store.shop_register_client(
            email, name, phone, ServOuts26Controller._hash_pwd(pwd),
            address=address, idno=idno if is_company else "",
            is_company=is_company)
        if r.get("success"):
            session["srvo_client"] = {"id": r["data"]["client_id"],
                                      "email": email, "name": name}
        return r

    @staticmethod
    def shop_login() -> Dict[str, Any]:
        from flask import session
        d = request.get_json(silent=True) or {}
        c = ServOuts26Store.shop_client_by_email(d.get("email") or "").get("data")
        if not c or not ServOuts26Controller._check_pwd(
                d.get("password") or "", c["pwd_hash"]):
            return {"success": False, "error": "invalid email or password"}
        session["srvo_client"] = {"id": c["id"], "email": c["email"],
                                  "name": c["full_name"]}
        return {"success": True,
                "data": {"name": c["full_name"], "email": c["email"]}}

    @staticmethod
    def shop_logout() -> Dict[str, Any]:
        from flask import session
        session.pop("srvo_client", None)
        return {"success": True}

    @staticmethod
    def shop_me() -> Dict[str, Any]:
        from flask import session
        c = session.get("srvo_client")
        return {"success": True,
                "data": {"name": c["name"], "email": c["email"]} if c else None}

    @staticmethod
    def shop_order() -> Dict[str, Any]:
        from flask import session
        c = session.get("srvo_client")
        if not c:
            return {"success": False, "error": "login required"}
        d = request.get_json(silent=True) or {}
        items = d.get("items") or []
        clean = []
        for it in items:
            try:
                cod, qty = int(it["cod"]), float(it.get("qty") or 1)
            except Exception:
                return {"success": False, "error": "bad item format"}
            if qty <= 0:
                return {"success": False, "error": "qty must be > 0"}
            clean.append({"cod": cod, "qty": qty,
                          "name": str(it.get("name") or "")[:200]})
        if not clean:
            return {"success": False, "error": "empty cart"}
        # RO: preturile vin DOAR de pe server (anti-manipulare)
        # EN: prices are server-side ONLY (anti-tampering)
        pr = ServOuts26Store.shop_prices_for([i["cod"] for i in clean])
        if not pr.get("success"):
            return pr
        for it in clean:
            it["price"] = pr["data"].get(it["cod"], 0)
        return ServOuts26Store.shop_create_order(
            c["id"], clean, note=(d.get("note") or ""))

    @staticmethod
    def shop_my_orders() -> Dict[str, Any]:
        from flask import session
        c = session.get("srvo_client")
        if not c:
            return {"success": False, "error": "login required"}
        return ServOuts26Store.shop_client_orders(c["id"])

    @staticmethod
    def shop_order_detail(order_id: int) -> Dict[str, Any]:
        from flask import session
        c = session.get("srvo_client")
        if c:
            return ServOuts26Store.shop_order_detail(order_id, client_id=c["id"])
        if session.get("username"):
            # RO/EN: back-office session may open any order
            return ServOuts26Store.shop_order_detail(order_id)
        return {"success": False, "error": "login required"}

    # ---------------- orders (back-office) ----------------

    @staticmethod
    def orders_admin() -> Dict[str, Any]:
        return ServOuts26Store.shop_orders_admin(
            status=request.args.get("status"),
            limit=request.args.get("limit", 200))

    @staticmethod
    def order_set_status() -> Dict[str, Any]:
        d = request.get_json(silent=True) or {}
        if not d.get("order_id") or not d.get("status"):
            return {"success": False, "error": "order_id and status required"}
        return ServOuts26Store.shop_order_set_status(
            int(d["order_id"]), d["status"])

    # ---------------- journal ----------------

    @staticmethod
    def get_journal() -> Dict[str, Any]:
        return ServOuts26Store.get_journal(
            only_module=request.args.get("all") != "1",
            search=request.args.get("q"),
            limit=request.args.get("limit", 200))
