#!/usr/bin/env python3
"""
Демо-данные для OLAP анализа кредитного портфеля AEÎ.
Добавляет ~30 кредитов с разнообразием по всем OLAP-измерениям:
  - По месяцу/кварталу/году выдачи (2023–2026)
  - По статусу (ACTIVE / OVERDUE / CLOSED)
  - По типу погашения (ANNUITY / DECLINING)
  - По классу риска (S / SM / SN / D / P / PI / C)
  - По типу члена (PERSON / COMPANY)
"""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.database import DatabaseModel
from models.aei_oracle_store import AEIStore

# ── Новые члены-компании и физлица ────────────────────────────
NEW_MEMBERS = [
    # (last_name, first_name, member_type, idnp_or_idno, phone, join_date)
    ("SRL Construct-Pro",    "",   "COMPANY",  "1006789012345", "+373 22 887 001", "05.01.2023"),
    ("SA TechMold",          "",   "COMPANY",  "1005678901234", "+373 22 556 002", "10.02.2023"),
    ("SRL AgroMD",           "",   "COMPANY",  "1007890123456", "+373 231 45 003", "15.03.2023"),
    ("ÎI Moraru Construct",  "",   "COMPANY",  "1008901234567", "+373 69 334 004", "20.04.2023"),
    ("Botnaru",    "Sergiu",  "PERSON",   "2001234567890", "+373 68 221 005", "01.06.2023"),
    ("Vrabie",     "Aliona",  "PERSON",   "2009876543210", "+373 79 112 006", "15.07.2023"),
    ("Leahu",      "Gheorghe","PERSON",   "2003456789012", "+373 60 443 007", "01.09.2023"),
    ("Butnaru",    "Tatiana", "PERSON",   "2002345678901", "+373 78 554 008", "10.10.2023"),
    ("Ciuntu",     "Mihai",   "PERSON",   "2004567890123", "+373 67 665 009", "05.01.2024"),
    ("Holban",     "Olga",    "PERSON",   "2008765432109", "+373 76 776 010", "20.02.2024"),
    ("Munteanu",   "Petru",   "PERSON",   "2005678901234", "+373 65 887 011", "01.04.2024"),
    ("Negru",      "Irina",   "PERSON",   "2007654321098", "+373 74 998 012", "15.05.2024"),
    ("SA Finance Plus",      "",   "COMPANY",  "1009012345678", "+373 22 441 013", "01.06.2024"),
    ("SRL LogisTrans",       "",   "COMPANY",  "1000123456789", "+373 22 552 014", "10.08.2024"),
]

# ── Кредиты для добавления ─────────────────────────────────────
# Формат:
#  contract_no, member_offset (1=M1, 12=first new member, etc.),
#  principal, rate, term_months, repayment, penalty,
#  sign_date, disbursement_date, end_date,
#  risk_class, status, purpose, collateral, currency
# member_offset: 1-11 = existing, 12-25 = new members (index in NEW_MEMBERS)
LOANS = [
    # ── 2023 ──────────────────────────────────────────────────────
    # Q1 2023
    ("C-2023-001", 13, 120_000,"13.5",24,"ANNUITY",  0.1,"01.02.2023","10.02.2023","10.02.2025","S",  "CLOSED","Modernizare hală producție","Gaj echipament",            "MDL"),
    ("C-2023-002",  6,  18_000,"15.0",12,"ANNUITY",  0.1,"15.02.2023","20.02.2023","20.02.2024","SM", "CLOSED","Consum personal",          "Fără garanții",             "MDL"),
    ("C-2023-003", 14, 200_000,"12.5",36,"ANNUITY",  0.1,"05.03.2023","15.03.2023","15.03.2026","S",  "ACTIVE","Extindere flotă auto",     "Gaj auto 3 unități",        "MDL"),
    # Q2 2023
    ("C-2023-004",  7,  22_000,"16.5",12,"DECLINING",0.1,"10.04.2023","15.04.2023","15.04.2024","SN", "CLOSED","Reparație capitală",       "Ipotecă teren",             "MDL"),
    ("C-2023-005", 15,  35_000,"15.0",18,"ANNUITY",  0.1,"20.05.2023","25.05.2023","25.11.2024","SM", "CLOSED","Consum și renovare",       "Girant",                    "MDL"),
    ("C-2023-006", 12,350_000,"11.5",48,"ANNUITY",  0.1,"01.06.2023","10.06.2023","10.06.2027","S",  "ACTIVE","Construcție depozit",      "Ipotecă teren + construcție","MDL"),
    # Q3 2023
    ("C-2023-007",  4,  15_000,"17.0",12,"DECLINING",0.2,"05.07.2023","10.07.2023","10.07.2024","D",  "CLOSED","Nevoi personale urgente",  "Fără garanții",             "MDL"),
    ("C-2023-008", 16,  50_000,"14.5",24,"ANNUITY",  0.1,"15.08.2023","20.08.2023","20.08.2025","SM", "ACTIVE","Utilaje agricole",         "Gaj utilaj",                "MDL"),
    ("C-2023-009",  9,  28_000,"16.0",18,"DECLINING",0.1,"20.09.2023","25.09.2023","25.03.2025","S",  "CLOSED","Consum și vacanță",        "Girant soț/soție",          "MDL"),
    # Q4 2023
    ("C-2023-010", 17,  42_000,"15.5",24,"ANNUITY",  0.1,"10.10.2023","15.10.2023","15.10.2025","SM", "ACTIVE","Renovare locuință",        "Gaj imobil",                "MDL"),
    ("C-2023-011", 13,480_000,"11.0",60,"ANNUITY",  0.1,"01.11.2023","10.11.2023","10.11.2028","S",  "ACTIVE","Investiție industrială",   "Ipotecă fabrică",           "MDL"),
    ("C-2023-012",  2,  12_000,"18.0", 9,"DECLINING",0.2,"15.11.2023","20.11.2023","20.08.2024","P",  "CLOSED","Creditare urgentă",        "Fără garanții",             "MDL"),

    # ── 2024 ──────────────────────────────────────────────────────
    # Q1 2024
    ("C-2024-002", 18,  65_000,"14.0",24,"ANNUITY",  0.1,"05.01.2024","10.01.2024","10.01.2026","S",  "ACTIVE","Achiziție teren agricol",  "Gaj teren",                 "MDL"),
    ("C-2024-003",  3,  30_000,"15.5",18,"DECLINING",0.1,"20.02.2024","25.02.2024","25.08.2025","SM", "ACTIVE","Consum și studii",         "Girant",                    "MDL"),
    ("C-2024-004", 14,160_000,"12.0",36,"ANNUITY",  0.1,"01.03.2024","10.03.2024","10.03.2027","S",  "ACTIVE","Extindere punct de lucru", "Gaj imobil comercial",      "MDL"),
    # Q2 2024
    ("C-2024-005", 19,  20_000,"17.0",12,"ANNUITY",  0.2,"10.04.2024","15.04.2024","15.04.2025","D",  "OVERDUE","Consum personal",         "Girant",                    "MDL"),
    ("C-2024-006", 20,  55_000,"14.5",24,"DECLINING",0.1,"05.05.2024","10.05.2024","10.05.2026","SM", "ACTIVE","Modernizare birou",        "Gaj mobilier+echipament",   "MDL"),
    ("C-2024-007", 25,500_000,"10.5",60,"ANNUITY",  0.1,"20.06.2024","01.07.2024","01.07.2029","S",  "ACTIVE","Construcție centru logistic","Ipotecă teren+construcție","MDL"),
    # Q3 2024
    ("C-2024-008",  6,  16_000,"18.5",12,"DECLINING",0.2,"10.07.2024","15.07.2024","15.07.2025","PI", "OVERDUE","Consum",                  "Fără garanții",             "MDL"),
    ("C-2024-009", 21,  38_000,"15.0",18,"ANNUITY",  0.1,"01.08.2024","05.08.2024","05.02.2026","SM", "ACTIVE","Reparație casă",           "Gaj imobil",                "MDL"),
    ("C-2024-010", 22, 250_000,"11.5",48,"ANNUITY",  0.1,"15.09.2024","20.09.2024","20.09.2028","S",  "ACTIVE","Achiziție spațiu comercial","Ipotecă spațiu",           "MDL"),
    # Q4 2024
    ("C-2024-011", 23,  45_000,"14.5",24,"DECLINING",0.1,"05.10.2024","10.10.2024","10.10.2026","SM", "ACTIVE","Utilaje horticultură",     "Gaj utilaj",                "MDL"),
    ("C-2024-012",  8,  18_500,"17.5",12,"ANNUITY",  0.2,"20.11.2024","25.11.2024","25.11.2025","D",  "OVERDUE","Nevoi urgente",           "Girant",                    "MDL"),
    ("C-2024-013", 12,420_000,"11.0",48,"ANNUITY",  0.1,"01.12.2024","10.12.2024","10.12.2028","S",  "ACTIVE","Extindere capacitate prod.","Ipotecă fabrică + gaj",    "MDL"),

    # ── 2025 ──────────────────────────────────────────────────────
    # Q1 2025
    ("C-2025-006", 24, 75_000,"13.5",30,"ANNUITY",  0.1,"10.01.2025","15.01.2025","15.07.2027","S",  "ACTIVE","Irigație teren agricol",   "Gaj teren + utilaj",        "MDL"),
    ("C-2025-007",  4,  14_000,"19.0", 9,"DECLINING",0.3,"01.02.2025","05.02.2025","05.11.2025","C",  "OVERDUE","Consum urgent",           "Fără garanții",             "MDL"),
    ("C-2025-008", 20, 90_000,"13.0",36,"DECLINING",0.1,"10.03.2025","15.03.2025","15.03.2028","S",  "ACTIVE","Renovare hotel mic",       "Ipotecă clădire",           "MDL"),
    # Q2 2025
    ("C-2025-009", 21, 32_000,"15.5",18,"ANNUITY",  0.1,"05.04.2025","10.04.2025","10.10.2026","SM", "ACTIVE","Extindere producție apicultură","Gaj utilaj",           "MDL"),
    ("C-2025-010", 22,180_000,"12.5",48,"ANNUITY",  0.1,"15.05.2025","20.05.2025","20.05.2029","S",  "ACTIVE","Achiziție echipament IT",  "Gaj echipament",            "MDL"),
    # Q3 2025
    ("C-2025-011", 23, 48_000,"14.0",24,"DECLINING",0.1,"10.07.2025","15.07.2025","15.07.2027","SM", "ACTIVE","Modernizare depozit",      "Gaj imobil",                "MDL"),
    ("C-2025-012",  9,  22_000,"16.5",18,"ANNUITY",  0.2,"20.08.2025","25.08.2025","25.02.2027","SN", "ACTIVE","Consum și educație",       "Girant",                   "MDL"),
    # Q4 2025
    ("C-2025-013", 24,110_000,"13.0",36,"ANNUITY",  0.1,"10.10.2025","15.10.2025","15.10.2028","S",  "ACTIVE","Sistem solar fotovoltaic", "Gaj instalație + teren",    "MDL"),
    ("C-2025-014",  2,  26_000,"15.0",18,"DECLINING",0.1,"20.11.2025","25.11.2025","25.05.2027","SM", "ACTIVE","Renovare apartament",      "Ipotecă apartament",        "MDL"),
    ("C-2025-015", 25,650_000,"10.0",72,"ANNUITY",  0.1,"01.12.2025","10.12.2025","10.12.2031","S",  "ACTIVE","Parc industrial — faza 1", "Ipotecă teren 5ha + gaj",   "MDL"),
]

def get_or_create_members():
    """Add new members, return {offset: member_id}."""
    with DatabaseModel() as db:
        r = db.execute_query("SELECT MAX(MEMBER_ID) FROM AEI_MEMBERS", {})
        max_id = int(r['data'][0][0] or 0)

        r2 = db.execute_query("SELECT MEMBER_ID FROM AEI_MEMBERS ORDER BY MEMBER_ID", {})
        existing_ids = [row[0] for row in r2.get('data', [])]

        added = 0
        for i, (last, first, mtype, doc, phone, jdate) in enumerate(NEW_MEMBERS):
            offset = 12 + i  # offsets 12-25
            # check if already added (by IDNP/IDNO)
            rc = db.execute_query(
                "SELECT COUNT(*) FROM AEI_MEMBERS WHERE IDNP=:d OR IDNO=:d",
                {"d": doc}
            )
            if rc['data'][0][0] > 0:
                continue
            field = "IDNO" if mtype == "COMPANY" else "IDNP"
            db.execute_query(f"""
                INSERT INTO AEI_MEMBERS
                    (LAST_NAME, FIRST_NAME, MEMBER_TYPE, {field},
                     PHONE, STATUS, JOIN_DATE, ADDRESS, NOTES)
                VALUES (:ln, :fn, :mt, :doc,
                        :ph, 'ACTIVE', TO_DATE(:jd,'DD.MM.YYYY'),
                        'Moldova', 'Demo member')
            """, {"ln":last,"fn":first,"mt":mtype,"doc":doc,"ph":phone,"jd":jdate})
            added += 1
        db.connection.commit()
        print(f"  Члены: добавлено {added}")

        # Build offset → member_id map via IDNP/IDNO lookup (handles duplicates correctly)
        r3 = db.execute_query("SELECT MEMBER_ID, IDNP, IDNO FROM AEI_MEMBERS ORDER BY MEMBER_ID", {})
        all_rows = r3.get('data', [])
        # existing members 1-11 by position
        pos_map = {i+1: row[0] for i, row in enumerate(all_rows)}
        # NEW_MEMBERS by doc lookup
        doc_to_mid = {}
        for row in all_rows:
            mid, idnp, idno = row[0], row[1], row[2]
            if idnp: doc_to_mid[str(idnp)] = mid
            if idno:  doc_to_mid[str(idno)]  = mid
        for i, (ln, fn, mt, doc, ph, jd) in enumerate(NEW_MEMBERS):
            offset = 12 + i
            mid = doc_to_mid.get(str(doc))
            if mid:
                pos_map[offset] = mid
        return pos_map

def add_loans(member_map):
    """Insert loans and generate schedules."""
    with DatabaseModel() as db:
        # existing contracts
        rc = db.execute_query("SELECT CONTRACT_NO FROM AEI_LOANS", {})
        existing = {row[0] for row in rc.get('data', [])}

    inserted = 0; skipped = 0; errors = 0
    for row in LOANS:
        (cno, moff, principal, rate, term, rtype, penalty,
         sign_dt, disb_dt, end_dt, risk, status, purpose, collateral, currency) = row

        if cno in existing:
            skipped += 1
            continue

        member_id = member_map.get(moff)
        if not member_id:
            print(f"  ! No member for offset {moff} (loan {cno})")
            errors += 1
            continue

        payload = {
            "member_id":      member_id,
            "contract_no":    cno,
            "sign_date":      sign_dt,
            "disbursement_date": disb_dt,
            "end_date":       end_dt,
            "principal":      float(principal),
            "interest_rate":  float(rate),
            "term_months":    int(term),
            "repayment_type": rtype,
            "penalty_rate":   float(penalty),
            "collateral":     collateral,
            "purpose":        purpose,
            "currency":       currency,
            "risk_class":     risk,
            "status":         "ACTIVE",  # will be updated below
            "notes":          f"Demo loan {cno}",
        }
        r = AEIStore.upsert_loan(payload)
        if not r.get("success"):
            print(f"  ! upsert_loan {cno}: {r.get('error')}")
            errors += 1
            continue

        loan_id = r.get("loan_id")
        if not loan_id:
            errors += 1
            continue

        # Generate schedule
        sg = AEIStore.generate_loan_schedule(loan_id)
        if not sg.get("success"):
            print(f"  ! schedule {cno}: {sg.get('error')}")

        # Update status and risk class
        with DatabaseModel() as db:
            db.execute_query(
                "UPDATE AEI_LOANS SET STATUS=:s, RISK_CLASS=:r WHERE LOAN_ID=:id",
                {"s": status, "r": risk, "id": loan_id}
            )
            db.connection.commit()

        inserted += 1

    print(f"  Кредиты: добавлено {inserted}, пропущено {skipped}, ошибок {errors}")
    return inserted

def mark_closed_loans_paid():
    """Pay all flows for CLOSED loans so they show correct payments."""
    with DatabaseModel() as db:
        r = db.execute_query(
            """SELECT f.FLOW_ID, f.AMOUNT_SCHEDULED, f.DUE_DATE, l.LOAN_ID
               FROM AEI_LOAN_FLOWS f
               JOIN AEI_LOANS l ON l.LOAN_ID = f.LOAN_ID
               WHERE l.STATUS = 'CLOSED'
                 AND f.FLOW_TYPE = 'PAYMENT'
                 AND (f.AMOUNT_PAID IS NULL OR f.AMOUNT_PAID = 0)""",
            {}
        )
        flows = r.get("data", [])
        print(f"  Неоплаченных потоков по CLOSED кредитам: {len(flows)}")
        paid = 0
        for flow in flows:
            fid, sched, due, lid = flow[0], float(flow[1] or 0), flow[2], flow[3]
            if hasattr(due, 'strftime'):
                pay_dt = due.strftime("%d.%m.%Y")
            else:
                pay_dt = str(due)
            res = AEIStore.record_loan_payment(fid, sched, pay_dt, "Achitat complet")
            if res.get("success"):
                paid += 1
        # reset status back to CLOSED (record_payment may flip to ACTIVE)
        db.execute_query(
            "UPDATE AEI_LOANS SET STATUS='CLOSED' WHERE STATUS='ACTIVE' AND LOAN_ID IN "
            "(SELECT DISTINCT LOAN_ID FROM AEI_LOAN_FLOWS WHERE FLOW_TYPE='PAYMENT' "
            " AND AMOUNT_PAID > 0 AND AMOUNT_OVERDUE = 0 "
            " GROUP BY LOAN_ID HAVING COUNT(*) = SUM(CASE WHEN AMOUNT_PAID >= AMOUNT_SCHEDULED*0.99 THEN 1 ELSE 0 END))",
            {}
        )
        db.connection.commit()
        print(f"  Оплачено потоков: {paid}")

def mark_partial_payments():
    """Simulate partial payments on ACTIVE loans for richer OLAP data."""
    with DatabaseModel() as db:
        # Pay 2-6 installments on each ACTIVE loan that has schedule
        r = db.execute_query(
            """SELECT l.LOAN_ID, l.CONTRACT_NO,
                      f.FLOW_ID, f.AMOUNT_SCHEDULED, f.DUE_DATE
               FROM AEI_LOANS l
               JOIN AEI_LOAN_FLOWS f ON f.LOAN_ID = l.LOAN_ID
               WHERE l.STATUS = 'ACTIVE'
                 AND f.FLOW_TYPE = 'PAYMENT'
                 AND (f.AMOUNT_PAID IS NULL OR f.AMOUNT_PAID = 0)
                 AND f.DUE_DATE < DATE '2026-01-01'
               ORDER BY l.LOAN_ID, f.DUE_DATE""",
            {}
        )
        flows = r.get("data", [])
        print(f"  Потоков ACTIVE до 01.01.2026: {len(flows)}")
        paid = 0
        for flow in flows:
            lid, cno, fid, sched, due = flow[0], flow[1], flow[2], float(flow[3] or 0), flow[4]
            if hasattr(due, 'strftime'):
                pay_dt = due.strftime("%d.%m.%Y")
            else:
                pay_dt = str(due)
            res = AEIStore.record_loan_payment(fid, sched, pay_dt, "Achitat la scadență")
            if res.get("success"):
                paid += 1
        print(f"  Оплачено прошедших рат: {paid}")

def print_olap_summary():
    with DatabaseModel() as db:
        # by status
        r = db.execute_query("""
            SELECT STATUS, COUNT(*), SUM(PRINCIPAL), AVG(INTEREST_RATE)
            FROM AEI_LOANS GROUP BY STATUS ORDER BY STATUS
        """, {})
        print("\n  По статусу:")
        for row in r.get("data", []):
            print(f"    {row[0]:10s}: {row[1]:3d} кред. {float(row[2]):>12,.0f} MDL  rate={float(row[3]):.1f}%")

        # by risk
        r2 = db.execute_query("""
            SELECT NVL(RISK_CLASS,'—'), COUNT(*), SUM(PRINCIPAL)
            FROM AEI_LOANS GROUP BY RISK_CLASS ORDER BY RISK_CLASS
        """, {})
        print("\n  По риску:")
        for row in r2.get("data", []):
            print(f"    {str(row[0]):6s}: {row[1]:3d} кред. {float(row[2]):>12,.0f} MDL")

        # by year
        r3 = db.execute_query("""
            SELECT TO_CHAR(DISBURSEMENT_DATE,'YYYY'), COUNT(*), SUM(PRINCIPAL)
            FROM AEI_LOANS GROUP BY TO_CHAR(DISBURSEMENT_DATE,'YYYY') ORDER BY 1
        """, {})
        print("\n  По году:")
        for row in r3.get("data", []):
            print(f"    {row[0]}: {row[1]:3d} кред. {float(row[2]):>12,.0f} MDL")

        # total
        r4 = db.execute_query("""
            SELECT COUNT(*), SUM(PRINCIPAL), AVG(INTEREST_RATE),
                   SUM(CASE WHEN STATUS='ACTIVE'  THEN PRINCIPAL ELSE 0 END),
                   SUM(CASE WHEN STATUS='OVERDUE' THEN PRINCIPAL ELSE 0 END),
                   SUM(CASE WHEN STATUS='CLOSED'  THEN PRINCIPAL ELSE 0 END)
            FROM AEI_LOANS
        """, {})
        if r4.get("data"):
            row = r4["data"][0]
            total = float(row[0]), float(row[1]), float(row[2] or 0)
            print(f"\n  ИТОГО: {int(row[0])} кред., портфель={float(row[1]):,.0f} MDL"
                  f", avg rate={float(row[2] or 0):.1f}%"
                  f"\n    Active={float(row[3]):,.0f}  Overdue={float(row[4]):,.0f}  Closed={float(row[5]):,.0f}")
            npl = float(row[4]) / max(float(row[1]),1) * 100
            print(f"    NPL={npl:.1f}%")

if __name__ == "__main__":
    print("=== AEÎ OLAP Demo Data Insertion ===\n")

    print("1. Члены АЭИ...")
    member_map = get_or_create_members()
    print(f"  member_map has {len(member_map)} entries")

    print("\n2. Кредиты...")
    add_loans(member_map)

    print("\n3. Оплата закрытых кредитов...")
    mark_closed_loans_paid()

    print("\n4. Оплата прошедших рат активных кредитов...")
    mark_partial_payments()

    print("\n5. Итог OLAP:")
    print_olap_summary()
