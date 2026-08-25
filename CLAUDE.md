# CLAUDE.md

Этот файл фиксирует обязательные инженерные правила для AI-агентов и разработчиков, которые добавляют или изменяют модули в проекте Artgranit.

## Главный принцип

Новые модули проектируются как **изолированные пакеты поверх общего ядра**,
Oracle-first и normalized-first.

Это означает:

1. весь код модуля лежит в `modules/<ключ>/` и подключается ядром
   (`core/module_loader.py`) — **в общем коде модуль не оставляет ничего**;
2. бизнес-данные модуля хранятся в Oracle;
3. схема данных нормализована;
4. у модуля есть собственный префикс Oracle-объектов;
5. код, dashboards, docs и deploy обновляются согласованно.

## Ядро и изоляция модулей — правило №1

Цель — **скорость параллельной разработки**. Несколько ИИ и несколько сессий
должны добавлять и развивать модули одновременно и никогда не конфликтовать.
Раньше модуль добавлялся правкой `app.py`: тринадцать модулей — девять тысяч
строк в одном файле, конфликт слияния с любой другой веткой и риск задеть
чужие маршруты. Поэтому теперь:

**Общее не трогаем. Модуль подключается сам.**

| Что | Где |
|---|---|
| Пакет модуля | `modules/<ключ>/__init__.py` — экспортирует `blueprint` с именем, равным ключу |
| Маршруты | `modules/<ключ>/routes.py`, адреса **без** префикса — его подставляет ядро |
| Валидация | `modules/<ключ>/controller.py` |
| SQL | `modules/<ключ>/store.py` |
| Чистые правила | `modules/<ключ>/rules.py` — без импорта БД, тестируются без wallet |
| Шаблоны | `modules/<ключ>/templates/` |
| DDL | `modules/<ключ>/sql/` |
| Установщик DDL | `modules/<ключ>/scripts/<ключ>_deploy.py` — **свой**, общий `deploy_oracle_objects.py` не трогать |
| Меню | `modules/<ключ>/module.json` |
| Документация | `docs/<Модуль>/` + `docs.json` |
| Тесты | `tests/test_<ключ>.py` |

Что ядро гарантирует и почему запрет сильнее проверки — `docs/CORE_MODULES.md`.
Образцы: `modules/seoforge/`, `modules/sda/`.

**Запрещено при добавлении модуля:**

1. править `app.py`, `deploy_oracle_objects.py`, `models/`, `controllers/`,
   `templates/`, `sql/` — это общий код;
2. писать адрес портала (`/UNA.md/orasldev/...`) строкой в шаблоне модуля:
   базу брать через `url_for`, иначе модуль привязан к точке монтирования;
3. вписывать модуль в шаблон меню руками.

**Проверка изоляции обязательна перед завершением задачи.** Она же —
приёмочный тест: в `tests/test_<ключ>.py` должны быть два теста по образцу
`tests/test_seoforge.py` — что общий `app.py` не упоминает модуль и что общий
установщик им не тронут.

```bash
git diff --name-only main HEAD   # ни одного общего файла
```

Старые модули (`aei`, `agro`, `biro26`, `colass`, `credit`, `decor`, `digi`,
`nufarul`, `planograms`, `servouts26`, `tbcontrol`) пока живут в `app.py` по
старому образцу — ядро их молча пропускает. Переносить их можно по одному,
одномоментная миграция не требуется.

## Как принимать решения

Владелец не хочет, чтобы у него спрашивали про технические развилки:
«мне вообще до лампочки, как ты всё это решишь». Решение принимать самому,
сообщать результат, а не список вариантов. Спрашивать только там, где
действие необратимо и выходит за рамки кода: деплой на боевой контур,
удаление данных, отправка чего-либо наружу.

## Критический production-инвариант

`https://nufarul.eminescu.md/` нельзя ломать.

Для любого AI-агента и разработчика это правило обязательное:

1. Не менять backend port, `systemd` unit, `WorkingDirectory`, virtualenv, `.env`, `nginx` `proxy_pass`, `server_name` или SSL-конфиг по отдельности, если это может уронить `https://nufarul.eminescu.md/`.
2. Любые изменения remote runtime или deploy-контура считаются незавершёнными, пока не подтверждено:
   `curl -I https://nufarul.eminescu.md/login`
3. Если домен начал отдавать `502`, `504`, `403`, неверный сертификат или перестал открываться после чьих-то правок, первая задача агента: восстановить `https://nufarul.eminescu.md/`, а не продолжать разработку.
4. Если в `/home/ubuntu/artgranit` уже работает другая модель или другой runtime-контур, нельзя “поверх” переключать порт или путь запуска без проверки live-домена.
5. Production URL `https://nufarul.eminescu.md/` важнее локальных экспериментов, временных рефакторингов и новых модулей.
6. **venv производственного сервера неприкосновенен.** 31.07.2026 сайт дважды падал с 500 на ~2 минуты: `deploy_to_remote.sh` делал `rm -rf /home/ubuntu/artgranit` (venv внутри, в архив не входит) и пересобирал окружение с нуля — работающий процесс умирал на ленивых импортах (`jinja2.debug`, `babel/locale-data`, `markupsafe`). **Причина устранена в тот же день:** скрипт теперь переносит venv в сторону до `rm -rf` и возвращает после распаковки (как `.env`/wallet). Правила остаются для любых других скриптов/агентов: ничего не удалять из `venv/`, никаких `pip uninstall`/массовых «чисток», и после ЛЮБОЙ операции на сервере — `curl -I https://nufarul.eminescu.md/login` → 200. Детали: `docs/NUFARUL_VENV_PROTECTED.md` (копии на сервере: `DO_NOT_DELETE_VENV.md`, `venv/DO_NOT_CLEAN.md`, `/home/ubuntu/DO_NOT_DELETE_VENV.md`).

## Что запрещено

Нельзя повторять следующие паттерны:

1. `APP_RUNTIME_KV`, `MODULE_RUNTIME_KV` и любые generic key-value таблицы для primary state;
2. `APP_EVENT_LOG` как общий контейнер для разных доменных данных;
3. хранение заказов, материалов, настроек, вариантов, статусов и других сущностей модуля в одном JSON blob;
4. использование `data/*.json`, `data/*.jsonl` или SQLite как authoritative storage;
5. добавление модуля без DDL, object prefix и документации.

## Обязательный шаблон для нового модуля

При создании нового модуля нужно сделать все пункты ниже.

### 1. Oracle-модель данных

1. Выбрать короткий префикс модуля, например `DECOR`, `NUF`, `CRED`.
2. Создать нормализованные таблицы по сущностям.
3. Разделить master-data, settings, documents, document items, metrics, statuses и logs.
4. Если нужен event log, сделать отдельную append-only таблицу модуля.

Примеры правильного подхода:

1. `DECOR_ORDERS` + `DECOR_ORDER_ITEMS`
2. `DECOR_SETTINGS` + дочерние таблицы значений
3. `CRED_EVENT_LOG` как отдельный event log

### 2. DDL и deploy

1. Добавить SQL-файл в `sql/`.
2. Включить этот файл в порядок выполнения в `deploy_oracle_objects.py`.
3. Проверить, что `deploy_to_remote.sh` недостаточно для новых Oracle-объектов: он переносит код, но по умолчанию не запускает DDL.
4. Если релиз модуля меняет Oracle-схему, отдельно выполнить установщик.
   Для модулей нового образца это **свой** скрипт модуля
   (`modules/<ключ>/scripts/<ключ>_deploy.py`), для старых — общий
   `python deploy_oracle_objects.py` или remote deploy с
   `DEPLOY_ORACLE_ON_REMOTE=1`.
5. **`--dry-run` не доказывает, что схема встанет.** Он показывает только,
   что файл правильно разбит на команды. 25.08.2026 DDL модуля SDA пережил
   четыре круга ревью и не устанавливался вовсе: строка `/` стояла только
   ПОСЛЕ триггера, разделитель блоков режет только по `/`, и каждый блок
   выходил как `CREATE INDEX; CREATE TABLE; CREATE SEQUENCE; CREATE OR
   REPLACE TRIGGER ... END;` — то есть один PL/SQL-оператор.
   `cursor.execute` на многооператорном тексте даёт ORA-00911.
   Правило: `/` ставить и ПЕРЕД, и ПОСЛЕ каждого PL/SQL-блока, а установщик
   один раз прогнать вживую.

### 2a. Oracle wallet на remote

1. Oracle wallet не считать частью application source tree.
2. На remote wallet должен храниться вне каталога деплоя, например в `/home/ubuntu/oracle_wallets/...`.
3. В remote `.env` `WALLET_DIR` должен быть абсолютным путём.
4. Нельзя полагаться на то, что wallet приедет на сервер вместе с обычным deploy архива кода.
5. Если по историческим причинам wallet лежит внутри проекта относительным путём, deploy обязан сохранить и восстановить его до миграции на внешний путь.

### 3. Backend и storage

1. Не добавлять новый модуль через local-file storage как временное решение.
2. Если нужен storage helper, он должен работать с нормализованными таблицами Oracle.
3. Публичный API storage-слоя может возвращать nested dict для совместимости UI, но persistence под ним должна оставаться нормализованной.
4. Если раньше существовал файл-источник для bootstrap, он может использоваться только для одноразовой миграции/seed, а не как постоянное хранилище.

### 4. UI и маршруты

1. Все UI-маршруты должны жить под `/UNA.md/orasldev/...`.
2. **Маршруты в `app.py` больше не добавляются.** Модуль объявляет их на
   своём blueprint в `modules/<ключ>/`, ядро подключает его само —
   см. [`docs/CORE_MODULES.md`](docs/CORE_MODULES.md). Образец полностью
   самодостаточного модуля — `modules/seoforge/`. Старые модули, чьи
   страницы ещё в `app.py`, продолжают работать и переносятся по одному.
3. Если модуль попадает в dashboards, обновить `dashboards/dashboard_*.json` и документацию в `docs/dashboards/`.
4. Нельзя оставлять устаревшие dashboard queries, которые смотрят на generic runtime tables.

### 4a. Видимость модуля в меню (обязательно)

Меню портала не пишется руками. Список модулей собирается при запуске
из карты маршрутов Flask (`models/module_registry.py`), поэтому любая
страница под `/UNA.md/orasldev/…` попадает в боковую панель и на страницу
`/UNA.md/orasldev/modules` сама — кто бы её ни добавил и в какой бы сессии.

От автора модуля требуется одно действие:

1. создать папку `modules/<ключ>/` с файлом `module.json`;
2. ключ — первый сегмент адреса до дефиса: у `/UNA.md/orasldev/biro26-site`
   ключ `biro26`;
3. в манифесте: `title` на трёх языках, `icon`, `order`, `url`, `descr`,
   при наличии — `docs` и `sql_prefix`, подписи страниц в `pages`.

Правила, которые нельзя нарушать:

1. **Нельзя прятать модуль из меню манифестом.** Манифест только украшает;
   отсутствие манифеста делает модуль «найденным автоматически»
   (оранжевая рамка на карте системы), но не невидимым.
2. **Нельзя вписывать модуль в шаблон меню руками.** Если пункт понадобился
   в шаблоне — значит, сломалось автообнаружение, чинить надо его.
3. Документация модуля кладётся в `docs/<Модуль>/`, а её реестр — в
   `docs/<Модуль>/docs.json` (`models/doc_registry.py`). Новый `.md` в папке
   появляется в хабе сам; без записи в манифесте он виден, но закрыт входом.
4. Внутри SPA-модуля новая панель `<section class="panel" id="panel-xyz">`
   подхватывается навигацией автоматически (`syncNavWithPanels`). Пункт
   с точкой вместо иконки означает «раздел найден, ему не назначили
   ни иконку, ни перевод» — это повод дописать NAV и словарь, а не
   признак поломки.

### 5. Документация

Каждый новый модуль обязан иметь:

1. описание Oracle-объектов и их префикса;
2. описание UI-маршрутов;
3. описание API;
4. инструкцию локального запуска;
5. инструкцию remote deploy;
6. checklist верификации после релиза.

Минимум нужно обновить:

1. `README.md`
2. профильный файл в `docs/dashboards/` или `docs/`
3. при необходимости `docs/PROJECT_DOCUMENTATION.html` или генератор этой документации

## Checklist перед завершением задачи

Перед тем как считать модуль готовым, проверить:

0. **изоляция:** `git diff --name-only main HEAD` не показывает ни одного
   общего файла; в `tests/test_<ключ>.py` есть два теста изоляции;
   ядро подключило модуль (`app.extensions["module_loader"].as_dict()` —
   ключ в `loaded`, не в `skipped`/`failed`);
0a. модуль виден в `/UNA.md/orasldev/modules` и в боковой панели портала,
   у него есть `modules/<ключ>/module.json`;
1. в коде нет SQLite/file-based authoritative state;
2. в коде нет generic runtime-table names вроде `APP_RUNTIME_KV`;
3. Oracle-объекты модуля реально существуют и видны в `USER_OBJECTS`;
4. dashboards и docs используют актуальные названия таблиц;
5. локальный запуск работает;
6. remote deploy обновляет код без потери `.env`, а remote wallet остаётся доступным по `WALLET_DIR`;
7. после deploy рабочий URL находится под `/login` и `/UNA.md/orasldev/...`, а не под абстрактным `/UNA.md/`.

## Отдельные правила для Artgranit

1. DECOR уже переведен на нормализованные `DECOR_*` таблицы. Не возвращать его к KV/blob storage.
2. Кредитный лог хранится в `CRED_EVENT_LOG`. Это event log, а не общий state store.
3. `deploy_to_remote.sh` разворачивает код в `/home/ubuntu/artgranit`.
4. Production Oracle wallet хранится вне каталога деплоя: `/home/ubuntu/oracle_wallets/wallet_HXPAVUNKCLU9HE7Q`.
5. Remote root URL может редиректить на `/login`; это нормальное поведение. Рабочий модульный URL: `/UNA.md/orasldev/...`.
6. Кредитование Biro26 живёт в `TMS_CREDITE_*` (провайдеры, организации, пакеты, заявки, лог вызовов API), развёрнутых в **обеих** БД — ADB основного проекта и OfficePlus 11g. DDL ставится отдельно от кода: `python deploy_credite_oracle.py --target adb|biro26|both`.
7. **Цена в кредит считается по ДЕЙСТВУЮЩЕЙ наценке**: `TMS_CREDITE_PLAN.MARKUP_PCT` + `TMS_CREDITE_ORG.TRANSPORT_MARKUP_PCT`. Надбавка организации заменяет неоказанный транспорт: при оплате в рассрочку транспорт не выставляется в счёт (`shop_invoice` пропускает блок при наличии `credit_plan_id`). Эта наценка обязана совпадать во всех четырёх местах: `models/biro26_credit.py` (`calc`), `controllers/biro26_controller.py` (`shop_invoice`) и три шаблона витрины — `site_cart.html`, `shop.html`, `site_product.html`. Расхождение = клиент видит одну цену, платит другую.

## Архивы и деплой (заморозка снята 2026-08-05)

Заморозка работ по архивам (31.07–05.08.2026) **снята владельцем 2026-08-05**:
стандартные процедуры архивации и `deploy_to_remote.sh` снова разрешены для
контура nufarul (92.5.3.187).

Полезный контекст, оставшийся от той недели:

1. Из архива деплоя исключены `AccountingDemoXcode` (600 МБ) и `.zip` к нему,
   `.claude` (92 МБ), `.superpowers`, старые `venv.*` — архив 37 МБ вместо 480 МБ
   (раньше `scp` падал по таймауту). Эти исключения сохранять.
2. `deploy_to_remote.sh` покрывает ТОЛЬКО nufarul. Контур officeplus.md
   (89.168.115.20, prod `/home/ubuntu/artgranit` + dev `/home/ubuntu/artgranit_shop1`)
   обновляется точечным патчем изменённых файлов:

```bash
cd /Users/pt/Projects.AI/Artgranit
tar -czf /tmp/patch.tar.gz <только изменённые файлы>
scp -i <ключ> /tmp/patch.tar.gz <user@host>:/tmp/patch.tar.gz
ssh -i <ключ> <user@host> 'cd /home/ubuntu/artgranit && tar -xzf /tmp/patch.tar.gz \
  && rm -f /tmp/patch.tar.gz && sudo systemctl restart artgranit'
```

Распаковка поверх каталога не трогает `venv/`, `.env` и wallet — их сохранять
отдельно не нужно. После КАЖДОГО обновления любого контура —
`curl -I https://nufarul.eminescu.md/login` и `curl -s -o /dev/null -w '%{http_code}' https://officeplus.md/cos`.

## VPN во внутреннюю сеть — поднимать самому

Площадки `192.168.0.*` (в том числе копия магазина на `192.168.0.250:8001`,
Proxmox `192.168.0.149` и площадка `192.168.0.148`) доступны **только** через
L2TP-туннель **VPN93**. Без него SSH и `scp` отваливаются по таймауту.

**Правило (владелец, 19.08.2026): туннель поднимает агент, а не человек.**
Не сообщать «VPN отвалился» и не ждать — проверить и включить:

```bash
scutil --nc status "VPN93" | head -1     # Connected / Disconnected
scutil --nc start  "VPN93"               # поднять
```

Порядок в работе:

1. Перед любым обращением к `192.168.0.*` — проверить статус.
2. Если не `Connected` — `scutil --nc start "VPN93"`, подождать 5–10 секунд
   и убедиться: `ping -c2 192.168.0.250` проходит.
3. Признак живого туннеля — интерфейс `ppp0` в состоянии `UP,RUNNING`,
   внешний адрес становится `93.115.136.18`. Повторный `start` на уже
   поднятом туннеле безвреден — соединение не рвётся, так что проверять
   статус заранее не обязательно, можно просто выполнить `start`.
4. Если соединения нет — причина всегда есть в логе, смотреть его, а не
   гадать:

```bash
tail -20 /var/log/ppp.log
```

| Строка в логе | Что значит | Что делать |
|---|---|---|
| `L2TP: incorrect user shared secret found` | не подходит общий ключ IPSec | **чинит только владелец**: Системные настройки → Сеть → VPN93 → Настройки аутентификации → Общий ключ — ввести заново |
| `L2TP cannot connect to the server` | сервер недоступен | проверить интернет и доступность 93.115.136.18 |
| `IPCP: up` + `local IP address` | туннель поднялся | работать дальше |

Про общий ключ (случай 22.08.2026): он лежит в **системной** связке ключей,
из терминала не читается — `security find-generic-password -g` открывает
диалог авторизации и подвисает; в документах проекта значение не записано.
Такую ошибку агент починить не может. Не тратить на неё время: сообщить
владельцу и продолжить на доступных площадках.

Пароли к самим машинам — в macOS Keychain, см. паспорт хоста
`PASSPORT_250_FLASK_ECOMMERCE.md`:

```bash
security find-internet-password -s 192.168.0.250 -a ubuntu -w
```

## Деплой: не отправлять `app.py` вслепую

19.08.2026 я уронил `nufarul.eminescu.md` на полторы минуты (502): отправил
`app.py` из рабочей ветки, а он импортирует модули (`controllers.peco_controller`,
`controllers.planogram_controller`), которых на сервере не было — служба не
поднялась.

**Правило:** если патч содержит `app.py`, он обязан содержать и все модули,
которые тот импортирует, либо отправлять код согласованным набором
(`controllers/ models/ integrations/ templates/ static/biro26/ config.py app.py`).
После каждого рестарта — сразу проверить, а не по итогам всей раскатки:

```bash
sudo systemctl restart artgranit && sleep 8
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/login   # 200
sudo journalctl -u artgranit --since '-1min' | grep -c ModuleNotFound   # 0
```

## Production infrastructure — точная конфигурация сервера

Зафиксировано по состоянию на 2026-04. Менять эти параметры можно только синхронно, с проверкой `https://nufarul.eminescu.md/` после каждого изменения.

### Flask / systemd

| Параметр | Значение |
|---|---|
| Сервис | `/etc/systemd/system/artgranit.service` |
| User | `ubuntu` |
| WorkingDirectory | `/home/ubuntu/artgranit` |
| ExecStart | `/home/ubuntu/artgranit/venv/bin/python3 app.py` |
| EnvironmentFile | `/home/ubuntu/artgranit/.env` |
| PORT | `8000` (только localhost: `127.0.0.1:8000`) |
| ENVIRONMENT | `REMOTE` |
| Python venv | `/home/ubuntu/artgranit/venv/` (Python 3.12) |

Перезапускать приложение только через:
```bash
sudo systemctl restart artgranit
```

Проверить статус:
```bash
sudo systemctl status artgranit
journalctl -u artgranit -f
```

**Нельзя** перезапускать через `pkill` + `nohup` — это уводит процесс из-под systemd, и при следующем restart сервера приложение не поднимется.

### Nginx

Конфиг: `/etc/nginx/sites-enabled/` (домен `nufarul.eminescu.md`)

- HTTP (80) → редирект 301 на HTTPS (кроме `.well-known/acme-challenge/`)
- HTTPS (443) → `proxy_pass http://127.0.0.1:8000`
- WebSocket поддержка: `Upgrade`, `Connection: upgrade`, `proxy_read_timeout 86400`
- `client_max_body_size 16M`
- Security headers: HSTS, X-Frame-Options, X-Content-Type-Options

Перезапустить nginx после изменений:
```bash
sudo nginx -t && sudo systemctl reload nginx
```

### SSL

- Провайдер: Let's Encrypt (certbot)
- Сертификат: `/etc/letsencrypt/live/nufarul.eminescu.md/fullchain.pem`
- Ключ: `/etc/letsencrypt/live/nufarul.eminescu.md/privkey.pem`
- Автопродление: certbot systemd timer + cron (`0 */12 * * *`)
- Продление не требует ручного вмешательства, пока сервер доступен по HTTP для ACME-challenge

Проверить сертификат:
```bash
certbot certificates
```

### Oracle Wallet

- Путь: `/home/ubuntu/oracle_wallets/wallet_HXPAVUNKCLU9HE7Q`
- В `.env`: `WALLET_DIR=/home/ubuntu/oracle_wallets/wallet_HXPAVUNKCLU9HE7Q`
- Wallet **не входит** в deploy-архив и не должен туда попадать

### Проверка production после любых изменений

```bash
# 1. Flask слушает
curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/login  # → 200

# 2. Домен отвечает через nginx + SSL
curl -I https://nufarul.eminescu.md/login  # → HTTP/2 200

# 3. Статус сервиса
sudo systemctl status artgranit --no-pager
```

## Если нужно быстро принять решение

Используй этот приоритет:

1. normalized Oracle tables;
2. explicit module prefix;
3. separate DDL deploy;
4. synced docs and dashboards;
5. verified local and remote routes.
