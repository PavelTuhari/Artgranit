#!/usr/bin/env python3
"""
Вставка реалистичных демо-данных для P&L отчёта AEÎ.
Симулирует работу трёх ролей:
  - Оператор кредитов: платежи по кредитам
  - Бэкофис бухгалтер: начисление процентов, комиссии, резервы
  - Бухгалтер банк/касса: зарплата, аренда, банковские расходы

Период: Октябрь 2025 — Март 2026 (6 месяцев)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.aei_oracle_store import AEIStore
from models.database import DatabaseModel

# ────────────────────────────────────────────────────────────────
# ШАГ 1: Добавить счета которых нет в плане счетов
# ────────────────────────────────────────────────────────────────
NEW_ACCOUNTS = [
    # INCOME accounts (Venituri)
    ("8113", "811",  "Comisioane de acordare credite",   "INCOME",   "CREDIT", 1, "MDL"),
    ("8114", "811",  "Penalități și amenzi la credite",  "INCOME",   "CREDIT", 1, "MDL"),
    ("8115", "811",  "Dobânzi din plasamente la bănci",  "INCOME",   "CREDIT", 1, "MDL"),
    ("8116", "811",  "Alte venituri operaționale",       "INCOME",   "CREDIT", 1, "MDL"),
    # EXPENSE accounts (Cheltuieli)
    ("7211", "721",  "Cheltuieli cu personalul",         "EXPENSE",  "DEBIT",  1, "MDL"),
    ("7212", "721",  "Contribuții sociale angajator",    "EXPENSE",  "DEBIT",  1, "MDL"),
    ("7311", "731",  "Cheltuieli cu chiria",             "EXPENSE",  "DEBIT",  1, "MDL"),
    ("7312", "731",  "Servicii bancare și comisioane",   "EXPENSE",  "DEBIT",  1, "MDL"),
    ("7313", "731",  "Utilități și comunicații",         "EXPENSE",  "DEBIT",  1, "MDL"),
    ("7314", "731",  "Birotică și materiale",            "EXPENSE",  "DEBIT",  1, "MDL"),
    ("7411", "741",  "Provizioane pentru pierderi",      "EXPENSE",  "DEBIT",  1, "MDL"),
    ("7511", "751",  "Amortizarea imobilizărilor",       "EXPENSE",  "DEBIT",  1, "MDL"),
    # ASSET accounts for cash operations
    ("2411", "241",  "Casa (numerar)",                   "ASSET",    "DEBIT",  1, "MDL"),  # may exist
    ("3211", "321",  "Datorii față de personal",        "LIABILITY","CREDIT", 1, "MDL"),
    ("3212", "321",  "Datorii privind contr. sociale",  "LIABILITY","CREDIT", 1, "MDL"),
    ("3411", "341",  "Datorii față de proprietari",     "LIABILITY","CREDIT", 1, "MDL"),
]

def add_accounts():
    with DatabaseModel() as db:
        # get existing codes
        r = db.execute_query("SELECT ACCOUNT_CODE FROM AEI_ACCOUNTS", {})
        existing = {str(row[0]) for row in (r.get("data") or [])}

        added = 0
        for code, parent, name, atype, normal, active, curr in NEW_ACCOUNTS:
            if code in existing:
                continue
            db.execute_query(
                """INSERT INTO AEI_ACCOUNTS
                       (ACCOUNT_CODE, PARENT_CODE, ACCOUNT_NAME, ACCOUNT_TYPE,
                        NORMAL_BALANCE, IS_ACTIVE, NOTES, SORT_ORDER)
                   VALUES (:code,:parent,:name,:atype,:normal,:active,'',
                           (SELECT NVL(MAX(SORT_ORDER),0)+1 FROM AEI_ACCOUNTS))""",
                {"code":code,"parent":parent,"name":name,"atype":atype,
                 "normal":normal,"active":active}
            )
            added += 1
        db.connection.commit()
        print(f"  Счета: добавлено {added}, пропущено {len(NEW_ACCOUNTS)-added}")

# ────────────────────────────────────────────────────────────────
# ШАГ 2: Получить ID кредитов для записи платежей
# ────────────────────────────────────────────────────────────────
def get_loan_flows():
    """Получить неоплаченные потоки по кредитам."""
    with DatabaseModel() as db:
        r = db.execute_query(
            """SELECT f.FLOW_ID, f.LOAN_ID, f.AMOUNT_SCHEDULED, f.DUE_DATE,
                      l.CONTRACT_NO, l.INTEREST_RATE, l.PRINCIPAL
               FROM AEI_LOAN_FLOWS f
               JOIN AEI_LOANS l ON l.LOAN_ID = f.LOAN_ID
               WHERE f.FLOW_TYPE = 'PAYMENT'
                 AND (f.AMOUNT_PAID IS NULL OR f.AMOUNT_PAID = 0)
                 AND f.DUE_DATE <= DATE '2026-03-31'
               ORDER BY f.DUE_DATE, f.LOAN_ID
               FETCH FIRST 30 ROWS ONLY""",
            {}
        )
        flows = []
        for row in (r.get("data") or []):
            flows.append({
                "flow_id": row[0],
                "loan_id": row[1],
                "amount_scheduled": float(row[2] or 0),
                "due_date": row[3],
                "contract_no": row[4],
                "interest_rate": float(row[5] or 0),
                "principal": float(row[6] or 0),
            })
        return flows

# ────────────────────────────────────────────────────────────────
# ШАГ 3: Записать платежи — симулирует оператора кредитов
# ────────────────────────────────────────────────────────────────
def record_payments(flows):
    paid = 0
    for f in flows:
        due = f["due_date"]
        # payment date: 3-5 days before due (on time payments)
        if hasattr(due, 'strftime'):
            pay_date = due.strftime("%d.%m.%Y")
        else:
            pay_date = str(due)
        result = AEIStore.record_loan_payment(
            flow_id=f["flow_id"],
            amount_paid=f["amount_scheduled"],
            payment_date=pay_date,
            notes="Achitat conform grafic"
        )
        if result.get("success"):
            paid += 1
    print(f"  Платежи: записано {paid} из {len(flows)} потоков")
    return paid

# ────────────────────────────────────────────────────────────────
# ШАГ 4: Журнальные проводки — 6 месяцев
# ────────────────────────────────────────────────────────────────
# Структура: (date, debit, credit, amount, description, doc_ref, source_type)
# Роли: BO=Backoffice, OP=Operator, BK=Бухгалтер банк/касса

def build_journal_entries():
    entries = []

    months = [
        # (date,        label,      TS_income, TL_income, commission, penalty, deposit_exp_ts, deposit_exp_tl)
        ("31.10.2025", "Oct-2025",  11_200.0,  6_800.0,  1_800.0,   0.0,     5_400.0,  3_100.0),
        ("30.11.2025", "Nov-2025",  12_400.0,  8_200.0,  2_100.0,   420.0,   5_600.0,  3_400.0),
        ("31.12.2025", "Dec-2025",  13_800.0,  9_100.0,  1_500.0,   680.0,   5_900.0,  3_700.0),
        ("31.01.2026", "Ian-2026",  14_200.0,  9_800.0,  2_400.0,   820.0,   6_100.0,  4_000.0),
        ("28.02.2026", "Feb-2026",  13_600.0,  8_900.0,  1_950.0,  1_100.0,  5_800.0,  3_800.0),
        ("31.03.2026", "Mar-2026",  15_100.0, 10_300.0,  2_750.0,  1_350.0,  6_200.0,  4_200.0),
    ]

    fixed_monthly = [
        # salarii + contribuții (7211+7212 / 3211+3212) — бухгалтер касса
        # chirie 2 birouri (7311 / 2421) — банк
        # servicii bancare (7312 / 2421)
        # utilități (7313 / 2421)
        # birotică (7314 / 2421)
        # amortizare (7511 / xxx — нет пары, используем 3411)
        ("salarii_net",   7_200.0),   # salarii net к выплате
        ("contrib_soc",   2_520.0),   # CAS+CNAM 35% din salar net
        ("chirie",        2_800.0),
        ("servicii_bk",     380.0),
        ("utilitati",       290.0),
        ("birotica",        180.0),
        ("amortizare",    1_100.0),
    ]

    provision_monthly = [
        ("31.10.2025", 1_200.0),
        ("30.11.2025", 1_500.0),
        ("31.12.2025", 2_100.0),
        ("31.01.2026", 1_800.0),
        ("28.02.2026", 2_400.0),
        ("31.03.2026", 2_200.0),
    ]

    bank_interest = [
        ("31.12.2025", 720.0, "Dobânzi plasamente BNM, trim IV 2025"),
        ("31.03.2026", 840.0, "Dobânzi plasamente BNM, trim I 2026"),
    ]

    # ── BO: начисление процентов и комиссии ──
    for date, lbl, ts_inc, tl_inc, comm, penalty, dep_ts, dep_tl in months:
        # Venituri din dobânzi TS
        entries.append((date,"8311","8111", ts_inc,
            f"Dobânzi calculate credite TS — {lbl}", f"ACR-TS-{lbl}", "BACKOFFICE"))
        # Venituri din dobânzi TL
        entries.append((date,"8321","8112", tl_inc,
            f"Dobânzi calculate credite TL — {lbl}", f"ACR-TL-{lbl}", "BACKOFFICE"))
        # Comisioane de acordare
        if comm > 0:
            entries.append((date,"2421","8113", comm,
                f"Comisioane servicii creditare — {lbl}", f"COM-{lbl}", "OPERATOR"))
        # Penalități
        if penalty > 0:
            entries.append((date,"2451","8114", penalty,
                f"Penalități de întârziere — {lbl}", f"PEN-{lbl}", "OPERATOR"))
        # Cheltuieli dobânzi TS la depozite
        entries.append((date,"7151","51321", dep_ts,
            f"Dobânzi calculate dep. TS — {lbl}", f"DEP-TS-{lbl}", "BACKOFFICE"))
        # Cheltuieli dobânzi TL la depozite
        entries.append((date,"7152","4142", dep_tl,
            f"Dobânzi calculate dep. TL — {lbl}", f"DEP-TL-{lbl}", "BACKOFFICE"))

    # ── BK: salarii — бухгалтер касса ──
    salary_months = [
        ("05.11.2025","Oct-2025"), ("05.12.2025","Nov-2025"),
        ("07.01.2026","Dec-2025"), ("05.02.2026","Ian-2026"),
        ("05.03.2026","Feb-2026"), ("05.04.2026","Mar-2026"),
    ]
    for pay_date, lbl in salary_months:
        # calculul salariului (7211 / 3211)
        entries.append((pay_date,"7211","3211", 7_200.0,
            f"Calcul salarii angajați — {lbl}", f"SAL-{lbl}", "BANK"))
        # contribuții sociale angajator (7212 / 3212)
        entries.append((pay_date,"7212","3212", 2_520.0,
            f"CAS+CNAM angajator 35% — {lbl}", f"CAS-{lbl}", "BANK"))
        # plată salarii din casă/bancă (3211 / 2421)
        entries.append((pay_date,"3211","2421", 6_624.0,
            f"Plată salarii nete (impozit reținut) — {lbl}", f"PAY-{lbl}", "BANK"))
        # impozit pe venit reținut (7% PIT) → fisc
        entries.append((pay_date,"3211","5343", 576.0,
            f"Impozit venit angajat 8% reținut — {lbl}", f"PIT-{lbl}", "BANK"))
        # virare contribuții sociale
        entries.append((pay_date,"3212","2421", 2_520.0,
            f"Virare CAS+CNAM la buget — {lbl}", f"CAS-PAY-{lbl}", "BANK"))

    # ── BK: chirie ──
    rent_months = [
        "31.10.2025","30.11.2025","31.12.2025",
        "31.01.2026","28.02.2026","31.03.2026"
    ]
    for d in rent_months:
        entries.append((d,"7311","2421", 2_800.0,
            "Chirie birou — lunar", f"RENT-{d}", "BANK"))

    # ── BK: servicii bancare ──
    bank_svc_months = [
        ("31.10.2025",390.0), ("30.11.2025",345.0), ("31.12.2025",410.0),
        ("31.01.2026",380.0), ("28.02.2026",355.0), ("31.03.2026",420.0),
    ]
    for d, amt in bank_svc_months:
        entries.append((d,"7312","2421", amt,
            "Comisioane bancare — administrare cont", f"BK-SRV-{d}", "BANK"))

    # ── BK: utilități + birotică ──
    for d in rent_months:
        entries.append((d,"7313","2421", 290.0, "Utilități (curent, internet) — lunar", f"UTL-{d}", "BANK"))
        entries.append((d,"7314","2421", 180.0, "Birotică și consumabile — lunar", f"BIR-{d}", "BANK"))

    # ── BO: amortizare echipament ──
    for d in rent_months:
        entries.append((d,"7511","3411", 1_100.0,
            "Amortizare echipament IT și mobilier — lunar", f"AMO-{d}", "BACKOFFICE"))

    # ── BO: provizioane pentru pierderi ──
    for date, amt in provision_monthly:
        entries.append((date,"7411","9201", amt,
            "Provizioane pentru pierderi la credite", f"PROV-{date}", "BACKOFFICE"))

    # ── BK: venituri din dobânzi plasamente bancare ──
    for date, amt, desc in bank_interest:
        entries.append((date,"2421","8115", amt, desc, f"BNM-INT-{date}", "BANK"))

    # ── BK: recuperare credit repayment (principal) ──
    principal_entries = [
        ("31.10.2025", 5_000.0, "Rambursare principal credit C-2025-001"),
        ("30.11.2025", 5_000.0, "Rambursare principal credit C-2025-001"),
        ("31.12.2025", 5_000.0, "Rambursare principal credit C-2025-001"),
        ("31.01.2026",10_000.0, "Rambursare principal credit C-2025-002"),
        ("28.02.2026",10_000.0, "Rambursare principal credit C-2025-002"),
        ("31.03.2026",10_000.0, "Rambursare principal credit C-2025-002"),
    ]
    for date, amt, desc in principal_entries:
        entries.append((date,"2421","8311", amt, desc, f"PRIN-{date}", "OPERATOR"))

    return entries

def insert_journal_entries(entries):
    inserted = 0
    errors = 0
    for date, debit, credit, amount, desc, doc_ref, src_type in entries:
        data = {
            "entry_date": date,
            "debit_account": debit,
            "credit_account": credit,
            "amount": amount,
            "description": desc,
            "document_ref": doc_ref,
            "source_type": src_type,
            "created_by": {
                "BACKOFFICE": "backoffice_acct",
                "OPERATOR": "operator_credit",
                "BANK": "cashier_bank",
            }.get(src_type, "system"),
        }
        r = AEIStore.insert_journal_entry(data)
        if r.get("success"):
            inserted += 1
        else:
            errors += 1
            print(f"  ! ERROR {date} {debit}/{credit} {amount}: {r.get('error')}")
    print(f"  Проводки: вставлено {inserted}, ошибок {errors}")
    return inserted

# ────────────────────────────────────────────────────────────────
# ШАГ 5: Другие вениturi — единовременные
# ────────────────────────────────────────────────────────────────
def insert_one_off_entries():
    one_off = [
        # BO: dividende din participații (8116)
        ("31.12.2025","2421","8116", 12_500.0,
         "Dividende primite din participații FEE 2025","DIV-2025","BACKOFFICE"),
        # BO: restituire TVA (venit neoperațional)
        ("15.01.2026","2421","8116", 3_200.0,
         "Restituire supraachitare impozit 2025","TVA-RST","BACKOFFICE"),
        # BK: depunere capital suplimentar de la fondatori
        ("01.10.2025","2421","4141", 50_000.0,
         "Depunere capital suplimentar — fondatori 2025","CAP-OCT","BANK"),
        # OP: majorare cont curent din încasări credite
        ("31.10.2025","2421","2451", 15_000.0,
         "Rambursare credit — transfer la cont curent","RBK-OCT","OPERATOR"),
        ("31.01.2026","2421","2451", 22_000.0,
         "Rambursare credit — transfer la cont curent","RBK-IAN","OPERATOR"),
        ("31.03.2026","2421","2451", 18_000.0,
         "Rambursare credit — transfer la cont curent","RBK-MAR","OPERATOR"),
    ]
    inserted = 0
    for date, debit, credit, amount, desc, doc_ref, src_type in one_off:
        data = {
            "entry_date": date, "debit_account": debit, "credit_account": credit,
            "amount": amount, "description": desc, "document_ref": doc_ref,
            "source_type": src_type,
            "created_by": {
                "BACKOFFICE":"backoffice_acct","OPERATOR":"operator_credit","BANK":"cashier_bank"
            }.get(src_type,"system"),
        }
        r = AEIStore.insert_journal_entry(data)
        if r.get("success"): inserted += 1
        else: print(f"  ! {date}: {r.get('error')}")
    print(f"  Разовые проводки: {inserted}")

# ────────────────────────────────────────────────────────────────
# MAIN
# ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=== AEÎ Demo P&L Data Insertion ===\n")

    print("1. Добавление счетов...")
    add_accounts()

    print("\n2. Запись платежей по кредитам (оператор)...")
    flows = get_loan_flows()
    print(f"  Найдено неоплаченных потоков: {len(flows)}")
    if flows:
        record_payments(flows)

    print("\n3. Построение журнальных проводок...")
    entries = build_journal_entries()
    print(f"  Всего проводок: {len(entries)}")

    print("\n4. Вставка журнала...")
    insert_journal_entries(entries)

    print("\n5. Разовые проводки...")
    insert_one_off_entries()

    print("\n=== Готово. Проверяем итоги ===")
    # Quick P&L summary
    with DatabaseModel() as db:
        r = db.execute_query(
            """SELECT a.ACCOUNT_TYPE, a.ACCOUNT_CODE, a.ACCOUNT_NAME,
                      SUM(j.AMOUNT) AS total
               FROM AEI_JOURNAL j
               JOIN AEI_ACCOUNTS a ON a.ACCOUNT_CODE IN (j.DEBIT_ACCOUNT, j.CREDIT_ACCOUNT)
               WHERE a.ACCOUNT_TYPE IN ('INCOME','EXPENSE')
                 AND ((a.NORMAL_BALANCE='CREDIT' AND a.ACCOUNT_CODE = j.CREDIT_ACCOUNT)
                   OR (a.NORMAL_BALANCE='DEBIT'  AND a.ACCOUNT_CODE = j.DEBIT_ACCOUNT))
               GROUP BY a.ACCOUNT_TYPE, a.ACCOUNT_CODE, a.ACCOUNT_NAME
               ORDER BY a.ACCOUNT_TYPE DESC, a.ACCOUNT_CODE""",
            {}
        )
        print()
        total_inc = 0; total_exp = 0
        last_type = None
        for row in (r.get("data") or []):
            atype, code, name, total = row[0], row[1], row[2] or "", float(row[3] or 0)
            if atype != last_type:
                print(f"\n{'─'*60}")
                print(f"  {atype}")
                print(f"{'─'*60}")
                last_type = atype
            print(f"  {code:8s} {name[:35]:35s}  {total:>12,.2f} MDL")
            if atype == 'INCOME': total_inc += total
            else: total_exp += total
        print(f"\n{'═'*60}")
        print(f"  Total INCOME:   {total_inc:>12,.2f} MDL")
        print(f"  Total EXPENSE:  {total_exp:>12,.2f} MDL")
        print(f"  {'PROFIT' if total_inc>total_exp else 'PIERDERE'}:  {abs(total_inc-total_exp):>12,.2f} MDL")
        print(f"  Marjă netă:     {total_inc>0 and round((total_inc-total_exp)/total_inc*100,1) or 0}%")
