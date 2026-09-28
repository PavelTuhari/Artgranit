"""Порог рассрочки 1500 лей — правило владельца от 18.08.2026.

Отдельный файл тестов — намеренно (CLAUDE.md, правило №2): эта логика уже
один раз молча исчезала при выкладке, когда жила в общем app.py. Тест —
второй сторож после выноса в models/biro26_credit_min.py.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from unittest.mock import patch  # noqa: E402


def test_threshold_module_lives_in_its_own_file():
    """Правило №2: важная логика не живёт в общих файлах."""
    root = pathlib.Path(__file__).resolve().parent.parent
    assert (root / "models/biro26_credit_min.py").exists()
    app_src = (root / "app.py").read_text(encoding="utf-8")
    # в общем файле — только однострочный вызов, не сама логика
    assert "credit_min_order" in app_src
    assert "DEFAULT_MIN" not in app_src


def test_default_is_1500_not_zero_when_db_is_down():
    """Ноль означал бы «рассрочка на любую сумму» — опасное умолчание."""
    from models import biro26_credit_min as cm
    assert cm.DEFAULT_MIN == 1500.0
    with patch("models.biro26_oracle_store.Biro26Store.get_setting",
               side_effect=RuntimeError("БД недоступна")):
        assert cm.min_order() == 1500.0


def test_threshold_comes_from_settings_without_redeploy():
    from models import biro26_credit_min as cm
    with patch("models.biro26_oracle_store.Biro26Store.get_setting",
               return_value="2000"):
        assert cm.min_order() == 2000.0
    with patch("models.biro26_oracle_store.Biro26Store.get_setting",
               return_value="1750,50"):
        assert cm.min_order() == 1750.5


def test_check_blocks_below_and_allows_at_threshold():
    from models import biro26_credit_min as cm
    with patch.object(cm, "min_order", return_value=1500.0):
        ok_low, msg = cm.check(1499.99)
        ok_at, _ = cm.check(1500.0)
    assert ok_low is False and msg
    assert ok_at is True
