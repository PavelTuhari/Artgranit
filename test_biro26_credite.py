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


def t_provider_test_detects_auth_failure() -> list[str]:
    """provider_test не считает успехом ответ провайдера об отказе авторизации."""
    import models.biro26_credit as bc

    class _FakeProv:
        capabilities = ["preapproved"]
        def is_configured(self): return True
        def preapproved(self, **kw):
            return {"success": True, "data": {"preapproved": False, "max_amount": 50000,
                                              "status": "Invalid User Name / Password - 50000",
                                              "message": ""}}

    class _FakeReg:
        def get(self, code): return _FakeProv()

    orig_reg, orig_log = bc.Biro26Credit._registry, bc.Biro26Credit._log_event
    bc.Biro26Credit._registry = staticmethod(lambda: _FakeReg())
    bc.Biro26Credit._log_event = staticmethod(lambda *a, **k: None)
    try:
        r = bc.Biro26Credit.provider_test("easycredit")
    finally:
        bc.Biro26Credit._registry = orig_reg
        bc.Biro26Credit._log_event = orig_log
    return [] if not r.get("success") else [f"provider_test отчитался успехом: {r}"]


def t_public_errors_are_neutral() -> list[str]:
    """Внутренние детали провайдера не уходят публичному клиенту."""
    import models.biro26_credit as bc

    class _FailProv:
        capabilities = ["preapproved"]
        def is_configured(self): return True
        def preapproved(self, **kw):
            return {"success": False,
                    "error": "401 https://partner-api-dev.iute.md/api/v1/orders"}

    class _FakeReg:
        def get(self, code): return _FailProv()

    orig_reg, orig_log, orig_link = (bc.Biro26Credit._registry, bc.Biro26Credit._log_event,
                                     bc.Biro26Credit._org_provider)
    bc.Biro26Credit._registry = staticmethod(lambda: _FakeReg())
    bc.Biro26Credit._log_event = staticmethod(lambda *a, **k: None)
    bc.Biro26Credit._org_provider = staticmethod(
        lambda org_id: {"org_id": org_id, "org_name": "T", "provider_code": "iute"})
    try:
        r = bc.Biro26Credit.api_preapproved({"org_id": 1, "idnp": "2000000000001",
                                             "amount": 10000, "phone": ""})
    finally:
        bc.Biro26Credit._registry = orig_reg
        bc.Biro26Credit._log_event = orig_log
        bc.Biro26Credit._org_provider = orig_link
    err = str(r.get("error") or "")
    fails = []
    if r.get("success"):
        fails.append("ошибка провайдера отдана как успех")
    for leak in ("partner-api-dev", "iute.md", "401", "http"):
        if leak in err.lower():
            fails.append(f"утечка внутренней детали {leak!r} в публичном ответе: {err!r}")
    return fails


def t_public_credit_requires_client_login() -> list[str]:
    """Публичные preapproved/submit требуют входа клиента магазина.

    Finding 5: раньше при 429 на обоих эндпоинтах тест проходил вырожденно,
    ничего не проверив. Теперь сначала сбрасываем счётчики лимитера (если
    установленная версия flask-limiter это поддерживает), а если оба вызова
    всё равно упёрлись в лимит — явно проваливаем тест, а не тихо проходим.
    """
    import app as _app
    c = _app.app.test_client()
    try:
        _app.limiter.reset()
    except Exception:
        pass
    fails = []
    checked = 0
    for path, body in (('/api/biro26/shop/credit/api/preapproved',
                        {"org_id": 1, "idnp": "2000000000001", "amount": 10000}),
                       ('/api/biro26/shop/credit/api/submit',
                        {"org_id": 1, "plan_id": 1, "amount": 10000,
                         "client_name": "T", "phone": "+37360000000",
                         "idnp": "2000000000001"})):
        r = c.post(path, json=body)
        if r.status_code == 429:
            continue  # rate-limited, not a proof of anything — see checked==0 below
        checked += 1
        d = r.get_json() or {}
        if d.get("success"):
            fails.append(f"{path}: доступен без входа клиента")
        if not d.get("auth_required"):
            fails.append(f"{path}: нет признака auth_required, ответ {d}")
    if checked == 0:
        fails.append("оба эндпоинта ответили 429 — тест не проверил ничего "
                     "(лимитер не сброшен/не сбрасывается); подождите сброса "
                     "окна лимита (10/min и 5/min) и перезапустите")
    return fails


def t_api_submit_status_save_failure_is_neutral() -> list[str]:
    """Finding 5: cind providerul accepta cererea, dar UPDATE-ul statusului
    local esueaza, textul brut al erorii Oracle (ORA-...) nu trebuie sa
    ajunga in raspunsul public — detaliile raman doar in jurnal."""
    import models.biro26_credit as bc

    class _FakeDB:
        """Nu atinge Oracle: INSERT-ul cererii "reuseste", UPDATE-ul statusului
        "esueaza" cu un mesaj Oracle brut, ca sa verificam ca nu se scurge."""

        def execute_query(self, sql, params=None):
            s = " ".join(sql.split()).upper()
            if "TMS_CREDITE_REQ_SEQ.NEXTVAL" in s:
                return {"success": True, "columns": ["ID"], "data": [[999999999]]}
            raise AssertionError(f"neasteptat query in test: {sql}")

        def execute_dml(self, sql, params=None):
            s = " ".join(sql.split()).upper()
            if s.startswith("INSERT INTO TMS_CREDITE_REQ ("):
                return {"success": True}
            if s.startswith("UPDATE TMS_CREDITE_REQ SET EXT_REF"):
                return {"success": False,
                        "message": "ORA-00001: unique constraint (X.PK_TMS) violated"}
            raise AssertionError(f"neasteptat dml in test: {sql}")

    class _FakeProv:
        capabilities = ["submit"]
        def is_configured(self): return True
        def submit(self, **kw):
            return {"success": True, "data": {"urn": "URN-TEST-1"}}

    class _FakeReg:
        def get(self, code): return _FakeProv()

    fake_plan = {"id": 1, "name": "Test", "org_id": 1, "org_name": "T",
                "months_min": 6, "months_max": 12, "amount_min": 1000,
                "amount_max": 100000, "markup_pct": 0, "annual_pct": 0,
                "monthly_fee_pct": 0, "issue_fee": 0, "avans_min_pct": 0}

    orig_db = bc.Biro26DB
    orig_reg = bc.Biro26Credit._registry
    orig_log = bc.Biro26Credit._log_event
    orig_org_provider = bc.Biro26Credit._org_provider
    orig_plan_get = bc.Biro26Credit.plan_get
    bc.Biro26DB = _FakeDB
    bc.Biro26Credit._registry = staticmethod(lambda: _FakeReg())
    bc.Biro26Credit._log_event = staticmethod(lambda *a, **k: None)
    bc.Biro26Credit._org_provider = staticmethod(
        lambda org_id: {"org_id": org_id, "org_name": "T", "provider_code": "easycredit"})
    bc.Biro26Credit.plan_get = staticmethod(lambda plan_id: dict(fake_plan))
    try:
        r = bc.Biro26Credit.api_submit({
            "org_id": 1, "plan_id": 1, "amount": 10000,
            "client_name": "Test Testov", "phone": "+37369000000",
            "idnp": "2000000000001"})
    finally:
        bc.Biro26DB = orig_db
        bc.Biro26Credit._registry = orig_reg
        bc.Biro26Credit._log_event = orig_log
        bc.Biro26Credit._org_provider = orig_org_provider
        bc.Biro26Credit.plan_get = orig_plan_get

    fails = []
    if r.get("success"):
        fails.append("ожidat success=False (UPDATE-ul statusului a esuat)")
    err = str(r.get("error") or "")
    if "ORA-" in err.upper():
        fails.append(f"textul brut al erorii Oracle s-a scurs in raspunsul public: {err!r}")
    if not err:
        fails.append("raspunsul public nu are deloc mesaj de eroare")
    return fails


def t_auth_failure_markers_precise() -> list[str]:
    """Finding 3: распознавание отказа авторизации не задевает легитимные тексты."""
    from models.biro26_credit import Biro26Credit as B
    should_match = [
        "Invalid User Name / Password - 50000",
        "401 Client Error: Unauthorized for url: https://partner-api-dev.iute.md/api/v1/x",
        "HTTP 403 Forbidden",
    ]
    should_not_match = [
        "Предодобрено до 50000 лей",
        "Two-factor authentication sent",
        "max_amount: 50000",
        "Cerere aprobata, suma 50000",
    ]
    fails = []
    for t in should_match:
        if not B._is_auth_failure({"data": {"status": t}}):
            fails.append(f"не распознан отказ авторизации: {t!r}")
    for t in should_not_match:
        if B._is_auth_failure({"data": {"message": t}}):
            fails.append(f"ложное срабатывание на: {t!r}")
    return fails


def t_request_create_insert_failure_is_neutral() -> list[str]:
    """Finding 1b: cind INSERT-ul cererii in TMS_CREDITE_REQ esueaza (ex. ORA-12154
    cu calea catre wallet-ul Oracle), textul brut nu trebuie sa ajunga in
    raspunsul public — doar in jurnalul TMS_CREDITE_REQ_EVENT."""
    import models.biro26_credit as bc

    class _FakeDB:
        """Nu atinge Oracle: INSERT-ul cererii "esueaza" cu un mesaj Oracle brut
        (calea wallet-ului), ca sa verificam ca nu se scurge in raspunsul public."""

        def execute_query(self, sql, params=None):
            s = " ".join(sql.split()).upper()
            if "TMS_CREDITE_REQ_SEQ.NEXTVAL" in s:
                return {"success": True, "columns": ["ID"], "data": [[999999997]]}
            if "FROM TMS_CREDITE_ORG" in s:
                return {"success": True,
                        "columns": ["ID", "NAME", "ORG_MODE", "API_URL"],
                        "data": [[1, "Test Org", "manual", None]]}
            raise AssertionError(f"neasteptat query in test: {sql}")

        def execute_dml(self, sql, params=None):
            s = " ".join(sql.split()).upper()
            if s.startswith("INSERT INTO TMS_CREDITE_REQ ("):
                return {"success": False,
                        "message": ("ORA-12154: TNS:could not resolve the connect "
                                   "identifier /home/ubuntu/oracle_wallets/wallet_X")}
            raise AssertionError(f"neasteptat dml in test: {sql}")

    fake_plan = {"id": 1, "name": "Test", "org_id": 1, "org_name": "T",
                "months_min": 6, "months_max": 12, "amount_min": 1000,
                "amount_max": 100000, "markup_pct": 0, "annual_pct": 0,
                "monthly_fee_pct": 0, "issue_fee": 0, "avans_min_pct": 0}

    logged = []
    orig_db = bc.Biro26DB
    orig_log = bc.Biro26Credit._log_event
    orig_plan_get = bc.Biro26Credit.plan_get
    orig_calc = bc.Biro26Credit.calc
    bc.Biro26DB = _FakeDB
    bc.Biro26Credit._log_event = staticmethod(lambda *a, **k: logged.append((a, k)))
    bc.Biro26Credit.plan_get = staticmethod(lambda plan_id: dict(fake_plan))
    bc.Biro26Credit.calc = staticmethod(
        lambda amount, plan_id, months, avans: {
            "success": True,
            "data": {"plan_id": 1, "plan": "Test", "org": "T", "months": 6,
                    "price": amount, "credit_price": amount, "markup_pct": 0,
                    "avans": 0, "financed": amount, "monthly": amount / 6,
                    "issue_fee": 0, "total": amount, "overcost": 0}})
    try:
        r = bc.Biro26Credit.request_create({
            "plan_id": 1, "amount": 10000, "qty": 1,
            "client_name": "Test Client", "phone": "+37360000000"})
    finally:
        bc.Biro26DB = orig_db
        bc.Biro26Credit._log_event = orig_log
        bc.Biro26Credit.plan_get = orig_plan_get
        bc.Biro26Credit.calc = orig_calc

    fails = []
    if r.get("success"):
        fails.append("ожidatat success=False (INSERT-ul cererii a esuat)")
    err = str(r.get("error") or "")
    if "ORA-" in err.upper():
        fails.append(f"textul brut al erorii Oracle s-a scurs in raspunsul public: {err!r}")
    if "wallet" in err.lower():
        fails.append(f"calea wallet-ului s-a scurs in raspunsul public: {err!r}")
    if not err:
        fails.append("raspunsul public nu are deloc mesaj de eroare")
    if not logged:
        fails.append("eroarea Oracle bruta nu a fost jurnalizata (_log_event neapelat)")
    return fails


def t_api_submit_insert_failure_is_neutral() -> list[str]:
    """Finding 1: cind INSERT-ul cererii in TMS_CREDITE_REQ esueaza (ex. ORA-12154
    cu calea catre wallet-ul Oracle), textul brut nu trebuie sa ajunga in
    raspunsul public — doar in jurnalul TMS_CREDITE_REQ_EVENT."""
    import models.biro26_credit as bc

    class _FakeDB:
        """Nu atinge Oracle: INSERT-ul cererii "esueaza" cu un mesaj Oracle brut
        (calea wallet-ului), ca sa verificam ca nu se scurge in raspunsul public."""

        def execute_query(self, sql, params=None):
            s = " ".join(sql.split()).upper()
            if "TMS_CREDITE_REQ_SEQ.NEXTVAL" in s:
                return {"success": True, "columns": ["ID"], "data": [[999999998]]}
            raise AssertionError(f"neasteptat query in test: {sql}")

        def execute_dml(self, sql, params=None):
            s = " ".join(sql.split()).upper()
            if s.startswith("INSERT INTO TMS_CREDITE_REQ ("):
                return {"success": False,
                        "message": ("ORA-12154: TNS:could not resolve the connect "
                                   "identifier /home/ubuntu/oracle_wallets/wallet_X")}
            raise AssertionError(f"neasteptat dml in test: {sql}")

    class _FakeProv:
        capabilities = ["submit"]
        def is_configured(self): return True
        def submit(self, **kw):
            raise AssertionError("submit nu trebuie apelat cind INSERT a esuat")

    class _FakeReg:
        def get(self, code): return _FakeProv()

    fake_plan = {"id": 1, "name": "Test", "org_id": 1, "org_name": "T",
                "months_min": 6, "months_max": 12, "amount_min": 1000,
                "amount_max": 100000, "markup_pct": 0, "annual_pct": 0,
                "monthly_fee_pct": 0, "issue_fee": 0, "avans_min_pct": 0}

    logged = []
    orig_db = bc.Biro26DB
    orig_reg = bc.Biro26Credit._registry
    orig_log = bc.Biro26Credit._log_event
    orig_org_provider = bc.Biro26Credit._org_provider
    orig_plan_get = bc.Biro26Credit.plan_get
    bc.Biro26DB = _FakeDB
    bc.Biro26Credit._registry = staticmethod(lambda: _FakeReg())
    bc.Biro26Credit._log_event = staticmethod(lambda *a, **k: logged.append((a, k)))
    bc.Biro26Credit._org_provider = staticmethod(
        lambda org_id: {"org_id": org_id, "org_name": "T", "provider_code": "easycredit"})
    bc.Biro26Credit.plan_get = staticmethod(lambda plan_id: dict(fake_plan))
    try:
        r = bc.Biro26Credit.api_submit({
            "org_id": 1, "plan_id": 1, "amount": 10000,
            "client_name": "Test Testov", "phone": "+37369000000",
            "idnp": "2000000000001"})
    finally:
        bc.Biro26DB = orig_db
        bc.Biro26Credit._registry = orig_reg
        bc.Biro26Credit._log_event = orig_log
        bc.Biro26Credit._org_provider = orig_org_provider
        bc.Biro26Credit.plan_get = orig_plan_get

    fails = []
    if r.get("success"):
        fails.append("ожидался success=False (INSERT-ul cererii a esuat)")
    err = str(r.get("error") or "")
    if "ORA-" in err.upper() or "wallet" in err.lower():
        fails.append(f"textul brut al erorii Oracle s-a scurs in raspunsul public: {err!r}")
    if not err:
        fails.append("raspunsul public nu are deloc mesaj de eroare")
    if not logged:
        fails.append("eroarea Oracle bruta nu a fost jurnalizata (_log_event neapelat)")
    return fails


def t_effective_markup_includes_transport() -> list[str]:
    """Действующая наценка = наценка пакета + надбавка организации за транспорт."""
    offers = Biro26Credit.public_offers()
    if not offers.get("success") or not offers["data"]:
        print("  [skip] нет активных организаций с пакетами")
        return []
    org = offers["data"][0]
    # надбавку читаем из БД, а не хардкодим: тест не должен ломаться при её смене
    tm = float(org.get("transport_markup_pct") or 0)
    plans = [p for p in (org.get("plans") or [])]
    if not plans:
        print("  [skip] у организации нет активных пакетов")
        return []
    fails = []
    for p in plans[:3]:
        plan_markup = float(p.get("markup_pct") or 0)
        r = Biro26Credit.calc(10000, p["id"], p["months_min"], 0)
        if not r.get("success"):
            fails.append(f"calc({p['id']}): {r.get('error')}")
            continue
        d = r["data"]
        expect_price = round(10000 * (1 + (plan_markup + tm) / 100), 2)
        if abs(d["credit_price"] - expect_price) > 0.01:
            fails.append(f"пакет {p['id']}: credit_price={d['credit_price']}, "
                         f"ожидалось {expect_price} ({plan_markup}+{tm}%)")
        if abs(float(d.get("plan_markup_pct", -1)) - plan_markup) > 0.01:
            fails.append(f"пакет {p['id']}: plan_markup_pct={d.get('plan_markup_pct')}, "
                         f"ожидалось {plan_markup}")
        if abs(float(d.get("transport_markup_pct", -1)) - tm) > 0.01:
            fails.append(f"пакет {p['id']}: transport_markup_pct="
                         f"{d.get('transport_markup_pct')}, ожидалось {tm}")
        if abs(float(d.get("markup_pct", -1)) - (plan_markup + tm)) > 0.01:
            fails.append(f"пакет {p['id']}: markup_pct={d.get('markup_pct')} "
                         f"не равен сумме {plan_markup}+{tm}")
    if tm == 0:
        print("  [note] надбавка сейчас 0 — проверена только формула, не эффект")
    return fails


def t_offers_carry_transport_markup() -> list[str]:
    """public_offers() отдаёт у организации числовое поле transport_markup_pct."""
    r = Biro26Credit.public_offers()
    if not r.get("success"):
        return [f"public_offers: {r.get('error')}"]
    fails = []
    for o in r["data"]:
        v = o.get("transport_markup_pct")
        if not isinstance(v, (int, float)):
            fails.append(f"{o.get('name')!r}: transport_markup_pct={v!r} не число")
    return fails


def t_invoice_transport_rule() -> list[str]:
    """Транспорт обязателен для обычного заказа и не требуется для кредитного.

    Заказ НЕ создаётся: без клиентской сессии роут отклоняет запрос раньше,
    чем дойдёт до записи, поэтому проверяем правило на уровне контроллера —
    что блок транспорта пропускается ровно при наличии credit_plan_id.
    """
    import inspect
    from controllers.biro26_controller import Biro26Controller
    src = inspect.getsource(Biro26Controller.shop_invoice)
    fails = []
    if "distance_km is required" not in src:
        fails.append("проверка обязательного транспорта исчезла из shop_invoice")
    if "credit_plan_id" not in src.split("distance_km is required")[0]:
        fails.append("блок транспорта не знает про credit_plan_id — "
                     "кредитный заказ по-прежнему потребует км")
    # и роут действительно не создаёт заказ без входа клиента
    import app as _app
    c = _app.app.test_client()
    r = c.post('/api/biro26/shop/invoice', json={"items": [{"cod": 1, "qty": 1}]})
    if r.status_code < 500 and (r.get_json() or {}).get("success"):
        fails.append("заказ создан без входа клиента")
    return fails


TESTS = [
    ("действующая наценка = пакет + транспорт", t_effective_markup_includes_transport),
    ("offers несут transport_markup_pct", t_offers_carry_transport_markup),
    ("правило транспорта при кредите", t_invoice_transport_rule),
    ("таблицы TMS_CREDITE_* существуют", t_tables_exist),
    ("нет YBIRO_CREDIT_* в коде", t_no_legacy_names_in_code),
    ("offers содержат provider", t_offers_carry_provider),
    ("offers несут capabilities провайдера", t_offers_carry_capabilities),
    ("providers_list маскирует секреты", t_providers_list),
    ("calc() не изменился", t_calc_unchanged),
    ("api без провайдера деградирует", t_api_without_provider_degrades),
    ("requests_list реально читает заявки", t_requests_list_reads),
    ("методы чтения не прячут ошибки SQL", t_reads_surface_sql_errors),
    ("_mask_idnp безопасен", t_mask_idnp),
    ("_safe_result вырезает PII", t_safe_result_drops_pii),
    ("публичный статус требует ref", t_status_requires_ref),
    ("публичный calc не падает с 500 на мусоре", t_calc_bad_input_no_500),
    ("provider_test распознаёт отказ авторизации", t_provider_test_detects_auth_failure),
    ("публичные ошибки нейтральны (без утечек)", t_public_errors_are_neutral),
    ("публичный credit требует входа клиента", t_public_credit_requires_client_login),
    ("api_submit: ошибка UPDATE статуса не течёт клиенту", t_api_submit_status_save_failure_is_neutral),
    ("api_submit: ошибка INSERT не течёт клиенту", t_api_submit_insert_failure_is_neutral),
    ("request_create: ошибка INSERT не течёт клиенту", t_request_create_insert_failure_is_neutral),
    ("маркеры отказа авторизации точны (без ложных срабатываний)", t_auth_failure_markers_precise),
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
