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


def test_peco_product_id_is_stable_regardless_of_search_filter():
    """id сорта топлива не должен «прыгать» от строки поиска.

    ROW_NUMBER() раньше считался после WHERE: сузил список поиском — id
    сместился, хотя открыт тот же сорт топлива. id используется в ссылке
    PUT/DELETE и как ключ строки на витрине, поэтому обязан оставаться
    равным номеру строки в полном, нефильтрованном перечне сортов.
    """
    cm, db = _fake_db({"success": True, "columns": _PECO_PROD_COLS,
                       "data": [_PECO_PROD_ROW]})
    with patch("models.plg_datasource.DatabaseModel", return_value=cm):
        PecoDataSource().list_products('ru', None, 'а-95')
    sql = db.execute_query.call_args[0][0]
    # Нумерация обязана происходить в inline view до применения фильтра:
    # WHERE поиска стоит снаружи, ROW_NUMBER() — внутри вложенного запроса.
    inner_end = sql.index(') v WHERE')
    assert 'ROW_NUMBER()' in sql[:inner_end]
    assert 'LIKE :p_q' in sql[inner_end:]


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


def test_peco_store_map_filters_active_station_with_explicit_id():
    """Ветка с явным store_id обязана фильтровать ACTIVE так же, как ветка
    без аргумента — иначе устаревшая закладка/ссылка отрисует план
    закрытой АЗС, как будто она всё ещё работает."""
    cm, db = _fake_db({"success": True, "columns": _PECO_TANK_COLS, "data": []})
    with patch("models.plg_datasource.DatabaseModel", return_value=cm):
        PecoDataSource().store_map('ru', 7)
    sql = db.execute_query.call_args[0][0]
    assert "s.ACTIVE = 1" in sql
    assert "PECO_STATIONS" in sql


_PECO_TANK_COLS_ADDR = _PECO_TANK_COLS + ["STATION_ADDRESS", "STATION_REGION"]
_PECO_TANK_ROWS_ADDR = [row + ("ул. Индепенденцей, 12", "Бэлць") for row in _PECO_TANK_ROWS]


def test_peco_store_map_surfaces_station_address():
    """Заголовок плана должен показывать тот же адрес, что и список точек
    (list_stores уже отдаёт ADDRESS/REGION — store_map их игнорировал)."""
    cm, _ = _fake_db({"success": True, "columns": _PECO_TANK_COLS_ADDR,
                      "data": _PECO_TANK_ROWS_ADDR})
    with patch("models.plg_datasource.DatabaseModel", return_value=cm):
        r = PecoDataSource().store_map('ru', 7)
    assert r["data"]["store"]["address"] == "ул. Индепенденцей, 12"
    assert r["data"]["store"]["city"] == "Бэлць"


# ── маршруты записи товаров: источник peco обязан быть только для чтения ──

def test_peco_source_blocks_product_write_routes():
    """PUT/DELETE /api/plg/products/<id> обязаны отклонять source=peco.

    Синтетический id сорта топлива (1..4) совпадает с id настоящих строк
    PLG_PRODUCTS: без серверной проверки запрос с витрины АЗС молча правил
    или удалял бы демо-товар с тем же номером.
    """
    import app as app_module
    with patch.object(app_module.AuthController, 'is_authenticated', return_value=True), \
         patch.object(app_module.PlanogramController, 'save_product') as save_m, \
         patch.object(app_module.PlanogramController, 'delete_product') as del_m:
        client = app_module.app.test_client()
        put_resp = client.put('/api/plg/products/1?source=peco', json={})
        del_resp = client.delete('/api/plg/products/1?source=peco')
    for resp in (put_resp, del_resp):
        assert resp.status_code == 403
        body = resp.get_json()
        assert body["success"] is False
        assert body.get("error")
    save_m.assert_not_called()
    del_m.assert_not_called()


def test_demo_source_still_allows_product_write_routes():
    """Демо-набор — единственный источник записи, гвард не должен его ломать."""
    import app as app_module
    with patch.object(app_module.AuthController, 'is_authenticated', return_value=True), \
         patch.object(app_module.PlanogramController, 'save_product',
                      return_value={"success": True, "data": {}}) as save_m:
        client = app_module.app.test_client()
        resp = client.put('/api/plg/products/1?source=demo', json={})
    assert resp.status_code == 200
    assert resp.get_json()["success"] is True
    save_m.assert_called_once()


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


def test_peco_source_blocks_product_create_route():
    """POST /api/plg/products обязан отклонять source=peco так же, как PUT/DELETE.

    Создание «товара» с витрины сортов топлива завело бы новую строку в
    PLG_PRODUCTS — тот же прорыв на запись, что правка и удаление, только
    через создание; закрывать надо все три метода, а не два.
    """
    import app as app_module
    with patch.object(app_module.AuthController, 'is_authenticated', return_value=True), \
         patch.object(app_module.PlanogramController, 'save_product') as save_m:
        client = app_module.app.test_client()
        resp = client.post('/api/plg/products?source=peco', json={"code": "A95"})
    assert resp.status_code == 403
    body = resp.get_json()
    assert body["success"] is False
    assert body.get("error")
    save_m.assert_not_called()


def test_demo_source_still_allows_product_create():
    """Защита второго источника не должна задевать обычный demo-режим —
    иначе она сломает работающий модуль ради нового источника."""
    import app as app_module
    with patch.object(app_module.AuthController, 'is_authenticated', return_value=True), \
         patch.object(app_module.PlanogramController, 'save_product',
                      return_value={"success": True}) as save_m:
        client = app_module.app.test_client()
        resp = client.post('/api/plg/products', json={"code": "X-1"})
    assert resp.status_code == 200
    save_m.assert_called_once()
