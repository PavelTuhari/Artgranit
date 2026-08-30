# Partner B2B API + integrarea Ultra

Modul izolat `modules/partner/` (nucleu: `core/module_loader.py`). Doua roluri:

1. **API pentru partenerii NOSTRI** — contract identic cu Ultra B2B API V1
   (`eshop.ultra.md/api-documentation`), ca un integrator care lucreaza deja
   cu Ultra sa se conecteze la officeplus.md schimbind doar base URL-ul si
   doua denumiri de cimpuri (`ultra_code`→`code`, `ultra_uuid`→`uuid`;
   alias-urile vechi sint acceptate in corpurile batch).
2. **Noi ca partener ULTRA** — clientul `modules/partner/ultra.py` aduce
   catalogul Ultra in ERP-ul una.md prin tamponul standard `BIRO26_GOODS`
   (SHEET='ULTRA'); publicarea ramine pe pipeline-ul de import al
   operatorului (validate → prepare → assign-keys).

## Adrese

| Ce | Unde |
|---|---|
| Documentatia publica (stil Ultra) | `https://officeplus.md/api-documentation` |
| Base URL public | `https://officeplus.md/api/v1` |
| Rutele reale Flask | `/UNA.md/orasldev/partner/api/...` (nginx face maparea) |
| Administrare (portal) | `/UNA.md/orasldev/partner/` |

## Obiecte Oracle (prefix PAPI_)

`PAPI_PARTNER` (conturi, legate de clientul ERP `TMS_UNIVERS.COD`),
`PAPI_TOKEN` (DOAR amprente SHA-256, access 1h / refresh 30 zile, rotatie),
`PAPI_LOG` (append-only: autentificari, comenzi, sincronizari Ultra).
Instalator PROPRIU: `python3 modules/partner/scripts/partner_deploy.py`
(instalatorul comun nu e atins). Instalat 28.08.2026, 9 obiecte VALID.

## Endpoint-uri

`POST /auth/token|refresh|revoke` · `GET /product` (+`/{id}`, `POST /batch`)
· `GET /category` · `GET /brand` · `GET /quantity` (+`POST /batch`) ·
`GET /changes?since&entity` (product/price/quantity, derivate din WEBATTR.
UPDATED_AT, TPR1D_PERPRLIST.DATASTART si diferenta instantaneelor de stoc) ·
`POST /order` (devine cont de plata REAL prin `Y_AI_BIRO26`; preturile DOAR
din coloana clientului; `validate_only:true` = verificare fara creare) ·
`GET /order` · `GET /health`. Limita: 120 cereri/min per partener.

## Integrarea Ultra (noi ca dealer)

Credentialele se introduc in pagina de administrare (YBIRO_SETTINGS:
`PARTNER_ULTRA_USER/_PASSWORD/_BASE`). Prima sincronizare = tot catalogul
(paginat 1000); urmatoarele = incremental prin `/api/changes` cu reperul
`PARTNER_ULTRA_SINCE`. Stub-urile "no image" se arunca (lectia impreso).
CLI/cron: `python3 modules/partner/scripts/ultra_sync.py [--full]`.
**Formatul REAL al API-ului Ultra difera de documentatia lor** (verificat
28.08.2026 cu contul de dealer): raspunsul la `/product` e o LISTA goala de
wrapper; `product_name` vine ca JSON-STRING (`'{"ro":...}'`), nu ca obiect;
preturile vin ca `{amount, currency: {code, name, rate}}` — `user_price`
(pretul de dealer) e in USD cu cursul zilei, `fixed_price` (retail) in MDL.
Clientul nostru normalizeaza totul la MDL (`amount * rate`) si accepta
ambele forme. Cont dealer: officeplussrl@gmail.com (parola in
YBIRO_SETTINGS.PARTNER_ULTRA_PASSWORD).

**Alte capcane ale API-ului lor, verificate pe viu (28–29.08.2026):**

| Ce zice documentatia | Ce face API-ul real | Ce facem noi |
|---|---|---|
| `sort=name_asc` e o optiune valida | raspunde **500 Server Error** | folosim `sort=updated_at`, cu revenire automata la "fara sortare" |
| paginare simpla `limit/offset` | fara sortare fixa **fereastra aluneca**: prima trecere = 38.706 rinduri cu doar **26.010 uuid-uri unice** (dubluri intre pagini, deci si goluri) | sortare fixa + deduplicare pe `ultra_uuid` in cadrul rularii |
| raspunsul e un obiect cu `data` | pentru `/product` e o **lista** direct | acceptam ambele forme |
| `product_name` e obiect multilingv | vine ca **JSON-STRING** | `_lang()` accepta si dict, si string |
| campurile de pret sint numere | sint `{amount, currency:{code,name,rate}}`, dealer in **USD** | `_money()` converteste in MDL dupa cursul din raspuns |

**Articolele Ultra sint numerice** (ex. `246019`), deci intra sub regula sursei
`ULTRA` din `TMS_ORG_IMPSRC` (`ART_PREFIX='ULT'`, `ART_MIN_LEN=6`): toate
primesc prefixul `ULT` inainte de a ajunge in tampon, ca sa nu se bata cap in
cap cu articolele altor furnizori.

## Verificare (28.08.2026, productie)

Token+refresh+revoke OK; 401 fara token / parola gresita; catalog cu preturi,
imagini, categorii; `/changes` OK; comanda reala **A-86** (doc 400, 20.159
lei) creata prin API si vizibila in `GET /order`; partener de test:
`apitest@officeplus.test` pe clientul "B2B Demo Client" (453040).

## Rulare locala si teste

`tests/test_partner.py` — doua teste de izolare + regulile pure (6 passed).
Modulul apare in `app.extensions["module_loader"]` la `loaded`.
