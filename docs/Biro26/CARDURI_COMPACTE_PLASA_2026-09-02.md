# Cardurile uriase au revenit (02.09.2026) — cauza si plasa de siguranta

## Semnalul

Proprietarul, a treia oara: «отвратительно широкие карточки товара! просили
уже не раз более компактно» — `officeplus.md/catalog?grupa=Piese+Imprimanta&page=3`,
doua coloane de ~870px.

## Ce s-a masurat pe pagina vie

| Ce | Valoare |
|---|---|
| `#grid.product-grid` — coloane calculate | `873px 836px 1264px 733px` intr-un container de 924px |
| foi CSS legate in `<head>` | `landing/styles.css`, `site-responsive.css`, `maib-liber.css` — **fara `site-mobile.css`** |
| `templates/biro26/site_base.html` pe birou | rescris 01.09.2026 15:55; `<link>`-ul catre `site-mobile.css` exista doar in `.bak-assetv` |
| blocul `<style>` inline al sablonului, linia 56 | `@media (min-width:1025px){.plp .product-grid{grid-template-columns:repeat(4,1fr)}}` |

## Mecanismul (acelasi ca pe 27.08, al treilea episod)

1. Sablonul comun `site_base.html` e rescris periodic de cealalta echipa; la
   rescriere a disparut `<link>`-ul catre `site-mobile.css`, unde stateau
   regulile cardurilor compacte.
2. Blocul `<style>` inline al lor sta DUPA foile legate si are aceeasi
   specificitate (`.plp .product-grid`) → cistiga prin ordinea sursei.
3. `repeat(4, 1fr)`: `1fr` = `minmax(auto, 1fr)` si nu coboara sub
   min-content. In «Piese Imprimanta» denumirile au cuvinte nerupte de 60 de
   caractere («IR2016/2018/2020/2022/.../imageCLASS») → coloana creste la
   870-1260px, grila iese din container, incap doua carduri pe rind.

## Ce s-a facut

1. **`static/biro26/site-responsive.css`** (fisier al nostru, legat si de
   sablonul lor) a primit o plasa de siguranta cu **specificitate de ID**:
   `#grid.product-grid { grid-template-columns: repeat(auto-fill, minmax(178px, 1fr)) }`
   + `min-width: 0` si `overflow-wrap: anywhere` pe card. Un ID bate orice
   regula doar-cu-clase, oriunde ar sta ea — inclusiv in inline-ul lor.
   Rescrierea urmatoare a sablonului nu mai poate strica cardurile decit
   scotind si aceasta foaie.
2. `<link>`-ul catre `site-mobile.css` a fost pus inapoi in sablonul de pe
   birou, **ultimul in `<head>`**, dupa blocul `<style>` (patch pe ancora,
   cu backup `site_base.html.bak-link-*`), cu comentariu «nu o stergeti».
3. Pe nufarul, unde sablonul e al nostru, a ajuns doar foaia CSS.

4. Denumirea se taie pe desktop la **4 rinduri** (`-webkit-line-clamp`), tot
   in plasa de siguranta: in «Piese Imprimanta» denumirile de 6-7 rinduri
   urcau cardul la 518px. Masurat dupa: card 217×435px (inainte 873×518).
5. **Cache-ul static**: biroul serveste statica cu `max-age=604800` (7 zile),
   iar `?v=` vine din `DEPLOY_COMMIT` (citit o data, la pornire). Un CSS
   inlocuit fara schimbarea versiunii ramine invizibil o saptamina pentru
   vizitatorii care revin — de aceea `DEPLOY_COMMIT` a fost trecut pe
   commit-ul curent si serviciul repornit. De fiecare data cind se schimba
   statica pe birou: **schimbati DEPLOY_COMMIT si reporniti**.

## Cum se verifica

Pe `https://officeplus.md/catalog?grupa=Piese+Imprimanta&page=3`, la 1440px
latime, grila trebuie sa aiba 5 coloane de ~180px; in consola:
`getComputedStyle(document.getElementById('grid')).gridTemplateColumns`.

## De tinut minte

Regulile care conteaza pentru proprietar NU stau in `site_base.html` si NU
depind de un `<link>` din el. Stau in foile noastre, cu specificitate care
nu poate fi batuta din intimplare. (Regula nr. 2 din CLAUDE.md, aplicata la
CSS.)
