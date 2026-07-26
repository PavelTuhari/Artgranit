# OfficePlus — проект ИИ: новый сайт-магазин по Figma + работающий прототип

**Версия:** 1.1  
**Дата:** 2026-07-26  
**Статус:** бриф / ТЗ для разработки с ИИ  
**Языки UI:** RO · RU · EN (как на текущем officeplus.md)

---

## 1. Цель проекта

Собрать **новый полноценный онлайн-магазин OfficePlus**, который:

1. **Визуально и UX** соответствует **Figma** (макеты + прототип) и уже развёрнутому **Figma-лендингу**.
2. **Функционально** работает как e-commerce: каталог, карточка, поиск, корзина, регистрация/ЛК, заказ, оплата (существующие интеграции Biro26).
3. **Не выкидывает** текущий WordPress-сайт: WP остаётся **оболочкой-источником информационных страниц** (контакты, доставка, о нас, политика и т.д.).
4. У нового сайта есть **своя ограниченная админка** (витрина/магазин/контент-блоки лендинга), а **простые текстовые страницы** берутся из **админки WordPress**.

**Критерий готовности:** посетитель на новом сайте видит Figma-витрину, может купить как в текущем магазине Biro26, а инфо-страницы синхронизированы с WP и не дублируются вручную в двух CMS.

---

## 2. Источники правды (Source of Truth)

| Область | Источник | Кто правит | Куда отдаёт |
|---|---|---|---|
| **Визуал лендинга / UI kit** | Figma + прототип | дизайн | новый фронт |
| **Прототип HTML** | `officeplus-standalone` / live **https://officeplus.md/landingfigma1/** | дизайн → dev | эталон вёрстки |
| **Товары, группы, цены, остатки, заказы** | ERP OfficePlus + **Biro26 API** (Artgranit) | ERP / backoffice Biro26 | новый магазин (API) |
| **Инфо-страницы (текст)** | **WordPress** `officeplus.md` | WP Admin | новый сайт (REST / embed / proxy) |
| **Меню инфо-страниц, контакты, политика** | WordPress pages + меню | WP Admin | новый сайт |
| **Ограниченная админка нового сайта** | своя (см. §6) | контент-менеджер витрины | блоки лендинга, баннеры, «товар дня», SEO витрины |
| **Зеркало справочников (backup/отчёты)** | APEX `OP_*` / OPVIEW (опционально) | sync | не primary для витрины |

**Запрещено:** делать WordPress primary store (WooCommerce не источник товаров). Товары — **только** Biro26/ERP.

---

## 3. Что уже есть (as-is)

### 3.1 WordPress — оболочка и инфо-контент

| | |
|---|---|
| URL | https://officeplus.md/ |
| Путь | `/home/admin/web/officeplus.md/public_html` |
| CMS | WordPress (Hestia), тема Twenty Twenty-Four |
| Роль сейчас | Главная с iframe магазина, инфо-страницы RO/RU/EN |
| Примеры страниц | Despre noi, Contacte, Livrare, Termeni, Politica, Metode de plată, Retur… |
| Админка | стандартный WP Admin |

### 3.2 Рабочий магазин Biro26 (логика e-commerce)

| | |
|---|---|
| UI | `/biro26-shop`, `/UNA.md/orasldev/biro26-shop` |
| Backoffice | `/biro26-backoffice` |
| API | `/api/biro26/shop/*`, `/api/biro26/*` |
| Backend | Artgranit Flask + gunicorn `127.0.0.1:8000` |
| Данные | Oracle 11g officeplus (ERP), thick worker |
| Уже умеет | каталог, дерево групп, фильтры, корзина, регистрация, счета, оплата, i18n |

### 3.3 Figma-лендинг (визуальный прототип)

| | |
|---|---|
| Live | **https://officeplus.md/landingfigma1/** |
| Пакет | `officeplus-standalone.zip` → static HTML/CSS/PNG |
| Содержимое | header/topbar, поиск, каталог-кнопка, hero slider, «товар дня», категории, блоки брендов, about, contact, newsletter, footer |
| Ограничение | **статика**: кнопки `#`, нет API, нет корзины, нет WP-страниц |

### 3.4 Инфра (контекст)

- Always Free Ubuntu: `mail.officeplus.md` / `89.168.115.20`
- Nginx: WP + proxy Biro26 + static landing
- Rate limit API: 200/hour; IP через `X-Real-IP` (после фикса 2026-07-24)
- APEX mirror OPVIEW — backup/отчёты, **не** замена shop API

---

## 3.5 Среда разработки: **shop1.officeplus.md** (обязательные требования)

**Решение зафиксировано 2026-07-26** (закрывает вопрос №1 из §16): развитие проекта ведётся
на поддомене **https://shop1.officeplus.md/**.

### 3.5.1 Правила

1. **Прод не трогаем.** Работающий сайт https://officeplus.md/ (WP + Biro26 shop) на весь период
   развития остаётся **нетронутым**: его файлы, БД `wordpress`, каталог `/home/ubuntu/artgranit`,
   сервис `artgranit` (:8000) и nginx-конфиги officeplus.md не изменяются под задачи нового сайта.
2. **shop1 = полная копия корневого сайта.** На shop1 скопировано всё с officeplus.md
   (WP-оболочка + Flask/Biro26), и **весь существующий код используется по максимуму** —
   новый Figma-фронт строится поверх этой копии, а не с нуля.
3. Все Phase 1–5 из §10 разрабатываются и принимаются **на shop1**; на прод переносится
   только принятый результат (Phase 6 cutover).
4. shop1 закрыт от индексации: заголовок `X-Robots-Tag: noindex, nofollow` + `blog_public=0`;
   маркер среды — заголовок `X-Env: shop1-dev`.
5. ⚠️ **Общая ERP.** Oracle 11g officeplus — **один и тот же** для прода и shop1 (товары, цены,
   клиенты — живые). Заказы/счета, созданные на shop1, попадают в реальную ERP — тестовые
   документы помечать/удалять через backoffice. Отдельная тестовая схема ERP не создаётся.

### 3.5.2 Конфигурация shop1 (as-built, 2026-07-26)

| Компонент | Прод officeplus.md | Dev shop1.officeplus.md |
|---|---|---|
| DNS | @ / www → 89.168.115.20 | shop1 → 89.168.115.20 (nic.md) |
| Hestia web domain | officeplus.md | shop1.officeplus.md (user admin) |
| SSL | Let's Encrypt | Let's Encrypt (Hestia) |
| WP файлы | `/home/admin/web/officeplus.md/public_html` | `/home/admin/web/shop1.officeplus.md/public_html` |
| WP БД (MariaDB) | `wordpress` | `wordpress_shop1` (user `wpuser`) |
| WP URL | WP_HOME/WP_SITEURL + search-replace `https://officeplus.md` → | `https://shop1.officeplus.md` |
| Flask/Biro26 код | `/home/ubuntu/artgranit` | `/home/ubuntu/artgranit_shop1` |
| systemd unit | `artgranit` → gunicorn `127.0.0.1:8000` (2 workers) | `artgranit-shop1` → gunicorn `127.0.0.1:8020` (1 worker, MemoryMax=500M) |
| nginx Biro26 proxy | `/home/admin/conf/web/officeplus.md/nginx*.conf_biro26` → :8000 | `/home/admin/conf/web/shop1.officeplus.md/nginx*.conf_biro26` → :8020 |
| Oracle ERP | общий: `officeplus@orange.una.md:4024` | тот же (⚠️ живые данные) |
| pdfme sidecar | общий `127.0.0.1:5488` (`pdfme.service`) | тот же |
| Порт 8010 | — | занят `op-micro`, **не использовать** |

Перезапуск dev-приложения: `sudo systemctl restart artgranit-shop1` (никогда pkill+nohup).

### 3.5.3 Deploy-цикл разработки

```text
локально (Mac, :6001/:6002) → shop1.officeplus.md (приёмка) → officeplus.md (только принятое)
```

- Код Flask/шаблоны деплоятся в `/home/ubuntu/artgranit_shop1` + `restart artgranit-shop1`.
- WP-правки — local-first (wordpress_officeplus/), публикация на shop1; на прод — после приёмки.
- После **любого** деплоя проверять, что прод жив:
  `curl -I https://officeplus.md/` и `curl -I https://officeplus.md/biro26-shop` → 200.

### 3.5.4 Статус реализации (2026-07-26)

**Главная по Figma запущена LIVE на https://shop1.officeplus.md/** (root):

1. Flask-маршрут `/UNA.md/orasldev/biro26-site` (шаблон `templates/biro26/site_home.html`),
   nginx shop1 отдаёт его на `location = /`; **WordPress на shop1 остался только
   админкой/источником контента** (`/wp-admin`, `/wp-json` работают).
2. Вёрстка — строго по прототипу `landingfigma1` (тот же `styles.css`, tokens, блоки:
   topbar, navbar+поиск+Каталог, hero-слайдер 3 слайда, «Товар дня» с таймером,
   H1+7 категорий, 2 ряда товаров, бренды, табы категорий, about/contact, newsletter, футер).
3. Данные живые из Biro26 API: товары (retail1, наличие), «товар дня» (детерминированно
   по дню, меняется ежедневно), категории/табы из `/shop/tree`, бренды из `/shop/brands`.
4. **Корзина общая** с магазином (`localStorage biro26_shop_cart`) — покупка с главной
   попадает в корзину `/biro26-shop`, checkout/оплата/кредит — существующие.
5. Deep-links в магазин: `?q=` (поиск), `?grupa=`, `?categorie=`, `?brand=`, `?sort=`,
   `?cart=1` (открыть корзину) — добавлены в `shop.html`.
6. i18n RO/RU переключатель (общий `biro26_lang`); тексты инфо-страниц — WP
   (`/biro26-shop?info=<slug>`).
7. Следующие фазы (§10): PLP/PDP в стиле Figma, WP REST bridge в chrome нового сайта,
   limited admin (hero/deal/секции), newsletter backend.

**Обновление 2026-07-26 (вечер): Phase 2–5 реализованы на shop1.**

| Фаза | Что сделано | URL |
|---|---|---|
| Phase 2 PLP | Каталог Figma-стиль: дерево групп/категорий с счётчиками, пресеты цен, бренды-чипы, сортировка, нумерованная пагинация, deep-links в URL | `/catalog` (`?q=&grupa=&categorie=&brand=&sort=&page=`) |
| Phase 2 PDP | Фиша товара: фото, цена+«Preț ofertă în rate», варианты, кол-во, описание+комментарии (чтение/добавление), похожие товары, breadcrumbs | `/produs/<cod>` |
| Phase 2/3 | Рассрочка на PDP: плитки 0%/кредит (от 1000 lei) + форма «Solicită în rate» (заявка EasyCredit с уведомлением) | на `/produs/<cod>` |
| Phase 3 | Coș+checkout: правка позиций, транспорт (центр+км, обяз.), услуги, TVA, метод Standard/Credit (плитки, аванс), создание счёта, PDF-ки, оплата MAIB/MIA QR/P2P; для кредита — кнопки «Cerere EasyCredit»+«Liber Card» | `/cos` |
| Phase 3 ЛК | Вход/регистрация (обязательные поля + IDNO юрлиц), профиль, logout; та же сессия что /biro26-shop | `/cont` (`?next=` redirect) |
| Phase 4 | WP REST bridge: инфо-страницы рендерятся сервер-сайд в chrome нового сайта (кэш 5 мин, `?lang=ru`→слаг `-ru`); WP = только админка контента | `/despre-noi /contacte /livrare /retur-produse /termeni-si-conditii /politica-de-confidentialitate` |
| Phase 5 | Limited admin витрины: Oracle-таблицы `YBIRO_SITE_HERO/DEAL/SECTION` (DDL `sql/biro26/12_ybiro_site.sql`), API `/api/biro26/site/*` (config публичный, CRUD под backoffice-auth), UI: hero-слайды RO/RU, «товар дня» override (COD+дедлайн), вкл/выкл секций главной | `/UNA.md/orasldev/biro26-site-admin` |

Архитектура фронта: Jinja-база `site_base.html` (общий chrome по Figma) + `static/biro26/site.js`
(общий JS: корзина, i18n, карточки); страницы `site_home/catalog/product/cart/account/page.html`.
API-расширение: `/api/biro26/shop/products?cod=` (одна карточка для PDP).
E2E проверено: регистрация → счёт №15 (COD 260) → PDF 57 KB. Прод officeplus.md не тронут.

**Обновление 2026-07-26 (ночь): пакет «доводка по ТЗ» реализован на shop1.**

| Что | Реализация |
|---|---|
| Newsletter backend | Oracle `YBIRO_SITE_SUBSCRIBER` (DDL `13_ybiro_site_subscribers.sql`), POST `/api/biro26/site/subscribe` (валидация email, дедуп, повторная подписка реактивирует), список подписчиков в limited admin |
| Избранное | ♡ на карточках работают (❤ toggle, localStorage `biro26_fav`), страница `/favorite` с карточками избранного, кнопка на PDP, ссылка в футере |
| Сравнение | до 4 товаров (`biro26_cmp`), кнопка «⚖ Compară» на PDP, страница `/compara` — таблица: фото, цена, бренд, наличие, код, группа/категория, UM, «Купить»; ссылка в футере |
| Адаптив (ТЗ §5.2) | `static/biro26/site-responsive.css`: fluid ≤1459, tablet ≤1024 (hero стек, 3-кол. гриды, PLP/PDP/coș в столбец), mobile ≤640/375 (2-кол. гриды, компактный topbar, поиск на всю ширину, фильтры каталога свёрнуты за кнопку «Filtre» Amazon-style). Проверено на 375px: без горизонтального скролла |
| SEO (ТЗ §11) | meta description, canonical, hreflang ro/ru, OG title/image, favicon — во всех страницах через `site_base.html` |

Осталось из ТЗ: Phase 6 (soft launch → cutover на прод-домен) — по решению владельца после приёмки shop1.

---

## 4. Целевая архитектура (to-be)

```
                    ┌─────────────────────────────┐
   Посетитель ───►  │  Новый сайт (Figma UI)       │
                    │  SPA / SSR / hybrid          │
                    └──────────┬──────────────────┘
           ┌───────────────────┼───────────────────┐
           ▼                   ▼                   ▼
   ┌───────────────┐  ┌─────────────────┐  ┌──────────────────┐
   │ Biro26 Shop   │  │ WordPress REST  │  │ Admin витрины    │
   │ API (товары,  │  │ /wp-json/       │  │ (ограниченная)   │
   │ корзина, ЛК)  │  │ pages, menus    │  │ баннеры, hero,   │
   └───────┬───────┘  └────────┬────────┘  │ «товар дня»…     │
           │                   │           └────────┬─────────┘
           ▼                   ▼                    │
   Oracle ERP 11g        WP MariaDB                 │
   officeplus            wordpress                  │
                                                    ▼
                                           своя БД/таблица
                                           (не ERP, не WP)
```

### Принцип «две CMS — разные зоны»

| Зона | Система | Примеры |
|---|---|---|
| **Витрина + e-commerce** | Новый фронт + Biro26 API + **limited admin** | home Figma, PLP, PDP, cart, checkout, account |
| **Информационный контент** | **WordPress only** | /contacte, /livrare, /despre-noi, политики, тексты RO/RU/EN |
| **ERP master data** | OfficePlus / Biro26 backoffice | номенклатура, цены, группы, клиенты ERP |

Новый сайт **не копирует** длинные тексты в свою админку — **читает** WP (или iframe/проксирует канонический URL WP, если так проще на первом этапе).

---

## 5. Визуал и Figma: обязательные блоки лендинга

Ориентир: прототип `landingfigma1` + полный Figma file (frames из макета).

### 5.1 Обязательные UI-блоки (из прототипа)

1. **Topbar** — часы работы, ссылка Livrare, телефон, переключатель RO/RU (и EN).
2. **Navbar** — логотип, поиск «Найти товары…», кнопка **Каталог**, корзина (badge), аккаунт.
3. **Hero** — слайдер промо + CTA.
4. **Товар дня** — таймер, наличие, цена, «Купить».
5. **H1 + категории** — карточки категорий (иконки/фото).
6. **Подборки** — «лучшие / популярные» (ряды товаров, «смотреть все»).
7. **Бренды** — полоса брендов.
8. **About** — блок о компании (короткий + ссылка на WP «Despre noi»).
9. **Contact / newsletter** — визуал + форма/ссылка (контактные тексты/адрес — из WP).
10. **Footer** — ссылки на инфо-страницы WP, соцсети, копирайт.

### 5.2 Правила соответствия Figma

- Пиксельная близость: отступы, типографика (Inter / system), цвета, радиусы, состояния hover/active.
- Адаптив: desktop → tablet → mobile (breakpoints из Figma; если нет — 1280 / 768 / 375).
- Все изображения из design system / assets; не оставлять emoji-placeholder на проде.
- i18n: строки UI в словаре RO/RU/EN; **не** хранить переводы инфо-страниц в limited admin.

### 5.3 Связь «прототип → прод»

| Прототип (static) | Прод |
|---|---|
| `href="#"` / mock badge 12 | реальные маршруты + API cart count |
| CSS-классы `.homepage`… | сохранить семантику или design tokens |
| PNG assets | CDN/static; lazy-load |
| Нет JS-логики магазина | подключить Biro26 shop API / BFF |

---

## 6. Ограниченная админка нового сайта

**Назначение:** править **только** то, чего нет в WP и что не должно идти в ERP.

### 6.1 В scope limited admin

- Баннеры / hero slides (картинка, title, CTA, порядок, период показа).
- «Товар дня» (COD товара из ERP **или** ручной override + таймер).
- Блоки главной: порядок секций, вкл/выкл, заголовки секций.
- Featured product lists (выбор COD / правило: «топ продаж» / «новинки»).
- SEO витрины (title/description homepage, OG image) — опционально.
- Feature flags (показать/скрыть блок).

### 6.2 Вне scope limited admin

- Полный CRUD номенклатуры, цен, групп → **Biro26 backoffice / ERP**.
- Тексты «Контакты», «Доставка», «О нас», политики → **WordPress**.
- Пользователи ERP, счета, платежи → **Biro26**.

### 6.3 Роли

| Роль | Доступ |
|---|---|
| `vitrine_editor` | limited admin витрины |
| `wp_editor` | только WP (как сейчас) |
| `shop_operator` | Biro26 backoffice |
| `admin` | всё |

### 6.4 Технические варианты (на выбор реализации)

**A (рекомендуется):** маленькое API + UI (FastAPI/Flask) + таблицы `VT_*` в APEX Always Free или отдельная schema;  
**B:** кастомные post types в WP только для баннеров (не для товаров);  
**C:** JSON-конфиг в git + CI (плохо для контент-менеджера).

Предпочтение: **A** или **B**, не смешивать товары с WP.

---

## 7. WordPress как источник информационных страниц

### 7.1 Что потребляет новый сайт из WP

- Список опубликованных pages (slug, title, content HTML, language variant).
- Меню (footer / info menu).
- Опции: телефон, email, адрес (если в options/ACF; иначе хардкод из Figma + override в limited admin).
- Мультиязычие: текущие slug `*-ru`, `*-en` или polylang/WPML — **использовать as-is**, не ломать.

### 7.2 Способы интеграции (приоритет)

1. **WordPress REST API** ` /wp-json/wp/v2/pages?slug=contacte` — предпочтительно.  
2. **Server-side fetch** в BFF нового сайта (кэш 5–15 мин).  
3. **Iframe** только как временный fallback (хуже SEO/UX).  
4. **Не** полный SQL dump WP в новую БД как primary.

### 7.3 Маршрутизация инфо-страниц на новом сайте

Пример:

```text
https://shop.officeplus.md/contacte     → контент WP page "contacte"
https://shop.officeplus.md/livrare      → WP "livrare"
https://shop.officeplus.md/despre-noi   → WP "despre-noi"
```

Либо поддомен / path prefix `/info/*`.  
Канонический URL: решить SEO (один canonical — либо WP, либо новый сайт).

### 7.4 Что WP **не** должен делать

- Не быть checkout.
- Не хранить корзину/заказы магазина.
- Не дублировать каталог товаров.

---

## 8. E-commerce: опора на Biro26

Новый фронт **обязан** использовать существующие контракты API (не изобретать ERP):

| Функция | API / модуль (ориентир) |
|---|---|
| Список товаров | `GET /api/biro26/shop/products` |
| Дерево/фасеты | `GET /api/biro26/shop/tree`, brands |
| Карточка | product by cod + `shop/product` info |
| Корзина / checkout | shop session + create invoice |
| Регистрация / login клиента | shop register/login |
| Прайс/остатки | как в текущем shop |

### 8.1 BFF (рекомендуется)

Слой между Figma-фронтом и Biro26:

- агрегирует ответы под UI-карточки Figma;
- кэш read-only каталога;
- **не** обходит rate limit бесконтрольно (учесть `200/hour`, X-Real-IP);
- internal sync/admin calls — отдельный key / exempt localhost.

### 8.2 Rate limit (инвариант)

- Публичные клиенты — по реальному IP (`X-Real-IP`).
- Полный dump каталога — **не** с браузера; batch/ночь/internal.
- Не поднимать лимит «в космос» без необходимости.

---

## 9. Информационная модель (упрощённо)

### 9.1 Сущности витрины (limited admin)

```text
VT_HERO_SLIDE     (id, lang, title, subtitle, cta_label, cta_url, image_url, sort, active_from, active_to)
VT_DEAL_OF_DAY    (id, product_cod, ends_at, stock_percent, active)
VT_HOME_SECTION   (id, code, title_ro/ru/en, enabled, sort)
VT_FEATURED_ITEM  (section_id, product_cod, sort)
VT_BANNER         (...)
```

### 9.2 Сущности магазина (read from Biro26)

```text
Product, Group/Category, Brand, Price, Stock, Client, Cart, Order/Invoice
```

### 9.3 Сущности контента (read from WP)

```text
Page(slug, lang, title, html, updated_at)
Menu(items → slug/url)
```

---

## 10. Этапы разработки (для ИИ / команды)

### Phase 0 — Контракты и инвентарь (1–2 дня)

- [ ] Зафиксировать Figma frames ↔ блоки `landingfigma1`.
- [ ] Список WP pages + slug RO/RU/EN.
- [ ] OpenAPI/таблица shop API Biro26 (используемые endpoints).
- [ ] Решение: path/domain нового сайта.

### Phase 1 — Каркас UI = Figma (статика → компоненты)

- [ ] Перенести `landingfigma1` в компонентную систему (React/Vue/Nuxt/… или enhanced static).
- [ ] Design tokens из CSS.
- [ ] i18n RO/RU/EN для chrome UI.
- [ ] Адаптив.

### Phase 2 — Каталог live

- [ ] Поиск, каталог, PLP, PDP на Biro26 API.
- [ ] Корзина + badge.
- [ ] «Товар дня» / featured — COD из API + admin override.

### Phase 3 — Checkout / ЛК

- [ ] Регистрация, login, заказ, печать счёта (как shop).
- [ ] Платежи — существующие интеграции.

### Phase 4 — WP content bridge

- [ ] REST client + кэш.
- [ ] Страницы footer/menu из WP.
- [ ] Не ломать текущий WP URL (или 301 strategy).

### Phase 5 — Limited admin

- [ ] Auth ролей.
- [ ] CRUD баннеров/секций/deal.
- [ ] Preview homepage.

### Phase 6 — Soft launch

- [ ] `/landingfigma1` или beta host.
- [ ] Параллельно WP+iframe shop.
- [ ] Cutover: новый сайт = main, WP = content CMS only.

---

## 11. Нефункциональные требования

| Тема | Требование |
|---|---|
| Performance | LCP < 2.5s mobile на homepage (сжатые PNG/WebP) |
| SEO | SSR или prerender homepage + PLP; canonical; hreflang RO/RU/EN |
| A11y | keyboard, aria, contrast как минимум WCAG AA для текста |
| Security | не светить ERP credentials; WP Application Passwords / readonly user |
| i18n | URL strategy согласовать с WP |
| Observability | логи 429, latency Biro26, ошибки WP REST |
| Deploy | static + BFF; **не** ломать `officeplus.md` WP и `/api/biro26` |
| Hosting | тот же Always Free Ubuntu / nginx path или поддомен |

---

## 12. Инварианты (нельзя нарушать)

1. **Не ломать** https://officeplus.md/ (WP) и Biro26 shop/backoffice; вся разработка нового сайта — только на **shop1.officeplus.md** (§3.5).  
2. **Не** переносить master-товары в WP или limited admin.  
3. **Не** дублировать тексты инфо-страниц в limited admin.  
4. Figma-лендинг — **визуальный контракт**; API — **функциональный контракт**.  
5. Rate limit и ERP нагрузка — уважать; полный catalog sync не с фронта.  
6. Пароли/секреты — keychain / env, не в git и не в HTML.

---

## 13. Definition of Done (DoD)

Новый сайт считается готовым, если:

1. Homepage **визуально** соответствует Figma/прототипу `landingfigma1` (review дизайна).  
2. Можно найти товар, добавить в корзину, оформить заказ (как на текущем shop).  
3. Страницы «Контакты / Доставка / О нас / …» показывают **актуальный** контент из WP после правки в WP Admin **без** деплоя фронта.  
4. Limited admin меняет hero/deal **без** деплоя и **без** WP.  
5. Старый WP+shop остаются работоспособны (rollback path).  
6. RO/RU/EN переключение UI + контент.  
7. Мобильная вёрстка без поломки корзины/меню.

---

## 14. Артефакты и ссылки (as-is)

| Артефакт | URL / путь |
|---|---|
| WP сайт (прод, не трогать) | https://officeplus.md/ |
| **Dev-среда (вся разработка тут)** | **https://shop1.officeplus.md/** |
| Dev shop / backoffice | https://shop1.officeplus.md/biro26-shop · /biro26-backoffice |
| Figma landing live | https://officeplus.md/landingfigma1/ |
| Biro26 shop | https://officeplus.md/biro26-shop |
| Biro26 backoffice | https://officeplus.md/biro26-backoffice |
| Docs APEX/microservices | https://officeplus.md/static/biro26/OFFICEPLUS_APEX_MICROSERVICES.html |
| Standalone zip | `officeplus-standalone.zip` |
| Landing files on server | `public_html/landingfigma1/` |
| Этот документ | `docs/OFFICEPLUS_AI_SITE_PROJECT.md` |

---

## 15. Промпт-якорь для ИИ-агента (копировать в задачу)

```text
Ты разрабатываешь новый сайт OfficePlus.
Вся разработка — ТОЛЬКО на https://shop1.officeplus.md/ (полная копия прода: WP + Flask
/home/ubuntu/artgranit_shop1, unit artgranit-shop1, порт 8020). Прод officeplus.md не трогать.
Визуал и UX: строго по Figma и прототипу https://officeplus.md/landingfigma1/
E-commerce: только API Biro26 (Artgranit), не WooCommerce.
Инфо-страницы (контакты, доставка, о нас, политики): только WordPress REST/контент officeplus.md;
не дублировать эти тексты во второй CMS.
Ограниченная админка нового сайта: только витрина (hero, баннеры, товар дня, секции главной).
Не ломать существующий WordPress и /api/biro26.
Учитывай rate limit API и proxy X-Real-IP.
Цель: полноценный онлайн-магазин = Figma landing + live catalog/cart/checkout + WP content.
```

---

## 16. Открытые решения (зафиксировать до Phase 2)

1. ~~Домен: path vs subdomain?~~ **Решено (2026-07-26): dev = поддомен `shop1.officeplus.md` (§3.5); финальный прод-домен решается на Phase 6.**  
2. Стек фронта: Nuxt / Next / Vue SPA / enhanced static?  
3. Limited admin storage: APEX vs WP CPT vs SQLite/Postgres?  
4. SEO cutover: когда новый homepage заменяет WP homepage?  
5. Figma file link + ответственный дизайнер (доступ для dev).

---

*Документ для ИИ и людей. Не содержит секретов. Обновлять при смене API/Figma frames.*
