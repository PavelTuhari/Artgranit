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
    """requests_list() реально читает заявки, а не глотает ошибку SQL."""
    r = Biro26Credit.requests_list(50)
    if not r.get("success"):
        return [f"requests_list: {r.get('error')}"]
    rows = r["data"]
    cnt = Biro26DB().execute_query("SELECT COUNT(*) FROM TMS_CREDITE_REQ")
    total = int(cnt["data"][0][0]) if cnt.get("success") and cnt["data"] else 0
    if total and not rows:
        return [f"в TMS_CREDITE_REQ {total} строк, а requests_list вернул 0"]
    if rows and not {"ext_ref", "api_status"} <= set(rows[0]):
        return [f"нет колонок ext_ref/api_status: {sorted(rows[0])}"]
    return []


def t_mask_idnp() -> list[str]:
    """_mask_idnp не раскрывает больше 4 символов и безопасен на коротких строках."""
    fails = []
    for src in ("2000000000001", "12345", "123", ""):
        m = Biro26Credit._mask_idnp(src)
        if src and src in m:
            fails.append(f"_mask_idnp({src!r}) вернул исходное значение: {m!r}")
        visible = sum(1 for a, b in zip(src, m) if a == b and a.isdigit())
        if len(src) > 6 and visible > 4:
            fails.append(f"_mask_idnp({src!r})={m!r}: открыто {visible} символов")
        if 0 < len(src) <= 6 and any(c.isdigit() for c in m):
            fails.append(f"_mask_idnp({src!r})={m!r}: короткая строка не замаскирована")
    return fails


def t_safe_result_drops_pii() -> list[str]:
    """_safe_result оставляет только разрешённые поля и маскирует длинные цифры."""
    raw = {"success": True,
           "data": {"preapproved": True, "max_amount": 15000,
                    "first_name": "Ион", "last_name": "Попеску",
                    "birth_date": "1990-01-01", "message": "OK"},
           "error": "userPin=2000000000001 invalid"}
    out = Biro26Credit._safe_result(raw)
    fails = []
    for banned in ("first_name", "last_name", "birth_date"):
        if banned in out:
            fails.append(f"поле {banned} попало в лог")
    if "2000000000001" in str(out):
        fails.append(f"полный IDNP остался в логе: {out}")
    if out.get("max_amount") != 15000 or out.get("preapproved") is not True:
        fails.append(f"полезные поля потерялись: {out}")
    return fails


TESTS = [
    ("таблицы TMS_CREDITE_* существуют", t_tables_exist),
    ("нет YBIRO_CREDIT_* в коде", t_no_legacy_names_in_code),
    ("offers содержат provider", t_offers_carry_provider),
    ("providers_list маскирует секреты", t_providers_list),
    ("calc() не изменился", t_calc_unchanged),
    ("api без провайдера деградирует", t_api_without_provider_degrades),
    ("requests_list реально читает заявки", t_requests_list_reads),
    ("_mask_idnp безопасен", t_mask_idnp),
    ("_safe_result вырезает PII", t_safe_result_drops_pii),
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
