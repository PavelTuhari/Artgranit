# Codul de pe servere comparat cu git — 01.10.2026

Cerința proprietarului: «проверь статус исходного кода по факту загруженного на
сервера officeplus и nufarul, всё выкатывай на гит, ничего нигде не должно пропасть».

## Metoda

Pe fiecare server s-a calculat hash-ul git (`sha1("blob <n>\0" + conținut)`) al
fiecărui fișier sursă (.py .html .js .css .sql .json .md .php .sh …; fără `venv/`,
`__pycache__`, `*.bak*`, `.env`, wallet, `vendor/`, uploads) și s-a căutat în
**toate** obiectele repo-ului (toate ramurile și tot istoricul). Fișier negăsit =
conținut care exista doar pe server.

## Rezultat

| Server | Ce | Fișiere | Doar pe server | Unde sînt acum |
|---|---|---|---|---|
| nufarul 92.5.3.187 | `/home/ubuntu/artgranit` | 1138 | **0** | — |
| office 192.168.0.250 (vitrina officeplus.md) | `/home/ubuntu/artgranit` | 1049 | 6 cod + 1 setări locale Claude | `prod/office-2026-10-01` |
| office 192.168.0.250 | `/var/www/officeplus` (WP: audit, mu-plugins) | 10 | 3 (+2 stub-uri WP) | `prod/office-2026-10-01` → `wordpress_officeplus/public_html/` |
| cloud 92.5.130.1 (rezerva) | `/home/ubuntu/artgranit` | 926 | 2 | `prod/cloud-2026-10-01` |
| cloud 92.5.130.1 | `/var/www/officeplus` (audit, mu-plugins, OfficePlus_Chatbot) | 21 | 16 | `prod/cloud-2026-10-01` → `wordpress_officeplus/public_html/` |

Cele 8 fișiere de cod de pe office/cloud (`app.py`, `biro26_oracle_store.py`,
`biro26_catalog_fast.py`, `site.js`, `site_product.html`, `site_cart.html`) sînt
aceeași dorădotare aplicată manual peste versiuni mai vechi: stocul
furnizorului (`FURNIZOR_STOC`, în `main` = commit 3b11df56) și pragul de credit
din `CREDIT_MIN_ORDER`. Funcțional ele există deja în `main`; ramurile `prod/*`
păstrează copiile EXACTE — sînt arhive, nu se îmbină.

Chatbot-ul a fost salvat fără `api/config.php` (credențiale), fără
`.officeplus_tokens.json` și `vendor/`; `api/config.example.php` = varianta cu
placeholder-e a proprietarului.

## Local

Toate ramurile locale din worktree-uri sînt pe origin (verificat: nicio ramură
locală cu comituri care nu sînt conținute într-o ramură `origin/*`). Repo-ul
`BIRO26`: 3 comituri ne-împinse pe `main` — împinse. Rămîn în afara git, intenționat:
`wallet_*` (secret), dump-urile `demo 1 abt17 2809206/` (168 MB) și `.rar` (33 MB),
fișierul de date `EFactura_639250048292811215.xml`.

## Capcane întîlnite

- zsh: `"$b:refs/heads/..."` — `:r` e modificator zsh și taie textul; se scrie `"${b}:refs/..."`.
- SSH la .250 cu parolă: `-o PreferredAuthentications=password -o PubkeyAuthentication=no`,
  altfel cheile locale epuizează `MaxAuthTries` și apare «Permission denied».
- VPN93 (L2TP) cade cu «incorrect user shared secret» — rețeaua 192.168.0.* merge
  totuși prin alt tunel (`utun9`, gateway 10.8.0.1).
