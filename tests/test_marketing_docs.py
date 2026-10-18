"""RO: materialele de marketing (docs/Marketing + static/marketing) — coerenta cifrelor
si a manifestului hub-ului. Documentatie: docs/Marketing/STRATEGIA_PROMOVARE.md"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MK = os.path.join(ROOT, "docs", "Marketing")


def _read(*p):
    return open(os.path.join(ROOT, *p), encoding="utf-8").read()


def test_manifest_describes_every_marketing_doc():
    man = json.load(open(os.path.join(MK, "docs.json"), encoding="utf-8"))
    files = sorted(f for f in os.listdir(MK) if f.endswith(".md"))
    assert files and sorted(man) == files
    for f, m in man.items():
        assert set(m["title"]) >= {"ro", "ru", "en"} and set(m["descr"]) >= {"ro", "ru", "en"}, f


def test_numbers_are_the_same_in_prospect_and_brochure():
    md = _read("docs", "Marketing", "PROSPECT_ARTGRANIT.md")
    html = _read("static", "marketing", "artgranit-prospect.html")
    for n in ("21", "99", "345", "143"):
        assert n in md and n in html, n
    assert "+373 620 07 211" in md and "+37362007211" in html


def test_brochure_is_static_and_bilingual():
    html = _read("static", "marketing", "artgranit-prospect.html")
    assert "<script src=" not in html and "googletagmanager" not in html and "fonts.googleapis" not in html
    assert html.count('data-l="ro"') > 20 and html.count('data-l="ru"') > 20
    assert 'onclick="setL(\'ru\'' in html


def test_strategy_covers_the_three_target_groups_with_kpis():
    s = _read("docs", "Marketing", "STRATEGIA_PROMOVARE.md")
    for h in ("### 3.1 Заказчики", "### 3.2 Разработчики", "### 3.3 Oracle", "## 1. Цели и показатели", "## 5. Бюджет"):
        assert h in s, h
    assert re.search(r"Oracle Partner\s?Network", s) and "Marketplace" in s


def test_readme_points_to_the_marketing_docs():
    r = _read("README.md")
    assert "docs/Marketing/PROSPECT_ARTGRANIT.md" in r and "STRATEGIA_PROMOVARE.md" in r
