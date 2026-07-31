#!/usr/bin/env python3
"""Тесты слоя настроек кредитных провайдеров (models/credite_settings.py).

Часть тестов работает на подставном бэкенде (без БД), часть — живые,
против ADB и Biro26; живые пропускаются, если БД недоступна.

Usage: ./venv/bin/python test_credite_settings.py
"""
from __future__ import annotations

import sys
from typing import Any, Dict, List

from models.credite_settings import (PROVIDER_DEFS, CrediteBackend, CrediteSettings,
                                     CrediteBackendError)


class FakeBackend(CrediteBackend):
    """Бэкенд в памяти: имитирует TMS_CREDITE_PROVIDER(_PARAM)."""

    id = "fake"

    def __init__(self) -> None:
        self.providers: List[Dict[str, Any]] = []
        self.params: List[Dict[str, Any]] = []
        self._next = 1

    def query(self, sql: str, params: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
        p = params or {}
        s = " ".join(sql.split()).upper()
        if "FROM TMS_CREDITE_PROVIDER_PARAM" in s:
            return [dict(r) for r in self.params if r["provider_id"] == p.get("p")]
        if "FROM TMS_CREDITE_PROVIDER" in s:
            rows = self.providers
            if ":C" in s:
                rows = [r for r in rows if r["code"] == p.get("c")]
            return [dict(r) for r in rows]
        raise AssertionError(f"неожиданный SQL: {sql}")

    def dml(self, sql: str, params: Dict[str, Any] | None = None) -> None:
        p = params or {}
        s = " ".join(sql.split()).upper()
        if s.startswith("INSERT INTO TMS_CREDITE_PROVIDER_PARAM"):
            self.params.append({"provider_id": p["p"], "param_name": p["n"],
                                "param_value": p["v"], "is_secret": p["s"]})
        elif s.startswith("INSERT INTO TMS_CREDITE_PROVIDER"):
            self.providers.append({"id": self._next, "code": p["c"], "name": p["n"],
                                   "enabled": p.get("en", "0"), "env": p.get("e", "sandbox"),
                                   "base_url": p.get("b"), "icon": p.get("i"),
                                   "color": p.get("col"), "ord": p.get("o", 0)})
            self._next += 1
        elif s.startswith("UPDATE TMS_CREDITE_PROVIDER_PARAM"):
            for r in self.params:
                if r["provider_id"] == p["p"] and r["param_name"] == p["n"]:
                    r["param_value"] = p["v"]
        elif s.startswith("UPDATE TMS_CREDITE_PROVIDER"):
            for r in self.providers:
                if r["code"] == p["c"]:
                    r.update({"enabled": p["en"], "env": p["e"], "base_url": p["b"]})
        else:
            raise AssertionError(f"неожиданный DML: {sql}")


class DeadBackend(CrediteBackend):
    """Бэкенд, имитирующий недоступную БД."""

    id = "dead"

    def query(self, sql, params=None):
        raise CrediteBackendError("ORA-12541: TNS:no listener")

    def dml(self, sql, params=None):
        raise CrediteBackendError("ORA-12541: TNS:no listener")


def t_save_and_get() -> List[str]:
    """save() создаёт строку, get() возвращает её с параметрами."""
    fails = []
    st = CrediteSettings(FakeBackend())
    st.save("easycredit", enabled=True, env="sandbox",
            base_url="https://tst.ecmoldova.cloud:8082",
            params={"api_user": "u1", "api_password": "p1"})
    d = st.get("easycredit")
    if d is None:
        return ["get() вернул None после save()"]
    if d["enabled"] is not True:
        fails.append(f"enabled={d['enabled']!r}, ожидалось True")
    if d["env"] != "sandbox":
        fails.append(f"env={d['env']!r}")
    if d["params"].get("api_user") != "u1":
        fails.append(f"api_user={d['params'].get('api_user')!r}")
    if d["params"].get("api_password") != "p1":
        fails.append(f"api_password={d['params'].get('api_password')!r}")
    return fails


def t_empty_secret_keeps_previous() -> List[str]:
    """Пустое значение секретного параметра не затирает сохранённое."""
    st = CrediteSettings(FakeBackend())
    st.save("easycredit", enabled=True, env="sandbox", base_url="https://a",
            params={"api_user": "u1", "api_password": "secret"})
    st.save("easycredit", enabled=True, env="production", base_url="https://b",
            params={"api_user": "u2", "api_password": ""})
    d = st.get("easycredit")
    fails = []
    if d["params"].get("api_password") != "secret":
        fails.append(f"пароль затёрт: {d['params'].get('api_password')!r}")
    if d["params"].get("api_user") != "u2":
        fails.append(f"несекретный параметр не обновился: {d['params'].get('api_user')!r}")
    if d["env"] != "production":
        fails.append(f"env не обновился: {d['env']!r}")
    return fails


def t_masked_hides_secrets() -> List[str]:
    """masked() отдаёт секреты маской, несекретные — как есть."""
    st = CrediteSettings(FakeBackend())
    st.save("easycredit", enabled=True, env="sandbox", base_url="https://a",
            params={"api_user": "operator", "api_password": "sup3rsecret"})
    m = st.masked("easycredit")
    fails = []
    if m["params"]["api_password"] == "sup3rsecret":
        fails.append("пароль отдан в открытом виде")
    if not m["params"]["api_password"].endswith("***"):
        fails.append(f"маска пароля: {m['params']['api_password']!r}")
    if m["params"]["api_user"] != "operator":
        fails.append(f"несекретный параметр замаскирован: {m['params']['api_user']!r}")
    if m.get("has_secret", {}).get("api_password") is not True:
        fails.append("has_secret['api_password'] должен быть True при заданном пароле")
    return fails


def t_dead_backend_returns_none() -> List[str]:
    """Недоступная БД → get() отдаёт None, а не исключение (фолбэк на .env)."""
    st = CrediteSettings(DeadBackend())
    try:
        d = st.get("easycredit")
    except Exception as e:
        return [f"get() бросил исключение вместо None: {e}"]
    return [] if d is None else [f"ожидался None, получено {d!r}"]


def t_provider_defs() -> List[str]:
    """PROVIDER_DEFS описывает оба провайдера с нужными параметрами."""
    fails = []
    for code, need in (("easycredit", {"api_user", "api_password"}),
                       ("iute", {"api_key", "pos_identifier", "salesman_identifier"})):
        spec = PROVIDER_DEFS.get(code)
        if not spec:
            fails.append(f"нет описания провайдера {code}")
            continue
        names = {n for n, _ in spec["params"]}
        if names != need:
            fails.append(f"{code}: параметры {names}, ожидались {need}")
        secrets = {n for n, s in spec["params"] if s}
        expected_secret = {"api_password"} if code == "easycredit" else {"api_key"}
        if secrets != expected_secret:
            fails.append(f"{code}: секретные {secrets}, ожидались {expected_secret}")
    return fails


def t_live_roundtrip() -> List[str]:
    """Живой roundtrip против обеих БД (пропускается, если БД недоступна)."""
    from models.credite_settings import adb_settings, biro26_settings
    fails = []
    for label, factory in (("adb", adb_settings), ("biro26", biro26_settings)):
        st = factory()
        d = st.get("easycredit")
        if d is None:
            print(f"  [skip] {label}: БД недоступна или TMS_CREDITE_PROVIDER пуста")
            continue
        if d["code"] != "easycredit":
            fails.append(f"{label}: code={d['code']!r}")
        if "params" not in d:
            fails.append(f"{label}: нет ключа params")
        print(f"  [live] {label}: enabled={d['enabled']} env={d['env']}")
    return fails


def t_config_reads_oracle() -> List[str]:
    """Config.easycredit_* берёт значения из Oracle, если провайдер там есть."""
    from config import Config
    from models.credite_settings import adb_settings

    st = adb_settings()
    d = st.get("easycredit")
    if d is None:
        print("  [skip] TMS_CREDITE_PROVIDER недоступна")
        return []
    fails = []
    if d["params"].get("api_user") and Config.easycredit_api_user() != d["params"]["api_user"]:
        fails.append(f"api_user: Config={Config.easycredit_api_user()!r}, "
                     f"Oracle={d['params']['api_user']!r}")
    if Config.easycredit_env() != d["env"]:
        fails.append(f"env: Config={Config.easycredit_env()!r}, Oracle={d['env']!r}")
    if Config.easycredit_base_url() != d["base_url"]:
        fails.append(f"base_url: Config={Config.easycredit_base_url()!r}, "
                     f"Oracle={d['base_url']!r}")
    return fails


def t_provider_settings_source() -> List[str]:
    """Провайдер, созданный с settings_source, читает настройки оттуда, а не из Config."""
    from integrations import build_registry
    from models.credite_settings import CrediteSettings

    st = CrediteSettings(FakeBackend())
    st.save("easycredit", enabled=True, env="production",
            base_url="https://fake-ec.example",
            params={"api_user": "fake_user", "api_password": "fake_pass"})
    st.save("iute", enabled=True, env="sandbox", base_url="https://fake-iute.example",
            params={"api_key": "fake_key", "pos_identifier": "POS1",
                    "salesman_identifier": "S1"})

    reg = build_registry(st)
    fails = []
    ec = reg.get("easycredit")
    if ec is None:
        return ["build_registry не зарегистрировал easycredit"]
    if ec._base_url() != "https://fake-ec.example":
        fails.append(f"base_url={ec._base_url()!r}")
    if ec._user() != "fake_user":
        fails.append(f"user={ec._user()!r}")
    if ec._password() != "fake_pass":
        fails.append(f"password={ec._password()!r}")
    if not ec.is_configured():
        fails.append("is_configured() = False при заполненных кредах")
    if ec.get_settings().get("user") == "fake_user":
        fails.append("get_settings() отдаёт логин без маски")

    iu = reg.get("iute")
    if iu is None:
        return fails + ["build_registry не зарегистрировал iute"]
    if iu._api_key() != "fake_key":
        fails.append(f"iute api_key={iu._api_key()!r}")
    if iu._pos_identifier() != "POS1":
        fails.append(f"iute pos={iu._pos_identifier()!r}")

    from integrations import registry as global_reg
    if global_reg.get("easycredit") is ec:
        fails.append("build_registry вернул глобальный singleton вместо нового реестра")
    return fails


def t_source_is_authoritative() -> List[str]:
    """Источник настроек авторитетен: пустые креды в нём НЕ подменяются значениями из Config."""
    from integrations import build_registry
    from models.credite_settings import CrediteSettings

    st = CrediteSettings(FakeBackend())
    st.save("easycredit", enabled=True, env="sandbox",
            base_url="https://only-here.example", params={"api_user": "", "api_password": ""})
    ec = build_registry(st).get("easycredit")
    fails = []
    if ec._user():
        fails.append(f"api_user подхвачен из Config: {ec._user()!r}")
    if ec._password():
        fails.append(f"api_password подхвачен из Config: {ec._password()!r}")
    if ec.is_configured():
        fails.append("is_configured() = True при пустых кредах в источнике")
    if ec._base_url() != "https://only-here.example":
        fails.append(f"base_url={ec._base_url()!r}, ожидался из источника")

    from integrations.easycredit_provider import EasyCreditProvider
    from config import Config
    plain = EasyCreditProvider()
    if plain._user() != Config.easycredit_api_user():
        fails.append("провайдер без источника перестал читать Config")
    return fails


def t_config_oracle_authoritative_even_if_empty() -> List[str]:
    """Finding 4: config._oracle() авторитетен, если запись есть — пустой
    пароль в Oracle НЕ подменяется значением из .env (по умолчанию 'demo'
    для EasyCredit); а если записи нет вовсе (_oracle вернул {}), фолбэк на
    .env по-прежнему работает."""
    import config as cfg

    fails = []
    orig_oracle = cfg._oracle

    # 1) запись есть, пароль намеренно пуст -> Config должен вернуть "", не "demo"
    cfg._oracle = lambda code: (
        {"env": "sandbox", "base_url": "https://tst.ecmoldova.cloud:8082",
         "api_user": "operator", "api_password": ""}
        if code == "easycredit" else {})
    try:
        pw = cfg.Config.easycredit_api_password()
        user = cfg.Config.easycredit_api_user()
    finally:
        cfg._oracle = orig_oracle
    if pw != "":
        fails.append(f"easycredit_api_password()={pw!r}, ожидалась '' "
                     f"(запись в Oracle есть, пароль в ней пуст)")
    if pw == "demo":
        fails.append("пустой пароль в Oracle подменён дефолтом .env ('demo')")
    if user != "operator":
        fails.append(f"easycredit_api_user()={user!r}, ожидался 'operator' из Oracle")

    # 2) записи нет вовсе (_oracle -> {}) -> фолбэк на .env по-прежнему работает
    cfg._oracle = lambda code: {}
    try:
        pw2 = cfg.Config.easycredit_api_password()
    finally:
        cfg._oracle = orig_oracle
    if pw2 != cfg.Config.EASYCREDIT_API_PASSWORD:
        fails.append(f"без записи в Oracle фолбэк на .env не сработал: "
                     f"{pw2!r} != {cfg.Config.EASYCREDIT_API_PASSWORD!r}")
    return fails


TESTS = [
    ("save + get", t_save_and_get),
    ("пустой секрет не затирает", t_empty_secret_keeps_previous),
    ("masked() скрывает секреты", t_masked_hides_secrets),
    ("недоступная БД -> None", t_dead_backend_returns_none),
    ("PROVIDER_DEFS", t_provider_defs),
    ("живой roundtrip", t_live_roundtrip),
    ("Config читает Oracle", t_config_reads_oracle),
    ("provider settings_source", t_provider_settings_source),
    ("источник авторитетен (нет утечки в Config)", t_source_is_authoritative),
    ("config._oracle авторитетен даже при пустом значении", t_config_oracle_authoritative_even_if_empty),
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
