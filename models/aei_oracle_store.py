"""AEI module Oracle store — AEI_* table operations.

Asociații de Economii și Împrumut (Credit Unions).
Prefix: AEI
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from models.database import DatabaseModel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rows(r: Dict) -> List[Dict]:
    """Convert DatabaseModel {success, columns, data} → list of dicts."""
    if not r.get("success") or not r.get("data"):
        return []
    cols = [c.lower() for c in r["columns"]]
    return [dict(zip(cols, row)) for row in r["data"]]


def _scalar(r: Dict, col: int = 0) -> Any:
    """Return first value from first row."""
    if r.get("success") and r.get("data"):
        return r["data"][0][col]
    return None


# ---------------------------------------------------------------------------
# AEI Store
# ---------------------------------------------------------------------------

class AEIStore:
    """All Oracle CRUD for AEI module."""

    # ================================================================
    # MEMBERS
    # ================================================================

    @staticmethod
    def get_members(status: str = None) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                sql = """SELECT MEMBER_ID, IDNP, IDNO, MEMBER_TYPE,
                                LAST_NAME, FIRST_NAME, FULL_NAME,
                                PHONE, EMAIL, ADDRESS, STATUS,
                                TO_CHAR(JOIN_DATE,'DD.MM.YYYY') AS JOIN_DATE
                           FROM AEI_MEMBERS"""
                params = {}
                if status:
                    sql += " WHERE STATUS = :status"
                    params["status"] = status
                sql += " ORDER BY LAST_NAME, FIRST_NAME"
                r = db.execute_query(sql, params)
                return {"success": True, "data": _rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_member(member_id: int) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    "SELECT * FROM AEI_MEMBERS WHERE MEMBER_ID = :id",
                    {"id": member_id}
                )
                rows = _rows(r)
                return {"success": True, "data": rows[0] if rows else None}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def upsert_member(data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                p = {
                    "idnp":        data.get("idnp"),
                    "idno":        data.get("idno"),
                    "member_type": data.get("member_type", "PERSON"),
                    "last_name":   data.get("last_name", ""),
                    "first_name":  data.get("first_name"),
                    "full_name":   data.get("full_name"),
                    "phone":       data.get("phone"),
                    "email":       data.get("email"),
                    "address":     data.get("address"),
                    "status":      data.get("status", "ACTIVE"),
                    "notes":       data.get("notes"),
                }
                if data.get("member_id"):
                    p["id"] = int(data["member_id"])
                    db.execute_query(
                        """UPDATE AEI_MEMBERS
                              SET IDNP=:idnp, IDNO=:idno, MEMBER_TYPE=:member_type,
                                  LAST_NAME=:last_name, FIRST_NAME=:first_name,
                                  FULL_NAME=:full_name, PHONE=:phone, EMAIL=:email,
                                  ADDRESS=:address, STATUS=:status, NOTES=:notes,
                                  UPDATED_AT=SYSTIMESTAMP
                            WHERE MEMBER_ID=:id""",
                        p
                    )
                else:
                    db.execute_query(
                        """INSERT INTO AEI_MEMBERS
                               (IDNP, IDNO, MEMBER_TYPE, LAST_NAME, FIRST_NAME,
                                FULL_NAME, PHONE, EMAIL, ADDRESS, STATUS, NOTES)
                           VALUES (:idnp, :idno, :member_type, :last_name, :first_name,
                                   :full_name, :phone, :email, :address, :status, :notes)""",
                        p
                    )
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def delete_member(member_id: int) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                db.execute_query(
                    "UPDATE AEI_MEMBERS SET STATUS='INACTIVE', UPDATED_AT=SYSTIMESTAMP WHERE MEMBER_ID=:id",
                    {"id": member_id}
                )
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ================================================================
    # DEPOSITS
    # ================================================================

    @staticmethod
    def get_deposits(status: str = None, member_id: int = None) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                sql = """SELECT d.DEPOSIT_ID, d.CONTRACT_NO, d.MEMBER_ID,
                                m.LAST_NAME||' '||m.FIRST_NAME AS MEMBER_NAME,
                                TO_CHAR(d.SIGN_DATE,'DD.MM.YYYY') AS SIGN_DATE,
                                TO_CHAR(d.START_DATE,'DD.MM.YYYY') AS START_DATE,
                                TO_CHAR(d.END_DATE,'DD.MM.YYYY') AS END_DATE,
                                d.PRINCIPAL, d.CURRENCY, d.INTEREST_RATE,
                                d.TAX_RATE, d.CAPITALIZATION, d.STATUS
                           FROM AEI_DEPOSITS d
                           JOIN AEI_MEMBERS m ON m.MEMBER_ID = d.MEMBER_ID
                          WHERE 1=1"""
                params = {}
                if status:
                    sql += " AND d.STATUS = :status"
                    params["status"] = status
                if member_id:
                    sql += " AND d.MEMBER_ID = :member_id"
                    params["member_id"] = member_id
                sql += " ORDER BY d.START_DATE DESC"
                r = db.execute_query(sql, params)
                return {"success": True, "data": _rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_deposit(deposit_id: int) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    """SELECT d.DEPOSIT_ID, d.CONTRACT_NO, d.MEMBER_ID,
                              TO_CHAR(d.SIGN_DATE,'DD.MM.YYYY') AS SIGN_DATE,
                              TO_CHAR(d.START_DATE,'DD.MM.YYYY') AS START_DATE,
                              TO_CHAR(d.END_DATE,'DD.MM.YYYY') AS END_DATE,
                              d.PRINCIPAL, d.CURRENCY, d.INTEREST_RATE, d.PENALTY_RATE,
                              d.TAX_RATE, d.CAPITALIZATION, d.TERM_MONTHS, d.STATUS,
                              d.NOTES, d.CREATED_AT,
                              m.LAST_NAME||' '||m.FIRST_NAME AS MEMBER_NAME
                         FROM AEI_DEPOSITS d
                         JOIN AEI_MEMBERS m ON m.MEMBER_ID=d.MEMBER_ID
                        WHERE d.DEPOSIT_ID=:id""",
                    {"id": deposit_id}
                )
                rows = _rows(r)
                return {"success": True, "data": rows[0] if rows else None}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def upsert_deposit(data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                p = {
                    "contract_no":    data.get("contract_no", ""),
                    "member_id":      int(data.get("member_id", 0)),
                    "sign_date":      data.get("sign_date"),
                    "start_date":     data.get("start_date"),
                    "end_date":       data.get("end_date"),
                    "principal":      float(data.get("principal", 0)),
                    "currency":       data.get("currency", "MDL"),
                    "interest_rate":  float(data.get("interest_rate", 0)),
                    "penalty_rate":   float(data.get("penalty_rate", 1)),
                    "tax_rate":       float(data.get("tax_rate", 6)),
                    "capitalization": data.get("capitalization", "QUARTERLY"),
                    "day_count":      data.get("day_count", "ACT365"),
                    "status":         data.get("status", "ACTIVE"),
                    "notes":          data.get("notes"),
                }
                if data.get("deposit_id"):
                    p["id"] = int(data["deposit_id"])
                    db.execute_query(
                        """UPDATE AEI_DEPOSITS
                              SET CONTRACT_NO=:contract_no, MEMBER_ID=:member_id,
                                  SIGN_DATE=TO_DATE(:sign_date,'DD.MM.YYYY'),
                                  START_DATE=TO_DATE(:start_date,'DD.MM.YYYY'),
                                  END_DATE=TO_DATE(:end_date,'DD.MM.YYYY'),
                                  PRINCIPAL=:principal, CURRENCY=:currency,
                                  INTEREST_RATE=:interest_rate, PENALTY_RATE=:penalty_rate,
                                  TAX_RATE=:tax_rate, CAPITALIZATION=:capitalization,
                                  DAY_COUNT=:day_count, STATUS=:status, NOTES=:notes,
                                  UPDATED_AT=SYSTIMESTAMP
                            WHERE DEPOSIT_ID=:id""",
                        p
                    )
                else:
                    db.execute_query(
                        """INSERT INTO AEI_DEPOSITS
                               (CONTRACT_NO, MEMBER_ID, SIGN_DATE, START_DATE, END_DATE,
                                PRINCIPAL, CURRENCY, INTEREST_RATE, PENALTY_RATE,
                                TAX_RATE, CAPITALIZATION, DAY_COUNT, STATUS, NOTES)
                           VALUES (:contract_no, :member_id,
                                   TO_DATE(:sign_date,'DD.MM.YYYY'),
                                   TO_DATE(:start_date,'DD.MM.YYYY'),
                                   TO_DATE(:end_date,'DD.MM.YYYY'),
                                   :principal, :currency, :interest_rate, :penalty_rate,
                                   :tax_rate, :capitalization, :day_count, :status, :notes)""",
                        p
                    )
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_deposit_flows(deposit_id: int) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    """SELECT FLOW_ID, DEPOSIT_ID,
                              TO_CHAR(FLOW_DATE,'DD.MM.YYYY') AS FLOW_DATE,
                              FLOW_TYPE, DAYS, AMOUNT,
                              BALANCE_5131, BALANCE_51321, BALANCE_51322,
                              BALANCE_5133, BALANCE_51331, BALANCE_51332, BALANCE_5343,
                              DESCRIPTION
                         FROM AEI_DEPOSIT_FLOWS
                        WHERE DEPOSIT_ID=:id
                        ORDER BY FLOW_DATE, FLOW_ID""",
                    {"id": deposit_id}
                )
                return {"success": True, "data": _rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ================================================================
    # LOANS
    # ================================================================

    @staticmethod
    def get_loans(status: str = None, member_id: int = None) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                sql = """SELECT l.LOAN_ID, l.CONTRACT_NO, l.MEMBER_ID,
                                m.LAST_NAME||' '||m.FIRST_NAME AS MEMBER_NAME,
                                TO_CHAR(l.SIGN_DATE,'DD.MM.YYYY') AS SIGN_DATE,
                                TO_CHAR(l.DISBURSEMENT_DATE,'DD.MM.YYYY') AS DISBURSEMENT_DATE,
                                TO_CHAR(l.END_DATE,'DD.MM.YYYY') AS END_DATE,
                                l.PRINCIPAL, l.CURRENCY, l.INTEREST_RATE,
                                l.TERM_MONTHS, l.REPAYMENT_TYPE, l.STATUS, l.RISK_CLASS
                           FROM AEI_LOANS l
                           JOIN AEI_MEMBERS m ON m.MEMBER_ID=l.MEMBER_ID
                          WHERE 1=1"""
                params = {}
                if status:
                    sql += " AND l.STATUS=:status"
                    params["status"] = status
                if member_id:
                    sql += " AND l.MEMBER_ID=:member_id"
                    params["member_id"] = member_id
                sql += " ORDER BY l.DISBURSEMENT_DATE DESC"
                r = db.execute_query(sql, params)
                return {"success": True, "data": _rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def upsert_loan(data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                p = {
                    "contract_no":      data.get("contract_no", ""),
                    "member_id":        int(data.get("member_id", 0)),
                    "sign_date":        data.get("sign_date"),
                    "disbursement_date":data.get("disbursement_date"),
                    "end_date":         data.get("end_date"),
                    "principal":        float(data.get("principal", 0)),
                    "currency":         data.get("currency", "MDL"),
                    "interest_rate":    float(data.get("interest_rate", 0)),
                    "penalty_rate":     float(data.get("penalty_rate", 0.1)),
                    "repayment_type":   data.get("repayment_type", "ANNUITY"),
                    "term_months":      int(data.get("term_months", 12)),
                    "purpose":          data.get("purpose"),
                    "collateral":       data.get("collateral"),
                    "status":           data.get("status", "ACTIVE"),
                    "risk_class":       data.get("risk_class", "S"),
                    "notes":            data.get("notes"),
                }
                if data.get("loan_id"):
                    p["id"] = int(data["loan_id"])
                    db.execute_query(
                        """UPDATE AEI_LOANS
                              SET CONTRACT_NO=:contract_no, MEMBER_ID=:member_id,
                                  SIGN_DATE=TO_DATE(:sign_date,'DD.MM.YYYY'),
                                  DISBURSEMENT_DATE=TO_DATE(:disbursement_date,'DD.MM.YYYY'),
                                  END_DATE=TO_DATE(:end_date,'DD.MM.YYYY'),
                                  PRINCIPAL=:principal, CURRENCY=:currency,
                                  INTEREST_RATE=:interest_rate, PENALTY_RATE=:penalty_rate,
                                  REPAYMENT_TYPE=:repayment_type, TERM_MONTHS=:term_months,
                                  PURPOSE=:purpose, COLLATERAL=:collateral,
                                  STATUS=:status, RISK_CLASS=:risk_class, NOTES=:notes,
                                  UPDATED_AT=SYSTIMESTAMP
                            WHERE LOAN_ID=:id""",
                        p
                    )
                else:
                    db.execute_query(
                        """INSERT INTO AEI_LOANS
                               (CONTRACT_NO, MEMBER_ID, SIGN_DATE, DISBURSEMENT_DATE, END_DATE,
                                PRINCIPAL, CURRENCY, INTEREST_RATE, PENALTY_RATE,
                                REPAYMENT_TYPE, TERM_MONTHS, PURPOSE, COLLATERAL, STATUS,
                                RISK_CLASS, NOTES)
                           VALUES (:contract_no, :member_id,
                                   TO_DATE(:sign_date,'DD.MM.YYYY'),
                                   TO_DATE(:disbursement_date,'DD.MM.YYYY'),
                                   TO_DATE(:end_date,'DD.MM.YYYY'),
                                   :principal, :currency, :interest_rate, :penalty_rate,
                                   :repayment_type, :term_months, :purpose, :collateral,
                                   :status, :risk_class, :notes)""",
                        p
                    )
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ================================================================
    # JOURNAL
    # ================================================================

    @staticmethod
    def get_journal(date_from: str = None, date_to: str = None,
                    account: str = None, source_type: str = None) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                sql = """SELECT ENTRY_ID, TO_CHAR(ENTRY_DATE,'DD.MM.YYYY') AS ENTRY_DATE,
                                ENTRY_NO, DEBIT_ACCOUNT, CREDIT_ACCOUNT,
                                EXTRA_DEBIT, EXTRA_CREDIT,
                                AMOUNT, DESCRIPTION, DOCUMENT_REF,
                                SOURCE_TYPE, SOURCE_ID
                           FROM AEI_JOURNAL
                          WHERE 1=1"""
                params = {}
                if date_from:
                    sql += " AND ENTRY_DATE >= TO_DATE(:df,'DD.MM.YYYY')"
                    params["df"] = date_from
                if date_to:
                    sql += " AND ENTRY_DATE <= TO_DATE(:dt,'DD.MM.YYYY')"
                    params["dt"] = date_to
                if account:
                    sql += " AND (DEBIT_ACCOUNT=:acc OR CREDIT_ACCOUNT=:acc)"
                    params["acc"] = account
                if source_type:
                    sql += " AND SOURCE_TYPE=:st"
                    params["st"] = source_type
                sql += " ORDER BY ENTRY_DATE, ENTRY_ID"
                r = db.execute_query(sql, params)
                return {"success": True, "data": _rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def insert_journal_entry(data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                db.execute_query(
                    """INSERT INTO AEI_JOURNAL
                           (ENTRY_DATE, ENTRY_NO, DEBIT_ACCOUNT, CREDIT_ACCOUNT,
                            EXTRA_DEBIT, EXTRA_CREDIT, AMOUNT, DESCRIPTION,
                            DOCUMENT_REF, SOURCE_TYPE, SOURCE_ID, FLOW_ID, CREATED_BY)
                       VALUES (TO_DATE(:entry_date,'DD.MM.YYYY'), :entry_no,
                               :debit_account, :credit_account, :extra_debit, :extra_credit,
                               :amount, :description, :document_ref,
                               :source_type, :source_id, :flow_id, :created_by)""",
                    {
                        "entry_date":    data.get("entry_date"),
                        "entry_no":      data.get("entry_no"),
                        "debit_account": data.get("debit_account"),
                        "credit_account":data.get("credit_account"),
                        "extra_debit":   data.get("extra_debit"),
                        "extra_credit":  data.get("extra_credit"),
                        "amount":        float(data.get("amount", 0)),
                        "description":   data.get("description"),
                        "document_ref":  data.get("document_ref"),
                        "source_type":   data.get("source_type"),
                        "source_id":     data.get("source_id"),
                        "flow_id":       data.get("flow_id"),
                        "created_by":    data.get("created_by", "system"),
                    }
                )
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ================================================================
    # ACCOUNTS (chart of accounts)
    # ================================================================

    @staticmethod
    def get_accounts() -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    """SELECT ACCOUNT_ID, ACCOUNT_CODE, PARENT_CODE,
                              ACCOUNT_NAME, ACCOUNT_TYPE, NORMAL_BALANCE,
                              IS_ACTIVE, NOTES, SORT_ORDER
                         FROM AEI_ACCOUNTS
                        ORDER BY SORT_ORDER, ACCOUNT_CODE""",
                    {}
                )
                return {"success": True, "data": _rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ================================================================
    # SETTINGS
    # ================================================================

    @staticmethod
    def get_settings() -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    "SELECT SETTING_KEY, SETTING_VALUE, SETTING_GROUP, DESCRIPTION FROM AEI_SETTINGS ORDER BY SETTING_GROUP, SETTING_KEY",
                    {}
                )
                rows = _rows(r)
                result = {row["setting_key"]: row["setting_value"] for row in rows}
                return {"success": True, "data": result, "rows": rows}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def set_setting(key: str, value: str) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                db.execute_query(
                    """MERGE INTO AEI_SETTINGS s
                       USING (SELECT :key AS k, :val AS v FROM DUAL) src
                       ON (s.SETTING_KEY = src.k)
                       WHEN MATCHED THEN
                           UPDATE SET SETTING_VALUE=src.v, UPDATED_AT=SYSTIMESTAMP
                       WHEN NOT MATCHED THEN
                           INSERT (SETTING_KEY, SETTING_VALUE) VALUES (src.k, src.v)""",
                    {"key": key, "val": value}
                )
                db.connection.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ================================================================
    # DASHBOARD STATS
    # ================================================================

    @staticmethod
    def get_dashboard_stats() -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                stats = {}

                r = db.execute_query(
                    "SELECT COUNT(*), NVL(SUM(PRINCIPAL),0) FROM AEI_DEPOSITS WHERE STATUS='ACTIVE'", {}
                )
                if r.get("data"):
                    stats["deposits_count"] = r["data"][0][0]
                    stats["deposits_principal"] = float(r["data"][0][1] or 0)

                r = db.execute_query(
                    "SELECT COUNT(*), NVL(SUM(PRINCIPAL),0) FROM AEI_LOANS WHERE STATUS='ACTIVE'", {}
                )
                if r.get("data"):
                    stats["loans_count"] = r["data"][0][0]
                    stats["loans_principal"] = float(r["data"][0][1] or 0)

                r = db.execute_query(
                    "SELECT COUNT(*) FROM AEI_MEMBERS WHERE STATUS='ACTIVE'", {}
                )
                if r.get("data"):
                    stats["members_count"] = r["data"][0][0]

                r = db.execute_query(
                    "SELECT COUNT(*) FROM AEI_DEPOSITS WHERE STATUS='ACTIVE' AND END_DATE <= SYSDATE+30", {}
                )
                if r.get("data"):
                    stats["deposits_expiring_30d"] = r["data"][0][0]

                r = db.execute_query(
                    "SELECT COUNT(*) FROM AEI_LOANS WHERE STATUS IN ('ACTIVE','OVERDUE') AND END_DATE < SYSDATE", {}
                )
                if r.get("data"):
                    stats["loans_overdue"] = r["data"][0][0]

                return {"success": True, "data": stats}
        except Exception as e:
            return {"success": False, "error": str(e), "data": {}}

    # ================================================================
    # EVENT LOG
    # ================================================================

    @staticmethod
    def log_event(event_type: str, source_table: str = None,
                  source_id: int = None, user_name: str = None,
                  description: str = None) -> None:
        try:
            with DatabaseModel() as db:
                db.execute_query(
                    """INSERT INTO AEI_EVENT_LOG
                           (EVENT_TYPE, SOURCE_TABLE, SOURCE_ID, USER_NAME, DESCRIPTION)
                       VALUES (:et, :st, :sid, :un, :desc)""",
                    {"et": event_type, "st": source_table,
                     "sid": source_id, "un": user_name, "desc": description}
                )
                db.connection.commit()
        except Exception:
            pass  # log errors must never break main flow
