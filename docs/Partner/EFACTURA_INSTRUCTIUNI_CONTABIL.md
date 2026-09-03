# e-Factura — instrucțiuni pentru contabilul OfficePlus

Cum se configurează integrarea cu SIA „e-Factura" (SFS) și cum se transmite
factura fiscală electronică dintr-un document deja întocmit — din back-office-ul
web OfficePlus sau din back-office-ul nativ una.md, prin acțiunea
**«Выгрузить в e-Factura»**.

## 1. Ce face integrarea, în trei propoziții

Documentul (contul / factura) întocmit în ERP se trimite ÎN ZIUA eliberării
în SIA e-Factura, **nesemnat**. Acolo el apare la «facturi de semnat» și se
semnează de cei doi semnatari (director, contabil-șef) cu semnătura
electronică — exact ca pînă acum, doar că datele nu se mai bat de mînă.
După semnături factura devine acceptată, iar starea ei se vede și în ERP.

## 2. Configurarea (o singură dată)

Pagina: portal → meniul **e-Factura** → *Setări* (adresa
`/UNA.md/orasldev/efactura/`). Se completează:

| Cîmp | Ce se scrie |
|---|---|
| Adresa serviciului | mediul **real**: `https://efactura-api.sfs.md/Service.svc` (pentru probe: `https://apiefactura-pre.sfs.md/Service.svc`) |
| Utilizator API / parola — primul semnatar | contul API creat pe `https://sfs.md/` → Cabinetul personal → SIA e-Factura → Setări → Utilizatorii companiei → «Creați utilizator API» (de regulă directorul) |
| Utilizator API / parola — al doilea semnatar | la fel, pentru contabilul-șef; opțional dacă firma semnează cu o singură persoană |
| Numele semnatarilor | pentru afișare |
| Seria facturii | seria firmei (ex. `AA`); numărul îl dă SFS la semnare |
| Cota TVA implicită | 20 — se folosește doar cînd documentul din ERP nu are TVA calculat |
| Rechizitele vînzătorului (`seller_*`) | **se lasă GOALE** — se iau din firma ERP-ului; se completează doar pe mediul de probă |
| Doar persoane juridice | pornit: e-Factura se emite doar clienților cu IDNO |

Apoi **«Testează conexiunea»** → trebuie ✅ pentru ambele conturi. Dacă apare
«Accesul e restricționat (403)», IP-ul serverului nu e deschis la SFS — se
cere la `asistenta@sfs.md` (o face firma IT).

Condiții pe care le asigură SFS, nu noi: contul API se creează cu semnătura
electronică a persoanei; accesul se dă pe adresa IP a serverului.

## 3. Transmiterea din back-office-ul web OfficePlus

1. Portal → **e-Factura** → secțiunea *Documente*.
2. Se scrie **codul documentului** (cel din ERP) → «👁 Vezi XML» ca să
   verificați datele (opțional) → **«📤 Trimite în e-Factura»**.
3. Rezultat:
   - **SENT** — factura e în e-Factura; urmează semnăturile pe `sfs.md`;
   - **ERROR** cu mesaj în română — cauza e scrisă (de obicei: data
     documentului nu e de azi, sau clientul nu are IDNO).
4. «Actualizează statusurile» aduce din SFS ce s-a acceptat / respins.

Clientul-persoană juridică poate cere singur factura electronică din
cabinetul lui de pe site (butonul «e-Factura» lîngă comandă) — merge pe
aceeași cale și se vede în aceeași listă.

## 4. Transmiterea din back-office-ul nativ una.md — acțiunea «Выгрузить в e-Factura»

Documentul se întocmește ca de obicei. În formularul **«CONT la plata»**,
în lista de acțiuni — lîngă «Сгенерировать счета» — există acțiunea
**«Выгрузить в e-Factura»** (înregistrată 02.09.2026, obiectul 11522 al
configuratorului, exact ca acțiunea contului de plată). Ea execută în Oracle:

```sql
BEGIN commit; EFA_NATIVE.send_doc_pr(:nrdoc); END;   -- nrdoc = codul intern al documentului
```

Ce se întîmplă: Oracle apelează serverul web (ca la «Contul de plată»),
serverul construiește XML-ul, îl trimite la SFS și scrie rezultatul în
`EFA_DOC`. Acțiunea întoarce un text: `SENT …` sau `ERROR: <motivul>`.
Starea se poate citi oricînd:

```sql
SELECT EFA_NATIVE.doc_status(:COD) FROM dual;   -- SENT / ERROR / ACCEPTED / … + mesaj
```

Pentru integratori: funcția `EFA_NATIVE.send_doc(p_doc)` întoarce răspunsul
complet; procedura `send_doc_pr` ridică `ORA-20000` la eroare, ca aplicația
nativă să afișeze mesajul.

## 5. Regulile SFS de care depinde fluxul zilnic

1. **Data facturii fiscale este ziua transmiterii.** SFS primește facturi
   doar cu data de azi (sau pînă la 10 zile în viitor). Contul de plată
   poate fi de ieri sau de acum o săptămînă — nu contează: la «Выгрузить в
   e-Factura» factura fiscală se emite cu data de AZI, iar data contului
   rămîne neschimbată în ERP.
2. **Numărul facturii îl dă SFS** la prima semnătură; numărul nostru
   (A-81) rămîne ca referință în ERP.
3. **Denumirea și adresa** părților se iau de SFS din registrul fiscal după
   IDNO — ce e scris în ERP e orientativ.
4. **Doi semnatari, două cozi**: după prima semnătură factura trece în coada
   celui de-al doilea; după a doua devine acceptată.
5. e-Factura e pentru **persoane juridice** (cu IDNO); pentru persoane
   fizice nu se emite.

## 6. Dacă ceva nu merge

| Ce vedeți | Ce înseamnă | Ce faceți |
|---|---|---|
| «clientul nu are IDNO» | persoană fizică | nu se emite e-Factura |
| «Accesul e restricționat (403)» | IP-ul serverului nu e la SFS | firma IT → asistenta@sfs.md |
| «eroare SOAP … pagină HTML (500)» | parola API greșită sau cont pe alt mediu | verificați contul pe sfs.md, re-introduceți parola în Setări |
| «IDNO-ul clientului … nu trece cifra de control» | IDNO greșit în fișa clientului (refuz local, fără apel la SFS) | corectați IDNO-ul în fișa clientului |
| «Buyer … isn't registered in the fiscal registry» | IDNO corect ca formă, dar necunoscut registrului SFS | verificați cu clientul IDNO-ul; pe mediul de probă registrul poate fi incomplet |
| «Validation failed …» | XML în afara schemei SFS | firma IT (jurnalul `EFA_CALL`) |

Totul ce s-a trimis și ce a răspuns SFS e în jurnalul modulului (pagina
e-Factura → *Jurnal*), cu parola mascată.
