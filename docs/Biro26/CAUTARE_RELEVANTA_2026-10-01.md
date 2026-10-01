# Căutare în catalog: relevanță în loc de alfabet — 01.10.2026

## Problema

`https://officeplus.md/api/biro26/shop/products?search=pix&limit=8` întorcea
întîi „2E Gaming mouse…”, „34" ASUS ROG…” — ele se potrivesc cu „pix” doar prin
descriere (senzor *PixArt* din `TMS_MPT_WEBATTR`). Pixurile adevărate erau la
mii de rînduri distanță (4538 de rezultate), pentru că `ORDER BY` era
`u.DENUMIREA, u.COD` — alfabetic. Aceeași funcție alimentează vitrina,
Partner API (`/api/v1/product`) și chatbotul de pe site.

## Ce s-a făcut

La **căutare + sortarea implicită** (`sort` = `name`/gol — UI-ul nu trimite
`?sort=name` deloc) ordinea e pe trepte de relevanță:

| Treaptă | Condiție |
|---|---|
| 0 | `DENUMIREA` începe cu termenul, sau `CODVECHI` = termenul exact |
| 1 | un cuvînt din `DENUMIREA` începe cu termenul (`'% '‖termen‖'%'`) |
| 2 | termenul apare oriunde în `DENUMIREA` |
| 3 | `NAMERUS` / `CODVECHI` / cod de bare conțin termenul |
| 4 | potrivire doar prin `TMS_MPT_WEBATTR` (denumire completă, descriere) |

În interiorul treptei — `DENUMIREA, COD`, ca înainte. Sortările explicite
(preț ↑/↓, Z–A) rămîn neschimbate; fără căutare ordinea e alfabetică, ca înainte.

Mulțimea rezultatelor și totalul **nu** se schimbă — doar ordinea.

## Fișiere

| Fișier | Ce |
|---|---|
| [`models/biro26_search_rank.py`](../../models/biro26_search_rank.py) | logica: `ORDER_BY`, `applies()` — fișier propriu (regula nr. 2) |
| [`models/biro26_oracle_store.py`](../../models/biro26_oracle_store.py) | `Biro26Store.get_products_stock`: ramura `else` a sortării — 3 rînduri |
| [`tests/test_biro26_search_relevance.py`](../../tests/test_biro26_search_relevance.py) | 6 teste, fără Oracle |

## Fără bind-uri noi (capcana ORA-01036)

`count_sql` se construiește **înainte** de `ORDER BY` și primește aceiași
parametri. Un bind nou doar în `ORDER BY` ar fi dat ORA-01036 la numărătoare.
De aceea toate treptele se scot din `:s` = `'%termen%'`, pe care filtrul de
căutare îl leagă deja în ambele interogări (inclusiv pe drumul Oracle Text de pe
nufarul/cloud, unde `:sq` lipsește): `SUBSTR(:s, 2)` = `'termen%'`,
`'% ' || SUBSTR(:s, 2)` = `'% termen%'`, `SUBSTR(:s, 2, LENGTH(:s) - 2)` = termenul.
Numărătoarea și cache-urile ei rămîn neatinse; testul
`test_binds_match_sql_exactly` verifică: bind-urile din SQL = cheile parametrilor.

## Verificare (Oracle real, 01.10.2026)

| Căutare | Înainte (primul rînd) | După | Timp |
|---|---|---|---|
| `pix` | 2E Gaming mouse… | PIX BILA SCH OFFICE N, Pix "scrie-sterge" Carioca… | 2,7 s (= ca înainte, `name_desc` 2,6 s) |
| `caiet` | — | Caiet 12 foi linie Star… | total 3950, neschimbat |

```bash
python3 -m pytest -q tests/test_biro26_search_relevance.py
curl -s "https://officeplus.md/api/biro26/shop/products?search=pix&limit=8" | python3 -m json.tool | grep -i denumirea
```

## Deploy

Fișierul `models/biro26_oracle_store.py` e **diferit pe fiecare server**
(vezi `docs/SERVERE_COD_VS_GIT_2026-10-01.md`, ramura `prod/office-2026-10-01`).
Nu se copiază fișierul din `main`: pe fiecare server se aplică patch-ul minim
peste versiunea lui — doar ramura `else` a sortării (copie `.bak-20261001`,
md5 înainte/după), plus fișierul nou `models/biro26_search_rank.py`. Rezultatul pe fiecare contur — în secțiunea
„Jurnal deploy” de mai jos.

## Jurnal deploy

01.10.2026 — patch minim (`apply_rank.py`: ancoră în `get_products_stock`, copie
`models/biro26_oracle_store.py.bak-20261001-search`, `py_compile`, rollback automat)
+ fișierul nou `models/biro26_search_rank.py`. md5 „înainte” = exact instantaneele
din `prod/*`, deci nimic nu se schimbase între timp pe servere.

| Server | md5 înainte | md5 după | Restart | Verificare |
|---|---|---|---|---|
| cloud `ubuntu@92.5.130.1:/home/ubuntu/artgranit` | `c08bc1e3…016c` | `bba2c567…7a58` | `systemctl restart artgranit` | `/login` 200, 0 Traceback, `pix` → PIX BILA SCH OFFICE N |
| nufarul `ubuntu@92.5.3.187:/home/ubuntu/artgranit` | `43908236…80` | `d62eeffe…7a58`* | `systemctl restart artgranit` | `/login` 200, `https://nufarul.eminescu.md/login` HTTP/2 200 |
| office `ubuntu@192.168.0.250:/home/ubuntu/artgranit` | `55f723a9…5259` | `14dbd082…2eca` | `systemctl restart artgranit` (gunicorn) | `/login` 200, `https://officeplus.md/cos` 200 |

\* `d62eeffe162f1bfef2e3a56d3bca7a58`

Live, după deploy:

- https://officeplus.md/api/biro26/shop/products?search=pix&limit=8&with_count=1 —
  PIX BILA SCH OFFICE N, PIX SCHNEIDER ERASABLE…, Pix "scrie-sterge"…; total 4538 (neschimbat)
- https://officeplus.md/api/biro26/shop/products?search=caiet&limit=8&with_count=1 — Caiet 12 foi…; total 3950
- https://officeplus.md/catalog?q=pix — 200

Rollback pe oricare server:

```bash
cd /home/ubuntu/artgranit && cp models/biro26_oracle_store.py.bak-20261001-search models/biro26_oracle_store.py && sudo systemctl restart artgranit
```
