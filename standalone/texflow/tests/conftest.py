import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from texflow import create_app, db  # noqa: E402


@pytest.fixture
def con():
    c = db.connect(":memory:")
    db.init_db(c)
    yield c
    c.close()


@pytest.fixture
def app(tmp_path):
    return create_app(str(tmp_path / "t.db"), testing=True)


@pytest.fixture
def client(app):
    return app.test_client()
