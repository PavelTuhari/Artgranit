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
