# Cartea IV — Măsurarea: de unde știm că funcționează

> Patru cifre pentru fiecare zi, patru pentru sănătatea pe termen lung.
> Restul sunt detalii care distrag.

---

## 1. Cele patru cifre de zi cu zi

| Cifra | Unde se vede | Ce vă spune |
|---|---|---|
| **Comenzi pe zi** | pâlnia, „Воронка за 7 дней” | dacă magazinul vinde azi |
| **Vizitatori din căutare** | Google Analytics | dacă munca de SEO dă roade |
| **ROI pe canal** | SEOForge → «ROI» | dacă banii de reclamă se întorc |
| **Pagini indexate** | Google Search Console | dacă Google ne vede deloc |

Dacă aveți timp pentru una singură, alegeți **comenzi pe zi**. Restul explică
de ce cresc sau scad.

---

## 2. Pâlnia vânzărilor

`/UNA.md/orasldev/funnel`

### 2.1. Ce arată fiecare bloc

| Blocul (text pe ecran) | Înseamnă | Cum se citește |
|---|---|---|
| „Воронка за 7 дней” | Pâlnia pe 7 zile | **forma**, nu cifra unei zile; căderi de o zi sunt normale |
| „Топ групп за 30 дней” | Top grupe | aici decideți unde puneți efort |
| „Топ товаров за 30 дней” | Top produse | ce scoateți în față în postări |
| Lista comenzilor blocate | comenzi intrate, nelivrate | fiecare rând = bani blocați |

### 2.2. Întrebarea săptămânală

Grupele din top trei sunt aceleași cu cele pe care le promovăm? Dacă nu —
ori promovăm ce nu se vinde, ori avem o grupă care se vinde singură și ar
crește mult cu puțin ajutor.

---

## 3. ROI: formula și citirea ei

`/UNA.md/orasldev/seoforge` → «ROI» → perioada → **«Показать»**

### 3.1. Formula

```
ROI = (venit − cheltuit) ÷ cheltuit × 100 %
```

| ROI | Înseamnă | Ce faceți |
|---|---|---|
| sub 0 % | ați dat mai mult decât ați primit | opriți sau schimbați, după 2 luni de date |
| 0–50 % | banii se întorc, câștig mic | reglați: alte cuvinte, alte ore, alte grupe |
| peste 100 % | fiecare leu aduce doi | **creșteți bugetul aici**, nu aiurea |

### 3.2. CPC și CPA

- **CPC** — cât plătiți pentru un clic. Crește brusc? concurență nouă.
- **CPA** — cât costă o comandă. Comparați-l cu **profitul** de pe o comandă
  medie, nu cu suma ei. Un CPA de 200 lei la o comandă de 1 500 lei cu 15 %
  marjă înseamnă pierdere.

> **Atenție:** ROI-ul este gol dacă nu s-au introdus cheltuielile reale în
> «Факты». Ecranul nu inventează date.
> Vedeți [Cartea II, punctul 4.1](GHID_2_EXECUTANT.md).

---

## 4. Cifrele care arată sănătatea pe termen lung

Cele patru de la punctul 1 spun ce s-a întâmplat ieri. Următoarele patru
spun dacă afacerea online **crește** sau doar se agită.

### 4.1. Valoarea medie a comenzii

```
Valoarea medie = venitul total ÷ numărul de comenzi
```

Crește când funcționează seturile, pragul și produsele complementare
(pârghia 6.3 din [Cartea I](GHID_1_DIRECTOR.md)). Este cifra care se mișcă
**fără un leu în plus de reclamă** — de aceea se privește prima.

### 4.2. Rata de revenire

```
Rata de revenire = clienți cu 2+ comenzi ÷ total clienți
```

Pentru consumabile, aceasta este cifra care decide dacă afacerea e sănătoasă.
Un magazin care vinde o singură dată fiecărui client trebuie să cumpere
clienți la nesfârșit. Crește prin campania de comandă repetată și prin
livrare care nu dezamăgește.

### 4.3. Cât costă un client nou și cât aduce

```
Cost pe client nou = cheltuiala pe reclamă ÷ clienți noi
Valoarea pe viață  = valoarea medie × numărul mediu de comenzi
```

Regula simplă: **un client trebuie să aducă de câteva ori mai mult decât a
costat.** Dacă un client-organizație comandă de patru ori pe an, puteți
plăti pentru el mult mai mult decât pentru unul care cumpără un caiet.

Aceasta este justificarea numerică a pârghiei 6.1.

### 4.4. Rata de conversie

```
Conversie = comenzi ÷ vizitatori × 100 %
```

Dacă traficul crește și conversia scade, aduceți publicul greșit — sau
pagina nu răspunde la ce caută el. A crește conversia de la 1 % la 1,3 %
înseamnă cu o treime mai multe comenzi **la același trafic**.

### 4.5. Semnalele mici, dinaintea comenzii

Nu toți cumpără azi. Urmăriți și:

- cereri de ofertă de la organizații;
- telefoane primite din site;
- adăugări în coș fără finalizare (unde se pierde omul?).

Pentru un magazin B2B, **cererea de ofertă este mai valoroasă decât o
comandă mică** — începe o relație, nu o tranzacție.

---

## 5. Ce nu măsoară sistemul singur

Sistemul vede comenzile și cheltuielile. **Nu vede** vizitatorii — asta o
face Google.

| Instrumentul | Ce dă | Starea |
|---|---|---|
| **Google Analytics** | câți oameni, de unde, ce pagini | contorul e instalat pe officeplus.md |
| **Google Search Console** | ce interogări ne aduc oameni, ce poziții avem, câte pagini a indexat | **trebuie confirmat dreptul asupra domeniului** |

**Search Console este gratuit și obligatoriu.** Fără el nu știți dacă Google
a citit harta site-ului și nu vedeți pentru ce cuvinte apăreți. Confirmarea
se face o dată și cere acces la DNS-ul domeniului.

Harta de trimis acolo: `https://officeplus.md/sitemap.xml`

---

## 6. Când trageți concluzii

| Ce măsurați | Nu trageți concluzii înainte de |
|---|---|
| O campanie de reclamă plătită | **2 săptămâni** |
| O campanie de comandă repetată | **14 zile** de la trimitere |
| Un articol nou | **6–8 săptămâni** |
| O rețea socială | **1 lună** (12–15 postări) |
| Contactele cu organizații | **2 luni** — ciclul lor de decizie e lung |
| Strategia SEO în ansamblu | **4 luni** |

Google nu reacționează în zile. Un articol publicat astăzi este citit în
câteva zile, evaluat în săptămâni și urcat în luni. Cine oprește la trei
săptămâni pentru că „nu merge”, oprește exact înainte de rezultat — și
repetă asta la nesfârșit.

---

## 7. Când opriți ceva

Opriți când **toate trei** sunt adevărate:

1. au trecut termenele de la punctul 6;
2. ROI sub 0 % două luni la rând;
3. ați încercat o modificare (alt public, altă grupă, alt text) și nu s-a
   schimbat nimic.

Opriți **imediat**, fără să așteptați, dacă:

- cheltuiala depășește planul și nimeni nu a decis asta;
- reclama duce către o pagină care nu funcționează;
- se vinde marfă pe care nu o avem și nu o putem aduce.

---

## 8. Raportul lunar pentru conducere

### 8.1. Formatul

O pagină, șapte rânduri. Mai mult nu se citește.

```
Luna: august 2026

1. Comenzi: 340 (iulie: 298) ..................... +14 %
2. Valoarea medie a comenzii: 2 140 lei (iulie: 1 980)  +8 %
3. Clienți care au revenit: 71 din 340 ........... 21 %
4. Vizitatori din căutare: 4 120 (iulie: 3 400) ... +21 %
5. Cheltuit pe reclamă: 8 000 lei
6. Venit atribuibil reclamei: 21 500 lei .......... ROI 169 %
7. Ce schimbăm luna viitoare: creștem bugetul pe „Rechizite școlare”,
   oprim campania pe „Componente PC” (ROI −12 % a doua lună).
```

Cifrele de mai sus sunt un exemplu de **format**, nu date reale.

### 8.2. De ce ultimul rând este cel mai important

Primele șase spun ce s-a întâmplat. Al șaptelea este singurul care schimbă
ceva. Un raport fără decizie este o cheltuială de timp.

### 8.3. Raportul zilnic nu îl înlocuiește

Raportul automat din pâlnie („Автономная сводка”) arată **ce s-a
întâmplat**. Rezumatul lunar spune **ce faceți în consecință**. Sunt lucruri
diferite.

---

**Următorul capitol:** [Cartea V — Când ceva nu merge](GHID_5_PROBLEME.md)
