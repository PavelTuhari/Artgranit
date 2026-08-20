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
