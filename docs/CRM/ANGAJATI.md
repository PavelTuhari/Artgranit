# Angajați: înregistrare, dezactivare, parolă, raport pe persoane

**Cerința proprietarului (10.09.2026):** *«Angajații să fie înregistrați de
mine ca administrator, iar în lista angajaților să apară data înregistrării,
posibilitatea de dezactivare a contului, parola standard cu posibilitate de
recuperare, adresa de e-mail și numărul de contact. În RAPORT să fie posibil
de ales raportul pe persoane și total.»*

Totul lucrează pe Oracle real (OfficePlus 11g). Regimul demo rămâne separat —
el este un alt chiriaș (`OWNER_KIND/OWNER_ID`) și nu se amestecă cu conturile.

---

## 1. Ideea: utilizatorul rămâne al ERP-ului

În UNA nu există un tabel de utilizatori. **Omul este un nod în arborele de
configurare**:

| Unde | Ce |
|---|---|
| `A$ADM` | nodul: `OBJ_TYPE=7`, `OBJ_SUBTYPE=0`, părinte = grupul `(7,-1)`, `SECTION` = `OBJ_ID` ca text (index unic global `A$ADM$UQ`) |
| `A$ADP` | proprietățile: `USERNAME, ID, ENABLED, ADMIN, FAMILIA, PASSDATE, ENCODED, PASSWORD, GROUPID, PASSATTEMPTS, PASSDAYS, AUTOLOCKEDDATE` |
| `A$UTIL.LOGIN(user, pass)` | autentificarea; întoarce `OBJ_ID`. Lanțul din `UniacCLNT`: `uDMA.cpp RegisterUser()` → `UN$USERPARAMS.REGISTERUSER` → `a$util.login` |
| `A$UTIL.SET_PASSWD(obj_id, pass)` | schimbarea parolei (respectă setările ERP: deschisă sau codificată) |

De aceea **nu s-a creat un registru paralel de utilizatori**. `CRM_EMPLOYEE`
doar adaugă ce lipsește în arbore (e-mail, telefon, data înregistrării,
observații) și ține cheia `OBJ_ID` a nodului.

Capcane verificate pe baza reală:

* booleanele în `A$ADP` se scriu **`'1'`/`'0'`** (`A$ADP$V` face
  `decode(bvalue, 1, 'true', 0, 'false')`); cu `'T'` → `ORA-01722` la login;
* `SECTION` e unic **global**, nu în grup: se ia întâi `A$ADM$SQ.NEXTVAL`;
* blocarea contului = `Enabled = false`, exact cum o înțelege ERP-ul;
  parolă greșită crește `PassErrors`, iar după `PassAttempts` ERP-ul singur
  pune `Enabled=false` + `AutoLockedDate`.

## 2. Obiecte Oracle — `modules/crm/sql/04_crm_employee.sql`

```
CRM_EMPLOYEE (OBJ_ID PK = A$ADM.OBJ_ID, USER_ID, USERNAME unic, FULL_NAME,
              EMAIL, PHONE, GROUP_ID, ENABLED, IS_ADMIN, REG_DATE, PASS_DATE,
              LOCKED_DATE, NOTES, SRC, SYNCED)
CRM_EMPLOYEE_LOG (jurnal: created/updated/enabled/disabled/password/synced)
CRM_EMP_SYNC     (pachetul de sincronizare)
```

### Sincronizarea în ambele părți (prin triggere, ca în ERP)

| Trigger | Unde | Ce face |
|---|---|---|
| `CRM_EMPLOYEE_AIU` | `AFTER INSERT OR UPDATE ON CRM_EMPLOYEE` | `CRM_EMP_SYNC.to_erp(...)` scrie `Enabled`, numele, e-mailul, telefonul în `A$ADP` |
| `CRM_EMP_ADP_AIU` | `AFTER INSERT OR UPDATE ON A$ADP` | orice schimbare făcută din **uniConf** ajunge în fișă |

`A$ADP` este tabel de bază al ERP-ului — pe el scrie tot configuratorul.
De aceea triggerul e făcut sigur prin construcție:

1. `WHEN (NEW.KEY IN (...))` — se trezește doar la cheile utilizatorului;
2. apel **dinamic** (`EXECUTE IMMEDIATE`) — un pachet lipsă sau invalid nu
   poate invalida triggerul și bloca scrierile din uniConf;
3. `EXCEPTION WHEN OTHERS THEN NULL` — sincronizarea nu rupe niciodată o
   operație a ERP-ului;
4. **fără `COMMIT` și fără `PRAGMA AUTONOMOUS_TRANSACTION`** — trigger-ul
   trăiește în tranzacția celui care scrie;
5. `g_busy` — pază contra buclei fișă → arbore → fișă;
6. `to_erp` primește valorile ca parametri (`:NEW.*`), nu face `SELECT` din
   `CRM_EMPLOYEE` (ar da `ORA-04091`, tabel în mutație — eroarea a existat).

## 3. Interfața — pagina «Angajați»

`modules/crm/static/crm_employees.js` + secțiunea `#sec-employees` din
`crm_app.html`. Punctul de meniu apare **doar în portal**; clientul din
cabinet nu-l vede (`CAB ? [] : ['employees']`), iar API-ul îi răspunde 403
(`office_only` din `routes_employees.py`).

Ce vede administratorul:

* **lista**: nume, utilizator, e-mail, telefon, grup, **data înregistrării**,
  starea (activ / dezactivat), administrator;
* **fișa**: nume, e-mail, telefon, observații — se salvează și ajung în arbore;
* **butoane**: `Salvează`, `Parolă nouă` (recuperare — se arată o singură
  dată, cu buton de copiere), `Verifică parola`, `Dezactivează` / `Activează`;
* **înregistrare**: utilizator, nume, grup, e-mail, telefon → contul apare
  imediat în ERP, cu parolă standard generată;
* **`Sincronizează`**: citește tot arborele în fișe (`CRM_EMP_SYNC.pull_all`).

Parola standard: 10 semne, fără glife care se confundă la dictare (`0 O 1 l I`).

### API (`/api/v2/employees`)

| Metodă | Adresă | Ce face |
|---|---|---|
| GET | `/api/v2/employees` | lista (`?q=`, `?enabled=`) |
| POST | `/api/v2/employees` | înregistrează contul, întoarce parola o singură dată |
| GET/PUT | `/api/v2/employees/<obj_id>` | fișa / salvarea datelor de contact |
| POST | `.../enabled` | dezactivare / activare (`Enabled` în arbore) |
| POST | `.../password` | parolă nouă prin `a$util.set_passwd` |
| POST | `.../check` | verifică o parolă prin `a$util.login` |
| POST | `/api/v2/employees/sync` | citește arborele |
| GET | `/api/v2/employees/events` | jurnalul |

## 4. Raportul pe persoane și total

Slug nou `by_person` (`modules/crm/reports.py`): pe fiecare responsabil —
proiecte, buget, sarcini, executate, întârziate — plus rândul **TOTAL**.
Selectorul de persoane e în capul oricărui raport (`crmReportPerson`);
lista vine din `/api/v2/meta` → `persons`. Exportul CSV păstrează filtrul.

## 5. Verificat pe baza reală (10.09.2026)

* 35 de angajați reali citiți din arbore (26 activi, 6 grupuri);
* cont de test creat → `a$util.login` a întors `OBJ_ID`;
* parolă greșită → mesajul ERP cu încercările rămase;
* dezactivare → ERP refuză logarea («Inscriptia utilizatorului … este blocata»);
* activare → logarea merge din nou;
* parolă nouă → cea veche nu mai merge;
* e-mail / telefon / nume scrise din fișă apar în arbore, iar schimbarea din
  uniConf apare în fișă;
* nodul de test a fost șters, scrierile ERP-ului au continuat normal;
* raportul `by_person`: 5 persoane + rândul total (10 proiecte, 447 700 MDL,
  100 sarcini, 49 executate, 23 întârziate).

## 6. Instalare

```bash
python3 modules/crm/scripts/crm_deploy.py --file 04_crm_employee.sql
```

Apoi, o singură dată, umplerea fișelor din arbore: butonul `Sincronizează`
din pagină sau `begin CRM_EMP_SYNC.pull_all; end;`.

## 7. Fișiere

| Fișier | Ce |
|---|---|
| `modules/crm/sql/04_crm_employee.sql` | tabele, pachet, cele două triggere |
| `modules/crm/employees.py` | reguli pure (nume, parolă, validări) |
| `modules/crm/store_employees.py` | SQL: listă, creare, parolă, activare, sync |
| `modules/crm/routes_employees.py` | API-ul, `office_only` |
| `modules/crm/static/crm_employees.js` | pagina |
| `modules/crm/reports.py` | raportul `by_person`, `persons()` |
| `tests/test_crm.py` | reguli, DDL sigur, API închis în cabinet, raport în 3 limbi |

---

## 8. Ajustările cerute pe capturile prototipului (11.09.2026)

Proprietarul a trimis două capturi din *Demo CRM* (Delphi) cu trei observații;
toate trei sunt făcute în CRM-web:

| Observația din captură | Ce s-a făcut |
|---|---|
| «de adaugat mapa cu angajati» (săgeata arată locul din meniu, sub *Clienți*) | punctul **Angajați** stă acum imediat după *Clienți*, nu la coada meniului; în cabinetul clientului rămâne ascuns |
| «sa fie adaugat sageata de alegere din lista angajatilor» (câmpul *Исполнитель*) | *Executant* (sarcini) și *Manager* (proiecte) sunt **liste de alegere**: tipul de câmp nou `PERSON`. Lista = angajații activi (conturile ERP) plus numele care apar deja în date; dacă valoarea veche nu e în listă, ea rămâne prima opțiune, deci nimic nu se pierde. În baza de date rămâne tot numele (în SQL `PERSON` se poartă exact ca `TEXT`) |
| «ar fi bine de adaugat calendarul pentru a alege data» | câmpurile de dată sunt `<input type="date">` — calendarul nativ al browserului, cu iconița din dreapta (*Început*, *Termen*, *Sdare*, *Termen tender* etc.) |

În cabinetul clientului lista angajaților nu se vede: `/api/v2/meta` întoarce
doar numele care apar în datele lui.

---

## Adrese live

| Ce | Adresa |
|---|---|
| Lista angajaților | <https://officeplus.md/UNA.md/orasldev/crm/#employees> · <https://nufarul.eminescu.md/UNA.md/orasldev/crm/#employees> |
| Capitolul din ghid (cu capturi) | <https://officeplus.md/UNA.md/orasldev/b26docs/CRM/GHID_CRM.html#angajati> |
| Raportul pe angajați | <https://officeplus.md/UNA.md/orasldev/crm/#reports> |
