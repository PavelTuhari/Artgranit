# SDA la Rogob — ce se schimbă din ianuarie 2027

> Dosar de prezentare pentru conducerea Rogob.
> Subiect: Sistemul de Depozit pentru Ambalaje (SDA), obligațiile care revin
> rețelei și modulul informatic propus peste platforma BIRO26 / OfficePlus.
> Elaborat: 25 august 2026. Bază: [sinteza normativă](LEGE_SDA_SINTEZA.md).

---

## 1. Rezumat pentru decizie

Din **25 ianuarie 2027** cel târziu, orice magazin din Republica Moldova care
vinde băuturi în sticlă, plastic sau metal încasează la casă o sumă returnabilă
— **depozitul** — și are obligații față de Administratorul SDA.

Pentru Rogob asta înseamnă trei lucruri:

**Vestea bună.** Rogob **nu are obligații de producător SDA**. Sistemul acoperă
exclusiv ambalajele de băuturi. Mezelurile, specialitățile din carne și
panificația „Plămădele" nu intră. Fără marcaj pe ambalaj, fără Registru propriu
de ambalaje, fără raportare lunară la data de 10, fără plata depozitului la data
de 25, fără tarif de administrare.

**Obligația reală.** Rogob este **comerciant**, prin cele peste 85 de magazine
proprii care vând băuturi la raft, și **comerciant HoReCa**, prin Rogob Grill
Cafe. Termenul de înregistrare la Administrator este de **6 luni de la
desemnarea acestuia** — desemnarea a avut loc în mai 2026, deci fereastra este
deja deschisă.

**Miza financiară.** Regulamentul scutește de punct propriu de returnare
magazinele **sub 100 m²** (respectiv sub 150 m² pentru tarabe în piață,
chioșcuri, benzinării și unități de alimentație publică). Magazinele
specializate de mezeluri sunt tipic sub acest prag. Diferența dintre a
demonstra la timp încadrarea și a nu o demonstra este diferența dintre câteva
obligații administrative și **zeci de puncte de returnare cu instalații
automate**, fiecare cu spațiu, personal și orar propriu.

**Prima acțiune recomandată, indiferent de restul deciziilor:** inventarierea
documentată a suprafeței comerciale a fiecărei unități. Este datul de intrare
pentru tot ce urmează și trebuie oricum depus la Administrator (pct. 78.3).

---

## 2. De ce Rogob nu este producător în sensul SDA

Regulamentul definește ambalajul supus sistemului ca ambalaj din sticlă,
plastic sau metal, cu volum între 0,1 și 3 litri, folosit pentru produsele de la
art. 54¹ alin. (3) din Legea 209/2016 — bere, cidru, vin, băuturi fermentate,
băuturi alcoolice și nealcoolice, apă minerală, apă potabilă, sucuri.

Producătorul, în sensul Regulamentului, este operatorul care **plasează pentru
prima dată pe piață produse ambalate în ambalaje SD**. Rogob produce mezeluri și
panificație. Niciunul dintre aceste produse nu intră în definiție.

> **De verificat înainte de depunere:** dacă Rogob îmbuteliază, importă sau
> distribuie sub marcă proprie orice băutură din lista de mai sus, calitatea de
> producător se activează pentru acel sortiment, cu setul complet de obligații.
> Similar, dacă livrările către cele peste 4 500 de magazine partenere includ
> băuturi, apare calitatea de **distribuitor** (pct. 14.7), cu obligația de a
> percepe depozitul mai departe pe lanț. Modulul propus acoperă ambele situații,
> dar rămân dezactivate până la confirmare.

---

## 3. Ce se schimbă concret în operațiuni

### 3.1 La casă (front)

Fiecare băutură vândută primește pe bon o **linie separată de depozit**, care
nu se confundă cu prețul produsului. Suma se calculează pe baza codului EAN, din
Registrul ambalajelor SD, și trebuie să fie **identică** în raft, în coș, pe bon
și în factură.

Aceasta e o cerință simplă în enunț și cea mai frecventă sursă de reclamații în
practică: dacă valoarea afișată la raft diferă de cea de pe bon, clientul vede
un preț și plătește altul. În platformă am tratat deja exact acest tip de
problemă la contorul de credite Biro26 și aplicăm aceeași disciplină — valoarea
se calculează într-un singur loc, pe server, și se propagă în toate afișările.

### 3.2 În magazin (informare)

Regulamentul cere afișarea a opt informații pentru consumatori (pct. 84): ce
produse intră în sistem, valoarea depozitului, dreptul de a returna în **orice**
punct din țară, adresa și orarul punctului propriu, modul de preluare,
modalitățile de rambursare, dreptul de a alege între numerar și tichet, și
situațiile în care rambursarea se refuză.

Pentru magazinele care intră în excepție se adaugă textul obligatoriu
„**Acest magazin nu funcționează ca punct de returnare a ambalajelor**", însoțit
de localizarea punctelor disponibile din zonă (pct. 92).

Modulul generează aceste afișaje automat, per unitate, cu datele corecte ale
punctului cel mai apropiat — nu ca fișiere redactate manual pentru 85 de adrese.

### 3.3 La punctul de returnare (unde există)

Se acceptă orice ambalaj SD, indiferent de unde a fost cumpărat produsul și
**fără a cere bonul fiscal**. Preluarea manuală permite rambursarea în numerar
sau prin tichet; instalația automată rambursează **doar prin tichet**, valabil
12 luni și preschimbabil la același comerciant.

Ambalajele returnate sunt **proprietatea Administratorului** din momentul
preluării — deci nu sunt marfă a Rogob, ci bunuri în custodie, cu evidență
separată.

### 3.4 În spate (back-office)

Evidența cerută expres de pct. 100: numărul de ambalaje returnate **în bucăți și
în kilograme**, defalcat pe material și volum, plus depozitele plătite
consumatorilor și cele încasate de la Administrator. Kilogramele se derivă
automat din greutatea unitară din Registru înmulțită cu numărul de bucăți — nu
e nevoie de cântărire la fiecare punct.

Administratorul plătește **tariful de gestionare** pentru fiecare ambalaj
preluat, prin transfer bancar, **cel mult la 14 zile**, diferențiat după metoda
de preluare, tipul și materialul ambalajului. Este un venit real al rețelei și
trebuie urmărit ca atare: modulul compară ce se cuvine cu ce s-a încasat și
semnalează întârzierile.

---

## 4. Harta de conformitate a rețelei — livrabilul care decide bugetul

Fiecare unitate Rogob se încadrează, în funcție de suprafața comercială și de
tipul amplasamentului, într-unul din trei regimuri:

| Regim | Condiție | Ce trebuie făcut |
|---|---|---|
| **A — punct propriu de returnare** | suprafață peste prag | punct în unitate sau la maximum 150 m, cu cel puțin același orar; decizie manual vs. instalație automată; personal și spațiu |
| **B — excepție, parteneriat cu APL** | până la 100 m², sau până la 150 m² la tarabe, chioșcuri, benzinării, alimentație publică | înregistrare cu suprafața declarată; afișaj obligatoriu; acord cu autoritatea locală; responsabil desemnat în relația cu Administratorul |
| **C — HoReCa** | Rogob Grill Cafe | predare directă către Administrator, fără punct public de returnare; tarif de gestionare pentru ambalajele predate |

Harta se construiește o singură dată, din datele de suprafață, și devine baza
dosarului de înregistrare, a planului de investiții și a afișajelor.

**Scenariile de cost, în termeni de ordin de mărime.** Dacă majoritatea celor 85
de unități se încadrează în regimul B, investiția se reduce la integrarea de
casă, afișaje și evidență. Dacă încadrarea nu poate fi demonstrată documentat la
termen, aceleași unități trec în regimul A, fiecare cu punct de returnare,
orar aliniat și, probabil, instalație automată. Nu avem încă datele de suprafață
pentru a cuantifica; le cerem tocmai pentru că această cifră este cea care
decide.

---

## 5. Ce propunem — modulul SDA peste BIRO26

Modulul se adaugă platformei existente, folosind aceleași mecanisme pe care
Rogob le are deja: datele stau în Oracle, în tabele proprii cu prefixul `SDA_`,
integrate cu nomenclatorul și codurile de bare din OfficePlus.

| Componentă | Ce rezolvă |
|---|---|
| **Registrul ambalajelor SD** | ce SKU poartă depozit, cu material, volum, greutate, categorie tarifară — sincronizat cu registrul public al Administratorului |
| **Rețea și regimuri** | unitățile, suprafețele, încadrarea A/B/C, punctele de returnare, orarele, instalațiile automate |
| **Depozit la casă** | linia de depozit pe bon și în coșul online, calculată server-side |
| **Chioșc de returnare** | scanare EAN, validare în Registru, refuz motivat, emitere tichet |
| **Registrul tichetelor** | cod unic, valoare, expirare la 12 luni, stare — emis, preschimbat în numerar, folosit la cumpărături; blochează dubla utilizare |
| **Predări către Administrator** | saci și sigilii, bucăți și kilograme, confirmarea centrului logistic |
| **Deconturi** | tariful de gestionare cuvenit vs. încasat, control al termenului de 14 zile |
| **Rapoarte și dosare** | evidența de la pct. 100, dosarul de înregistrare de la pct. 78, afișajele de la pct. 84 și 92 |

Detaliile tehnice — model de date, interfețe, integrări — sunt în
[specificația modulului](SPEC_SDA.md).

---

## 6. Calendar propus

| Etapă | Conținut | Când |
|---|---|---|
| **0. Inventar** | suprafețele comerciale ale tuturor unităților, tipul amplasamentului, sortimentul de băuturi vândut | imediat |
| **1. Harta de conformitate** | încadrarea A/B/C per unitate, scenarii de cost, decizia manual vs. automat | 2–3 săptămâni de la inventar |
| **2. Dosarul de înregistrare** | notificarea digitală semnată electronic către Administrator, cu cele opt blocuri de la pct. 78 | în fereastra de 6 luni de la desemnare |
| **3. Acorduri cu APL** | pentru unitățile din regimul B, lista locațiilor aprobată de autoritatea locală | paralel cu etapa 2 |
| **4. Implementare informatică** | registru, casă, chioșc, tichete, deconturi, rapoarte | până în toamna 2026 |
| **5. Pilot** | un oraș sau un grup de magazine, cu date reale | înainte de decembrie 2026 |
| **6. Punere în funcțiune** | întreaga rețea | **25 ianuarie 2027** |

Etapele 0 și 1 nu depind de nicio decizie privind furnizorul de software și pot
începe acum. Sunt și cele care aduc cea mai mare parte a valorii.

---

## 7. Ce nu este încă stabilit prin lege

Valoarea depozitului, nivelurile tarifului de administrare și ale tarifului de
gestionare, grafica mărcii SDA, formatul raportării și specificațiile codului de
bare urmează să fie stabilite prin ordin al ministrului mediului și prin
documentele Administratorului.

Consecința practică: **niciuna dintre aceste mărimi nu se scrie în cod.** În
modul sunt parametri cu perioade de valabilitate, exact ca prețurile din
OfficePlus — o valoare schimbată retroactiv recalculează corect deconturile deja
emise. Aceasta este singura arhitectură care rezistă la un sistem încă în
construcție normativă.

---

## 8. Ce vă cerem pentru pasul următor

1. **Suprafețele comerciale** ale unităților — există în OfficePlus sau trebuie
   inventariate pe teren?
2. **Confirmarea** că Rogob nu îmbuteliază și nu importă băuturi sub marcă
   proprie.
3. **Confirmarea** dacă livrările către magazinele partenere includ băuturi.
4. Persoana desemnată pentru relația cu Administratorul SDA.

Cu răspunsurile la primele trei putem livra harta de conformitate și o estimare
de cost pe scenarii în două–trei săptămâni.
