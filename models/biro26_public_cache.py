"""RO: cache-ul PUBLIC al catalogului — portat in main pe 19.10.2026 din app.py-ul
care rula pe nufarul (slepok prod/nufarul-live, scris direct pe server si ramas
in afara git-ului). Logica aici, in app.py doar apelurile (regula nr. 2).

- `public_cached(resp)`: arborele de grupe si brandurile sint IDENTICE pentru toti
  si se schimba o data pe zi (dupa import), dar cintaresc ~400 KB si treceau prin
  tunelul birou->cloud la FIECARE pagina de catalog; browserul le tine 10 minute.
- `warm_catalog()`: la pornire se incalzesc arborele si brandurile, altfel PRIMUL
  vizitator dupa repornire le platea integral (~25 s pe conturul lent).
EN: browser cache for public, rarely-changing catalog data + startup warm-up."""


def public_cached(resp, seconds: int = 600):
    resp.headers['Cache-Control'] = f'public, max-age={seconds}'
    return resp


def warm_catalog() -> None:
    try:
        from models.biro26_oracle_store import Biro26Store
        Biro26Store.get_product_tree()
        Biro26Store.get_product_brands()
    except Exception:                                        # noqa: BLE001
        pass
