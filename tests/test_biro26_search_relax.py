"""Cautarea relaxata a catalogului (08.09.2026, «SOS! nu gaseste produse»). Fara Oracle."""
import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
from models.biro26_search_relax import attempts, with_fallback  # noqa: E402


def test_attempts_for_the_owner_phrase():
    a = attempts("Smartphone Samsung Galaxy A27 Negru")
    assert a[0] == "Smartphone Samsung Galaxy A27 black"
    assert a[1] == "Samsung Galaxy A27 black"
    assert "Samsung Galaxy A27" in a and "A27" in a
    assert attempts("A27") == [] and attempts("") == []
    assert len(attempts("a b c d e f g h i j")) <= 8


def test_fallback_returns_first_non_empty_variant_with_markers():
    calls = []
    def fn(**kw):
        calls.append(kw["search"])
        return {"success": True, "data": [1] if kw["search"] == "Samsung Galaxy A27" else [], "total": 0}
    r = with_fallback(fn, {"search": "Smartphone Samsung Galaxy A27 Negru", "limit": 24})
    assert r["data"] == [1] and r["relaxed_query"] == "Samsung Galaxy A27"
    assert r["original_query"] == "Smartphone Samsung Galaxy A27 Negru" and calls[0] == "Smartphone Samsung Galaxy A27 Negru"


def test_no_fallback_when_found_or_single_word():
    calls = []
    def fn(**kw):
        calls.append(kw["search"]); return {"success": True, "data": []}
    assert "relaxed_query" not in with_fallback(fn, {"search": "SM-A2768ZKEUC"}) and calls == ["SM-A2768ZKEUC"]
    calls.clear()
    def fn2(**kw):
        calls.append(kw["search"]); return {"success": True, "data": [1]}
    with_fallback(fn2, {"search": "caiet a5"}); assert calls == ["caiet a5"]


def test_controller_hook_is_one_call():
    src = open(os.path.join(ROOT, "controllers", "biro26_controller.py"), encoding="utf-8").read()
    assert "with_fallback(Biro26Store.get_products_stock, dict(" in src
