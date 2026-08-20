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
