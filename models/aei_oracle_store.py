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
                              d.TAX_RATE, d.CAPITALIZATION, d.DAY_COUNT, d.STATUS,
                              d.PARENT_ID, d.NOTES, d.CREATED_AT, d.UPDATED_AT,
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
                    r2 = db.execute_query(
                        "SELECT LOAN_ID FROM AEI_LOANS WHERE CONTRACT_NO=:cn ORDER BY LOAN_ID DESC",
                        {"cn": p["contract_no"]}
                    )
                    new_id = r2["data"][0][0] if r2.get("data") else None
                    return {"success": True, "loan_id": new_id}
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
    # REPORTS
    # ================================================================

    @staticmethod
    def get_trial_balance(date_from: str = None, date_to: str = None) -> Dict[str, Any]:
        """Оборотно-сальдовая ведомость по счетам AEI_JOURNAL."""
        try:
            with DatabaseModel() as db:
                p: Dict = {}
                # opening: all entries strictly before date_from
                if date_from:
                    ob_where = "ENTRY_DATE < TO_DATE(:df,'DD.MM.YYYY')"
                    p["df"] = date_from
                else:
                    ob_where = "1=0"   # no opening balance if no date_from

                # period: entries in [date_from, date_to]
                per_cond = "1=1"
                if date_from:
                    per_cond += " AND ENTRY_DATE >= TO_DATE(:df,'DD.MM.YYYY')"
                if date_to:
                    per_cond += " AND ENTRY_DATE <= TO_DATE(:dt,'DD.MM.YYYY')"
                    p["dt"] = date_to

                sql = f"""
                WITH ob AS (
                    SELECT account_code,
                           SUM(debit_amt)  AS ob_dt,
                           SUM(credit_amt) AS ob_ct
                    FROM (
                        SELECT DEBIT_ACCOUNT  AS account_code, AMOUNT AS debit_amt, 0 AS credit_amt
                        FROM AEI_JOURNAL WHERE {ob_where}
                        UNION ALL
                        SELECT CREDIT_ACCOUNT, 0, AMOUNT
                        FROM AEI_JOURNAL WHERE {ob_where}
                    ) GROUP BY account_code
                ),
                per AS (
                    SELECT account_code,
                           SUM(debit_amt)  AS per_dt,
                           SUM(credit_amt) AS per_ct
                    FROM (
                        SELECT DEBIT_ACCOUNT  AS account_code, AMOUNT AS debit_amt, 0 AS credit_amt
                        FROM AEI_JOURNAL WHERE {per_cond}
                        UNION ALL
                        SELECT CREDIT_ACCOUNT, 0, AMOUNT
                        FROM AEI_JOURNAL WHERE {per_cond}
                    ) GROUP BY account_code
                ),
                all_accts AS (
                    SELECT DISTINCT account_code FROM ob
                    UNION
                    SELECT DISTINCT account_code FROM per
                )
                SELECT
                    a.account_code,
                    ac.ACCOUNT_NAME,
                    ac.ACCOUNT_TYPE,
                    NVL(ob.ob_dt,0)  AS ob_dt,
                    NVL(ob.ob_ct,0)  AS ob_ct,
                    NVL(per.per_dt,0) AS per_dt,
                    NVL(per.per_ct,0) AS per_ct,
                    GREATEST(NVL(ob.ob_dt,0) + NVL(per.per_dt,0)
                             - NVL(ob.ob_ct,0) - NVL(per.per_ct,0), 0) AS fin_dt,
                    GREATEST(NVL(ob.ob_ct,0) + NVL(per.per_ct,0)
                             - NVL(ob.ob_dt,0) - NVL(per.per_dt,0), 0) AS fin_ct
                FROM all_accts a
                LEFT JOIN ob  ON ob.account_code  = a.account_code
                LEFT JOIN per ON per.account_code = a.account_code
                LEFT JOIN AEI_ACCOUNTS ac ON ac.ACCOUNT_CODE = a.account_code
                ORDER BY a.account_code
                """
                r = db.execute_query(sql, p)
                rows = []
                for row in (r.get("data") or []):
                    rows.append({
                        "account_code": row[0],
                        "account_name": row[1] or "",
                        "account_type": row[2] or "",
                        "ob_dt":   float(row[3] or 0),
                        "ob_ct":   float(row[4] or 0),
                        "per_dt":  float(row[5] or 0),
                        "per_ct":  float(row[6] or 0),
                        "fin_dt":  float(row[7] or 0),
                        "fin_ct":  float(row[8] or 0),
                    })
                # totals
                totals = {k: sum(r[k] for r in rows)
                          for k in ("ob_dt","ob_ct","per_dt","per_ct","fin_dt","fin_ct")}
                return {"success": True, "data": rows, "totals": totals}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_olap_loans(group_by: str = "month", date_from: str = None, date_to: str = None) -> Dict[str, Any]:
        """OLAP агрегация кредитов по выбранному измерению."""
        try:
            with DatabaseModel() as db:
                dim_expr = {
                    "month":        "TO_CHAR(l.DISBURSEMENT_DATE,'YYYY-MM')",
                    "quarter":      "TO_CHAR(l.DISBURSEMENT_DATE,'YYYY') || '-Q' || TO_CHAR(l.DISBURSEMENT_DATE,'Q')",
                    "year":         "TO_CHAR(l.DISBURSEMENT_DATE,'YYYY')",
                    "status":       "l.STATUS",
                    "repayment":    "l.REPAYMENT_TYPE",
                    "risk":         "NVL(l.RISK_CLASS,'—')",
                    "member_type":  "NVL(m.MEMBER_TYPE,'—')",
                }.get(group_by, "TO_CHAR(l.DISBURSEMENT_DATE,'YYYY-MM')")

                p: Dict = {}
                where = "WHERE 1=1"
                if date_from:
                    where += " AND l.DISBURSEMENT_DATE >= TO_DATE(:df,'DD.MM.YYYY')"
                    p["df"] = date_from
                if date_to:
                    where += " AND l.DISBURSEMENT_DATE <= TO_DATE(:dt,'DD.MM.YYYY')"
                    p["dt"] = date_to

                sql = f"""
                SELECT
                    {dim_expr}              AS dim_value,
                    COUNT(*)                AS loan_count,
                    SUM(l.PRINCIPAL)        AS total_principal,
                    AVG(l.INTEREST_RATE)    AS avg_rate,
                    SUM(CASE WHEN l.STATUS='ACTIVE'  THEN l.PRINCIPAL ELSE 0 END) AS active_principal,
                    SUM(CASE WHEN l.STATUS='OVERDUE' THEN l.PRINCIPAL ELSE 0 END) AS overdue_principal,
                    SUM(CASE WHEN l.STATUS='CLOSED'  THEN l.PRINCIPAL ELSE 0 END) AS closed_principal,
                    COUNT(CASE WHEN l.STATUS='OVERDUE' THEN 1 END)                AS overdue_count,
                    SUM(NVL(lf.total_paid,0))     AS total_paid,
                    SUM(NVL(lf.total_overdue,0))  AS total_overdue,
                    SUM(l.PRINCIPAL * l.INTEREST_RATE / 100 * l.TERM_MONTHS / 12) AS projected_interest
                FROM AEI_LOANS l
                LEFT JOIN AEI_MEMBERS m ON m.MEMBER_ID = l.MEMBER_ID
                LEFT JOIN (
                    SELECT LOAN_ID,
                           SUM(AMOUNT_PAID)    AS total_paid,
                           SUM(AMOUNT_OVERDUE) AS total_overdue
                    FROM AEI_LOAN_FLOWS
                    GROUP BY LOAN_ID
                ) lf ON lf.LOAN_ID = l.LOAN_ID
                {where}
                GROUP BY {dim_expr}
                ORDER BY 1
                """
                r = db.execute_query(sql, p)
                rows = []
                for row in (r.get("data") or []):
                    rows.append({
                        "dim":               row[0] or "—",
                        "loan_count":        int(row[1] or 0),
                        "total_principal":   float(row[2] or 0),
                        "avg_rate":          round(float(row[3] or 0), 2),
                        "active_principal":  float(row[4] or 0),
                        "overdue_principal": float(row[5] or 0),
                        "closed_principal":  float(row[6] or 0),
                        "overdue_count":     int(row[7] or 0),
                        "total_paid":        float(row[8] or 0),
                        "total_overdue":     float(row[9] or 0),
                        "projected_interest":float(row[10] or 0),
                    })
                totals = {k: sum(r[k] for r in rows if isinstance(r[k], (int,float)))
                          for k in ("loan_count","total_principal","active_principal",
                                    "overdue_principal","closed_principal","overdue_count",
                                    "total_paid","total_overdue","projected_interest")}
                totals["avg_rate"] = round(sum(r["avg_rate"]*r["loan_count"] for r in rows) / max(totals["loan_count"],1), 2)
                return {"success": True, "data": rows, "totals": totals}
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
    # LOAN FLOWS — schedule + payments
    # ================================================================

    @staticmethod
    def get_loan_flows(loan_id: int) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    """SELECT FLOW_ID,
                              TO_CHAR(DUE_DATE,'DD.MM.YYYY')     AS DUE_DATE,
                              FLOW_TYPE, AMOUNT_SCHEDULED, AMOUNT_PAID,
                              AMOUNT_OVERDUE, BALANCE_PRINCIPAL,
                              TO_CHAR(PAYMENT_DATE,'DD.MM.YYYY') AS PAYMENT_DATE,
                              DAYS_OVERDUE, DESCRIPTION
                         FROM AEI_LOAN_FLOWS
                        WHERE LOAN_ID=:lid
                        ORDER BY DUE_DATE, FLOW_ID""",
                    {"lid": loan_id}
                )
                return {"success": True, "data": _rows(r)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_loan(loan_id: int) -> Dict[str, Any]:
        try:
            with DatabaseModel() as db:
                r = db.execute_query(
                    """SELECT l.LOAN_ID, l.CONTRACT_NO, l.MEMBER_ID,
                              TO_CHAR(l.SIGN_DATE,'DD.MM.YYYY')         AS SIGN_DATE,
                              TO_CHAR(l.DISBURSEMENT_DATE,'DD.MM.YYYY') AS DISBURSEMENT_DATE,
                              TO_CHAR(l.END_DATE,'DD.MM.YYYY')          AS END_DATE,
                              l.PRINCIPAL, l.CURRENCY, l.INTEREST_RATE, l.PENALTY_RATE,
                              l.REPAYMENT_TYPE, l.TERM_MONTHS, l.PURPOSE, l.COLLATERAL,
                              l.STATUS, l.RISK_CLASS, l.PROVISION_PCT, l.NOTES,
                              m.LAST_NAME||' '||m.FIRST_NAME AS MEMBER_NAME
                         FROM AEI_LOANS l
                         JOIN AEI_MEMBERS m ON m.MEMBER_ID=l.MEMBER_ID
                        WHERE l.LOAN_ID=:id""",
                    {"id": loan_id}
                )
                rows = _rows(r)
                return {"success": True, "data": rows[0] if rows else None}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def generate_loan_schedule(loan_id: int) -> Dict[str, Any]:
        """Generate annuity or declining repayment schedule and persist to AEI_LOAN_FLOWS."""
        from datetime import datetime, timedelta
        import math

        try:
            with DatabaseModel() as db:
                # --- load loan ---
                r = db.execute_query(
                    """SELECT PRINCIPAL, INTEREST_RATE, TERM_MONTHS, REPAYMENT_TYPE,
                              DISBURSEMENT_DATE, END_DATE, CONTRACT_NO
                         FROM AEI_LOANS WHERE LOAN_ID=:id""",
                    {"id": loan_id}
                )
                if not r.get("data"):
                    return {"success": False, "error": "Loan not found"}
                row = r["data"][0]
                principal    = float(row[0])
                annual_rate  = float(row[1]) / 100.0
                n_months     = int(row[2])
                rtype        = row[3]          # ANNUITY | DECLINING
                disb_date    = row[4]          # datetime
                contract_no  = row[6]

                # --- clear existing PAYMENT rows ---
                db.execute_query(
                    "DELETE FROM AEI_LOAN_FLOWS WHERE LOAN_ID=:lid AND FLOW_TYPE='PAYMENT'",
                    {"lid": loan_id}
                )

                monthly_rate = annual_rate / 12.0
                balance      = principal
                flows        = []

                if rtype == "ANNUITY":
                    # equal total payment each month
                    if monthly_rate > 0:
                        annuity = principal * monthly_rate / (1 - (1 + monthly_rate) ** (-n_months))
                    else:
                        annuity = principal / n_months

                    for i in range(1, n_months + 1):
                        interest_part  = round(balance * monthly_rate, 2)
                        principal_part = round(annuity - interest_part, 2)
                        if i == n_months:
                            principal_part = round(balance, 2)
                            interest_part  = round(annuity - principal_part, 2)
                            if interest_part < 0:
                                interest_part = 0.0
                        payment_total  = round(principal_part + interest_part, 2)
                        balance        = round(balance - principal_part, 2)
                        if balance < 0:
                            balance = 0.0

                        # due date: disbursement day-of-month, i months later
                        if isinstance(disb_date, str):
                            base = datetime.strptime(disb_date, "%d.%m.%Y")
                        else:
                            base = disb_date

                        month = base.month - 1 + i
                        year  = base.year + month // 12
                        month = month % 12 + 1
                        try:
                            due = base.replace(year=year, month=month)
                        except ValueError:
                            import calendar
                            last_day = calendar.monthrange(year, month)[1]
                            due = base.replace(year=year, month=month, day=last_day)

                        flows.append({
                            "loan_id":    loan_id,
                            "due":        due.strftime("%d.%m.%Y"),
                            "sched":      payment_total,
                            "principal":  principal_part,
                            "interest":   interest_part,
                            "bal":        balance,
                            "descr":      f"Rata {i}/{n_months}: principal {principal_part:,.2f} + dobândă {interest_part:,.2f}",
                        })

                else:  # DECLINING — equal principal each month
                    principal_part = round(principal / n_months, 2)
                    for i in range(1, n_months + 1):
                        if i == n_months:
                            principal_part = round(balance, 2)
                        interest_part = round(balance * monthly_rate, 2)
                        payment_total = round(principal_part + interest_part, 2)
                        balance       = round(balance - principal_part, 2)
                        if balance < 0:
                            balance = 0.0

                        if isinstance(disb_date, str):
                            base = datetime.strptime(disb_date, "%d.%m.%Y")
                        else:
                            base = disb_date

                        month = base.month - 1 + i
                        year  = base.year + month // 12
                        month = month % 12 + 1
                        try:
                            due = base.replace(year=year, month=month)
                        except ValueError:
                            import calendar
                            last_day = calendar.monthrange(year, month)[1]
                            due = base.replace(year=year, month=month, day=last_day)

                        flows.append({
                            "loan_id":   loan_id,
                            "due":       due.strftime("%d.%m.%Y"),
                            "sched":     payment_total,
                            "principal": principal_part,
                            "interest":  interest_part,
                            "bal":       balance,
                            "descr":     f"Rata {i}/{n_months}: principal {principal_part:,.2f} + dobândă {interest_part:,.2f}",
                        })

                # --- insert rows (pass only bound keys) ---
                for f in flows:
                    r = db.execute_query(
                        """INSERT INTO AEI_LOAN_FLOWS
                               (LOAN_ID, DUE_DATE, FLOW_TYPE, AMOUNT_SCHEDULED,
                                AMOUNT_PAID, AMOUNT_OVERDUE, BALANCE_PRINCIPAL, DESCRIPTION)
                           VALUES
                               (:loan_id, TO_DATE(:due,'DD.MM.YYYY'), 'PAYMENT',
                                :sched, 0, 0, :bal, :descr)""",
                        {"loan_id": f["loan_id"], "due": f["due"],
                         "sched": f["sched"], "bal": f["bal"], "descr": f["descr"]}
                    )
                    if not r.get("success"):
                        raise Exception(f"Insert failed: {r.get('message')}")

                db.connection.commit()
                return {"success": True, "count": len(flows),
                        "message": f"Grafic generat: {len(flows)} rate ({rtype})"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def record_loan_payment(flow_id: int, amount_paid: float,
                            payment_date: str, notes: str = None) -> Dict[str, Any]:
        """Mark a loan flow row as paid (full or partial)."""
        try:
            with DatabaseModel() as db:
                # get scheduled amount and due date
                r = db.execute_query(
                    """SELECT AMOUNT_SCHEDULED, DUE_DATE, LOAN_ID
                         FROM AEI_LOAN_FLOWS WHERE FLOW_ID=:fid""",
                    {"fid": flow_id}
                )
                if not r.get("data"):
                    return {"success": False, "error": "Flow not found"}
                sched, due_date, loan_id = r["data"][0]
                sched = float(sched)
                amount_paid = round(float(amount_paid), 2)
                overdue = round(max(sched - amount_paid, 0), 2)

                # days overdue
                from datetime import datetime
                today = datetime.today()
                if isinstance(due_date, str):
                    due = datetime.strptime(due_date, "%d.%m.%Y")
                else:
                    due = due_date
                days_ov = max((today - due).days, 0) if overdue > 0 else 0

                db.execute_query(
                    """UPDATE AEI_LOAN_FLOWS
                          SET AMOUNT_PAID   = :paid,
                              AMOUNT_OVERDUE= :ov,
                              PAYMENT_DATE  = TO_DATE(:pdate,'DD.MM.YYYY'),
                              DAYS_OVERDUE  = :dov,
                              DESCRIPTION   = :descr
                        WHERE FLOW_ID=:fid""",
                    {
                        "paid":  amount_paid,
                        "ov":    overdue,
                        "pdate": payment_date,
                        "dov":   days_ov,
                        "descr": notes or f"Achitat {amount_paid:,.2f} din {sched:,.2f}",
                        "fid":   flow_id,
                    }
                )

                # update loan status if overdue
                if overdue > 0 and days_ov > 0:
                    db.execute_query(
                        "UPDATE AEI_LOANS SET STATUS='OVERDUE', UPDATED_AT=SYSTIMESTAMP WHERE LOAN_ID=:lid",
                        {"lid": loan_id}
                    )

                db.connection.commit()
                return {"success": True, "overdue": overdue, "days_overdue": days_ov}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def calculate_deposit_interest(deposit_id: int) -> Dict[str, Any]:
        """Calculate accrued interest from last flow date to today."""
        from datetime import datetime

        try:
            with DatabaseModel() as db:
                # get deposit details
                r = db.execute_query(
                    """SELECT d.PRINCIPAL, d.INTEREST_RATE, d.TAX_RATE, d.CAPITALIZATION,
                              TO_CHAR(d.START_DATE,'DD.MM.YYYY') AS START_DATE,
                              TO_CHAR(d.END_DATE,'DD.MM.YYYY')   AS END_DATE,
                              d.STATUS, d.CONTRACT_NO
                         FROM AEI_DEPOSITS d WHERE d.DEPOSIT_ID=:id""",
                    {"id": deposit_id}
                )
                if not r.get("data"):
                    return {"success": False, "error": "Deposit not found"}
                row = r["data"][0]
                principal, rate, tax_rate, cap, start_s, end_s, status, contract_no = row
                principal = float(principal)
                rate      = float(rate) / 100.0
                tax_rate  = float(tax_rate) / 100.0

                # get last capitalization event
                r2 = db.execute_query(
                    """SELECT TO_CHAR(MAX(FLOW_DATE),'DD.MM.YYYY'), MAX(BALANCE_5131)
                         FROM AEI_DEPOSIT_FLOWS
                        WHERE DEPOSIT_ID=:id AND FLOW_TYPE IN ('DEPOSIT','CAPITALIZATION','SUPPLEMENTARY')""",
                    {"id": deposit_id}
                )
                last_date_s, current_balance = r2["data"][0] if r2.get("data") else (None, None)

                # fallback to start date
                if not last_date_s:
                    last_date_s = start_s
                calc_from = datetime.strptime(last_date_s, "%d.%m.%Y")
                today     = datetime.today()
                end_date  = datetime.strptime(end_s, "%d.%m.%Y")
                calc_to   = min(today, end_date)

                balance = float(current_balance or principal)
                days    = (calc_to - calc_from).days

                gross_interest = round(balance * rate * days / 365.0, 2)
                tax_amount     = round(gross_interest * tax_rate, 2)
                net_interest   = round(gross_interest - tax_amount, 2)

                return {
                    "success": True,
                    "data": {
                        "contract_no":      contract_no,
                        "balance":          balance,
                        "rate_pct":         float(rate * 100),
                        "days":             days,
                        "from_date":        last_date_s,
                        "to_date":          calc_to.strftime("%d.%m.%Y"),
                        "gross_interest":   gross_interest,
                        "tax_amount":       tax_amount,
                        "net_interest":     net_interest,
                        "status":           status,
                    }
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

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
