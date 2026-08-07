# Biro26 на nufarul: два варианта магазина + локальная копия WordPress

Дата: 2026-08-06. Сервер: nufarul (92.5.3.187, `nufarul.eminescu.md`).
Источник восстановления: архив `/Users/pt/Projects.AI/BIRO26/Backups/WP/260805`
(Hestia-бэкап `admin.2026-08-05_05-11-17.tar` с officeplus 89.168.115.20 +
дамп `officeplus_wp_localhost.sql` из phpMyAdmin).

## 1. Два варианта магазина (терминология владельца)

| Вариант | URL на nufarul | Что это |
|---|---|---|
| **shop** | `/UNA.md/orasldev/biro26-wp/` | Стандартный шаблон WordPress (тема twentytwentyfour, копия **shop2.officeplus.md**), магазин внутри — **iframe** на `/UNA.md/orasldev/biro26-shop` (старый UI `shop.html`) |
| **shop1** | `/UNA.md/orasldev/biro26-1shop` | **Цельный сайт** магазина — актуальный Figma-дизайн officeplus.md (site_home/catalog/produs/cos/cont); настройки, страницы и картинки берёт из локальной WP-админки |

Обе плитки добавлены на распределительную страницу `/UNA.md/orasldev/biro26`
(шаблон `templates/biro26_admin.html`).

- wp-admin (общий для обоих вариантов — страницы, реквизиты, картинки):
  `/UNA.md/orasldev/biro26-wp/wp-admin/`, пользователь `officeplus`
  (пароль передан владельцу в чате 2026-08-06; хранится только в WP).

## 2. Маршрут `biro26-1shop` (цельный магазин)

- В `app.py` каждый маршрут `biro26-site/*` получил **алиас-декоратор**
  `/UNA.md/orasldev/biro26-1shop[/...]` (catalog, product, cart, account,
  page, favorites, compare, brands, payment-result) — те же view-функции,
  те же `static/biro26/*`.
- Красивые ссылки (`/catalog`, `/cos`, `/produs/N`, `/credite`…) существуют
  только за nginx officeplus.md. На nufarul их переводит **клиентский шим**
  в `static/biro26/site.js`:
  - `SITE_PREFIX` — определяется по `location.pathname` (`/UNA.md/orasldev/biro26-…`);
  - `siteURL(p)` — маппинг pretty → Flask (`/cos`→`/cart`, `/cont`→`/account`,
    `/produs/N`→`/product/N`, `/favorite`→`/favorites`, `/compara`→`/compare`,
    `/branduri`→`/brands`, прочее→`/page/<slug>`);
  - перехватчик кликов по `<a href="/…">` переписывает href на лету
    (без `preventDefault`, так что `target="_blank"` работает);
  - все прямые `location.href` в шаблонах пропущены через `siteURL()`.

## 3. Копия WordPress (`biro26-wp`)

### Файлы
- `/var/www/officeplus/` — `public_html` из `web/shop2.officeplus.md/domain_data.tar.zst`
  (владелец `www-data`); наш `wp-config.php` сохранён поверх (chmod 640).
- Симлинк `/var/www/wpuna/UNA.md/orasldev/biro26-wp → /var/www/officeplus` —
  чтобы путь на диске совпадал с URI (по образцу ServOuts `/var/www/wproot`).
- Предыдущий вариант (копия ОСНОВНОГО WP officeplus.md) сохранён как откат:
  файлы `/var/www/officeplus.main/`, БД `/home/ubuntu/officeplus_wp_main_backup.sql.gz`.

### База данных
- MariaDB `officeplus_wp` (utf8mb4/unicode_520_ci), пользователь
  `officeplus_wp@localhost`; пароль сгенерирован, живёт только в `wp-config.php`.
- Импортирована секция `wordpress_shop2` из дампа. Дамп — **мульти-БД**
  (`CREATE DATABASE wordpress / wordpress_shop1 / wordpress_shop2` + `USE`),
  поэтому при импорте секцию нужно вырезать и удалить `CREATE DATABASE`/`USE`,
  иначе данные молча уходят в другую БД. Импорт строго с
  `--default-character-set=utf8mb4` (иначе эмодзи в контенте → ORA-подобная
  ошибка `Incorrect string value`).
- Служебные страницы витрины shop1 (`site-rechizite`, `site-plati`,
  `site-branduri`, `site-about[-ru/-en]`, `site-contact`, `credite`,
  `credite-ru`) в shop2-БД отсутствовали — перенесены из бэкапа основной БД
  (`wp_posts`/`wp_postmeta` с офсетом ID +10000, `post_author=1`).

### Замены URL в БД (wp search-replace, --all-tables)
1. `https://shop2.officeplus.md` → `https://nufarul.eminescu.md/UNA.md/orasldev/biro26-wp`
2. `src="/biro26-shop"` → `src="/UNA.md/orasldev/biro26-shop"` (iframe магазина)
3. `href="/biro26-shop"` → аналогично
4. `"/biro26-backoffice"` → `"/UNA.md/orasldev/biro26-backoffice"`

Корневые `/biro26-*` пути работали только через nginx-rewrite на officeplus;
на nufarul корень уходит во Flask → 404 внутри iframe («Not Found…»).

### nginx (`/etc/nginx/sites-enabled/nufarul.eminescu.md`)
```nginx
location = /UNA.md/orasldev/biro26-wp { return 301 /UNA.md/orasldev/biro26-wp/; }
location ^~ /UNA.md/orasldev/biro26-wp/ {
    root /var/www/wpuna;
    index index.php;
    try_files $uri $uri/ /UNA.md/orasldev/biro26-wp/index.php?$args;
    client_max_body_size 16M;
    location ~ \.php$ {
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:/run/php/php8.3-fpm.sock;
    }
}
```
Блок стоит ДО `location /` (proxy на Flask :8000). Бэкап конфига перед
правкой: `/tmp/nufarul.nginx.bak` (и обычные копии Hestia нет — это не Hestia-сервер).

## 4. Переменные `.env` на nufarul (инстансные отличия)

| Ключ | Значение на nufarul | Зачем |
|---|---|---|
| `BIRO26_SHOP_WP_API` | `https://nufarul.eminescu.md/UNA.md/orasldev/biro26-wp/wp-json` | витрина shop1 читает WP-контент из ЛОКАЛЬНОЙ копии (не зависит от officeplus.md) |
| `BIRO26_SHOP_TOPBAR_BG` / `_FG` | `#b1c5a4` / `#1e293b` | верхняя панель старого магазина — как на shop2 |
| `BIRO26_SHOP_NAV` | `Catalog\|?;Despre noi\|info:despre-noi;Contacte\|info:contacte;Livrare\|info:livrare;Retur produse\|info:retur-produse` | пункты меню; формат `info:<slug>` ОБЯЗАТЕЛЕН — прямые `?info=` URL рендерятся с `target="_top"` и выбрасывают из WP-обёртки (пропадает нижнее меню) |
| `BIRO26_CREDIT_HIDE_ORGS` | (не задан — все организации видны) | на officeplus скрывает «MAIB Credit de consum» |

## 5. Безопасность — компрометация живых WP

В БД из архива найдены **бэкдор-администраторы**:
основная БД — 7 × `wp2_*@wp2shell.invalid`; shop2 — **45** (те же `wp2_*` +
`bob_*@bobresearchlabs.com`). В локальной копии все удалены
(`wp user delete … --reassign=1`), остался только `officeplus`;
PHP-файлов в `uploads/` нет. **Живые officeplus.md / shop1 / shop2 заражены
теми же аккаунтами** — после восстановления доступа обязательна чистка
(или перезаливка из этой вычищенной копии). Возможная причина внезапного
SSH-бана officeplus — активность этих бэкдоров.

## 5a. Liber Card: настройки через админку (инструкция для клиента)

Действующая конфигурация (2026-08-06, по требованию владельца):
**только «Liber Card / 6 rate»** (наценка 8% + 10% организации), 3/4/5 rate
выключены, **максимум 50 000 лей** (лимит карты MAIB Liber).

Всё меняется без программиста в кредит-админке
`/UNA.md/orasldev/biro26-credite` → организация **Liber Card MAIB** (есть на
обоих серверах; БД общая — изменение действует сразу на officeplus.md и nufarul):

1. **Включить/выключить срок** — в списке пакетов организации поставить/снять
   галочку *Activ* у нужного «Liber Card / N rate» и сохранить.
   Выключенные пакеты не удаляются — их можно вернуть в любой момент.
2. **Изменить лимиты** — поля *Suma min / Suma max* пакета.
   ВАЖНО: лимиты проверяются по ФИНАНСИРУЕМОЙ сумме (цена × наценка),
   т.е. «до 50 000 финансируемых» ≈ до ~46 300 лей стандартной цены при 8%+10%.
3. **Изменить наценку** — поле *Comision / Markup %* пакета (+ поле
   *Transport markup %* на самой организации; действующая цена в кредит =
   сумма двух). После изменения наценки проверить, что она совпадает во всех
   витринах (см. CLAUDE.md, правило 7).
4. Изменения подхватываются автоматически в течение 5 минут (кэш офферов);
   мгновенно — рестарт `sudo systemctl restart artgranit`.
5. Если организация пропала из корзины совсем — у неё не осталось ни одного
   активного пакета (см. инцидент 2026-08-06) либо она скрыта инстансно
   через `BIRO26_CREDIT_HIDE_ORGS` в `.env`.

## 6. Чек-лист проверки после любых работ

```bash
curl -I  https://nufarul.eminescu.md/login                                  # 200
curl -sI https://nufarul.eminescu.md/UNA.md/orasldev/biro26-wp/ | head -1   # 200
curl -sI https://nufarul.eminescu.md/UNA.md/orasldev/biro26-1shop | head -1 # 200
curl -s  https://nufarul.eminescu.md/api/biro26/site/info/site-rechizite | head -c 80
```
Эталон для «shop»: страница и `?info=…` должны побайтово совпадать с
`https://shop2.officeplus.md/biro26-shop` (кроме нового `target="_top"`… —
после фикса формата NAV дифф = 0 строк).

## 7. Откат на копию основного WP (если понадобится)

```bash
sudo mv /var/www/officeplus /var/www/officeplus.shop2
sudo mv /var/www/officeplus.main /var/www/officeplus
zcat /home/ubuntu/officeplus_wp_main_backup.sql.gz | sudo mysql --default-character-set=utf8mb4 --database=officeplus_wp
# wp-config.php уже настроен; siteurl в бэкапе — уже nufarul/biro26-wp
```
