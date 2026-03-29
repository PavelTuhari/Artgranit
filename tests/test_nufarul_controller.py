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


def test_get_group_params_includes_subgroups_json():
    """SUBGROUPS_JSON must be present in each group row returned."""
    rows = [
        ('dry_cleaning', 'Химчистка', 'Curățare', '👗', 10,
         '[{"key":"color"}]', '[{"key":"sg1","label_ru":"Test"}]', 'Y')
    ]
    cols = ['GROUP_KEY','LABEL_RU','LABEL_RO','ICON','SORT_ORDER',
            'PARAMS_JSON','SUBGROUPS_JSON','ACTIVE']
    with patch('controllers.nufarul_controller.DatabaseModel',
               return_value=FakeDB(rows, cols)):
        result = NufarulController.get_group_params()
    assert result['success'] is True
    assert len(result['data']) == 1
    row = result['data'][0]
    assert 'subgroups_json' in row, "subgroups_json key must be present"
    assert row['subgroups_json'] == '[{"key":"sg1","label_ru":"Test"}]'


# ── create_order_with_params ──────────────────────────────────

def test_create_order_with_params_writes_params_to_companion_table():
    """PARAMS JSON must be inserted into NUF_ORDER_ITEM_PARAMS for each item.
    The controller now uses db.connection.cursor() directly (batch path), so we
    mock the cursor rather than execute_query."""
    params_inserts = []
    executemany_calls = []

    # cursor.fetchone / fetchall return values depend on the SQL issued
    call_idx = [0]
    def fake_execute(sql, params=None):
        call_idx[0] += 1

    def fake_fetchone():
        # bootstrap query: seq_val, order_id, year, status_id
        return (1001, 2001, "2026", 99)

    def fake_fetchall():
        # item IDs batch query
        return [(3001,)]

    def fake_executemany(sql, data):
        executemany_calls.append((sql, data))
        if 'NUF_ORDER_ITEM_PARAMS' in sql:
            for row in data:
                params_inserts.append(row.get('params'))

    mock_cursor = MagicMock()
    mock_cursor.__enter__ = lambda s: s
    mock_cursor.__exit__ = MagicMock(return_value=False)
    mock_cursor.execute = fake_execute
    mock_cursor.fetchone = fake_fetchone
    mock_cursor.fetchall = fake_fetchall
    mock_cursor.executemany = fake_executemany

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.commit = MagicMock()
    mock_conn.rollback = MagicMock()

    class DirectCursorDB(FakeDB):
        @property
        def connection(self):
            return mock_conn

    items = [
        {"service_id": 1, "qty": 1, "price": 180.0,
         "params": {"color": "#c0392b", "fabric": "Шерсть", "stains": True}}
    ]
    with patch('controllers.nufarul_controller.DatabaseModel', return_value=DirectCursorDB([], [])):
        result = NufarulController.create_order_with_params("Test", "+373", items)

    assert result.get('success'), f"Expected success, got: {result}"
    assert len(params_inserts) == 1, f"Expected 1 params insert, got {len(params_inserts)}"
    stored = json.loads(params_inserts[0])
    assert stored["color"] == "#c0392b"
    assert stored["fabric"] == "Шерсть"
