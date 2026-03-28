"""Tests for NufarulController new methods."""
import json
import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch, MagicMock, call
from controllers.nufarul_controller import NufarulController


class FakeDB:
    """Minimal DB mock for controller unit tests."""
    def __init__(self, rows, columns=None):
        self._rows = rows
        self._cols = columns or []
        self.connection = MagicMock()
        self.connection.cursor.return_value.__enter__ = lambda s: s
        self.connection.cursor.return_value.__exit__ = MagicMock(return_value=False)
    def execute_query(self, sql, params=None):
        return {"success": True, "data": self._rows, "columns": self._cols}
    def __enter__(self): return self
    def __exit__(self, *a): pass


# ── get_group_params ──────────────────────────────────────────

def test_get_group_params_all():
    rows = [
        ('clothing', 'Одежда', 'Îmbrăcăminte', '👗', 10, '[{"key":"color"}]', 'Y'),
        ('carpets',  'Ковры',  'Covoare',       '🪞', 20, '[{"key":"size_m2"}]', 'Y'),
    ]
    cols = ['GROUP_KEY','LABEL_RU','LABEL_RO','ICON','SORT_ORDER','PARAMS_JSON','ACTIVE']
    with patch('controllers.nufarul_controller.DatabaseModel', return_value=FakeDB(rows, cols)):
        result = NufarulController.get_group_params()
    assert result['success'] is True
    assert len(result['data']) == 2
    assert result['data'][0]['group_key'] == 'clothing'
    assert result['data'][0]['params_json'] == '[{"key":"color"}]'


def test_get_group_params_single():
    rows = [('clothing', 'Одежда', 'Îmbrăcăminte', '👗', 10, '[{"key":"color"}]', 'Y')]
    cols = ['GROUP_KEY','LABEL_RU','LABEL_RO','ICON','SORT_ORDER','PARAMS_JSON','ACTIVE']
    with patch('controllers.nufarul_controller.DatabaseModel', return_value=FakeDB(rows, cols)):
        result = NufarulController.get_group_params(group_key='clothing')
    assert result['success'] is True
    assert result['data']['group_key'] == 'clothing'


def test_get_group_params_single_not_found():
    with patch('controllers.nufarul_controller.DatabaseModel', return_value=FakeDB([], [])):
        result = NufarulController.get_group_params(group_key='nonexistent')
    assert result['success'] is False


# ── create_order_with_params ──────────────────────────────────

def test_create_order_with_params_writes_params_to_companion_table():
    """PARAMS JSON must be inserted into NUF_ORDER_ITEM_PARAMS for each item."""
    params_inserts = []
    call_count = [0]

    class TrackingDB(FakeDB):
        def execute_query(self, sql, params=None):
            call_count[0] += 1
            if 'NUF_ORDER_ITEM_PARAMS' in sql and params:
                params_inserts.append(params.get('params'))
            if 'NEXTVAL' in sql:
                return {"success": True, "data": [[call_count[0]]], "columns": ["NX"]}
            if "TO_CHAR" in sql:
                return {"success": True, "data": [["2026"]], "columns": ["Y"]}
            if "NUF_ORDER_STATUSES" in sql:
                return {"success": True, "data": [[1]], "columns": ["ID"]}
            return {"success": True, "data": [], "columns": []}

    items = [
        {"service_id": 1, "qty": 1, "price": 180.0,
         "params": {"color": "#c0392b", "fabric": "Шерсть", "stains": True}}
    ]
    with patch('controllers.nufarul_controller.DatabaseModel', return_value=TrackingDB([], [])):
        NufarulController.create_order_with_params("Test", "+373", items)

    assert len(params_inserts) == 1, f"Expected 1 params insert, got {len(params_inserts)}"
    stored = json.loads(params_inserts[0])
    assert stored["color"] == "#c0392b"
    assert stored["fabric"] == "Шерсть"
