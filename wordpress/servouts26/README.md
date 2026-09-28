# WordPress ServOuts26 — site-обвязка (локальная установка)

Сайт-обвязка модуля **ServOuts26** (CRM/аутсорсинг бухгалтерии) по образцу
`wordpress_officeplus/` (officeplus.md ↔ biro26). Главная страница WP
встраивает фронт-офис (магазин услуг) Flask через iframe.

## Структура
- `public_html/` — свежая установка WordPress (ro_RO), тема по умолчанию.
- База: MariaDB **`servouts26_wp_local`** (user `pt`, socket `/tmp/mysql.sock`).
- Только README в git; дерево WP — в .gitignore (как у officeplus).

## Порты локального контура (группа 6000, ср. officeplus 6001/6002)

| Сервис | Порт | Ссылка |
|---|---|---|
| Flask (магазин/админка Artgranit) | 3003 | http://localhost:3003/UNA.md/orasldev/servouts26-shop |
| WordPress (сайт, магазин в iframe) | 6003 | http://localhost:6003/ |

Запуск:
```bash
venv/bin/python app.py                                   # Flask, порт 3003
php -d memory_limit=512M /opt/homebrew/bin/wp \
  --path=wordpress/servouts26/public_html \
  server --host=127.0.0.1 --port=6003                    # WordPress
```
Остановить: `lsof -ti :6003 | xargs kill`

## Страницы
- **Главная** (`/`, page 4 «Magazin servicii») — full-bleed iframe магазина.
  Канонический контент: `static/servouts26/wp_front_shop_canonical.html`
  (локально `src` iframe = `http://localhost:3003/...`; на проде, когда WP и
  Flask будут за одним nginx-доменом, заменить на относительный
  `/UNA.md/orasldev/servouts26-shop`).
- `despre-noi` (page 6), `contacte` (page 7) — обычные WP-страницы.

## Доступ в wp-admin (локально)
`http://localhost:6003/wp-admin/` · user `admin` · пароль `ServOuts26wp#`
(локальная установка; при выносе на прод — сменить).

## Production (развёрнуто 18.07.2026)

**https://nufarul.eminescu.md/servouts/** (внимание: голый `eminescu.md`
указывает на другой сервер — прод живёт на поддомене nufarul).

| Компонент | Значение |
|---|---|
| Файлы | `/var/www/servouts` (nginx root-паттерн через symlink `/var/www/wproot/servouts`) |
| БД | MariaDB `wordpress_servouts`, user `wp_servouts` (innodb_buffer_pool=64M — на сервере 1GB RAM) |
| PHP | php8.3-fpm, sock `/run/php/php8.3-fpm.sock` |
| Nginx | location `/servouts/` в `/etc/nginx/sites-enabled/nufarul.eminescu.md` (бэкап конфига в `/home/ubuntu/nginx_nufarul.bak.*`) |
| Главная (page 4) | iframe `/UNA.md/orasldev/servouts26-shop` (относительный — тот же домен), канон: `static/servouts26/wp_front_shop_prod.html` |
| Backoffice (page 9) | iframe `/UNA.md/orasldev/servouts26` (Flask сам требует /login), канон: `static/servouts26/wp_backoffice_prod.html` |
| wp-cli на сервере | `sudo -u www-data wp --path=/var/www/servouts …` |

Публикация контента — точечно через wp-cli (`wp post update …`); дамп БД
целиком на живой сервер не заливать (по правилу officeplus).
