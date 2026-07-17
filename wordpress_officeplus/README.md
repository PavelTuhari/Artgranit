# WordPress officeplus.md — copie locală de lucru

> **Regula de lucru (17.07.2026):** toate modificările WordPress se fac
> ÎNTÂI AICI, local, apoi se publică pe serverul remote. Nu se editează
> direct pe server (except hotfix de urgență, urmat imediat de `wp_pull`).

## Structura
- `public_html/` — copia completă a instalării live
  (`/home/admin/web/officeplus.md/public_html` de pe 89.168.115.20;
  vhost Hestia, apache, user `admin`).
- `db/officeplus_wp.sql.gz` — dump-ul bazei `wordpress` (wp db export).
- Doar acest README + scripturile de sincronizare stau în git;
  arborele WP și dump-ul sunt în .gitignore (120MB, date live).

## Sincronizare
```bash
scripts/wp_pull.sh              # aduce fișierele + dump-ul DB de pe server
scripts/wp_push.sh              # publică FIȘIERELE locale pe server (dry-run implicit)
scripts/wp_push.sh --go         # publică efectiv
```

**Fișiere** (teme, plugin-uri, uploads) — se publică cu `wp_push.sh`.

**Conținut (pagini, meniuri, setări)** — trăiește în DB; NU se împinge
dump-ul peste serverul live (ar șterge comenzi/If comentarii create între
timp). Conținutul se publică punctual prin wp-cli, exemplu:
```bash
ssh -i /Users/pt/Projects.AI/BIRO26/biro26_rsa ubuntu@89.168.115.20 \
  'sudo -u www-data wp --path=/home/admin/web/officeplus.md/public_html \
   post update 6 /tmp/pagina.html'
```
Conținutul canonic al primei pagini (iframe magazin + scriptul de limbi):
`static/biro26/wp_page6_shop_canonical.html`.

## Rulare locală (opțional)
Instalarea poate fi pornită local cu `wp server` sau MAMP/LocalWP:
importați `db/officeplus_wp.sql.gz` într-un MySQL local, ajustați
`wp-config.php` (DB_HOST/USER/PASSWORD) și `wp search-replace
https://officeplus.md http://localhost:8080` pe copia locală a bazei.
