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


__all__ = ["blueprint", "root_blueprint"]
