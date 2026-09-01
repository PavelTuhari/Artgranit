"""Карта сайта и robots.txt — в папке модуля, а не в общем коде.

Почему модулем. Раньше эти маршруты жили в `app.py`. Любая ветка, где их
нет, теряла их при выкладке: 27.08.2026 контур переставили на другую
ветку — и публичный сайт остался без `robots.txt` и `sitemap.xml`, оба
адреса стали отдавать 404. В папке модуля такого случиться не может:
маршруты уезжают вместе с папкой, а ядро находит её само.

Адреса `/robots.txt` и `/sitemap.xml` обязаны жить в корне сайта, поэтому
объявлены списком `root_paths` в манифесте: ядро подключает их без
префикса и не даёт двум модулям занять один адрес.
"""
from flask import Blueprint, Response

# RO: partea obisnuita a modulului - sub prefixul lui.
blueprint = Blueprint("seo", __name__)

# RO: adresele care trebuie sa fie in RADACINA site-ului. Nucleul le
#     inregistreaza separat, dupa lista din manifest.
root_blueprint = Blueprint("seo_root", __name__)


def _xml(body: str) -> Response:
    return Response(body, mimetype="application/xml",
                    headers={"Cache-Control": "public, max-age=21600"})


@root_blueprint.route("/robots.txt")
def robots():
    from models.biro26_sitemap import robots_txt
    return Response(robots_txt(), mimetype="text/plain",
                    headers={"Cache-Control": "public, max-age=21600"})


@root_blueprint.route("/sitemap.xml")
def sitemap_index():
    from models.biro26_sitemap import index_xml
    return _xml(index_xml())


@root_blueprint.route("/sitemap-pages.xml")
def sitemap_pages():
    from models.biro26_sitemap import pages_xml
    return _xml(pages_xml())


@root_blueprint.route("/sitemap-categories.xml")
def sitemap_categories():
    from models.biro26_sitemap import categories_xml
    return _xml(categories_xml())


@root_blueprint.route("/sitemap-products-<int:part>.xml")
def sitemap_products(part: int):
    from models.biro26_sitemap import products_xml
    return _xml(products_xml(part))


# RO: DOMENIUL INTERN officeplus.una.md trebuie INCHIS pentru motoarele de
#     cautare - e o dublura tehnica a magazinului. Capcana: nginx-ul din
#     fata trimite TRAFICUL PUBLIC catre birou tot sub numele intern (pe
#     partea de birou numele public e ocupat de alt site), deci "noindex pe
#     tot ce vine cu Host intern" ar inchide si site-ul public. De aceea
#     frontalul marcheaza traficul public cu antetul X-Public-Site, iar
#     noindex primeste DOAR ce vine pe numele intern FARA acest marcaj -
#     adica doar vizitele directe pe officeplus.una.md.
# EN: the internal domain gets noindex ONLY when the request arrived
#     directly (no X-Public-Site mark from our own front proxy) - otherwise
#     we would deindex the public site too, since the front rewrites Host.
INTERNAL_NOINDEX_HOSTS = {"officeplus.una.md"}


@root_blueprint.after_app_request
def _noindex_internal_domain(response):
    from flask import request
    host = (request.host or "").lower().split(":")[0]
    if (host in INTERNAL_NOINDEX_HOSTS
            and request.headers.get("X-Public-Site") != "1"):
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


__all__ = ["blueprint", "root_blueprint"]
