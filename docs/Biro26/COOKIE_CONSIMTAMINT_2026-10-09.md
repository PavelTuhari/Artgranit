# Consimțămîntul pentru cookie-uri pe officeplus.md — 09.10.2026

Cererea proprietarului: «conform noii legi a datelor cu caracter personal este nevoie
ca pe site să apară la deschidere fereastra cu acceptarea cookie».

## Ce se întîmpla înainte (verificat pe site-ul viu)

La prima deschidere a paginii, **fără nicio întrebare**:

| Ce | Ce lasă în browser |
|---|---|
| Google Analytics (`gtag.js`) | cookie `_ga`, `_ga_STJ1NQDGY0`, cereri la google-analytics.com |
| JivoChat | 7 chei `jv_*` în localStorage, cereri la jivosite.com |
| Atribuirea reclamelor (serverul nostru) | cookie `op_vid` (ID de vizitator) + `op_attr` (sursa: Facebook, Google…), 90 de zile |
| Google Fonts | IP-ul vizitatorului la fonts.googleapis.com la fiecare pagină |
| Harta Google din pagina principală | iframe maps.google.com cu cookie-urile Google |

## Ce face acum

La prima vizită, jos pe pagină apare fereastra **«🍪 Folosim cookie-uri»** (RO / RU după
limba site-ului) cu trei butoane de aceeași mărime: **Refuz**, **Personalizez**,
**Accept toate**. Pînă la alegere nu pornește nimic din tabelul de mai sus.

| Categorie | Ce pornește | Fără acord |
|---|---|---|
| Strict necesare (mereu) | sesiunea contului, coșul, limba, alegerea însăși | — |
| Funcționale | JivoChat; harta Google | fără chat; în locul hărții o placă «Afișați harta» (click = acord doar pentru hartă) |
| Analitice | Google Analytics (`gtag.js` se descarcă abia acum) | nicio cerere la Google |
| Marketing | `op_vid` / `op_attr` pe server | nu se pun; cele vechi se golesc |

- Alegerea se ține în cookie-ul `op_consent` = `v1.a0.f1.m0.<timp>`, **180 de zile**,
  pe tot domeniul `.officeplus.md`. După 180 de zile — sau dacă se schimbă categoriile
  (`CONSENT_VERSION` → `v2`) — se întreabă din nou.
- În subsol, lîngă «Politica de confidențialitate», apare linkul **«Setări cookie»**:
  alegerea se poate schimba oricînd. La retragerea acordului cookie-urile `_ga*` și
  datele `jv_*` se șterg, iar pagina se reîncarcă fără ele.
- Fontul Inter e acum **găzduit la noi** (`/static/biro26/fonts/inter/`, licență OFL),
  nu la Google Fonts.

## Fișiere

| Fișier | Ce |
|---|---|
| `static/biro26/cookie-consent.js` / `.css` (noi) | toată logica și aspectul bannerului |
| `templates/biro26/_site_cookie_consent.html` (nou) | le leagă în vitrină; `?v=` se schimbă la orice modificare |
| `templates/biro26/site_base.html` | `gtag.js` și Jivo nu se mai încarcă direct (rămîne doar `consent default = denied` și ID-urile); fontul local; 1 linie include |
| `templates/biro26/site_home.html` | harta: `data-opcc-src` în loc de iframe direct |
| `models/biro26_cookie_consent.py` (nou) + 3 linii în `models/biro26_social.py` | `op_vid`/`op_attr` doar cu `m1`, golite fără acord |
| `wordpress_officeplus/mu-plugins/officeplus-cookie-consent.php` (nou) | același banner pe paginile WordPress (pagina 404) |
| `wordpress_officeplus/mu-plugins/officeplus-jivochat.php` | Jivo pe WP doar prin consimțămînt |
| `tests/test_cookie_consent.py` | 9 teste |

## Verificat viu (10.10.2026)

- `https://officeplus.md/` după ștergerea cookie-urilor: bannerul apare; **0 cookie-uri,
  0 cereri** la Google / Jivo; în locul hărții — placa «Afișați harta»; fontul se
  încarcă de la noi.
- «Refuz» → `op_consent=v1.a0.f0.m0…`, nimic nu pornește; «Setări cookie» deschide
  fereastra cu cele 4 categorii.
- «Accept toate» → pornesc GA (`_ga`), JivoChat și harta.
- Server (curl cu `?utm_source=facebook`): fără alegere — niciun `Set-Cookie op_*`;
  refuz pe marketing + `op_vid` vechi → `op_vid=` gol; acord `m1` → `op_vid` nou + `op_attr`.
- Pagina 404 a WordPress: bannerul e prezent, Jivo nu se mai încarcă direct.
- `login` 200 pe nufarul, 92.5.130.1, office .250; 0 Traceback. Fișierele înlocuite pe
  servere aveau md5-ul din `main`; copii `.bak-2026-10-09` alături.

## Politica de confidențialitate — propunere pentru secțiunea 7

Pagina `/politica-de-confidentialitate` vine din WordPress (pagina cu slug-ul
`politica-de-confidentialitate`). Secțiunea 7 de acum spune doar «Puteți gestiona
cookie-urile din setările browserului» — nu mai corespunde. **Textul de mai jos NU
e publicat** — e un document juridic al firmei și se publică după acordul proprietarului.

> **7. Cookie-uri**
>
> Folosim cookie-uri și tehnologii similare (localStorage). Cele strict necesare
> funcționează fără consimțămînt; celelalte — doar dacă le acceptați în fereastra
> afișată la prima vizită. Alegerea se păstrează 180 de zile și o puteți schimba
> oricînd din linkul «Setări cookie» din subsolul site-ului.
>
> | Categorie | Ce folosim | Furnizor | Durata |
> |---|---|---|---|
> | Strict necesare | sesiunea contului și coșul, limba, `op_consent` (alegerea dvs.) | OfficePlus | sesiune / 180 zile |
> | Funcționale | chatul de asistență (`jv_*`), harta din pagina de contacte | JivoChat, Google Maps | conform furnizorului |
> | Analitice | `_ga`, `_ga_*` — statistici agregate de vizitare | Google Analytics | pînă la 2 ani |
> | Marketing | `op_vid`, `op_attr` — sursa vizitei (Facebook, Google, TikTok…) | OfficePlus | 90 de zile |
>
> Retragerea consimțămîntului nu afectează legalitatea prelucrării efectuate înainte de
> retragere. Fontul și celelalte resurse ale site-ului se încarcă de pe serverele noastre.

## Adrese live

- Site: <https://officeplus.md/> (bannerul la prima vizită; «Setări cookie» în subsol)
- Test: <https://nufarul.eminescu.md/UNA.md/orasldev/biro26-site>
- Politica (de actualizat): <https://officeplus.md/politica-de-confidentialitate>
