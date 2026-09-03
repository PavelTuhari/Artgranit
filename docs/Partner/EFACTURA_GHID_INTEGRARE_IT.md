# e-Factura — ghid de integrare si testare pentru firma IT

Pentru echipa care dezvolta si intretine modulul `modules/efactura/` al
platformei Artgranit. Principiul de baza, cerut de proprietar (02.09.2026):
**firma IT isi deschide PROPRIUL cont de test in e-Factura si testeaza totul
pe el, fara sa deranjeze clientul.** Clientul intra in joc o singura data,
la go-live, cu contul lui real.

## 1. Contul de test al firmei IT — o singura data

1. E-mail la **asistenta@sfs.md**: IDNO-ul firmei IT, numele/IDNP-ul a doi
   angajati (director + contabil sau doi dezvoltatori cu semnatura
   electronica), rolul, e-mail, telefon si **IP-ul extern al serverului** de
   pe care se fac apelurile (nu al laptopului). Model: `SCRISOARE_ACCES_EFACTURA.md`.
2. Dupa raspuns (la noi: tichet TT1651472, o zi lucratoare): intrare cu
   semnatura electronica pe `https://preproductie.sfs.md/` → Cabinetul
   personal → SIA e-Factura → Setări → Utilizatorii companiei → «Creați
   utilizator API» — cite unul pentru fiecare semnatar.
3. Parolele se pun in macOS Keychain (`security add-generic-password -s
   efactura-api-pre -a <utilizator> -w`), nu in fisiere.
4. Verificare: `GET https://apiefactura-pre.sfs.md/Service.svc?wsdl` de pe
   server → 200. Apoi `modules/efactura/scripts/efactura_smoke.py` (fara
   `--send` intii).

De aici incolo orice test — inclusiv cu documente REALE ale clientului — se
face pe contul firmei IT, pe mediul de proba. Furnizorul din XML e firma IT
(setarile `seller_*`), cumparatorul si marfa vin din documentele clientului.
SFS oricum inlocuieste denumirile din registru dupa IDNO.

## 2. Arhitectura modulului (ce atinge ce)

| Fisier | Rol |
|---|---|
| `sfs.py` | clientul SOAP (WS-Security UsernameToken, SOAPAction cu `IService`, `<request>` in namespace DataContract), `build_invoice_xml` dupa XSD, traducerea erorilor de retea |
| `journal.py` + `sql/02_efa_call.sql` | jurnalul complet al apelurilor (`EFA_CALL`): plic cu parola mascata, raspuns brut, HTTP, durata, verdict |
| `testff.py` | motorul probei: validare (0,01–10 lei, max 5 pozitii), XML, trimitere, cozi de semnare, `ping` (adresa + IP + conturi) |
| `controller.py` | drumul documentelor REALE din ERP: `build_payload` (firma, client, pozitii, cota TVA), `send`, `status`, `refresh_statuses`; regula datei |
| `store.py` + `sql/01_efa_core.sql` | `EFA_SETTING` (conturi, adresa, `seller_*`, `seria`, `tva_rate`), `EFA_DOC` (starea fiecarui document), `EFA_LOG` |
| `routes.py` | `/` admin, `/admin/*`, `/my/*` (cabinetul clientului), `/api/*` (X-API-Key, pentru aplicatii native), `/test*`, `/widget.js` |
| `templates/efactura_test.html` | pagina probei: cont API ad-hoc, rechizite, pozitii, rezultat clar, jurnal |
| `scripts/efactura_deploy.py` | instalatorul DDL propriu (idempotent) |
| `scripts/efactura_smoke.py` | proba cap-coada de pe Mac, cu parolele din Keychain |
| `tests/test_efactura.py` | 36 de teste: izolare, XML vs XSD (xmllint), contract SOAP vs WSDL, cozi, fereastra de date, erori mascate |

Regula nr. 1/2 din `CLAUDE.md`: totul sta in `modules/efactura/`; nimic in
`app.py`/fisierele comune. Widget-ul pentru alt modul = o linie:
`<script src="/UNA.md/orasldev/efactura/widget.js"></script>`.

## 3. Cum se testeaza (fara client)

### 3.1 Proba de 1 leu, automat
```bash
EFA_USER_1=<u1> EFA_PASS_1="$(security find-generic-password -s efactura-api-pre -a <u1> -w)" \
EFA_USER_2=<u2> EFA_PASS_2="$(security find-generic-password -s efactura-api-pre -a <u2> -w)" \
venv/bin/python modules/efactura/scripts/efactura_smoke.py --send
```
Asteptat: ✅ pe ambele conturi, `PostInvoices: ACCEPTATA … TotalInvoicesPosted 1`,
coada Order 1 cu o factura. Apoi semnatura pe portal si re-verificarea
cozilor (Order 1 → Order 2 → acceptate).

### 3.2 Documente reale, pe mediul de proba
Setarile back-office (`/UNA.md/orasldev/efactura/`): adresa = mediul de
proba, conturile firmei IT, `seller_*` = firma IT. Apoi:
- din back-office: cod document → «Trimite in e-Factura»;
- din API-ul intern: `POST /UNA.md/orasldev/efactura/api/send/<cod>` cu
  `X-API-Key` (token-ul `BIRO26_API_TOKEN` din `.env`), corp optional
  `{"override_date": "YYYY-MM-DD"}` pentru documente vechi (DOAR pe proba);
- din cabinetul clientului: butonul de pe comanda lui (`/my/send/<cod>`).
Asteptat: `EFA_DOC.STATUS = SENT`, factura in Order 1.

### 3.3 Ce se verifica dupa fiecare schimbare de cod
```bash
venv/bin/python -m pytest tests/test_efactura.py -q      # 36 teste, ~2 s
```
Testul `test_validates_against_the_official_xsd` valideaza XML-ul cu
`xmllint` fata de `docs/Partner/sfs/TaxInvoiceSchema.xsd`; daca SFS
publica un XSD nou, se inlocuieste fisierul si se ruleaza testele.

## 4. Regulile SFS care nu sint scrise nicaieri (invatate pe 02.09.2026)

Lista completa, cu raspunsurile care le-au dezvaluit:
`EFACTURA_SCENARIU_TESTARE.md`, §2. Pe scurt: XSD-ul oficial;
`CreationMotiv` 4/5; nodurile goale obligatorii (`Seria`, `Number`,
`BankAccount` x2, `VehicleLogbook`, `Redirections`); data doar azi…+10;
normalizarea din registru; erorile SOAP mascate de HTML; accesul pe IP.

## 4a. Actiunea din back-office-ul nativ una.md

Back-office-ul nativ (uniConf.exe) tine actiunile formularelor in
`A$ADM` (obiect: tip 1/subtip 2, parinte = tipul de document, nume RU/RO/EN,
`SECTION` unic) si `A$ADP` (proprietati; `SQL1` = blocul PL/SQL executat cu
`:nrdoc`). «Contul de plata» e obiectul 11476. Actiunea e-Factura e clona
lui — `scripts/efactura_native_action.py` (idempotent; `--remove` o
scoate) — cu `SQL1 = BEGIN commit; EFA_NATIVE.send_doc_pr(:nrdoc); END;`.
Pachetul `EFA_NATIVE` (`sql/03_efa_native.sql`) face UTL_HTTP pe
`http://officeplus.md/api/biro26/efactura/…` (HTTP simplu — Oracle 11g nu
are wallet TLS; prefixul e singurul neredirectat la HTTPS). Cheia:
`YBIRO_SETTINGS.API_GEN_KEY`. Pe 02.09.2026: OBJ_ID 11522, verificat din
Oracle cu un document real (`HTTP 200, SENT`) si cu drumurile de eroare.

## 5. Go-live la client — checklist

1. Clientul (firma care EMITE facturile) isi creeaza conturile API pe
   `https://sfs.md/` -> Cabinetul personal -> SIA e-Factura / Setari ->
   Utilizatorii companiei -> «Creati utilizator API» — cite unul per semnatar.
2. Nimic altceva de cerut la SFS: pentru mediul real NU se acorda acces
   suplimentar si NU exista lista de IP (raspuns CTIF la TT1651472,
   03.09.2026). Lista de IP e doar o regula a mediului de test.
3. Setari e-Factura: adresa `https://efactura-api.sfs.md/Service.svc`,
   conturile clientului, `seller_*` GOALE (furnizorul = firma din ERP),
   `seria` reala, `tva_rate` confirmat de contabil, `only_companies`,
   `creation_motiv` dupa statutul TVA al clientului (platitor 4|5,
   neplatitor 1|2|3 — SFS refuza valoarea din cealalta grupa).
4. «Testează conexiunea» din admin → ✅ pe ambele conturi (metoda `Test`,
   nu trimite nimic).
5. Prima factura reala: un document emis AZI, valoare mica, catre un client
   real → `SENT` → semnaturi pe `sfs.md` → `refresh_statuses` o aduce ca
   acceptata.
6. Proces: factura se trimite in ziua eliberarii (fereastra SFS).

## 6. Depanare rapida

| Simptom | Cauza | Unde se vede |
|---|---|---|
| 403 + pagina HTML | pe mediul de TEST: IP-ul serverului nu e pe lista SFS; pe mediul real nu exista lista — de verificat contul | «Verifică contul» → linia `ip_server` |
| 500 + pagina HTML | fault SOAP mascat (parola gresita / cont pe alt mediu) | jurnal `EFA_CALL`, `result = html` |
| `Status 3, Validation failed` | XML in afara XSD | jurnal, coloana «Ce a răspuns SFS» |
| `Object reference not set` | lipseste un nod «gol obligatoriu» | compara cu `docs/Partner/sfs/ModelFacturafiscala.xml` |
| `Specify the correct date` | document mai vechi de azi | refuzat local, mesaj in romana |
| factura nu apare in Order 2 | prima semnatura nu s-a pus | portal, coada Order 1 |
