import pytest

from texflow import rules


def test_ean13_check_digit_known_codes():
    assert rules.ean13_check_digit("400638133393") == 1          # 4006381333931
    assert rules.ean13_check_digit("590123412345") == 7          # 5901234123457
    assert rules.is_valid_ean13("4006381333931")
    assert not rules.is_valid_ean13("4006381333932")
    assert not rules.is_valid_ean13("40063813339")


def test_make_ean13_internal_prefix():
    code = rules.make_ean13("200", 15)
    assert code.startswith("200000000015") and rules.is_valid_ean13(code)
    assert len({rules.make_ean13("21", n) for n in range(1, 500)}) == 499
    with pytest.raises(ValueError):
        rules.make_ean13("200", 10 ** 9)
    with pytest.raises(ValueError):
        rules.make_ean13("2a", 1)


def test_sku_zara_style_and_cyrillic():
    assert rules.make_sku("4387", "401", "m") == "4387-401-M"
    assert rules.make_sku("tsh 01", "800", "XL") == "TSH01-800-XL"
    assert rules.make_sku("Джинсы", "400", "28") == "DZHINSY-400-28"
    with pytest.raises(ValueError):
        rules.make_sku("", "1", "S")


def test_translit():
    assert rules.translit("Чёрный Щука") == "Chernyy Schuka"
    assert rules.translit("Ağırlık ş ţ") == "Agirlik s t"
    assert rules.translit("ABC 123") == "ABC 123"


@pytest.mark.parametrize("price,step,ending,expected", [
    (183, 10, 0.1, 189.9), (189.9, 10, 0.1, 189.9), (189.95, 10, 0.1, 199.9),
    (183, 1, 0.01, 183.99), (183, 100, 1, 199), (183.2, 0, 0, 183.2), (0, 10, 0.1, 0), (5, 10, 0, 10),
])
def test_psych_round(price, step, ending, expected):
    assert rules.psych_round(price, step, ending) == pytest.approx(expected)


def test_retail_price_markup_vat_rounding():
    r = rules.retail_price(100, 100, 20, 10, 0.1)
    assert r["net"] == 200 and r["gross"] == 240 and r["price"] == 249.9
    assert r["real_markup_pct"] == pytest.approx(108.2, abs=0.1)
    # минимальная наценка поднимает слишком низкую
    assert rules.retail_price(100, 10, 0, 1, 0, min_margin_pct=30)["price"] == 130


def _lines():
    return [rules.CostLine("a", 10, 5.0, weight_kg=10, duty_pct=10),
            rules.CostLine("b", 30, 1.0, weight_kg=30, duty_pct=0)]


@pytest.mark.parametrize("method", ["value", "qty", "weight"])
def test_allocation_distributes_whole_lump(method):
    costs = rules.ShipmentCosts(fx_rate=2, freight=100, customs=50, broker=30, other=20, method=method)
    res = rules.allocate_landed_cost(_lines(), costs)
    assert sum(r.overhead_unit * r.qty for r in res) == pytest.approx(200, abs=0.01)
    a = res[0]
    assert a.goods_unit == 10 and a.duty_unit == 1


def test_allocation_by_value_vs_qty():
    v = {r.key: r for r in rules.allocate_landed_cost(_lines(), rules.ShipmentCosts(freight=80, method="value"))}
    q = {r.key: r for r in rules.allocate_landed_cost(_lines(), rules.ShipmentCosts(freight=80, method="qty"))}
    # по стоимости: a=50, b=30 → a несёт 50/80 → 50 на 10 шт = 5/шт
    assert v["a"].overhead_unit == pytest.approx(5)
    assert q["a"].overhead_unit == pytest.approx(2)
    assert q["b"].overhead_unit == pytest.approx(2)


def test_allocation_weight_fallback_and_errors():
    lines = [rules.CostLine("x", 4, 1.0), rules.CostLine("y", 0, 1.0)]
    res = rules.allocate_landed_cost(lines, rules.ShipmentCosts(freight=40, method="weight"))
    assert len(res) == 1 and res[0].overhead_unit == 10
    assert rules.allocate_landed_cost([], rules.ShipmentCosts()) == []
    with pytest.raises(ValueError):
        rules.allocate_landed_cost(lines, rules.ShipmentCosts(method="magic"))


def test_reconcile_statuses():
    rows = {r["key"]: r for r in rules.reconcile({"TSH": 100, "JNS": 50, "DRS": 10}, {"TSH": 100, "JNS": 47, "DRS": 12, "ACC": 3})}
    assert rows["TSH"]["status"] == "ok"
    assert rows["JNS"]["status"] == "short" and rows["JNS"]["diff"] == -3 and rows["JNS"]["diff_pct"] == -6.0
    assert rows["DRS"]["status"] == "over"
    assert rows["ACC"]["status"] == "extra" and rows["ACC"]["diff_pct"] is None
