# Cartea IV — Măsurarea: de unde știm că funcționează

> Patru cifre contează cu adevărat. Restul sunt detalii care distrag.

---

## 1. Cele patru cifre

| Cifra | Unde se vede | Ce vă spune |
|---|---|---|
| **Comenzi pe zi** | pâlnia, „Воронка за 7 дней” | dacă magazinul vinde azi |
| **Vizitatori din căutare** | Google Analytics | dacă munca de SEO dă roade |
| **ROI pe canal** | SEOForge → «ROI» | dacă banii de reclamă se întorc |
| **Pagini indexate** | Google Search Console | dacă Google ne vede deloc |

Dacă aveți timp pentru una singură, alegeți **comenzi pe zi**. Restul
explică de ce cresc sau scad.

---

## 2. Pâlnia vânzărilor

`/UNA.md/orasldev/funnel`

| Blocul (text pe ecran) | Înseamnă | Cum se citește |
|---|---|---|
| „Воронка за 7 дней” | Pâlnia pe 7 zile | forma, nu cifra unei zile. Căderi de o zi sunt normale |
| „Топ групп за 30 дней” | Top grupe pe 30 de zile | **aici decideți unde puneți efort** |
| „Топ товаров за 30 дней” | Top produse | ce scoateți în față în postări |
| Lista comenzilor blocate | comenzi intrate, nelivrate | fiecare rând = bani blocați |

**Cea mai utilă întrebare săptămânală:** grupele din top trei sunt aceleași
cu cele pe care le promovăm? Dacă nu — ori promovăm ce nu se vinde, ori
avem o grupă care se vinde singură și ar exploda cu puțin ajutor.

---

## 3. ROI: formula și citirea ei

`/UNA.md/orasldev/seoforge` → «ROI» → perioada → **«Показать»**

Tabelul dă pe fiecare canal: **cheltuit, clicuri, conversii, venit, ROI,
CPC, CPA, CTR**.

```
ROI = (venit − cheltuit) ÷ cheltuit × 100 %
```

| ROI | Înseamnă | Ce faceți |
|---|---|---|
| sub 0 % | ați dat mai mult decât ați primit | opriți sau schimbați, după 2 luni de date |
| 0–50 % | se întorc banii, câștig mic | reglați: alte cuvinte, alte ore, alte grupe |
| peste 100 % | fiecare leu aduce doi | **creșteți bugetul aici**, nu aiurea |

Alte două cifre utile:

- **CPC** — cât plătiți pentru un clic. Crește brusc? concurență nouă.
- **CPA** — cât costă o comandă. Comparați-l cu **profitul** de pe o
  comandă medie, nu cu suma ei. Un CPA de 200 lei la o comandă de 1 500 lei
  cu 15 % marjă înseamnă pierdere.

> **Atenție:** ROI-ul este gol dacă nu s-au introdus cheltuielile reale în
> «Факты». Ecranul nu inventează date. Vedeți
> [Cartea II, punctul 5.1](GHID_2_EXECUTANT.md).

---

## 4. Ce nu măsoară sistemul singur

Sistemul vede comenzile și cheltuielile. **Nu vede** vizitatorii — asta o
face Google.

| Instrumentul | Ce dă | Unde |
|---|---|---|
| **Google Analytics** | câți oameni, de unde, ce pagini | contorul e deja instalat pe officeplus.md |
| **Google Search Console** | ce interogări ne aduc oameni, ce poziții avem, câte pagini a indexat | trebuie confirmat dreptul asupra domeniului |

**Search Console este gratuit și obligatoriu.** Fără el nu știți dacă
Google a citit harta site-ului și nu vedeți pentru ce cuvinte apăreți.
Confirmarea dreptului se face o singură dată și cere acces la DNS-ul
domeniului.

Harta site-ului, de trimis în Search Console: `https://officeplus.md/sitemap.xml`

---

## 5. Când trageți concluzii

| Ce măsurați | Nu trageți concluzii înainte de |
|---|---|
| O campanie de reclamă plătită | **2 săptămâni** |
| Un articol nou | **6–8 săptămâni** |
| O rețea socială | **1 lună** (12–15 postări) |
| Strategia SEO în ansamblu | **4 luni** |

Motivul este simplu: Google nu reacționează în zile. Un articol publicat
astăzi este citit în câteva zile, evaluat în săptămâni și urcat în poziții
în luni. Cine oprește la 3 săptămâni pentru că „nu merge”, oprește exact
înainte de rezultat — și repetă asta la nesfârșit.

---

## 6. Când opriți ceva

Opriți când **toate trei** sunt adevărate:

1. au trecut termenele de la punctul 5;
2. ROI sub 0 % două luni la rând;
3. ați încercat o modificare (alt public, altă grupă, alt text) și nu s-a
   schimbat nimic.

Opriți **imediat**, fără să așteptați, dacă:

- cheltuiala depășește planul și nimeni nu a decis asta;
- reclama duce către o pagină care nu funcționează;
- se vinde marfă pe care nu o avem și nu o putem aduce.

---

## 7. Raportul lunar pentru conducere

O pagină, cinci rânduri. Mai mult nu se citește.

```
Luna: august 2026

1. Comenzi: 340 (iulie: 298) ................ +14 %
2. Vizitatori din căutare: 4 120 (iulie: 3 400)  +21 %
3. Cheltuit pe reclamă: 8 000 lei
4. Venit atribuibil reclamei: 21 500 lei ..... ROI 169 %
5. Ce schimbăm luna viitoare: creștem bugetul pe „Rechizite școlare”,
   oprim campania pe „Componente PC” (ROI −12 % a doua lună).
```

Cifrele de mai sus sunt un exemplu de **format**, nu date reale.

Raportul zilnic automat din pâlnie („Автономная сводка”) nu înlocuiește
acest rezumat lunar: el arată ce s-a întâmplat, rezumatul lunar spune ce
faceți în consecință.

---

**Următorul capitol:** [Cartea V — Când ceva nu merge](GHID_5_PROBLEME.md)
