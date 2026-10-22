# Pauza site-ului officeplus.md — «lucrări tehnice» (17.10.2026)

Cererea proprietarului: «этот проект по точке входа officeplus.md надо поставить на паузу —
ведутся технические работы, зайдите позже — добавь параметр и активируй его. nufarul
остаётся без изменения».

## Parametrul

| Cheie `YBIRO_SETTINGS` | Valori | Ce face |
|---|---|---|
| `SITE_PAUSE` | `1` = pauză, `0` (sau lipsă) = site normal | oprește magazinul public pe officeplus.* |
| `SITE_PAUSE_MSG_RO` | text, gol = standard | mesajul în română pe pagina de pauză |
| `SITE_PAUSE_MSG_RU` | text, gol = standard | mesajul în rusă |

**Comutatorul** (după logare): <https://officeplus.md/UNA.md/orasldev/sitepause/> — buton
«⏸️ Pune site-ul pe pauză» / «▶️ Redeschide site-ul» și cele două mesaje.

Din SQL, dacă backofficeul nu e la îndemînă:

```sql
BEGIN y_ai_BIRO26.set_setting('SITE_PAUSE', '0'); END;   -- redeschide
BEGIN y_ai_BIRO26.set_setting('SITE_PAUSE', '1'); END;   -- pauză
```

Efectul: imediat pe serverul care a primit clicul, în cel mult 20 de secunde pe celelalte
(valoarea se ține în memorie — o citire din baza costă ~2 s, nu se poate la fiecare cerere).

## Ce se oprește și ce rămîne

Doar pe domeniile magazinului (`Config.BIRO26_SHOP_HOSTS` = `officeplus.md`,
`officeplus.una.md`). **nufarul.eminescu.md lucrează cu aceeași bază, dar are alt domeniu
și modulul nici nu e instalat acolo — rămîne neschimbat.**

| Pe pauză răspunde 503 «lucrări tehnice» | Rămîne deschis |
|---|---|
| vitrina: `/`, `/catalog`, `/produs/…`, `/cos`, `/cont`, paginile de informații | `/login`, `/logout` |
| `/UNA.md/orasldev/biro26-site…`, `biro26-shop`, `biro26-1shop` | backofficeul `/UNA.md/orasldev/…` (de aici se ridică pauza) |
| API-ul magazinului `/api/biro26/shop/…` (comenzi, coș) — JSON `{"maintenance": true}` | API-ul partenerilor `/api/v1/…`, `/api-documentation` (integrările lor nu se rup) |
| | fișierele statice, `robots.txt`, `favicon` |

- Pagina: RO + RU, telefonul și emailul (comenzile se primesc în continuare la telefon),
  `503` + `Retry-After: 3600` + `noindex` — Google înțelege că e temporar și **nu scoate
  paginile din index**.
- **Cei logați văd magazinul ca de obicei** — ca să-l poată verifica înainte de redeschidere.
- Orice eroare în mecanismul pauzei lasă site-ul să meargă (nu-l poate opri din greșeală).
- Rămîn în afara Flask (nu le atinge pauza): pagina 404 a WordPress și asistentul
  `/OfficePlus_Chatbot/` deschis direct (butonul lui de pe vitrină dispare odată cu vitrina).

## Fișiere — modul izolat (nu atinge `app.py`)

| Fișier | Ce |
|---|---|
| `modules/sitepause/__init__.py` | blueprint, conectat de nucleu (`core/module_loader.py`) |
| `modules/sitepause/rules.py` | reguli pure: domeniu, căi deschise / oprite |
| `modules/sitepause/store.py` | `SITE_PAUSE` în YBIRO_SETTINGS, ținut în memorie, reîmprospătat la 20 s |
| `modules/sitepause/routes.py` | hook-ul pe toată aplicația + comutatorul |
| `modules/sitepause/templates/sitepause/pause.html`, `admin.html` | pagina de pauză și comutatorul |
| `tests/test_sitepause.py` | 11 teste (reguli, 503, nufarul neatins, cei logați, izolare) |

Instalat pe office 192.168.0.250 (vitrina publică) și cloud 92.5.130.1 (rezerva). Pe
nufarul **nu** s-a instalat nimic.

## Adrese

- Comutatorul: <https://officeplus.md/UNA.md/orasldev/sitepause/>
- Site-ul (pe pauză): <https://officeplus.md/>
- nufarul (neschimbat): <https://nufarul.eminescu.md/login>

## Добавлено 22.10.2026: WordPress (wp-login.php, /wp-admin/) — тоже на паузе

Владелец: «https://officeplus.md/wp-login.php?redirect_to=…wp-admin%2Fexport.php&reauth=1 —
это тоже на паузу, типа тех работы ведутся».

WordPress officeplus.md работает на облаке 92.5.130.1 вне Flask, поэтому пауза там
стоит в nginx и спрашивает **тот же параметр `SITE_PAUSE`**:

| Кусок | Где |
|---|---|
| `GET /UNA.md/orasldev/sitepause/gate` → 204 (открыто) / 403 (пауза); ошибка → 204 | `modules/sitepause/routes.py` |
| `GET /UNA.md/orasldev/sitepause/page` → та же страница «lucrări tehnice», 503 | `modules/sitepause/routes.py` |
| `auth_request` → `@op_wp_pause` | `ubuntu@92.5.130.1:/etc/nginx/conf.d/officeplus-wp-pause.inc` (копия: `deploy/officeplus/wp-pause.inc`) |
| подключено в `location = /wp-login.php` и `^~ /wp-admin/` | `/etc/nginx/snippets/wp-harden.conf`, `/etc/nginx/conf.d/officeplus-wp-gate.inc` (резервные копии `*.bak-2026-10-22`) |

Проверено вживую: без секретного cookie `wp-login.php`/`/wp-admin/` — по-прежнему 404
(секретный вход не раскрыт); с cookie — 503 со страницей паузы; `/wp-admin/export.php`
раньше открывался без cookie (302 на форму входа), теперь — 503; `admin-ajax.php`,
`/login` бэк-офиса и nufarul не затронуты. Снятие паузы тем же переключателем
<https://officeplus.md/UNA.md/orasldev/sitepause/> открывает и WordPress (≤ 20 с).

Инцидент при установке: первая версия `wp-pause.inc` не прошла `nginx -t`
(`proxy_pass` с путём в именованном location), а проверка в скрипте шла через
`| tail` и не увидела ошибки — reload выполнился, работающий nginx остался на старой
конфигурации (сайт не падал), но файлы на диске были невалидны ~2 минуты. Исправлено
(`rewrite … break` + `proxy_pass` без пути), `nginx -t` OK. Вывод: код возврата
`nginx -t` проверять напрямую, не через конвейер.
