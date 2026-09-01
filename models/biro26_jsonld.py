"""RO: Marcajul schema.org pentru fisa produsului (Product + Offer).
EN: schema.org markup for the product page (Product + Offer).

RO: De ce. Fara marcaj, in rezultatele cautarii produsul apare ca un link
    obisnuit. Cu Product + Offer, Google poate arata pretul, disponibilitatea
    si codul de bare direct in rezultate - acelasi loc in lista aduce vizibil
    mai multe intrari pe magazin.
EN: Without markup a product is just a blue link in search results. With
    Product + Offer, Google can show price, availability and the barcode right
    in the result.

RO: Marcajul se construieste pe SERVER, din acelasi rind pe care il primeste
    si pagina. Asa datele din marcaj si cele de pe ecran nu pot sa se
    contrazica - iar contradictia este exact ce Google considera marcaj
    inselator.
EN: The markup is built on the SERVER from the same row the page renders, so
    the markup and the visible page can never disagree - and disagreement is
    exactly what Google treats as deceptive markup.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

# RO: moneda magazinului / EN: the shop's currency
CURRENCY = "MDL"

# RO: codul de bare are 13 cifre (EAN-13); altfel nu este gtin13 si nu se pune
#     - un cod gresit este mai rau decit lipsa lui.
# EN: a barcode is 13 digits (EAN-13); anything else is not a gtin13 and is
#     omitted - a wrong code is worse than no code.
_GTIN13 = re.compile(r"^\d{13}$")


def _text(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _price(value: Any) -> Optional[str]:
    """RO: pretul ca numar cu doua zecimale. EN: price with two decimals."""
    if value is None:
        return None
    try:
        return f"{float(str(value).replace(',', '.')):.2f}"
    except (TypeError, ValueError):
        return None


def availability(row: Dict[str, Any]) -> str:
    """RO: disponibilitatea reala, nu cea dorita.

    Magazinul vinde si la comanda - fisele fara stoc NU sint indisponibile,
    ele se comanda. De aceea lipsa stocului inseamna BackOrder, nu
    OutOfStock: altfel marcajul ar spune ca produsul nu se poate cumpara,
    desi butonul de cumparare este acolo si functioneaza.
    """
    avail = row.get("avail_cant")
    if avail is None:
        avail = row.get("real_cant")
    try:
        in_stock = float(avail or 0) > 0
    except (TypeError, ValueError):
        in_stock = False
    return ("https://schema.org/InStock" if in_stock
            else "https://schema.org/BackOrder")


def product_name(row: Dict[str, Any], lang: str = "ro") -> Optional[str]:
    if lang == "ru":
        return (_text(row.get("namerus")) or _text(row.get("denumirea")))
    return (_text(row.get("denumirea")) or _text(row.get("namerus")))


def product(row: Dict[str, Any], url: str, *, lang: str = "ro",
            price_field: str = "retail1",
            seller: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """RO: obiectul Product + Offer. None daca nu avem nici nume, nici pret.

    Google cere pentru Offer cel putin pretul si moneda; un Product fara
    ele nu aduce nimic si doar umple pagina.
    """
    name = product_name(row, lang)
    price = _price(row.get(price_field) or row.get("retail1"))
    if not name or not price:
        return None

    data: Dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": name,
        "url": url,
    }

    sku = _text(row.get("codvechi")) or _text(row.get("cod"))
    if sku:
        data["sku"] = sku

    barcode = _text(row.get("barcode"))
    if barcode and _GTIN13.match(barcode):
        data["gtin13"] = barcode

    image = _text(row.get("image"))
    if image:
        data["image"] = [image]

    brand = _text(row.get("brand"))
    if brand:
        data["brand"] = {"@type": "Brand", "name": brand}

    # RO: descrierea completa daca exista; altfel numele - Google cere ceva.
    description = _text(row.get("denum_full")) or name
    data["description"] = description

    category = " / ".join(p for p in (_text(row.get("grupa")),
                                      _text(row.get("categorie"))) if p)
    if category:
        data["category"] = category

    offer: Dict[str, Any] = {
        "@type": "Offer",
        "url": url,
        "priceCurrency": CURRENCY,
        "price": price,
        "availability": availability(row),
        "itemCondition": "https://schema.org/NewCondition",
    }
    if seller:
        offer["seller"] = {"@type": "Organization", "name": seller}
    data["offers"] = offer
    return data


def script_tag(data: Optional[Dict[str, Any]]) -> str:
    """RO: gata de pus in pagina.

    `</script>` din datele produsului ar inchide devreme eticheta si ar rupe
    pagina, de aceea bara oblica se scapa - asa cere si specificatia JSON-LD.
    """
    if not data:
        return ""
    body = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    body = body.replace("</", "<\\/")
    return '<script type="application/ld+json">' + body + '</script>'
