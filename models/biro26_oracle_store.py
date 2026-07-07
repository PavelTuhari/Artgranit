"""Biro26 module Oracle store — all SQL + YBIRO_Import_Marfa package calls.

Target DB: OfficePlus ERP (Oracle 11g) via models.biro26_db.Biro26DB (subprocess
worker, thick mode). Prefix for our own objects: YBIRO_.

11g notes: no OFFSET/FETCH — pagination uses the ROWNUM pattern (see _page()).
Multi-statement atomic ops use db.execute_script([...]) (one transaction).
"""
from __future__ import annotations

import re as _re
from typing import Any, Dict, List, Optional

from models.biro26_db import Biro26DB

PKG = "YBIRO_Import_Marfa"

# Canonical configurable package vars (without g_ prefix), TZ §7.1.
G_PARAMS: List[str] = [
    "tbl_goods", "col_key", "col_id", "col_brand", "col_articol",
    "col_denumire", "col_angro", "col_ionline", "col_retail", "seq_key",
    "codprice", "um", "gr1", "tip", "caccess", "codtva",
    "date_start", "date_end", "group_type", "empty_brand",
    "len_codvechi", "len_denumire", "isarhiv_arc", "isarhiv_lock",
    "confus_max_cyr",
]

# g_* typed as NUMBER / PLS_INTEGER → emit unquoted in PL/SQL
_NUMERIC = {"codprice", "len_codvechi", "len_denumire", "confus_max_cyr"}
# g_* typed as DATE → emit DATE 'YYYY-MM-DD'
_DATE = {"date_start", "date_end"}


def _rows(r: Dict) -> List[Dict]:
    if not r.get("success") or not r.get("data"):
        return []
    cols = [c.lower() for c in r["columns"]]
    out = [dict(zip(cols, row)) for row in r["data"]]
    for d in out:           # drop the ROWNUM pagination artifact from _page()
        d.pop("rn", None)
    return out


def _result(r: Dict) -> Dict[str, Any]:
    """Standard read result: surface DB errors instead of masking as empty success."""
    if not r.get("success"):
        return {"success": False, "error": r.get("message")}
    return {"success": True, "data": _rows(r)}


def _q(v: Any) -> str:
    return "'" + str(v).replace("'", "''") + "'"


_IDENT_RE = _re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,60}$")


def _is_ident(name: str) -> bool:
    return bool(name and _IDENT_RE.match(name))


def _page(inner_sql: str, limit: int, offset: int) -> str:
    """Wrap an ORDER-BY'd inner SELECT with Oracle 11g ROWNUM pagination."""
    return (f"SELECT * FROM (SELECT a.*, ROWNUM rn FROM ({inner_sql}) a "
            f"WHERE ROWNUM <= {int(offset) + int(limit)}) WHERE rn > {int(offset)}")


def build_gset_block(profile: Dict[str, Any]) -> str:
    """Build PL/SQL assignment lines that set YBIRO_Import_Marfa.g_* vars."""
    lines = []
    for name, val in profile.items():
        if name not in G_PARAMS or val is None or val == "":
            continue
        if name in _NUMERIC:
            rhs = str(int(val))  # numeric param: coerce, reject non-integer
        elif name in _DATE:
            rhs = f"DATE {_q(val)}"
        else:
            rhs = _q(val)
        lines.append(f"  {PKG}.g_{name} := {rhs};")
    return "\n".join(lines)


class Biro26Store:
    """All OfficePlus CRUD + package orchestration for Biro26."""

    # ============================================================
    # CONNECTION
    # ============================================================
    @staticmethod
    def test_connection() -> Dict[str, Any]:
        try:
            return Biro26DB().test_connection()
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ============================================================
    # MAPPING PROFILES
    # ============================================================
    @staticmethod
    def get_profiles() -> Dict[str, Any]:
        try:
            r = Biro26DB().execute_query(
                "SELECT id, name, codprice, is_default, "
                "TO_CHAR(created_at,'DD.MM.YYYY HH24:MI') created_at, created_by "
                "FROM YBIRO_MAP_PROFILE ORDER BY is_default DESC, name")
            return _result(r)
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_profile(profile_id: int) -> Dict[str, Any]:
        try:
            db = Biro26DB()
            head = _rows(db.execute_query(
                "SELECT id, name, codprice, is_default FROM YBIRO_MAP_PROFILE WHERE id=:id",
                {"id": profile_id}))
            if not head:
                return {"success": False, "error": "profile not found"}
            params = _rows(db.execute_query(
                "SELECT param_name, param_value FROM YBIRO_MAP_PARAM WHERE profile_id=:id",
                {"id": profile_id}))
            pmap = {p["param_name"]: p["param_value"] for p in params}
            return {"success": True, "data": {**head[0], "params": pmap}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def create_profile(name: str, codprice: int, params: Dict[str, str]) -> Dict[str, Any]:
        try:
            stmts: List[Dict[str, Any]] = [{
                "sql": "INSERT INTO YBIRO_MAP_PROFILE(name, codprice, is_default) "
                       "VALUES(:n, :c, '0')",
                "params": {"n": name, "c": codprice}, "kind": "dml",
            }]
            for k, v in params.items():
                if k in G_PARAMS:
                    stmts.append({
                        "sql": "INSERT INTO YBIRO_MAP_PARAM(profile_id, param_name, param_value) "
                               "SELECT id, :k, :v FROM YBIRO_MAP_PROFILE WHERE name=:n",
                        "params": {"k": k, "v": str(v), "n": name}, "kind": "dml",
                    })
            stmts.append({
                "sql": "SELECT id FROM YBIRO_MAP_PROFILE WHERE name=:n",
                "params": {"n": name}, "kind": "query",
            })
            res = Biro26DB().execute_script(stmts)
            if not res.get("success"):
                return {"success": False, "error": res.get("message")}
            last = res["results"][-1]
            new_id = last["data"][0][0] if last.get("data") else None
            return {"success": True, "data": {"id": new_id}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def update_profile(profile_id: int, params: Dict[str, str],
                       codprice: Optional[int] = None) -> Dict[str, Any]:
        try:
            stmts: List[Dict[str, Any]] = []
            if codprice is not None:
                stmts.append({
                    "sql": "UPDATE YBIRO_MAP_PROFILE SET codprice=:c WHERE id=:id",
                    "params": {"c": codprice, "id": profile_id}, "kind": "dml"})
            for k, v in params.items():
                if k not in G_PARAMS:
                    continue
                stmts.append({
                    "sql": "MERGE INTO YBIRO_MAP_PARAM t "
                           "USING (SELECT :p pid, :k pn FROM dual) s "
                           "ON (t.profile_id=s.pid AND t.param_name=s.pn) "
                           "WHEN MATCHED THEN UPDATE SET param_value=:v "
                           "WHEN NOT MATCHED THEN INSERT(profile_id,param_name,param_value) "
                           "VALUES(:p,:k,:v)",
                    "params": {"p": profile_id, "k": k, "v": str(v)}, "kind": "dml"})
            if not stmts:
                return {"success": True}
            res = Biro26DB().execute_script(stmts)
            return {"success": res.get("success", False), "error": res.get("message") or None}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def activate_profile(profile_id: int) -> Dict[str, Any]:
        try:
            res = Biro26DB().execute_script([
                {"sql": "UPDATE YBIRO_MAP_PROFILE SET is_default='0'",
                 "params": {}, "kind": "dml"},
                {"sql": "UPDATE YBIRO_MAP_PROFILE SET is_default='1' WHERE id=:id",
                 "params": {"id": profile_id}, "kind": "dml"},
            ])
            return {"success": res.get("success", False), "error": res.get("message") or None}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # internal: active profile params for the g_* preamble
    @staticmethod
    def _active_params() -> Dict[str, str]:
        rows = _rows(Biro26DB().execute_query(
            "SELECT param_name, param_value FROM YBIRO_MAP_PARAM WHERE profile_id="
            "(SELECT id FROM (SELECT id FROM YBIRO_MAP_PROFILE WHERE is_default='1' "
            " ORDER BY id) WHERE ROWNUM=1)"))
        return {r["param_name"]: r["param_value"] for r in rows}

    @staticmethod
    def _run_pkg(proc_call: str, capture: bool = True) -> Dict[str, Any]:
        """Set active g_* then run a package proc in ONE block (session state)."""
        try:
            preamble = build_gset_block(Biro26Store._active_params())
            block = f"BEGIN\n{preamble}\n  {PKG}.{proc_call}\nEND;"
            res = Biro26DB().call_proc(block, capture_output=capture)
            return {"success": res.get("success", False),
                    "output": res.get("output_lines", []),
                    "error": res.get("message") or None}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ============================================================
    # SOURCE FEED — BIRO26_GOODS
    # ============================================================
    @staticmethod
    def get_goods(search: Optional[str] = None, brand: Optional[str] = None,
                  furnizor: Optional[str] = None, status: Optional[str] = None,
                  limit: int = 200, offset: int = 0) -> Dict[str, Any]:
        try:
            # ROW_STATUS: IN_DICT (key already in dictionary), CONFLICT (same
            # CODVECHI maps to an existing product), else NEW.
            inner = """
              SELECT g.ID, g.ARTICOL, g.DENUMIRE, g.BRAND, g.FURNIZOR,
                     g.ANGRO, g.IONLINE, g.RETAIL1, g.STOC, g.COD_UNIVERS,
                     g.PHOTO_URL, g.IMAGE_LINK,
                     CASE
                       WHEN g.COD_UNIVERS IS NOT NULL
                         AND EXISTS (SELECT 1 FROM TMS_UNIVERS u
                                     WHERE u.COD = g.COD_UNIVERS) THEN 'IN_DICT'
                       WHEN EXISTS (SELECT 1 FROM TMS_UNIVERS u
                                    WHERE u.CODVECHI = SUBSTR(g.ARTICOL,1,20)
                                      AND u.TIP='P') THEN 'CONFLICT'
                       ELSE 'NEW'
                     END AS ROW_STATUS
                FROM BIRO26_GOODS g
               WHERE 1=1"""
            params: Dict[str, Any] = {}
            if search:
                inner += " AND (UPPER(g.DENUMIRE) LIKE UPPER(:s) OR UPPER(g.ARTICOL) LIKE UPPER(:s))"
                params["s"] = f"%{search}%"
            if brand:
                inner += " AND g.BRAND = :brand"; params["brand"] = brand
            if furnizor:
                inner += " AND g.FURNIZOR = :furnizor"; params["furnizor"] = furnizor
            inner += " ORDER BY g.ID"
            r = Biro26DB().execute_query(_page(inner, limit, offset), params)
            if not r.get("success"):
                return {"success": False, "error": r.get("message")}
            data = _rows(r)
            if status:
                data = [d for d in data if d.get("row_status") == status]
            return {"success": True, "data": data}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def goods_brands() -> Dict[str, Any]:
        try:
            r = Biro26DB().execute_query(
                "SELECT BRAND, COUNT(*) CNT FROM BIRO26_GOODS GROUP BY BRAND ORDER BY BRAND")
            return _result(r)
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def goods_count() -> Dict[str, Any]:
        try:
            r = Biro26DB().execute_query("SELECT COUNT(*) CNT FROM BIRO26_GOODS")
            return {"success": True, "data": {"count": r["data"][0][0] if r["data"] else 0}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def validate_input() -> Dict[str, Any]:
        return Biro26Store._run_pkg("validate_input;", capture=True)

    @staticmethod
    def prepare_input() -> Dict[str, Any]:
        return Biro26Store._run_pkg("prepare_input;", capture=True)

    @staticmethod
    def assign_keys() -> Dict[str, Any]:
        return Biro26Store._run_pkg("assign_keys;", capture=True)

    @staticmethod
    def source_columns(source: str) -> Dict[str, Any]:
        """Column names of a table/view source (identifier-validated)."""
        if not _is_ident(source):
            return {"success": False, "error": "invalid source name"}
        try:
            r = Biro26DB().execute_query(f"SELECT * FROM {source} WHERE ROWNUM = 0")
            if not r.get("success"):
                return {"success": False, "error": r.get("message")}
            return {"success": True, "data": list(r.get("columns", []))}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def source_sample(source: str, limit: int = 20) -> Dict[str, Any]:
        if not _is_ident(source):
            return {"success": False, "error": "invalid source name"}
        try:
            r = Biro26DB().execute_query(
                f"SELECT * FROM {source} WHERE ROWNUM <= :n", {"n": int(limit)})
            if not r.get("success"):
                return {"success": False, "error": r.get("message")}
            return {"success": True, "columns": list(r.get("columns", [])),
                    "data": [list(row) for row in r.get("data", [])]}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ============================================================
    # DICTIONARY — TMS_UNIVERS + TMS_MPT
    # ============================================================
    @staticmethod
    def get_univers(search: Optional[str] = None, gr1: Optional[str] = None,
                    arhiv: Optional[str] = None, limit: int = 200,
                    offset: int = 0) -> Dict[str, Any]:
        try:
            inner = ("SELECT COD, CODVECHI, DENUMIREA, NAMERUS, GR1, UM, ISARHIV "
                     "FROM TMS_UNIVERS WHERE TIP='P'")
            params: Dict[str, Any] = {}
            if search:
                inner += (" AND (UPPER(DENUMIREA) LIKE UPPER(:s) "
                          "OR UPPER(NAMERUS) LIKE UPPER(:s) OR CODVECHI LIKE :s "
                          "OR EXISTS (SELECT 1 FROM TMS_MPT_BARCODE b "
                          "  WHERE b.COD = TMS_UNIVERS.COD AND b.BARCODE LIKE :s))")
                params["s"] = f"%{search}%"
            if gr1:
                inner += " AND GR1=:gr1"; params["gr1"] = gr1
            if arhiv == "active":
                inner += " AND (ISARHIV IS NULL OR ISARHIV='0')"
            elif arhiv == "archived":
                inner += " AND ISARHIV IS NOT NULL AND ISARHIV<>'0'"
            inner += " ORDER BY DENUMIREA"
            r = Biro26DB().execute_query(_page(inner, limit, offset), params)
            return _result(r)
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_univers_card(cod: int) -> Dict[str, Any]:
        try:
            db = Biro26DB()
            u = _rows(db.execute_query("SELECT * FROM TMS_UNIVERS WHERE COD=:c", {"c": cod}))
            if not u:
                return {"success": False, "error": "not found"}
            mpt = _rows(db.execute_query("SELECT * FROM TMS_MPT WHERE COD=:c", {"c": cod}))
            # primary image: ERP VMS_MPT_TVR.IE_LINKADRES (keyed by COD); fallback to feed
            tvr = _rows(db.execute_query(
                "SELECT IE_LINKADRES FROM VMS_MPT_TVR WHERE COD=:c AND ROWNUM=1", {"c": cod}))
            img = _rows(db.execute_query(
                "SELECT PHOTO_URL, IMAGE_LINK FROM BIRO26_GOODS "
                "WHERE COD_UNIVERS = :c AND ROWNUM = 1", {"c": cod}))
            photo = img[0] if img else {}
            ie = tvr[0].get("ie_linkadres") if tvr else None
            barcodes = [b["barcode"] for b in _rows(db.execute_query(
                "SELECT BARCODE FROM TMS_MPT_BARCODE WHERE COD=:c ORDER BY BARCODE",
                {"c": cod}))]
            goods = _rows(db.execute_query(
                "SELECT BRAND, GRUPA, CATEGORIE, ANGRO, IONLINE, RETAIL1 "
                "FROM BIRO26_GOODS WHERE COD_UNIVERS=:c AND ROWNUM=1", {"c": cod}))
            return {"success": True,
                    "data": {"univers": u[0], "mpt": mpt[0] if mpt else None,
                             "photo_url": ie or photo.get("photo_url"),
                             "image_link": photo.get("image_link"),
                             "ie_linkadres": ie,
                             "barcodes": barcodes,
                             "goods": goods[0] if goods else None}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def import_univers() -> Dict[str, Any]:
        return Biro26Store._run_pkg("import_univers;", capture=True)

    @staticmethod
    def import_images() -> Dict[str, Any]:
        """Import feed image links into TMS_MPT_TVR.IE_LINKADRES (keyed by COD).

        Set-based MERGE from BIRO26_GOODS: one row per COD_UNIVERS (PHOTO_URL,
        else IMAGE_LINK). Idempotent — re-run after a new feed updates/inserts links.
        Backs the product-card image (VMS_MPT_TVR is a view over TMS_MPT_TVR)."""
        try:
            r = Biro26DB().execute_dml(
                "MERGE INTO TMS_MPT_TVR t USING ("
                "  SELECT COD_UNIVERS AS COD, "
                "         MAX(SUBSTR(NVL(PHOTO_URL, IMAGE_LINK),1,1000)) AS URL "
                "  FROM BIRO26_GOODS "
                "  WHERE COD_UNIVERS IS NOT NULL "
                "    AND (PHOTO_URL IS NOT NULL OR IMAGE_LINK IS NOT NULL) "
                "  GROUP BY COD_UNIVERS"
                ") s ON (t.COD = s.COD) "
                "WHEN MATCHED THEN UPDATE SET t.IE_LINKADRES = s.URL "
                "WHEN NOT MATCHED THEN INSERT (COD, IE_LINKADRES) VALUES (s.COD, s.URL)")
            if not r.get("success"):
                return {"success": False, "error": r.get("message")}
            return {"success": True, "rows": r.get("rowcount", 0)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def archive_univers(isarhiv: str = "1") -> Dict[str, Any]:
        # value '2' is blocked by trigger TMS_UNIVERS_DONT_DELETE; guard upstream too
        return Biro26Store._run_pkg(f"archive_univers(p_isarhiv => {_q(isarhiv)});",
                                    capture=True)

    @staticmethod
    def fix_denumirea_confusables(cod: Optional[int] = None) -> Dict[str, Any]:
        arg = f"p_cod => {int(cod)}" if cod is not None else "p_cod => NULL"
        return Biro26Store._run_pkg(f"fix_denumirea_confusables({arg});", capture=True)

    # ============================================================
    # GROUPS — VPR01M_GROUPS + category tree (read-only)
    # ============================================================
    @staticmethod
    def get_groups(codprice: int = 1) -> Dict[str, Any]:
        try:
            r = Biro26DB().execute_query(
                "SELECT CODPRICE, CODGRP, GRPNAME, TYPE_SC, GR1_SC "
                "FROM VPR01M_GROUPS WHERE CODPRICE=:c ORDER BY CODGRP", {"c": codprice})
            return _result(r)
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def update_group(codprice: int, codgrp: int, grpname: str) -> Dict[str, Any]:
        try:
            return Biro26DB().execute_dml(
                "UPDATE VPR01M_GROUPS SET GRPNAME=:n WHERE CODPRICE=:c AND CODGRP=:g",
                {"n": grpname, "c": codprice, "g": codgrp})
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def import_groups(codprice: int = 1) -> Dict[str, Any]:
        return Biro26Store._run_pkg(f"import_groups(p_codprice => {int(codprice)});",
                                    capture=True)

    @staticmethod
    def merge_groups(codprice: int, src_codgrp: int, dst_codgrp: int) -> Dict[str, Any]:
        """Move prices from src group to dst, then delete empty src group (one tx)."""
        try:
            res = Biro26DB().execute_script([
                {"sql": "UPDATE TPR1D_PERPRLIST SET CODGRP=:dst "
                        "WHERE CODPRICE=:c AND CODGRP=:src",
                 "params": {"dst": dst_codgrp, "c": codprice, "src": src_codgrp},
                 "kind": "dml"},
                {"sql": "DELETE FROM VPR01M_GROUPS WHERE CODPRICE=:c AND CODGRP=:src",
                 "params": {"c": codprice, "src": src_codgrp}, "kind": "dml"},
            ])
            return {"success": res.get("success", False), "error": res.get("message") or None}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_categories() -> Dict[str, Any]:
        """Read-only category roots from TMS_SYSGR (phase 1; labels in TEXT)."""
        try:
            r = Biro26DB().execute_query(
                "SELECT ID0, TEXT AS LABEL, TIP, GR1, NODETYPE "
                "FROM TMS_SYSGR ORDER BY ID0")
            if not r.get("success"):
                return {"success": False, "error": r.get("message")}
            return _result(r)
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ============================================================
    # SUPPLIERS — TMS_ORG (+ name via TMS_UNIVERS TIP='O') / FURNIZOR
    # ============================================================
    @staticmethod
    def get_suppliers(search: Optional[str] = None,
                      limit: int = 200, offset: int = 0) -> Dict[str, Any]:
        try:
            inner = ("SELECT o.COD, u.DENUMIREA AS NAME, o.GR1, o.ADRESS, o.BANK, "
                     "o.CODFISCAL FROM TMS_ORG o "
                     "LEFT JOIN TMS_UNIVERS u ON u.COD=o.COD AND u.TIP='O'")
            params: Dict[str, Any] = {}
            if search:
                inner += " WHERE UPPER(u.DENUMIREA) LIKE UPPER(:s)"
                params["s"] = f"%{search}%"
            inner += " ORDER BY u.DENUMIREA"
            r = Biro26DB().execute_query(_page(inner, limit, offset), params)
            return _result(r)
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_furnizori() -> Dict[str, Any]:
        try:
            r = Biro26DB().execute_query(
                "SELECT FURNIZOR, COUNT(*) CNT FROM BIRO26_GOODS "
                "WHERE FURNIZOR IS NOT NULL GROUP BY FURNIZOR ORDER BY FURNIZOR")
            return _result(r)
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ============================================================
    # PRICE LIST — VPR1D_PRDATE / VTPR1D_PERPRLIST
    # ============================================================
    @staticmethod
    def get_pricelists() -> Dict[str, Any]:
        """Price lists (VPR0M_PRICES) — left panel of the Windows-style layout."""
        try:
            return _result(Biro26DB().execute_query(
                "SELECT CODPRICE, PRICENAME, VAL, TYPE_SC FROM VPR0M_PRICES ORDER BY CODPRICE"))
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_prices(codprice: int = 1, codgrp: Optional[int] = None,
                   limit: int = 200, offset: int = 0) -> Dict[str, Any]:
        try:
            # join item name (TMS_UNIVERS) + image link (VMS_MPT_TVR.IE_LINKADRES)
            inner = ("SELECT p.CODPRICE, p.CODGRP, p.SC, u.DENUMIREA, "
                     "p.PRETV, p.PRETV1, p.PRETV2, p.PRETV3, "
                     "TO_CHAR(p.DATASTART,'DD.MM.YYYY') DATASTART, m.IE_LINKADRES IMAGE "
                     "FROM VTPR1D_PERPRLIST p "
                     "LEFT JOIN TMS_UNIVERS u ON u.COD = p.SC "
                     "LEFT JOIN VMS_MPT_TVR m ON m.COD = p.SC "
                     "WHERE p.CODPRICE=:c")
            params: Dict[str, Any] = {"c": codprice}
            if codgrp is not None:
                inner += " AND p.CODGRP=:g"; params["g"] = codgrp
            inner += " ORDER BY p.CODGRP, u.DENUMIREA"
            r = Biro26DB().execute_query(_page(inner, limit, offset), params)
            return _result(r)
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_dates(codprice: int = 1) -> Dict[str, Any]:
        try:
            # DATAEND is computed inside the view via a date conversion that raises
            # ORA-01843 under our session NLS, so it is omitted (open-end is implicit).
            r = Biro26DB().execute_query(
                "SELECT CODPRICE, CODGRP, TO_CHAR(DATA,'DD.MM.YYYY') DATA, NRDOC "
                "FROM VPR1D_PRDATE WHERE CODPRICE=:c ORDER BY CODGRP",
                {"c": codprice})
            if not r.get("success"):
                return {"success": False, "error": r.get("message")}
            return _result(r)
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def update_price(codprice: int, codgrp: int, sc: int, datastart: str,
                     pretv=None, pretv1=None, pretv2=None) -> Dict[str, Any]:
        """Update price cells via the INSTEAD OF trigger on VTPR1D_PERPRLIST.
        datastart is 'DD.MM.YYYY'. PK = (CODPRICE, CODGRP, SC, DATASTART)."""
        try:
            return Biro26DB().execute_dml(
                "UPDATE VTPR1D_PERPRLIST SET PRETV=:p, PRETV1=:p1, PRETV2=:p2 "
                "WHERE CODPRICE=:c AND CODGRP=:g AND SC=:sc "
                "AND DATASTART=TO_DATE(:d,'DD.MM.YYYY')",
                {"p": pretv, "p1": pretv1, "p2": pretv2,
                 "c": codprice, "g": codgrp, "sc": sc, "d": datastart})
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def import_dates(codprice: int = 1, data: Optional[str] = None) -> Dict[str, Any]:
        arg = f"p_codprice => {int(codprice)}"
        if data:
            arg += f", p_data => DATE {_q(data)}"
        return Biro26Store._run_pkg(f"import_dates({arg});", capture=True)

    @staticmethod
    def import_prices(codprice: int = 1, date_start: Optional[str] = None,
                      date_end: Optional[str] = None) -> Dict[str, Any]:
        arg = f"p_codprice => {int(codprice)}"
        if date_start:
            arg += f", p_date_start => DATE {_q(date_start)}"
        if date_end:
            arg += f", p_date_end => DATE {_q(date_end)}"
        return Biro26Store._run_pkg(f"import_prices({arg});", capture=True)

    @staticmethod
    def rollback_pricelist(codprice: int = 1) -> Dict[str, Any]:
        return Biro26Store._run_pkg(
            f"rollback_pricelist(p_codprice => {int(codprice)});", capture=True)

    # ============================================================
    # STOCK BALANCES — UN$SOLD.GET_SOLDT (session-scoped GTT) persisted
    # into normal tables so any later request can read the result fast.
    # ============================================================

    STOCK_GTT = "YBIRO_STOCK_GTT"          # fixed name so the whole calc runs in ONE session
    DEFAULT_CONT = "217 2165 2114"          # RO: conturi marfa / EN: goods GL accounts
    DEFAULT_PFILT = "ACDE12"                # RO: masca filtru / EN: filter mask (per formula)

    @staticmethod
    def calc_stock(data_doc: str, dep_filter: str = "",
                   cont_filter: Optional[str] = None,
                   pfilt: Optional[str] = None) -> Dict[str, Any]:
        """Run UN$SOLD.GET_SOLDT and persist the balance into YBIRO_STOCK_CALC(_ITEM).

        data_doc: 'YYYY-MM-DD' (the :datadoc bind). dep_filter: the :m_ctdep bind
        (blank = no department filter value supplied by the caller). Everything
        (compute + persist) runs in ONE Oracle session (one execute_script call)
        because GET_SOLDT's result is a Global Temporary Table, visible only within
        the session that created it — a later request cannot see its rows. The
        persisted YBIRO_STOCK_CALC_ITEM already carries its own index (SC), so no
        index is created on the ephemeral GTT (Oracle blocks that: ORA-14452).
        """
        cont = cont_filter or Biro26Store.DEFAULT_CONT
        flt = pfilt or Biro26Store.DEFAULT_PFILT
        gtt = Biro26Store.STOCK_GTT
        try:
            res = Biro26DB().execute_script([
                {"sql": "UPDATE YBIRO_STOCK_CALC SET is_latest='0' WHERE is_latest='1'",
                 "params": {}, "kind": "dml"},
                {"sql": f"BEGIN EXECUTE IMMEDIATE 'DROP TABLE {gtt}'; "
                        "EXCEPTION WHEN OTHERS THEN NULL; END;",
                 "params": {}, "kind": "dml"},
                {"sql": ("DECLARE v VARCHAR2(100); BEGIN "
                        f"v := UN$SOLD.GET_SOLDT(pData => TO_DATE(:p_data,'YYYY-MM-DD'), "
                        f"sTableName => '{gtt}', pFilt => :p_pfilt, pCont => :p_cont, "
                        "pDep => :p_dep); END;"),
                 "params": {"p_data": data_doc, "p_pfilt": flt, "p_cont": cont,
                            "p_dep": dep_filter or " "},
                 "kind": "dml"},
                {"sql": "INSERT INTO YBIRO_STOCK_CALC(data_doc, dep_filter, cont_filter, "
                        "pfilt, src_table, row_count, is_latest, status) "
                        "VALUES(TO_DATE(:p_data,'YYYY-MM-DD'), :p_dep, :p_cont, :p_pfilt, "
                        f"'{gtt}', (SELECT COUNT(*) FROM {gtt}), '1', 'OK')",
                 "params": {"p_data": data_doc, "p_dep": dep_filter or "", "p_cont": cont,
                            "p_pfilt": flt},
                 "kind": "dml"},
                {"sql": "INSERT INTO YBIRO_STOCK_CALC_ITEM(calc_id, sc, dep, cant, cant1) "
                        "SELECT (SELECT MAX(id) FROM YBIRO_STOCK_CALC WHERE is_latest='1'), "
                        f"SC, NVL(DEP,0), SUM(CANT), SUM(CANT1) FROM {gtt} "
                        "WHERE SC IS NOT NULL GROUP BY SC, NVL(DEP,0)",
                 "params": {}, "kind": "dml"},
            ])
            if not res.get("success"):
                return {"success": False, "error": res.get("message")}
            head = _rows(Biro26DB().execute_query(
                "SELECT * FROM (SELECT id, row_count, "
                "TO_CHAR(run_at,'DD.MM.YYYY HH24:MI') run_at FROM YBIRO_STOCK_CALC "
                "WHERE is_latest='1' ORDER BY id DESC) WHERE ROWNUM=1"))
            return {"success": True, "data": head[0] if head else None}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_latest_stock_calc() -> Dict[str, Any]:
        try:
            r = Biro26DB().execute_query(
                "SELECT * FROM (SELECT id, TO_CHAR(data_doc,'DD.MM.YYYY') data_doc, "
                "dep_filter, cont_filter, pfilt, row_count, status, err_text, "
                "TO_CHAR(run_at,'DD.MM.YYYY HH24:MI') run_at FROM YBIRO_STOCK_CALC "
                "WHERE is_latest='1' ORDER BY id DESC) WHERE ROWNUM=1")
            if not r.get("success"):
                return {"success": False, "error": r.get("message")}
            rows = _rows(r)
            return {"success": True, "data": rows[0] if rows else None}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_stock_items(limit: int = 500, offset: int = 0) -> Dict[str, Any]:
        """Rows of the latest stock calculation (SC, total CANT across depts)."""
        try:
            inner = ("SELECT i.sc, u.DENUMIREA, SUM(i.cant) cant FROM YBIRO_STOCK_CALC_ITEM i "
                     "LEFT JOIN TMS_UNIVERS u ON u.COD = i.sc "
                     "WHERE i.calc_id = (SELECT id FROM YBIRO_STOCK_CALC WHERE is_latest='1') "
                     "GROUP BY i.sc, u.DENUMIREA ORDER BY u.DENUMIREA")
            r = Biro26DB().execute_query(_page(inner, limit, offset))
            return _result(r)
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_products_stock(search: Optional[str] = None, gr1: Optional[str] = None,
                           brand: Optional[str] = None, categorie: Optional[str] = None,
                           grupa: Optional[str] = None,
                           limit: int = 200, offset: int = 0,
                           price_date: Optional[str] = None) -> Dict[str, Any]:
        """Product + stock grid (Windows-Excel-style columns), TIP='P' driven.

        Real balance comes from the latest YBIRO_STOCK_CALC_ITEM (NULL if never
        calculated or item has no postings). App/UI applies the visual placeholder
        constant when real_cant is NULL or 0, mirroring the legacy Excel export.
        Paginated (ROWNUM, 11g) so the UI can page through all ~78k products via
        infinite scroll instead of loading everything at once.
        BARCODE = first EAN from TMS_MPT_BARCODE, BC_CNT = how many the item has;
        text search also matches any of the item's barcodes.
        Prices (retail1/angro/ionline) come from the period price list
        TPR1D_PERPRLIST (codprice=1) AS OF price_date ('YYYY-MM-DD', default
        today) — same principle as the Listă de prețuri tab — falling back to
        the BIRO26_GOODS feed values for items not in the price list yet.
        """
        if not price_date:
            from datetime import date as _date
            price_date = _date.today().isoformat()
        try:
            inner = (
                "SELECT u.COD, u.CODVECHI, u.DENUMIREA, u.NAMERUS, u.UM, u.TIP, "
                "g.GRUPA, g.CATEGORIE, g.BRAND, "
                "NVL(pl.PRETV1, g.ANGRO) ANGRO, "
                "NVL(pl.PRETV2, g.IONLINE) IONLINE, "
                # RO: RETAIL1 e VARCHAR in feed; conversia doar pentru valori numerice
                # EN: RETAIL1 is VARCHAR in the feed; convert only numeric-looking values
                "NVL(pl.PRETV, CASE WHEN REGEXP_LIKE(TRIM(g.RETAIL1), "
                "'^-?[0-9]+([.,][0-9]+)?$') THEN "
                "TO_NUMBER(REPLACE(TRIM(g.RETAIL1),',','.')) END) RETAIL1, "
                "ROUND(NVL(pl.PRETV1, g.ANGRO)/1.2,2) ANGRO_FARA_TVA, "
                "NVL(m.IE_LINKADRES, NVL(g.PHOTO_URL,g.IMAGE_LINK)) IMAGE, "
                "s.CANT REAL_CANT, bc.BARCODE, bc.BC_CNT "
                "FROM TMS_UNIVERS u "
                # dedupe: the feed holds a few identical duplicate rows per product
                "LEFT JOIN (SELECT gg.* FROM (SELECT g0.*, ROW_NUMBER() OVER "
                "  (PARTITION BY g0.COD_UNIVERS ORDER BY g0.ID) RN0 "
                "  FROM BIRO26_GOODS g0) gg WHERE gg.RN0 = 1) g ON g.COD_UNIVERS = u.COD "
                "LEFT JOIN VMS_MPT_TVR m ON m.COD = u.COD "
                # RO: pretul in vigoare la data ceruta / EN: price effective at the requested date
                "LEFT JOIN TPR1D_PERPRLIST pl ON pl.CODPRICE = 1 AND pl.SC = u.COD "
                "  AND TO_DATE(:pd,'YYYY-MM-DD') BETWEEN pl.DATASTART AND pl.DATAEND "
                "LEFT JOIN (SELECT sc, SUM(cant) cant FROM YBIRO_STOCK_CALC_ITEM "
                "  WHERE calc_id = (SELECT id FROM YBIRO_STOCK_CALC WHERE is_latest='1') "
                "  GROUP BY sc) s ON s.sc = u.COD "
                "LEFT JOIN (SELECT COD, MIN(BARCODE) BARCODE, COUNT(*) BC_CNT "
                "  FROM TMS_MPT_BARCODE GROUP BY COD) bc ON bc.COD = u.COD "
                "WHERE u.TIP='P'")
            params: Dict[str, Any] = {"pd": price_date}
            if search:
                # pre-resolve the matching COD set (two cheap scans) instead of
                # OR/EXISTS predicates inside the heavy join — with the VMS_MPT_TVR
                # view and the ROW_NUMBER feed dedupe in play, the OR form made
                # Oracle evaluate the whole join row-by-row (minutes, not seconds)
                inner += (" AND u.COD IN ("
                          "SELECT COD FROM TMS_UNIVERS WHERE TIP='P' AND ("
                          "  UPPER(DENUMIREA) LIKE UPPER(:s) "
                          "  OR UPPER(NAMERUS) LIKE UPPER(:s) OR CODVECHI LIKE :s) "
                          "UNION "
                          "SELECT COD FROM TMS_MPT_BARCODE WHERE BARCODE LIKE :s)")
                params["s"] = f"%{search}%"
            if gr1:
                inner += " AND u.GR1=:gr1"; params["gr1"] = gr1
            if brand:
                inner += " AND g.BRAND=:brand"; params["brand"] = brand
            if grupa:
                inner += " AND g.GRUPA=:grupa"; params["grupa"] = grupa
            if categorie:
                inner += " AND g.CATEGORIE=:categorie"; params["categorie"] = categorie
            inner += " ORDER BY u.DENUMIREA"
            r = Biro26DB().execute_query(_page(inner, limit, offset), params)
            return _result(r)
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_product_tree() -> Dict[str, Any]:
        """GRUPA -> CATEGORIE counts for the Marfă/Stoc left-panel tree
        (same TIP='P' + BIRO26_GOODS scope as the grid; ~768 rows)."""
        try:
            r = Biro26DB().execute_query(
                "SELECT g.GRUPA, g.CATEGORIE, COUNT(*) CNT FROM TMS_UNIVERS u "
                "JOIN BIRO26_GOODS g ON g.COD_UNIVERS=u.COD "
                "WHERE u.TIP='P' AND g.GRUPA IS NOT NULL "
                "GROUP BY g.GRUPA, g.CATEGORIE ORDER BY g.GRUPA, g.CATEGORIE")
            return _result(r)
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_product_brands() -> Dict[str, Any]:
        """Distinct brands for the Marfă/Stoc filter dropdown, scoped to the same
        TIP='P' + BIRO26_GOODS join as get_products_stock (so filter options never
        lead to an empty result)."""
        try:
            r = Biro26DB().execute_query(
                "SELECT g.BRAND, COUNT(*) CNT FROM TMS_UNIVERS u "
                "JOIN BIRO26_GOODS g ON g.COD_UNIVERS=u.COD "
                "WHERE u.TIP='P' AND g.BRAND IS NOT NULL "
                "GROUP BY g.BRAND ORDER BY g.BRAND")
            return _result(r)
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_product_categories() -> Dict[str, Any]:
        """Distinct product groups (CATEGORIE) for the Marfă/Stoc filter dropdown."""
        try:
            r = Biro26DB().execute_query(
                "SELECT g.CATEGORIE, COUNT(*) CNT FROM TMS_UNIVERS u "
                "JOIN BIRO26_GOODS g ON g.COD_UNIVERS=u.COD "
                "WHERE u.TIP='P' AND g.CATEGORIE IS NOT NULL "
                "GROUP BY g.CATEGORIE ORDER BY g.CATEGORIE")
            return _result(r)
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ============================================================
    # PRODUCT EDITING — attributes across TMS_UNIVERS / BIRO26_GOODS /
    # TMS_MPT_TVR (image) / TMS_MPT_BARCODE, one atomic script.
    # TMS_UNIVERS updates are audited by its history triggers; CODVECHI
    # uniqueness and barcode uniqueness are enforced by DB triggers and
    # surface as errors here.
    # ============================================================

    UNIVERS_EDIT_FIELDS = {"denumirea": "DENUMIREA", "namerus": "NAMERUS",
                           "codvechi": "CODVECHI", "um": "UM"}
    GOODS_EDIT_FIELDS = {"brand": "BRAND", "grupa": "GRUPA", "categorie": "CATEGORIE",
                         "angro": "ANGRO", "ionline": "IONLINE", "retail1": "RETAIL1"}

    @staticmethod
    def update_product(cod: int, univers: Optional[Dict[str, Any]] = None,
                       goods: Optional[Dict[str, Any]] = None,
                       image: Optional[str] = None,
                       bc_add: Optional[List[str]] = None,
                       bc_remove: Optional[List[str]] = None) -> Dict[str, Any]:
        try:
            cod = int(cod)
            stmts: List[Dict[str, Any]] = []

            uv = {k: v for k, v in (univers or {}).items()
                  if k in Biro26Store.UNIVERS_EDIT_FIELDS}
            if uv:
                sets = ", ".join(f"{Biro26Store.UNIVERS_EDIT_FIELDS[k]} = :{k}" for k in uv)
                stmts.append({"sql": f"UPDATE TMS_UNIVERS SET {sets} WHERE COD = :cod",
                              "params": {**uv, "cod": cod}, "kind": "dml"})

            gv = {k: v for k, v in (goods or {}).items()
                  if k in Biro26Store.GOODS_EDIT_FIELDS}
            if gv:
                sets = ", ".join(f"{Biro26Store.GOODS_EDIT_FIELDS[k]} = :{k}" for k in gv)
                stmts.append({"sql": f"UPDATE BIRO26_GOODS SET {sets} WHERE COD_UNIVERS = :cod",
                              "params": {**gv, "cod": cod}, "kind": "dml"})

            if image is not None:
                stmts.append({"sql": "MERGE INTO TMS_MPT_TVR t USING (SELECT :cod c FROM dual) s "
                                     "ON (t.COD = s.c) "
                                     "WHEN MATCHED THEN UPDATE SET t.IE_LINKADRES = :img "
                                     "WHEN NOT MATCHED THEN INSERT (COD, IE_LINKADRES) "
                                     "VALUES (:cod, :img)",
                              "params": {"cod": cod, "img": image[:1000] if image else None},
                              "kind": "dml"})

            for b in (bc_add or []):
                b = str(b).strip()[:15]
                if not b:
                    continue
                # barcode FK needs a TMS_MPT card; create a minimal one if missing
                stmts.append({"sql": "INSERT INTO TMS_MPT (COD) "
                                     "SELECT :cod FROM dual WHERE NOT EXISTS "
                                     "(SELECT 1 FROM TMS_MPT WHERE COD = :cod)",
                              "params": {"cod": cod}, "kind": "dml"})
                stmts.append({"sql": "INSERT INTO TMS_MPT_BARCODE (COD, BARCODE) "
                                     "SELECT :cod, :b FROM dual WHERE NOT EXISTS "
                                     "(SELECT 1 FROM TMS_MPT_BARCODE WHERE COD = :cod AND BARCODE = :b)",
                              "params": {"cod": cod, "b": b}, "kind": "dml"})

            for b in (bc_remove or []):
                stmts.append({"sql": "DELETE FROM TMS_MPT_BARCODE WHERE COD = :cod AND BARCODE = :b",
                              "params": {"cod": cod, "b": str(b).strip()}, "kind": "dml"})

            if not stmts:
                return {"success": False, "error": "nothing to update"}
            res = Biro26DB().execute_script(stmts)
            if not res.get("success"):
                return {"success": False, "error": res.get("message")}
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── product tree editing (BIRO26_GOODS.GRUPA / .CATEGORIE) ─────────
    @staticmethod
    def rename_tree_node(level: str, old: str, new: str,
                         grupa: Optional[str] = None) -> Dict[str, Any]:
        try:
            if not old or not new:
                return {"success": False, "error": "old and new names are required"}
            if level == "grupa":
                r = Biro26DB().execute_dml(
                    "UPDATE BIRO26_GOODS SET GRUPA = :new WHERE GRUPA = :old",
                    {"new": new, "old": old})
            elif level == "categorie":
                r = Biro26DB().execute_dml(
                    "UPDATE BIRO26_GOODS SET CATEGORIE = :new "
                    "WHERE GRUPA = :g AND CATEGORIE = :old",
                    {"new": new, "old": old, "g": grupa})
            else:
                return {"success": False, "error": "level must be grupa|categorie"}
            if not r.get("success"):
                return {"success": False, "error": r.get("message")}
            return {"success": True, "rows": r.get("rowcount", 0)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def move_tree_categorie(grupa: str, categorie: str, new_grupa: str) -> Dict[str, Any]:
        try:
            if not (grupa and categorie and new_grupa):
                return {"success": False, "error": "grupa, categorie, new_grupa are required"}
            r = Biro26DB().execute_dml(
                "UPDATE BIRO26_GOODS SET GRUPA = :ng "
                "WHERE GRUPA = :g AND CATEGORIE = :c",
                {"ng": new_grupa, "g": grupa, "c": categorie})
            if not r.get("success"):
                return {"success": False, "error": r.get("message")}
            return {"success": True, "rows": r.get("rowcount", 0)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ============================================================
    # WEB-SHOP — self-registered clients (YBIRO_CLIENT + TMS_UNIVERS
    # TIP='O' via package y_ai_BIRO26) and "cont de plata" invoices
    # (TMDB_DOCS + VMDB_ST201M/D, visible in VMDB_DOCS_WORK).
    # ============================================================

    @staticmethod
    def shop_register_client(email: str, full_name: str, phone: str,
                             pwd_hash: str) -> Dict[str, Any]:
        try:
            res = Biro26DB().execute_script([
                {"sql": """DECLARE
  v_cod NUMBER;
BEGIN
  v_cod := y_ai_BIRO26.register_client(p_name => :nm);
  INSERT INTO YBIRO_CLIENT (univers_cod, email, full_name, phone, pwd_hash)
  VALUES (v_cod, :em, :nm, :ph, :pw);
END;""",
                 "params": {"nm": full_name, "em": email.lower().strip(),
                            "ph": phone or "", "pw": pwd_hash},
                 "kind": "dml"},
                {"sql": "SELECT id, univers_cod FROM YBIRO_CLIENT WHERE email = :em",
                 "params": {"em": email.lower().strip()}, "kind": "query"},
            ])
            if not res.get("success"):
                return {"success": False, "error": res.get("message")}
            row = res["results"][-1]["data"]
            return {"success": True,
                    "data": {"client_id": row[0][0], "univers_cod": row[0][1]}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def shop_client_by_email(email: str) -> Dict[str, Any]:
        try:
            rows = _rows(Biro26DB().execute_query(
                "SELECT id, univers_cod, email, full_name, phone, pwd_hash "
                "FROM YBIRO_CLIENT WHERE email = :em",
                {"em": (email or "").lower().strip()}))
            return {"success": True, "data": rows[0] if rows else None}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def shop_create_invoice(client_cod: int, items: List[Dict[str, Any]],
                            coment: str = "") -> Dict[str, Any]:
        """Create the invoice + all lines in ONE session/transaction, then
        return {cod, nrset}. items: [{cod, qty, price, name?}]."""
        try:
            if not items:
                return {"success": False, "error": "empty cart"}
            lines = []
            params: Dict[str, Any] = {"client": int(client_cod)}
            for i, it in enumerate(items[:200]):
                lines.append(f"  y_ai_BIRO26.add_line(v_cod, :sc{i}, :q{i}, :p{i}, :c{i});")
                params[f"sc{i}"] = int(it["cod"])
                params[f"q{i}"] = float(it.get("qty") or 0)
                params[f"p{i}"] = float(it.get("price") or 0)
                params[f"c{i}"] = (str(it.get("name") or "")[:180] or None)
            block = ("DECLARE\n  v_cod NUMBER;\nBEGIN\n"
                     "  v_cod := y_ai_BIRO26.create_invoice(p_client_cod => :client);\n"
                     + "\n".join(lines) + "\nEND;")
            res = Biro26DB().execute_script([
                {"sql": block, "params": params, "kind": "dml"},
                {"sql": "SELECT y_ai_BIRO26.last_doc FROM dual",
                 "params": {}, "kind": "query"},
            ])
            if not res.get("success"):
                return {"success": False, "error": res.get("message")}
            cod = res["results"][-1]["data"][0][0]
            nr = _rows(Biro26DB().execute_query(
                "SELECT NRSET FROM TMDB_DOCS WHERE COD = :c", {"c": cod}))
            return {"success": True,
                    "data": {"cod": cod, "nrset": nr[0]["nrset"] if nr else None}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def shop_prices_for(cods: List[int]) -> Dict[str, Any]:
        """Authoritative retail prices for the shop invoice (server-side —
        the public client must not be able to supply its own price). Reads
        the period price list (codprice=1) as of today, falling back to the
        BIRO26_GOODS feed value for items not in the price list yet."""
        try:
            cods = [int(c) for c in cods][:200]
            if not cods:
                return {"success": True, "data": {}}
            marks = ",".join(f":c{i}" for i in range(len(cods)))
            params = {f"c{i}": c for i, c in enumerate(cods)}
            rows = _rows(Biro26DB().execute_query(
                f"SELECT g.COD_UNIVERS COD, "
                f"NVL(MAX(pl.PRETV), MAX(CASE WHEN REGEXP_LIKE(TRIM(g.RETAIL1), "
                f"'^-?[0-9]+([.,][0-9]+)?$') THEN "
                f"TO_NUMBER(REPLACE(TRIM(g.RETAIL1), ',', '.')) END)) PRICE "
                f"FROM BIRO26_GOODS g "
                f"LEFT JOIN TPR1D_PERPRLIST pl ON pl.CODPRICE = 1 "
                f"  AND pl.SC = g.COD_UNIVERS "
                f"  AND TRUNC(SYSDATE) BETWEEN pl.DATASTART AND pl.DATAEND "
                f"WHERE g.COD_UNIVERS IN ({marks}) "
                f"GROUP BY g.COD_UNIVERS", params))
            return {"success": True,
                    "data": {int(r["cod"]): float(r["price"] or 0) for r in rows}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ============================================================
    # PRICE PERIODS on Marfă/Stoc — y_ai_BIRO26.set_price/del_price
    # over TPR1D_PERPRLIST (same principle as the Listă de prețuri
    # tab: a change SPLITS the period at the chosen date, a delete
    # MERGES neighbouring periods; the last row cannot be deleted).
    # ============================================================

    @staticmethod
    def get_price_history(sc: int, codprice: int = 1) -> Dict[str, Any]:
        """All price periods of one item, oldest first (the Istoric prețuri
        bottom panel of Marfă/Stoc)."""
        try:
            return _result(Biro26DB().execute_query(
                "SELECT CODPRICE, CODGRP, SC, "
                "TO_CHAR(DATASTART,'DD.MM.YYYY') DATASTART, "
                "TO_CHAR(DATAEND,'DD.MM.YYYY') DATAEND, "
                "PRETV, PRETV1, PRETV2 "
                "FROM TPR1D_PERPRLIST "
                "WHERE CODPRICE = :cp AND SC = :sc ORDER BY DATASTART",
                {"cp": int(codprice), "sc": int(sc)}))
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def set_product_price(sc: int, data: str, retail1=None, angro=None,
                          ionline=None, codprice: int = 1) -> Dict[str, Any]:
        """Set item prices effective from `data` ('YYYY-MM-DD') via
        y_ai_BIRO26.set_price (splits the period). None keeps the current
        value of that price column."""
        try:
            r = Biro26DB().execute_dml(
                "BEGIN y_ai_BIRO26.set_price("
                "p_sc => :sc, p_data => TO_DATE(:d,'YYYY-MM-DD'), "
                "p_pretv => :pv, p_pretv1 => :p1, p_pretv2 => :p2, "
                "p_codprice => :cp); END;",
                {"sc": int(sc), "d": data,
                 "pv": None if retail1 is None else float(retail1),
                 "p1": None if angro is None else float(angro),
                 "p2": None if ionline is None else float(ionline),
                 "cp": int(codprice)})
            if not r.get("success"):
                return {"success": False, "error": r.get("message")}
            return Biro26Store.get_price_history(sc, codprice)
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def delete_price_period(sc: int, data: str,
                            codprice: int = 1) -> Dict[str, Any]:
        """Delete the period starting at `data` ('DD.MM.YYYY' as shown in the
        history panel) via y_ai_BIRO26.del_price (merges periods; the last
        remaining row raises ORA-20261)."""
        try:
            r = Biro26DB().execute_dml(
                "BEGIN y_ai_BIRO26.del_price("
                "p_sc => :sc, p_data => TO_DATE(:d,'DD.MM.YYYY'), "
                "p_codprice => :cp); END;",
                {"sc": int(sc), "d": data, "cp": int(codprice)})
            if not r.get("success"):
                return {"success": False, "error": r.get("message")}
            return Biro26Store.get_price_history(sc, codprice)
        except Exception as e:
            return {"success": False, "error": str(e)}
