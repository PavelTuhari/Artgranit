# Integrarea cu SIA „e-Factura” (SFS.md)

> ## ✅ STAREA CURENTA (31.08.2026): INTEGRAREA ESTE FACUTA
>
> Modulul `modules/efactura/` este scris, instalat pe toate conturile si
> functional. Mai lipsesc **doar credentialele** (utilizatorul API care se
> creeaza in e-Factura de persoana cu rol de Manager).
>
> * Pagina modulului: **`/UNA.md/orasldev/efactura/`** — setari, jurnal,
>   previzualizare XML, buton de trimitere.
> * Detaliile implementarii: [sectiunea 8](#8-implementat-31082026--modulul-modulesefactura)
>   de la finalul acestui document.
> * Ce trebuie de la companie: [sectiunea 5](#5-ce-trebuie-de-la-proprietar-nu-pot-obtine-singur).
>
> Sectiunile 1–7 de mai jos sint **analiza dinaintea dezvoltarii** — se
> pastreaza pentru ca explica DE CE integrarea arata asa (regimuri, metode
> API, capcane). Raspunsul „nu s-a facut" din sectiunea 1 se refera la
> starea de la 30.08.2026, INAINTE de dezvoltare.

---

**Intrebarea proprietarului (30.08.2026):** se poate face partajare cu sfs.md
ca factura sa se descarce in sistem si in e-Factura? S-a facut deja aceasta
integrare in proiect?

## 1. Raspuns scurt (la data analizei, 30.08.2026)

**Atunci integrarea NU exista** — nu era nicaieri in proiect. Singura urma era
o linie in specificatia modulului AGRO:
`Integration with e-factura/customs → Phase 2` (adica amanata, nu executata).

**Da, se poate face** — SFS publica un API oficial pentru sistemele contabile
(ERP), exact pentru acest scenariu. → **A si fost facuta a doua zi**, vezi
sectiunea 8.

## 2. Ce am verificat (inainte de dezvoltare)

| Verificare | Rezultat |
|---|---|
| Cod: `efactura`, `e-factura`, `sfs.md`, `mconnect`, `servicii.fisc` | doar mentiunea „Phase 2" din specul AGRO |
| Obiecte Oracle `%EFACT%`, `%E_FACT%`, `%SFS%` in schema OFFICEPLUS | niciunul |
| Aceleasi obiecte in TOATE schemele vizibile (`ALL_OBJECTS`) | niciunul (doar pachete Oracle native) |
| Rechizitele necesare exista in ERP? | **da**: `TMS_ORG.CODFISCAL` (IDNO), conturi bancare in `VMS_ORG_CONT_FISC` |
| Documentele magazinului | `TMDB_DOCS`, `SYSFID=12280` — **cont de plata**, 50 in ultimele 30 de zile |

**Atentie la o diferenta importanta:** magazinul emite acum *cont de plata*
(factura proforma), NU *factura fiscala*. In e-Factura se transmit facturi
FISCALE. Deci integrarea presupune si definirea documentului fiscal in ERP,
nu doar transmiterea celui existent.

Clienti persoane juridice in magazin: **5** din 17 (doar pentru ei e relevanta
e-Factura; persoanelor fizice nu li se emite factura fiscala electronica).

## 3. Ce ofera SFS (verificat in ghidul oficial de integrare)

SIA „e-Factura" expune un **serviciu SOAP/WCF** (nu REST):
`basicHttpBinding`, securitate `TransportWithMessageCredential`, contract
descris prin WSDL. Autentificare: utilizator + parola pe HTTPS, sistemul
intoarce un **token de sesiune** folosit la apelurile urmatoare.

**Metodele disponibile:**

| Trimitere | Citire |
|---|---|
| `PostInvoices` — transmite facturi (XML) | `GetAcceptedInvoices` |
| `PostInvoicesWithAttachment` | `GetRejectedInvoices` |
| `PostAcceptedInvoices` | `GetInvoicesBySeriaNumber` |
| `PostRejectedInvoices` | `GetInvoicesContentForPrint` |
| `PostCanceledInvoices` | `GetInvoicesForSigning`, `GetInvoicesQRcodes` |
| | `GetTaxpayersInfo`, `GetLogs` |

`PostInvoices` primeste `PostInvoicesRequest {RequestId, InvoicesXml,
ActorRole, InvoicesXmlStatus}` si intoarce `PostInvoicesResponse
{TotalInvoices, TotalInvoicesPosted, TimeStamp, Status, RequestId,
ErrorMessage}`. Continutul facturii — **XML valid dupa schema XSD** a SFS.

## 4. Doua regimuri — de aici depinde arhitectura

| | Semi-automatizat | Complet automatizat |
|---|---|---|
| Transmiterea prin API | da | da |
| Semnatura electronica | **manual**, in interfata web e-Factura, de persoana autorizata | automat, din sistem |
| Certificat digital in momentul transmiterii | **nu e nevoie** | **necesar** |
| Anulare / respingere | manual, din web | din sistem |
| Efort de implementare | mai mic | mai mare (integrarea semnaturii) |

Pentru inceput, regimul **semi-automatizat** este alegerea rationala: factura
pleaca din sistemul nostru automat, iar contabilul doar o semneaza in
e-Factura. Trecerea la „complet automatizat" se poate face ulterior, fara a
reface transmiterea.

## 5. Ce trebuie de la proprietar (nu pot obtine singur)

1. **Utilizator API in e-Factura.** Se creeaza DOAR de persoana cu rol de
   Manager (Director) al companiei: e-Factura → *Setari* → *Utilizatorii
   companiei* → butonul **„CREEAZĂ UN UTILIZATOR API"**. De acolo ies
   utilizatorul si parola pentru API.
2. **Decizia asupra regimului** (semi vs complet automatizat).
3. Pentru regimul complet automatizat — **certificatul digital** al companiei.
4. Confirmarea **organizatiei-vinzator** (IDNO-ul cu care se emit facturile).

## 6. Ce fac eu dupa primirea acestora

Modul izolat `modules/efactura/` (aceeasi schema ca `modules/partner/`):
contur Oracle propriu `EFA_*` (jurnal de transmiteri, statusuri, erori),
maparea documentului ERP → XML dupa XSD-ul SFS, buton „Trimite in e-Factura"
in back-office plus transmitere automata optionala, sincronizarea statusurilor
(`GetAcceptedInvoices` / `GetRejectedInvoices`), stocarea QR-codurilor si a
raspunsurilor pentru audit. Codul comun nu se atinge.

**Estimare:** transmiterea + jurnalul + statusurile — realizabile imediat ce
exista utilizatorul API. Partea nesigura fara acces este **XSD-ul exact** al
facturii: se descarca din sectiunea *Help* a e-Factura, cu contul companiei.

## 7. Surse

- [Ghid de integrare semi-automatizata SIA „e-Factura"](https://efactura.sfs.md/Help/Ghid_integrare_Semi_Automatizata.pdf)
- [CTIF — integrarea sistemelor contabile cu noua versiune „e-Factura"](https://www.ctif.gov.md/ro/integrarea-sistemelor-de-contabilitate-ale-agentilor-economici-cu-noua-versiune-sistemului-e)
- [SFS — e-Factura in baza fisierului XML](https://sfs.md/ro/stiri/in-atentia-contribuabililor-care-emit-e-factura-in-baza-fisierului-xml)
- [Ghidul utilizatorului SI „e-Factura" v.2.0](https://egov.md/sites/default/files/document/attachments/ghid_de_utilizare_e-factura.pdf)
- Suport tehnic CTIF: **022 822222**

---

## 8. IMPLEMENTAT (31.08.2026) — modulul `modules/efactura/`

Integrarea este scrisa si instalata pe toate conturile; **asteapta doar
credentialele** (utilizatorul API din e-Factura). Pina atunci modulul
functioneaza „in gol": arata XML-ul care ar pleca, dar nu trimite nimic.

### Trei intrari, o singura logica

Ca si forma tiparita a contului, trimiterea e disponibila din trei locuri, iar
in spate ruleaza EXACT acelasi cod (`modules/efactura/controller.py`):

| Intrare | Adresa | Cine are voie |
|---|---|---|
| Back-office | `/UNA.md/orasldev/efactura/` | sesiunea portalului |
| Cabinetul clientului | buton «e-Factura» linga PDF/HTML in „Comenzile mele" | clientul, DOAR documentele lui (serverul verifica) |
| API intern | `/UNA.md/orasldev/efactura/api/send/<doc>`, `/api/status/<doc>`, `/api/preview/<doc>`, `/api/docs`, `/api/health` | `X-API-Key` — acelasi antet ca restul API-ului Biro26, pentru back-office-urile native |

### Contur Oracle propriu (prefix EFA_)

`EFA_SETTING` (setarile integrarii), `EFA_DOC` (o linie per document:
status NEW/SENT/ACCEPTED/REJECTED/ERROR, numarul SFS, RequestId, eroarea),
`EFA_LOG` (jurnal append-only: ce XML a plecat si ce a raspuns SFS — pentru
audit fiscal). Instalator propriu:
`python3 modules/efactura/scripts/efactura_deploy.py`. Instalat 31.08.2026,
7 obiecte VALID.

### Clientul SOAP

Scris de mina, fara `zeep` (nu e in venv-ul productiei, iar o dependinta noua
pe conturul viu nu se justifica pentru cinci metode): plic SOAP cu
WS-Security `UsernameToken` peste HTTPS, exact cum cere
`basicHttpBinding` / `TransportWithMessageCredential` din ghidul SFS.
Metode acoperite: `PostInvoices`, `GetAcceptedInvoices`, `GetRejectedInvoices`,
`GetInvoicesBySeriaNumber`, `GetTaxpayersInfo`, `GetLogs`.

### Rechizitele vinzatorului — din ERP, nu din admin

`Biro26Report.doc_data` da deja blocul `firm` din care se tipareste contul:
IDNO `1026602001837`, denumirea, adresa, IBAN, banca. Modulul il foloseste
ca sursa, iar setarile din admin doar il SUPRASCRIU. Asa nu se poate intimpla
ca pe hirtie sa fie o firma si in e-Factura alta.

### Verificat pe documente reale

XML valid pentru contul A-86 (televizor + tonere) si pentru un client
persoana juridica (`CABINETUL AVOCATULUI…`, IDNO 3202121297825 in `<Buyer>`);
caracterele speciale (`"`, `&`, `<`) escapate; fara credentiale — mesaj clar,
nu exceptie; toate cele trei intrari intorc 401 fara autentificare.
Teste: `tests/test_efactura.py` (7 passed), inclusiv cele doua de izolare.

### Ce ramine de facut cind vin credentialele

1. Se completeaza in pagina modulului: **endpoint**, **utilizator API**,
   **parola** (+ eventual seria facturii).
2. Butonul **«Testează conexiunea»** confirma accesul.
3. La primul document real se compara XML-ul nostru cu **XSD-ul** descarcat
   din sectiunea *Help* a e-Facturii si se aliniaza denumirile nodurilor
   (XML-ul plecat se vede in jurnal, deci alinierea se face pe date reale).

---

## 9. Pornirea in 4 pasi (cind aveti utilizatorul API)

1. **Creati utilizatorul API** in e-Factura — DOAR persoana cu rol de
   Manager (Director) poate: *Setări → Utilizatorii companiei →*
   **„CREEAZĂ UN UTILIZATOR API"**. Notati utilizatorul si parola.
2. **Completati setarile** in `/UNA.md/orasldev/efactura/`: endpoint-ul
   serviciului, utilizatorul, parola. Restul (IDNO, denumire, IBAN, banca)
   se ia automat din ERP — se completeaza doar daca vreti sa suprascrieti.
3. **Apasati „Testează conexiunea"** — confirma accesul fara sa trimita nimic.
4. **Trimiteti primul document** si comparati XML-ul din jurnal cu **XSD-ul**
   descarcat din sectiunea *Help* a e-Facturii. Daca SFS cere alte denumiri de
   noduri, se aliniaza in `modules/efactura/sfs.py` (`build_invoice_xml`) —
   pe date reale, nu pe presupuneri.

### Verificat inainte de predare (31.08.2026)

| Ce | Rezultat |
|---|---|
| Obiecte Oracle `EFA_*` | 7, toate VALID |
| Setari | `configured = false` — asteapta credentialele; regim `semi`; doar persoane juridice |
| Document real de la client juridic → XML | contul **A-72**: vinzator IDNO `1026602001837`, cumparator IDNO `9999000161242`, 2 pozitii, total `222 000.00` |
| Trimitere fara credentiale | mesaj clar, nu exceptie |
| Jurnal | scrie corect (5 inregistrari) |
| Cele trei intrari fara autentificare | 401 / redirect la login |
