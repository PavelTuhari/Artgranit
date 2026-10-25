"""RO: pachetul «Proiect tip» (docs/ProiectTip + static/proiect-tip): toate documentele
exista in MD si HTML, HTML-ul e la zi cu Markdown-ul, copiile publice nu contin
documentele interne si nici secrete, iar hub-ul le poate deschide.
Documentatie: docs/ProiectTip/00_INDEX.md"""
import importlib.util
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "docs", "ProiectTip")
PUB = os.path.join(ROOT, "static", "proiect-tip")


def _builder():
    spec = importlib.util.spec_from_file_location(
        "build_pt", os.path.join(ROOT, "scripts", "build_proiect_tip_html.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_every_doc_has_md_and_html_and_html_is_current():
    b = _builder()
    for name, label, pub in b.DOCS:
        md = open(os.path.join(SRC, name + ".md"), encoding="utf-8").read()
        html = open(os.path.join(SRC, name + ".html"), encoding="utf-8").read()
        assert html == b.page(name, label, md, public=False), "HTML vechi: rulati build_proiect_tip_html.py (%s)" % name
        if pub:
            pub_html = open(os.path.join(PUB, name + ".html"), encoding="utf-8").read()
            assert pub_html == b.page(name, label, md, public=True), name


def test_the_four_requested_parts_are_present():
    b = _builder()
    names = [n for n, _, _ in b.DOCS]
    for need in ("01_MARKETING", "02_GHID_PROPRIETAR", "04_INSTRUCTIUNI_CUMPARATOR", "05_INSTRUCTIUNI_OPERATOR"):
        assert need in names


def test_public_copies_hold_only_public_docs_and_no_secrets():
    b = _builder()
    public = {n for n, _, pub in b.DOCS if pub}
    files = {f[:-5] for f in os.listdir(PUB) if f.endswith(".html")} - {"index"}
    assert files == public
    for f in os.listdir(PUB):
        s = open(os.path.join(PUB, f), encoding="utf-8").read()
        for bad in ("opgate", "op-intrare", "password=", "PW=", "wallet_HX", "BEGIN PRIVATE KEY"):
            assert bad not in s, (f, bad)
    for f in os.listdir(SRC):
        if f.endswith((".md", ".html")):
            s = open(os.path.join(SRC, f), encoding="utf-8").read()
            assert "op-intrare" not in s and "opgate" not in s, f


def test_links_between_docs_point_to_html():
    for f in os.listdir(SRC):
        if f.endswith(".html"):
            s = open(os.path.join(SRC, f), encoding="utf-8").read()
            assert not re.search(r'href="\d\d_[A-Z_]+\.md"', s), f


def test_hub_serves_the_folder_and_manifest_describes_both_formats():
    src = open(os.path.join(ROOT, "modules", "b26docs", "routes.py"), encoding="utf-8").read()
    for folder in ("ProiectTip", "Marketing", "Git"):
        assert '"%s"' % folder in src
    man = json.load(open(os.path.join(SRC, "docs.json"), encoding="utf-8"))
    for f in os.listdir(SRC):
        if f.endswith((".md", ".html")):
            assert f in man, f
