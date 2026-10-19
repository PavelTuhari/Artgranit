# UNA.md/PECO Data Source for Planograms — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `UNA.md/PECO` as a second supported data source for the Planograms module, so the module can render the real 46-station fuel network from `PECO_*` tables instead of the demo dataset.

**Architecture:** A `PlanogramDataSource` ABC in `models/plg_datasource.py` with two implementations — `DemoDataSource` (delegates to the controller's existing PLG queries, behaviour unchanged) and `PecoDataSource` (reads `PECO_STATIONS`/`PECO_TANKS`/`PECO_REF_FUEL_GRADES`/`PECO_PRICES` directly). `PlanogramController` normalizes a new `?source=` query parameter exactly like the existing `?lang=`, then dispatches through a factory. PECO SQL aliases single-language columns into the `_RU/_RO/_EN` triple (`s.NAME AS NAME_RU, …`) so the existing `_localize()` path produces the `name`/`address` keys the frontend already reads — no frontend rendering logic changes, only one line in the `api()` helper plus a source switcher.

**Tech Stack:** Python 3.12, Flask, Oracle (python-oracledb thin mode via `models/database.py`), pytest 9.0.2, vanilla JS template (`templates/planograms.html`).

## Global Constraints

- **Read-only.** No writes to `PECO_*` from the Planograms module. Price/shift/delivery edits stay in `peco-admin`, `peco-shift`, `peco-pump`.
- **No new Oracle DDL.** Only existing tables and views are used. No file added to `sql/`, no change to `deploy_oracle_objects.py`.
- **No second source of truth.** PECO data is read live; it is never copied into `PLG_*` tables.
- **Production invariant:** after any remote deploy, `curl -I https://nufarul.eminescu.md/login` must return `HTTP/2 200` (`CLAUDE.md`).
- **Source codes are exactly `demo` and `peco`**; default is `demo`. Unknown value falls back to `demo` (same contract as `PlanogramController.lang`).
- **Late imports** inside methods are the established pattern for cross-module access here (see `models/credite_settings.py:82-84`) — use them to avoid circular imports.
- **Tests:** plain pytest, module-level `def test_*()`, Oracle fully mocked via `unittest.mock.patch`, no fixtures, no conftest. Run from repo root with `./venv/bin/python -m pytest`.
- **Test docstrings in Russian**, explaining the business reason for the assertion (repo convention, `tests/test_peco.py`).
- Work happens on the current branch `feat/peco` in `/Users/pt/Projects.AI/Artgranit`.

---

## File Structure

| File | Responsibility |
|---|---|
| `models/plg_datasource.py` (create) | `PlanogramDataSource` ABC, `DemoDataSource`, `PecoDataSource`, `get_data_source()` factory. All PECO→Planogram mapping SQL lives here. |
| `controllers/planogram_controller.py` (modify) | `SOURCES`/`DEFAULT_SOURCE` constants, `source()` normalizer, `source` parameter on the three serving methods, dispatch through the factory. Existing demo SQL bodies move into private `_*_demo` statics, unchanged. |
| `app.py` (modify) | `_plg_source()` helper next to `_plg_lang()`; pass it to the three routes. |
| `templates/planograms.html` (modify) | Append `&source=` in the `api()` helper; render a source switcher mirroring the language switcher. |
| `tests/test_plg_datasource.py` (create) | Unit tests for normalizer, factory, PECO SQL shape, and returned dict keys. |
| `docs/Planograms/PLANOGRAMS_MODULE.md` (modify) | New section «Источники данных». |
| `README.md` (modify) | Module entry updated per `CLAUDE.md` §5. |

### Concept mapping (locked in — used verbatim by `PecoDataSource`)

| Planograms | PECO | Note |
|---|---|---|
| Store | `PECO_STATIONS` (`ACTIVE = 1`) | 46 АЗС |
| Product | `PECO_REF_FUEL_GRADES` | no numeric PK → id synthesized with `ROW_NUMBER()` |
| Product price | `PECO_PRICES` `VALID_TO IS NULL` | network-wide `AVG` (product list has no store context) |
| Zone | fuel grade present at the station | one per tank, carries `FILL_PCT` as traffic |
| Fixture | `PECO_TANKS` (`ACTIVE = 1`) | capacity/current from `V_PECO_TANK_LEVELS` |
| Map geometry | — | synthesized deterministically from tank ordinal (PECO has no `POS_X/POS_Y`) |

---

## Task 1: Data-source ABC, factory, and source normalizer

**Files:**
- Create: `models/plg_datasource.py`
- Modify: `controllers/planogram_controller.py` (add `SOURCES`, `DEFAULT_SOURCE`, `source()` after the existing `lang()` at lines 31-41)
- Test: `tests/test_plg_datasource.py`

**Interfaces:**
- Consumes: nothing (first task).
- Produces:
  - `models.plg_datasource.PlanogramDataSource` — ABC with `id: str` and abstract methods `list_stores(self, lang: str, dataset_id: Optional[int] = None) -> Dict`, `list_products(self, lang: str, category_id: Optional[int] = None, search: Optional[str] = None) -> Dict`, `store_map(self, lang: str, store_id: Optional[int] = None) -> Dict`
  - `models.plg_datasource.DemoDataSource` (`id = "demo"`), `models.plg_datasource.PecoDataSource` (`id = "peco"`)
  - `models.plg_datasource.get_data_source(source: str) -> PlanogramDataSource`
  - `PlanogramController.SOURCES = ('demo', 'peco')`, `PlanogramController.DEFAULT_SOURCE = 'demo'`, `PlanogramController.source(value: Optional[str]) -> str`

- [ ] **Step 1: Write the failing test**

Create `tests/test_plg_datasource.py`:

```python
"""Модуль «Планограммы» — источники данных (Oracle полностью замокан)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch, MagicMock

from controllers.planogram_controller import PlanogramController
from models.plg_datasource import (DemoDataSource, PecoDataSource,
                                   PlanogramDataSource, get_data_source)


def _fake_db(query_result):
    """Контекст-менеджер, отдающий db с заданным ответом execute_query."""
    db = MagicMock()
    db.execute_query.return_value = query_result
    cm = MagicMock()
    cm.__enter__.return_value = db
    cm.__exit__.return_value = False
    return cm, db


# ── нормализация параметра источника ─────────────────────────────────

def test_source_normalizer_accepts_known_codes():
    """Оба поддерживаемых источника проходят как есть."""
    assert PlanogramController.source('demo') == 'demo'
    assert PlanogramController.source('peco') == 'peco'


def test_unknown_source_falls_back_to_demo():
    """Неизвестный источник не должен ронять модуль — как и неизвестный язык."""
    assert PlanogramController.source('oracle-of-delphi') == 'demo'
    assert PlanogramController.source('') == 'demo'
    assert PlanogramController.source(None) == 'demo'


def test_source_normalizer_is_case_insensitive():
    """Ссылку с ?source=PECO пользователь может прислать из письма."""
    assert PlanogramController.source('PECO') == 'peco'
    assert PlanogramController.source('  Peco ') == 'peco'


# ── фабрика ──────────────────────────────────────────────────────────

def test_factory_returns_matching_implementation():
    assert isinstance(get_data_source('demo'), DemoDataSource)
    assert isinstance(get_data_source('peco'), PecoDataSource)


def test_factory_defaults_to_demo_on_unknown_source():
    """Фабрика повторяет контракт нормализатора, а не падает."""
    assert isinstance(get_data_source('nonsense'), DemoDataSource)


def test_both_sources_implement_the_interface():
    """Оба источника обязаны отвечать на один и тот же контракт."""
    for impl in (DemoDataSource(), PecoDataSource()):
        assert isinstance(impl, PlanogramDataSource)
        for method in ('list_stores', 'list_products', 'store_map'):
            assert callable(getattr(impl, method))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/pt/Projects.AI/Artgranit && ./venv/bin/python -m pytest tests/test_plg_datasource.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'models.plg_datasource'`

- [ ] **Step 3: Create the data-source module**

Create `models/plg_datasource.py`:

```python
"""Источники данных модуля «Планограммы».

Модуль поддерживает два источника:

  demo — демонстрационный набор PLG_* (PLG_DATASETS.CODE = 'DEMO');
  peco — реальная сеть АЗС проекта PECO, объекты PECO_* читаются напрямую.

Дублировать станции и резервуары в PLG_* нельзя: это завело бы второй
источник правды по остаткам топлива — ровно то, что запрещает CLAUDE.md.
Поэтому источник peco читает PECO_* «как есть», а совпадение форматов
ответа обеспечивается алиасами в SQL: одноязычные колонки PECO
раскладываются в тройку NAME_RU/NAME_RO/NAME_EN, которую уже умеет
разворачивать PlanogramController._localize().

Источник peco доступен только на чтение. Цены, смены и приёмка цистерн
остаются за интерфейсами PECO (peco-admin, peco-shift, peco-pump).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class PlanogramDataSource(ABC):
    """Контракт источника данных для витрины планограмм.

    Все методы возвращают тот же формат, что и одноимённые методы
    PlanogramController: {"success": bool, "data": ..., "lang": str}
    либо {"success": False, "error": str}.
    """

    id: str = "abstract"

    @abstractmethod
    def list_stores(self, lang: str, dataset_id: Optional[int] = None) -> Dict:
        """Список торговых точек источника."""

    @abstractmethod
    def list_products(self, lang: str, category_id: Optional[int] = None,
                      search: Optional[str] = None) -> Dict:
        """Товарный справочник источника."""

    @abstractmethod
    def store_map(self, lang: str, store_id: Optional[int] = None) -> Dict:
        """План точки: зоны и оборудование в координатах карты."""


class DemoDataSource(PlanogramDataSource):
    """Демонстрационный набор PLG_*.

    Делегирует в PlanogramController — SQL демо-источника остаётся там,
    где был, поэтому поведение по умолчанию не меняется. Импорт локальный:
    контроллер сам импортирует этот модуль (тот же приём, что в
    models/credite_settings.py).
    """

    id = "demo"

    def list_stores(self, lang: str, dataset_id: Optional[int] = None) -> Dict:
        from controllers.planogram_controller import PlanogramController
        return PlanogramController._stores_demo(lang, dataset_id)

    def list_products(self, lang: str, category_id: Optional[int] = None,
                      search: Optional[str] = None) -> Dict:
        from controllers.planogram_controller import PlanogramController
        return PlanogramController._products_demo(lang, category_id, search)

    def store_map(self, lang: str, store_id: Optional[int] = None) -> Dict:
        from controllers.planogram_controller import PlanogramController
        return PlanogramController._store_map_demo(lang, store_id)


class PecoDataSource(PlanogramDataSource):
    """Сеть АЗС проекта PECO (UNA.md/PECO), только чтение."""

    id = "peco"

    def list_stores(self, lang: str, dataset_id: Optional[int] = None) -> Dict:
        raise NotImplementedError

    def list_products(self, lang: str, category_id: Optional[int] = None,
                      search: Optional[str] = None) -> Dict:
        raise NotImplementedError

    def store_map(self, lang: str, store_id: Optional[int] = None) -> Dict:
        raise NotImplementedError


#: Реестр источников: единственное место, где перечислены реализации.
_SOURCES: Dict[str, Any] = {
    DemoDataSource.id: DemoDataSource,
    PecoDataSource.id: PecoDataSource,
}


def get_data_source(source: str) -> PlanogramDataSource:
    """Реализация источника по коду. Неизвестный код -> демо."""
    return _SOURCES.get(source, DemoDataSource)()
```

- [ ] **Step 4: Add the source normalizer to the controller**

In `controllers/planogram_controller.py`, immediately after the existing `DEFAULT_LANG = 'ru'` (line 32), add:

```python
    SOURCES = ('demo', 'peco')
    DEFAULT_SOURCE = 'demo'
```

and immediately after the existing `lang()` static method (ends line 41), add:

```python
    @staticmethod
    def source(value: Optional[str]) -> str:
        """Нормализует код источника данных. Неизвестный -> источник по умолчанию.

        Контракт повторяет lang(): неизвестное значение не ошибка, а откат
        на демо-набор, иначе ссылка с опечаткой роняла бы весь модуль.
        """
        code = (value or '').strip().lower()
        return code if code in PlanogramController.SOURCES else PlanogramController.DEFAULT_SOURCE
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/pt/Projects.AI/Artgranit && ./venv/bin/python -m pytest tests/test_plg_datasource.py -v`
Expected: PASS, 6 passed

- [ ] **Step 6: Verify the app still imports**

Run: `cd /Users/pt/Projects.AI/Artgranit && ./venv/bin/python -c "import app; print('ok')"`
Expected: `ok`

- [ ] **Step 7: Commit**

```bash
cd /Users/pt/Projects.AI/Artgranit
git add models/plg_datasource.py controllers/planogram_controller.py tests/test_plg_datasource.py
git commit -m "feat(plg): add data-source abstraction and ?source= normalizer"
```

---

## Task 2: Move demo bodies behind private statics

**Files:**
- Modify: `controllers/planogram_controller.py` — `get_stores` (178-198), `get_store_map` (273-300), `get_products` (441-462)
- Test: `tests/test_plg_datasource.py`

**Interfaces:**
- Consumes: `PlanogramController.source()` and `get_data_source()` from Task 1.
- Produces: `PlanogramController._stores_demo(lang, dataset_id)`, `PlanogramController._products_demo(lang, category_id, search)`, `PlanogramController._store_map_demo(lang, store_id)` — the existing SQL bodies, verbatim, now callable by `DemoDataSource`. Public `get_stores`/`get_products`/`get_store_map` gain a trailing `source` parameter and dispatch through the factory.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_plg_datasource.py`:

```python
# ── диспетчеризация контроллера по источнику ─────────────────────────

def test_get_stores_defaults_to_demo_sql():
    """Без ?source= поведение обязано остаться прежним — PLG_STORES."""
    cm, db = _fake_db({"success": True, "columns": ["ID", "CODE"], "data": [(1, "MD-CHS-024")]})
    with patch("controllers.planogram_controller.DatabaseModel", return_value=cm):
        r = PlanogramController.get_stores('ru')
    assert r["success"] is True
    sql = db.execute_query.call_args[0][0]
    assert "PLG_STORES" in sql
    assert "PECO_STATIONS" not in sql


def test_get_stores_with_peco_source_queries_peco_stations():
    """При source=peco витрина обязана читать станции PECO, а не демо-магазины."""
    cm, db = _fake_db({"success": True, "columns": ["ID", "CODE"], "data": [(1, "AZS-001")]})
    with patch("models.plg_datasource.DatabaseModel", return_value=cm):
        r = PlanogramController.get_stores('ru', None, 'peco')
    assert r["success"] is True
    sql = db.execute_query.call_args[0][0]
    assert "PECO_STATIONS" in sql
    assert "PLG_STORES" not in sql


def test_unknown_source_still_serves_demo_data():
    """Опечатка в ?source= не должна оставлять пользователя с пустым экраном."""
    cm, db = _fake_db({"success": True, "columns": ["ID"], "data": [(1,)]})
    with patch("controllers.planogram_controller.DatabaseModel", return_value=cm):
        r = PlanogramController.get_stores('ru', None, 'nonsense')
    assert r["success"] is True
    assert "PLG_STORES" in db.execute_query.call_args[0][0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/pt/Projects.AI/Artgranit && ./venv/bin/python -m pytest tests/test_plg_datasource.py -v -k source`
Expected: FAIL — `test_get_stores_with_peco_source_queries_peco_stations` raises `NotImplementedError`

- [ ] **Step 3: Rename the three demo bodies and add dispatch**

In `controllers/planogram_controller.py`, rename `get_stores` (line 178) to `_stores_demo` and change its signature — **the body stays byte-for-byte identical**:

```python
    @staticmethod
    def _stores_demo(lang: str, dataset_id: Optional[int] = None) -> Dict:
        """Демо-источник: магазины из PLG_STORES."""
        lang = PlanogramController.lang(lang)
        sql = ("SELECT s.ID, s.CODE, s.NAME_RU, s.NAME_RO, s.NAME_EN, s.CITY, "
               "s.ADDRESS_RU, s.ADDRESS_RO, s.ADDRESS_EN, s.AREA_SQM, s.MAP_WIDTH, s.MAP_HEIGHT, "
               "s.CHECKOUT_QTY, s.MANAGER_NAME, s.STATUS, s.STORE_FORMAT, s.DATASET_ID, "
               "(SELECT COUNT(*) FROM PLG_ZONES z WHERE z.STORE_ID = s.ID) AS ZONE_COUNT "
               "FROM PLG_STORES s WHERE s.STATUS <> 'inactive'")
        params: Dict[str, Any] = {}
        if dataset_id:
            sql += " AND s.DATASET_ID = :p_ds"
            params["p_ds"] = int(dataset_id)
        try:
            with DatabaseModel() as db:
                r = db.execute_query(sql + " ORDER BY ZONE_COUNT DESC, s.CODE", params)
                if not r.get("success"):
                    return PlanogramController._fail(r)
                return {"success": True, "data": PlanogramController._localized(r, lang), "lang": lang}
        except Exception as e:
            return {"success": False, "error": str(e)}
```

Then add the new public dispatcher directly above it:

```python
    @staticmethod
    def get_stores(lang: str = DEFAULT_LANG, dataset_id: Optional[int] = None,
                   source: str = DEFAULT_SOURCE) -> Dict:
        from models.plg_datasource import get_data_source
        return get_data_source(PlanogramController.source(source)).list_stores(
            PlanogramController.lang(lang), dataset_id)
```

Apply the identical treatment to `get_products` (441) → `_products_demo(lang, category_id, search)` and `get_store_map` (273) → `_store_map_demo(lang, store_id)`. Note the argument order changes to put `lang` first, matching the ABC:

```python
    @staticmethod
    def get_products(category_id: Optional[int] = None, search: Optional[str] = None,
                     lang: str = DEFAULT_LANG, source: str = DEFAULT_SOURCE) -> Dict:
        from models.plg_datasource import get_data_source
        return get_data_source(PlanogramController.source(source)).list_products(
            PlanogramController.lang(lang), category_id, search)

    @staticmethod
    def _products_demo(lang: str, category_id: Optional[int] = None,
                       search: Optional[str] = None) -> Dict:
        """Демо-источник: товары из V_PLG_PRODUCTS."""
        # ← существующее тело get_products без изменений, начиная с
        #    `lang = PlanogramController.lang(lang)`
```

```python
    @staticmethod
    def get_store_map(store_id: Optional[int] = None, lang: str = DEFAULT_LANG,
                      source: str = DEFAULT_SOURCE) -> Dict:
        from models.plg_datasource import get_data_source
        return get_data_source(PlanogramController.source(source)).store_map(
            PlanogramController.lang(lang), store_id)

    @staticmethod
    def _store_map_demo(lang: str, store_id: Optional[int] = None) -> Dict:
        """Демо-источник: зоны и оборудование из V_PLG_ZONES / V_PLG_FIXTURES."""
        # ← существующее тело get_store_map без изменений
```

- [ ] **Step 4: Give PecoDataSource a temporary station query so the dispatch test passes**

In `models/plg_datasource.py`, add the import at the top of the module body:

```python
from models.database import DatabaseModel
```

and replace `PecoDataSource.list_stores` with:

```python
    def list_stores(self, lang: str, dataset_id: Optional[int] = None) -> Dict:
        sql = ("SELECT s.ID, s.CODE FROM PECO_STATIONS s "
               "WHERE s.ACTIVE = 1 ORDER BY s.CODE")
        try:
            with DatabaseModel() as db:
                r = db.execute_query(sql, {})
                if not r.get("success"):
                    return {"success": False, "error": r.get("message") or "query failed"}
                cols = [c.lower() for c in (r.get("columns") or [])]
                return {"success": True, "lang": lang,
                        "data": [dict(zip(cols, row)) for row in (r.get("data") or [])]}
        except Exception as e:
            return {"success": False, "error": str(e)}
```

(Task 3 replaces this with the full column mapping — it exists now only so the dispatch is testable end-to-end.)

- [ ] **Step 5: Run the full test file**

Run: `cd /Users/pt/Projects.AI/Artgranit && ./venv/bin/python -m pytest tests/test_plg_datasource.py -v`
Expected: PASS, 9 passed

- [ ] **Step 6: Verify no existing caller broke**

Run: `cd /Users/pt/Projects.AI/Artgranit && ./venv/bin/python -m pytest tests/ -q && ./venv/bin/python -c "import app; print('ok')"`
Expected: existing suite passes, then `ok`

- [ ] **Step 7: Commit**

```bash
cd /Users/pt/Projects.AI/Artgranit
git add controllers/planogram_controller.py models/plg_datasource.py tests/test_plg_datasource.py
git commit -m "refactor(plg): dispatch stores/products/map through data source"
```

---

## Task 3: PecoDataSource — stations as stores

**Files:**
- Modify: `models/plg_datasource.py` (`PecoDataSource.list_stores`)
- Test: `tests/test_plg_datasource.py`

**Interfaces:**
- Consumes: `PlanogramDataSource`, `DatabaseModel` (Task 1/2).
- Produces: `PecoDataSource._query(sql, params) -> List[Dict]` (shared helper, lowercased column keys, raises nothing — returns `[]` on empty) and a `list_stores` result whose rows carry the keys the frontend reads: `id, code, name, address, city, zone_count`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_plg_datasource.py`:

```python
# ── источник peco: станции как «магазины» ────────────────────────────

_PECO_STORE_COLS = ["ID", "CODE", "NAME_RU", "NAME_RO", "NAME_EN", "CITY",
                    "ADDRESS_RU", "ADDRESS_RO", "ADDRESS_EN", "AREA_SQM",
                    "MAP_WIDTH", "MAP_HEIGHT", "CHECKOUT_QTY", "MANAGER_NAME",
                    "STATUS", "STORE_FORMAT", "DATASET_ID", "ZONE_COUNT"]
_PECO_STORE_ROW = (7, "AZS-014", "АЗС Бэлць-2", "АЗС Бэлць-2", "АЗС Бэлць-2",
                   "Бэлць", "ул. Индепенденцей, 12", "ул. Индепенденцей, 12",
                   "ул. Индепенденцей, 12", None, 780, 460, None, None,
                   "active", "azs", None, 4)


def test_peco_stores_expose_frontend_keys():
    """Витрина читает s.name/s.address — источник обязан их отдать,
    хотя в PECO_STATIONS одна колонка NAME без языковых вариантов."""
    cm, _ = _fake_db({"success": True, "columns": _PECO_STORE_COLS,
                      "data": [_PECO_STORE_ROW]})
    with patch("models.plg_datasource.DatabaseModel", return_value=cm):
        r = PecoDataSource().list_stores('ru')
    row = r["data"][0]
    assert r["success"] is True
    assert row["id"] == 7 and row["code"] == "AZS-014"
    assert row["name"] == "АЗС Бэлць-2"
    assert row["address"] == "ул. Индепенденцей, 12"
    assert row["zone_count"] == 4


def test_peco_stores_skip_inactive_stations():
    """Закрытая АЗС не должна попадать в выбор точек."""
    cm, db = _fake_db({"success": True, "columns": _PECO_STORE_COLS, "data": []})
    with patch("models.plg_datasource.DatabaseModel", return_value=cm):
        PecoDataSource().list_stores('ru')
    assert "s.ACTIVE = 1" in db.execute_query.call_args[0][0]


def test_peco_stores_never_raise_on_db_error():
    """Недоступный Oracle обязан давать сообщение, а не трассировку в UI."""
    cm = MagicMock()
    cm.__enter__.side_effect = Exception("ORA-12541")
    with patch("models.plg_datasource.DatabaseModel", return_value=cm):
        r = PecoDataSource().list_stores('ru')
    assert r["success"] is False and "ORA-12541" in r["error"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/pt/Projects.AI/Artgranit && ./venv/bin/python -m pytest tests/test_plg_datasource.py -v -k peco_stores`
Expected: FAIL — `KeyError: 'name'` (the temporary Task-2 query selects only `ID, CODE`)

- [ ] **Step 3: Implement the shared helper and the full station mapping**

In `models/plg_datasource.py`, replace the whole `PecoDataSource` class body written so far with:

```python
class PecoDataSource(PlanogramDataSource):
    """Сеть АЗС проекта PECO (UNA.md/PECO), только чтение.

    Одноязычные колонки PECO раскладываются алиасами в тройку
    NAME_RU/NAME_RO/NAME_EN: так _localize() контроллера сам соберёт
    ключ `name`, и витрина не отличает источник от демо-набора.
    """

    id = "peco"

    #: Габариты синтетической карты станции (PECO не хранит координат).
    MAP_WIDTH = 780
    MAP_HEIGHT = 460

    @staticmethod
    def _query(sql: str, params: Optional[Dict[str, Any]] = None) -> list:
        """SELECT с ключами словарей в нижнем регистре.

        Бросает PecoSourceError, если execute_query вернул success=False:
        models.database.execute_query не бросает исключений сам, и без
        этой проверки ошибка SQL молча превратилась бы в пустой экран.
        """
        with DatabaseModel() as db:
            r = db.execute_query(sql, params or {})
        if not r.get("success"):
            raise PecoSourceError(r.get("message") or "query failed")
        cols = [c.lower() for c in (r.get("columns") or [])]
        return [dict(zip(cols, row)) for row in (r.get("data") or [])]

    def list_stores(self, lang: str, dataset_id: Optional[int] = None) -> Dict:
        """Станции сети как торговые точки витрины.

        dataset_id игнорируется: у источника peco нет тестовых наборов —
        это живая сеть, а не сгенерированные данные.
        """
        sql = (
            "SELECT s.ID, s.CODE, "
            "s.NAME AS NAME_RU, s.NAME AS NAME_RO, s.NAME AS NAME_EN, "
            "s.REGION AS CITY, "
            "s.ADDRESS AS ADDRESS_RU, s.ADDRESS AS ADDRESS_RO, s.ADDRESS AS ADDRESS_EN, "
            "CAST(NULL AS NUMBER) AS AREA_SQM, "
            + str(self.MAP_WIDTH) + " AS MAP_WIDTH, "
            + str(self.MAP_HEIGHT) + " AS MAP_HEIGHT, "
            "CAST(NULL AS NUMBER) AS CHECKOUT_QTY, "
            "CAST(NULL AS VARCHAR2(150)) AS MANAGER_NAME, "
            "'active' AS STATUS, 'azs' AS STORE_FORMAT, "
            "CAST(NULL AS NUMBER) AS DATASET_ID, "
            "(SELECT COUNT(*) FROM PECO_TANKS t "
            "  WHERE t.STATION_ID = s.ID AND t.ACTIVE = 1) AS ZONE_COUNT "
            "FROM PECO_STATIONS s WHERE s.ACTIVE = 1 ORDER BY s.CODE"
        )
        try:
            rows = self._query(sql)
        except Exception as e:
            return {"success": False, "error": str(e)}
        return {"success": True, "lang": lang,
                "data": localize_rows(rows, lang)}

    def list_products(self, lang: str, category_id: Optional[int] = None,
                      search: Optional[str] = None) -> Dict:
        raise NotImplementedError

    def store_map(self, lang: str, store_id: Optional[int] = None) -> Dict:
        raise NotImplementedError
```

Add above the classes, after the imports:

```python
class PecoSourceError(RuntimeError):
    """Ошибка чтения объектов PECO."""


def localize_rows(rows: list, lang: str, langs: tuple = ('ru', 'ro', 'en'),
                  default_lang: str = 'ru') -> list:
    """Разворачивает тройки <base>_ru/_ro/_en в сводный ключ <base>.

    Единственная реализация на проект: PlanogramController._localize
    делегирует сюда. Живёт в модели, потому что направление зависимостей
    «контроллер -> модель» разрешено, а обратное — нет.

    Исходные языковые колонки сохраняются: они нужны формам
    редактирования, где оператор правит все три языка сразу.
    """
    suffixes = tuple('_' + code for code in langs)
    out = []
    for row in rows:
        bases = {k[:-3] for k in row if k.endswith(suffixes)}
        new = dict(row)
        for base in bases:
            value = row.get(base + '_' + lang)
            if value in (None, ''):
                value = row.get(base + '_' + default_lang)
            new[base] = value
        out.append(new)
    return out
```

**Решение владельца (предполётная сверка):** дубля логики локализации быть
не должно. В том же шаге отредактируйте `controllers/planogram_controller.py`
так, чтобы существующий `_localize` делегировал в эту функцию, сохранив
свою сигнатуру и поведение:

```python
    @staticmethod
    def _localize(rows: List[Dict], lang: str) -> List[Dict]:
        """
        Добавляет к тройкам колонок `<base>_ru/_ro/_en` сводный ключ `<base>`
        на выбранном языке. Если перевода нет — подставляет русский вариант.
        Исходные языковые колонки сохраняются: они нужны формам редактирования,
        где оператор правит все три языка сразу.

        Реализация — models.plg_datasource.localize_rows: её же использует
        источник peco, и расходиться этим двум путям нельзя.
        """
        from models.plg_datasource import localize_rows
        return localize_rows(rows, lang, PlanogramController.LANGS,
                             PlanogramController.DEFAULT_LANG)
```

Дальше по плану вместо `_localize_rows(...)` вызывайте `localize_rows(...)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/pt/Projects.AI/Artgranit && ./venv/bin/python -m pytest tests/test_plg_datasource.py -v`
Expected: PASS, 12 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/pt/Projects.AI/Artgranit
git add models/plg_datasource.py tests/test_plg_datasource.py
git commit -m "feat(plg): map PECO stations onto the store list"
```

---

## Task 4: PecoDataSource — fuel grades as products

**Files:**
- Modify: `models/plg_datasource.py` (`PecoDataSource.list_products`)
- Test: `tests/test_plg_datasource.py`

**Interfaces:**
- Consumes: `PecoDataSource._query`, `localize_rows` (Task 3).
- Produces: `list_products` rows with keys `id, code, name, category, category_color, price, currency, uom, brand, barcode, status`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_plg_datasource.py`:

```python
# ── источник peco: сорта топлива как «товары» ────────────────────────

_PECO_PROD_COLS = ["ID", "CODE", "CATEGORY_ID", "CATEGORY_CODE",
                   "CATEGORY_RU", "CATEGORY_RO", "CATEGORY_EN", "CATEGORY_COLOR",
                   "NAME_RU", "NAME_RO", "NAME_EN", "BARCODE", "BRAND", "UOM",
                   "PRICE", "CURRENCY", "STATUS"]
_PECO_PROD_ROW = (2, "A95", None, "FUEL", "Топливо", "Combustibil", "Fuel",
                  "#43a047", "Бензин А-95", "Бензин А-95", "Бензин А-95",
                  None, None, "L", 23.90, "MDL", "active")


def test_peco_products_are_fuel_grades_with_current_price():
    """Товар источника peco — сорт топлива; цена берётся действующая."""
    cm, db = _fake_db({"success": True, "columns": _PECO_PROD_COLS,
                       "data": [_PECO_PROD_ROW]})
    with patch("models.plg_datasource.DatabaseModel", return_value=cm):
        r = PecoDataSource().list_products('ru')
    row = r["data"][0]
    assert r["success"] is True
    assert row["code"] == "A95" and row["name"] == "Бензин А-95"
    assert row["price"] == 23.90 and row["uom"] == "L"
    assert row["category"] == "Топливо"
    sql = db.execute_query.call_args[0][0]
    assert "VALID_TO IS NULL" in sql  # действующая цена, а не любая


def test_peco_products_synthesize_numeric_id():
    """PECO_REF_FUEL_GRADES ключуется кодом, а витрине нужен числовой id."""
    cm, db = _fake_db({"success": True, "columns": _PECO_PROD_COLS,
                       "data": [_PECO_PROD_ROW]})
    with patch("models.plg_datasource.DatabaseModel", return_value=cm):
        r = PecoDataSource().list_products('ru')
    assert r["data"][0]["id"] == 2
    assert "ROW_NUMBER()" in db.execute_query.call_args[0][0]


def test_peco_product_search_filters_by_name_and_code():
    """Поиск в витрине обязан работать и на источнике peco."""
    cm, db = _fake_db({"success": True, "columns": _PECO_PROD_COLS, "data": []})
    with patch("models.plg_datasource.DatabaseModel", return_value=cm):
        PecoDataSource().list_products('ru', None, 'дизель')
    sql, params = db.execute_query.call_args[0][0], db.execute_query.call_args[0][1]
    assert "LIKE :p_q" in sql
    assert params["p_q"] == "%ДИЗЕЛЬ%"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/pt/Projects.AI/Artgranit && ./venv/bin/python -m pytest tests/test_plg_datasource.py -v -k peco_product`
Expected: FAIL — `NotImplementedError`

- [ ] **Step 3: Implement `list_products`**

In `models/plg_datasource.py`, replace `PecoDataSource.list_products` with:

```python
    def list_products(self, lang: str, category_id: Optional[int] = None,
                      search: Optional[str] = None) -> Dict:
        """Сорта топлива как товарный справочник витрины.

        Цена — средняя действующая по сети: список товаров не привязан
        к станции (get_products не принимает store_id), а цены на АЗС
        различаются. Цену конкретной станции показывает план точки.

        category_id игнорируется: у источника peco одна категория —
        топливо, отдельного справочника категорий нет.
        """
        sql = (
            "SELECT ROW_NUMBER() OVER (ORDER BY g.SORT_ORDER, g.CODE) AS ID, "
            "g.CODE, "
            "CAST(NULL AS NUMBER) AS CATEGORY_ID, "
            "'FUEL' AS CATEGORY_CODE, "
            "'Топливо' AS CATEGORY_RU, 'Combustibil' AS CATEGORY_RO, 'Fuel' AS CATEGORY_EN, "
            "g.COLOR AS CATEGORY_COLOR, "
            "g.NAME AS NAME_RU, g.NAME AS NAME_RO, g.NAME AS NAME_EN, "
            "CAST(NULL AS VARCHAR2(40)) AS BARCODE, "
            "CAST(NULL AS VARCHAR2(150)) AS BRAND, "
            "'L' AS UOM, "
            "(SELECT ROUND(AVG(p.PRICE), 2) FROM PECO_PRICES p "
            "  WHERE p.GRADE_CODE = g.CODE AND p.VALID_TO IS NULL) AS PRICE, "
            "'MDL' AS CURRENCY, "
            "'active' AS STATUS "
            "FROM PECO_REF_FUEL_GRADES g WHERE 1 = 1"
        )
        params: Dict[str, Any] = {}
        if search:
            sql += " AND (UPPER(g.CODE) LIKE :p_q OR UPPER(g.NAME) LIKE :p_q)"
            params["p_q"] = "%" + search.strip().upper() + "%"
        try:
            rows = self._query(sql + " ORDER BY g.SORT_ORDER, g.CODE", params)
        except Exception as e:
            return {"success": False, "error": str(e)}
        return {"success": True, "lang": lang, "data": localize_rows(rows, lang)}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/pt/Projects.AI/Artgranit && ./venv/bin/python -m pytest tests/test_plg_datasource.py -v`
Expected: PASS, 15 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/pt/Projects.AI/Artgranit
git add models/plg_datasource.py tests/test_plg_datasource.py
git commit -m "feat(plg): map PECO fuel grades onto the product list"
```

---

## Task 5: PecoDataSource — station map from tanks

**Files:**
- Modify: `models/plg_datasource.py` (`PecoDataSource.store_map`)
- Test: `tests/test_plg_datasource.py`

**Interfaces:**
- Consumes: `PecoDataSource._query`, `localize_rows`, `PecoDataSource.MAP_WIDTH/MAP_HEIGHT`.
- Produces: `store_map` result `{"success": True, "lang": str, "data": {"store": {...}|None, "zones": [...], "fixtures": [...]}}`; zone rows carry `id, store_id, code, name, zone_type, color, pos_x, pos_y, width, height, sort_order, status, traffic_pct, fixture_count`; fixture rows carry `id, store_id, zone_id, code, name, fixture_type, pos_x, pos_y, width, height, shelf_count, status, item_count`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_plg_datasource.py`:

```python
# ── источник peco: план станции ──────────────────────────────────────

_PECO_TANK_COLS = ["TANK_ID", "STATION_ID", "STATION_CODE", "STATION_NAME",
                   "TANK_CODE", "GRADE_CODE", "GRADE_NAME", "CAPACITY_L",
                   "CURRENT_L", "MIN_ALARM_L", "FILL_PCT", "IS_LOW", "COLOR"]
_PECO_TANK_ROWS = [
    (11, 7, "AZS-014", "АЗС Бэлць-2", "T-1", "A95", "Бензин А-95",
     30000, 18450, 3000, 61.5, 0, "#43a047"),
    (12, 7, "AZS-014", "АЗС Бэлць-2", "T-2", "DIESEL", "Дизель",
     27000, 2100, 3000, 7.8, 1, "#455a64"),
]


def test_peco_store_map_builds_zone_and_fixture_per_tank():
    """Каждый резервуар — зона (сорт топлива) и оборудование (сам резервуар)."""
    cm, _ = _fake_db({"success": True, "columns": _PECO_TANK_COLS,
                      "data": _PECO_TANK_ROWS})
    with patch("models.plg_datasource.DatabaseModel", return_value=cm):
        r = PecoDataSource().store_map('ru', 7)
    data = r["data"]
    assert r["success"] is True
    assert len(data["zones"]) == 2 and len(data["fixtures"]) == 2
    assert data["zones"][0]["name"] == "Бензин А-95"
    assert data["fixtures"][0]["code"] == "T-1"
    assert data["fixtures"][0]["zone_id"] == data["zones"][0]["id"]


def test_peco_store_map_uses_fill_pct_as_traffic():
    """Наполненность резервуара — аналог проходимости зоны: она красит план."""
    cm, _ = _fake_db({"success": True, "columns": _PECO_TANK_COLS,
                      "data": _PECO_TANK_ROWS})
    with patch("models.plg_datasource.DatabaseModel", return_value=cm):
        r = PecoDataSource().store_map('ru', 7)
    assert r["data"]["zones"][0]["traffic_pct"] == 61.5
    assert r["data"]["zones"][1]["traffic_pct"] == 7.8


def test_peco_store_map_geometry_is_inside_the_canvas():
    """PECO не хранит координат — синтетическая раскладка обязана попадать
    в холст, иначе резервуары уедут за край плана."""
    cm, _ = _fake_db({"success": True, "columns": _PECO_TANK_COLS,
                      "data": _PECO_TANK_ROWS})
    with patch("models.plg_datasource.DatabaseModel", return_value=cm):
        r = PecoDataSource().store_map('ru', 7)
    for zone in r["data"]["zones"]:
        assert 0 <= zone["pos_x"] <= PecoDataSource.MAP_WIDTH - zone["width"]
        assert 0 <= zone["pos_y"] <= PecoDataSource.MAP_HEIGHT - zone["height"]


def test_peco_store_map_without_station_returns_empty_plan():
    """Сеть без активных станций не должна ронять экран плана."""
    cm, _ = _fake_db({"success": True, "columns": _PECO_TANK_COLS, "data": []})
    with patch("models.plg_datasource.DatabaseModel", return_value=cm):
        r = PecoDataSource().store_map('ru', None)
    assert r["success"] is True
    assert r["data"]["store"] is None
    assert r["data"]["zones"] == [] and r["data"]["fixtures"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/pt/Projects.AI/Artgranit && ./venv/bin/python -m pytest tests/test_plg_datasource.py -v -k store_map`
Expected: FAIL — `NotImplementedError`

- [ ] **Step 3: Implement `store_map`**

In `models/plg_datasource.py`, replace `PecoDataSource.store_map` with:

```python
    #: Синтетическая сетка плана: 4 колонки, шаг и габарит блока.
    GRID_COLS = 4
    CELL_W = 170
    CELL_H = 120
    BLOCK_W = 140
    BLOCK_H = 90
    MARGIN = 30

    def _slot(self, ordinal: int) -> Dict[str, int]:
        """Координаты блока по порядковому номеру резервуара (с нуля).

        PECO не хранит план станции, поэтому раскладка синтетическая, но
        детерминированная: один и тот же резервуар всегда занимает то же
        место, иначе план «прыгал» бы между обновлениями.
        """
        col, row = ordinal % self.GRID_COLS, ordinal // self.GRID_COLS
        return {"pos_x": self.MARGIN + col * self.CELL_W,
                "pos_y": self.MARGIN + row * self.CELL_H}

    def store_map(self, lang: str, store_id: Optional[int] = None) -> Dict:
        """План станции: сорт топлива — зона, резервуар — оборудование.

        Резервуар на станции ровно один на сорт (UQ_PECO_TANKS_ST_GR),
        поэтому зона и оборудование идут парой: зона отвечает за смысл
        (какое топливо), оборудование — за физику (ёмкость и остаток).
        """
        empty = {"store": None, "zones": [], "fixtures": []}
        sql = ("SELECT v.TANK_ID, v.STATION_ID, v.STATION_CODE, v.STATION_NAME, "
               "v.TANK_CODE, v.GRADE_CODE, v.GRADE_NAME, v.CAPACITY_L, "
               "v.CURRENT_L, v.MIN_ALARM_L, v.FILL_PCT, v.IS_LOW, g.COLOR "
               "FROM V_PECO_TANK_LEVELS v "
               "JOIN PECO_REF_FUEL_GRADES g ON g.CODE = v.GRADE_CODE ")
        params: Dict[str, Any] = {}
        if store_id:
            sql += "WHERE v.STATION_ID = :p_station "
            params["p_station"] = int(store_id)
        else:
            sql += ("WHERE v.STATION_ID = (SELECT MIN(ID) FROM PECO_STATIONS "
                    "                       WHERE ACTIVE = 1) ")
        try:
            rows = self._query(sql + "ORDER BY v.TANK_CODE", params)
        except Exception as e:
            return {"success": False, "error": str(e)}
        if not rows:
            return {"success": True, "lang": lang, "data": empty}

        first = rows[0]
        store = {"id": first["station_id"], "code": first["station_code"],
                 "name": first["station_name"], "address": None, "city": None,
                 "area_sqm": None, "map_width": self.MAP_WIDTH,
                 "map_height": self.MAP_HEIGHT, "checkout_qty": None,
                 "manager_name": None}

        zones, fixtures = [], []
        for i, t in enumerate(rows):
            slot = self._slot(i)
            zone_id = int(t["tank_id"])
            zones.append({
                "id": zone_id, "store_id": t["station_id"],
                "store_code": t["station_code"], "code": t["grade_code"],
                "zone_type": "fuel", "zone_type_name": "Топливо",
                "is_selling": 1, "category_id": None,
                "category": "Топливо", "name": t["grade_name"],
                "pos_x": slot["pos_x"], "pos_y": slot["pos_y"],
                "width": self.BLOCK_W, "height": self.BLOCK_H,
                "color": t.get("color"), "area_sqm": None,
                "sort_order": i, "status": "active",
                # наполненность резервуара занимает место проходимости:
                # это единственная величина плана, меняющаяся в реальном времени
                "traffic_pct": t.get("fill_pct"),
                "visitors": None, "dwell_sec": None, "pickups": None,
                "traffic_date": None,
                "traffic_level": "low" if t.get("is_low") else "normal",
                "fixture_count": 1,
            })
            fixtures.append({
                "id": zone_id, "store_id": t["station_id"],
                "store_code": t["station_code"], "zone_id": zone_id,
                "zone": t["grade_name"], "code": t["tank_code"],
                "fixture_type": "tank", "fixture_type_name": "Резервуар",
                "icon": "🛢", "name": t["tank_code"],
                "pos_x": slot["pos_x"] + 10, "pos_y": slot["pos_y"] + 26,
                "width": self.BLOCK_W - 20, "height": self.BLOCK_H - 40,
                "orientation": "H", "shelf_count": 1,
                "width_mm": None, "height_mm": None, "depth_mm": None,
                "serial_number": None, "status": "active",
                "created_at": None, "updated_at": None,
                "item_count": 1, "facing_count": 1,
                "capacity_l": t.get("capacity_l"),
                "current_l": t.get("current_l"),
                "fill_pct": t.get("fill_pct"),
                "is_low": t.get("is_low"),
            })
        return {"success": True, "lang": lang,
                "data": {"store": store, "zones": zones, "fixtures": fixtures}}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/pt/Projects.AI/Artgranit && ./venv/bin/python -m pytest tests/test_plg_datasource.py -v`
Expected: PASS, 19 passed

- [ ] **Step 5: Commit**

```bash
cd /Users/pt/Projects.AI/Artgranit
git add models/plg_datasource.py tests/test_plg_datasource.py
git commit -m "feat(plg): build station plan from PECO tanks"
```

---

## Task 6: Route wiring and the source switcher in the UI

**Files:**
- Modify: `app.py` — add `_plg_source()` after `_plg_lang()` (2746-2748); update routes `api_plg_stores` (2902-2906), `api_plg_map` (2917-2920), `api_plg_products` (2976-2980)
- Modify: `templates/planograms.html` — `api()` helper (1137-1151), `.sb-foot` block (269-281), CSS near the `.lang-switch` rules (71-77), state near line 1009, switcher JS near `renderLangSwitch`/`setLang` (1172-1192)
- Test: `tests/test_plg_datasource.py`

**Interfaces:**
- Consumes: `PlanogramController.source()`, `get_stores/get_products/get_store_map` with the `source` parameter (Tasks 1-5).
- Produces: `_plg_source()` in `app.py`; JS globals `SOURCE`, `setSource(code)`, `renderSourceSwitch()` in the template.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_plg_datasource.py`:

```python
# ── маршруты ─────────────────────────────────────────────────────────

def test_routes_pass_source_through_to_the_controller():
    """?source= обязан доезжать до контроллера на всех трёх маршрутах,
    иначе переключатель в витрине окажется декоративным."""
    import app as app_module
    client = app_module.app.test_client()
    for path, method in (('/api/plg/stores', 'get_stores'),
                         ('/api/plg/map', 'get_store_map'),
                         ('/api/plg/products', 'get_products')):
        with patch.object(app_module.PlanogramController, method,
                          return_value={"success": True, "data": []}) as m:
            client.get(path + '?source=peco')
        assert m.call_args.args[-1] == 'peco' or m.call_args.kwargs.get('source') == 'peco', \
            f"{path}: источник не передан в {method}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/pt/Projects.AI/Artgranit && ./venv/bin/python -m pytest tests/test_plg_datasource.py -v -k routes`
Expected: FAIL — the assertion fires: the routes still call the controller without a source argument

- [ ] **Step 3: Wire the routes**

In `app.py`, directly after `_plg_lang()` (line 2748), add:

```python
def _plg_source():
    """Источник данных модуля планограмм: ?source=demo|peco."""
    return PlanogramController.source(request.args.get('source'))
```

Update the three routes:

```python
@app.route('/api/plg/stores', methods=['GET'])
def api_plg_stores():
    return jsonify(PlanogramController.get_stores(
        _plg_lang(), request.args.get('dataset_id', type=int), _plg_source()))
```

```python
@app.route('/api/plg/map', methods=['GET'])
def api_plg_map():
    return jsonify(PlanogramController.get_store_map(
        request.args.get('store_id', type=int), _plg_lang(), _plg_source()))
```

```python
@app.route('/api/plg/products', methods=['GET'])
def api_plg_products():
    return jsonify(PlanogramController.get_products(
        request.args.get('category_id', type=int),
        request.args.get('q'), _plg_lang(), _plg_source()))
```

- [ ] **Step 4: Run the route test**

Run: `cd /Users/pt/Projects.AI/Artgranit && ./venv/bin/python -m pytest tests/test_plg_datasource.py -v`
Expected: PASS, 20 passed

- [ ] **Step 5: Send the source with every API call**

In `templates/planograms.html`, line 1009 area, add the state next to `LANG`:

```javascript
let SOURCE = localStorage.getItem('plg_source') || 'demo';
```

In the `api()` helper, change the fetch line (1146) from:

```javascript
        const res = await fetch(API + path + sep + 'lang=' + LANG, opts);
```

to:

```javascript
        const res = await fetch(API + path + sep + 'lang=' + LANG + '&source=' + SOURCE, opts);
```

- [ ] **Step 6: Render the switcher**

In `templates/planograms.html`, inside `.sb-foot` immediately above `<div class="lang-switch" id="langSwitch"></div>` (line 271), add:

```html
            <div class="src-switch" id="srcSwitch"></div>
```

Add CSS next to the `.lang-switch` rules (after line 77):

```css
.src-switch { display: flex; flex-direction: column; gap: 4px; margin-bottom: 10px; }
.src-btn {
    padding: 5px 8px; border-radius: 5px; border: 1px solid rgba(255,255,255,.12);
    background: transparent; color: var(--sidebar-fg); font-size: 11px; cursor: pointer;
    font-family: inherit; text-align: left;
}
.src-btn.active { background: var(--accent); border-color: var(--accent); color: #fff; font-weight: 700; }
.src-btn small { display: block; opacity: .7; font-size: 10px; }
```

Add the renderer and handler next to `renderLangSwitch`/`setLang` (after line 1192):

```javascript
// Поддерживаемые источники данных модуля.
const SOURCES = [
    {code: 'demo', title: 'Демо-набор', hint: 'учебные магазины PLG'},
    {code: 'peco', title: 'UNA.md/PECO', hint: 'сеть АЗС, реальные данные'}
];

function renderSourceSwitch() {
    document.getElementById('srcSwitch').innerHTML = SOURCES.map(s =>
        `<button class="src-btn ${s.code === SOURCE ? 'active' : ''}" onclick="setSource('${s.code}')">`
        + `${esc(s.title)}<small>${esc(s.hint)}</small></button>`
    ).join('');
}

async function setSource(code) {
    if (code === SOURCE) return;
    SOURCE = code;
    localStorage.setItem('plg_source', code);
    STORE_ID = null;              // точки другого источника — другие id
    renderSourceSwitch();
    await loadStores();
    await loadMap();
    reloadActive();
}
```

Call `renderSourceSwitch()` from `applyI18n()` right after the existing `renderLangSwitch()` call (line 1163):

```javascript
    renderLangSwitch();
    renderSourceSwitch();
```

- [ ] **Step 6a: Render fuel zones with their fill level**

Задача 5 кладёт наполненность резервуара в `traffic_pct` зоны, но в
SVG-отрисовке зон нет ветки для `zone_type === 'fuel'`: такие зоны
попадают в общий `else` и рисуются плоской коробкой — единственная живая
величина плана не видна. Добавьте ветку перед финальным `else` в
отрисовке зон (рядом с ветками `checkout` / `entrance`, примерно строка
1445 `templates/planograms.html`):

```javascript
        } else if (z.zone_type === 'fuel') {
            const pct = Math.max(0, Math.min(100, z.traffic_pct || 0));
            const low = z.traffic_level === 'low';
            parts.push(`<g class="zn" data-tip="${esc(tip)}">
                <rect x="${x}" y="${y}" width="${w}" height="${h}" rx="4"
                      fill="#16233a" stroke="${low ? '#dc2626' : '#2d3d55'}" stroke-width="${low ? 2 : 1}"/>
                <rect x="${x + 4}" y="${y + h - 12}" width="${w - 8}" height="7" rx="3" fill="#0f1929"/>
                <rect x="${x + 4}" y="${y + h - 12}" width="${(w - 8) * pct / 100}" height="7" rx="3"
                      fill="${z.color || (low ? '#dc2626' : '#2563eb')}"/>
                <text x="${x + w / 2}" y="${y + 16}" text-anchor="middle" fill="#cbd5e1"
                      font-size="9" font-weight="700">${esc(z.name)}</text>
                <text x="${x + w / 2}" y="${y + h - 18}" text-anchor="middle" fill="#94a3b8"
                      font-size="8">${pct}%</text>
            </g>`);
```

Красный резервуар (`traffic_level === 'low'`, то есть остаток ниже
аварийного) обводится и заливается красным — это тот же сигнал, что
`IS_LOW` в `V_PECO_TANK_LEVELS`. Визуальный контроль — в задаче 7.

- [ ] **Step 7: Verify the switcher is not caught by the demo write-guard**

Run: `cd /Users/pt/Projects.AI/Artgranit && grep -n "WRITE_RE" templates/planograms.html`
Confirm `setSource` does not match the pattern (it must not start with `save`/`delete`/etc., exactly as `setLang` does not). If it matches, rename the handler to `switchSource` and update both call sites.

- [ ] **Step 8: Run the whole suite and the import check**

Run: `cd /Users/pt/Projects.AI/Artgranit && ./venv/bin/python -m pytest tests/ -q && ./venv/bin/python -c "import app; print('ok')"`
Expected: suite passes, then `ok`

- [ ] **Step 9: Commit**

```bash
cd /Users/pt/Projects.AI/Artgranit
git add app.py templates/planograms.html tests/test_plg_datasource.py
git commit -m "feat(plg): add data source switcher to routes and UI"
```

---

## Task 7: Live verification and documentation

**Files:**
- Modify: `docs/Planograms/PLANOGRAMS_MODULE.md` (new section after §35)
- Modify: `README.md` (Planograms module entry)

**Interfaces:**
- Consumes: everything from Tasks 1-6.
- Produces: no code interfaces — documentation only.

- [ ] **Step 1: Start the app locally**

Run:
```bash
cd /Users/pt/Projects.AI/Artgranit && ./venv/bin/python app.py
```
Expected: server starts on port 3003 (`Config.SERVER_PORT`). Leave it running in a second shell for the next steps.

- [ ] **Step 2: Verify the demo source is unchanged**

Run: `curl -s 'http://127.0.0.1:3003/api/plg/stores?lang=ru' | head -c 400`
Expected: `{"success": true, ...}` with the familiar demo stores (`MD-CHS-024` etc.) — identical to the pre-change response.

- [ ] **Step 3: Verify the PECO source returns real stations**

Run:
```bash
curl -s 'http://127.0.0.1:3003/api/plg/stores?lang=ru&source=peco' | head -c 400
curl -s 'http://127.0.0.1:3003/api/plg/products?lang=ru&source=peco' | head -c 400
curl -s 'http://127.0.0.1:3003/api/plg/map?lang=ru&source=peco' | head -c 400
```
Expected: stations with `"code": "AZS-..."` and non-empty `"name"`; products listing fuel grades with a numeric `price`; a map with non-empty `zones` and `fixtures`.

If Oracle is unreachable locally, the responses will be `{"success": false, "error": "ORA-..."}` — that is an environment limitation, not a code failure. Record it explicitly in the commit message rather than claiming the check passed.

- [ ] **Step 4: Verify the switcher in the browser**

Open `http://127.0.0.1:3003/UNA.md/orasldev/planograms`, click «UNA.md/PECO» in the sidebar, and confirm: the store dropdown fills with АЗС, the plan renders tanks, and clicking «Демо-набор» restores the previous view. Take a screenshot of both states.

- [ ] **Step 5: Confirm no DDL was touched**

Run: `cd /Users/pt/Projects.AI/Artgranit && git diff --stat main...HEAD -- sql/ deploy_oracle_objects.py`
Expected: empty output (the Global Constraint «no new Oracle DDL» holds).

- [ ] **Step 6: Document the sources**

In `docs/Planograms/PLANOGRAMS_MODULE.md`, add after §35:

```markdown
## 36. Источники данных

Модуль поддерживает два источника; переключатель — в левой панели,
выбор запоминается в `localStorage` и едет параметром `?source=`
во всех запросах `/api/plg/*`.

| Код | Название | Данные |
|---|---|---|
| `demo` | Демо-набор | Учебные магазины `PLG_*` (`PLG_DATASETS.CODE = 'DEMO'`). Источник по умолчанию. |
| `peco` | UNA.md/PECO | Живая сеть АЗС проекта PECO: `PECO_STATIONS`, `PECO_TANKS`, `PECO_REF_FUEL_GRADES`, `PECO_PRICES`, `V_PECO_TANK_LEVELS`. |

Реализация — `models/plg_datasource.py`: интерфейс `PlanogramDataSource`
и две реализации (`DemoDataSource`, `PecoDataSource`), фабрика
`get_data_source()`. Контроллер нормализует код источника методом
`PlanogramController.source()` — по тому же контракту, что и `lang()`:
неизвестное значение откатывается на `demo`, а не роняет модуль.

### Соответствие понятий

| Планограммы | PECO |
|---|---|
| Магазин | Станция (`PECO_STATIONS`, `ACTIVE = 1`) |
| Товар | Сорт топлива (`PECO_REF_FUEL_GRADES`) |
| Зона | Сорт топлива на станции; проходимость зоны = наполненность резервуара |
| Оборудование | Резервуар (`PECO_TANKS`) |
| Цена товара | Средняя действующая по сети (`PECO_PRICES`, `VALID_TO IS NULL`) |

### Почему данные не копируются в PLG_*

Дублировать станции и резервуары означало бы завести второй источник
правды по остаткам топлива — ровно то, что запрещает `CLAUDE.md`.
Поэтому `PecoDataSource` читает объекты PECO напрямую, а совпадение
формата ответа обеспечивают алиасы в SQL: одноязычные колонки PECO
раскладываются в тройку `NAME_RU/NAME_RO/NAME_EN`, которую разворачивает
уже существующий `_localize()`. Витрина не отличает источник от демо —
менять логику отрисовки не понадобилось.

### Ограничения источника `peco`

* **Только чтение.** Цены, смены и приёмка цистерн остаются за
  интерфейсами PECO (`peco-admin`, `peco-shift`, `peco-pump`).
  Запись из витрины планограмм не предусмотрена.
* **План станции синтетический.** PECO не хранит координат оборудования,
  поэтому раскладка строится детерминированной сеткой по порядковому
  номеру резервуара — она читаема, но не отражает реальную геометрию
  площадки.
* **Цена в списке товаров — средняя по сети.** Список товаров не привязан
  к станции, а цены на АЗС различаются; цену конкретной станции
  показывает план точки.
* **Наборы тестовых данных (`dataset_id`) не применяются** — это живая
  сеть, а не сгенерированные данные.

Проектное решение: [`docs/superpowers/specs/2026-08-20-peco-data-source-design.md`](../superpowers/specs/2026-08-20-peco-data-source-design.md).
```

- [ ] **Step 7: Update README**

In `README.md`, find the Planograms module entry and add one line to it:

```markdown
Источники данных: `demo` (учебные магазины) и `UNA.md/PECO` (живая сеть АЗС,
только чтение) — переключатель в левой панели, см.
[docs/Planograms/PLANOGRAMS_MODULE.md](docs/Planograms/PLANOGRAMS_MODULE.md) §36.
```

- [ ] **Step 8: Commit**

```bash
cd /Users/pt/Projects.AI/Artgranit
git add docs/Planograms/PLANOGRAMS_MODULE.md README.md
git commit -m "docs(plg): document demo and UNA.md/PECO data sources"
```

---

## Acceptance criteria (from the spec)

1. `/UNA.md/orasldev/planograms?source=peco` serves the real stations from `PECO_STATIONS` — Task 6 Step 4, Task 7 Step 3.
2. Switching back to `source=demo` preserves the previous behaviour — Task 2 Step 1 (`test_get_stores_defaults_to_demo_sql`), Task 7 Step 2.
3. Products under `source=peco` are fuel grades with the current station price — Task 4.
4. No new Oracle DDL — Task 7 Step 5.
5. After any remote deploy: `curl -I https://nufarul.eminescu.md/login` → `HTTP/2 200`. **This plan does not deploy.** Deployment is a separate, explicitly-requested step; if it is requested, follow `CLAUDE.md` «Деплой: не отправлять `app.py` вслепую» — the patch must carry `app.py` together with `controllers/`, `models/`, `templates/`.

## Out of scope

- Writes to `PECO_*` from the Planograms module.
- Project B (planogram3d autoorder visualization) — separate plan after this one lands.
- A `source` column/setting persisted server-side: the parameter is per-request, matching the existing `dataset_id` and `lang` conventions.
