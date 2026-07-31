#!/usr/bin/env python3
"""Biro26 — кредитный модуль на TMS_CREDITE_* (живой тест против OfficePlus).

Usage: ./venv/bin/python test_biro26_credite.py
"""
from __future__ import annotations

import sys

from models.biro26_credit import Biro26Credit
from models.biro26_db import Biro26DB

TABLES = ["TMS_CREDITE_PROVIDER", "TMS_CREDITE_PROVIDER_PARAM", "TMS_CREDITE_ORG",
          "TMS_CREDITE_PLAN", "TMS_CREDITE_REQ", "TMS_CREDITE_REQ_EVENT"]


def t_tables_exist() -> list[str]:
    db = Biro26DB()
    fails = []
    for t in TABLES:
        r = db.execute_query(
            "SELECT COUNT(*) FROM USER_OBJECTS WHERE OBJECT_NAME = :n", {"n": t})
        if not r.get("success") or not r["data"] or int(r["data"][0][0]) == 0:
            fails.append(f"нет объекта {t}")
    return fails


def t_no_legacy_names_in_code() -> list[str]:
    """В коде модуля не осталось обращений к YBIRO_CREDIT_*."""
    src = open("models/biro26_credit.py", encoding="utf-8").read()
    return ["в models/biro26_credit.py остались YBIRO_CREDIT_*"] \
        if "YBIRO_CREDIT_" in src else []


def t_offers_carry_provider() -> list[str]:
    """public_offers() отдаёт у каждой организации поле provider."""
    r = Biro26Credit.public_offers()
    if not r.get("success"):
        return [f"public_offers: {r.get('error')}"]
    fails = []
    for o in r["data"]:
        if "provider" not in o:
            fails.append(f"организация {o.get('name')!r} без ключа provider")
            continue
        p = o["provider"]
        if p is not None and not {"code", "name", "configured"} <= set(p):
            fails.append(f"provider организации {o.get('name')!r}: ключи {set(p)}")
    return fails


def t_providers_list() -> list[str]:
    r = Biro26Credit.providers_list()
    if not r.get("success"):
        return [f"providers_list: {r.get('error')}"]
    codes = {p["code"] for p in r["data"]}
    if codes != {"easycredit", "iute"}:
        return [f"провайдеры {codes}, ожидались easycredit + iute"]
    for p in r["data"]:
        for secret_name in ("api_password", "api_key"):
            v = p.get("params", {}).get(secret_name)
            if v and not v.endswith("***"):
                return [f"{p['code']}: секрет {secret_name} не замаскирован: {v!r}"]
    return []


def t_calc_unchanged() -> list[str]:
    """calc() продолжает считать по прежней формуле для существующего пакета."""
    plans = Biro26Credit.plans_list()
    if not plans.get("success"):
        return [f"plans_list: {plans.get('error')}"]
    enabled = [p for p in plans["data"] if p.get("enabled") == "1"]
    if not enabled:
        print("  [skip] нет включённых пакетов кредита")
        return []
    p = enabled[0]
    r = Biro26Credit.calc(10000, p["id"], p["months_min"], 0)
    if not r.get("success"):
        return [f"calc: {r.get('error')}"]
    d = r["data"]
    expected_price = round(10000 * (1 + float(p["markup_pct"] or 0) / 100), 2)
    if abs(d["credit_price"] - expected_price) > 0.01:
        return [f"credit_price={d['credit_price']}, ожидалось {expected_price}"]
    return []


def t_api_without_provider_degrades() -> list[str]:
    """api_preapproved для организации без провайдера возвращает ошибку, не падает."""
    r = Biro26Credit.api_preapproved({"org_id": 999999, "idnp": "2000000000001",
                                      "amount": 10000, "phone": "+37369000001"})
    if r.get("success"):
        return ["ожидался отказ для несуществующей организации"]
    if not r.get("error"):
        return ["нет поля error в ответе"]
    return []


def t_requests_list_reads() -> list[str]:
    """requests_list() читает заявки и не прячет ошибку SQL под пустой успех."""
    fails = []
    r = Biro26Credit.requests_list(50)
    if not r.get("success"):
        return [f"requests_list: {r.get('error')}"]
    rows = r["data"]
    cnt = Biro26DB().execute_query("SELECT COUNT(*) FROM TMS_CREDITE_REQ")
    total = int(cnt["data"][0][0]) if cnt.get("success") and cnt["data"] else 0
    if total == 0:
        fails.append("в TMS_CREDITE_REQ нет строк — тест ничего не проверяет")
    if total and not rows:
        fails.append(f"в TMS_CREDITE_REQ {total} строк, а requests_list вернул 0")
    if rows and not {"ext_ref", "api_status", "provider_code"} <= set(rows[0]):
        fails.append(f"нет ожидаемых колонок: {sorted(rows[0])}")
    # ошибка SQL обязана всплыть как success=False, а не как пустой успех
    bad = Biro26DB().execute_query("SELECT NO_SUCH_COLUMN FROM TMS_CREDITE_REQ")
    if bad.get("success"):
        fails.append("заведомо неверный запрос отчитался успехом — проверка невалидна")
    return fails


def t_reads_surface_sql_errors() -> list[str]:
    """Методы чтения не отдают пустой успех при ошибке SQL."""
    import inspect
    src = inspect.getsource(Biro26Credit)
    fails = []
    if '"success": True, "data": rows' in src or "'success': True, 'data': rows" in src:
        fails.append("остался паттерн success=True с необработанной ошибкой запроса")
    for name in ("orgs_list", "plans_list", "public_offers", "request_events"):
        body = inspect.getsource(getattr(Biro26Credit, name))
        if "_result(" not in body and "success" in body and "_rows(" in body:
            fails.append(f"{name} всё ещё возвращает _rows() без проверки успеха")
    return fails


def t_mask_idnp() -> list[str]:
    """_mask_idnp сохраняет длину, раскрывает не более 2+2 символов и не течёт на коротких."""
    fails = []
    cases = ["2000000000001", "1234567", "123456", "12", "1", ""]
    for src in cases:
        m = Biro26Credit._mask_idnp(src)
        if len(m) != len(src):
            fails.append(f"_mask_idnp({src!r})={m!r}: длина {len(m)} != {len(src)}")
            continue
        if src and src == m:
            fails.append(f"_mask_idnp({src!r}) вернул исходное значение")
        if len(src) > 6:
            if m[:2] != src[:2] or m[-2:] != src[-2:]:
                fails.append(f"_mask_idnp({src!r})={m!r}: края должны быть открыты")
            if any(c.isdigit() for c in m[2:-2]):
                fails.append(f"_mask_idnp({src!r})={m!r}: середина не замаскирована")
        elif src:
            if any(c.isdigit() for c in m):
                fails.append(f"_mask_idnp({src!r})={m!r}: короткая строка не замаскирована")
    return fails


def t_safe_result_drops_pii() -> list[str]:
    """_safe_result оставляет только allowlist и чистит PII, включая вложенные структуры."""
    raw = {"success": True,
           "data": {"preapproved": True, "max_amount": 15000,
                    "first_name": "Ион", "last_name": "Попеску",
                    "birth_date": "1990-01-01", "message": "OK",
                    "status": {"first_name": "Ion", "idnp": "2000000000001",
                               "state": "NEW"},
                    "history": [{"first_name": "Ana", "message": "tel 069 123 456 789"}]},
           "error": "userPin=2000-000-000-001 invalid"}
    out = Biro26Credit._safe_result(raw)
    flat = str(out)
    fails = []
    for banned in ("first_name", "last_name", "birth_date", "Ион", "Попеску", "Ion", "Ana"):
        if banned in flat:
            fails.append(f"PII {banned!r} попало в лог: {flat[:200]}")
    for banned in ("2000000000001", "2000-000-000-001", "069 123 456 789"):
        if banned in flat:
            fails.append(f"незамаскированные цифры {banned!r}: {flat[:200]}")
    if out.get("max_amount") != 15000 or out.get("preapproved") is not True:
        fails.append(f"полезные поля потерялись: {out}")
    return fails


def t_status_requires_ref() -> list[str]:
    """Публичный статус не отдаётся без совпадающей ссылки, ответ неразличим от «нет такой»."""
    import app as _app
    c = _app.app.test_client()
    fails = []
    r1 = c.get('/api/biro26/shop/credit/api/status?req_id=1')
    d1 = r1.get_json() or {}
    if d1.get("success"):
        fails.append("статус отдан без параметра ref")
    r2 = c.get('/api/biro26/shop/credit/api/status?req_id=1&ref=NOPE-000')
    d2 = r2.get_json() or {}
    if d2.get("success"):
        fails.append("статус отдан по неверной ссылке")
    r3 = c.get('/api/biro26/shop/credit/api/status?req_id=99999999&ref=NOPE-000')
    d3 = r3.get_json() or {}
    if (d3.get("error") or "") != (d2.get("error") or ""):
        fails.append(f"ответы различимы: несуществующая={d3.get('error')!r}, "
                     f"чужая={d2.get('error')!r}")
    return fails


def t_calc_bad_input_no_500() -> list[str]:
    """Публичный calc не отдаёт 500 на пустом или мусорном теле."""
    import app as _app
    c = _app.app.test_client()
    fails = []
    # Базовые случаи мусора без плана
    for body in (None, {}, {"amount": "abc"}, {"plan_id": "x", "amount": 1000}):
        r = c.post('/api/biro26/shop/credit/calc', json=body)
        if r.status_code == 429:
            continue  # rate-limited, not a 500 — acceptable under repeated runs
        if r.status_code >= 500:
            fails.append(f"body={body!r} -> HTTP {r.status_code}")
        elif (r.get_json() or {}).get("success"):
            fails.append(f"body={body!r} принято як валидное")
    # Случаи с реальным включённым пакетом, но мусорными months и avans
    plans = Biro26Credit.plans_list()
    if plans.get("success"):
        enabled = [p for p in plans["data"] if p.get("enabled") == "1"]
        if enabled:
            pid = enabled[0]["id"]
            for body in ({"plan_id": pid, "amount": 10000, "months": "abc"},
                         {"plan_id": pid, "amount": 10000, "avans": "abc"}):
                r = c.post('/api/biro26/shop/credit/calc', json=body)
                if r.status_code == 429:
                    continue  # rate-limited, acceptable
                if r.status_code >= 500:
                    fails.append(f"body={body!r} -> HTTP {r.status_code}")
                elif (r.get_json() or {}).get("success"):
                    fails.append(f"body={body!r} принято как валидное")
    return fails


def t_offers_carry_capabilities() -> list[str]:
    """provider в offers несёт список возможностей, согласованный с реестром провайдеров."""
    r = Biro26Credit.public_offers()
    if not r.get("success"):
        return [f"public_offers: {r.get('error')}"]
    reg = Biro26Credit._registry()
    fails = []
    for o in r["data"]:
        p = o.get("provider")
        if p is None:
            continue
        if not isinstance(p.get("capabilities"), list):
            fails.append(f"{o.get('name')!r}: capabilities не список: {p.get('capabilities')!r}")
            continue
        prov = reg.get(p["code"])
        if prov is not None and set(p["capabilities"]) != set(prov.capabilities):
            fails.append(f"{p['code']}: {p['capabilities']} != {prov.capabilities}")
    # контракт провайдеров: easycredit умеет preapproved, iute — нет
    ec, iu = reg.get("easycredit"), reg.get("iute")
    if ec is not None and "preapproved" not in ec.capabilities:
        fails.append("easycredit потерял preapproved")
    if iu is not None and "preapproved" in iu.capabilities:
        fails.append("iute заявил preapproved, хотя метод не реализован — обнови витрину")
    return fails


TESTS = [
    ("таблицы TMS_CREDITE_* существуют", t_tables_exist),
    ("нет YBIRO_CREDIT_* в коде", t_no_legacy_names_in_code),
    ("offers содержат provider", t_offers_carry_provider),
    ("providers_list маскирует секреты", t_providers_list),
    ("calc() не изменился", t_calc_unchanged),
    ("api без провайдера деградирует", t_api_without_provider_degrades),
    ("requests_list реально читает заявки", t_requests_list_reads),
    ("методы чтения не прячут ошибки SQL", t_reads_surface_sql_errors),
    ("_mask_idnp безопасен", t_mask_idnp),
    ("_safe_result вырезает PII", t_safe_result_drops_pii),
    ("публичный статус требует ref", t_status_requires_ref),
    ("публичный calc не падает с 500 на мусоре", t_calc_bad_input_no_500),
]


def main() -> int:
    bad = 0
    for name, fn in TESTS:
        try:
            fails = fn()
        except Exception as e:
            import traceback
            traceback.print_exc()
            fails = [f"исключение: {e}"]
        if fails:
            bad += 1
            print(f"[FAIL] {name}")
            for f in fails:
                print(f"        {f}")
        else:
            print(f"[ok]   {name}")
    print(f"\n{len(TESTS) - bad}/{len(TESTS)} passed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
