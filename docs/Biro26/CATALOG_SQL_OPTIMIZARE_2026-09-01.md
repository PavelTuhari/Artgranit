# Catalogul: de ce incarca baza si ce s-a schimbat (01.09.2026)

## Semnalul

Proprietarul a raportat incarcare mare pe baza, cu `SQL_ID a795hqqdfs065` —
interogarea grilei de produse a magazinului.

## Ce s-a masurat (nu presupus)

Din jurnalul Apache al masinii de productie `192.168.0.250`, fereastra
01.09.2026 00:00–19:50:

| Masura | Valoare |
|---|---|
| apeluri `/api/biro26/shop/products` | 1.547 |
| combinatii DIFERITE de filtre | 1.171 |
| dintre ele cerute o singura data | 876 |
| cu filtru pe grupa/categorie/brand | **1.148 (74%)** |
| fisa unui produs (`cod=`) | 365 |
| de la roboti (Googlebot) | 231 (15%) |

Doua concluzii care au schimbat directia:

1. **Cache-ul nu putea ajuta** — trei sferturi din cereri sint unice. Marirea
   TTL-ului ar fi fost lucru degeaba.
2. **Robotii nu erau vinovatul** — 15% din trafic. Blocarea lor ar fi rezolvat
   o saptime din problema si ar fi scos magazinul din Google.

Apoi s-a masurat interogarea bucata cu bucata, pe baza de productie (din
timpul total se scad ~0,9 s de pornire a worker-ului Oracle):

| Bucata | Timp SQL |
|---|---|
| nucleul (`TMS_UNIVERS` + feed deduplicat + pret) | **~0,95 s** |
| adaugarea stocului (`YBIRO_STOCK_CALC_ITEM`) | +0,05 s |
| adaugarea rezervarilor (comenzi `VMDB_ST201D`) | +0,03 s |

Deci nu agregarile erau problema, ci nucleul. Cauza exacta: feed-ul
`BIRO26_GOODS` are duplicate (**235.649 de rinduri pentru 197.377 de coduri**)
si se deduplica cu

```sql
ROW_NUMBER() OVER (PARTITION BY COD_UNIVERS ORDER BY ID) = 1
```

adica Oracle sorta toata tabela la FIECARE cerere de catalog, ca sa intoarca
24 de produse.

## Ce s-a schimbat

Fisier nou: **`models/biro26_catalog_fast.py`** (regula nr. 2 — logica in
fisierul ei, in `models/biro26_oracle_store.py` doar apelul).

1. filtrele feed-ului trec printr-un `u.COD IN (SELECT COD_UNIVERS FROM
   BIRO26_GOODS WHERE ...)` — intr-un `IN` duplicatele nu deranjeaza, deci
   deduparea nu mai e necesara inainte de paginare;
2. pagina se alege pe `TMS_UNIVERS` (index pe denumire);
3. deduparea, preturile, stocul, rezervarile, codurile de bare si variantele
   se lipesc DOAR peste cele 24–200 de rinduri ale paginii.

Drumul vechi ramine neschimbat pentru cautarea dupa text, filtrele de pret si
sortarea dupa pret — acolo pretul efectiv trebuie stiut inainte de paginare.
Comutarea o face `supports()`.

## Cistigul masurat

Timp SQL, mediana din 5 rulari:

| Forma cererii | Inainte | Acum | De cite ori |
|---|---|---|---|
| filtru pe grupa (74% din trafic) | 0,97 s | 0,18 s | **5,4×** |
| grupa + categorie | 0,89 s | 0,34 s | 2,6× |
| catalog simplu | 1,88 s | 0,25 s | 7,5× |

## Cum se verifica ca nu s-a stricat nimic

`tests/test_catalog_fast.py` compara cele doua drumuri pe baza reala, rind cu
rind si cimp cu cimp, pe sase combinatii de filtre (pagina 1, pagina 3, grupa,
sortare inversa, produse noi, fisa unui produs). Rezultatul la punerea in
functiune: **coduri identice, zero cimpuri diferite**.

```bash
venv/bin/python -m pytest tests/test_catalog_fast.py -q
```

Echivalenta deduparii s-a verificat si direct in baza: `MIN(ID)` per cod si
`ROW_NUMBER() ... ORDER BY ID` aleg acelasi rind — **0 diferente** pe toate
cele 197.377 de coduri.

## Ce a mers prost la punerea in functiune (de tinut minte)

Prima varianta pusa pe masina de birou a **rupt catalogul pentru ~2 minute**:
paginile cu `with_count=1` (adica toate paginile vitrinei) intorceau
`name '_cached' is not defined`. Cauza: masina de birou ruleaza o ramura mai
veche a `biro26_oracle_store.py`, in care ajutorul de cache nu exista. Eu
testasem local, unde exista.

A doua varianta a intors rinduri, dar `total` iesea 0: interogarea de
numarare nu foloseste bind-ul `:pd` al paginii, iar Oracle refuza bind-urile
in plus. Se trimit acum doar bind-urile care apar in ea.

Doua invataminte, ambele acum in test:

1. **Testul trebuie sa acopere `with_count`** — forma pe care o cere vitrina
   la fiecare pagina. Fara ea, verificarea mea a trecut pe linga defect.
2. **Ce se patcheaza pe masina de birou nu poate presupune functii din ramura
   mea.** Codul nou nu trebuie sa depinda de ajutoare din fisierul comun.

## Ce NU s-a facut si de ce

* **Nu s-a blocat Googlebot** — 15% din trafic, si scoaterea magazinului din
  cautare costa mai mult decit incarcarea.
* **Nu s-a marit TTL-ul cache-ului** — 876 din 1.171 de chei se cer o singura
  data.
* **Nu s-au sters duplicatele din `BIRO26_GOODS`** — ar fi cistigul cel mai
  mare (join simplu, fara dedupare), dar cere DDL si curatare pe baza de
  productie plus o modificare in import. De discutat separat cu proprietarul.

## Pragul de 1.500 lei — verificare separata

Semnalul din sesiunea paralela („a disparut `CREDIT_MIN_ORDER`") s-a verificat
pe site-ul VIU: pragul **functioneaza**. In `templates/biro26/site_cart.html`
logica exista sub numele `MIN_ORDER` (de aici si cautarea fara rezultat dupa
numele vechi): mesajul rosu, butonul de comanda si Liber Card dezactivate sub
prag, plus garda `guardMinOrder()`. Serverul verifica acelasi prag prin
`models/biro26_credit_min.py`, chemat din `controllers/biro26_controller.py`.

Pe `https://officeplus.md/cos` se vede `MIN_ORDER = 1500` si textul-conditie.

Singurul lucru real de reparat era ca vitrina avea 1500 scris in cod, iar
serverul citea `YBIRO_SETTINGS.CREDIT_MIN_ORDER` — la o schimbare a setarii
cele doua ar fi spus lucruri diferite. Acum vitrina ia valoarea din
`window.CREDIT_MIN_ORDER`, cu 1500 doar ca rezerva.
