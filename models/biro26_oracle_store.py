"""Biro26 module Oracle store — all SQL + YBIRO_Import_Marfa package calls.

Target DB: OfficePlus ERP (Oracle 11g) via models.biro26_db.Biro26DB (subprocess
worker, thick mode). Prefix for our own objects: YBIRO_.

11g notes: no OFFSET/FETCH — pagination uses the ROWNUM pattern (see _page()).
Multi-statement atomic ops use db.execute_script([...]) (one transaction).
"""
from __future__ import annotations

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
    return [dict(zip(cols, row)) for row in r["data"]]


def _q(v: Any) -> str:
    return "'" + str(v).replace("'", "''") + "'"


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
            rhs = str(val)
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
            return {"success": True, "data": _rows(r)}
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
            return {"success": True, "data": _rows(r)}
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
                          "OR UPPER(NAMERUS) LIKE UPPER(:s) OR CODVECHI LIKE :s)")
                params["s"] = f"%{search}%"
            if gr1:
                inner += " AND GR1=:gr1"; params["gr1"] = gr1
            if arhiv == "active":
                inner += " AND (ISARHIV IS NULL OR ISARHIV='0')"
            elif arhiv == "archived":
                inner += " AND ISARHIV IS NOT NULL AND ISARHIV<>'0'"
            inner += " ORDER BY DENUMIREA"
            r = Biro26DB().execute_query(_page(inner, limit, offset), params)
            return {"success": True, "data": _rows(r)}
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
            return {"success": True,
                    "data": {"univers": u[0], "mpt": mpt[0] if mpt else None}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def import_univers() -> Dict[str, Any]:
        return Biro26Store._run_pkg("import_univers;", capture=True)

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
            return {"success": True, "data": _rows(r)}
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
            return {"success": True, "data": _rows(r)}
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
            return {"success": True, "data": _rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_furnizori() -> Dict[str, Any]:
        try:
            r = Biro26DB().execute_query(
                "SELECT FURNIZOR, COUNT(*) CNT FROM BIRO26_GOODS "
                "WHERE FURNIZOR IS NOT NULL GROUP BY FURNIZOR ORDER BY FURNIZOR")
            return {"success": True, "data": _rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ============================================================
    # PRICE LIST — VPR1D_PRDATE / VTPR1D_PERPRLIST
    # ============================================================
    @staticmethod
    def get_prices(codprice: int = 1, codgrp: Optional[int] = None,
                   limit: int = 200, offset: int = 0) -> Dict[str, Any]:
        try:
            inner = ("SELECT CODPRICE, CODGRP, SC, PRETV, PRETV1, PRETV2, PRETV3, "
                     "TO_CHAR(DATASTART,'DD.MM.YYYY') DATASTART "
                     "FROM VTPR1D_PERPRLIST WHERE CODPRICE=:c")
            params: Dict[str, Any] = {"c": codprice}
            if codgrp is not None:
                inner += " AND CODGRP=:g"; params["g"] = codgrp
            inner += " ORDER BY CODGRP, SC"
            r = Biro26DB().execute_query(_page(inner, limit, offset), params)
            return {"success": True, "data": _rows(r)}
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
            return {"success": True, "data": _rows(r)}
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
