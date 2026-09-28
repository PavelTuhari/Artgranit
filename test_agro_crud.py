#!/usr/bin/env python3
"""
AGRO module — CRUD integration tests.

Tests INSERT (create) and UPDATE operations for all AGRO entities
via HTTP API against a running Flask server.

Usage:
  python test_agro_crud.py                    # run all tests
  python test_agro_crud.py --base-url http://host:port  # custom server
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import requests

# ── defaults ──────────────────────────────────────────────────────
DEFAULT_BASE = "http://localhost:3003"
USERNAME = "ADMIN"
PASSWORD = "ArtG2025UNAmd##"


def login(s: requests.Session, base: str) -> bool:
    r = s.post(f"{base}/api/login", json={"username": USERNAME, "password": PASSWORD})
    return r.ok and r.json().get("success")


def _ts() -> str:
    return str(int(time.time()))


# ── result tracking ───────────────────────────────────────────────
results: list[dict] = []


def report(entity: str, op: str, ok: bool, detail: str = ""):
    status = "OK" if ok else "FAIL"
    results.append({"entity": entity, "op": op, "ok": ok, "detail": detail})
    sym = "\u2713" if ok else "\u2717"
    print(f"  {sym} {entity:30s} {op:8s} {status}  {detail}")


# ── Generic CRUD helper ──────────────────────────────────────────
def crud_test(
    s: requests.Session,
    base: str,
    entity: str,
    url: str,
    create_data: dict,
    update_fields: dict,
    id_key: str = "id",
):
    """Test create (POST), read-back (GET), and update (POST with id)."""
    full_url = f"{base}{url}"

    # 1. CREATE
    r = s.post(full_url, json=create_data)
    body = r.json() if r.ok else {}
    ok = r.ok and body.get("success", False)
    report(entity, "INSERT", ok, body.get("error", ""))
    if not ok:
        return None

    # 2. READ (get created record)
    r2 = s.get(full_url)
    body2 = r2.json() if r2.ok else {}
    rows = body2.get("data", [])
    # find the created record by matching create_data fields
    rec_id = None
    for row in rows:
        match = True
        for k, v in create_data.items():
            if k in ("active",) or v is None or v == "":
                continue
            row_val = str(row.get(k, "")).lower() if row.get(k) is not None else ""
            data_val = str(v).lower()
            if row_val != data_val:
                match = False
                break
        if match:
            rec_id = row.get(id_key)
            break
    if rec_id is None and rows:
        # fallback: take the last row
        rec_id = rows[-1].get(id_key)
    report(entity, "READ", rec_id is not None, f"id={rec_id}" if rec_id else "not found")
    if rec_id is None:
        return None

    # 3. UPDATE
    upd = dict(create_data)
    upd[id_key] = rec_id
    upd.update(update_fields)
    r3 = s.post(full_url, json=upd)
    body3 = r3.json() if r3.ok else {}
    ok3 = r3.ok and body3.get("success", False)
    report(entity, "UPDATE", ok3, body3.get("error", ""))

    return rec_id


# ══════════════════════════════════════════════════════════════════
#  TEST DEFINITIONS
# ══════════════════════════════════════════════════════════════════

def test_admin_references(s: requests.Session, base: str):
    """Test all 11 admin reference tables."""
    ts = _ts()

    # 1. Suppliers
    crud_test(s, base, "Suppliers", "/api/agro-admin/suppliers",
              {"code": f"TST-S-{ts}", "name": f"Test Supplier {ts}", "country": "MD",
               "tax_id": f"TIN{ts}", "contact_phone": "+373-69-000000",
               "contact_email": f"s{ts}@test.md", "address": "Chisinau", "active": "Y"},
              {"name": f"Updated Supplier {ts}", "country": "RO"})

    # 2. Customers
    crud_test(s, base, "Customers", "/api/agro-admin/customers",
              {"code": f"TST-C-{ts}", "name": f"Test Customer {ts}", "customer_type": "domestic",
               "country": "MD", "tax_id": f"CIN{ts}", "contact_phone": "+373-60-111111",
               "contact_email": f"c{ts}@test.md", "address": "Balti", "active": "Y"},
              {"name": f"Updated Customer {ts}", "customer_type": "export"})

    # 3. Warehouses
    wh_id = crud_test(s, base, "Warehouses", "/api/agro-admin/warehouses",
                      {"code": f"TST-W-{ts}", "name": f"Test WH {ts}", "warehouse_type": "cold_storage",
                       "address": "Singera", "capacity_kg": "50000", "active": "Y"},
                      {"name": f"Updated WH {ts}", "capacity_kg": "75000"})

    # 4. Storage Cells (needs warehouse_id)
    if wh_id:
        crud_test(s, base, "Storage Cells", "/api/agro-admin/storage-cells",
                  {"warehouse_id": wh_id, "code": f"TST-CELL-{ts}", "name": f"Test Cell {ts}",
                   "cell_type": "chamber", "temp_min": "-2", "temp_max": "4",
                   "humidity_min": "85", "humidity_max": "95", "capacity_kg": "10000", "active": "Y"},
                  {"name": f"Updated Cell {ts}", "temp_max": "6"})

    # 5. Items
    crud_test(s, base, "Items", "/api/agro-admin/items",
              {"code": f"TST-I-{ts}", "name_ru": f"Тест-продукт {ts}", "name_ro": f"Produs-test {ts}",
               "item_group": "fruit", "unit": "kg", "default_tare_kg": "0.3",
               "shelf_life_days": "30", "optimal_temp_min": "0", "optimal_temp_max": "4", "active": "Y"},
              {"name_ru": f"Обновлённый продукт {ts}", "shelf_life_days": "45"})

    # 6. Packaging Types
    crud_test(s, base, "Packaging Types", "/api/agro-admin/packaging-types",
              {"code": f"TST-P-{ts}", "name_ru": f"Тест тара {ts}", "name_ro": f"Ambalaj test {ts}",
               "tare_weight_kg": "0.5", "capacity_kg": "20", "active": "Y"},
              {"name_ru": f"Обновлённая тара {ts}", "capacity_kg": "25"})

    # 7. Vehicles
    crud_test(s, base, "Vehicles", "/api/agro-admin/vehicles",
              {"plate_number": f"X{ts[-4:]}XX", "vehicle_type": "truck",
               "driver_name": f"Driver {ts}", "active": "Y"},
              {"driver_name": f"Updated Driver {ts}", "vehicle_type": "refrigerator"})

    # 8. Currencies
    crud_test(s, base, "Currencies", "/api/agro-admin/currencies",
              {"code": f"T{ts[-2:]}", "name": f"TestCur {ts}", "symbol": "T", "active": "Y"},
              {"name": f"UpdCur {ts}"})

    # 9. Exchange Rates
    crud_test(s, base, "Exchange Rates", "/api/agro-admin/exchange-rates",
              {"from_currency": "1", "to_currency": "2", "rate": "18.5",
               "rate_date": "2026-03-15", "source": "test"},
              {"rate": "19.0"})

    # 10. Formula Params
    crud_test(s, base, "Formula Params", "/api/agro-admin/formula-params",
              {"param_name": f"test_param_{ts}", "param_value": "1.05",
               "item_id": "", "active": "Y"},
              {"param_value": "1.10"})

    # 11. Module Config
    crud_test(s, base, "Module Config", "/api/agro-admin/module-config",
              {"config_key": f"test_key_{ts}", "config_value": "test_value",
               "config_group": "test", "description": f"Test config {ts}"},
              {"config_value": "updated_value"})


def test_field_purchase(s: requests.Session, base: str):
    """Test purchase document creation and line items."""
    ts = _ts()

    # Get reference IDs first
    sup = s.get(f"{base}/api/agro-admin/suppliers").json().get("data", [])
    wh = s.get(f"{base}/api/agro-admin/warehouses").json().get("data", [])
    items = s.get(f"{base}/api/agro-admin/items").json().get("data", [])
    cur = s.get(f"{base}/api/agro-admin/currencies").json().get("data", [])

    if not sup or not wh or not items:
        report("Purchase Doc", "INSERT", False, "missing reference data (suppliers/warehouses/items)")
        return

    # Create purchase document
    line_items = [
        {
            "item_id": items[0].get("id"),
            "gross_weight_kg": 1050,
            "tare_weight_kg": 50,
            "net_weight_kg": 1000,
            "price_per_kg": 12.5,
            "amount": 12500,
            "packaging_type_id": None,
            "crate_count": 20,
        }
    ]
    doc_data = {
        "supplier_id": sup[0].get("id"),
        "warehouse_id": wh[0].get("id"),
        "currency_id": cur[0].get("id") if cur else None,
        "vehicle_plate": "X999XX",
        "driver_name": "Test Driver",
        "items": line_items,
        "lines": line_items,
    }
    r = s.post(f"{base}/api/agro-field/purchases", json=doc_data)
    body = r.json() if r.ok else {}
    ok = r.ok and body.get("success", False)
    data = body.get("data", {})
    doc_id = data.get("doc_id") if isinstance(data, dict) else None
    report("Purchase Doc", "INSERT", ok, body.get("error", "") or f"doc_id={doc_id}")
    if not ok or not doc_id:
        return

    # Read back
    r2 = s.get(f"{base}/api/agro-field/purchases/{doc_id}")
    body2 = r2.json() if r2.ok else {}
    ok2 = r2.ok and body2.get("success", False)
    report("Purchase Doc", "READ", ok2, body2.get("error", ""))

    # Update (add note or update fields)
    upd = {"id": doc_id, "notes": f"Updated at {ts}", "vehicle_plate": "Y888YY", "lines": line_items}
    r3 = s.put(f"{base}/api/agro-field/purchases/{doc_id}", json=upd)
    body3 = r3.json() if r3.ok else {}
    ok3 = r3.ok and body3.get("success", False)
    report("Purchase Doc", "UPDATE", ok3, body3.get("error", ""))


def test_warehouse_ops(s: requests.Session, base: str):
    """Test warehouse operations: stock read, readings, tasks."""
    # Stock
    r = s.get(f"{base}/api/agro-warehouse/stock")
    body = r.json() if r.ok else {}
    report("Warehouse Stock", "READ", r.ok and body.get("success", False), body.get("error", ""))

    # Readings
    r2 = s.get(f"{base}/api/agro-warehouse/readings")
    body2 = r2.json() if r2.ok else {}
    report("Warehouse Readings", "READ", r2.ok and body2.get("success", False), body2.get("error", ""))

    # Add a reading (need a cell_id)
    cells = s.get(f"{base}/api/agro-admin/storage-cells").json().get("data", [])
    if cells:
        reading = {
            "cell_id": cells[0].get("id"),
            "temperature_c": 2.5,
            "humidity_pct": 90,
            "reading_source": "manual",
            "recorded_by": "test_script",
        }
        r3 = s.post(f"{base}/api/agro-warehouse/readings", json=reading)
        body3 = r3.json() if r3.ok else {}
        report("Storage Reading", "INSERT", r3.ok and body3.get("success", False), body3.get("error", ""))
    else:
        report("Storage Reading", "INSERT", False, "no cells available")

    # Alerts
    r4 = s.get(f"{base}/api/agro-warehouse/alerts")
    body4 = r4.json() if r4.ok else {}
    report("Warehouse Alerts", "READ", r4.ok and body4.get("success", False), body4.get("error", ""))

    # Tasks
    r5 = s.get(f"{base}/api/agro-warehouse/tasks")
    body5 = r5.json() if r5.ok else {}
    report("Warehouse Tasks", "READ", r5.ok and body5.get("success", False), body5.get("error", ""))

    # Create a processing task
    batches_r = s.get(f"{base}/api/agro-warehouse/stock").json()
    batches = batches_r.get("data", [])
    if batches:
        task_data = {
            "batch_id": batches[0].get("batch_id") or batches[0].get("id"),
            "task_type": "sorting",
            "description": "Test sorting task",
            "assigned_to": "test_user",
        }
        r6 = s.post(f"{base}/api/agro-warehouse/tasks", json=task_data)
        body6 = r6.json() if r6.ok else {}
        report("Processing Task", "INSERT", r6.ok and body6.get("success", False), body6.get("error", ""))


def test_sales_ops(s: requests.Session, base: str):
    """Test sales document creation."""
    ts = _ts()

    cust = s.get(f"{base}/api/agro-admin/customers").json().get("data", [])
    wh = s.get(f"{base}/api/agro-admin/warehouses").json().get("data", [])
    items = s.get(f"{base}/api/agro-admin/items").json().get("data", [])
    cur = s.get(f"{base}/api/agro-admin/currencies").json().get("data", [])

    if not cust or not wh or not items:
        report("Sales Doc", "INSERT", False, "missing reference data")
        return

    doc_data = {
        "customer_id": cust[0].get("id"),
        "warehouse_id": wh[0].get("id"),
        "sale_type": "domestic",
        "currency_id": cur[0].get("id") if cur else None,
        "lines": [
            {
                "item_id": items[0].get("id"),
                "gross_weight_kg": 500,
                "tare_weight_kg": 10,
                "net_weight_kg": 490,
                "price_per_kg": 15.0,
                "amount": 7350,
            }
        ],
    }
    r = s.post(f"{base}/api/agro-sales/documents", json=doc_data)
    body = r.json() if r.ok else {}
    ok = r.ok and body.get("success", False)
    doc_id = body.get("doc_id") or body.get("id")
    report("Sales Doc", "INSERT", ok, body.get("error", "") or f"doc_id={doc_id}")

    # Read back
    r2 = s.get(f"{base}/api/agro-sales/documents")
    body2 = r2.json() if r2.ok else {}
    report("Sales Docs List", "READ", r2.ok and body2.get("success", False), body2.get("error", ""))

    # Available stock
    r3 = s.get(f"{base}/api/agro-sales/available-stock")
    body3 = r3.json() if r3.ok else {}
    report("Available Stock", "READ", r3.ok and body3.get("success", False), body3.get("error", ""))


def test_qa_ops(s: requests.Session, base: str):
    """Test QA checklists and checks."""
    ts = _ts()

    # Create checklist
    cl_data = {
        "name": f"Тест чеклист {ts}",
        "name_ru": f"Тест чеклист {ts}",
        "name_ro": f"Checklist test {ts}",
        "active": "Y",
        "items": [
            {"parameter_name_ru": "Температура", "parameter_name_ro": "Temperatura",
             "value_type": "number", "min_value": "0", "max_value": "4", "is_critical": "Y", "item_order": 1},
            {"parameter_name_ru": "Влажность", "parameter_name_ro": "Umiditate",
             "value_type": "number", "min_value": "85", "max_value": "95", "is_critical": "N", "item_order": 2},
        ],
    }
    r = s.post(f"{base}/api/agro-qa/checklists", json=cl_data)
    body = r.json() if r.ok else {}
    ok = r.ok and body.get("success", False)
    cl_id = body.get("checklist_id") or body.get("id")
    report("QA Checklist", "INSERT", ok, body.get("error", "") or f"id={cl_id}")

    # Read checklists
    r2 = s.get(f"{base}/api/agro-qa/checklists")
    body2 = r2.json() if r2.ok else {}
    report("QA Checklists", "READ", r2.ok and body2.get("success", False),
           f"count={len(body2.get('data', []))}")

    # Perform a check if we have checklist and batches
    batches_r = s.get(f"{base}/api/agro-warehouse/stock").json()
    batches = batches_r.get("data", [])
    checklists = body2.get("data", [])
    if batches and checklists:
        check_data = {
            "checklist_id": checklists[0].get("id"),
            "batch_id": batches[0].get("batch_id") or batches[0].get("id"),
            "check_date": "2026-03-15",
            "inspector": "test_inspector",
            "values": [{"checklist_item_id": 1, "value": "2.5"}],
        }
        r3 = s.post(f"{base}/api/agro-qa/checks", json=check_data)
        body3 = r3.json() if r3.ok else {}
        report("QA Check", "INSERT", r3.ok and body3.get("success", False), body3.get("error", ""))

    # HACCP plans
    haccp_data = {
        "code": f"HACCP-{ts}",
        "plan_name": f"HACCP План {ts}",
        "name_ru": f"HACCP План {ts}",
        "name_ro": f"Plan HACCP {ts}",
        "process_stage": "reception",
        "active": "Y",
        "ccps": [
            {"hazard_type": "biological", "hazard_description": "Pathogen contamination",
             "critical_limit_min": "0", "critical_limit_max": "4",
             "monitoring_frequency": "every_batch", "corrective_action": "Reject batch"},
        ],
    }
    r4 = s.post(f"{base}/api/agro-qa/haccp/plans", json=haccp_data)
    body4 = r4.json() if r4.ok else {}
    report("HACCP Plan", "INSERT", r4.ok and body4.get("success", False), body4.get("error", ""))

    r5 = s.get(f"{base}/api/agro-qa/haccp/plans")
    body5 = r5.json() if r5.ok else {}
    report("HACCP Plans", "READ", r5.ok and body5.get("success", False),
           f"count={len(body5.get('data', []))}")


def test_scale(s: requests.Session, base: str):
    """Test scale emulator API."""
    # Config
    r = s.get(f"{base}/api/agro-scale/config")
    body = r.json() if r.ok else {}
    report("Scale Config", "READ", r.ok and body.get("success", False), body.get("error", ""))

    # Read (idle)
    r2 = s.get(f"{base}/api/agro-scale/read")
    body2 = r2.json() if r2.ok else {}
    report("Scale Read (idle)", "READ", r2.ok and body2.get("success", False), body2.get("error", ""))

    # Simulate load
    r3 = s.post(f"{base}/api/agro-scale/simulate", json={"weight_kg": 30.0})
    body3 = r3.json() if r3.ok else {}
    report("Scale Simulate", "INSERT", r3.ok and body3.get("success", False), body3.get("error", ""))

    # Wait for settling
    import time as _time
    _time.sleep(2)

    # Read (stable)
    r4 = s.get(f"{base}/api/agro-scale/read")
    body4 = r4.json() if r4.ok else {}
    stable = body4.get("data", {}).get("stable", False)
    report("Scale Read (stable)", "READ", r4.ok and stable,
           f"gross={body4.get('data', {}).get('gross_kg')}")

    # Zero
    r5 = s.post(f"{base}/api/agro-scale/zero", json={})
    body5 = r5.json() if r5.ok else {}
    report("Scale Zero", "UPDATE", r5.ok and body5.get("success", False), body5.get("error", ""))

    # Tare
    r6 = s.post(f"{base}/api/agro-scale/tare", json={})
    body6 = r6.json() if r6.ok else {}
    report("Scale Tare", "UPDATE", r6.ok and body6.get("success", False),
           f"tare_kg={body6.get('tare_kg')}")

    # Capture
    r7 = s.post(f"{base}/api/agro-scale/capture", json={})
    body7 = r7.json() if r7.ok else {}
    report("Scale Capture", "INSERT", r7.ok and body7.get("success", False), body7.get("error", ""))

    # List scales
    r8 = s.get(f"{base}/api/agro-scale/list")
    body8 = r8.json() if r8.ok else {}
    report("Scale List", "READ", r8.ok and body8.get("success", False), body8.get("error", ""))


def test_reports(s: requests.Session, base: str):
    """Test report endpoints."""
    for rpt in ["stock", "purchases", "sales", "mass_balance"]:
        r = s.get(f"{base}/api/agro-admin/reports/{rpt}")
        body = r.json() if r.ok else {}
        ok = r.ok and body.get("success", False)
        report(f"Report: {rpt}", "READ", ok, body.get("error", ""))


# ══════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════

def main():
    ap = argparse.ArgumentParser(description="AGRO CRUD integration tests")
    ap.add_argument("--base-url", default=DEFAULT_BASE)
    args = ap.parse_args()
    base = args.base_url.rstrip("/")

    print(f"\nAGRO CRUD Tests — {base}")
    print("=" * 76)

    s = requests.Session()

    # Auth
    print("\n[Auth]")
    if not login(s, base):
        print("  FAIL: cannot login")
        sys.exit(1)
    print("  Logged in OK\n")

    # Run test suites
    print("[Admin Reference Tables]")
    test_admin_references(s, base)

    print("\n[Field — Purchases]")
    test_field_purchase(s, base)

    print("\n[Warehouse Operations]")
    test_warehouse_ops(s, base)

    print("\n[Sales Operations]")
    test_sales_ops(s, base)

    print("\n[QA / HACCP]")
    test_qa_ops(s, base)

    print("\n[Scale Emulator]")
    test_scale(s, base)

    print("\n[Reports]")
    test_reports(s, base)

    # Summary
    total = len(results)
    passed = sum(1 for r in results if r["ok"])
    failed = total - passed
    print("\n" + "=" * 76)
    print(f"Total: {total}  |  Passed: {passed}  |  Failed: {failed}")
    if failed:
        print("\nFailed tests:")
        for r in results:
            if not r["ok"]:
                print(f"  - {r['entity']} / {r['op']}: {r['detail']}")
    print()
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
