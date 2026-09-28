#!/usr/bin/env python3
"""Seed AGRO demo data into all 4 operational modules via HTTP API.

Modules seeded:
  1. Field / Purchases  -- 5 purchase documents
  2. Warehouse          -- readings, movements, processing tasks
  3. QA / HACCP         -- checklists, checks, batch blocks, HACCP plans & records
  4. Sales              -- 4 sales documents + 1 export declaration

Prerequisites:
  - The app must be running at http://localhost:3003
  - Master/reference data (suppliers, customers, items, warehouses, cells,
    currencies) must already exist via the Admin module.
"""
from __future__ import annotations

import json
import random
import sys
import time
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

import requests

BASE = "http://localhost:3003"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TIMEOUT = 120  # seconds per request (confirm operations are slow on remote Oracle)


def api_get(s: requests.Session, path: str, params: dict = None) -> dict:
    try:
        r = s.get(f"{BASE}{path}", params=params, timeout=TIMEOUT)
        return r.json()
    except requests.exceptions.Timeout:
        return {"success": False, "error": f"TIMEOUT after {TIMEOUT}s"}
    except Exception as e:
        return {"success": False, "error": str(e)[:200]}


def api_post(s: requests.Session, path: str, data: dict) -> dict:
    try:
        r = s.post(f"{BASE}{path}", json=data, timeout=TIMEOUT)
        return r.json()
    except requests.exceptions.Timeout:
        return {"success": False, "error": f"TIMEOUT after {TIMEOUT}s"}
    except Exception as e:
        return {"success": False, "error": str(e)[:200]}


def api_put(s: requests.Session, path: str, data: dict = None) -> dict:
    try:
        r = s.put(f"{BASE}{path}", json=data or {}, timeout=TIMEOUT)
        return r.json()
    except requests.exceptions.Timeout:
        return {"success": False, "error": f"TIMEOUT after {TIMEOUT}s"}
    except Exception as e:
        return {"success": False, "error": str(e)[:200]}


def ok(result: dict) -> bool:
    """Check whether an API response signals success."""
    return result.get("success") is True


def require_list(result: dict, key: str, label: str) -> list:
    """Extract a non-empty list from an API result or abort."""
    items = result.get(key) or result.get("data", {}).get(key, [])
    if not items:
        # Fallback: try top-level 'rows'/'items'/'data'
        for fallback_key in ("rows", "items", "data"):
            items = result.get(fallback_key, [])
            if isinstance(items, list) and items:
                break
    if not items:
        print(f"  [FATAL] No {label} found in reference data. "
              f"Please create master data first via Admin module.")
        print(f"         API response: {json.dumps(result, ensure_ascii=False)[:300]}")
        sys.exit(1)
    return items


# ---------------------------------------------------------------------------
# Counters
# ---------------------------------------------------------------------------
counts: Dict[str, int] = {
    "purchases_created": 0,
    "purchases_confirmed": 0,
    "readings_created": 0,
    "movements_created": 0,
    "tasks_created": 0,
    "tasks_updated": 0,
    "checklists_created": 0,
    "qa_checks_created": 0,
    "batches_blocked": 0,
    "batches_unblocked": 0,
    "haccp_plans_created": 0,
    "haccp_ccps_created": 0,
    "haccp_records_created": 0,
    "sales_created": 0,
    "sales_confirmed": 0,
    "export_decls_created": 0,
}


# ---------------------------------------------------------------------------
# 0. Login
# ---------------------------------------------------------------------------

def login(s: requests.Session) -> None:
    import os
    from dotenv import load_dotenv
    load_dotenv()
    username = os.environ.get("DEFAULT_USERNAME", "ADMIN")
    password = os.environ.get("DEFAULT_PASSWORD", "")
    r = s.post(f"{BASE}/login",
               data={"username": username, "password": password},
               allow_redirects=False)
    if r.status_code == 200:
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        if not body.get("success"):
            print(f"Login failed: {body.get('error', 'unknown')}")
            sys.exit(1)
    elif r.status_code not in (302,):
        print(f"Login failed (HTTP {r.status_code})")
        sys.exit(1)
    print(f"[OK] Logged in as {username}")


# ---------------------------------------------------------------------------
# 1. Purchases (Field module)
# ---------------------------------------------------------------------------

def seed_purchases(s: requests.Session) -> List[int]:
    """Create 5 purchase documents, confirm the first 3. Returns created doc IDs."""
    print("\n=== 1. Purchases (Field) ===")

    # Load references
    refs = api_get(s, "/api/agro-field/sync/references")
    suppliers = require_list(refs, "suppliers", "suppliers")
    warehouses = require_list(refs, "warehouses", "warehouses")
    items = require_list(refs, "items", "items")

    sup_ids = [sup.get("id") or sup.get("ID") for sup in suppliers]
    wh_ids = [wh.get("id") or wh.get("ID") for wh in warehouses]
    item_ids = [it.get("id") or it.get("ID") for it in items]

    print(f"  refs: {len(sup_ids)} suppliers, {len(wh_ids)} warehouses, {len(item_ids)} items")

    def pick_sup(idx: int) -> int:
        return sup_ids[idx % len(sup_ids)]

    def pick_wh(idx: int) -> int:
        return wh_ids[idx % len(wh_ids)]

    def make_line(item_idx: int) -> dict:
        item_id = item_ids[item_idx % len(item_ids)]
        pallets = random.randint(1, 5)
        crates = random.randint(5, 30)
        gross = round(random.uniform(200, 2000), 1)
        tare = round(random.uniform(5, 15) * crates, 1)
        net = round(gross - tare, 1)
        if net < 10:
            net = gross * 0.9
        price = round(random.uniform(0.50, 5.00), 2)
        return {
            "item_id": item_id,
            "pallets": pallets,
            "crates": crates,
            "gross_weight_kg": gross,
            "tare_weight_kg": tare,
            "net_weight_kg": net,
            "price_per_kg": price,
        }

    purchase_specs = [
        # (supplier_idx, warehouse_idx, num_lines, date_str, should_confirm)
        (0, 0, 3, "2026-03-10", True),
        (1, 0, 2, "2026-03-11", True),
        (0, 0, 4, "2026-03-12", True),
        (min(2, len(sup_ids) - 1), 0, 1, "2026-03-14", False),
        (1, 0, 2, "2026-03-15", False),
    ]

    created_ids: List[int] = []
    line_counter = 0

    for i, (sup_i, wh_i, n_lines, doc_date, confirm) in enumerate(purchase_specs, 1):
        lines = []
        for _ in range(n_lines):
            lines.append(make_line(line_counter))
            line_counter += 1

        payload = {
            "supplier_id": pick_sup(sup_i),
            "warehouse_id": pick_wh(wh_i),
            "doc_date": doc_date,
            "lines": lines,
        }

        res = api_post(s, "/api/agro-field/purchases", payload)
        doc_id = (res.get("doc_id") or res.get("id")
                  or res.get("data", {}).get("doc_id")
                  or res.get("data", {}).get("id"))
        if ok(res) and doc_id:
            counts["purchases_created"] += 1
            created_ids.append(doc_id)
            tag = "draft"
            if confirm:
                cr = api_put(s, f"/api/agro-field/purchases/{doc_id}/confirm")
                if ok(cr):
                    counts["purchases_confirmed"] += 1
                    tag = "confirmed"
                else:
                    tag = f"draft (confirm failed: {cr.get('error', '?')})"
            print(f"  PUR-{i:03d} id={doc_id} {tag} ({n_lines} lines)")
        else:
            print(f"  PUR-{i:03d} FAILED: {res.get('error', json.dumps(res, ensure_ascii=False)[:200])}")

    return created_ids


# ---------------------------------------------------------------------------
# 2. Warehouse -- readings, movements, tasks
# ---------------------------------------------------------------------------

def seed_warehouse(s: requests.Session) -> None:
    print("\n=== 2. Warehouse ===")

    # --- 2a. Temperature / sensor readings ---
    print("  -- sensor readings --")
    cells_res = api_get(s, "/api/agro-admin/storage-cells")
    cells = (cells_res.get("rows") or cells_res.get("items")
             or cells_res.get("data") or [])
    if not cells:
        print("  [WARN] No storage cells found; skipping readings.")
    else:
        cell_ids = [c.get("id") or c.get("ID") for c in cells]
        for i in range(12):
            cell_id = cell_ids[i % len(cell_ids)]
            # Alternate cold-storage and dry-storage profiles
            if i % 3 == 0:
                temp = round(random.uniform(18, 22), 1)
                humidity = round(random.uniform(60, 70), 1)
            else:
                temp = round(random.uniform(2, 8), 1)
                humidity = round(random.uniform(80, 95), 1)
            payload = {
                "cell_id": cell_id,
                "temperature_c": temp,
                "humidity_pct": humidity,
                "o2_pct": round(random.uniform(18, 21), 1),
                "co2_pct": round(random.uniform(0.03, 0.5), 2),
                "recorded_by": "sensor_bot",
            }
            res = api_post(s, "/api/agro-warehouse/readings", payload)
            if ok(res):
                counts["readings_created"] += 1
            else:
                print(f"    reading #{i+1} FAILED: {res.get('error', '?')}")
        print(f"    created {counts['readings_created']} readings")

    # --- 2b. Stock movements ---
    print("  -- stock movements --")
    stock_res = api_get(s, "/api/agro-warehouse/stock")
    batches = (stock_res.get("rows") or stock_res.get("items")
               or stock_res.get("data") or stock_res.get("batches") or [])
    if not batches:
        print("  [WARN] No batches in stock; skipping movements & tasks.")
        return

    batch_ids = [b.get("batch_id") or b.get("id") or b.get("ID") or b.get("BATCH_ID")
                 for b in batches]
    batch_ids = [b for b in batch_ids if b is not None]

    if not batch_ids:
        print("  [WARN] Could not extract batch IDs from stock response.")
        return

    # Get warehouses and cells for target references
    wh_res = api_get(s, "/api/agro-admin/warehouses")
    warehouses = wh_res.get("rows") or wh_res.get("items") or wh_res.get("data") or []
    wh_ids = [w.get("id") or w.get("ID") for w in warehouses] if warehouses else [None]
    cell_ids_all = cell_ids if cells else [None]

    movement_specs = [
        {"movement_type": "transfer", "reason": "Перемещение в камеру хранения"},
        {"movement_type": "processing", "reason": "Передача на сортировку"},
        {"movement_type": "adjustment", "reason": "Корректировка по инвентаризации"},
    ]

    for i, spec in enumerate(movement_specs):
        bid = batch_ids[i % len(batch_ids)]
        payload = {
            "batch_id": bid,
            "movement_type": spec["movement_type"],
            "qty_kg": round(random.uniform(50, 300), 1),
            "to_warehouse_id": wh_ids[0],
            "to_cell_id": cell_ids_all[i % len(cell_ids_all)] if cell_ids_all[0] else None,
            "reason": spec["reason"],
        }
        res = api_post(s, "/api/agro-warehouse/movements", payload)
        if ok(res):
            counts["movements_created"] += 1
            print(f"    movement #{i+1} ({spec['movement_type']}) OK")
        else:
            print(f"    movement #{i+1} FAILED: {res.get('error', '?')}")

    # --- 2c. Processing tasks ---
    print("  -- processing tasks --")
    task_specs = [
        {"task_type": "sorting", "description": "Сортировка по калибру и качеству"},
        {"task_type": "washing", "description": "Мойка и первичная обработка"},
        {"task_type": "packing", "description": "Фасовка в потребительскую упаковку"},
        {"task_type": "labeling", "description": "Маркировка партии и наклейка этикеток"},
    ]

    task_ids: List[int] = []
    for i, spec in enumerate(task_specs):
        bid = batch_ids[i % len(batch_ids)]
        payload = {
            "batch_id": bid,
            "task_type": spec["task_type"],
            "description": spec["description"],
            "input_qty_kg": round(random.uniform(100, 500), 1),
        }
        res = api_post(s, "/api/agro-warehouse/tasks", payload)
        tid = (res.get("task_id") or res.get("id")
               or res.get("data", {}).get("task_id")
               or res.get("data", {}).get("id"))
        if ok(res) and tid:
            counts["tasks_created"] += 1
            task_ids.append(tid)
            print(f"    task #{i+1} ({spec['task_type']}) id={tid}")
        else:
            print(f"    task #{i+1} FAILED: {res.get('error', '?')}")

    # Update statuses: first two -> completed, third -> in_progress
    status_updates = [
        ("in_progress", None, None),
        ("completed", lambda inp: round(inp * 0.92, 1), lambda inp: round(inp * 0.08, 1)),
    ]
    for i, tid in enumerate(task_ids[:3]):
        # Move to in_progress first
        res1 = api_put(s, f"/api/agro-warehouse/tasks/{tid}/status",
                       {"status": "in_progress"})
        if i < 2:
            # Then complete
            input_qty = round(random.uniform(100, 500), 1)
            res2 = api_put(s, f"/api/agro-warehouse/tasks/{tid}/status", {
                "status": "completed",
                "output_qty": round(input_qty * 0.92, 1),
                "waste_qty": round(input_qty * 0.08, 1),
            })
            if ok(res2):
                counts["tasks_updated"] += 1
                print(f"    task id={tid} -> completed")
            else:
                counts["tasks_updated"] += 1 if ok(res1) else 0
                print(f"    task id={tid} -> in_progress (complete failed: {res2.get('error','?')})")
        else:
            if ok(res1):
                counts["tasks_updated"] += 1
                print(f"    task id={tid} -> in_progress")


# ---------------------------------------------------------------------------
# 3. QA / HACCP
# ---------------------------------------------------------------------------

def seed_qa(s: requests.Session) -> None:
    print("\n=== 3. QA / HACCP ===")

    # --- 3a. Checklists ---
    print("  -- checklists --")
    checklist_defs = [
        {
            "name": "Входной контроль фруктов",
            "checklist_type": "incoming",
            "active": "Y",
            "items": [
                {"param_name": "Температура продукта", "choices": "2-8 C, +-1 C",
                 "is_critical": "Y"},
                {"param_name": "Визуальные повреждения", "choices": "отсутствуют, до 5%",
                 "is_critical": "Y"},
                {"param_name": "Целостность упаковки", "choices": "не нарушена",
                 "is_critical": "N"},
                {"param_name": "Признаки вредителей", "choices": "отсутствуют",
                 "is_critical": "Y"},
                {"param_name": "Влажность", "choices": "85-95%, +-5%",
                 "is_critical": "N"},
            ],
        },
        {
            "name": "GMP ежедневная проверка",
            "checklist_type": "gmp",
            "active": "Y",
            "items": [
                {"param_name": "Мытьё рук", "choices": "выполнено",
                 "is_critical": "Y"},
                {"param_name": "Чистота униформы", "choices": "чисто",
                 "is_critical": "N"},
                {"param_name": "Санитация оборудования", "choices": "выполнено",
                 "is_critical": "Y"},
                {"param_name": "Чистота полов", "choices": "чисто",
                 "is_critical": "N"},
            ],
        },
        {
            "name": "Санитарный контроль склада",
            "checklist_type": "sanitary",
            "active": "Y",
            "items": [
                {"param_name": "Ловушки для грызунов", "choices": "исправны",
                 "is_critical": "Y"},
                {"param_name": "Качество воды", "choices": "норма",
                 "is_critical": "Y"},
                {"param_name": "Утилизация отходов", "choices": "выполнено",
                 "is_critical": "N"},
                {"param_name": "Вентиляция", "choices": "работает",
                 "is_critical": "N"},
            ],
        },
    ]

    checklist_ids: List[int] = []
    checklist_item_map: Dict[int, List[int]] = {}  # checklist_id -> list of item IDs

    for cl_def in checklist_defs:
        res = api_post(s, "/api/agro-qa/checklists", cl_def)
        cl_id = (res.get("id") or res.get("checklist_id")
                 or res.get("data", {}).get("id")
                 or res.get("data", {}).get("checklist_id"))
        if ok(res) and cl_id:
            counts["checklists_created"] += 1
            checklist_ids.append(cl_id)
            print(f"    checklist '{cl_def['name']}' id={cl_id}")
            # Fetch detail to get item IDs
            detail = api_get(s, f"/api/agro-qa/checklists/{cl_id}")
            items = (detail.get("items") or detail.get("data", {}).get("items") or [])
            item_ids = [it.get("id") or it.get("ID") or it.get("item_id")
                        for it in items]
            item_ids = [x for x in item_ids if x is not None]
            checklist_item_map[cl_id] = item_ids
        else:
            print(f"    checklist '{cl_def['name']}' FAILED: "
                  f"{res.get('error', json.dumps(res, ensure_ascii=False)[:200])}")

    # --- 3b. QA Checks (need batch IDs) ---
    print("  -- qa checks --")
    stock_res = api_get(s, "/api/agro-warehouse/stock")
    batches = (stock_res.get("rows") or stock_res.get("items")
               or stock_res.get("data") or stock_res.get("batches") or [])
    batch_ids = [b.get("batch_id") or b.get("id") or b.get("ID") or b.get("BATCH_ID")
                 for b in batches]
    batch_ids = [b for b in batch_ids if b is not None]

    if not batch_ids:
        print("  [WARN] No batches for QA checks; skipping checks, blocks.")
    else:
        check_count = min(4, len(batch_ids) * len(checklist_ids))
        for i in range(check_count):
            bid = batch_ids[i % len(batch_ids)]
            cl_id = checklist_ids[i % len(checklist_ids)] if checklist_ids else None
            if not cl_id:
                continue
            item_ids = checklist_item_map.get(cl_id, [])
            values = []
            for j, iid in enumerate(item_ids):
                # Make most compliant, a few not
                compliant = not (i == 1 and j == 0)  # One failure in 2nd check
                values.append({
                    "checklist_item_id": iid,
                    "actual_value": "OK" if compliant else "НЕ OK -- отклонение",
                    "is_compliant": "Y" if compliant else "N",
                })
            payload = {
                "batch_id": bid,
                "checklist_id": cl_id,
                "checked_by": "qa_inspector",
                "values": values,
            }
            res = api_post(s, "/api/agro-qa/checks", payload)
            if ok(res):
                counts["qa_checks_created"] += 1
                chk_id = (res.get("check_id") or res.get("id")
                          or res.get("data", {}).get("check_id")
                          or res.get("data", {}).get("id"))
                print(f"    check #{i+1} batch={bid} checklist={cl_id} id={chk_id}")
            else:
                print(f"    check #{i+1} FAILED: {res.get('error', '?')}")

        # --- 3c. Batch blocks ---
        print("  -- batch blocks --")
        block_targets = batch_ids[:2] if len(batch_ids) >= 2 else batch_ids[:1]
        blocked_ids: List[int] = []

        for i, bid in enumerate(block_targets):
            reason = ("Превышение температуры хранения" if i == 0
                      else "Обнаружены визуальные дефекты")
            res = api_post(s, f"/api/agro-qa/batches/{bid}/block",
                           {"reason": reason, "blocked_by": "qa_inspector"})
            if ok(res):
                counts["batches_blocked"] += 1
                blocked_ids.append(bid)
                print(f"    blocked batch {bid}: {reason}")
            else:
                print(f"    block batch {bid} FAILED: {res.get('error', '?')}")

        # Unblock the first one
        if blocked_ids:
            bid = blocked_ids[0]
            res = api_post(s, f"/api/agro-qa/batches/{bid}/unblock", {
                "unblocked_by": "qa_manager",
                "resolution": "Температура стабилизирована, повторная проверка пройдена",
            })
            if ok(res):
                counts["batches_unblocked"] += 1
                print(f"    unblocked batch {bid}")
            else:
                print(f"    unblock batch {bid} FAILED: {res.get('error', '?')}")

    # --- 3d. HACCP Plans ---
    print("  -- haccp plans --")
    haccp_plans = [
        {"plan_name": "HACCP Фрукты свежие", "process_stage": "fruits", "active": "Y"},
        {"plan_name": "HACCP Овощи хранение", "process_stage": "vegetables", "active": "Y"},
    ]
    plan_ids: List[int] = []
    for plan in haccp_plans:
        res = api_post(s, "/api/agro-qa/haccp/plans", plan)
        pid = (res.get("plan_id") or res.get("id")
               or res.get("data", {}).get("plan_id")
               or res.get("data", {}).get("id"))
        if ok(res) and pid:
            counts["haccp_plans_created"] += 1
            plan_ids.append(pid)
            print(f"    plan '{plan['plan_name']}' id={pid}")
        else:
            print(f"    plan '{plan['plan_name']}' FAILED: {res.get('error', '?')}")

    # --- 3e. CCPs ---
    print("  -- haccp ccps --")
    ccp_defs = [
        # (plan_idx, ccp_number, hazard_type, hazard_description, limit_min, limit_max, monitoring, corrective)
        (0, "CCP-1", "biological", "Биологическое загрязнение при приёмке сырья",
         None, 8.0, "Измерение термометром при приёмке", "Отклонить партию и уведомить поставщика"),
        (0, "CCP-2", "biological", "Рост патогенов при повышенной температуре хранения",
         2.0, 6.0, "Мониторинг датчиками каждые 15 мин", "Перевести в исправную камеру"),
        (0, "CCP-3", "physical", "Нарушение холодовой цепи при отгрузке",
         None, 10.0, "Проверка температуры в кузове", "Задержать отгрузку до охлаждения"),
        (1, "CCP-1", "biological", "Развитие плесени при высокой влажности хранения овощей",
         70.0, 85.0, "Гигрометр 2 раза в смену", "Включить осушитель, переместить продукцию"),
        (1, "CCP-2", "physical", "Механическое повреждение при сортировке",
         None, 3.0, "Визуальный контроль при сортировке", "Остановить линию, откалибровать оборудование"),
    ]

    ccp_ids: List[int] = []
    for (plan_idx, ccp_num, haz_type, hazard, lim_min, lim_max, monitoring, corrective) in ccp_defs:
        if plan_idx >= len(plan_ids):
            continue
        payload = {
            "plan_id": plan_ids[plan_idx],
            "ccp_number": ccp_num,
            "hazard_type": haz_type,
            "hazard_description": hazard,
            "critical_limit_min": lim_min,
            "critical_limit_max": lim_max,
            "monitoring_frequency": monitoring,
            "corrective_action": corrective,
        }
        ccp_name = f"{ccp_num} {hazard[:40]}"
        res = api_post(s, "/api/agro-qa/haccp/ccps", payload)
        cid = (res.get("ccp_id") or res.get("id")
               or res.get("data", {}).get("ccp_id")
               or res.get("data", {}).get("id"))
        if ok(res) and cid:
            counts["haccp_ccps_created"] += 1
            ccp_ids.append(cid)
            print(f"    ccp '{ccp_name}' id={cid}")
        else:
            print(f"    ccp '{ccp_name}' FAILED: {res.get('error', '?')}")

    # --- 3f. HACCP Records ---
    print("  -- haccp records --")
    if ccp_ids and batch_ids:
        record_specs = [
            # (ccp_idx, batch_idx, measured_value, corrective_action)
            (0, 0, "6.5", None),
            (0, 0, "11.2", "Партия отклонена -- превышение температуры"),  # deviation!
            (1, 0, "3.8", None),
            (1, 1 % len(batch_ids), "4.1", None),
            (2, 0, "8.5", None),
            (min(3, len(ccp_ids)-1), 0, "92", "Включён осушитель"),  # deviation!
            (min(4, len(ccp_ids)-1), 1 % len(batch_ids), "1.2", None),
        ]
        for ccp_idx, batch_idx, value, corrective in record_specs:
            if ccp_idx >= len(ccp_ids):
                continue
            payload = {
                "ccp_id": ccp_ids[ccp_idx],
                "batch_id": batch_ids[batch_idx % len(batch_ids)],
                "measured_value": value,
            }
            if corrective:
                payload["corrective_action"] = corrective
            res = api_post(s, "/api/agro-qa/haccp/records", payload)
            if ok(res):
                counts["haccp_records_created"] += 1
            else:
                print(f"    haccp record FAILED: {res.get('error', '?')}")
        print(f"    created {counts['haccp_records_created']} HACCP records "
              f"(incl. deviations)")
    else:
        print("  [WARN] No CCPs or batches for HACCP records.")


# ---------------------------------------------------------------------------
# 4. Sales
# ---------------------------------------------------------------------------

def seed_sales(s: requests.Session) -> None:
    print("\n=== 4. Sales ===")

    # Load references
    cust_res = api_get(s, "/api/agro-admin/customers")
    customers = (cust_res.get("rows") or cust_res.get("items")
                 or cust_res.get("data") or [])
    if not customers:
        print("  [WARN] No customers found; skipping sales.")
        return
    cust_ids = [c.get("id") or c.get("ID") for c in customers]

    wh_res = api_get(s, "/api/agro-admin/warehouses")
    warehouses = (wh_res.get("rows") or wh_res.get("items")
                  or wh_res.get("data") or [])
    wh_ids = [w.get("id") or w.get("ID") for w in warehouses] if warehouses else [None]

    items_res = api_get(s, "/api/agro-admin/items")
    items = (items_res.get("rows") or items_res.get("items")
             or items_res.get("data") or [])
    item_ids = [it.get("id") or it.get("ID") for it in items] if items else []

    curr_res = api_get(s, "/api/agro-admin/currencies")
    currencies = (curr_res.get("rows") or curr_res.get("items")
                  or curr_res.get("data") or [])
    curr_ids = [c.get("id") or c.get("ID") for c in currencies] if currencies else [None]

    if not item_ids:
        print("  [WARN] No items found; skipping sales.")
        return

    print(f"  refs: {len(cust_ids)} customers, {len(wh_ids)} warehouses, "
          f"{len(item_ids)} items, {len(curr_ids)} currencies")

    def make_sale_line(item_idx: int) -> dict:
        return {
            "item_id": item_ids[item_idx % len(item_ids)],
            "qty_kg": round(random.uniform(100, 1500), 1),
            "price_per_kg": round(random.uniform(1.0, 6.0), 2),
        }

    sale_specs = [
        # (cust_idx, wh_idx, curr_idx, n_lines, notes, confirm)
        (0, 0, 0, 2, "Заказ для внутреннего рынка", True),
        (1 % len(cust_ids), 0, 0, 3, "Экспортный заказ -- Румыния", True),
        (0, 0, 0, 1, "Пробный заказ", False),
        (min(2, len(cust_ids)-1), 0, 0, 2, "Сезонная поставка", False),
    ]

    created_sale_ids: List[int] = []
    line_counter = 0

    for i, (ci, wi, cri, n_lines, notes, confirm) in enumerate(sale_specs, 1):
        lines = []
        for _ in range(n_lines):
            lines.append(make_sale_line(line_counter))
            line_counter += 1

        payload = {
            "customer_id": cust_ids[ci],
            "warehouse_id": wh_ids[wi % len(wh_ids)],
            "currency_id": curr_ids[cri % len(curr_ids)],
            "notes": notes,
            "lines": lines,
        }

        res = api_post(s, "/api/agro-sales/documents", payload)
        doc_id = (res.get("doc_id") or res.get("id")
                  or res.get("data", {}).get("doc_id")
                  or res.get("data", {}).get("id"))
        if ok(res) and doc_id:
            counts["sales_created"] += 1
            created_sale_ids.append(doc_id)
            tag = "draft"
            if confirm:
                cr = api_put(s, f"/api/agro-sales/documents/{doc_id}/confirm")
                if ok(cr):
                    counts["sales_confirmed"] += 1
                    tag = "confirmed"
                else:
                    tag = f"draft (confirm failed: {cr.get('error', '?')})"
            print(f"  SALE-{i:03d} id={doc_id} {tag} ({n_lines} lines) -- {notes}")
        else:
            print(f"  SALE-{i:03d} FAILED: {res.get('error', json.dumps(res, ensure_ascii=False)[:200])}")

    # --- Export declaration for the second sale (export) ---
    print("  -- export declarations --")
    export_doc_id = created_sale_ids[1] if len(created_sale_ids) >= 2 else None
    if export_doc_id:
        payload = {
            "sales_doc_id": export_doc_id,
            "destination_country": "Romania",
            "customs_code": "Giurgiulesti",
            "transport_conditions": "road",
            "phyto_cert_number": "PHYTO-MD-2026-0342",
            "notes": "Экспорт свежих фруктов, требуется фитосанитарный сертификат",
        }
        res = api_post(s, "/api/agro-sales/export-decl", payload)
        if ok(res):
            counts["export_decls_created"] += 1
            decl_id = (res.get("decl_id") or res.get("id")
                       or res.get("data", {}).get("id"))
            print(f"    export decl id={decl_id} for sale {export_doc_id}")
        else:
            print(f"    export decl FAILED: {res.get('error', '?')}")
    else:
        print("  [WARN] No confirmed export sale for export declaration.")


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def print_summary() -> None:
    print("\n" + "=" * 55)
    print("  AGRO Demo Data Seed -- Summary")
    print("=" * 55)
    sections = [
        ("PURCHASES (Field)", [
            ("Created", counts["purchases_created"]),
            ("Confirmed", counts["purchases_confirmed"]),
        ]),
        ("WAREHOUSE", [
            ("Sensor readings", counts["readings_created"]),
            ("Stock movements", counts["movements_created"]),
            ("Processing tasks created", counts["tasks_created"]),
            ("Processing tasks updated", counts["tasks_updated"]),
        ]),
        ("QA / HACCP", [
            ("Checklists", counts["checklists_created"]),
            ("QA checks", counts["qa_checks_created"]),
            ("Batches blocked", counts["batches_blocked"]),
            ("Batches unblocked", counts["batches_unblocked"]),
            ("HACCP plans", counts["haccp_plans_created"]),
            ("HACCP CCPs", counts["haccp_ccps_created"]),
            ("HACCP records", counts["haccp_records_created"]),
        ]),
        ("SALES", [
            ("Created", counts["sales_created"]),
            ("Confirmed", counts["sales_confirmed"]),
            ("Export declarations", counts["export_decls_created"]),
        ]),
    ]
    for section, rows in sections:
        print(f"\n  {section}:")
        for label, count in rows:
            status = "OK" if count > 0 else "--"
            print(f"    {label:<30s} {count:>4d}  [{status}]")

    total = sum(counts.values())
    print(f"\n  TOTAL operations: {total}")
    print("=" * 55)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("AGRO Demo Data Seeder")
    print(f"Target: {BASE}\n")

    s = requests.Session()

    # Step 0: Login
    login(s)

    # Step 1: Purchases
    purchase_ids = seed_purchases(s)

    # Brief pause to let confirmed purchases generate batches
    time.sleep(0.5)

    # Step 2: Warehouse (needs batches from confirmed purchases)
    seed_warehouse(s)

    # Step 3: QA / HACCP (needs batches)
    seed_qa(s)

    # Step 4: Sales
    seed_sales(s)

    # Summary
    print_summary()


if __name__ == "__main__":
    main()
