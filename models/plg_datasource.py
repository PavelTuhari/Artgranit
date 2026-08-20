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
from typing import Any, Dict, Optional, Type

from models.database import DatabaseModel


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
        """Сорта топлива как товарный справочник витрины.

        Цена — средняя действующая по сети: список товаров не привязан
        к станции (get_products не принимает store_id), а цены на АЗС
        различаются. Цену конкретной станции показывает план точки.

        category_id игнорируется: у источника peco одна категория —
        топливо, отдельного справочника категорий нет.
        """
        # ROW_NUMBER() нумерует резервуары внутри inline view, до фильтра
        # поиска: если бы номер считался после WHERE, id одного и того же
        # сорта топлива менялся бы от строки поиска (найдёт "дизель" —
        # получит id=1, сбросит фильтр — тот же сорт станет id=3), а id
        # используется в ссылках PUT/DELETE и как React-подобный key на
        # витрине.
        sql = (
            "SELECT v.ID, v.CODE, v.CATEGORY_ID, v.CATEGORY_CODE, "
            "v.CATEGORY_RU, v.CATEGORY_RO, v.CATEGORY_EN, v.CATEGORY_COLOR, "
            "v.NAME_RU, v.NAME_RO, v.NAME_EN, v.BARCODE, v.BRAND, v.UOM, "
            "v.PRICE, v.CURRENCY, v.STATUS FROM ("
            "SELECT ROW_NUMBER() OVER (ORDER BY g.SORT_ORDER, g.CODE) AS ID, "
            "g.CODE, g.SORT_ORDER, "
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
            "FROM PECO_REF_FUEL_GRADES g) v WHERE 1 = 1"
        )
        params: Dict[str, Any] = {}
        if search:
            sql += " AND (UPPER(v.CODE) LIKE :p_q OR UPPER(v.NAME_RU) LIKE :p_q)"
            params["p_q"] = "%" + search.strip().upper() + "%"
        try:
            rows = self._query(sql + " ORDER BY v.SORT_ORDER, v.CODE", params)
        except Exception as e:
            return {"success": False, "error": str(e)}
        return {"success": True, "lang": lang, "data": localize_rows(rows, lang)}

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
               "v.CURRENT_L, v.MIN_ALARM_L, v.FILL_PCT, v.IS_LOW, g.COLOR, "
               "s.ADDRESS AS STATION_ADDRESS, s.REGION AS STATION_REGION "
               "FROM V_PECO_TANK_LEVELS v "
               "JOIN PECO_REF_FUEL_GRADES g ON g.CODE = v.GRADE_CODE "
               "JOIN PECO_STATIONS s ON s.ID = v.STATION_ID ")
        params: Dict[str, Any] = {}
        # ACTIVE фильтруется в обеих ветках: без него декоммиссированная
        # станция, чей id где-то остался (закладка, старая ссылка), молча
        # отрисует план, как будто станция всё ещё работает.
        if store_id:
            sql += "WHERE v.STATION_ID = :p_station AND s.ACTIVE = 1 "
            params["p_station"] = int(store_id)
        else:
            sql += ("WHERE v.STATION_ID = (SELECT MIN(ID) FROM PECO_STATIONS "
                    "                       WHERE ACTIVE = 1) AND s.ACTIVE = 1 ")
        try:
            rows = self._query(sql + "ORDER BY v.TANK_CODE", params)
        except Exception as e:
            return {"success": False, "error": str(e)}
        if not rows:
            return {"success": True, "lang": lang, "data": empty}

        first = rows[0]
        store = {"id": first["station_id"], "code": first["station_code"],
                 "name": first["station_name"],
                 "address": first.get("station_address"),
                 "city": first.get("station_region"),
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


#: Реестр источников: единственное место, где перечислены реализации.
_SOURCES: Dict[str, Type[PlanogramDataSource]] = {
    DemoDataSource.id: DemoDataSource,
    PecoDataSource.id: PecoDataSource,
}


def get_data_source(source: str) -> PlanogramDataSource:
    """Реализация источника по коду. Неизвестный код -> демо."""
    return _SOURCES.get(source, DemoDataSource)()
