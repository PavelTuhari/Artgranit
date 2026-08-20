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
