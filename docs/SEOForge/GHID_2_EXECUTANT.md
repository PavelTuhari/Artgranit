# Cartea II — Manualul executantului

> Ce faceți, în ce ordine, pe ce apăsați. Citiți-o cu programul deschis
> și faceți fiecare pas pe rând.

**Atenție utilă:** interfața back-office-ului este **în limba rusă**.
În fiecare tabel de mai jos găsiți, între ghilimele, exact textul care
scrie pe ecran, ca să nu căutați.

---

## 1. Ce vă trebuie ca să începeți

| | |
|---|---|
| **Acces** | cont în back-office (`/UNA.md/orasldev`). Fără el nu se deschide niciun ecran. |
| **Timp** | 5 minute pe zi, 30 de minute pe săptămână, 2 ore pe lună |
| **Cunoștințe** | niciuna tehnică. Nu scrieți cod, nu atingeți serverul |

---

## 2. Harta ecranelor

| Ecran | Adresa | Ce scrie pe meniu | Ce face |
|---|---|---|---|
| Pâlnia | `/UNA.md/orasldev/funnel` | — | comenzi pe zile, ce se vinde, ce s-a blocat |
| Rețele | `/UNA.md/orasldev/social` | — | postarea zilei, rețelele conectate |
| SEOForge | `/UNA.md/orasldev/seoforge` | 8 secțiuni (mai jos) | buget, cheltuieli, ROI, strategie |

Secțiunile din SEOForge, în ordinea din meniul din stânga:

| Ce scrie pe ecran | Înseamnă | Când intrați |
|---|---|---|
| «Портфель» | Portofoliu — toate site-urile, plan și rest de buget | ca privire de ansamblu |
| «Сайты» | Site-uri — profilul fiecărui site: domeniu, limbi, nișă | rar, la configurare |
| «Кампании» | Campanii — codul campaniei (= `utm_campaign`), termene, buget | la pornirea unei campanii |
| «Бюджет» | Buget — plan pe perioade, articole și canale | lunar |
| «Факты» | Fapte — cheltuielile reale și metricile site-ului | lunar, obligatoriu |
| «ROI» | ROI — cât a costat și cât a adus fiecare canal | lunar |
| «Стратегия» | Strategie — documentele de lucru, cu versiuni | la revizuiri |
| «Справочники» | Dicționare — canale, articole de cheltuială, cursuri valutare | la configurare |

---

## 3. Rutina zilnică — 5 minute

**Pasul 1.** Deschideți pâlnia: `/UNA.md/orasldev/funnel`

**Pasul 2.** Priviți „Воронка за 7 дней” (*Pâlnia pe 7 zile*). Este un
grafic cu comenzile pe zile. Vă interesează o singură întrebare: **ziua
de ieri arată ca zilele dinainte?** O cădere bruscă înseamnă fie
sărbătoare, fie ceva stricat pe site.

**Pasul 3.** Coborâți la lista comenzilor blocate. Sunt comenzile intrate,
dar nelivrate de mult timp. Fiecare rând este un client care așteaptă și
un ban care nu a intrat. Dacă apare ceva acolo — sunați vânzările, nu
rezolvați dumneavoastră.

**Pasul 4.** (opțional, 1 minut) Deschideți `/UNA.md/orasldev/social` și
priviți blocul „Что уйдёт сегодня” (*Ce pleacă azi*) — textul postării de
astăzi. Dacă citiți ceva ciudat, opriți publicarea pentru azi debifând
„публиковать ежедневно” (*publică zilnic*) și anunțați.

> **Nu faceți zilnic:** nu regenerați articolele, nu schimbați bugete,
> nu postați manual „ca să fie mai mult”. Zilnic doar priviți.

---

## 4. Rutina săptămânală — 30 de minute

**1. Ce s-a vândut.** În pâlnie, tabelele „Топ групп за 30 дней”
(*Top grupe pe 30 de zile*) și „Топ товаров за 30 дней” (*Top produse*).
Notați-vă **primele trei grupe**. Acestea sunt grupele pe care merită
conținut și, mai târziu, buget de reclamă. Nu ghiciți ce se vinde — se
vede aici.

**2. Comenzile blocate.** Aceeași listă ca zilnic, dar acum o închideți:
fiecare rând, cu un răspuns de la vânzări.

**3. Rețelele.** Pe `/UNA.md/orasldev/social`, în blocul „Площадки”
(*Platforme*), verificați că rețelele pornite au bifa verde „настроено”
(*configurat*). O rețea care a căzut pe gri înseamnă cheie expirată — cel
mai des Facebook, vedeți [Cartea V](GHID_5_PROBLEME.md).

**4. O privire în Google Analytics** (dacă aveți acces): crește numărul
de vizitatori din căutare față de săptămâna trecută? Nu trageți concluzii
dintr-o singură săptămână — doar urmăriți tendința.

---

## 5. Rutina lunară — 2 ore

Se face în primele zile ale lunii, pentru luna încheiată.

### 5.1. Introduceți cheltuielile reale (30 min)

Fără acest pas, ecranul ROI arată gol și nimeni nu știe dacă banii au
făcut ceva.

1. `/UNA.md/orasldev/seoforge` → «Факты»
2. Pentru fiecare cheltuială: butonul **«Добавить расход»** (*Adaugă
   cheltuială*) — data, canalul, campania, suma, moneda.
3. Dacă aveți export din cabinetul de reclamă (fișier CSV): butonul
   **«Предпросмотр»** (*Previzualizare*) arată ce se va încărca, și abia
   apoi **«Загрузить»** (*Încarcă*). **Priviți întotdeauna previzualizarea**
   — importul dublat strică toate cifrele lunii.
   Formatul fișierelor: [Formatul importului CSV](CSV_FORMAT.md).

### 5.2. Citiți ROI (20 min)

«ROI» → alegeți perioada → **«Показать»** (*Arată*).

Tabelul arată pe fiecare canal: cheltuit, clicuri, conversii, venit, ROI,
CPC, CPA. Cum se citesc aceste cifre și când opriți un canal — în
[Cartea IV](GHID_4_MASURARE.md).

### 5.3. Planificați luna următoare (20 min)

«Бюджет» → completați planul pe perioadă, articol și canal →
**«Записать план»** (*Înscrie planul*).

Planul nu este o formalitate: fără el, ecranul nu are cu ce compara
cheltuiala reală și nu vedeți depășirile.

### 5.4. Regenerați articolele de catalog (30 min)

Catalogul se schimbă — poziții noi, prețuri noi, mărci noi. Articolele
trebuie să spună adevărul de azi, nu de acum trei luni.

```bash
# 1. Se generează textele din baza ERP
python modules/seoforge/scripts/wp_category_posts.py

# 2. Se încarcă în WordPress (actualizează, nu dublează)
sudo -u www-data wp --path=/var/www/officeplus \
  eval-file /tmp/wp_create_posts.php
```

Răspunsul corect arată așa: `создано 0, обновлено 526, сохранено ручных 0,
ошибок 0` — *create 0, actualizate 526, păstrate manual 0, erori 0*.

**„Păstrate manual”** înseamnă articole pe care cineva le-a editat de mână
în WordPress: sistemul **nu le atinge**, ca să nu șteargă munca omului.
Dacă vedeți un număr acolo, e în regulă — cineva a scris ceva mai bun.

Ce fac exact aceste comenzi și de ce în această ordine:
[Articole de catalog în WordPress](WP_CATEGORY_POSTS.md).

---

## 6. Pas cu pas: pornirea autopostării

Se face **o singură dată**, apoi merge singură.

1. Deschideți `/UNA.md/orasldev/social`
2. În „Площадки” vedeți ce rețele sunt gata. **Telegram este deja
   configurat.** Restul apar gri până se introduc cheile — cheile se obțin
   după instrucțiunea [Promovare în rețele fără buget](SOCIAL_AUTOMATION.md).
3. Alegeți ora: câmpul «в … :00». Recomandat **10:00** — dimineața,
   când oamenii sunt pe telefon.
4. Alegeți limba: «язык» → RO sau RU.
5. **Înainte de a porni automatul**, apăsați **«Опубликовать сейчас»**
   (*Publică acum*) și uitați-vă la rezultat. Fiecare rețea răspunde
   separat: ✅ sau ❌ cu motivul.
6. Dacă publicarea de probă a mers — bifați «публиковать ежедневно»
   (*publică zilnic*) și apăsați **«Сохранить»** (*Salvează*).

Ce se publică: lunea — selecția „se cumpără acum” din comenzi reale, în
restul zilelor — câte o secțiune din catalog, prin rotație, ca textul să
nu se repete.

---

## 7. Pas cu pas: raportul automat către conducere

Pâlnia poate trimite singură un rezumat zilnic.

1. `/UNA.md/orasldev/funnel` → blocul „Автономная сводка”
   (*Raportul autonom*)
2. Completați destinatarii și ora. **Ora implicită este 22:00** și nu e
   întâmplătoare: serviciul de poștă al serverului lucrează doar între
   22:00 și 02:00.
3. **«Отправить сейчас»** (*Trimite acum*) — verificați că ajunge.
4. **«Сохранить»** (*Salvează*).

> Poșta electronică (SMTP) **nu este configurată** în acest moment.
> Telegram și WhatsApp funcționează. Dacă vreți e-mail, este o cerere
> separată către administrator.

---

## 8. Ce nu faceți niciodată

| Nu faceți | De ce |
|---|---|
| Nu postați de mai multe ori pe zi în aceeași rețea | rețelele scad acoperirea celor care postează des; efectul e invers |
| Nu scrieți în postări reduceri sau promoții care nu există în bază | o vizită câștigată, un client pierdut definitiv, și risc de penalizare Google |
| Nu editați articolele direct în WordPress fără motiv | e permis și se păstrează, dar acel articol nu se mai actualizează automat cu prețuri noi |
| Nu încărcați de două ori același CSV | dublează cheltuielile și strică ROI-ul lunii |
| Nu trageți concluzii din două săptămâni | vedeți calendarul din [Cartea I, punctul 8](GHID_1_DIRECTOR.md) |
| Nu opriți o campanie fără să vă uitați în ROI | poate tocmai ea aducea comenzile |

---

## 9. Calendarul dumneavoastră, pe scurt

| Când | Ce | Unde | Cât |
|---|---|---|---|
| În fiecare dimineață | privire pe pâlnie + textul zilei | funnel, social | 5 min |
| Luni | top grupe, comenzi blocate, rețele | funnel, social | 30 min |
| Prima zi lucrătoare a lunii | cheltuieli, ROI, plan, regenerare articole | seoforge + comenzi | 2 h |
| Cu 4 săptămâni înainte de sezon | conținut de sezon | [Cartea III](GHID_3_CONTINUT.md) | 1 zi |

---

**Următorul capitol:** [Cartea III — Conținutul](GHID_3_CONTINUT.md)
