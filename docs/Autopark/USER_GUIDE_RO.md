# Ghidul utilizatorului — Parcul auto BEMOL

Cum se lucrează în sistem: planificarea livrărilor de combustibil,
conducerea curselor, calculul salariilor și setarea parametrilor. Fără
termeni tehnici.

**Adresa sistemului:** https://nufarul.eminescu.md/UNA.md/orasldev/autopark
Autentificarea se face cu contul dumneavoastră din rețea.

---

## Cuprins

1. [Ecranul conducerii](#1-ecranul-conducerii)
2. [Distribuția combustibilului: planul de livrare](#2-distribuția-combustibilului-planul-de-livrare)
3. [Executarea livrării](#3-executarea-livrării)
4. [Salarii și control](#4-salarii-și-control)
5. [Setări pe perioade](#5-setări-pe-perioade)
6. [Întrebări frecvente](#6-întrebări-frecvente)

---

## 1. Ecranul conducerii

Secțiunea **«Руководству»** din meniul din stânga. Trei carduri și un
rând cu ceea ce necesită o decizie.

![Ecranul conducerii](/UNA.md/orasldev/autopark/static/docs/01-board.png)

**Disponibilitatea combustibilului în rețea.** Cifra mare arată câte
stații sunt în regulă din numărul total. Mai jos: câte necesită livrare
astăzi, câte sunt aproape de minim, care stație este cea mai critică.
Culoarea benzii de sus: verde — totul în regulă, galben — există stații
aproape de minim, roșu — există stații care au nevoie de livrare astăzi.

**Costul livrării.** Cât costă transportul unui litru: salariile
șoferilor plus valoarea motorinei consumate peste normă. Alături — ponderea
din prețul litrului. Amortizarea și reparațiile nu sunt incluse: sistemul
nu dispune de aceste date.

**Ce a adus automatizarea.** Câte curse au fost formate prin calcul și cât
timp de lucru al logisticianului înseamnă acest lucru. Timpul este o
estimare la norma de 25 de minute de planificare manuală per cursă, iar
acest lucru este menționat explicit.

**Ce necesită decizie.** Unul până la trei rânduri în limbaj obișnuit.
Dacă nu este nevoie de intervenție, scrie exact acest lucru.

Butonul **«Распечатать»** trimite ecranul la imprimantă în aceeași formă.

---

## 2. Distribuția combustibilului: planul de livrare

Secțiunea **«Распределение топлива»**. Aici lucrează logisticianul.

![Distribuția combustibilului](/UNA.md/orasldev/autopark/static/docs/02-supply.png)

### Pasul 1. Verificarea stării rezervoarelor

Tabelul de sus conține toate rezervoarele rețelei. Coloanele:

| Coloana | Semnificație |
|---|---|
| Остаток | ultimul stoc cunoscut de combustibil |
| Мин. | stocul minim sub care nu se poate coborî |
| Залив | cât este permis să se toarne în rezervor |
| Продажи/сут | ritmul mediu de vânzări pe două săptămâni |
| Дней | în câte zile stocul ajunge la minim |
| В пути | combustibilul care este deja în drum spre această stație |
| Допустимо | cât se poate livra chiar acum |
| Источник | de unde provine cifra stocului |

Rândurile cu rezerva sub o zi sunt evidențiate — acestea sunt stațiile
care necesită livrare astăzi.

### Pasul 2. Calculul planului

Stabiliți orizontul (câte zile în avans analizăm) și apăsați
**«Рассчитать план»**. Calculul durează câteva secunde.

Câmpurile «Запас, дней» și «АЗС в рейсе» pot rămâne goale — atunci se
folosesc valorile din setări.

### Pasul 3. Citirea planului

Tabelul «План: что, куда и сколько везти» conține câte un rând pentru
fiecare rezervor care necesită livrare.

Coloana **«Рекомендовано»** — cât propune sistemul să se livreze.
Coloana **«Запас после, дн»** — pentru câte zile ajunge după livrare.
Coloana **«Примечание»** explică situațiile speciale:

| Notă | Semnificație |
|---|---|
| нет свободного объёма | rezervorul este aproape plin, nu are unde fi livrat |
| не хватило отсеков | toate compartimentele cisternelor sunt deja repartizate |
| запас превысит норму в днях | chiar și cel mai mic compartiment depășește rezerva săptămânală a acestei stații |
| недовоз до цели | se livrează mai puțin decât dorit: compartimentul se descarcă doar integral |

### Pasul 4. Verificarea repartizării pe compartimente

Tabelul «Рейсы и распределение по отсекам». Rândurile sunt în **ordinea
descărcării**: primul rând este ceea ce se descarcă primul, iar acesta
este întotdeauna compartimentul din coada cisternei.

Volumul din câmpul «Правка» poate fi modificat manual. După modificare
sistemul verifică imediat:

- **peste volumul compartimentului** — modificarea este respinsă, fizic
  imposibil;
- **peste volumul admis al rezervorului** — respinsă, ar însemna
  revărsare;
- **sub volumul compartimentului** — acceptată cu avertisment:
  compartimentul nu se golește complet, ceea ce tehnic este interzis.

### Pasul 5. Aprobarea

Alegeți parcarea și punctul final, atribuiți un șofer fiecărei cisterne și
apăsați **«Утвердить план и создать рейсы»**. Cursele apar cu starea
«запланировано».

Dacă pentru un segment al traseului lipsește distanța din nomenclator,
sistemul creează cursa și spune deschis care segment lipsește: fără el nu
se calculează parcursul normativ și, prin urmare, nici salariul.

---

## 3. Executarea livrării

Cardul «Исполнение поставок» din aceeași secțiune.

Cursa parcurge lanțul: **planificat → cerere de încărcare → încărcat →
în drum → livrat → recepționat de stație**. Butonul din ultima coloană
trece cursa la pasul următor.

Cele patru câmpuri de volum se completează pe parcurs:

| Câmp | Cine completează |
|---|---|
| План | sistemul, la calcul |
| Загружено | operatorul de încărcare |
| Документ | conform facturii |
| Принято | conform procesului-verbal de descărcare la stație |

Rândurile în care diferența depășește pragul sunt evidențiate. Bifa
**«только расхождения»** lasă în tabel doar aceste rânduri.

---

## 4. Salarii și control

Secțiunea **«Зарплата»** — calculul pentru fiecare cursă și totalul pe
șofer.

![Salarii](/UNA.md/orasldev/autopark/static/docs/04-payroll.png)

Formula este simplă: **parcurs normativ × tarif**. Parcursul normativ este
suma segmentelor traseului: parcare → punct de încărcare → stație → … →
parcare.

Important: salariul se calculează **nu pentru orice cursă**, ci pentru cea
dusă până la livrare. Cursa doar planificată sau încă în drum nu intră în
calcul.

Secțiunea **«Контроль»** arată abaterile: parcursul real față de normativ
și consumul real de motorină față de normă. Depășirile sunt evidențiate.

Cardul «Экономика перевозки и рейтинг водителей» din secțiunea
«Распределение топлива» oferă totalul perioadei: costul livrării unui
litru, încărcarea medie a cisternelor, consumul peste normă și
clasamentul șoferilor după respectarea traseului. Clasamentul se
calculează în procente față de normativ, nu în kilometri — altfel șoferul
curselor lungi ar apărea întotdeauna mai slab decât cel urban.

---

## 5. Setări pe perioade

Secțiunea **«Настройки по периодам»**. Aici angajatul rețelei modifică
totul singur.

![Setări pe perioade](/UNA.md/orasldev/autopark/static/docs/03-periods.png)

Regula principală: setarea **intră în vigoare de la o dată**, nu
înlocuiește valoarea anterioară. Dacă tariful crește de la 1 octombrie,
luna septembrie rămâne calculată la tariful din septembrie.

**Tariful șoferului.** Indicați data de început, tariful pe kilometru și,
dacă este cazul, suplimentul pe cursă. Perioada anterioară deschisă se
închide automat cu o zi înainte — nu trebuie închisă manual.

**Parametrii de planificare.** Plafonul rezervei în zile (de regulă 7),
orizontul de calcul, câte stații se grupează într-o cursă, pragul de
diferență semnificativă plan/fapt în procente.

**Limitele rezervorului.** Stocul minim, volumul admis și rezerva în zile
— pentru un rezervor anume. Câmpul gol înseamnă «se folosește valoarea
generală». Util pentru iarnă și pentru stațiile cu rulaj neobișnuit.

**Compartimentele cisternelor.** Volumele separate prin virgulă:
`6000, 6000, 6500, 6500`. Numărul 1 este lângă cabină, ultimul este cel
din coadă. Dacă indicați data de început, configurația anterioară rămâne
în istoric.

**Grupurile de stații.** Bifați stațiile deservite de o singură cursă și
salvați componența. Grupul poate fi modificat pe perioadă.

Câmpul de sus **«Показать, что действует на дату»** răspunde la întrebarea
«ce era în august»: introduceți data și veți vedea tariful și parametrii
valabili atunci.

---

## 6. Întrebări frecvente

**Sistemul trimite singur mașina?**
Nu. El calculează și propune, cursa se creează doar după ce apăsați
«Утвердить».

**De ce sistemul propune mai puțin decât este necesar?**
Compartimentul se descarcă doar integral. Dacă sunt necesari 8 000 l, iar
compartimentele au 6 250 l, sistemul livrează 6 250: două compartimente ar
însemna 12 500 l, peste volumul liber al rezervorului.

**De ce o stație apare în plan cu nota «nu există volum liber»?**
Rezervorul este aproape plin sau spre el este deja în drum combustibil.
Stația rămâne în listă intenționat: trebuie să vedeți că are nevoie și de
ce livrarea nu este posibilă acum.

**Am modificat tariful — se recalculează luna trecută?**
Nu. Tariful intră în vigoare de la data indicată, perioada închisă rămâne
neschimbată.

**De ce o cursă nu a intrat în salariu?**
Salariul se calculează pentru cursele livrate. Verificați starea: dacă
este «запланировано» sau «в пути», cursa încă nu se plătește.

**Unde văd de ce sistemul a ales tocmai această cisternă?**
În tabelul curselor se vede familia de combustibil și volumele
compartimentelor. O cisternă nu primește necesar de motorină dacă îi este
permisă doar benzina și nu transportă benzină și motorină în aceeași cursă.

---

Întrebări despre utilizare — responsabilului de parcul auto.
Întrebări tehnice — în `docs/Autopark/README.md`.
