"""Тесты модуля воронки продаж и кнопки-шпаргалки витрины."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from unittest.mock import MagicMock, patch  # noqa: E402


# ── воронка: правильные документы и правильные меры ────────────────────

def test_funnel_counts_shop_orders_not_all_documents():
    """Заказ магазина — SYSFID 12280; посчитать все документы подряд значило
    бы записать в продажи зарплату и инвентаризацию."""
    from modules.funnel import store
    assert store.SYSFID_ORDER == 12280
    db = MagicMock()
    db.execute_query.return_value = {"success": True, "columns": [], "data": []}
    store.clear_cache()
    with patch("modules.funnel.store.Biro26DB", return_value=db):
        store.orders_by_day(7)
    sql, params = db.execute_query.call_args[0]
    assert ":sf" in sql and params["sf"] == 12280


def test_summary_conversion_and_average_check():
    from modules.funnel import store
    rows = [
        {"day": "2026-08-25", "orders": 4, "total": 400.0,
         "delivered": 1, "delivered_sum": 100.0},
        {"day": "2026-08-26", "orders": 6, "total": 600.0,
         "delivered": 4, "delivered_sum": 400.0},
    ]
    with patch.object(store, "orders_by_day", return_value=rows):
        s = store.summary(7)
    assert s["orders"] == 10 and s["delivered"] == 5
    assert s["conversion_pct"] == 50.0
    assert s["avg_check"] == 100.0


def test_summary_with_no_orders_does_not_divide_by_zero():
    from modules.funnel import store
    with patch.object(store, "orders_by_day", return_value=[]):
        s = store.summary(7)
    assert s["orders"] == 0
    assert s["conversion_pct"] is None and s["avg_check"] is None


def test_goods_come_from_the_credit_side_of_the_line():
    """Товар в строке ST201 лежит в CTSC — проверено по живым данным;
    DTSC у заказов пуст."""
    from modules.funnel import store
    src = pathlib.Path(store.__file__).read_text(encoding="utf-8")
    assert "l.CTSC" in src and "l.SC " not in src


def test_bestsellers_order_puts_nulls_last():
    """Oracle при DESC ставит NULL первыми — без NULLS LAST безымянная
    сумма возглавила бы список."""
    from models.biro26_oracle_store import Biro26Store
    import models.biro26_oracle_store as m
    src = pathlib.Path(m.__file__).read_text(encoding="utf-8")
    block = src[src.index("def get_shop_bestsellers"):src.index("def get_product_tree")]
    assert "DESC NULLS LAST" in block


# ── автономная сводка ──────────────────────────────────────────────────

def test_digest_is_sent_once_per_day_after_the_hour(monkeypatch):
    import datetime
    from modules.funnel import digest
    values = {digest.K_ENABLED: "1", digest.K_HOUR: "22", digest.K_LAST: ""}
    monkeypatch.setattr(digest, "_setting",
                        lambda k, d="": values.get(k, d))

    class _Now(datetime.datetime):
        @classmethod
        def now(cls):
            return cls(2026, 8, 26, 23, 5)
    monkeypatch.setattr(digest.datetime, "datetime", _Now)
    assert digest.due() is True
    values[digest.K_LAST] = "2026-08-26"          # уже отправляли сегодня
    assert digest.due() is False


def test_digest_respects_the_off_switch(monkeypatch):
    from modules.funnel import digest
    monkeypatch.setattr(digest, "_setting",
                        lambda k, d="": "0" if k == digest.K_ENABLED else d)
    assert digest.due() is False


def test_digest_does_not_fire_before_the_hour(monkeypatch):
    """Час по умолчанию 22:00 — почтовый сервер хоста включён только
    22:00–02:00, дневная отправка упала бы."""
    import datetime
    from modules.funnel import digest
    assert digest.DEFAULT_HOUR == 22
    monkeypatch.setattr(digest, "_setting",
                        lambda k, d="": {"FUNNEL_DIGEST_ENABLED": "1",
                                         "FUNNEL_DIGEST_HOUR": "22"}.get(k, d))

    class _Now(datetime.datetime):
        @classmethod
        def now(cls):
            return cls(2026, 8, 26, 14, 0)
    monkeypatch.setattr(digest.datetime, "datetime", _Now)
    assert digest.due() is False


def test_digest_text_carries_the_numbers_and_the_stale_list(monkeypatch):
    from modules.funnel import digest, store
    monkeypatch.setattr(store, "summary", lambda d: {
        "days": d, "orders": 7, "orders_sum": 1234.5, "delivered": 3,
        "delivered_sum": 500.0, "conversion_pct": 42.9, "avg_check": 176.4,
        "by_day": []})
    monkeypatch.setattr(store, "top_groups", lambda d, n: [
        {"grupa": "Televizoare", "orders": 2, "total": 340000}])
    monkeypatch.setattr(store, "top_products", lambda d, n: [])
    monkeypatch.setattr(store, "stale_orders", lambda a, b: [
        {"cod": 1, "nr": "305", "day": "2026-07-07", "total": 1579,
         "client": "Pavel Tuhari"}])
    text = digest.compose()
    assert "заказов 7" in text and "Televizoare" in text
    assert "305" in text and "Не отгружено" in text
    assert "officeplus.md/UNA.md/orasldev/funnel" in text


# ── панель закрыта, шпаргалка открыта ─────────────────────────────────

def test_funnel_api_requires_login():
    src = pathlib.Path(__file__).resolve().parent.parent / "modules/funnel/routes.py"
    text = src.read_text(encoding="utf-8")
    # каждый api-маршрут начинается с проверки входа
    import re
    for m in re.finditer(r'@blueprint\.route\("(/api/[^"]+)"', text):
        tail = text[m.end():m.end() + 300]
        assert "_guard()" in tail, f"маршрут {m.group(1)} без проверки входа"


def test_cheatsheet_uses_real_addresses_not_onclick():
    tpl = (pathlib.Path(__file__).resolve().parent.parent
           / "templates/biro26/site_base.html").read_text(encoding="utf-8")
    assert "opGuideBtn" in tpl
    assert "/produs/'+x.cod" in tpl or "/produs/' + x.cod" in tpl
    assert "catalog?grupa=" in tpl
