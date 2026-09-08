# Catalog: căutare relaxată cînd fraza întreagă nu găsește nimic (08.09.2026)

**Semnal:** «SOS! nu găsește produse în catalog» — pe officeplus.md
«Smartphone Samsung Galaxy A27 Negru» dădea 0 produse, la fel «SM-A2768ZKEUC».

**Cauza:** căutarea magazinului (`Biro26Store.get_products_stock`) e un
`LIKE '%fraza întreagă%'` pe denumire / NAMERUS / CODVECHI / cod de bare /
denumirea completă. Orice cuvînt în plus (culoarea în română — produsele au
«Black», «Smartphone» în față, altă ordine, memoria) → 0. Serverul,
baza și API-ul erau în regulă («Samsung Galaxy A27» dădea 7 produse).
«SM-A2768ZKEUC» e codul producătorului și nu există în nomenclator (codurile
noastre sînt GOG00…, nici codul de bare nu îl conține) — acolo 0 e corect.

**Soluția** (fișier propriu `models/biro26_search_relax.py`, un apel de o linie
în `Biro26Controller.get_products_stock`): DOAR cînd rezultatul e gol și fraza
are ≥ 2 cuvinte, se încearcă pe rînd, pînă la 8 variante:
1. culorile RO/RU → EN (negru → black, alb → white …) și fără cuvintele
   generice (smartphone, telefon…);
2. fără ultimul cuvînt, fără ultimele două… (păstrînd ≥ 2 cuvinte), apoi fără
   primul, primele două…;
3. codul de model singur (litere + cifre: A27, A2768, apoi 256GB);
4. abia la urmă marca singură.
Răspunsul primește `relaxed_query` și `original_query`.

Rezultate: «Smartphone Samsung Galaxy A27 Negru» → 7 produse (după «Samsung
Galaxy A27»); «Samsung A27 negru 256» → după «A27»; «Galaxy A27 8/256 negru»
→ 1 produs (după «Galaxy A27 8/256»). Costul: doar la 0 rezultate, cîte o
interogare pe variantă.

**Fișiere:** `models/biro26_search_relax.py` (nou), `controllers/biro26_controller.py`
(hook, controlerul era identic pe office și în main — înlocuit cu backup
`.bak-20260908-0601` pe ambele servere), `tests/test_biro26_search_relax.py` (4).

**Verificare:** `pytest tests/test_biro26_search_relax.py -q`; public:
`https://officeplus.md/api/biro26/shop/products?limit=2&with_count=1&search=Smartphone%20Samsung%20Galaxy%20A27%20Negru`
→ `relaxed_query: "Samsung Galaxy A27"`.

**Pasul următor (opțional):** pagina catalogului să afișeze «Nimic pentru
«…» — se arată rezultatele pentru «…»» folosind `relaxed_query`
(`templates/biro26/site_catalog.html`, punctual).
