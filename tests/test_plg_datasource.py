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
