"""ServOuts26 store — all Oracle operations for the UNITEST schema.

CRM/SaaS pentru servicii de contabilitate: nomenclatorul de servicii
(TMS_UNIVERS/TMS_MPT), organizatii/clienti (TMS_ORG), pricelist-uri
(TPR0M_PRICES -> TPR01M_GROUPS -> TPR1D_PRDATE -> VTPR1D_PERPRLIST) si
importul configurabil prin pachetul YServOuts_BP. Jurnal: XLOG.

Every call goes through ServOuts26DB (thick-mode subprocess worker) — the
main Flask process stays thin. Multi-query screens are batched into ONE
execute_script call so a screen costs a single worker subprocess.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from models.servouts26_db import ServOuts26DB

# RO: cheile de configurare g_* expuse in UI (profil de mapare)
# EN: the g_* configuration keys exposed in the UI (mapping profile)
CONF_KEYS = [
    "tbl_goods", "col_key", "col_id", "col_brand", "col_articol",
    "col_denumire", "col_angro", "col_ionline", "col_retail", "seq_key",
    "codprice", "pricename", "currency", "um", "gr1", "tip", "caccess",
    "codtva", "date_start", "date_end", "group_type", "empty_brand",
    "len_codvechi", "len_denumire", "isarhiv_arc", "isarhiv_lock",
    "confus_max_cyr",
]

# RO: pasii de import permisi din UI (whitelist — niciodata text liber)
# EN: import steps allowed from the UI (whitelist — never free text)
IMPORT_STEPS = {
    "prepare_input", "validate_input", "assign_keys", "import_univers",
    "import_groups", "import_dates", "import_prices", "import_all",
    "fix_denumirea_confusables",
}


def _rows(r: Dict) -> List[Dict]:
    if not r.get("success") or not r.get("data"):
        return []
    cols = [c.lower() for c in r.get("columns", [])]
    return [dict(zip(cols, row)) for row in r["data"]]


def _script_rows(res: Dict, idx: int) -> List[Dict]:
    """Rows of statement #idx from an execute_script result."""
    try:
        block = res["results"][idx]
        cols = [c.lower() for c in block.get("columns", [])]
        return [dict(zip(cols, row)) for row in block.get("data", [])]
    except Exception:
        return []


def _conf_block(profile: Optional[Dict[str, Any]]) -> str:
    """PL/SQL set_conf calls for a mapping profile (values bound, keys whitelisted)."""
    if not profile:
        return ""
    parts = []
    for key in CONF_KEYS:
        if key in profile and profile[key] not in (None, ""):
            parts.append(key)
    return "".join(
        f"YServOuts_BP.set_conf('{k}', :c_{k}); " for k in parts
    )


def _conf_binds(profile: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not profile:
        return {}
    return {f"c_{k}": str(profile[k]) for k in CONF_KEYS
            if k in profile and profile[k] not in (None, "")}


class ServOuts26Store:
    """All UNITEST-schema operations for the ServOuts26 module."""

    # ================================================================
    # CONNECTION / DASHBOARD
    # ================================================================

    @staticmethod
    def test_connection() -> Dict[str, Any]:
        with ServOuts26DB() as db:
            return db.test_connection()

    @staticmethod
    def get_dashboard() -> Dict[str, Any]:
        try:
            with ServOuts26DB() as db:
                cp = ServOuts26Store._current_codprice(db)
                r = db.execute_script([
                    {"sql": """SELECT
                          SUM(CASE WHEN TIP IN ('P','T') AND NVL(ISARHIV,'0') <> '1' THEN 1 ELSE 0 END),
                          SUM(CASE WHEN TIP = 'O' THEN 1 ELSE 0 END),
                          SUM(CASE WHEN NVL(ISARHIV,'0') = '1' THEN 1 ELSE 0 END),
                          COUNT(*)
                        FROM TMS_UNIVERS""", "kind": "query"},
                    {"sql": "SELECT COUNT(*) FROM TMS_ORG", "kind": "query"},
                    {"sql": "SELECT COUNT(*) FROM TPR01M_GROUPS WHERE CODPRICE = :cp AND GRPNAME IS NOT NULL",
                     "params": {"cp": cp}, "kind": "query"},
                    {"sql": "SELECT COUNT(*) FROM TPR1D_PERPRLIST WHERE CODPRICE = :cp",
                     "params": {"cp": cp}, "kind": "query"},
                    {"sql": "SELECT COUNT(*), SUM(CASE WHEN STATUS = 'ERR' THEN 1 ELSE 0 END) FROM SRVO_INPUT_GOODS",
                     "kind": "query"},
                    {"sql": """SELECT * FROM (
                          SELECT IPROPERTY, IEVENT, NRREC, COMENT,
                                 TO_CHAR(ITIME,'DD.MM.YYYY HH24:MI:SS') ITIME
                            FROM XLOG WHERE IOBJECT = 'SERVOUTS'
                           ORDER BY ITIME DESC, ROWNUM DESC) WHERE ROWNUM <= 10""",
                     "kind": "query"},
                ])
                if not r.get("success"):
                    return {"success": False, "error": r.get("message")}
                u = _script_rows(r, 0)[0]
                stg = _script_rows(r, 4)[0]
                return {"success": True, "data": {
                    "codprice": cp,
                    "services_active": list(u.values())[0],
                    "orgs_in_univers": list(u.values())[1],
                    "archived": list(u.values())[2],
                    "univers_total": list(u.values())[3],
                    "orgs": list(_script_rows(r, 1)[0].values())[0],
                    "price_groups": list(_script_rows(r, 2)[0].values())[0],
                    "price_rows": list(_script_rows(r, 3)[0].values())[0],
                    "staging_rows": list(stg.values())[0],
                    "staging_errors": list(stg.values())[1] or 0,
                    "journal": _script_rows(r, 5),
                }}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def _current_codprice(db: ServOuts26DB) -> int:
        r = db.execute_query("SELECT YSERVOUTS_BP.GET_CONF('codprice') FROM dual")
        try:
            return int(r["data"][0][0])
        except Exception:
            return 26

    # ================================================================
    # NOMENCLATOR (TMS_UNIVERS + TMS_MPT)
    # ================================================================

    @staticmethod
    def get_univers(tip: str = None, gr1: str = None, arhiv: str = None,
                    search: str = None, limit: int = 500) -> Dict[str, Any]:
        try:
            sql = """SELECT * FROM (
                       SELECT u.COD, u.CODVECHI, u.DENUMIREA, u.NAMERUS, u.UM,
                              u.GR1, u.GR2, u.TIP, NVL(u.ISARHIV,'0') ISARHIV
                         FROM TMS_UNIVERS u WHERE 1=1"""
            p: Dict[str, Any] = {}
            if tip:
                sql += " AND u.TIP = :tip"
                p["tip"] = tip
            if gr1:
                sql += " AND u.GR1 = :gr1"
                p["gr1"] = gr1
            if arhiv == "1":
                sql += " AND NVL(u.ISARHIV,'0') = '1'"
            elif arhiv == "0":
                sql += " AND NVL(u.ISARHIV,'0') <> '1'"
            if search:
                sql += """ AND (UPPER(u.DENUMIREA) LIKE '%'||UPPER(:q)||'%'
                            OR UPPER(u.NAMERUS) LIKE '%'||UPPER(:q)||'%'
                            OR UPPER(u.CODVECHI) LIKE '%'||UPPER(:q)||'%'
                            OR TO_CHAR(u.COD) = :q)"""
                p["q"] = search
            sql += " ORDER BY u.COD DESC) WHERE ROWNUM <= :lim"
            p["lim"] = min(int(limit or 500), 2000)
            with ServOuts26DB() as db:
                r = db.execute_query(sql, p)
                if not r.get("success"):
                    return {"success": False, "error": r.get("message")}
                return {"success": True, "data": _rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_univers_filters() -> Dict[str, Any]:
        try:
            with ServOuts26DB() as db:
                r = db.execute_script([
                    {"sql": "SELECT TIP, COUNT(*) CNT FROM TMS_UNIVERS GROUP BY TIP ORDER BY 1", "kind": "query"},
                    {"sql": "SELECT GR1, COUNT(*) CNT FROM TMS_UNIVERS WHERE GR1 IS NOT NULL GROUP BY GR1 ORDER BY 2 DESC", "kind": "query"},
                ])
                return {"success": True,
                        "tips": _script_rows(r, 0), "gr1s": _script_rows(r, 1)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_univers_card(cod: int) -> Dict[str, Any]:
        try:
            with ServOuts26DB() as db:
                r = db.execute_script([
                    {"sql": "SELECT u.* FROM TMS_UNIVERS u WHERE u.COD = :cod",
                     "params": {"cod": cod}, "kind": "query"},
                    {"sql": """SELECT COD, MATPRET, TOTPRET, TOTPRET1, MATUM, PRODUM,
                                      TEXT1, TEXT2, TEXT3, STRIH2_CODINTERN
                                 FROM TMS_MPT WHERE COD = :cod""",
                     "params": {"cod": cod}, "kind": "query"},
                    {"sql": """SELECT p.CODPRICE, pr.PRICENAME, p.CODGRP, g.GRPNAME,
                                      TO_CHAR(p.DATASTART,'DD.MM.YYYY') DATASTART,
                                      TO_CHAR(p.DATAEND,'DD.MM.YYYY') DATAEND,
                                      p.PRETV, p.PRETV1, p.PRETV2, p.PRETV3
                                 FROM TPR1D_PERPRLIST p
                                 LEFT JOIN TPR01M_GROUPS g
                                        ON g.CODPRICE = p.CODPRICE AND g.CODGRP = p.CODGRP
                                 LEFT JOIN TPR0M_PRICES pr ON pr.CODPRICE = p.CODPRICE
                                WHERE p.SC = :cod ORDER BY p.CODPRICE, p.DATASTART DESC""",
                     "params": {"cod": cod}, "kind": "query"},
                ])
                if not r.get("success"):
                    return {"success": False, "error": r.get("message")}
                rows = _script_rows(r, 0)
                return {"success": True,
                        "univers": rows[0] if rows else None,
                        "mpt": (_script_rows(r, 1) or [None])[0],
                        "prices": _script_rows(r, 2)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def update_univers(cod: int, data: Dict[str, Any]) -> Dict[str, Any]:
        # RO: campuri editabile — lista alba; restul raman ale ERP-ului
        # EN: editable fields — whitelist; everything else stays ERP-owned
        allowed = ["DENUMIREA", "NAMERUS", "UM", "GR1", "GR2", "CODTVA"]
        sets, p = [], {"cod": cod}
        for f in allowed:
            if f.lower() in data:
                sets.append(f"{f} = :{f.lower()}")
                p[f.lower()] = data[f.lower()] or None
        if not sets:
            return {"success": False, "error": "nothing to update"}
        try:
            with ServOuts26DB() as db:
                r = db.execute_dml(
                    f"UPDATE TMS_UNIVERS SET {', '.join(sets)} WHERE COD = :cod", p)
                if not r.get("success"):
                    return {"success": False, "error": r.get("message")}
                db.call_proc(
                    "BEGIN YServOuts_BP.log('update_univers','OK', :c, 1); END;",
                    {"c": f"COD={cod} UI edit: {', '.join(sorted(k for k in data))}"})
                return {"success": True, "rowcount": r.get("rowcount", 0)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def archive_univers(cod: int, value: str = None) -> Dict[str, Any]:
        try:
            with ServOuts26DB() as db:
                if value:
                    r = db.call_proc(
                        "BEGIN YServOuts_BP.archive_univers(:cod, :v); END;",
                        {"cod": cod, "v": value})
                else:
                    r = db.call_proc(
                        "BEGIN YServOuts_BP.archive_univers(:cod); END;", {"cod": cod})
                return {"success": r.get("success", False), "error": r.get("message")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ================================================================
    # GROUPS (pricelist groups + category tree)
    # ================================================================

    @staticmethod
    def get_groups(codprice: int = None) -> Dict[str, Any]:
        try:
            with ServOuts26DB() as db:
                cp = codprice or ServOuts26Store._current_codprice(db)
                r = db.execute_query(
                    """SELECT g.CODPRICE, g.CODGRP, g.GRPNAME, g.TYPE_SC, g.GR1_SC,
                              (SELECT COUNT(*) FROM TPR1D_PERPRLIST p
                                WHERE p.CODPRICE = g.CODPRICE AND p.CODGRP = g.CODGRP) PRICE_ROWS,
                              (SELECT COUNT(*) FROM TPR1D_PRDATE d
                                WHERE d.CODPRICE = g.CODPRICE AND d.CODGRP = g.CODGRP) PERIODS
                         FROM TPR01M_GROUPS g
                        WHERE g.CODPRICE = :cp
                        ORDER BY NVL2(g.GRPNAME, 0, 1), g.GRPNAME, g.CODGRP""",
                    {"cp": cp})
                if not r.get("success"):
                    return {"success": False, "error": r.get("message")}
                return {"success": True, "codprice": cp, "data": _rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def rename_group(codprice: int, codgrp: int, name: str) -> Dict[str, Any]:
        try:
            with ServOuts26DB() as db:
                r = db.execute_dml(
                    "UPDATE VPR01M_GROUPS SET GRPNAME = :n WHERE CODPRICE = :cp AND CODGRP = :g",
                    {"n": (name or "")[:25], "cp": codprice, "g": codgrp})
                if r.get("success"):
                    db.call_proc(
                        "BEGIN YServOuts_BP.log('rename_group','OK', :c, 1); END;",
                        {"c": f"CODPRICE={codprice} CODGRP={codgrp} -> {name}"})
                return {"success": r.get("success", False), "error": r.get("message")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def merge_groups(codprice: int, src: int, dst: int) -> Dict[str, Any]:
        try:
            with ServOuts26DB() as db:
                r = db.call_proc(
                    "BEGIN YServOuts_BP.merge_groups(:s, :d, :cp); END;",
                    {"s": src, "d": dst, "cp": codprice})
                return {"success": r.get("success", False), "error": r.get("message")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_systree() -> Dict[str, Any]:
        try:
            with ServOuts26DB() as db:
                r = db.execute_query(
                    """SELECT * FROM (SELECT s.GROUP1, s.GROUP2, s.GROUP3, s.GROUP4,
                              s.GROUP5, s.SC, u.DENUMIREA
                         FROM TMS_SYSGRP s
                         LEFT JOIN TMS_UNIVERS u ON u.COD = s.SC
                        ORDER BY s.GROUP1, s.GROUP2, s.GROUP3, s.GROUP4, s.GROUP5)
                       WHERE ROWNUM <= 1000""")
                return {"success": r.get("success", False),
                        "data": _rows(r), "error": r.get("message")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ================================================================
    # ORGANIZATIONS / CLIENTS (TMS_ORG)
    # ================================================================

    @staticmethod
    def get_orgs(search: str = None, limit: int = 300) -> Dict[str, Any]:
        try:
            sql = """SELECT * FROM (
                       SELECT o.COD, u.DENUMIREA, u.NAMERUS, o.CODFISCAL, o.ADRESS,
                              o.TELEFON, o.CONTACT, o.DIRECTOR, o.BANK, o.ACCOUNT
                         FROM TMS_ORG o
                         LEFT JOIN TMS_UNIVERS u ON u.COD = o.COD
                        WHERE 1=1"""
            p: Dict[str, Any] = {}
            if search:
                sql += """ AND (UPPER(u.DENUMIREA) LIKE '%'||UPPER(:q)||'%'
                            OR UPPER(u.NAMERUS) LIKE '%'||UPPER(:q)||'%'
                            OR o.CODFISCAL LIKE '%'||:q||'%'
                            OR TO_CHAR(o.COD) = :q)"""
                p["q"] = search
            sql += " ORDER BY u.DENUMIREA) WHERE ROWNUM <= :lim"
            p["lim"] = min(int(limit or 300), 2000)
            with ServOuts26DB() as db:
                r = db.execute_query(sql, p)
                return {"success": r.get("success", False),
                        "data": _rows(r), "error": r.get("message")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_org_card(cod: int) -> Dict[str, Any]:
        try:
            with ServOuts26DB() as db:
                r = db.execute_script([
                    {"sql": """SELECT o.COD, u.DENUMIREA, u.NAMERUS, o.CODFISCAL, o.OKPO,
                                      o.ADRESS, o.ADDR_FACT, o.TELEFON, o.TELPRIM, o.FAX,
                                      o.CONTACT, o.DIRECTOR, o.PERSDECONTR,
                                      o.TELEFONPERSDECONTR, o.BANK, o.MFO, o.ACCOUNT,
                                      o.ACCOUNT1, o.ACCOUNT2
                                 FROM TMS_ORG o
                                 LEFT JOIN TMS_UNIVERS u ON u.COD = o.COD
                                WHERE o.COD = :cod""",
                     "params": {"cod": cod}, "kind": "query"},
                    {"sql": """SELECT COD_BANK, TIPBANK, VALUTA, ACCOUNT1, ACCOUNT2,
                                      REKVIZIT1, REKVIZIT2, REKVIZIT3
                                 FROM TMS_ORG_ACCOUNTS WHERE COD_ORG = :cod""",
                     "params": {"cod": cod}, "kind": "query"},
                ])
                if not r.get("success"):
                    return {"success": False, "error": r.get("message")}
                rows = _script_rows(r, 0)
                return {"success": True,
                        "org": rows[0] if rows else None,
                        "accounts": _script_rows(r, 1)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ================================================================
    # PRICELISTS
    # ================================================================

    @staticmethod
    def get_pricelists() -> Dict[str, Any]:
        try:
            with ServOuts26DB() as db:
                r = db.execute_query(
                    """SELECT p.CODPRICE, p.PRICENAME, p.TYPE_SC, p.VAL,
                              (SELECT COUNT(*) FROM TPR01M_GROUPS g WHERE g.CODPRICE = p.CODPRICE) GROUPS_CNT,
                              (SELECT COUNT(*) FROM TPR1D_PERPRLIST t WHERE t.CODPRICE = p.CODPRICE) PRICE_ROWS
                         FROM TPR0M_PRICES p ORDER BY p.CODPRICE""")
                return {"success": r.get("success", False),
                        "data": _rows(r), "error": r.get("message")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_prices(codprice: int, codgrp: int = None, search: str = None,
                   limit: int = 500) -> Dict[str, Any]:
        try:
            sql = """SELECT * FROM (
                       SELECT p.CODPRICE, p.CODGRP, g.GRPNAME, p.SC, p.CLCSC, p.CLCSCT,
                              TO_CHAR(p.DATASTART,'DD.MM.YYYY') DATASTART,
                              TO_CHAR(p.DATAEND,'DD.MM.YYYY') DATAEND,
                              p.PRETV, p.PRETV1, p.PRETV2, p.PRETV3
                         FROM VTPR1D_PERPRLIST p
                         LEFT JOIN TPR01M_GROUPS g
                                ON g.CODPRICE = p.CODPRICE AND g.CODGRP = p.CODGRP
                        WHERE p.CODPRICE = :cp"""
            p: Dict[str, Any] = {"cp": codprice}
            if codgrp:
                sql += " AND p.CODGRP = :grp"
                p["grp"] = codgrp
            if search:
                sql += """ AND (UPPER(p.CLCSCT) LIKE '%'||UPPER(:q)||'%'
                            OR UPPER(p.CLCSC) LIKE '%'||UPPER(:q)||'%'
                            OR TO_CHAR(p.SC) = :q)"""
                p["q"] = search
            sql += " ORDER BY g.GRPNAME, p.CLCSCT) WHERE ROWNUM <= :lim"
            p["lim"] = min(int(limit or 500), 5000)
            with ServOuts26DB() as db:
                r = db.execute_query(sql, p)
                return {"success": r.get("success", False),
                        "data": _rows(r), "error": r.get("message")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def update_price(codprice: int, codgrp: int, sc: int, datastart: str,
                     prices: Dict[str, Any]) -> Dict[str, Any]:
        sets, p = [], {"cp": codprice, "g": codgrp, "sc": sc, "ds": datastart}
        for col in ("pretv", "pretv1", "pretv2", "pretv3"):
            if col in prices:
                sets.append(f"{col.upper()} = :{col}")
                v = prices[col]
                p[col] = float(v) if v not in (None, "") else None
        if not sets:
            return {"success": False, "error": "nothing to update"}
        try:
            with ServOuts26DB() as db:
                r = db.execute_dml(
                    f"""UPDATE VTPR1D_PERPRLIST SET {', '.join(sets)}
                         WHERE CODPRICE = :cp AND CODGRP = :g AND SC = :sc
                           AND DATASTART = TO_DATE(:ds,'DD.MM.YYYY')""", p)
                if r.get("success"):
                    db.call_proc(
                        "BEGIN YServOuts_BP.log('update_price','OK', :c, :n); END;",
                        {"c": f"CODPRICE={codprice} CODGRP={codgrp} SC={sc}",
                         "n": r.get("rowcount", 0)})
                return {"success": r.get("success", False),
                        "rowcount": r.get("rowcount", 0), "error": r.get("message")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def rollback_pricelist(codprice: int) -> Dict[str, Any]:
        try:
            with ServOuts26DB() as db:
                r = db.call_proc(
                    "BEGIN YServOuts_BP.rollback_pricelist(:cp); END;",
                    {"cp": codprice})
                return {"success": r.get("success", False), "error": r.get("message")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ================================================================
    # STAGING (SRVO_INPUT_GOODS)
    # ================================================================

    @staticmethod
    def get_staging(limit: int = 500) -> Dict[str, Any]:
        try:
            with ServOuts26DB() as db:
                r = db.execute_query(
                    """SELECT * FROM (
                         SELECT ID, ARTICOL, DENUMIRE, BRAND, RETAIL1, ANGRO,
                                IONLINE, COD_UNIVERS, STATUS, ERR_MSG
                           FROM SRVO_INPUT_GOODS ORDER BY ID)
                       WHERE ROWNUM <= :lim""",
                    {"lim": min(int(limit or 500), 5000)})
                return {"success": r.get("success", False),
                        "data": _rows(r), "error": r.get("message")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def load_staging(rows: List[Dict[str, Any]], replace: bool = False) -> Dict[str, Any]:
        if not rows:
            return {"success": False, "error": "no rows"}
        try:
            statements = []
            if replace:
                statements.append({"sql": "DELETE FROM SRVO_INPUT_GOODS", "kind": "dml"})
            for row in rows[:5000]:
                statements.append({
                    "sql": """INSERT INTO SRVO_INPUT_GOODS
                                (ID, ARTICOL, DENUMIRE, BRAND, RETAIL1, ANGRO, IONLINE)
                              VALUES (SRVO_INPUT_SEQ.NEXTVAL, :a, :d, :b, :r, :an, :io)""",
                    "params": {
                        "a": (row.get("articol") or None),
                        "d": (row.get("denumire") or None),
                        "b": (row.get("brand") or None),
                        "r": (row.get("retail1") or None),
                        "an": (row.get("angro") or None),
                        "io": (row.get("ionline") or None),
                    },
                    "kind": "dml",
                })
            with ServOuts26DB() as db:
                r = db.execute_script(statements)
                if r.get("success"):
                    db.call_proc(
                        "BEGIN YServOuts_BP.log('load_staging','OK', :c, :n); END;",
                        {"c": "Incarcare feed din UI / feed loaded from UI",
                         "n": len(rows)})
                return {"success": r.get("success", False),
                        "loaded": len(rows) if r.get("success") else 0,
                        "error": r.get("message")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def clear_staging() -> Dict[str, Any]:
        try:
            with ServOuts26DB() as db:
                r = db.execute_dml("DELETE FROM SRVO_INPUT_GOODS")
                return {"success": r.get("success", False),
                        "rowcount": r.get("rowcount", 0), "error": r.get("message")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ================================================================
    # IMPORT / MAPPING PROFILES
    # ================================================================

    @staticmethod
    def get_config() -> Dict[str, Any]:
        """Current g_* defaults as seen by a fresh session."""
        try:
            cols = ", ".join(
                f"YSERVOUTS_BP.GET_CONF('{k}') \"{k}\"" for k in CONF_KEYS)
            with ServOuts26DB() as db:
                r = db.execute_query(f"SELECT {cols} FROM dual")
                rows = _rows(r)
                return {"success": r.get("success", False),
                        "data": rows[0] if rows else {}, "error": r.get("message")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def run_step(step: str, profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Run one whitelisted package step; the mapping profile is applied via
        set_conf in the SAME PL/SQL block (one worker session)."""
        if step not in IMPORT_STEPS:
            return {"success": False, "error": f"unknown step: {step}"}
        try:
            block = ("BEGIN " + _conf_block(profile)
                     + f"YServOuts_BP.{step}; END;")
            with ServOuts26DB() as db:
                r = db.call_proc(block, _conf_binds(profile))
                return {"success": r.get("success", False), "error": r.get("message")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_profiles() -> Dict[str, Any]:
        try:
            with ServOuts26DB() as db:
                r = db.execute_query(
                    """SELECT PROFILE_NAME, PARAM_NAME, PARAM_VALUE
                         FROM SRVO_MAP_PROFILES ORDER BY PROFILE_NAME, PARAM_NAME""")
                profiles: Dict[str, Dict[str, str]] = {}
                for row in _rows(r):
                    profiles.setdefault(row["profile_name"], {})[
                        row["param_name"]] = row["param_value"]
                return {"success": r.get("success", False),
                        "data": profiles, "error": r.get("message")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def save_profile(name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if not name:
            return {"success": False, "error": "profile name required"}
        clean = {k: str(v) for k, v in (params or {}).items()
                 if k in CONF_KEYS and v not in (None, "")}
        try:
            statements = [{"sql": "DELETE FROM SRVO_MAP_PROFILES WHERE PROFILE_NAME = :n",
                           "params": {"n": name}, "kind": "dml"}]
            for k, v in clean.items():
                statements.append({
                    "sql": """INSERT INTO SRVO_MAP_PROFILES
                                (PROFILE_NAME, PARAM_NAME, PARAM_VALUE, UPDATED_AT)
                              VALUES (:n, :k, :v, SYSDATE)""",
                    "params": {"n": name, "k": k, "v": v}, "kind": "dml"})
            with ServOuts26DB() as db:
                r = db.execute_script(statements)
                return {"success": r.get("success", False),
                        "saved": len(clean), "error": r.get("message")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def delete_profile(name: str) -> Dict[str, Any]:
        try:
            with ServOuts26DB() as db:
                r = db.execute_dml(
                    "DELETE FROM SRVO_MAP_PROFILES WHERE PROFILE_NAME = :n",
                    {"n": name})
                return {"success": r.get("success", False),
                        "rowcount": r.get("rowcount", 0), "error": r.get("message")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ================================================================
    # SHOP — public catalog, clients, orders (SRVO_CLIENT / SRVO_ORDERS)
    # ================================================================

    @staticmethod
    def shop_catalog() -> Dict[str, Any]:
        """Active services of the module pricelist (today's period prices)."""
        try:
            with ServOuts26DB() as db:
                cp = ServOuts26Store._current_codprice(db)
                r = db.execute_query(
                    """SELECT p.SC, u.CODVECHI, u.DENUMIREA, u.NAMERUS, u.UM,
                              g.GRPNAME, p.PRETV, p.PRETV1, p.PRETV2
                         FROM TPR1D_PERPRLIST p
                         JOIN TMS_UNIVERS u ON u.COD = p.SC
                         LEFT JOIN TPR01M_GROUPS g
                                ON g.CODPRICE = p.CODPRICE AND g.CODGRP = p.CODGRP
                        WHERE p.CODPRICE = :cp
                          AND TRUNC(SYSDATE) BETWEEN p.DATASTART AND p.DATAEND
                          AND NVL(u.ISARHIV,'0') <> '1'
                        ORDER BY g.GRPNAME, u.DENUMIREA""",
                    {"cp": cp})
                return {"success": r.get("success", False), "codprice": cp,
                        "data": _rows(r), "error": r.get("message")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def shop_prices_for(cods: List[int]) -> Dict[str, Any]:
        """Authoritative server-side prices (the public client must not be
        able to supply its own price)."""
        if not cods:
            return {"success": True, "data": {}}
        try:
            marks = ",".join(f":c{i}" for i in range(len(cods[:100])))
            params = {f"c{i}": int(c) for i, c in enumerate(cods[:100])}
            with ServOuts26DB() as db:
                cp = ServOuts26Store._current_codprice(db)
                params["cp"] = cp
                r = db.execute_query(
                    f"""SELECT p.SC, p.PRETV FROM TPR1D_PERPRLIST p
                         WHERE p.CODPRICE = :cp
                           AND TRUNC(SYSDATE) BETWEEN p.DATASTART AND p.DATAEND
                           AND p.SC IN ({marks})""", params)
                if not r.get("success"):
                    return {"success": False, "error": r.get("message")}
                return {"success": True,
                        "data": {int(row[0]): float(row[1] or 0)
                                 for row in r.get("data", [])}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def shop_client_by_email(email: str) -> Dict[str, Any]:
        try:
            with ServOuts26DB() as db:
                r = db.execute_query(
                    """SELECT ID, EMAIL, FULL_NAME, PHONE, PWD_HASH, ADDRESS,
                              IDNO, IS_COMPANY FROM SRVO_CLIENT
                        WHERE EMAIL = :em""",
                    {"em": (email or "").lower().strip()})
                rows = _rows(r)
                return {"success": True, "data": rows[0] if rows else None}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def shop_register_client(email: str, full_name: str, phone: str,
                             pwd_hash: str, address: str = "", idno: str = "",
                             is_company: bool = False) -> Dict[str, Any]:
        try:
            with ServOuts26DB() as db:
                res = db.execute_script([
                    {"sql": """INSERT INTO SRVO_CLIENT
                                 (ID, EMAIL, FULL_NAME, PHONE, PWD_HASH,
                                  ADDRESS, IDNO, IS_COMPANY)
                               VALUES (SRVO_CLIENT_SEQ.NEXTVAL, :em, :nm, :ph,
                                       :pw, :ad, :idno, :isco)""",
                     "params": {"em": email.lower().strip(), "nm": full_name,
                                "ph": phone or "", "pw": pwd_hash,
                                "ad": (address or "")[:400],
                                "idno": (idno or "")[:20],
                                "isco": "1" if is_company else "0"},
                     "kind": "dml"},
                    {"sql": "SELECT ID FROM SRVO_CLIENT WHERE EMAIL = :em",
                     "params": {"em": email.lower().strip()}, "kind": "query"},
                ])
                if not res.get("success"):
                    return {"success": False, "error": res.get("message")}
                cid = res["results"][-1]["data"][0][0]
                db.call_proc(
                    "BEGIN YServOuts_BP.log('shop_register','OK', :c, 1); END;",
                    {"c": f"Client nou / new client: {full_name} <{email}>"})
                return {"success": True, "data": {"client_id": cid}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def shop_create_order(client_id: int,
                          items: List[Dict[str, Any]],
                          note: str = "") -> Dict[str, Any]:
        """Create the order + lines in ONE transaction; returns {order_id, order_no}."""
        if not items:
            return {"success": False, "error": "empty cart"}
        try:
            total = round(sum(float(i["qty"]) * float(i["price"])
                              for i in items), 2)
            # RO: totul intr-un singur bloc PL/SQL (o tranzactie); secventa
            #     se citeste intr-o variabila (ORA-02287 in WHERE/expresii).
            # EN: everything in ONE PL/SQL block (one transaction); the
            #     sequence goes through a variable (ORA-02287 otherwise).
            lines = []
            params: Dict[str, Any] = {"cid": int(client_id), "tot": total,
                                      "note": (note or "")[:500]}
            for i, it in enumerate(items[:100], start=1):
                lines.append(
                    "  INSERT INTO SRVO_ORDER_ITEMS"
                    " (ORDER_ID, LINE_NO, SC, NAME, QTY, PRICE, SUMA)"
                    f" VALUES (v_id, {i}, :sc{i}, :nm{i}, :q{i}, :p{i}, :s{i});")
                params[f"sc{i}"] = int(it["cod"])
                params[f"nm{i}"] = (str(it.get("name") or ""))[:200] or None
                params[f"q{i}"] = float(it["qty"])
                params[f"p{i}"] = float(it["price"])
                params[f"s{i}"] = round(float(it["qty"]) * float(it["price"]), 2)
            block = ("DECLARE\n  v_id NUMBER;\nBEGIN\n"
                     "  SELECT SRVO_ORDERS_SEQ.NEXTVAL INTO v_id FROM dual;\n"
                     "  INSERT INTO SRVO_ORDERS"
                     " (ORDER_ID, ORDER_NO, CLIENT_ID, STATUS, TOTAL, NOTE)"
                     " VALUES (v_id, 'SO-' || TO_CHAR(v_id), :cid, 'NEW',"
                     " :tot, :note);\n"
                     + "\n".join(lines) + "\nEND;")
            statements = [
                {"sql": block, "params": params, "kind": "dml"},
                {"sql": """SELECT ORDER_ID, ORDER_NO, TOTAL FROM (
                             SELECT ORDER_ID, ORDER_NO, TOTAL FROM SRVO_ORDERS
                              WHERE CLIENT_ID = :cid ORDER BY ORDER_ID DESC)
                            WHERE ROWNUM = 1""",
                 "params": {"cid": int(client_id)}, "kind": "query"},
            ]
            with ServOuts26DB() as db:
                res = db.execute_script(statements)
                if not res.get("success"):
                    return {"success": False, "error": res.get("message")}
                row = res["results"][-1]["data"][0]
                db.call_proc(
                    "BEGIN YServOuts_BP.log('shop_order','OK', :c, :n); END;",
                    {"c": f"Comanda / order {row[1]} total={row[2]}",
                     "n": len(items)})
                return {"success": True,
                        "data": {"order_id": row[0], "order_no": row[1],
                                 "total": row[2]}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def shop_client_orders(client_id: int) -> Dict[str, Any]:
        try:
            with ServOuts26DB() as db:
                r = db.execute_query(
                    """SELECT ORDER_ID, ORDER_NO, STATUS, TOTAL, CURRENCY, NOTE,
                              TO_CHAR(CREATED_AT,'DD.MM.YYYY HH24:MI') CREATED_AT
                         FROM SRVO_ORDERS WHERE CLIENT_ID = :cid
                        ORDER BY ORDER_ID DESC""", {"cid": int(client_id)})
                return {"success": r.get("success", False),
                        "data": _rows(r), "error": r.get("message")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def shop_order_detail(order_id: int,
                          client_id: Optional[int] = None) -> Dict[str, Any]:
        """Order header + lines (+client requisites for the printable invoice).
        client_id given -> ownership is enforced (shop session)."""
        try:
            p: Dict[str, Any] = {"oid": int(order_id)}
            own = ""
            if client_id is not None:
                own = " AND o.CLIENT_ID = :cid"
                p["cid"] = int(client_id)
            with ServOuts26DB() as db:
                r = db.execute_script([
                    {"sql": f"""SELECT o.ORDER_ID, o.ORDER_NO, o.STATUS, o.TOTAL,
                                       o.CURRENCY, o.NOTE,
                                       TO_CHAR(o.CREATED_AT,'DD.MM.YYYY HH24:MI') CREATED_AT,
                                       c.FULL_NAME, c.EMAIL, c.PHONE, c.ADDRESS,
                                       c.IDNO, c.IS_COMPANY
                                  FROM SRVO_ORDERS o
                                  JOIN SRVO_CLIENT c ON c.ID = o.CLIENT_ID
                                 WHERE o.ORDER_ID = :oid{own}""",
                     "params": p, "kind": "query"},
                    {"sql": """SELECT LINE_NO, SC, NAME, QTY, PRICE, SUMA
                                 FROM SRVO_ORDER_ITEMS WHERE ORDER_ID = :oid
                                ORDER BY LINE_NO""",
                     "params": {"oid": int(order_id)}, "kind": "query"},
                ])
                if not r.get("success"):
                    return {"success": False, "error": r.get("message")}
                head = _script_rows(r, 0)
                if not head:
                    return {"success": False, "error": "order not found"}
                return {"success": True, "order": head[0],
                        "items": _script_rows(r, 1)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def shop_orders_admin(status: str = None, limit: int = 200) -> Dict[str, Any]:
        try:
            sql = """SELECT * FROM (
                       SELECT o.ORDER_ID, o.ORDER_NO, o.STATUS, o.TOTAL,
                              o.CURRENCY, o.NOTE,
                              TO_CHAR(o.CREATED_AT,'DD.MM.YYYY HH24:MI') CREATED_AT,
                              c.FULL_NAME, c.EMAIL, c.PHONE,
                              (SELECT COUNT(*) FROM SRVO_ORDER_ITEMS i
                                WHERE i.ORDER_ID = o.ORDER_ID) LINES
                         FROM SRVO_ORDERS o
                         JOIN SRVO_CLIENT c ON c.ID = o.CLIENT_ID WHERE 1=1"""
            p: Dict[str, Any] = {}
            if status:
                sql += " AND o.STATUS = :st"
                p["st"] = status
            sql += " ORDER BY o.ORDER_ID DESC) WHERE ROWNUM <= :lim"
            p["lim"] = min(int(limit or 200), 2000)
            with ServOuts26DB() as db:
                r = db.execute_query(sql, p)
                return {"success": r.get("success", False),
                        "data": _rows(r), "error": r.get("message")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def shop_order_set_status(order_id: int, status: str) -> Dict[str, Any]:
        if status not in ("NEW", "CONFIRMED", "IN_WORK", "DONE", "CANCELED"):
            return {"success": False, "error": f"bad status: {status}"}
        try:
            with ServOuts26DB() as db:
                r = db.execute_dml(
                    """UPDATE SRVO_ORDERS SET STATUS = :st, UPDATED_AT = SYSDATE
                        WHERE ORDER_ID = :oid""",
                    {"st": status, "oid": int(order_id)})
                if r.get("success") and r.get("rowcount"):
                    db.call_proc(
                        "BEGIN YServOuts_BP.log('order_status','OK', :c, 1); END;",
                        {"c": f"ORDER_ID={order_id} -> {status}"})
                return {"success": r.get("success", False),
                        "rowcount": r.get("rowcount", 0),
                        "error": r.get("message")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ================================================================
    # JOURNAL (XLOG)
    # ================================================================

    @staticmethod
    def get_journal(only_module: bool = True, search: str = None,
                    limit: int = 200) -> Dict[str, Any]:
        try:
            sql = """SELECT * FROM (
                       SELECT IOBJECT, IPROPERTY, IEVENT,
                              TO_CHAR(ITIME,'DD.MM.YYYY HH24:MI:SS') ITIME,
                              NRREC, COMENT, OS_USER, MACHINE
                         FROM XLOG WHERE 1=1"""
            p: Dict[str, Any] = {}
            if only_module:
                sql += " AND IOBJECT = 'SERVOUTS'"
            if search:
                sql += """ AND (UPPER(COMENT) LIKE '%'||UPPER(:q)||'%'
                            OR UPPER(IPROPERTY) LIKE '%'||UPPER(:q)||'%')"""
                p["q"] = search
            sql += " ORDER BY ITIME DESC, ROWNUM DESC) WHERE ROWNUM <= :lim"
            p["lim"] = min(int(limit or 200), 2000)
            with ServOuts26DB() as db:
                r = db.execute_query(sql, p)
                return {"success": r.get("success", False),
                        "data": _rows(r), "error": r.get("message")}
        except Exception as e:
            return {"success": False, "error": str(e)}
