# Biro26 × EasyCredit/Iute Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Перенести библиотеку кредитных провайдеров (EasyCredit SOAP, Iute REST) в бэк-офис Biro26, хранить настройки в Oracle-таблицах `TMS_CREDITE_*` в обеих БД, и дать клиенту витрины Biro26 полный флоу кредитной заявки (preapproved → submit → status).

**Architecture:** Новый слой `models/credite_settings.py` читает/пишет настройки провайдеров в `TMS_CREDITE_PROVIDER(_PARAM)` через один из двух бэкендов — `AdbBackend` (Oracle ADB основного проекта) или `Biro26Backend` (Oracle 11g OfficePlus через subprocess worker). Существующие `CreditProvider`-реализации получают опциональный `settings_source`, что позволяет инстанцировать один и тот же `EasyCreditProvider` с настройками любого контура. `models/biro26_credit.py` переезжает на `TMS_CREDITE_*` и получает методы `api_preapproved` / `api_submit` / `api_status`, каждый вызов логируется в append-only `TMS_CREDITE_REQ_EVENT`.

**Tech Stack:** Python 3.12, Flask, python-oracledb (thin + wallet для ADB; thick через subprocess worker для 11g), flask_limiter, ванильный JS в self-contained Jinja-шаблонах.

**Spec:** [docs/superpowers/specs/2026-07-31-biro26-easycredit-design.md](../specs/2026-07-31-biro26-easycredit-design.md)

## Global Constraints

- Production-инвариант: `https://nufarul.eminescu.md/` не должен ломаться. После любых изменений remote-контура — `curl -I https://nufarul.eminescu.md/login` → `HTTP/2 200`.
- Oracle-first, normalized-first. Никаких JSON blob и generic KV для primary state. `data/*.json` после миграции — только одноразовый seed.
- Префикс всех новых объектов: `TMS_CREDITE_`.
- DDL совместим одновременно с Oracle 11g и ADB: никаких identity-колонок, только `SEQUENCE` + `BEFORE INSERT` триггер.
- Biro26/OfficePlus — charset `CL8MSWIN1251`. Кириллицу писать в 11g **только** через python-oracledb (`Biro26DB`), никогда через SQLcl/sqlplus.
- `YBIRO_CREDIT_ORG`, `YBIRO_CREDIT_PLAN`, `YBIRO_CREDIT_REQ` после миграции переименовываются в `*_OLD`. **Ничего не дропать.**
- Формула расчёта рассрочки не меняется (см. `Biro26Credit.calc`).
- Полный IDNP клиента в БД не хранится — только `IDNP_MASKED` вида `20*******01`.
- Тексты интерфейса — RO/RU, как в остальном модуле Biro26.
- Локальный запуск тестов: `./venv/bin/python <файл>.py`. Тесты в проекте — самостоятельные скрипты с `main() -> int`, а не pytest.
- Питон-интерпретатор: `./venv/bin/python` (локально), `/home/ubuntu/artgranit/venv/bin/python` (remote).

---

## File Structure

**Создаются:**

| Файл | Ответственность |
|---|---|
| `sql/50_credite_tables.sql` | DDL `TMS_CREDITE_*` для ADB (в порядок `deploy_oracle_objects.py`) |
| `sql/biro26/12_tms_credite.sql` | Тот же DDL для 11g (номера 10, 11 заняты) |
| `deploy_credite_oracle.py` | Идемпотентный деплой DDL + миграция + seed, `--target adb\|biro26\|both` |
| `models/credite_settings.py` | Бэкенды БД + `CrediteSettings` (CRUD настроек провайдеров) |
| `test_credite_settings.py` | Тесты слоя настроек |

**Модифицируются:**

| Файл | Что меняется |
|---|---|
| `app.py:863-885` | Фикс путей документации `/docs/easycredit`, `/docs/iute` |
| `app.py` (блок ~6161-6210) | Новые роуты провайдеров и публичного API кредитного флоу |
| `config.py` | `Config.easycredit_*` / `iute_*` читают из Oracle; `save_*` пишут в Oracle |
| `integrations/base_provider.py` | `settings_source` в `CreditProvider`; `ProviderRegistry` перестаёт быть singleton |
| `integrations/easycredit_provider.py` | Чтение настроек через `settings_source` с фолбэком на `Config` |
| `integrations/iute_provider.py` | То же |
| `integrations/__init__.py` | `build_registry(settings_source)` |
| `models/biro26_credit.py` | Переход на `TMS_CREDITE_*`; `api_preapproved` / `api_submit` / `api_status`; лог событий |
| `controllers/biro26_controller.py` | Контроллерные обёртки новых операций |
| `templates/biro26/credit_admin.html` | Вкладка «Provideri API»; селект провайдера в организации; API-колонки в заявках |
| `templates/biro26/site_cart.html` | Полный кредитный флоу в корзине |
| `templates/biro26/shop.html` | Тот же флоу в модалке товара |
| `docs/CREDITE/project_easycredit.html` | Переписывается |
| `docs/CREDITE/project_iute.html` | Раздел настроек |
| `README.md`, `docs/Biro26/README_BIRO26.html` | Ссылки и описание модуля |
| `test_biro26_smoke.py` | Проверка `TMS_CREDITE_*` |

---

## Task 1: Фикс роутов документации

Самостоятельная задача — чинит 404 на двух живых страницах, ни от чего не зависит.

**Files:**
- Modify: `app.py:863-885`

**Interfaces:**
- Consumes: ничего
- Produces: ничего (изолированный фикс)

- [ ] **Step 1: Убедиться, что баг воспроизводится**

```bash
cd /Users/pt/Projects.AI/Artgranit
ls docs/project_easycredit.html docs/project_iute.html 2>&1
ls docs/CREDITE/project_easycredit.html docs/CREDITE/project_iute.html
```

Ожидается: первая команда — `No such file or directory` для обоих; вторая — оба файла существуют. Это и есть причина 404.

- [ ] **Step 2: Исправить пути**

В `app.py` в функции `docs_easycredit()` заменить строку:

```python
    p = Path(__file__).parent / "docs" / "project_easycredit.html"
```

на:

```python
    p = Path(__file__).parent / "docs" / "CREDITE" / "project_easycredit.html"
```

В функции `docs_iute()` заменить строку:

```python
    p = Path(__file__).parent / "docs" / "project_iute.html"
```

на:

```python
    p = Path(__file__).parent / "docs" / "CREDITE" / "project_iute.html"
```

- [ ] **Step 3: Проверить, что файлы теперь находятся**

```bash
cd /Users/pt/Projects.AI/Artgranit
./venv/bin/python -c "
from pathlib import Path
for n in ('project_easycredit.html', 'project_iute.html'):
    p = Path('.') / 'docs' / 'CREDITE' / n
    print(n, p.exists(), p.stat().st_size)
"
```

Ожидается: `project_easycredit.html True <размер>` и `project_iute.html True <размер>`, оба размера > 0.

- [ ] **Step 4: Проверить синтаксис app.py**

```bash
cd /Users/pt/Projects.AI/Artgranit && ./venv/bin/python -c "import ast,sys; ast.parse(open('app.py',encoding='utf-8').read()); print('OK')"
```

Ожидается: `OK`

- [ ] **Step 5: Commit**

```bash
cd /Users/pt/Projects.AI/Artgranit
git add app.py
git commit -m "fix(docs): роуты /docs/easycredit и /docs/iute указывали на несуществующие пути

Файлы лежат в docs/CREDITE/, обе страницы отдавали 404.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 2: DDL `TMS_CREDITE_*` и скрипт деплоя

**Files:**
- Create: `sql/50_credite_tables.sql`
- Create: `sql/biro26/12_tms_credite.sql`
- Create: `deploy_credite_oracle.py`
- Modify: `deploy_oracle_objects.py` (добавить файл в порядок выполнения)

**Interfaces:**
- Consumes: `models.database.DatabaseModel`, `models.biro26_db.Biro26DB`
- Produces: таблицы `TMS_CREDITE_PROVIDER`, `TMS_CREDITE_PROVIDER_PARAM`, `TMS_CREDITE_ORG`, `TMS_CREDITE_PLAN`, `TMS_CREDITE_REQ`, `TMS_CREDITE_REQ_EVENT` в обеих БД; CLI `python deploy_credite_oracle.py --target adb|biro26|both`

- [ ] **Step 1: Написать DDL**

Создать `sql/50_credite_tables.sql`:

```sql
-- =====================================================================
-- RO/RU: TMS_CREDITE_* — creditare: provideri API (EasyCredit, Iute),
--        organizatii, pachete, cereri si jurnalul apelurilor API.
-- Acelasi DDL se aplica in AMBELE baze: Oracle ADB (proiectul principal)
-- si Oracle 11g (OfficePlus/Biro26). Fara identity — secventa + trigger.
-- Migrare din YBIRO_CREDIT_* — vezi deploy_credite_oracle.py.
-- =====================================================================

CREATE TABLE TMS_CREDITE_PROVIDER (
  ID        NUMBER NOT NULL,
  CODE      VARCHAR2(30)  NOT NULL,
  NAME      VARCHAR2(100) NOT NULL,
  ENABLED   VARCHAR2(1)   DEFAULT '0',
  ENV       VARCHAR2(20)  DEFAULT 'sandbox',
  BASE_URL  VARCHAR2(400),
  ICON      VARCHAR2(20),
  COLOR     VARCHAR2(20),
  INFO      VARCHAR2(2000),
  ORD       NUMBER DEFAULT 0,
  UPDATED   DATE DEFAULT SYSDATE,
  CONSTRAINT PK_TMS_CREDITE_PROVIDER PRIMARY KEY (ID),
  CONSTRAINT UQ_TMS_CREDITE_PROV_CODE UNIQUE (CODE)
);
CREATE SEQUENCE TMS_CREDITE_PROVIDER_SEQ START WITH 1 NOCACHE;
CREATE OR REPLACE TRIGGER TMS_CREDITE_PROVIDER_BI
  BEFORE INSERT ON TMS_CREDITE_PROVIDER FOR EACH ROW WHEN (NEW.ID IS NULL)
BEGIN SELECT TMS_CREDITE_PROVIDER_SEQ.NEXTVAL INTO :NEW.ID FROM dual; END;
/

CREATE TABLE TMS_CREDITE_PROVIDER_PARAM (
  PROVIDER_ID NUMBER       NOT NULL,
  PARAM_NAME  VARCHAR2(40) NOT NULL,
  PARAM_VALUE VARCHAR2(400),
  IS_SECRET   VARCHAR2(1) DEFAULT '0',
  CONSTRAINT PK_TMS_CREDITE_PRV_PARAM PRIMARY KEY (PROVIDER_ID, PARAM_NAME),
  CONSTRAINT FK_TMS_CREDITE_PRV_PARAM FOREIGN KEY (PROVIDER_ID)
    REFERENCES TMS_CREDITE_PROVIDER (ID)
);

CREATE TABLE TMS_CREDITE_ORG (
  ID          NUMBER NOT NULL,
  NAME        VARCHAR2(100) NOT NULL,
  ENABLED     VARCHAR2(1) DEFAULT '1',
  ORG_MODE    VARCHAR2(10) DEFAULT 'manual',
  PROVIDER_ID NUMBER,
  API_URL     VARCHAR2(400),
  LOGO_URL    VARCHAR2(400),
  INFO        VARCHAR2(2000),
  ORD         NUMBER DEFAULT 0,
  CONSTRAINT PK_TMS_CREDITE_ORG PRIMARY KEY (ID),
  CONSTRAINT FK_TMS_CREDITE_ORG_PRV FOREIGN KEY (PROVIDER_ID)
    REFERENCES TMS_CREDITE_PROVIDER (ID)
);
CREATE SEQUENCE TMS_CREDITE_ORG_SEQ START WITH 1 NOCACHE;
CREATE OR REPLACE TRIGGER TMS_CREDITE_ORG_BI
  BEFORE INSERT ON TMS_CREDITE_ORG FOR EACH ROW WHEN (NEW.ID IS NULL)
BEGIN SELECT TMS_CREDITE_ORG_SEQ.NEXTVAL INTO :NEW.ID FROM dual; END;
/

CREATE TABLE TMS_CREDITE_PLAN (
  ID              NUMBER NOT NULL,
  ORG_ID          NUMBER NOT NULL,
  NAME            VARCHAR2(120) NOT NULL,
  MONTHS_MIN      NUMBER NOT NULL,
  MONTHS_MAX      NUMBER NOT NULL,
  AMOUNT_MIN      NUMBER DEFAULT 1000,
  AMOUNT_MAX      NUMBER DEFAULT 100000,
  MARKUP_PCT      NUMBER DEFAULT 0,
  ANNUAL_PCT      NUMBER DEFAULT 0,
  MONTHLY_FEE_PCT NUMBER DEFAULT 0,
  ISSUE_FEE       NUMBER DEFAULT 0,
  AVANS_MIN_PCT   NUMBER DEFAULT 0,
  ENABLED         VARCHAR2(1) DEFAULT '1',
  INFO            VARCHAR2(2000),
  CONSTRAINT PK_TMS_CREDITE_PLAN PRIMARY KEY (ID),
  CONSTRAINT FK_TMS_CREDITE_PLAN_ORG FOREIGN KEY (ORG_ID)
    REFERENCES TMS_CREDITE_ORG (ID)
);
CREATE SEQUENCE TMS_CREDITE_PLAN_SEQ START WITH 1 NOCACHE;
CREATE INDEX IX_TMS_CREDITE_PLAN_ORG ON TMS_CREDITE_PLAN (ORG_ID);
CREATE OR REPLACE TRIGGER TMS_CREDITE_PLAN_BI
  BEFORE INSERT ON TMS_CREDITE_PLAN FOR EACH ROW WHEN (NEW.ID IS NULL)
BEGIN SELECT TMS_CREDITE_PLAN_SEQ.NEXTVAL INTO :NEW.ID FROM dual; END;
/

CREATE TABLE TMS_CREDITE_REQ (
  ID                 NUMBER NOT NULL,
  ORG_ID             NUMBER,
  PLAN_ID            NUMBER,
  MONTHS             NUMBER,
  PRODUCT_COD        NUMBER,
  PRODUCT_NAME       VARCHAR2(300),
  QTY                NUMBER DEFAULT 1,
  AMOUNT             NUMBER,
  CREDIT_PRICE       NUMBER,
  MONTHLY            NUMBER,
  CLIENT_NAME        VARCHAR2(200),
  PHONE              VARCHAR2(40),
  STATUS             VARCHAR2(20) DEFAULT 'NEW',
  PROVIDER_CODE      VARCHAR2(30),
  EXT_REF            VARCHAR2(120),
  API_STATUS         VARCHAR2(60),
  PREAPPROVED_AMOUNT NUMBER,
  IDNP_MASKED        VARCHAR2(20),
  LAST_CHECK         DATE,
  CREATED            DATE DEFAULT SYSDATE,
  CONSTRAINT PK_TMS_CREDITE_REQ PRIMARY KEY (ID)
);
CREATE SEQUENCE TMS_CREDITE_REQ_SEQ START WITH 1 NOCACHE;
CREATE INDEX IX_TMS_CREDITE_REQ_EXT ON TMS_CREDITE_REQ (EXT_REF);
CREATE OR REPLACE TRIGGER TMS_CREDITE_REQ_BI
  BEFORE INSERT ON TMS_CREDITE_REQ FOR EACH ROW WHEN (NEW.ID IS NULL)
BEGIN SELECT TMS_CREDITE_REQ_SEQ.NEXTVAL INTO :NEW.ID FROM dual; END;
/

CREATE TABLE TMS_CREDITE_REQ_EVENT (
  ID            NUMBER NOT NULL,
  REQ_ID        NUMBER,
  PROVIDER_CODE VARCHAR2(30),
  OP            VARCHAR2(30),
  HTTP_CODE     NUMBER,
  DURATION_MS   NUMBER,
  PAYLOAD       CLOB,
  RESULT        CLOB,
  IS_ERROR      VARCHAR2(1) DEFAULT '0',
  CREATED       DATE DEFAULT SYSDATE,
  CONSTRAINT PK_TMS_CREDITE_REQ_EVENT PRIMARY KEY (ID)
);
CREATE SEQUENCE TMS_CREDITE_REQ_EVENT_SEQ START WITH 1 NOCACHE;
CREATE INDEX IX_TMS_CREDITE_EVT_REQ ON TMS_CREDITE_REQ_EVENT (REQ_ID);
CREATE OR REPLACE TRIGGER TMS_CREDITE_REQ_EVENT_BI
  BEFORE INSERT ON TMS_CREDITE_REQ_EVENT FOR EACH ROW WHEN (NEW.ID IS NULL)
BEGIN SELECT TMS_CREDITE_REQ_EVENT_SEQ.NEXTVAL INTO :NEW.ID FROM dual; END;
/
```

- [ ] **Step 2: Продублировать DDL для 11g**

```bash
cd /Users/pt/Projects.AI/Artgranit
cp sql/50_credite_tables.sql sql/biro26/12_tms_credite.sql
```

Файл идентичен — DDL намеренно написан на пересечении диалектов 11g и ADB. Дописать первой строкой в `sql/biro26/12_tms_credite.sql`:

```sql
-- Copie a sql/50_credite_tables.sql pentru OfficePlus (Oracle 11g).
```

- [ ] **Step 3: Написать скрипт деплоя**

Создать `deploy_credite_oracle.py`:

```python
#!/usr/bin/env python3
"""Deploy TMS_CREDITE_* to both Oracle databases (idempotent).

ADB    — main project (thin mode + wallet), models/database.py
Biro26 — OfficePlus Oracle 11g (thick subprocess worker), models/biro26_db.py

Steps per target:
  1. create tables/sequences/triggers that do not exist yet
  2. migrate data from YBIRO_CREDIT_* (if present and not migrated yet)
  3. seed TMS_CREDITE_PROVIDER from data/*.json + .env (if empty)
  4. rename YBIRO_CREDIT_* -> *_OLD

Usage: ./venv/bin/python deploy_credite_oracle.py --target both
"""
from __future__ import annotations

import argparse
import sys
from typing import Any, Dict, List

from models.credite_settings import AdbBackend, Biro26Backend, CrediteBackend, PROVIDER_DEFS

TABLES = ["TMS_CREDITE_PROVIDER", "TMS_CREDITE_PROVIDER_PARAM", "TMS_CREDITE_ORG",
          "TMS_CREDITE_PLAN", "TMS_CREDITE_REQ", "TMS_CREDITE_REQ_EVENT"]

DDL_PATH = {"adb": "sql/50_credite_tables.sql", "biro26": "sql/biro26/12_tms_credite.sql"}


def _split_ddl(text: str) -> List[str]:
    """Split the DDL file into statements.

    PL/SQL trigger bodies are terminated by a lone '/' line; plain DDL by ';'.
    """
    out, buf, in_plsql = [], [], False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("--") and not buf:
            continue
        if s == "/":
            if buf:
                out.append("\n".join(buf).strip())
                buf, in_plsql = [], False
            continue
        if s.upper().startswith("CREATE OR REPLACE TRIGGER"):
            in_plsql = True
        buf.append(line)
        if not in_plsql and s.endswith(";"):
            stmt = "\n".join(buf).strip().rstrip(";").strip()
            if stmt:
                out.append(stmt)
            buf = []
    if buf and "\n".join(buf).strip():
        out.append("\n".join(buf).strip().rstrip(";").strip())
    return [s for s in out if s]


def _exists(be: CrediteBackend, name: str) -> bool:
    rows = be.query("SELECT COUNT(*) CNT FROM USER_OBJECTS WHERE OBJECT_NAME = :n",
                    {"n": name.upper()})
    return bool(rows) and int(rows[0]["cnt"]) > 0


def create_objects(be: CrediteBackend, ddl_file: str) -> int:
    with open(ddl_file, encoding="utf-8") as f:
        stmts = _split_ddl(f.read())
    created = 0
    for stmt in stmts:
        head = " ".join(stmt.split()[:4]).upper()
        try:
            be.dml(stmt)
            created += 1
            print(f"  + {head}")
        except Exception as e:
            msg = str(e)
            # ORA-00955 name already used, ORA-02260/01408 index/constraint exists
            if "ORA-00955" in msg or "ORA-01408" in msg or "ORA-02275" in msg:
                print(f"  = {head} (уже есть)")
            else:
                print(f"  ! {head}: {msg[:200]}")
                raise
    return created


def migrate_legacy(be: CrediteBackend) -> None:
    """Copy YBIRO_CREDIT_* into TMS_CREDITE_* preserving IDs. Idempotent."""
    if not _exists(be, "YBIRO_CREDIT_ORG"):
        print("  = YBIRO_CREDIT_ORG отсутствует — миграция не нужна")
        return
    n = be.query("SELECT COUNT(*) CNT FROM TMS_CREDITE_ORG")[0]["cnt"]
    if int(n) > 0:
        print("  = TMS_CREDITE_ORG уже заполнена — миграция пропущена")
        return
    be.dml("INSERT INTO TMS_CREDITE_ORG (ID, NAME, ENABLED, ORG_MODE, API_URL, "
           "LOGO_URL, INFO, ORD) SELECT ID, NAME, ENABLED, ORG_MODE, API_URL, "
           "LOGO_URL, INFO, ORD FROM YBIRO_CREDIT_ORG")
    be.dml("INSERT INTO TMS_CREDITE_PLAN (ID, ORG_ID, NAME, MONTHS_MIN, MONTHS_MAX, "
           "AMOUNT_MIN, AMOUNT_MAX, MARKUP_PCT, ANNUAL_PCT, MONTHLY_FEE_PCT, "
           "ISSUE_FEE, AVANS_MIN_PCT, ENABLED, INFO) SELECT ID, ORG_ID, NAME, "
           "MONTHS_MIN, MONTHS_MAX, AMOUNT_MIN, AMOUNT_MAX, MARKUP_PCT, ANNUAL_PCT, "
           "MONTHLY_FEE_PCT, ISSUE_FEE, AVANS_MIN_PCT, ENABLED, INFO "
           "FROM YBIRO_CREDIT_PLAN")
    if _exists(be, "YBIRO_CREDIT_REQ"):
        be.dml("INSERT INTO TMS_CREDITE_REQ (ID, ORG_ID, PLAN_ID, MONTHS, PRODUCT_COD, "
               "PRODUCT_NAME, QTY, AMOUNT, CREDIT_PRICE, MONTHLY, CLIENT_NAME, PHONE, "
               "STATUS, CREATED) SELECT ID, ORG_ID, PLAN_ID, MONTHS, PRODUCT_COD, "
               "PRODUCT_NAME, QTY, AMOUNT, CREDIT_PRICE, MONTHLY, CLIENT_NAME, PHONE, "
               "STATUS, CREATED FROM YBIRO_CREDIT_REQ")
    for tab in ("ORG", "PLAN", "REQ"):
        rows = be.query(f"SELECT NVL(MAX(ID), 0) + 1 NX FROM TMS_CREDITE_{tab}")
        nxt = int(rows[0]["nx"])
        be.dml(f"DROP SEQUENCE TMS_CREDITE_{tab}_SEQ")
        be.dml(f"CREATE SEQUENCE TMS_CREDITE_{tab}_SEQ START WITH {nxt} NOCACHE")
        print(f"  ~ TMS_CREDITE_{tab}_SEQ -> START WITH {nxt}")
    print("  + данные перенесены из YBIRO_CREDIT_*")


def rename_legacy(be: CrediteBackend) -> None:
    for tab in ("YBIRO_CREDIT_ORG", "YBIRO_CREDIT_PLAN", "YBIRO_CREDIT_REQ"):
        if _exists(be, tab) and not _exists(be, tab + "_OLD"):
            be.dml(f"RENAME {tab} TO {tab}_OLD")
            print(f"  ~ {tab} -> {tab}_OLD")


def seed_providers(be: CrediteBackend) -> None:
    """Seed TMS_CREDITE_PROVIDER from data/*.json + .env — once."""
    from config import Config, _load_easycredit_overrides, _load_iute_overrides

    src = {
        "easycredit": {
            "over": _load_easycredit_overrides(),
            "env": Config.easycredit_env(),
            "base_url": Config.easycredit_base_url(),
            "params": {"api_user": Config.easycredit_api_user(),
                       "api_password": Config.easycredit_api_password()},
        },
        "iute": {
            "over": _load_iute_overrides(),
            "env": Config.iute_env(),
            "base_url": Config.iute_base_url(),
            "params": {"api_key": Config.iute_api_key(),
                       "pos_identifier": Config.iute_pos_identifier(),
                       "salesman_identifier": Config.iute_salesman_identifier()},
        },
    }
    for code, spec in PROVIDER_DEFS.items():
        rows = be.query("SELECT ID FROM TMS_CREDITE_PROVIDER WHERE CODE = :c", {"c": code})
        if rows:
            print(f"  = провайдер {code} уже есть")
            continue
        s = src[code]
        be.dml("INSERT INTO TMS_CREDITE_PROVIDER (CODE, NAME, ENABLED, ENV, BASE_URL, "
               "ICON, COLOR, ORD) VALUES (:c, :n, '0', :e, :b, :i, :col, :o)",
               {"c": code, "n": spec["name"], "e": s["env"], "b": s["base_url"],
                "i": spec["icon"], "col": spec["color"], "o": spec["ord"]})
        pid = int(be.query("SELECT ID FROM TMS_CREDITE_PROVIDER WHERE CODE = :c",
                           {"c": code})[0]["id"])
        for pname, secret in spec["params"]:
            be.dml("INSERT INTO TMS_CREDITE_PROVIDER_PARAM (PROVIDER_ID, PARAM_NAME, "
                   "PARAM_VALUE, IS_SECRET) VALUES (:p, :n, :v, :s)",
                   {"p": pid, "n": pname, "v": s["params"].get(pname) or None,
                    "s": "1" if secret else "0"})
        print(f"  + провайдер {code} создан (ENABLED='0')")


def run(target: str) -> int:
    be: CrediteBackend = AdbBackend() if target == "adb" else Biro26Backend()
    print(f"\n=== {target} ===")
    try:
        create_objects(be, DDL_PATH[target])
        migrate_legacy(be)
        seed_providers(be)
        rename_legacy(be)
    except Exception as e:
        print(f"  FAIL: {e}")
        return 1
    missing = [t for t in TABLES if not _exists(be, t)]
    if missing:
        print(f"  FAIL: отсутствуют объекты {missing}")
        return 1
    print(f"  OK: все {len(TABLES)} таблиц на месте")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", choices=["adb", "biro26", "both"], default="both")
    a = ap.parse_args()
    targets = ["adb", "biro26"] if a.target == "both" else [a.target]
    return max(run(t) for t in targets)


if __name__ == "__main__":
    sys.exit(main())
```

Скрипт импортирует `models.credite_settings` — он появится в Task 3. Порядок выполнения: сначала Task 3 (бэкенды), потом запуск деплоя. Поэтому шаг проверки ниже — только синтаксис.

- [ ] **Step 4: Включить DDL в порядок деплоя ADB**

В `deploy_oracle_objects.py` найти список файлов в порядке выполнения и добавить `'50_credite_tables.sql'` после последнего существующего `sql/*.sql` (перед `47_nufarul_system_settings.sql` не вставлять — только в конец списка). Точное имя переменной проверить командой:

```bash
cd /Users/pt/Projects.AI/Artgranit && grep -n "nufarul_system_settings\|\.sql'" deploy_oracle_objects.py | head -20
```

- [ ] **Step 5: Проверить синтаксис**

```bash
cd /Users/pt/Projects.AI/Artgranit
./venv/bin/python -c "import ast; ast.parse(open('deploy_credite_oracle.py',encoding='utf-8').read()); ast.parse(open('deploy_oracle_objects.py',encoding='utf-8').read()); print('OK')"
```

Ожидается: `OK`

- [ ] **Step 6: Проверить разбор DDL на statements**

```bash
cd /Users/pt/Projects.AI/Artgranit
./venv/bin/python -c "
import importlib.util, sys
spec = importlib.util.spec_from_file_location('d', 'deploy_credite_oracle.py')
src = open('deploy_credite_oracle.py',encoding='utf-8').read()
ns = {}
exec(compile(src.split('from models.credite_settings')[0] + src.split('DDL_PATH = ')[0].split('TABLES = ')[0][0:0], 'x', 'exec'), ns)
" 2>/dev/null || ./venv/bin/python - <<'PY'
import re
src = open('deploy_credite_oracle.py', encoding='utf-8').read()
m = re.search(r'def _split_ddl.*?\n\ndef ', src, re.S)
ns = {'List': list, 'text': ''}
exec(m.group(0).rsplit('\ndef ', 1)[0], ns)
stmts = ns['_split_ddl'](open('sql/50_credite_tables.sql', encoding='utf-8').read())
print('statements:', len(stmts))
for s in stmts:
    print(' -', ' '.join(s.split()[:4]))
PY
```

Ожидается: `statements: 18` и список из 6 `CREATE TABLE`, 6 `CREATE SEQUENCE`, 3 `CREATE INDEX`, 6 `CREATE OR REPLACE TRIGGER` — суммарно 21. Если число отличается, поправить `_split_ddl`, пока каждый оператор не выделяется отдельно и ни один не содержит лишнего `;`.

- [ ] **Step 7: Commit**

```bash
cd /Users/pt/Projects.AI/Artgranit
git add sql/50_credite_tables.sql sql/biro26/12_tms_credite.sql deploy_credite_oracle.py deploy_oracle_objects.py
git commit -m "feat(credite): DDL TMS_CREDITE_* + идемпотентный деплой в обе БД

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 3: Слой настроек `models/credite_settings.py`

**Files:**
- Create: `models/credite_settings.py`
- Create: `test_credite_settings.py`

**Interfaces:**
- Consumes: `models.database.DatabaseModel`, `models.biro26_db.Biro26DB`
- Produces:
  - `PROVIDER_DEFS: dict[str, dict]` — описание провайдеров: `name`, `icon`, `color`, `ord`, `params: list[tuple[str, bool]]`, `default_base_url: dict[str, str]`
  - `class CrediteBackend` с методами `query(sql, params) -> list[dict]` и `dml(sql, params) -> None` (бросает `CrediteBackendError`)
  - `class AdbBackend(CrediteBackend)`, `class Biro26Backend(CrediteBackend)`
  - `class CrediteSettings` — `__init__(backend)`, `get(code) -> dict | None`, `list_all() -> list[dict]`, `save(code, enabled, env, base_url, params) -> dict`, `masked(code) -> dict | None`, `invalidate(code=None)`
  - `adb_settings() -> CrediteSettings`, `biro26_settings() -> CrediteSettings` — модульные синглтоны

- [ ] **Step 1: Написать падающий тест**

Создать `test_credite_settings.py`:

```python
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
    if m["params"].get("has_api_password") is not None:
        pass
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


TESTS = [
    ("save + get", t_save_and_get),
    ("пустой секрет не затирает", t_empty_secret_keeps_previous),
    ("masked() скрывает секреты", t_masked_hides_secrets),
    ("недоступная БД -> None", t_dead_backend_returns_none),
    ("PROVIDER_DEFS", t_provider_defs),
    ("живой roundtrip", t_live_roundtrip),
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
```

- [ ] **Step 2: Запустить тест — убедиться, что падает**

```bash
cd /Users/pt/Projects.AI/Artgranit && ./venv/bin/python test_credite_settings.py
```

Ожидается: `ModuleNotFoundError: No module named 'models.credite_settings'`

- [ ] **Step 3: Написать реализацию**

Создать `models/credite_settings.py`:

```python
"""Настройки кредитных провайдеров в Oracle (TMS_CREDITE_PROVIDER + _PARAM).

Один и тот же DDL развёрнут в двух БД, и каждый контур читает свою:
  AdbBackend    — Oracle ADB основного проекта (thin mode + wallet)
  Biro26Backend — Oracle 11g OfficePlus (thick mode, subprocess worker)

CrediteSettings — CRUD поверх любого бэкенда, с кэшем в памяти (TTL 60 c).
При недоступности БД чтение возвращает None: вызывающий код (config.py,
провайдеры) откатывается на значения из .env.
"""
from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

CACHE_TTL_SEC = 60


class CrediteBackendError(RuntimeError):
    """Ошибка доступа к БД настроек."""


# Описание провайдеров: единственный источник правды о наборе параметров.
# params: список (имя, секретный?) — секретные маскируются в API-ответах,
# и пустое значение при сохранении означает «не менять».
PROVIDER_DEFS: Dict[str, Dict[str, Any]] = {
    "easycredit": {
        "name": "EasyCredit",
        "icon": "💳",
        "color": "#667eea",
        "ord": 1,
        "params": [("api_user", False), ("api_password", True)],
        "default_base_url": {"sandbox": "https://tst.ecmoldova.cloud:8082",
                             "production": "https://w81.ecredit.md:8082"},
    },
    "iute": {
        "name": "Iute Credit",
        "icon": "🟣",
        "color": "#7c3aed",
        "ord": 2,
        "params": [("api_key", True), ("pos_identifier", False),
                   ("salesman_identifier", False)],
        "default_base_url": {"sandbox": "https://iute-core-partner-gateway.iute.eu",
                             "production": "https://iute-core-partner-gateway.iute.eu"},
    },
}


class CrediteBackend(ABC):
    """Доступ к БД, в которой лежат TMS_CREDITE_*."""

    id: str = "abstract"

    @abstractmethod
    def query(self, sql: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """SELECT. Ключи словарей — имена колонок в нижнем регистре."""

    @abstractmethod
    def dml(self, sql: str, params: Optional[Dict[str, Any]] = None) -> None:
        """INSERT/UPDATE/DELETE/DDL. Бросает CrediteBackendError при ошибке."""


class AdbBackend(CrediteBackend):
    """Oracle ADB основного проекта."""

    id = "adb"

    def query(self, sql: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        from models.database import DatabaseModel
        try:
            with DatabaseModel() as db:
                r = db.execute_query(sql, params or {})
        except Exception as e:
            raise CrediteBackendError(str(e)) from e
        if not r.get("success"):
            raise CrediteBackendError(r.get("message") or "query failed")
        cols = [c.lower() for c in r.get("columns", [])]
        return [dict(zip(cols, row)) for row in r.get("data", [])]

    def dml(self, sql: str, params: Optional[Dict[str, Any]] = None) -> None:
        from models.database import DatabaseModel
        try:
            with DatabaseModel() as db:
                r = db.execute_query(sql, params or {})
                if r.get("success"):
                    db.connection.commit()
        except Exception as e:
            raise CrediteBackendError(str(e)) from e
        if not r.get("success"):
            raise CrediteBackendError(r.get("message") or "dml failed")


class Biro26Backend(CrediteBackend):
    """Oracle 11g OfficePlus через thick-subprocess worker."""

    id = "biro26"

    def query(self, sql: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        from models.biro26_db import Biro26DB
        r = Biro26DB().execute_query(sql, params or {})
        if not r.get("success"):
            raise CrediteBackendError(r.get("message") or "query failed")
        cols = [c.lower() for c in r.get("columns", [])]
        return [dict(zip(cols, row)) for row in r.get("data", [])]

    def dml(self, sql: str, params: Optional[Dict[str, Any]] = None) -> None:
        from models.biro26_db import Biro26DB
        r = Biro26DB().execute_dml(sql, params or {})
        if not r.get("success"):
            raise CrediteBackendError(r.get("message") or "dml failed")


class CrediteSettings:
    """CRUD настроек провайдеров поверх одного бэкенда."""

    def __init__(self, backend: CrediteBackend) -> None:
        self.backend = backend
        self._cache: Dict[str, tuple[float, Optional[Dict[str, Any]]]] = {}
        self._lock = threading.Lock()

    # ── чтение ──

    def get(self, code: str) -> Optional[Dict[str, Any]]:
        """Настройки провайдера с расшифрованными параметрами.

        Возвращает None, если провайдера нет или БД недоступна.
        """
        code = (code or "").strip().lower()
        with self._lock:
            hit = self._cache.get(code)
            if hit and time.time() - hit[0] < CACHE_TTL_SEC:
                return hit[1]
        val = self._load(code)
        with self._lock:
            self._cache[code] = (time.time(), val)
        return val

    def _load(self, code: str) -> Optional[Dict[str, Any]]:
        try:
            rows = self.backend.query(
                "SELECT ID, CODE, NAME, ENABLED, ENV, BASE_URL, ICON, COLOR, INFO, ORD "
                "FROM TMS_CREDITE_PROVIDER WHERE CODE = :c", {"c": code})
        except CrediteBackendError:
            return None
        if not rows:
            return None
        return self._hydrate(rows[0])

    def _hydrate(self, row: Dict[str, Any]) -> Dict[str, Any]:
        try:
            prows = self.backend.query(
                "SELECT PARAM_NAME, PARAM_VALUE, IS_SECRET "
                "FROM TMS_CREDITE_PROVIDER_PARAM WHERE PROVIDER_ID = :p",
                {"p": row["id"]})
        except CrediteBackendError:
            prows = []
        spec = PROVIDER_DEFS.get(row["code"], {})
        env = (row.get("env") or "sandbox").lower()
        base = (row.get("base_url") or "").rstrip("/")
        if not base:
            base = (spec.get("default_base_url") or {}).get(env, "")
        return {
            "id": row["id"],
            "code": row["code"],
            "name": row.get("name") or spec.get("name") or row["code"],
            "enabled": (row.get("enabled") or "0") == "1",
            "env": env,
            "base_url": base,
            "icon": row.get("icon") or spec.get("icon", "🏦"),
            "color": row.get("color") or spec.get("color", "#0066CC"),
            "info": row.get("info") or "",
            "ord": int(row.get("ord") or 0),
            "params": {p["param_name"]: (p["param_value"] or "") for p in prows},
            "secrets": {p["param_name"] for p in prows if p.get("is_secret") == "1"},
        }

    def list_all(self) -> List[Dict[str, Any]]:
        """Все известные провайдеры. Отсутствующие в БД — как незаполненные."""
        out = []
        for code, spec in sorted(PROVIDER_DEFS.items(), key=lambda kv: kv[1]["ord"]):
            d = self.get(code)
            if d is None:
                d = {"id": None, "code": code, "name": spec["name"], "enabled": False,
                     "env": "sandbox",
                     "base_url": spec["default_base_url"]["sandbox"],
                     "icon": spec["icon"], "color": spec["color"], "info": "",
                     "ord": spec["ord"], "params": {}, "secrets": set()}
            out.append(d)
        return out

    def masked(self, code: str) -> Optional[Dict[str, Any]]:
        """Копия get() с замаскированными секретами — безопасна для JSON-API."""
        d = self.get(code)
        if d is None:
            return None
        out = dict(d)
        out["params"] = {}
        out["has_secret"] = {}
        for name, value in d["params"].items():
            if name in d["secrets"]:
                out["params"][name] = (value[:3] + "***") if value else ""
                out["has_secret"][name] = bool(value)
            else:
                out["params"][name] = value
        out["secrets"] = sorted(d["secrets"])
        out["configured"] = self.is_configured(code)
        return out

    def is_configured(self, code: str) -> bool:
        """Заданы ли все секретные параметры провайдера."""
        d = self.get(code)
        if d is None:
            return False
        spec = PROVIDER_DEFS.get(code, {})
        required = [n for n, secret in spec.get("params", []) if secret]
        if code == "easycredit":
            required = ["api_user", "api_password"]
        return all((d["params"].get(n) or "").strip() for n in required)

    # ── запись ──

    def save(self, code: str, *, enabled: bool, env: str, base_url: str,
             params: Dict[str, str]) -> Dict[str, Any]:
        """Сохранить настройки. Пустое значение секретного параметра = «не менять»."""
        code = (code or "").strip().lower()
        spec = PROVIDER_DEFS.get(code)
        if not spec:
            return {"success": False, "error": f"неизвестный провайдер: {code}"}
        env = (env or "sandbox").lower()
        if env not in ("sandbox", "production"):
            env = "sandbox"
        base_url = (base_url or "").strip().rstrip("/") or spec["default_base_url"][env]
        try:
            rows = self.backend.query(
                "SELECT ID FROM TMS_CREDITE_PROVIDER WHERE CODE = :c", {"c": code})
            if rows:
                pid = int(rows[0]["id"])
                self.backend.dml(
                    "UPDATE TMS_CREDITE_PROVIDER SET ENABLED=:en, ENV=:e, BASE_URL=:b, "
                    "UPDATED=SYSDATE WHERE CODE=:c",
                    {"en": "1" if enabled else "0", "e": env, "b": base_url, "c": code})
            else:
                self.backend.dml(
                    "INSERT INTO TMS_CREDITE_PROVIDER (CODE, NAME, ENABLED, ENV, "
                    "BASE_URL, ICON, COLOR, ORD) "
                    "VALUES (:c, :n, :en, :e, :b, :i, :col, :o)",
                    {"c": code, "n": spec["name"], "en": "1" if enabled else "0",
                     "e": env, "b": base_url, "i": spec["icon"],
                     "col": spec["color"], "o": spec["ord"]})
                pid = int(self.backend.query(
                    "SELECT ID FROM TMS_CREDITE_PROVIDER WHERE CODE = :c",
                    {"c": code})[0]["id"])
            existing = {p["param_name"]: p for p in self.backend.query(
                "SELECT PARAM_NAME, PARAM_VALUE, IS_SECRET "
                "FROM TMS_CREDITE_PROVIDER_PARAM WHERE PROVIDER_ID = :p", {"p": pid})}
            for pname, secret in spec["params"]:
                new = (params.get(pname) or "").strip()
                if pname in existing:
                    if secret and not new:
                        continue  # пустой секрет — не затираем
                    self.backend.dml(
                        "UPDATE TMS_CREDITE_PROVIDER_PARAM SET PARAM_VALUE=:v "
                        "WHERE PROVIDER_ID=:p AND PARAM_NAME=:n",
                        {"v": new or None, "p": pid, "n": pname})
                else:
                    self.backend.dml(
                        "INSERT INTO TMS_CREDITE_PROVIDER_PARAM (PROVIDER_ID, "
                        "PARAM_NAME, PARAM_VALUE, IS_SECRET) VALUES (:p, :n, :v, :s)",
                        {"p": pid, "n": pname, "v": new or None,
                         "s": "1" if secret else "0"})
        except CrediteBackendError as e:
            return {"success": False, "error": str(e)}
        self.invalidate(code)
        return {"success": True}

    def invalidate(self, code: Optional[str] = None) -> None:
        with self._lock:
            if code is None:
                self._cache.clear()
            else:
                self._cache.pop(code.lower(), None)


_ADB: Optional[CrediteSettings] = None
_BIRO26: Optional[CrediteSettings] = None


def adb_settings() -> CrediteSettings:
    """Настройки провайдеров основного проекта (Oracle ADB)."""
    global _ADB
    if _ADB is None:
        _ADB = CrediteSettings(AdbBackend())
    return _ADB


def biro26_settings() -> CrediteSettings:
    """Настройки провайдеров Biro26 (Oracle 11g OfficePlus)."""
    global _BIRO26
    if _BIRO26 is None:
        _BIRO26 = CrediteSettings(Biro26Backend())
    return _BIRO26
```

- [ ] **Step 4: Запустить тест — должен пройти**

```bash
cd /Users/pt/Projects.AI/Artgranit && ./venv/bin/python test_credite_settings.py
```

Ожидается: `6/6 passed`. Живой тест печатает `[skip]`, если таблицы ещё не развёрнуты — это нормально до Task 2 deploy.

- [ ] **Step 5: Развернуть таблицы в обеих БД (без переименования legacy)**

⚠️ Обе БД — общие с production: локальная разработка и remote-приложение ходят в одни и те же
Oracle ADB и OfficePlus 11g. Работающий на remote код пока обращается к `YBIRO_CREDIT_*`,
поэтому переименование в `*_OLD` откладывается до Task 10 — после того, как новый код уедет
на сервер. Добавить в `deploy_credite_oracle.py` флаг `--rename-legacy` (по умолчанию выключен)
и вызывать `rename_legacy(be)` только при нём.

```bash
cd /Users/pt/Projects.AI/Artgranit && ./venv/bin/python deploy_credite_oracle.py --target both
```

Ожидается: для каждого target — строки `+ CREATE TABLE TMS_CREDITE_...`, `+ провайдер easycredit создан`, `+ провайдер iute создан` и финальное `OK: все 6 таблиц на месте`. Строк `~ YBIRO_CREDIT_ORG -> ...` быть НЕ должно.

- [ ] **Step 6: Проверить идемпотентность**

```bash
cd /Users/pt/Projects.AI/Artgranit && ./venv/bin/python deploy_credite_oracle.py --target both
```

Ожидается: те же таблицы, но строки `= ... (уже есть)`, `= TMS_CREDITE_ORG уже заполнена — миграция пропущена`, `= провайдер easycredit уже есть`, и снова `OK: все 6 таблиц на месте`. Никаких ошибок.

- [ ] **Step 7: Повторно запустить тест — живой roundtrip теперь работает**

```bash
cd /Users/pt/Projects.AI/Artgranit && ./venv/bin/python test_credite_settings.py
```

Ожидается: `6/6 passed`, и в выводе теста «живой roundtrip» — строки `[live] adb: enabled=False env=...` и `[live] biro26: enabled=False env=...`.

- [ ] **Step 8: Commit**

```bash
cd /Users/pt/Projects.AI/Artgranit
git add models/credite_settings.py test_credite_settings.py
git commit -m "feat(credite): слой настроек провайдеров в Oracle (TMS_CREDITE_PROVIDER)

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 4: `config.py` — настройки из Oracle вместо `data/*.json`

**Files:**
- Modify: `config.py:12-70` (функции загрузки/сохранения), `config.py:235-300` (классметоды `Config`)

**Interfaces:**
- Consumes: `models.credite_settings.adb_settings`
- Produces: `Config.easycredit_env/base_url/api_user/api_password`, `Config.iute_env/base_url/api_key/pos_identifier/salesman_identifier` — сигнатуры не меняются; `save_easycredit_settings(env, base_url, api_user, api_password)`, `save_iute_settings(env, base_url, api_key, pos_identifier, salesman_identifier)` — сигнатуры не меняются, но пишут в Oracle

- [ ] **Step 1: Написать тест на приоритет источников**

Добавить в `test_credite_settings.py` перед списком `TESTS`:

```python
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
```

И добавить в список `TESTS` элемент:

```python
    ("Config читает Oracle", t_config_reads_oracle),
```

- [ ] **Step 2: Запустить — убедиться, что падает**

```bash
cd /Users/pt/Projects.AI/Artgranit && ./venv/bin/python test_credite_settings.py
```

Ожидается: `[FAIL] Config читает Oracle` с расхождением по `base_url` или `env` (config.py пока читает JSON/.env, а не Oracle). Если случайно совпало — временно изменить `env` провайдера в БД:

```bash
cd /Users/pt/Projects.AI/Artgranit && ./venv/bin/python -c "
from models.credite_settings import adb_settings
print(adb_settings().save('easycredit', enabled=False, env='production', base_url='', params={}))
"
```
и запустить тест снова — он должен упасть.

- [ ] **Step 3: Переписать чтение настроек в `config.py`**

Заменить функции `_load_easycredit_overrides` и `_load_iute_overrides` (строки 16-35) на:

```python
def _json_overrides(path: Path) -> dict:
    """Читает data/*_settings.json. Используется ТОЛЬКО как seed при деплое
    (deploy_credite_oracle.py) — авторитетное хранилище теперь Oracle."""
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _load_easycredit_overrides():
    """Seed-источник EasyCredit. Не читается в рантайме — см. _oracle('easycredit')."""
    return _json_overrides(EASYCREDIT_SETTINGS_PATH)


def _load_iute_overrides():
    """Seed-источник Iute. Не читается в рантайме — см. _oracle('iute')."""
    return _json_overrides(IUTE_SETTINGS_PATH)


def _oracle(code: str) -> dict:
    """Настройки провайдера из TMS_CREDITE_PROVIDER (ADB). {} при недоступности."""
    try:
        from models.credite_settings import adb_settings
        d = adb_settings().get(code)
    except Exception:
        return {}
    if not d:
        return {}
    out = {"env": d["env"], "base_url": d["base_url"]}
    out.update(d["params"])
    return out
```

- [ ] **Step 4: Переписать сохранение настроек в `config.py`**

Заменить тела `save_easycredit_settings` и `save_iute_settings` на запись в Oracle:

```python
def save_easycredit_settings(env: str, base_url: str, api_user: str, api_password: str) -> None:
    """Сохраняет настройки EasyCredit в TMS_CREDITE_PROVIDER (ADB).
    Пустой api_password означает «не менять» (см. CrediteSettings.save)."""
    from models.credite_settings import adb_settings
    r = adb_settings().save("easycredit", enabled=True, env=env, base_url=base_url,
                            params={"api_user": api_user, "api_password": api_password})
    if not r.get("success"):
        raise RuntimeError(r.get("error") or "не удалось сохранить настройки EasyCredit")


def save_iute_settings(env: str, base_url: str, api_key: str, pos_identifier: str,
                       salesman_identifier: str) -> None:
    """Сохраняет настройки Iute в TMS_CREDITE_PROVIDER (ADB).
    Пустой api_key означает «не менять»."""
    from models.credite_settings import adb_settings
    r = adb_settings().save("iute", enabled=True, env=env, base_url=base_url,
                            params={"api_key": api_key,
                                    "pos_identifier": pos_identifier,
                                    "salesman_identifier": salesman_identifier})
    if not r.get("success"):
        raise RuntimeError(r.get("error") or "не удалось сохранить настройки Iute")
```

- [ ] **Step 5: Переключить классметоды `Config` на Oracle**

Заменить восемь классметодов (строки ~239-300) на:

```python
    @classmethod
    def easycredit_base_url(cls) -> str:
        o = _oracle('easycredit')
        base = o.get('base_url') or cls.EASYCREDIT_BASE_URL
        if base:
            return base.rstrip('/')
        if (o.get('env') or cls.EASYCREDIT_ENV) == 'production':
            return 'https://w81.ecredit.md:8082'
        return 'https://tst.ecmoldova.cloud:8082'

    @classmethod
    def easycredit_env(cls) -> str:
        return _oracle('easycredit').get('env') or cls.EASYCREDIT_ENV

    @classmethod
    def easycredit_api_user(cls) -> str:
        return _oracle('easycredit').get('api_user') or cls.EASYCREDIT_API_USER

    @classmethod
    def easycredit_api_password(cls) -> str:
        return _oracle('easycredit').get('api_password') or cls.EASYCREDIT_API_PASSWORD
```

и аналогично для Iute:

```python
    @classmethod
    def iute_base_url(cls) -> str:
        o = _oracle('iute')
        base = o.get('base_url') or cls.IUTE_BASE_URL
        if base:
            return base.rstrip('/')
        return 'https://iute-core-partner-gateway.iute.eu'

    @classmethod
    def iute_env(cls) -> str:
        return _oracle('iute').get('env') or cls.IUTE_ENV

    @classmethod
    def iute_api_key(cls) -> str:
        return _oracle('iute').get('api_key') or cls.IUTE_API_KEY

    @classmethod
    def iute_pos_identifier(cls) -> str:
        return _oracle('iute').get('pos_identifier') or cls.IUTE_POS_IDENTIFIER

    @classmethod
    def iute_salesman_identifier(cls) -> str:
        return _oracle('iute').get('salesman_identifier') or cls.IUTE_SALESMAN_IDENTIFIER
```

- [ ] **Step 6: Запустить тест — должен пройти**

```bash
cd /Users/pt/Projects.AI/Artgranit && ./venv/bin/python test_credite_settings.py
```

Ожидается: `7/7 passed`

- [ ] **Step 7: Проверить, что приложение импортируется**

```bash
cd /Users/pt/Projects.AI/Artgranit && ./venv/bin/python -c "import app; print('app OK')"
```

Ожидается: `app OK`

- [ ] **Step 8: Commit**

```bash
cd /Users/pt/Projects.AI/Artgranit
git add config.py test_credite_settings.py
git commit -m "refactor(credite): Config читает настройки провайдеров из Oracle, data/*.json только seed

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 5: `settings_source` в провайдерах и `build_registry`

**Files:**
- Modify: `integrations/base_provider.py`
- Modify: `integrations/easycredit_provider.py`
- Modify: `integrations/iute_provider.py`
- Modify: `integrations/__init__.py`

**Interfaces:**
- Consumes: `models.credite_settings.CrediteSettings`
- Produces:
  - `CreditProvider.__init__(self, settings_source=None)`; защищённый `self._cfg() -> dict`
  - `build_registry(settings_source) -> ProviderRegistry` в `integrations/__init__.py`
  - Глобальный `registry` продолжает работать как раньше (настройки ADB через `Config`)

- [ ] **Step 1: Написать тест**

Добавить в `test_credite_settings.py` перед `TESTS`:

```python
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
```

И добавить в `TESTS`:

```python
    ("provider settings_source", t_provider_settings_source),
```

- [ ] **Step 2: Запустить — убедиться, что падает**

```bash
cd /Users/pt/Projects.AI/Artgranit && ./venv/bin/python test_credite_settings.py
```

Ожидается: `[FAIL] provider settings_source` с `ImportError: cannot import name 'build_registry'`

- [ ] **Step 3: Добавить `settings_source` в базовый класс**

В `integrations/base_provider.py` добавить в класс `CreditProvider` сразу после docstring класса (перед секцией «Метаданные»):

```python
    def __init__(self, settings_source: Any = None) -> None:
        """settings_source — объект с методом get(code) -> dict | None
        (обычно models.credite_settings.CrediteSettings). None = читать Config."""
        self._settings_source = settings_source

    def _cfg(self) -> dict[str, Any]:
        """Настройки этого провайдера из settings_source. {} если источника нет."""
        if self._settings_source is None:
            return {}
        try:
            d = self._settings_source.get(self.id)
        except Exception:
            return {}
        return d or {}

    def _cfg_param(self, name: str) -> str:
        """Значение параметра из settings_source ('' если нет)."""
        return (self._cfg().get("params") or {}).get(name) or ""
```

Убрать singleton из `ProviderRegistry` — заменить метод `__new__` на обычный `__init__`:

```python
class ProviderRegistry:
    """Реестр доступных кредитных провайдеров.

    Глобальный экземпляр `registry` обслуживает основной проект (настройки ADB
    через Config). Для отдельного контура (например, Biro26 с настройками в
    Oracle 11g) создаётся свой экземпляр — см. integrations.build_registry.
    """

    def __init__(self) -> None:
        self._providers: dict[str, CreditProvider] = {}
```

(строки с `_instance`, `_providers: dict[str, CreditProvider]` на уровне класса и метод `__new__` удаляются; остальные методы `register`/`get`/`list_all`/`list_dicts`/`ids` не меняются).

- [ ] **Step 4: Переключить EasyCreditProvider на settings_source**

В `integrations/easycredit_provider.py` заменить четыре приватных метода:

```python
    def _base_url(self) -> str:
        return self._cfg().get("base_url") or Config.easycredit_base_url()

    def _user(self) -> str:
        return self._cfg_param("api_user") or Config.easycredit_api_user()

    def _password(self) -> str:
        return self._cfg_param("api_password") or Config.easycredit_api_password()

    def _verify_ssl(self) -> bool:
        return self._env() == "production"

    def _env(self) -> str:
        return self._cfg().get("env") or Config.easycredit_env()
```

И в `get_settings()` заменить `"env": Config.easycredit_env(),` на `"env": self._env(),`.

- [ ] **Step 5: Переключить IuteProvider на settings_source**

В `integrations/iute_provider.py` заменить приватные методы:

```python
    def _base_url(self) -> str:
        return self._cfg().get("base_url") or Config.iute_base_url()

    def _env(self) -> str:
        return self._cfg().get("env") or Config.iute_env()

    def _api_key(self) -> str:
        return self._cfg_param("api_key") or Config.iute_api_key()

    def _pos_identifier(self) -> str:
        return self._cfg_param("pos_identifier") or Config.iute_pos_identifier()

    def _salesman_identifier(self) -> str:
        return self._cfg_param("salesman_identifier") or Config.iute_salesman_identifier()
```

И в `get_settings()` заменить `"env": Config.iute_env(),` на `"env": self._env(),`.

- [ ] **Step 6: Добавить `build_registry`**

Переписать `integrations/__init__.py`:

```python
# Integrations (EasyCredit, Iute, ...)
# Авто-регистрация провайдеров в глобальном реестре (настройки основного
# проекта — через Config, который читает Oracle ADB).
# Для отдельного контура (Biro26, Oracle 11g) — build_registry(settings_source).

from typing import Any

from integrations.base_provider import CreditProvider, ProviderRegistry, registry

from integrations.easycredit_provider import EasyCreditProvider
from integrations.iute_provider import IuteProvider

registry.register(EasyCreditProvider())
registry.register(IuteProvider())

PROVIDER_CLASSES = [EasyCreditProvider, IuteProvider]


def build_registry(settings_source: Any) -> ProviderRegistry:
    """Новый реестр провайдеров, читающих настройки из settings_source.

    settings_source — объект с методом get(code) -> dict | None,
    обычно models.credite_settings.CrediteSettings.
    """
    reg = ProviderRegistry()
    for cls in PROVIDER_CLASSES:
        reg.register(cls(settings_source))
    return reg
```

- [ ] **Step 7: Запустить тест — должен пройти**

```bash
cd /Users/pt/Projects.AI/Artgranit && ./venv/bin/python test_credite_settings.py
```

Ожидается: `8/8 passed`

- [ ] **Step 8: Проверить, что демо основного проекта не сломалось**

```bash
cd /Users/pt/Projects.AI/Artgranit && ./venv/bin/python -c "
from integrations import registry
for p in registry.list_all():
    d = p.to_dict()
    print(d['id'], 'configured=', d['configured'], 'env=', d['settings'].get('env'))
"
```

Ожидается: две строки — `easycredit configured= ... env= ...` и `iute configured= ... env= ...`, без исключений.

- [ ] **Step 9: Commit**

```bash
cd /Users/pt/Projects.AI/Artgranit
git add integrations/ test_credite_settings.py
git commit -m "feat(credite): провайдеры получают settings_source, build_registry для отдельного контура

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 6: `models/biro26_credit.py` — переход на `TMS_CREDITE_*` и API-методы

**Files:**
- Modify: `models/biro26_credit.py` (весь файл)

**Interfaces:**
- Consumes: `models.credite_settings.biro26_settings`, `integrations.build_registry`, `models.biro26_db.Biro26DB`, `models.biro26_oracle_store._rows`
- Produces (используется Task 7):
  - `Biro26Credit.orgs_list`, `org_save`, `plans_list`, `plan_save`, `plan_delete`, `public_offers`, `plan_get`, `calc`, `request_create`, `requests_list`, `request_status` — сигнатуры не меняются
  - `Biro26Credit.providers_list() -> {"success": bool, "data": list[dict]}`
  - `Biro26Credit.provider_save(d: dict) -> {"success": bool, "error"?: str}` — `d` содержит `code`, `enabled`, `env`, `base_url`, `params`
  - `Biro26Credit.provider_test(code: str) -> {"success": bool, "data"?: dict, "error"?: str}`
  - `Biro26Credit.api_preapproved(d: dict) -> {"success": bool, "data": {"preapproved": bool, "max_amount": float, "message": str}}` — `d`: `org_id`, `idnp`, `amount`, `phone`
  - `Biro26Credit.api_submit(d: dict) -> {"success": bool, "data": {"req_id": int, "ext_ref": str, "status": str}}` — `d`: `org_id`, `plan_id`, `months`, `amount`, `client_name`, `phone`, `idnp`, `product_name`, `product_cod`, `qty`
  - `Biro26Credit.api_status(req_id: int) -> {"success": bool, "data": {"status": str, "ext_ref": str}}`
  - `Biro26Credit.request_events(req_id: int) -> {"success": bool, "data": list[dict]}`

- [ ] **Step 1: Написать тест**

Создать `test_biro26_credite.py`:

```python
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
    if not plans.get("success") or not plans["data"]:
        print("  [skip] нет пакетов кредита")
        return []
    p = plans["data"][0]
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


TESTS = [
    ("таблицы TMS_CREDITE_* существуют", t_tables_exist),
    ("нет YBIRO_CREDIT_* в коде", t_no_legacy_names_in_code),
    ("offers содержат provider", t_offers_carry_provider),
    ("providers_list маскирует секреты", t_providers_list),
    ("calc() не изменился", t_calc_unchanged),
    ("api без провайдера деградирует", t_api_without_provider_degrades),
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
```

- [ ] **Step 2: Запустить — убедиться, что падает**

```bash
cd /Users/pt/Projects.AI/Artgranit && ./venv/bin/python test_biro26_credite.py
```

Ожидается: минимум три падения — `нет YBIRO_CREDIT_* в коде`, `offers содержат provider`, `providers_list маскирует секреты` (последний с `AttributeError: type object 'Biro26Credit' has no attribute 'providers_list'`).

- [ ] **Step 3: Переименовать таблицы в существующих запросах**

Во всём `models/biro26_credit.py` заменить:

```bash
cd /Users/pt/Projects.AI/Artgranit
python3 - <<'PY'
import re, pathlib
p = pathlib.Path('models/biro26_credit.py')
s = p.read_text(encoding='utf-8')
for a, b in (('YBIRO_CREDIT_ORG_SEQ', 'TMS_CREDITE_ORG_SEQ'),
             ('YBIRO_CREDIT_PLAN_SEQ', 'TMS_CREDITE_PLAN_SEQ'),
             ('YBIRO_CREDIT_REQ_SEQ', 'TMS_CREDITE_REQ_SEQ'),
             ('YBIRO_CREDIT_ORG', 'TMS_CREDITE_ORG'),
             ('YBIRO_CREDIT_PLAN', 'TMS_CREDITE_PLAN'),
             ('YBIRO_CREDIT_REQ', 'TMS_CREDITE_REQ')):
    s = s.replace(a, b)
p.write_text(s, encoding='utf-8')
print('done')
PY
```

Ожидается: `done`. Затем убедиться:

```bash
cd /Users/pt/Projects.AI/Artgranit && grep -c "YBIRO_CREDIT_" models/biro26_credit.py
```

Ожидается: `0`

- [ ] **Step 4: Убрать вставку ID через SEQ (теперь есть триггеры)**

Триггеры `*_BI` проставляют ID сами, но явные `SEQ.NEXTVAL` в INSERT остаются рабочими (`WHEN (NEW.ID IS NULL)` не срабатывает). Менять эти INSERT не требуется — оставить как есть.

- [ ] **Step 5: Добавить провайдерский слой и API-методы**

В `models/biro26_credit.py` дописать в конец файла (внутри класса `Biro26Credit`, с тем же отступом, что у остальных `@staticmethod`):

```python
    # ── провайдеры API (TMS_CREDITE_PROVIDER, настройки Biro26/11g) ──

    @staticmethod
    def _registry():
        """Реестр провайдеров с настройками из Oracle 11g (Biro26)."""
        from integrations import build_registry
        from models.credite_settings import biro26_settings
        return build_registry(biro26_settings())

    @staticmethod
    def providers_list() -> Dict[str, Any]:
        """RO: providerii API cu setari mascate (pentru admin).
        EN: API providers with masked secrets (admin page)."""
        try:
            from models.credite_settings import PROVIDER_DEFS, biro26_settings
            st = biro26_settings()
            out = []
            for code in sorted(PROVIDER_DEFS, key=lambda c: PROVIDER_DEFS[c]["ord"]):
                d = st.masked(code)
                if d is None:
                    spec = PROVIDER_DEFS[code]
                    d = {"code": code, "name": spec["name"], "enabled": False,
                         "env": "sandbox",
                         "base_url": spec["default_base_url"]["sandbox"],
                         "icon": spec["icon"], "color": spec["color"],
                         "params": {n: "" for n, _ in spec["params"]},
                         "secrets": [n for n, s in spec["params"] if s],
                         "configured": False}
                d["param_defs"] = [{"name": n, "secret": s}
                                   for n, s in PROVIDER_DEFS[code]["params"]]
                out.append(d)
            return {"success": True, "data": out}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def provider_save(d: Dict[str, Any]) -> Dict[str, Any]:
        """RO: salveaza setarile providerului. Secret gol = «nu schimba»."""
        from models.credite_settings import PROVIDER_DEFS, biro26_settings
        code = (d.get("code") or "").strip().lower()
        if code not in PROVIDER_DEFS:
            return {"success": False, "error": f"provider necunoscut: {code}"}
        params = {n: (d.get("params") or {}).get(n) or ""
                  for n, _ in PROVIDER_DEFS[code]["params"]}
        return biro26_settings().save(
            code,
            enabled=d.get("enabled") in (True, "1", 1, "true"),
            env=(d.get("env") or "sandbox"),
            base_url=(d.get("base_url") or ""),
            params=params)

    @staticmethod
    def provider_test(code: str) -> Dict[str, Any]:
        """RO: test de conexiune la provider (check_auth / preapproved de proba)."""
        import time as _t
        prov = Biro26Credit._registry().get((code or "").strip().lower())
        if prov is None:
            return {"success": False, "error": f"provider necunoscut: {code}"}
        if not prov.is_configured():
            return {"success": False, "error": "providerul nu e configurat"}
        t0 = _t.time()
        if "check_auth" in prov.capabilities:
            res = prov.check_auth()
        else:
            res = prov.preapproved(uin="2000000000001", amount=1000)
        ms = int((_t.time() - t0) * 1000)
        Biro26Credit._log_event(None, code, "check_auth", res, ms, {})
        return {"success": bool(res.get("success")),
                "data": {"duration_ms": ms, "result": res.get("data") or {}},
                "error": res.get("error")}

    # ── jurnal apeluri API ──

    @staticmethod
    def _mask_idnp(idnp: str) -> str:
        s = (idnp or "").strip()
        return f"{s[:2]}{'*' * max(0, len(s) - 4)}{s[-2:]}" if len(s) > 4 else "*" * len(s)

    @staticmethod
    def _log_event(req_id: Optional[int], provider_code: str, op: str,
                   result: Dict[str, Any], duration_ms: int,
                   payload: Dict[str, Any]) -> None:
        """RO: scrie un rind in TMS_CREDITE_REQ_EVENT (best-effort, nu arunca)."""
        import json as _j
        try:
            safe = dict(payload or {})
            if "idnp" in safe:
                safe["idnp"] = Biro26Credit._mask_idnp(safe["idnp"])
            if "phone" in safe and safe["phone"]:
                safe["phone"] = str(safe["phone"])[:5] + "***"
            Biro26DB().execute_dml(
                "INSERT INTO TMS_CREDITE_REQ_EVENT (REQ_ID, PROVIDER_CODE, OP, "
                "HTTP_CODE, DURATION_MS, PAYLOAD, RESULT, IS_ERROR) "
                "VALUES (:r, :p, :o, :h, :d, :pl, :res, :e)",
                {"r": req_id, "p": (provider_code or "")[:30], "o": (op or "")[:30],
                 "h": result.get("http_code"), "d": duration_ms,
                 "pl": _j.dumps(safe, ensure_ascii=False)[:3900],
                 "res": _j.dumps(result, ensure_ascii=False, default=str)[:3900],
                 "e": "0" if result.get("success") else "1"})
        except Exception:
            pass

    @staticmethod
    def request_events(req_id: int) -> Dict[str, Any]:
        """RO: jurnalul apelurilor API pentru o cerere."""
        try:
            rows = _rows(Biro26DB().execute_query(
                "SELECT ID, PROVIDER_CODE, OP, HTTP_CODE, DURATION_MS, IS_ERROR, "
                "PAYLOAD, RESULT, TO_CHAR(CREATED,'DD.MM.YYYY HH24:MI:SS') CREATED "
                "FROM TMS_CREDITE_REQ_EVENT WHERE REQ_ID = :i ORDER BY ID",
                {"i": int(req_id)}))
            return {"success": True, "data": rows}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── fluxul API al clientului: preapproved -> submit -> status ──

    @staticmethod
    def _org_provider(org_id: int) -> Optional[Dict[str, Any]]:
        """RO: providerul legat de organizatie, sau None."""
        rows = _rows(Biro26DB().execute_query(
            "SELECT o.ID ORG_ID, o.NAME ORG_NAME, p.CODE PROVIDER_CODE "
            "FROM TMS_CREDITE_ORG o JOIN TMS_CREDITE_PROVIDER p "
            "  ON p.ID = o.PROVIDER_ID "
            "WHERE o.ID = :i AND o.ENABLED = '1' AND p.ENABLED = '1'",
            {"i": int(org_id)}))
        return rows[0] if rows else None

    @staticmethod
    def api_preapproved(d: Dict[str, Any]) -> Dict[str, Any]:
        """RO: verifica suma preaprobata la providerul organizatiei."""
        import time as _t
        try:
            org_id = int(d.get("org_id") or 0)
            amount = round(float(d.get("amount") or 0), 2)
        except (TypeError, ValueError):
            return {"success": False, "error": "date invalide"}
        idnp = (d.get("idnp") or "").strip()
        if len(idnp) < 10:
            return {"success": False, "error": "IDNP invalid"}
        link = Biro26Credit._org_provider(org_id)
        if not link:
            return {"success": False,
                    "error": "organizația nu are provider API configurat"}
        code = link["provider_code"]
        prov = Biro26Credit._registry().get(code)
        if prov is None or not prov.is_configured():
            return {"success": False, "error": f"providerul {code} nu e configurat"}
        t0 = _t.time()
        res = prov.preapproved(uin=idnp, amount=int(amount),
                               phone=(d.get("phone") or "").strip())
        ms = int((_t.time() - t0) * 1000)
        Biro26Credit._log_event(None, code, "preapproved", res, ms,
                                {"idnp": idnp, "amount": amount, "org_id": org_id})
        if not res.get("success"):
            return {"success": False, "error": res.get("error") or "eroare provider"}
        data = res.get("data") or {}
        return {"success": True, "data": {
            "preapproved": bool(data.get("preapproved")),
            "max_amount": float(data.get("max_amount") or 0),
            "message": data.get("message") or ""}}

    @staticmethod
    def api_submit(d: Dict[str, Any]) -> Dict[str, Any]:
        """RO: creeaza cererea in TMS_CREDITE_REQ si o trimite la provider."""
        import time as _t
        name = (d.get("client_name") or "").strip()
        phone = (d.get("phone") or "").strip()
        idnp = (d.get("idnp") or "").strip()
        if not name or not phone:
            return {"success": False, "error": "Numele și telefonul sunt obligatorii"}
        if len(idnp) < 10:
            return {"success": False, "error": "IDNP invalid"}
        try:
            org_id = int(d.get("org_id") or 0)
            plan_id = int(d.get("plan_id") or 0)
            qty = max(1, int(d.get("qty") or 1))
            amount = round(float(d.get("amount") or 0), 2)
        except (TypeError, ValueError):
            return {"success": False, "error": "date invalide"}
        link = Biro26Credit._org_provider(org_id)
        if not link:
            return {"success": False,
                    "error": "organizația nu are provider API configurat"}
        code = link["provider_code"]
        prov = Biro26Credit._registry().get(code)
        if prov is None or not prov.is_configured():
            return {"success": False, "error": f"providerul {code} nu e configurat"}
        sim = Biro26Credit.calc(amount, plan_id, d.get("months"), 0)
        if not sim.get("success"):
            return sim
        s = sim["data"]
        product_name = (d.get("product_name") or "Comandă OfficePlus")[:300]
        # RO: rezervam ID-ul din secventa INAINTE de INSERT — subprocess worker-ul
        #     nu suporta bind-uri OUT, iar SELECT MAX(ID) ar fi supus unei curse
        #     la cereri concurente. NEXTVAL e atomic.
        seq = _rows(Biro26DB().execute_query(
            "SELECT TMS_CREDITE_REQ_SEQ.NEXTVAL ID FROM dual"))
        if not seq:
            return {"success": False, "error": "nu s-a putut aloca ID-ul cererii"}
        req_id = int(seq[0]["id"])
        ins = Biro26DB().execute_dml(
            "INSERT INTO TMS_CREDITE_REQ (ID, ORG_ID, PLAN_ID, MONTHS, PRODUCT_COD, "
            "PRODUCT_NAME, QTY, AMOUNT, CREDIT_PRICE, MONTHLY, CLIENT_NAME, PHONE, "
            "PROVIDER_CODE, IDNP_MASKED, API_STATUS) VALUES (:id, :o, :p, :m, :pc, "
            ":pn, :q, :a, :cp, :mo, :cn, :ph, :prc, :idm, 'SENDING')",
            {"id": req_id, "o": org_id, "p": plan_id, "m": s["months"],
             "pc": int(d.get("product_cod") or 0) or None, "pn": product_name,
             "q": qty, "a": amount, "cp": s["credit_price"], "mo": s["monthly"],
             "cn": name[:200], "ph": phone[:40], "prc": code[:30],
             "idm": Biro26Credit._mask_idnp(idnp)[:20]})
        if not ins.get("success"):
            return {"success": False, "error": ins.get("message")}
        kwargs = {"fio": name, "phone": phone, "uin": idnp,
                  "amount": int(round(s["credit_price"])),
                  "goods_price": int(round(s["credit_price"])),
                  "product_name": product_name,
                  "program_name": f"0-0-{s['months']}",
                  "order_id": f"OP-{req_id}", "user_pin": idnp,
                  "currency": "MDL"}
        t0 = _t.time()
        res = prov.submit(**kwargs)
        ms = int((_t.time() - t0) * 1000)
        Biro26Credit._log_event(req_id, code, "submit", res, ms,
                                {"idnp": idnp, "phone": phone, "amount": amount,
                                 "plan_id": plan_id, "months": s["months"]})
        data = res.get("data") or {}
        ext_ref = (data.get("urn") or data.get("order_id")
                   or kwargs["order_id"]) if res.get("success") else None
        api_status = ("SENT" if res.get("success") else "ERROR")
        Biro26DB().execute_dml(
            "UPDATE TMS_CREDITE_REQ SET EXT_REF = :x, API_STATUS = :s, "
            "LAST_CHECK = SYSDATE WHERE ID = :i",
            {"x": (ext_ref or "")[:120] or None, "s": api_status, "i": req_id})
        if not res.get("success"):
            return {"success": False, "error": res.get("error") or "eroare provider",
                    "data": {"req_id": req_id}}
        return {"success": True, "data": {"req_id": req_id, "ext_ref": ext_ref,
                                          "status": api_status,
                                          "monthly": s["monthly"],
                                          "months": s["months"],
                                          "org": link["org_name"]}}

    @staticmethod
    def api_status(req_id: int) -> Dict[str, Any]:
        """RO: reinterogheaza statusul cererii la provider si il salveaza."""
        import time as _t
        rows = _rows(Biro26DB().execute_query(
            "SELECT ID, PROVIDER_CODE, EXT_REF, API_STATUS FROM TMS_CREDITE_REQ "
            "WHERE ID = :i", {"i": int(req_id)}))
        if not rows:
            return {"success": False, "error": "cerere inexistentă"}
        r = rows[0]
        code, ext = r.get("provider_code"), r.get("ext_ref")
        if not code or not ext:
            return {"success": True, "data": {"status": r.get("api_status") or "",
                                              "ext_ref": ext or ""}}
        prov = Biro26Credit._registry().get(code)
        if prov is None or not prov.is_configured():
            return {"success": True, "data": {"status": r.get("api_status") or "",
                                              "ext_ref": ext}}
        t0 = _t.time()
        res = prov.check_status(urn=ext, order_id=ext)
        ms = int((_t.time() - t0) * 1000)
        Biro26Credit._log_event(int(req_id), code, "status", res, ms, {"ext_ref": ext})
        if not res.get("success"):
            return {"success": False, "error": res.get("error") or "eroare provider",
                    "data": {"status": r.get("api_status") or "", "ext_ref": ext}}
        st = ((res.get("data") or {}).get("status")
              or (res.get("data") or {}).get("state") or "")
        Biro26DB().execute_dml(
            "UPDATE TMS_CREDITE_REQ SET API_STATUS = :s, LAST_CHECK = SYSDATE "
            "WHERE ID = :i", {"s": (st or "")[:60] or None, "i": int(req_id)})
        return {"success": True, "data": {"status": st, "ext_ref": ext}}
```

- [ ] **Step 6: Добавить `provider` в `public_offers`**

В `models/biro26_credit.py` заменить тело `public_offers` на:

```python
    @staticmethod
    def public_offers() -> Dict[str, Any]:
        """RO: organizatiile active cu pachetele active + providerul API legat.
        EN: enabled orgs with enabled plans and the linked API provider."""
        try:
            from models.credite_settings import biro26_settings
            orgs = _rows(Biro26DB().execute_query(
                "SELECT o.ID, o.NAME, o.ORG_MODE, o.LOGO_URL, o.INFO, "
                "p.CODE PROVIDER_CODE, p.NAME PROVIDER_NAME, p.ICON PROVIDER_ICON "
                "FROM TMS_CREDITE_ORG o "
                "LEFT JOIN TMS_CREDITE_PROVIDER p "
                "  ON p.ID = o.PROVIDER_ID AND p.ENABLED = '1' "
                "WHERE o.ENABLED = '1' ORDER BY o.ORD, o.ID"))
            plans = _rows(Biro26DB().execute_query(
                "SELECT p.ID, p.ORG_ID, p.NAME, p.MONTHS_MIN, p.MONTHS_MAX, "
                "p.AMOUNT_MIN, p.AMOUNT_MAX, p.MARKUP_PCT, p.ANNUAL_PCT, "
                "p.MONTHLY_FEE_PCT, p.ISSUE_FEE, p.AVANS_MIN_PCT "
                "FROM TMS_CREDITE_PLAN p JOIN TMS_CREDITE_ORG o ON o.ID = p.ORG_ID "
                "WHERE p.ENABLED = '1' AND o.ENABLED = '1' "
                "ORDER BY p.ORG_ID, p.MONTHS_MIN"))
            st = biro26_settings()
            for o in orgs:
                o["plans"] = [p for p in plans if p["org_id"] == o["id"]]
                code = o.pop("provider_code", None)
                o["provider"] = None if not code else {
                    "code": code,
                    "name": o.get("provider_name") or code,
                    "icon": o.get("provider_icon") or "🏦",
                    "configured": st.is_configured(code)}
                o.pop("provider_name", None)
                o.pop("provider_icon", None)
            return {"success": True, "data": [o for o in orgs if o["plans"]]}
        except Exception as e:
            return {"success": False, "error": str(e)}
```

- [ ] **Step 7: Добавить `provider_id` в `org_save` и `orgs_list`**

В `orgs_list` заменить SELECT-список: после `o.INFO, o.ORD, ` добавить `o.PROVIDER_ID, `.

В `org_save` добавить в `params` строку:

```python
                      "pid": int(d["provider_id"]) if d.get("provider_id") else None,
```

в UPDATE — `PROVIDER_ID=:pid, ` перед `ORD=:o`; в INSERT — колонку `PROVIDER_ID` в список и `:pid` в VALUES.

- [ ] **Step 8: Запустить тест — должен пройти**

```bash
cd /Users/pt/Projects.AI/Artgranit && ./venv/bin/python test_biro26_credite.py
```

Ожидается: `6/6 passed`

- [ ] **Step 9: Проверить, что старые тесты не сломались**

```bash
cd /Users/pt/Projects.AI/Artgranit && ./venv/bin/python test_biro26_smoke.py && ./venv/bin/python test_credite_settings.py
```

Ожидается: smoke без FAIL, `8/8 passed` для настроек.

- [ ] **Step 10: Commit**

```bash
cd /Users/pt/Projects.AI/Artgranit
git add models/biro26_credit.py test_biro26_credite.py
git commit -m "feat(biro26): кредитный модуль на TMS_CREDITE_*, API-флоу через провайдеров

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 7: Роуты — админ API провайдеров и публичный кредитный флоу

**Files:**
- Modify: `controllers/biro26_controller.py` (секция credit, ~строка 615)
- Modify: `app.py` (блок credit-роутов, ~строки 6161-6210)

**Interfaces:**
- Consumes: методы `Biro26Credit` из Task 6
- Produces (используется Tasks 8-9):
  - `GET  /api/biro26/credit/providers` → `{success, data: [{code, name, icon, color, enabled, env, base_url, params, param_defs, configured}]}`
  - `PUT  /api/biro26/credit/providers` → тело `{code, enabled, env, base_url, params}` → `{success}`
  - `POST /api/biro26/credit/providers/<code>/test` → `{success, data: {duration_ms, result}, error?}`
  - `GET  /api/biro26/credit/requests/<id>/events` → `{success, data: [...]}`
  - `POST /api/biro26/shop/credit/api/preapproved` → тело `{org_id, idnp, amount, phone}` → `{success, data: {preapproved, max_amount, message}}`
  - `POST /api/biro26/shop/credit/api/submit` → тело `{org_id, plan_id, months, amount, qty, client_name, phone, idnp, product_name, product_cod}` → `{success, data: {req_id, ext_ref, status, monthly, months, org}}`
  - `GET  /api/biro26/shop/credit/api/status?req_id=N` → `{success, data: {status, ext_ref}}`

- [ ] **Step 1: Добавить контроллерные обёртки**

В `controllers/biro26_controller.py` после метода `credit_plan_delete` добавить:

```python
    # ── credit: provideri API + fluxul clientului ──

    @staticmethod
    def credit_providers() -> Dict[str, Any]:
        from models.biro26_credit import Biro26Credit
        return Biro26Credit.providers_list()

    @staticmethod
    def credit_provider_save() -> Dict[str, Any]:
        from models.biro26_credit import Biro26Credit
        return Biro26Credit.provider_save(request.get_json(silent=True) or {})

    @staticmethod
    def credit_provider_test(code: str) -> Dict[str, Any]:
        from models.biro26_credit import Biro26Credit
        return Biro26Credit.provider_test(code)

    @staticmethod
    def credit_request_events(req_id: int) -> Dict[str, Any]:
        from models.biro26_credit import Biro26Credit
        return Biro26Credit.request_events(req_id)

    @staticmethod
    def credit_api_preapproved() -> Dict[str, Any]:
        from models.biro26_credit import Biro26Credit
        return Biro26Credit.api_preapproved(request.get_json(silent=True) or {})

    @staticmethod
    def credit_api_submit() -> Dict[str, Any]:
        from models.biro26_credit import Biro26Credit
        return Biro26Credit.api_submit(request.get_json(silent=True) or {})

    @staticmethod
    def credit_api_status() -> Dict[str, Any]:
        from models.biro26_credit import Biro26Credit
        try:
            req_id = int(request.args.get('req_id') or 0)
        except (TypeError, ValueError):
            return {"success": False, "error": "req_id invalid"}
        if not req_id:
            return {"success": False, "error": "req_id lipsește"}
        return Biro26Credit.api_status(req_id)
```

Проверить, что `request` уже импортирован в файле:

```bash
cd /Users/pt/Projects.AI/Artgranit && grep -n "^from flask import\|^import flask" controllers/biro26_controller.py
```

Если `request` отсутствует в импорте — добавить его.

- [ ] **Step 2: Добавить роуты в `app.py`**

После роута `api_biro26_credit_plan_delete` (перед комментарием `# ── translations management page + API`) вставить:

```python
# ── credit: provideri API (admin, auth) ──
@app.route('/api/biro26/credit/providers', methods=['GET'])
def api_biro26_credit_providers():
    return _b26(Biro26Controller.credit_providers)

@app.route('/api/biro26/credit/providers', methods=['PUT'])
def api_biro26_credit_provider_save():
    return _b26(Biro26Controller.credit_provider_save)

@app.route('/api/biro26/credit/providers/<code>/test', methods=['POST'])
def api_biro26_credit_provider_test(code):
    return _b26(lambda: Biro26Controller.credit_provider_test(code))

@app.route('/api/biro26/credit/requests/<int:req_id>/events', methods=['GET'])
def api_biro26_credit_request_events(req_id):
    return _b26(lambda: Biro26Controller.credit_request_events(req_id))

# ── credit: fluxul API al clientului (public, rate-limited) ──
@app.route('/api/biro26/shop/credit/api/preapproved', methods=['POST'])
@limiter.limit("10 per minute")
def api_biro26_shop_credit_preapproved():
    return jsonify(Biro26Controller.credit_api_preapproved())

@app.route('/api/biro26/shop/credit/api/submit', methods=['POST'])
@limiter.limit("5 per minute")
def api_biro26_shop_credit_submit():
    return jsonify(Biro26Controller.credit_api_submit())

@app.route('/api/biro26/shop/credit/api/status', methods=['GET'])
@limiter.limit("60 per minute")
def api_biro26_shop_credit_api_status():
    return jsonify(Biro26Controller.credit_api_status())
```

- [ ] **Step 3: Проверить, что `limiter` не исключает BIRO26-пути**

```bash
cd /Users/pt/Projects.AI/Artgranit && sed -n '70,110p' app.py
```

В проекте BIRO26-пути освобождены от общего лимита (см. комментарий в `config.py`: «anonymous non-BIRO26 /api only; BIRO26 + auth are exempt in app.py»). Явные декораторы `@limiter.limit(...)` выше перекрывают это освобождение для трёх новых публичных роутов. Если в `app.py` есть глобальный `default_limits` с `exempt_when`, убедиться, что `exempt_when` не отключает и явные лимиты; если отключает — заменить `@limiter.limit("N per minute")` на собственную проверку через `limiter.shared_limit` либо оставить лимит только на `submit`, зафиксировав это в комментарии.

- [ ] **Step 4: Проверить синтаксис и регистрацию роутов**

```bash
cd /Users/pt/Projects.AI/Artgranit && ./venv/bin/python -c "
import app
paths = sorted(str(r) for r in app.app.url_map.iter_rules() if 'credit' in str(r))
for p in paths: print(p)
"
```

Ожидается: в списке присутствуют `/api/biro26/credit/providers`, `/api/biro26/credit/providers/<code>/test`, `/api/biro26/credit/requests/<int:req_id>/events`, `/api/biro26/shop/credit/api/preapproved`, `/api/biro26/shop/credit/api/submit`, `/api/biro26/shop/credit/api/status`.

- [ ] **Step 5: Проверить живьём**

Запустить приложение локально и вызвать публичный роут:

```bash
cd /Users/pt/Projects.AI/Artgranit && ./run_local.sh > /tmp/app_credit.log 2>&1 &
sleep 8
curl -s -X POST http://127.0.0.1:3003/api/biro26/shop/credit/api/preapproved \
  -H 'Content-Type: application/json' \
  -d '{"org_id": 999999, "idnp": "2000000000001", "amount": 10000}'
echo
curl -s "http://127.0.0.1:3003/api/biro26/shop/credit/offers" | head -c 400
echo
```

Ожидается: первый вызов → `{"error":"organizația nu are provider API configurat","success":false}`; второй → JSON со списком организаций, у каждой есть ключ `provider`.

Остановить приложение:

```bash
pkill -f "python app.py" || true
```

- [ ] **Step 6: Commit**

```bash
cd /Users/pt/Projects.AI/Artgranit
git add app.py controllers/biro26_controller.py
git commit -m "feat(biro26): роуты провайдеров API и публичного кредитного флоу

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 8: Бэк-офис — вкладка «Provideri API»

**Files:**
- Modify: `templates/biro26/credit_admin.html`

**Interfaces:**
- Consumes: роуты из Task 7
- Produces: UI (потребителей в коде нет)

- [ ] **Step 1: Добавить секцию провайдеров в разметку**

В `templates/biro26/credit_admin.html` перед блоком с таблицей организаций (`<tbody id="orgs">`) вставить карточную секцию:

```html
<section style="margin-bottom:18px">
  <h2 style="font-size:15px;margin:0 0 4px">Provideri API · API-провайдеры</h2>
  <div class="muted" style="font-size:12px;margin-bottom:8px">
    Setările se păstrează în TMS_CREDITE_PROVIDER (OfficePlus). Cîmpul unui secret
    lăsat gol înseamnă «nu schimba». ·
    Настройки хранятся в TMS_CREDITE_PROVIDER; пустое поле секрета — «не менять».
  </div>
  <div id="providers" style="display:flex;flex-wrap:wrap;gap:12px"></div>
</section>
```

- [ ] **Step 2: Добавить JS рендера и сохранения провайдеров**

В `<script>` того же файла добавить перед функцией `load()`:

```javascript
var PROVIDERS = [];

function provCard(p, i) {
  var fields = (p.param_defs || []).map(function (d) {
    var v = (p.params || {})[d.name] || '';
    return '<label style="display:block;font-size:11.5px;margin-top:6px">' + d.name +
      (d.secret ? ' <span class="muted">(secret)</span>' : '') +
      '<input data-prov="' + i + '" data-param="' + d.name + '" value="' +
      (d.secret ? '' : String(v).replace(/"/g, '&quot;')) + '" placeholder="' +
      (d.secret && v ? String(v).replace(/"/g, '&quot;') : '') +
      '" style="width:100%;padding:5px;border:1px solid #cbd5e1;border-radius:6px;font-size:12px"></label>';
  }).join('');
  return '<div style="border:1px solid #e2e8f0;border-left:4px solid ' + (p.color || '#0066CC') +
    ';border-radius:8px;padding:10px;width:290px">' +
    '<div style="font-weight:700;font-size:13.5px">' + (p.icon || '') + ' ' + p.name +
    ' <span style="font-weight:400;font-size:11.5px;color:' +
    (p.configured ? '#059669' : '#b91c1c') + '">' +
    (p.configured ? 'configurat' : 'neconfigurat') + '</span></div>' +
    '<label style="display:block;font-size:11.5px;margin-top:6px">' +
    '<input type="checkbox" data-prov="' + i + '" data-field="enabled"' +
    (p.enabled ? ' checked' : '') + '> activ / включён</label>' +
    '<label style="display:block;font-size:11.5px;margin-top:6px">env' +
    '<select data-prov="' + i + '" data-field="env" style="width:100%;padding:5px;border:1px solid #cbd5e1;border-radius:6px;font-size:12px">' +
    '<option value="sandbox"' + (p.env === 'sandbox' ? ' selected' : '') + '>sandbox</option>' +
    '<option value="production"' + (p.env === 'production' ? ' selected' : '') + '>production</option>' +
    '</select></label>' +
    '<label style="display:block;font-size:11.5px;margin-top:6px">base_url' +
    '<input data-prov="' + i + '" data-field="base_url" value="' +
    String(p.base_url || '').replace(/"/g, '&quot;') +
    '" style="width:100%;padding:5px;border:1px solid #cbd5e1;border-radius:6px;font-size:12px"></label>' +
    fields +
    '<div style="margin-top:9px;display:flex;gap:6px">' +
    '<button onclick="saveProv(' + i + ')" style="flex:1;padding:6px;border:0;border-radius:6px;background:#111827;color:#fff;font-size:12px;cursor:pointer">Salvează</button>' +
    '<button onclick="testProv(' + i + ')" style="flex:1;padding:6px;border:1px solid #cbd5e1;border-radius:6px;background:#fff;font-size:12px;cursor:pointer">Test conexiune</button>' +
    '</div><div id="prov-res-' + i + '" class="muted" style="font-size:11.5px;margin-top:5px"></div></div>';
}

function renderProviders() {
  document.getElementById('providers').innerHTML =
    PROVIDERS.map(function (p, i) { return provCard(p, i); }).join('');
}

function provPayload(i) {
  var p = PROVIDERS[i], out = {code: p.code, params: {}};
  document.querySelectorAll('[data-prov="' + i + '"]').forEach(function (el) {
    if (el.dataset.field === 'enabled') out.enabled = el.checked;
    else if (el.dataset.field) out[el.dataset.field] = el.value;
    else if (el.dataset.param) out.params[el.dataset.param] = el.value;
  });
  return out;
}

async function saveProv(i) {
  var r = await j('/api/biro26/credit/providers',
    {method: 'PUT', body: JSON.stringify(provPayload(i))});
  if (!r.success) { toast(r.error || 'Eroare', true); return; }
  toast('Salvat');
  await loadProviders();
}

async function testProv(i) {
  var out = document.getElementById('prov-res-' + i);
  out.textContent = '…';
  var r = await j('/api/biro26/credit/providers/' + PROVIDERS[i].code + '/test',
    {method: 'POST'});
  out.textContent = r.success
    ? '✅ OK · ' + ((r.data || {}).duration_ms || 0) + ' ms'
    : '❌ ' + (r.error || 'eroare');
  out.style.color = r.success ? '#059669' : '#b91c1c';
}

async function loadProviders() {
  var r = await j('/api/biro26/credit/providers');
  PROVIDERS = (r && r.success) ? r.data : [];
  renderProviders();
}
```

- [ ] **Step 3: Добавить селект провайдера в строку организации**

В функции `orgRow(o, i)` добавить ячейку с селектом провайдера — после ячейки `org_mode` (найти строку с `org_mode` в `orgRow` и вставить следом):

```javascript
    '<td><select data-org="' + i + '" data-f="provider_id" style="padding:4px;border:1px solid #cbd5e1;border-radius:6px;font-size:12px">' +
    '<option value="">— manual —</option>' +
    PROVIDERS.filter(function (p) { return p.enabled; }).map(function (p) {
      return '<option value="' + (p.id || '') + '"' +
        (String(o.provider_id || '') === String(p.id) ? ' selected' : '') + '>' +
        p.icon + ' ' + p.name + '</option>';
    }).join('') + '</select></td>' +
```

Добавить соответствующий `<th>` в шапку таблицы организаций: `<th>Provider API</th>` — рядом с заголовком колонки режима.

В функции `saveOrg(i)` добавить `provider_id` в отправляемое тело, читая значение селекта:

```javascript
  var sel = document.querySelector('[data-org="' + i + '"][data-f="provider_id"]');
  body.provider_id = sel && sel.value ? parseInt(sel.value, 10) : null;
```

(вставить перед вызовом `j('/api/biro26/credit/orgs', {method: 'PUT', ...})`; имя переменной с телом запроса взять из существующего кода `saveOrg`).

- [ ] **Step 4: Добавить API-колонки и лог в таблицу заявок**

В функции `loadReqs()` в разметке строки заявки добавить две ячейки после статуса:

```javascript
    '<td style="font-size:11.5px">' + (r.ext_ref || '—') + '</td>' +
    '<td style="font-size:11.5px">' + (r.api_status || '—') +
    (r.ext_ref ? ' <button onclick="refreshReq(' + r.id + ')" style="border:0;background:none;cursor:pointer" title="Actualizează statusul">🔄</button>' +
      ' <button onclick="showEvents(' + r.id + ')" style="border:0;background:none;cursor:pointer" title="Jurnal API">📋</button>' : '') +
    '</td>' +
```

Добавить два `<th>`: `<th>Ref</th><th>Status API</th>` — и увеличить `colspan` у плейсхолдера `<tr><td colspan="9">` до `11`.

Добавить функции:

```javascript
async function refreshReq(id) {
  var r = await j('/api/biro26/shop/credit/api/status?req_id=' + id);
  toast(r.success ? ('Status: ' + ((r.data || {}).status || '—')) : (r.error || 'Eroare'), !r.success);
  await loadReqs();
}

async function showEvents(id) {
  var r = await j('/api/biro26/credit/requests/' + id + '/events');
  if (!r.success) { toast(r.error || 'Eroare', true); return; }
  var lines = (r.data || []).map(function (e) {
    return e.created + ' · ' + e.op + ' · ' + (e.is_error === '1' ? 'EROARE' : 'OK') +
      ' · ' + (e.duration_ms || 0) + ' ms\n    ' + (e.result || '').slice(0, 300);
  }).join('\n');
  alert(lines || 'Fără evenimente API');
}
```

- [ ] **Step 5: Вызвать `loadProviders()` при загрузке**

В функции `load()` добавить `await loadProviders();` **до** загрузки организаций (селект провайдера в `orgRow` читает массив `PROVIDERS`).

- [ ] **Step 6: Проверить в браузере**

```bash
cd /Users/pt/Projects.AI/Artgranit && ./run_local.sh > /tmp/app_credit.log 2>&1 &
sleep 8
```

Открыть `http://127.0.0.1:3003/UNA.md/orasldev/biro26-credit-admin` (после логина) и проверить:

1. Видны две карточки провайдеров — EasyCredit и Iute, обе со статусом `neconfigurat`.
2. У EasyCredit заполнить `api_user` / `api_password` тестовыми значениями, нажать «Salvează» → тост `Salvat`, после перезагрузки страницы статус `configurat`, а поле пароля пустое с маской в placeholder.
3. Нажать «Test conexiune» → появляется `✅ OK · N ms` либо `❌ <ошибка провайдера>` (обе реакции корректны — важно, что страница не падает).
4. В таблице организаций появился селект «Provider API»; выбрать EasyCredit, сохранить, перезагрузить — выбор сохранился.

Проверить отсутствие ошибок JS:

```bash
grep -i "error\|traceback" /tmp/app_credit.log | tail -20
```

Ожидается: нет трейсбеков, связанных с credit-роутами.

Остановить приложение: `pkill -f "python app.py" || true`

- [ ] **Step 7: Commit**

```bash
cd /Users/pt/Projects.AI/Artgranit
git add templates/biro26/credit_admin.html
git commit -m "feat(biro26): бэк-офис — вкладка провайдеров API, привязка к организации, лог вызовов

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 9: Фронт-офис — кредитный флоу в корзине и карточке товара

**Files:**
- Modify: `templates/biro26/site_cart.html`
- Modify: `templates/biro26/shop.html`

**Interfaces:**
- Consumes: `GET /api/biro26/shop/credit/offers` (теперь с полем `provider`), `POST .../api/preapproved`, `POST .../api/submit`, `GET .../api/status`
- Produces: UI

- [ ] **Step 1: Добавить форму кредитной заявки в корзину**

В `templates/biro26/site_cart.html` внутрь `<div id="credit-box">` (после поля `credit-avans`) добавить:

```html
<div id="ec-flow" style="display:none;margin-top:10px;border-top:1px solid #e2e8f0;padding-top:10px">
  <div style="font-weight:700;font-size:13px;margin-bottom:6px">
    <span id="ec-org-label"></span>
  </div>
  <div style="display:flex;flex-wrap:wrap;gap:6px">
    <input id="ec-fio" placeholder="Nume Prenume · ФИО"
           style="flex:1;min-width:170px;padding:6px;border:1px solid #cbd5e1;border-radius:6px">
    <input id="ec-phone" placeholder="+373 …"
           style="width:150px;padding:6px;border:1px solid #cbd5e1;border-radius:6px">
    <input id="ec-idnp" placeholder="IDNP" maxlength="13"
           style="width:150px;padding:6px;border:1px solid #cbd5e1;border-radius:6px">
  </div>
  <div style="display:flex;gap:6px;margin-top:8px">
    <button id="ec-pre" onclick="ecPreapproved()"
            style="flex:1;padding:8px;border:1px solid #cbd5e1;border-radius:6px;background:#fff;cursor:pointer">
      🔍 Verifică preaprobarea · Проверить предодобрение
    </button>
    <button id="ec-sub" onclick="ecSubmit()" disabled
            style="flex:1;padding:8px;border:0;border-radius:6px;background:#94a3b8;color:#fff;cursor:not-allowed">
      📨 Trimite cererea · Отправить заявку
    </button>
  </div>
  <div id="ec-out" style="font-size:12.5px;margin-top:8px"></div>
</div>
```

- [ ] **Step 2: Добавить JS кредитного флоу**

В `<script>` файла `site_cart.html` добавить:

```javascript
/* RO: fluxul API al organizatiei de creditare (preapproved -> submit -> status).
   Se afiseaza doar daca organizatia are provider API configurat in back-office.
   EN: credit-provider API flow, shown only when the org has a configured provider. */
var ecCtx = {org: null, reqId: null, poll: null};

function ecOrgOf(tile) {
  if (!tile) return null;
  var o = OFFERS.find(function (x) { return x.id === tile.org.id; });
  return (o && o.provider && o.provider.configured) ? o : null;
}

function ecUI() {
  var box = document.getElementById('ec-flow');
  var t = currentTile();
  var org = ecOrgOf(t);
  ecCtx.org = org;
  box.style.display = org ? '' : 'none';
  if (org) {
    document.getElementById('ec-org-label').textContent =
      (org.provider.icon || '') + ' ' + org.provider.name +
      ' — cerere online · онлайн-заявка';
  }
}

function ecOut(html, color) {
  var el = document.getElementById('ec-out');
  el.innerHTML = html;
  el.style.color = color || '#334155';
}

async function ecPreapproved() {
  var t = currentTile();
  if (!ecCtx.org || !t) return;
  var idnp = document.getElementById('ec-idnp').value.trim();
  if (idnp.length < 10) { ecOut('IDNP invalid · Неверный IDNP', '#b91c1c'); return; }
  ecOut('…');
  var r = await j(API + '/credit/api/preapproved', {method: 'POST', body: JSON.stringify({
    org_id: ecCtx.org.id, idnp: idnp, amount: Math.round(t.credit_price),
    phone: document.getElementById('ec-phone').value.trim()})});
  var btn = document.getElementById('ec-sub');
  if (!r.success) {
    ecOut('❌ ' + (r.error || 'eroare'), '#b91c1c');
    btn.disabled = true; btn.style.background = '#94a3b8'; btn.style.cursor = 'not-allowed';
    return;
  }
  var d = r.data || {};
  if (d.preapproved) {
    ecOut('✅ Preaprobat pînă la <b>' + Math.round(d.max_amount) +
      ' lei</b> · Предодобрено до ' + Math.round(d.max_amount) + ' лей', '#059669');
    btn.disabled = false; btn.style.background = '#111827'; btn.style.cursor = 'pointer';
  } else {
    ecOut('⚠️ ' + (d.message || 'Fără preaprobare · Без предодобрения') +
      '<br>Puteți trimite cererea — decizia o ia creditorul.', '#b45309');
    btn.disabled = false; btn.style.background = '#111827'; btn.style.cursor = 'pointer';
  }
}

async function ecSubmit() {
  var t = currentTile();
  if (!ecCtx.org || !t) return;
  var fio = document.getElementById('ec-fio').value.trim();
  var phone = document.getElementById('ec-phone').value.trim();
  var idnp = document.getElementById('ec-idnp').value.trim();
  if (!fio || !phone) { ecOut('Numele și telefonul sunt obligatorii', '#b91c1c'); return; }
  ecOut('…');
  var r = await j(API + '/credit/api/submit', {method: 'POST', body: JSON.stringify({
    org_id: ecCtx.org.id, plan_id: t.plan.id, months: t.m,
    amount: t.credit_price / (1 + (t.plan.markup_pct || 0) / 100),
    qty: 1, client_name: fio, phone: phone, idnp: idnp,
    product_name: 'Coș OfficePlus'})});
  if (!r.success) { ecOut('❌ ' + (r.error || 'eroare'), '#b91c1c'); return; }
  ecCtx.reqId = r.data.req_id;
  ecOut('📨 Cerere trimisă · Заявка отправлена<br>Referință: <b>' +
    (r.data.ext_ref || '—') + '</b><br><span id="ec-st">Se verifică statusul…</span>', '#0f766e');
  ecPoll(0);
}

function ecPoll(n) {
  if (ecCtx.poll) clearTimeout(ecCtx.poll);
  if (n > 24 || !ecCtx.reqId) {                       // 24 × 5 c = 2 минуты
    var el0 = document.getElementById('ec-st');
    if (el0) el0.textContent = 'Verificați statusul mai tîrziu — managerul vă va contacta.';
    return;
  }
  ecCtx.poll = setTimeout(async function () {
    var r = await j(API + '/credit/api/status?req_id=' + ecCtx.reqId);
    var el = document.getElementById('ec-st');
    var st = (r.data || {}).status || '';
    if (el) el.textContent = 'Status: ' + (st || '—');
    var done = /APPROV|REJECT|APROB|RESPINS|DECLIN|CANCEL/i.test(st);
    if (!done) ecPoll(n + 1);
  }, 5000);
}
```

- [ ] **Step 3: Подключить `ecUI()` к переключению способа оплаты и выбору срока**

В `site_cart.html` найти функцию `setPm(m)` и функцию, которая перерисовывает плитки сроков (использует `tiles`), и в конце каждой добавить вызов:

```javascript
  ecUI();
```

Также убедиться, что существует функция `currentTile()`, возвращающая выбранную плитку (`{plan, org, m, monthly, credit_price}`). Если её нет — добавить, читая выбранную плитку из той же переменной, что использует существующая функция сохранения заказа (в текущем коде это переменная с выбранной плиткой в обработчике `payMethod === 'credit'`):

```javascript
function currentTile() {
  return (typeof selectedTile !== 'undefined') ? selectedTile : null;
}
```

Имя переменной сверить командой:

```bash
cd /Users/pt/Projects.AI/Artgranit && grep -n "tiles\|var t = " templates/biro26/site_cart.html | head -20
```

- [ ] **Step 4: Скрывать фолбэк-кнопку, когда доступен API**

В `site_cart.html` найти место, где формируется кнопка `📝 Cerere de credit EasyCredit` (около строки 194), и обернуть её условием:

```javascript
  if (payMethod === 'credit' && !ecOrgOf(currentTile())) {
```

то есть старая кнопка показывается **только** когда у организации нет сконфигурированного провайдера.

- [ ] **Step 5: Продублировать флоу в карточке товара**

В `templates/biro26/shop.html` в блок `<div id="credit-box">` (строка ~303) добавить тот же HTML из Step 1 (с теми же id) и тот же JS из Step 2. В `shop.html` вызов `ecUI()` добавить в конец функции `creditUI()`. Кнопку `📝 Cerere de credit EasyCredit · Кредитная заявка` (строка ~920) обернуть тем же условием из Step 4.

- [ ] **Step 6: Проверить в браузере**

```bash
cd /Users/pt/Projects.AI/Artgranit && ./run_local.sh > /tmp/app_credit.log 2>&1 &
sleep 8
```

Сценарий А — провайдер выключен:
1. В бэк-офисе снять галочку «актив» у EasyCredit, сохранить.
2. Открыть витрину, положить товар в корзину, выбрать «Rate / credit».
3. Ожидается: формы IDNP нет, видна старая кнопка «Cerere de credit».

Сценарий Б — провайдер включён и привязан:
1. В бэк-офисе включить EasyCredit, заполнить креды, привязать к организации.
2. Повторить шаги витрины.
3. Ожидается: появилась форма ФИО/телефон/IDNP; «Verifică preaprobarea» возвращает либо зелёное «Preaprobat …», либо красную ошибку провайдера; старой кнопки нет.
4. Заполнить форму, нажать «Trimite cererea» → появляется `Referință: <URN>` и строка `Status: …`, обновляющаяся раз в 5 секунд.
5. В бэк-офисе на вкладке заявок эта заявка видна с `Ref` и `Status API`; кнопка 📋 показывает события `preapproved` / `submit` / `status`.

Проверить консоль браузера — JS-ошибок быть не должно. Проверить лог:

```bash
grep -i "traceback" /tmp/app_credit.log | tail -20
```

Ожидается: пусто.

Остановить приложение: `pkill -f "python app.py" || true`

- [ ] **Step 7: Commit**

```bash
cd /Users/pt/Projects.AI/Artgranit
git add templates/biro26/site_cart.html templates/biro26/shop.html
git commit -m "feat(biro26): витрина — кредитный флоу preapproved/submit/status при включённом провайдере

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

## Task 10: Документация и финальная верификация

**Files:**
- Modify: `docs/CREDITE/project_easycredit.html`
- Modify: `docs/CREDITE/project_iute.html`
- Modify: `README.md`
- Modify: `docs/Biro26/README_BIRO26.html`
- Modify: `test_biro26_smoke.py`

**Interfaces:**
- Consumes: всё предыдущее
- Produces: обновлённая документация

- [ ] **Step 1: Добавить проверку `TMS_CREDITE_*` в smoke-тест**

В `test_biro26_smoke.py` в список `REQUIRED` добавить шесть имён:

```python
REQUIRED = [
    "BIRO26_GOODS", "TMS_UNIVERS", "TMS_MPT", "TMS_UM",
    "VPR01M_GROUPS", "VPR1D_PRDATE", "TPR1D_PERPRLIST", "VTPR1D_PERPRLIST",
    "TMS_ORG", "TMS_SYSGRP",
    "TMS_CREDITE_PROVIDER", "TMS_CREDITE_PROVIDER_PARAM", "TMS_CREDITE_ORG",
    "TMS_CREDITE_PLAN", "TMS_CREDITE_REQ", "TMS_CREDITE_REQ_EVENT",
]
```

- [ ] **Step 2: Запустить smoke-тест**

```bash
cd /Users/pt/Projects.AI/Artgranit && ./venv/bin/python test_biro26_smoke.py
```

Ожидается: все объекты найдены, ни одного FAIL.

- [ ] **Step 3: Переписать `docs/CREDITE/project_easycredit.html`**

Сохранить существующие стили страницы (шапка, CSS, ссылку «Назад»). Заменить содержательную часть на разделы:

1. **Обзор** — EasyCredit Moldova, SOAP API, две точки применения: демо `/UNA.md/orasldev/credit-easycredit` (основной проект) и бэк-офис/витрина Biro26.
2. **SOAP-операции** — таблица: `Preapproved_v2.1` (проверка предодобренной суммы), `Request_v4_PJ` (подача заявки, возвращает URN), `URNStatus_v2` (статус по URN), `ClientInfo` (данные клиента). Для каждой — endpoint-суффикс `.svc`, SOAPAction, ключевые поля, ссылка на `integrations/easycredit_client.py`.
3. **Архитектура интеграции** — `CreditProvider` / `ProviderRegistry` (`integrations/base_provider.py`), `EasyCreditProvider`, `build_registry(settings_source)`; схема: клиент витрины → `/api/biro26/shop/credit/api/*` → `Biro26Credit` → `build_registry(biro26_settings())` → `EasyCreditProvider` → `easycredit_client` → SOAP.
4. **Хранение настроек** — таблица `TMS_CREDITE_PROVIDER` + `TMS_CREDITE_PROVIDER_PARAM`, перечень параметров (`api_user`, `api_password` — секретный), правило «пустой секрет = не менять», два независимых контура (ADB и 11g), фолбэк на `.env`. Явно отметить, что `data/easycredit_settings.json` — только seed.
5. **Схема `TMS_CREDITE_*`** — таблица всех шести объектов с назначением колонок (перенести из спеки, раздел 4).
6. **Настройка в бэк-офисе** — путь `/UNA.md/orasldev/biro26-credit-admin`, вкладка «Provideri API», шаги: включить → env → base_url → креды → «Test conexiune» → привязать провайдера к организации.
7. **Флоу на витрине** — четыре шага (форма → preapproved → submit → опрос status), поведение при выключенном/упавшем провайдере, дисклеймер об оценочности расчёта.
8. **API** — таблица роутов из Task 7 с телами запросов и ответов.
9. **Деплой** — `python deploy_credite_oracle.py --target both`, идемпотентность, что DDL не входит в `deploy_to_remote.sh`.
10. **Checklist верификации** — семь пунктов из раздела 10 спеки.

- [ ] **Step 4: Обновить `docs/CREDITE/project_iute.html`**

Заменить раздел о настройках: вместо `data/iute_settings.json` описать `TMS_CREDITE_PROVIDER` с параметрами `api_key` (секретный), `pos_identifier`, `salesman_identifier`; добавить абзац о том, что Iute доступен на витрине Biro26 наравне с EasyCredit — при включении и привязке к организации; поставить ссылку на `project_easycredit.html` как на общее описание архитектуры провайдеров.

- [ ] **Step 5: Обновить `README.md` и `docs/Biro26/README_BIRO26.html`**

В `README.md` в раздел о модулях добавить подраздел «Кредитование (TMS_CREDITE_*)»: назначение, список таблиц, ссылки на `/UNA.md/orasldev/docs/easycredit` и `/UNA.md/orasldev/biro26-credit-admin`, команду деплоя.

В `docs/Biro26/README_BIRO26.html` добавить блок «Creditare / Кредитование» с теми же сведениями и ссылкой на страницу документации EasyCredit.

- [ ] **Step 6: Проверить, что страницы документации открываются**

```bash
cd /Users/pt/Projects.AI/Artgranit && ./run_local.sh > /tmp/app_credit.log 2>&1 &
sleep 8
for u in docs/easycredit docs/iute biro26-credit-admin; do
  printf '%-24s ' "$u"
  curl -s -o /dev/null -w '%{http_code}\n' "http://127.0.0.1:3003/UNA.md/orasldev/$u"
done
pkill -f "python app.py" || true
```

Ожидается: для всех трёх — `200` или `302` (редирект на `/login`, если сессия не установлена). Код `404` означает, что путь всё ещё неверен.

- [ ] **Step 7: Прогнать все тесты**

```bash
cd /Users/pt/Projects.AI/Artgranit
./venv/bin/python test_credite_settings.py && \
./venv/bin/python test_biro26_credite.py && \
./venv/bin/python test_biro26_smoke.py
```

Ожидается: `8/8 passed`, `6/6 passed`, smoke без FAIL.

- [ ] **Step 8: Commit**

```bash
cd /Users/pt/Projects.AI/Artgranit
git add docs/CREDITE/project_easycredit.html docs/CREDITE/project_iute.html \
        README.md docs/Biro26/README_BIRO26.html test_biro26_smoke.py
git commit -m "docs(credite): документация EasyCredit/Iute — TMS_CREDITE_*, бэк-офис Biro26, флоу витрины

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

- [ ] **Step 9: Remote deploy**

```bash
cd /Users/pt/Projects.AI/Artgranit && ./deploy_to_remote.sh
```

Затем развернуть Oracle-объекты на remote (код деплой их не создаёт):

```bash
ssh -i ~/.ssh/artgranit-oci.key ubuntu@92.5.3.187 \
  'cd /home/ubuntu/artgranit && ./venv/bin/python deploy_credite_oracle.py --target both'
```

Ожидается: `OK: все 6 таблиц на месте` для обоих target.

- [ ] **Step 10: Верификация production**

```bash
ssh -i ~/.ssh/artgranit-oci.key ubuntu@92.5.3.187 'sudo systemctl restart artgranit && sleep 5 && sudo systemctl is-active artgranit'
curl -s -o /dev/null -w 'local flask: %{http_code}\n' -I https://nufarul.eminescu.md/login
curl -I https://nufarul.eminescu.md/login 2>&1 | head -3
curl -s -o /dev/null -w 'docs/easycredit: %{http_code}\n' https://nufarul.eminescu.md/UNA.md/orasldev/docs/easycredit
```

Ожидается: `active`; `HTTP/2 200` для `/login`; для `docs/easycredit` — `200` или `302` (редирект на логин), но **не** `404` и не `502`.

Если `/login` отдаёт `502`/`504` — немедленно откатиться и восстанавливать production до продолжения любой другой работы (см. CLAUDE.md, критический инвариант).

---

## Self-Review

**Покрытие спеки:**

| Раздел спеки | Задача |
|---|---|
| 4. Схема данных + миграция | Task 2 |
| 5. `models/credite_settings.py` | Task 3 |
| 5. `config.py` | Task 4 |
| 5. `integrations/` | Task 5 |
| 5. `models/biro26_credit.py` | Task 6 |
| 5. `app.py` роуты | Task 7 |
| 6. Бэк-офис | Task 8 |
| 7. Фронт-офис | Task 9 |
| 8. Документация (+ фикс роутов) | Task 1, Task 10 |
| 9. Деплой | Task 2 (скрипт), Task 10 (запуск) |
| 10. Тесты и checklist | Tasks 3, 6, 10 |

**Согласованность имён:** `CrediteSettings.get/save/masked/is_configured/invalidate`, `CrediteBackend.query/dml`, `build_registry`, `Biro26Credit.providers_list/provider_save/provider_test/api_preapproved/api_submit/api_status/request_events` — используются одинаково во всех задачах, где встречаются.

**Решение по получению ID заявки:** `api_submit` резервирует ID через `SELECT TMS_CREDITE_REQ_SEQ.NEXTVAL FROM dual` до INSERT и вставляет его явно. `RETURNING ID INTO` использовать нельзя — subprocess-worker (`models/biro26_worker.py`) не поддерживает OUT-бинды. Существующий `request_create` продолжает использовать `SELECT MAX(ID)`; менять его в рамках этой работы не требуется, но при следующем касании его стоит перевести на тот же приём.
