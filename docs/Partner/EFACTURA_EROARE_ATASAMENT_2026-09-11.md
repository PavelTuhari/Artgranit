# 11.09.2026 — «A apărut o eroare la încărcarea atașamentului» (documentul 431)

## Ce a văzut operatorul

Acțiunea **«Выгрузить в e-Factura»** (action 12) din aplicația nativă a dat:

```
ORA-20000: e-Factura: A aparut o eroare la incarcarea atasamentului.
           Va rugam sa incercati mai tarziu.
ORA-06512: la "OFFICEPLUS.EFA_NATIVE", line 92
tmdb_docs.cod = 431
```

`line 92` = `RAISE_APPLICATION_ERROR` din `EFA_NATIVE.send_doc_pr` — adică
**fereastra prin care aplicația arată mesajul**, nu locul defecțiunii.

## Ce s-a întâmplat de fapt

Din jurnalul `EFA_CALL` (apelurile 341, 342, 343 — trei apăsări între 14:12
și 14:13) și din `EFA_DOC`:

| Ce | Valoare |
|---|---|
| Metodă | `PostInvoices`, HTTP **200** |
| `RequestId` | `97e9dd0c4143424dab3a541aefd797cf` |
| `Status` | 2 (răspuns prelucrat — **nu** «acceptat») |
| `TotalInvoices` | 1 |
| `TotalInvoicesPosted` | **0** |
| `ErrorMessage` | «A apărut o eroare la încărcarea atașamentului. Vă rugăm să încercați mai târziu.» |

Deci: cererea a ajuns la SFS, a trecut de autentificare și de schema XML
(factura a fost numărată: `TotalInvoices=1`), iar serverul lor a căzut la
pasul următor — salvarea XML-ului ca **atașament** în stocarea lor. Mesajul
este al SFS și conține chiar îndemnul «încercați mai târziu».

**`TotalInvoicesPosted=0` înseamnă că în SIA e-Factura nu a intrat nimic** —
niciuna dintre cele trei apăsări nu a creat vreo factură. Acțiunea se poate
repeta fără riscul dublurilor. (Spre deosebire de 03.09.2026, când fiecare
apăsare REUȘISE și au apărut patru facturi.)

## De ce nu e vina documentului 431

Factura are 4 rânduri, total 310,00 MDL, cumpărător `SRL ARTINICA-CV`
(IDNO 1003602008279). Față de documentele trimise cu succes (A-91 pe
08.09, A-92 pe 03.09) are trei particularități, toate permise de
`TaxInvoiceSchema.xsd` (unde `Code` și `Name` sunt `xs:string` simplu, fără
lungime sau set de caractere impus):

* denumire cu **chirilice**: `* Hama Аудио адаптер "mini" для 3,5 mm jack`;
* `*` la începutul a două denumiri;
* spațiu în cod: `Code="GMB CCSATA2RECEPTACL"`.

Ghilimelele din denumire nu sunt vinovate: factura acceptată din 08.09 avea
`Corector &quot;2 in 1&quot;` și a trecut.

Nu se poate demonstra 100% fără o probă pe mediul lor, iar o probă înseamnă
o factură reală în SIA (endpoint-ul configurat este **cel real**,
`https://efactura-api.sfs.md/Service.svc`), așa că nu am făcut-o din proprie
inițiativă.

## Ce s-a schimbat în cod

Operatorul nu trebuie să ghicească a cui e vina și dacă poate repeta.
`modules/efactura/rules.py` — funcții pure, testate:

* `sfs_transient(err)` — recunoaște mesajele serverului SFS (atașament,
  «încercați mai târziu», timeout);
* `explain_sfs_error(err, parsed)` — păstrează textul SFS și adaugă:
  * `[eroare la SFS, nu in document]` când refuzul e al lor;
  * «Nimic nu a intrat in SIA e-Factura (0 din 1) — actiunea se poate repeta»;
  * sau, dacă ceva a intrat deja: «ATENTIE: 1 din 2 au INTRAT deja … nu
    repetati actiunea» — exact capcana din 03.09.2026.

`controller.py` folosește mesajul explicat atât pentru răspunsul API, cât și
pentru `EFA_DOC.ERR_MSG`, deci apare la fel în fereastra nativă
(ORA-20000), în istoria documentului (`TMDB_DOCS_LOG`) și în back-office.

După deploy, aceeași situație se va vedea așa:

```
e-Factura: A aparut o eroare la incarcarea atasamentului. Va rugam sa
incercati mai tarziu. [eroare la SFS, nu in document] Nimic nu a intrat in
SIA e-Factura (0 din 1) - actiunea se poate repeta.
```

## Ce are de făcut operatorul acum

1. **Repetați acțiunea** pentru documentul 431 — nimic nu s-a creat la SFS.
2. Dacă dă din nou aceeași eroare, nu e nimic de corectat în factură:
   serverul SFS are o problemă la atașamente; încercați peste un timp.
3. Verificarea, fără a trimite nimic:
   `SELECT EFA_NATIVE.doc_status(431) FROM dual;`

## Deploy

Modificările sunt pe ramura `feat/efactura` (Python, fără DDL). Conturul care
răspunde la `http://officeplus.md/api/biro26/efactura/...` este cel din
birou (192.168.0.250), accesibil doar prin **VPN93** — tunelul refuză acum
conexiunea (`L2TP: incorrect user shared secret`), iar cheia partajată o
poate reintroduce doar proprietarul (Preferințe → Rețea → VPN93). Până
atunci în producție rămâne mesajul vechi (scurt), dar **comportamentul nu se
schimbă**: și acum se poate repeta în siguranță.
