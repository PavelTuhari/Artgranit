"""Stratul de date al modulului Partner API.

RO: tabelele proprii PAPI_* plus REFOLOSIREA functiilor deja verificate ale
magazinului (Biro26Store / Biro26Report) — aceleasi preturi, stocuri si
documente ca in vitrina si in back-office; modulul nu isi inventeaza SQL
paralel pentru date pe care ERP-ul le da deja.
EN: PAPI_* tables + reuse of the proven shop store; no parallel SQL for data
the ERP already serves.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from models.biro26_db import Biro26DB
from models.biro26_oracle_store import Biro26Store, _rows

from modules.partner import rules


class PartnerStore:

    # ── parteneri ──────────────────────────────────────────────────────
    @staticmethod
    def partner_list() -> Dict[str, Any]:
        rows = _rows(Biro26DB().execute_query(
            "SELECT p.ID, p.EMAIL, p.NAME, p.UNIVERS_COD, p.ENABLED, "
            "TO_CHAR(p.CREATED,'DD.MM.YYYY') CREATED, "
            "TO_CHAR(p.LAST_LOGIN,'DD.MM.YYYY HH24:MI') LAST_LOGIN, "
            "u.DENUMIREA CLIENT_NAME "
            "FROM PAPI_PARTNER p LEFT JOIN TMS_UNIVERS u ON u.COD = p.UNIVERS_COD "
            "ORDER BY p.ID"))
        return {"success": True, "data": rows}

    @staticmethod
    def partner_save(d: Dict[str, Any]) -> Dict[str, Any]:
        email = str(d.get("email") or "").strip().lower()[:200]
        if "@" not in email:
            return {"success": False, "error": "email invalid"}
        try:
            univers_cod = int(d.get("univers_cod") or 0)
        except (TypeError, ValueError):
            return {"success": False, "error": "univers_cod invalid"}
        if not univers_cod:
            return {"success": False, "error": "univers_cod obligatoriu"}
        enabled = "1" if str(d.get("enabled", "1")) == "1" else "0"
        name = str(d.get("name") or "")[:200]
        db = Biro26DB()
        if d.get("id"):
            sets = ["EMAIL=:e", "NAME=:n", "UNIVERS_COD=:u", "ENABLED=:en"]
            p = {"e": email, "n": name, "u": univers_cod, "en": enabled,
                 "i": int(d["id"])}
            if d.get("password"):
                sets.append("PWD_HASH=:h")
                p["h"] = rules.hash_password(str(d["password"]))
            r = db.execute_dml(
                f"UPDATE PAPI_PARTNER SET {', '.join(sets)} WHERE ID=:i", p)
        else:
            if not d.get("password"):
                return {"success": False, "error": "parola obligatorie"}
            r = db.execute_dml(
                "INSERT INTO PAPI_PARTNER (EMAIL, PWD_HASH, NAME, UNIVERS_COD, "
                "ENABLED) VALUES (:e, :h, :n, :u, :en)",
                {"e": email, "h": rules.hash_password(str(d["password"])),
                 "n": name, "u": univers_cod, "en": enabled})
        if not r.get("success"):
            return {"success": False, "error": r.get("message")}
        PartnerStore.log(None, "partner_save", email)
        return {"success": True}

    @staticmethod
    def partner_by_email(email: str) -> Optional[Dict[str, Any]]:
        rows = _rows(Biro26DB().execute_query(
            "SELECT ID, EMAIL, PWD_HASH, NAME, UNIVERS_COD, ENABLED "
            "FROM PAPI_PARTNER WHERE EMAIL = :e",
            {"e": str(email or "").strip().lower()}))
        return rows[0] if rows else None

    # ── token-uri ──────────────────────────────────────────────────────
    @staticmethod
    def tokens_issue(partner_id: int) -> Dict[str, str]:
        """RO: emite perechea access+refresh; in baza intra doar amprentele.
        EN: issue the access+refresh pair; only fingerprints are stored."""
        access, refresh = rules.new_token(), rules.new_token()
        db = Biro26DB()
        db.execute_dml(
            "INSERT INTO PAPI_TOKEN (PARTNER_ID, KIND, TOKEN_HASH, EXPIRES) "
            "VALUES (:p, 'access', :h, SYSDATE + :ttl/86400)",
            {"p": int(partner_id), "h": rules.token_hash(access),
             "ttl": rules.ACCESS_TTL_S})
        db.execute_dml(
            "INSERT INTO PAPI_TOKEN (PARTNER_ID, KIND, TOKEN_HASH, EXPIRES) "
            "VALUES (:p, 'refresh', :h, SYSDATE + :ttl/86400)",
            {"p": int(partner_id), "h": rules.token_hash(refresh),
             "ttl": rules.REFRESH_TTL_S})
        db.execute_dml("UPDATE PAPI_PARTNER SET LAST_LOGIN = SYSDATE "
                       "WHERE ID = :p", {"p": int(partner_id)})
        return {"access": access, "refresh": refresh}

    @staticmethod
    def token_lookup(token: str, kind: str) -> Optional[Dict[str, Any]]:
        """RO: token valid -> partenerul lui; None altfel."""
        rows = _rows(Biro26DB().execute_query(
            "SELECT t.PARTNER_ID, p.EMAIL, p.UNIVERS_COD, p.ENABLED "
            "FROM PAPI_TOKEN t JOIN PAPI_PARTNER p ON p.ID = t.PARTNER_ID "
            "WHERE t.TOKEN_HASH = :h AND t.KIND = :k AND t.REVOKED = '0' "
            "AND t.EXPIRES > SYSDATE",
            {"h": rules.token_hash(token), "k": kind}))
        row = rows[0] if rows else None
        if row and str(row.get("enabled")) != "1":
            return None
        return row

    @staticmethod
    def token_revoke(token: str) -> None:
        Biro26DB().execute_dml(
            "UPDATE PAPI_TOKEN SET REVOKED='1' WHERE TOKEN_HASH = :h",
            {"h": rules.token_hash(token)})

    @staticmethod
    def tokens_revoke_all(partner_id: int) -> None:
        Biro26DB().execute_dml(
            "UPDATE PAPI_TOKEN SET REVOKED='1' WHERE PARTNER_ID = :p",
            {"p": int(partner_id)})

    # ── jurnal ─────────────────────────────────────────────────────────
    @staticmethod
    def log(partner_id: Optional[int], event: str, detail: str = "") -> None:
        try:
            Biro26DB().execute_dml(
                "INSERT INTO PAPI_LOG (PARTNER_ID, EVENT, DETAIL) "
                "VALUES (:p, :e, :d)",
                {"p": partner_id, "e": event[:40], "d": (detail or "")[:1000]})
        except Exception:                                    # noqa: BLE001
            pass

    # ── catalog: refolosim functiile magazinului ──────────────────────
    @staticmethod
    def products(args: Dict[str, Any]) -> Dict[str, Any]:
        limit = min(max(int(args.get("limit") or 100), 1), 1000)
        offset = max(int(args.get("offset") or 0), 0)
        sort_map = {"price_asc": "price_asc", "price_desc": "price_desc",
                    "name_asc": "name", "name_desc": "name_desc"}
        return Biro26Store.get_products_stock(
            search=args.get("search"),
            grupa=args.get("category"), brand=args.get("brand"),
            price_min=_f(args.get("min_price")),
            price_max=_f(args.get("max_price")),
            limit=limit, offset=offset, with_count=True,
            sort=sort_map.get(str(args.get("sort") or ""), "name"))

    @staticmethod
    def products_by_codes(codes: List[str]) -> List[Dict[str, Any]]:
        """RO: pina la 1000 de coduri (COD numeric sau CODVECHI) — pentru
        /product/batch si /quantity/batch."""
        out: List[Dict[str, Any]] = []
        nums = [c for c in codes if str(c).isdigit()][:1000]
        arts = [str(c)[:60] for c in codes if not str(c).isdigit()][:1000]
        db = Biro26DB()
        cods = set(int(c) for c in nums)
        if arts:
            marks = ",".join(f":a{i}" for i in range(len(arts)))
            rows = _rows(db.execute_query(
                f"SELECT COD FROM TMS_UNIVERS WHERE CODVECHI IN ({marks})",
                {f"a{i}": a for i, a in enumerate(arts)}))
            cods |= {int(r["cod"]) for r in rows}
        for cod in list(cods)[:1000]:
            r = Biro26Store.get_products_stock(cod=cod, limit=1)
            out.extend(r.get("data") or [])
        return out

    @staticmethod
    def product_one(pid: str) -> Optional[Dict[str, Any]]:
        rows = PartnerStore.products_by_codes([pid])
        return rows[0] if rows else None

    # ── modificari incrementale (/api/changes) ────────────────────────
    @staticmethod
    def changes(since: str, entity: str, limit: int) -> Dict[str, Any]:
        """RO: modificarile de la `since` incoace, pe entitati — derivate din
        datele pe care ERP-ul le are deja: descrierile (product), lista de
        preturi in vigoare (price) si diferenta dintre ultimele doua
        instantanee de stoc (quantity). EN: incremental changes derived from
        existing ERP data."""
        limit = min(max(limit, 1), 1000)
        db = Biro26DB()
        out: List[Dict[str, Any]] = []
        p = {"s": since, "lim": limit + 1}
        if entity in ("", "product"):
            rows = _rows(db.execute_query(
                "SELECT COD, TO_CHAR(UPDATED_AT,'YYYY-MM-DD\"T\"HH24:MI:SS') TS "
                "FROM (SELECT COD, UPDATED_AT FROM TMS_MPT_WEBATTR "
                "  WHERE UPDATED_AT > TO_DATE(:s,'YYYY-MM-DD\"T\"HH24:MI:SS') "
                "  ORDER BY UPDATED_AT) WHERE ROWNUM <= :lim", p))
            out += [{"entity": "product", "action": "updated",
                     "entity_id": str(r["cod"]), "changed_at": r["ts"]}
                    for r in rows]
        if entity in ("", "price"):
            rows = _rows(db.execute_query(
                "SELECT SC, TO_CHAR(DATASTART,'YYYY-MM-DD\"T\"HH24:MI:SS') TS "
                "FROM (SELECT SC, DATASTART FROM TPR1D_PERPRLIST "
                "  WHERE CODPRICE = 1 "
                "  AND DATASTART > TO_DATE(:s,'YYYY-MM-DD\"T\"HH24:MI:SS') "
                "  ORDER BY DATASTART) WHERE ROWNUM <= :lim", p))
            out += [{"entity": "price", "action": "updated",
                     "entity_id": str(r["sc"]), "changed_at": r["ts"]}
                    for r in rows]
        if entity in ("", "quantity"):
            # RO: diferenta intre ultimele doua instantanee de stoc
            rows = _rows(db.execute_query(
                "SELECT sc, TO_CHAR(d,'YYYY-MM-DD\"T\"HH24:MI:SS') TS FROM ("
                " SELECT a.sc, c1.DATA_DOC d FROM "
                "  (SELECT sc, SUM(cant) q FROM YBIRO_STOCK_CALC_ITEM WHERE calc_id = "
                "    (SELECT MAX(id) FROM YBIRO_STOCK_CALC WHERE is_latest='1') GROUP BY sc) a "
                "  FULL JOIN "
                "  (SELECT sc, SUM(cant) q FROM YBIRO_STOCK_CALC_ITEM WHERE calc_id = "
                "    (SELECT MAX(id) FROM YBIRO_STOCK_CALC WHERE is_latest <> '1') GROUP BY sc) b "
                "  ON b.sc = a.sc "
                "  CROSS JOIN (SELECT MAX(DATA_DOC) DATA_DOC FROM YBIRO_STOCK_CALC "
                "              WHERE is_latest='1') c1 "
                "  WHERE NVL(a.q,0) <> NVL(b.q,0) "
                "  AND c1.DATA_DOC > TO_DATE(:s,'YYYY-MM-DD\"T\"HH24:MI:SS') "
                ") WHERE ROWNUM <= :lim", p))
            out += [{"entity": "quantity", "action": "updated",
                     "entity_id": str(r["sc"]), "changed_at": r["ts"]}
                    for r in rows]
        out.sort(key=lambda c: c["changed_at"])
        has_more = len(out) > limit
        out = out[:limit]
        return {"changes": out,
                "next_since": out[-1]["changed_at"] if out else since,
                "has_more": has_more}

    # ── comenzi: direct in ERP-ul una.md ──────────────────────────────
    @staticmethod
    def order_create(partner: Dict[str, Any],
                     payload: Dict[str, Any]) -> Dict[str, Any]:
        """RO: comanda partenerului devine un cont de plata web REAL in ERP
        (acelasi drum ca B2B-ul si vitrina: Y_AI_BIRO26). Preturile se iau
        din coloana clientului (fizica/juridica/contract), nu din cerere —
        partenerul nu isi poate dicta pretul.
        EN: the order becomes a real web invoice via the proven pipeline;
        prices come from the client's price column, never from the request."""
        client_cod = int(partner["univers_cod"])
        price_field = Biro26Store.client_price_field(client_cod) or "retail1"
        items = []
        for line in payload["products"]:
            pid = str(line.get("uuid") or line.get("code"))
            row = PartnerStore.product_one(pid)
            if not row:
                return {"success": False,
                        "error": f"product not found: {pid}"}
            price = rules._num(row.get(price_field)) or rules._num(
                row.get("retail1")) or 0
            if price <= 0:
                return {"success": False,
                        "error": f"product without price: {pid}"}
            items.append({"cod": int(row["cod"]),
                          "qty": int(line["quantity"]),
                          "price": price,
                          "name": row.get("denumirea")})
        if payload.get("validate_only"):
            return {"success": True, "validated": True,
                    "items": len(items),
                    "total": round(sum(i["qty"] * i["price"] for i in items), 2)}
        coment = (f"Partner API: {partner['email']} · "
                  f"delivery={payload['delivery']} payment={payload['payment']}")
        sd = payload.get("shipping_data")
        if isinstance(sd, dict):
            coment += " · " + "; ".join(f"{k}={v}" for k, v in list(sd.items())[:8])
        r = Biro26Store.shop_create_invoice(client_cod, items, coment[:250])
        if not r.get("success"):
            return r
        PartnerStore.log(int(partner["partner_id"]), "order",
                         f"doc={r['data'].get('cod')} nr={r['data'].get('nrmanual')}")
        return {"success": True, "data": r["data"]}

    @staticmethod
    def orders_list(partner: Dict[str, Any], limit: int) -> Dict[str, Any]:
        from models.biro26_report import Biro26Report
        return Biro26Report.docs_list(str(partner["univers_cod"]),
                                      min(max(limit, 1), 200))


def _f(v: Any) -> Optional[float]:
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None
