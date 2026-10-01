"""RO: asistentul OfficePlus (chatbot) pe vitrina — buton + iframe izolat.

Ce se verifica:
- site_base.html il include O SINGURA DATA, printr-o linie (regula nr. 2);
- butonul apare doar pe officeplus.* (botul exista doar acolo) sau cu ?chatbot=1;
- iframe-ul se creeaza abia la click si mesajul de inchidere e acceptat doar
  de la https://officeplus.md;
- embed.html are ACELASI marcaj ca index.html al proprietarului (altfel
  script.js nu-si gaseste elementele);
- cantitatea din Partner API include stocul furnizorului, ca insigna «În stoc»;
- in git nu ajunge nicio credentiala a botului.
Documentatie: docs/Biro26/CHATBOT_PE_SITE_2026-10-01.md
"""
import os
import re
from types import SimpleNamespace

import jinja2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOT = os.path.join(ROOT, "wordpress_officeplus", "public_html", "OfficePlus_Chatbot")
PARTIAL = "biro26/_site_chatbot.html"


def _read(*p):
    return open(os.path.join(ROOT, *p), encoding="utf-8").read()


def _render(host, args=None):
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.join(ROOT, "templates")))
    req = SimpleNamespace(host=host, args=args or {})
    return env.get_template(PARTIAL).render(request=req)


def test_site_base_includes_chatbot_once_as_one_line():
    src = _read("templates", "biro26", "site_base.html")
    lines = [l for l in src.splitlines() if "_site_chatbot.html" in l]
    assert lines == ['  {% include "biro26/_site_chatbot.html" %}']
    # inainte de </body>, dupa JivoChat — nu intirzie afisarea paginii
    assert src.index("_site_chatbot.html") > src.index("code.jivosite.com")
    assert src.index("_site_chatbot.html") < src.rindex("</body>")


def test_launcher_only_on_officeplus_or_forced():
    assert 'id="opAsistBtn"' in _render("officeplus.md")
    assert 'id="opAsistBtn"' in _render("officeplus.una.md")      # trafic prin failover-ul din oficiu
    assert 'id="opAsistBtn"' not in _render("nufarul.eminescu.md")
    assert 'id="opAsistBtn"' in _render("nufarul.eminescu.md", {"chatbot": "1"})


def test_iframe_is_lazy_isolated_and_origin_checked():
    html = _render("officeplus.md")
    assert "<iframe" not in html, "iframe-ul trebuie creat abia la click"
    assert "createElement('iframe')" in html
    assert "https://officeplus.md/OfficePlus_Chatbot/embed.html" in html
    assert "e.origin !== 'https://officeplus.md'" in html
    # coltul sting: dreptul e ocupat de #opGuideBtn si JivoChat
    assert re.search(r"#opAsistBtn\{position:fixed;left:18px;bottom:18px", html)
    # nimic din style.css/script.js al botului nu intra direct in pagina vitrinei
    assert "OfficePlus_Chatbot/style.css" not in html and "OfficePlus_Chatbot/script.js" not in html


def test_embed_markup_equals_owner_index():
    body = re.compile(r"<body>(.*?)<script src=\"script.js\"></script>", re.S)
    idx = body.search(open(os.path.join(BOT, "index.html"), encoding="utf-8").read()).group(1)
    emb = body.search(open(os.path.join(BOT, "embed.html"), encoding="utf-8").read()).group(1)
    assert idx == emb
    emb_full = open(os.path.join(BOT, "embed.html"), encoding="utf-8").read()
    assert "postMessage({ opChat: 'close' }" in emb_full and 'name="robots" content="noindex"' in emb_full


def test_no_chatbot_secrets_in_git():
    assert not os.path.exists(os.path.join(BOT, "api", "config.php"))
    assert not os.path.exists(os.path.join(BOT, "api", ".officeplus_tokens.json"))
    ex = open(os.path.join(BOT, "api", "config.example.php"), encoding="utf-8").read()
    for k in ("OFFICEPLUS_USERNAME", "OFFICEPLUS_PASSWORD", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        assert re.search(r"const %s='[A-Z_]*AICI'" % k, ex), k


def test_partner_quantity_includes_supplier_stock():
    from modules.partner import rules
    row = {"cod": 7, "denumirea": "Pix", "retail1": 10, "avail_cant": 0, "furnizor_stoc": 1000}
    assert rules.map_product(row)["quantity"] == 1000
    assert rules.map_quantity(row)["quantity"] == 1000
    assert rules.sellable_qty({"avail_cant": 3, "furnizor_stoc": "2"}) == 5
    # server cu catalog vechi (fara FURNIZOR_STOC) sau valori stricate
    assert rules.sellable_qty({"avail_cant": 4}) == 4
    assert rules.sellable_qty({"avail_cant": None, "furnizor_stoc": "x"}) == 0
    assert rules.sellable_qty({"avail_cant": -2, "furnizor_stoc": None}) == 0


def test_bot_shows_retail_price_not_dealer_price():
    """RO: in contractul API `user_price` = pretul DEALERULUI (angro), `fixed_price` =
    pretul cu amanuntul. Pe site botul vorbeste cu cumparatorul — deci retail
    intii; altfel oferta PDF iesea cu rinduri angro si total retail (validarea
    serverului calculeaza pe coloana clientului «Persoana fizica» = retail1)."""
    js = open(os.path.join(BOT, "script.js"), encoding="utf-8").read()
    assert "pr=p.fixed_price??p.user_price??p.price_d??0" in js
    assert "pr=p.user_price??p.fixed_price" not in js


def test_jivo_bar_hidden_while_panel_open_on_phone():
    html = _render("officeplus.md")
    assert "body.opAsistOpen jdiv{display:none!important}" in html
    assert "document.body.classList.add('opAsistOpen')" in html
    assert "document.body.classList.remove('opAsistOpen')" in html
