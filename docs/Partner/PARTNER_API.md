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
Conectivitatea verificata: `eshop.ultra.md/api/auth/token` raspunde 401 pe
credentiale gresite (contract confirmat); mai trebuie DOAR credentialele
reale de dealer de la Ultra.

## Verificare (28.08.2026, productie)

Token+refresh+revoke OK; 401 fara token / parola gresita; catalog cu preturi,
imagini, categorii; `/changes` OK; comanda reala **A-86** (doc 400, 20.159
lei) creata prin API si vizibila in `GET /order`; partener de test:
`apitest@officeplus.test` pe clientul "B2B Demo Client" (453040).

## Rulare locala si teste

`tests/test_partner.py` — doua teste de izolare + regulile pure (6 passed).
Modulul apare in `app.extensions["module_loader"]` la `loaded`.
