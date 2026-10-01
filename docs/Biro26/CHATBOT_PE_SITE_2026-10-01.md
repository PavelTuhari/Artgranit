# Asistentul OfficePlus (chatbot) pe vitrină — 01.10.2026

Întrebarea proprietarului: «de ce pe site nu este acest chatbot?» + «Telegram — нужен
токен бота и chat id».

## De ce nu era

Botul era instalat (15.09) ca **pagină separată** — `https://officeplus.md/OfficePlus_Chatbot/` —
dar paginile magazinului (`/`, `/catalog`, `/produs/…`, `/cos`) le randează aplicația
Flask, nu WordPress: un folder pus în `/var/www/officeplus` nu apare în ele.
Nimic nu trimitea spre pagina botului. Iar și acolo nu lucra:

| Problemă | Efect | Rezolvare |
|---|---|---|
| `api/config.php` cu `API_USERNAME_AICI` | căutarea dădea 500 «Autentificarea API a eșuat» | cont Partner API dedicat `chatbot@officeplus.md` (PAPI_PARTNER id 21, client ERP 240551 «Persoana fizica» → prețul cu amănuntul) |
| `TELEGRAM_*_AICI` | ofertele nu ajungeau la manager | botul existent al magazinului **@NordOfficePlus_bot** + chat-ul care primește deja comenzile site-ului (`YBIRO_SETTINGS.NOTIFY_TG_TOKEN/CHAT`); verificat cu `getMe`/`getChat`, fără mesaj |
| `script.js`: `user_price ?? fixed_price` | cumpărătorul vedea prețul de **dealer** (angro): hîrtia A4 71,53 în loc de 103 MDL; PDF-ul ar fi ieșit cu rînduri angro și total retail | `fixed_price ?? user_price` — retail întîi |
| `quantity` din API = doar stocul nostru | «Stoc: 0» și refuz «nu este disponibil» la marfa pe care vitrina o arată «În stoc» (tonere: 1 din 1000) | `modules/partner/rules.py` → `sellable_qty` = stocul nostru + `FURNIZOR_STOC`, aceeași regulă ca insigna vitrinei |

Credențialele stau **doar** în `/var/www/officeplus/OfficePlus_Chatbot/api/config.php`
pe 92.5.130.1 (640, www-data; copia veche `config.php.bak-2026-10-01`). În git e
`api/config.example.php` cu placeholder-e.

## Cum e pus pe vitrină

- `templates/biro26/_site_chatbot.html` (nou) — buton verde 💬 în colțul **stîng**-jos
  (dreptul e ocupat de fițuica `#opGuideBtn` și de JivoChat) + panou cu iframe.
- `templates/biro26/site_base.html` — o singură linie `{% include %}` înainte de `</body>`.
- iframe și nu `style.css`/`script.js` direct: CSS-ul botului are `*{…}` și
  `body{font-family:Arial}` (ar fi schimbat fontul întregului magazin), iar scriptul
  folosește id-uri generice și adrese relative `api/…`, care pe `/catalog` ar fi
  nimerit în Flask.
- iframe-ul se creează abia la primul click; pe telefon panoul e pe tot ecranul și
  bara JivoChat se ascunde cît e deschis.
- Butonul apare doar pe `officeplus.*`; pe nufarul (test) — cu `?chatbot=1`.
- `embed.html` (nou, lîngă `index.html` al proprietarului): fereastra deschisă, fără
  butonul propriu, «×» închide panoul vitrinei. Marcajul e copiat 1:1 din `index.html`
  (test). `?v=20261001` pe `embed.html`, `style.css`, `script.js` — **la orice
  modificare a lor se schimbă data**, altfel vizitatorii rămîn pe versiunea din cache
  (s-a întîmplat la probă: browserul arăta încă prețul angro).

Sursa botului e acum în git: `wordpress_officeplus/public_html/OfficePlus_Chatbot/`
(fără `config.php`, token, `vendor/`). **Arhiva `Downloads/OfficePlus_Chatbot_NotepadPP.zip`
e mai veche** decît ce rulează (fără corecturile din 15.09 și de azi) — nu se urcă peste.

## Verificat viu (01.10.2026)

- butonul pe `https://officeplus.md/`, `/catalog`, `/produs/162325`, `/cos` — da;
  pe `https://nufarul.eminescu.md/UNA.md/orasldev/biro26-site` — nu, cu `?chatbot=1` — da;
- căutare «pix schneider» → fotografii, 27,67 MDL (retail), «Stoc: 1000»; adăugare în coș;
- `validate-order.php` → «Order is valid (not created)», total 2 × 27,67 = 55,34;
  `PAPI_LOG` al contului 21: 0 comenzi reale;
- PDF-ul ofertei generat pe server (23 KB, șters după probă);
- `login` 200 pe nufarul, 92.5.130.1, office .250; 0 Traceback.

**Neverificat**: trimiterea efectivă în Telegram — ar fi pus un mesaj real în chat-ul
managerului. Prima ofertă adevărată o va verifica (sau o probă cu acordul proprietarului).

## Ce a rămas, separat

Căutarea **întregului site** sortează alfabetic: la «pix» primele sînt mouse-urile
«2E Gaming…» (se potrivesc prin descrierea «PixArt»), pe vitrină la fel ca în bot.
Corectura ține de `Biro26Store.get_products_stock` (ordine după relevanță), iar acel
fișier diferă pe fiecare server (vezi `docs/SERVERE_COD_VS_GIT_2026-10-01.md` pe
ramura `prod/office-2026-10-01`) — se face odată cu sincronizarea serverelor cu `main`.

## Fișiere

| Fișier | Ce |
|---|---|
| `templates/biro26/_site_chatbot.html` | nou — butonul + iframe |
| `templates/biro26/site_base.html` | +1 linie include |
| `modules/partner/rules.py` | `sellable_qty` |
| `wordpress_officeplus/public_html/OfficePlus_Chatbot/` | sursa botului + `embed.html`; `script.js` — retail întîi |
| `tests/test_site_chatbot.py` | 8 teste |

## Adrese live

- Magazinul cu asistentul: <https://officeplus.md/catalog> (buton 💬 stînga-jos)
- Asistentul singur: <https://officeplus.md/OfficePlus_Chatbot/embed.html?v=20261001>
- Test pe nufarul: <https://nufarul.eminescu.md/UNA.md/orasldev/biro26-site?chatbot=1>
- Contul API al botului: <https://officeplus.md/UNA.md/orasldev/partner/> (partener `chatbot@officeplus.md`)
