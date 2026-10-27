# officeplus.una.md переведён на nufarul — витрина и бэк-офис работают после демо-пароля

*27.10.2026 · владелец: «officeplus.una.md перевести на nufarul, и соответственно чтобы через него
после ввода демо-пароля всё работало по адресу officeplus.una.md — и фронт, и бэк, как будто это
по-прежнему заблокированный officeplus.md»*

## Как было и как стало

```
                         ┌── cookie demo нет ──────────────► страница пароля (как раньше)
officeplus.una.md ─► .148 nginx ┤
  (прямой заход)               └── cookie demo есть ─► https://nufarul.eminescu.md   ← НОВОЕ
                                                        (Host nufarul, пауза не действует)

officeplus.md ─► облако 92.5.130.1 ─► .148 (IP облака) ─► 192.168.0.250:8001   ← без изменений
                                                          (SITE_PAUSE=1 → 503)
```

- **Прямые заходы на officeplus.una.md после пароля** идут на nufarul.eminescu.md. Flask там
  видит имя `nufarul.eminescu.md`, которого нет в `BIRO26_SHOP_HOSTS`, поэтому пауза
  (`SITE_PAUSE`) не срабатывает: магазин, корзина, кабинет, вход и бэк-офис работают.
  База та же — общая Oracle OfficePlus.
- **Трафик officeplus.md** приходит на .148 с IP облака (`geo $op_cloud`) и по-прежнему уходит
  на офисный сервер `.250` (`location @opoffice`) — officeplus.md остаётся на паузе.
- Адреса витрины повторяют карту Apache на `.250`: `/` → главная, `/catalog`, `/cos`, `/cont`,
  `/branduri`, `/favorite`, `/compara`, `/cerere-credit`, `/produs/<код>`, информационные
  страницы (`/livrare`, `/contacte`, `/credite` и др.), плюс `/back-office/` → бэк-офис.
- В ответах nufarul адрес `https://nufarul.eminescu.md` заменяется на
  `https://officeplus.una.md` (`proxy_redirect`, `sub_filter`, `proxy_cookie_domain`) —
  пользователь всё время остаётся на officeplus.una.md.
- Каждый ответ помечен `X-Robots-Tag: noindex, nofollow` (демо-домен не индексируется) и
  `X-Shop-Origin: nufarul` (видно, откуда пришёл ответ).

## Файлы

| Где | Что |
|---|---|
| `root@192.168.0.148:/etc/nginx/conf.d/officeplus.una.md.conf` | изменён: `location /` и `/static/` делят трафик облако / прямой, `@opoffice`, карта адресов, `map $op_nuf_conn_upgrade` |
| `root@192.168.0.148:/etc/nginx/officeplus-nufarul.inc` | новый: заголовки и `proxy_pass https://92.5.3.187` (SNI nufarul.eminescu.md) |
| `root@192.168.0.148:/etc/nginx/officeplus.una.md.conf.bak-2026-10-27` | копия до изменения |
| `deploy/officeplus/148/` (git) | копии обоих файлов; значение cookie заслонки заменено на `<DEMO_COOKIE>` |

Код приложения не менялся. nufarul (nginx, служба, `.env`) не трогался.

## Проверка (27.10.2026)

| Адрес | Без пароля | С паролем |
|---|---|---|
| https://officeplus.una.md/ | страница пароля | 200, «OfficePlus – Totul de ce ai nevoie…», `X-Shop-Origin: nufarul` |
| https://officeplus.una.md/catalog, `/cos`, `/cont`, `/branduri`, `/produs/162325`, `/livrare`, `/credite` | страница пароля | 200, настоящие заголовки витрины |
| https://officeplus.una.md/login | страница пароля | 200, вход портала |
| https://officeplus.una.md/UNA.md/orasldev/biro26-backoffice | страница пароля | 302 → `https://officeplus.una.md/login?next=…` |
| https://officeplus.una.md/api/biro26/shop/products?limit=2 | — | 200, JSON с товарами |
| https://officeplus.md/, `/cos` | 503 (пауза, `x-shop-origin: spare`) | — |
| https://nufarul.eminescu.md/login | 200 | — |

```bash
curl -s -b opdemo=<значение> -D- -o /dev/null https://officeplus.una.md/ | grep -i x-shop-origin   # nufarul
curl -s -o /dev/null -w '%{http_code}\n' https://officeplus.md/                                       # 503
```

## Чего нет на nufarul

WordPress-админки (`/wp-admin/`, `/wp-login.php`) на nufarul нет — через officeplus.una.md они
отвечают 404. На officeplus.md они тоже закрыты паузой с 22.10.2026. Информационные страницы
WordPress витрина читает через REST и показывает (`/livrare` и др. — 200).

## Откат

```bash
cp -p /etc/nginx/officeplus.una.md.conf.bak-2026-10-27 /etc/nginx/conf.d/officeplus.una.md.conf
nginx -t && systemctl reload nginx
```
