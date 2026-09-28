# Установка и развёртывание модуля «Планограммы»

Документ описывает все скрипты, участвующие в установке модуля, порядок их
запуска и что каждый из них делает — и, что важнее, чего **не** делает.

Модуль живёт внутри приложения Artgranit и отдельно не устанавливается:
ставится код приложения плюс Oracle-объекты с префиксом `PLG_`.

---

## 0. Кратко: минимальный путь

```bash
# 1. Окружение и зависимости
cd /Users/pt/Projects.AI/Artgranit
python3 -m venv venv && venv/bin/pip install -r requirements.txt

# 2. Oracle-объекты модуля (11 файлов, префикс PLG_)
venv/bin/python deploy_oracle_objects.py --only plg_

# 3. Локальный запуск
./run_local.sh          # → http://localhost:3003/UNA.md/orasldev/planograms
```

```bash
# 4. Развёртывание кода на боевой контур nufarul
./deploy_to_remote.sh
```

```bash
# 5. Обязательная проверка после ЛЮБОГО деплоя
curl -I https://nufarul.eminescu.md/login
```

---

## 1. Требования

| Компонент | Версия / условие |
|---|---|
| Python | 3.12 (на сервере — `/home/ubuntu/artgranit/venv`, Python 3.12) |
| Oracle | Autonomous Database (ADB), доступ через wallet |
| Драйвер | `python-oracledb` (thin mode, ставится из `requirements.txt`) |
| ОС разработки | macOS / Linux |
| Порт локально | 3003 (`PORT` в `.env` или окружении) |

Новых зависимостей модуль не добавляет: все визуализации (карта зала, Гант,
граф поставщиков, ценовые шкалы, пузырьковая диаграмма) нарисованы своим SVG,
все алгоритмы прогноза — чистый Python без numpy/scipy.

---

## 2. Конфигурация: `.env`

Файл `.env` лежит в корне проекта и **никогда не попадает в архив деплоя** —
`deploy_to_remote.sh` сохраняет его на сервере и возвращает после распаковки.

Ключи, которые нужны модулю:

| Ключ | Назначение |
|---|---|
| `DB_USER`, `DB_PASSWORD` | Учётная запись Oracle |
| `CONNECT_STRING`, `TNS_ALIAS` | Строка подключения к ADB |
| `WALLET_DIR` | **Абсолютный** путь к распакованному wallet вне каталога проекта |
| `WALLET_PASSWORD`, `WALLET_ZIP` | Пароль wallet и путь к архиву (если используется) |
| `ENVIRONMENT` | `LOCAL` или `REMOTE` |
| `PORT`, `SERVER_HOST` | Порт и интерфейс Flask |
| `SECRET_KEY` | Подпись сессий |
| `DEFAULT_USERNAME`, `DEFAULT_PASSWORD` | Учётка входа в приложение; если не заданы, берутся `DB_USER`/`DB_PASSWORD` |
| `REMOTE_SERVER_HOST`, `REMOTE_USER`, `REMOTE_SSH_KEY`, `REMOTE_SSH_PORT`, `REMOTE_PATH` | Параметры деплоя на nufarul |

> **Wallet.** На сервере wallet хранится вне каталога деплоя:
> `/home/ubuntu/oracle_wallets/wallet_HXPAVUNKCLU9HE7Q`, а `WALLET_DIR` в
> remote-`.env` указывает на него абсолютным путём. В архив деплоя wallet
> не входит и входить не должен.

---

## 3. Oracle-объекты модуля

### 3.1 Состав: 11 SQL-файлов

Порядок обязателен — файлы ссылаются друг на друга.

| Файл | Что создаёт |
|---|---|
| `sql/80_plg_tables.sql` | Справочники, master-data, документ «Планограмма», метрики, уведомления, настройки, аудит |
| `sql/81_plg_views.sql` | 12 представлений `V_PLG_*` основного контура |
| `sql/82_plg_demo_data.sql` | Демо-магазин по макету: зоны, оборудование, товары, планограммы, акции, задачи, 30 дней метрик |
| `sql/83_plg_i18n.sql` | Словарь строк интерфейса RU/RO/EN |
| `sql/84_plg_testdata.sql` | Наборы данных (`PLG_DATASETS`), факт продаж, реестр алгоритмов генерации, журнал прогонов; `ALTER TABLE` над `PLG_STORES`/`PLG_PRODUCTS` |
| `sql/85_plg_forecast.sql` | Алгоритмы и модели прогноза, прогоны, результаты, представления |
| `sql/86_plg_i18n_gen.sql` | Строки интерфейса генератора и конфигуратора прогноза |
| `sql/87_plg_logistics.sql` | РЦ, зоны обслуживания, транспорт, рейсы, состав рейса |
| `sql/88_plg_partners.sql` | Поставщики, контакты, контракты, товарные группы, конкуренты, цены, рынки, сети |
| `sql/89_plg_partner_views.sql` | 13 представлений логистики и партнёрского контура |
| `sql/90_plg_i18n_partners.sql` | Строки интерфейса логистики, поставщиков, конкурентов, рынков |
| `sql/91_plg_processes.sql` | Бизнес-процессы: `PLG_PROCESSES` и восемь схем BPMN в формате draw.io. **Файл генерируется** скриптом `scripts/gen_plg_processes.py`, править нужно его |
| `sql/92_plg_i18n_processes.sql` | Строки интерфейса раздела «Бизнес-процессы» |
| `sql/93_plg_fresh.sql` | Фреш-контур: температурные режимы, профили категорий, маршруты поставки, фреш-колонки товара и результата прогноза, алгоритм `fresh` и две модели, разметка фреш-товаров, засев маршрутов |
| `sql/94_plg_mobile.sql` | Мобильный контур: устройства, заказы из зала, позиции, журнал распознавания, речевой словарь, представления |
| `sql/95_plg_i18n_fresh.sql` | Строки интерфейса разделов «Фреш» и «Заказы из зала» |

Файлы `93`, `94`, `95` рассчитаны на **повторный запуск**: добавление колонок
идёт через проверку словаря, справочники через `MERGE`, словарь интерфейса
пересоздаётся по ключам. Повторный прогон `91` перезаписывает схемы процессов
целиком — правки, сделанные оператором в бэк-офисе, при этом теряются:
эталон схемы лежит в генераторе.

### 3.2 Скрипт: `deploy_oracle_objects.py`

Единственный способ ставить схему модуля.

```bash
# Посмотреть, что будет выполнено, ничего не меняя
venv/bin/python deploy_oracle_objects.py --only plg_ --dry-run

# Развернуть все объекты модуля
venv/bin/python deploy_oracle_objects.py --only plg_

# Развернуть отдельные очереди
venv/bin/python deploy_oracle_objects.py --only 84_plg 85_plg 86_plg
venv/bin/python deploy_oracle_objects.py --only 87_plg 88_plg 89_plg 90_plg
venv/bin/python deploy_oracle_objects.py --only 93_plg 94_plg 95_plg
```

### Вспомогательные скрипты

| Скрипт | Назначение |
|---|---|
| `scripts/gen_plg_processes.py` | Генерирует `sql/91_plg_processes.sql` из компактного описания процессов. Запускать после правки схем, затем деплоить SQL |
| `scripts/gen_plg_presentation.py` | Пересобирает `docs/Planograms/presentation.html`: живые ссылки и BPMN-слайды |
| `scripts/gen_plg_bonus_slides.py` | Добавляет в презентацию блок слайдов под конкретную сеть. Идемпотентен |
| `scripts/seed_plg_voice_demo.py` | Демо-данные голосового контура: устройства и заказы из зала. `--store CODE --reset` |

| Флаг | Что делает |
|---|---|
| `--only SUBSTR [SUBSTR …]` | Выполнить только файлы, содержащие подстроку. **Без него скрипт прогонит ВЕСЬ список файлов проекта**, включая демо-данные других модулей — они вставятся повторно |
| `--dry-run` | Разобрать файлы и показать число команд, ничего не выполняя |
| `--drop` | Сначала выполнить `00_drop.sql`. Для модуля не нужен |
| `--sql-dir PATH` | Другой каталог с SQL |

**Как скрипт разбирает файлы.** Разделитель блоков — одиночный `/` на отдельной
строке (стиль SQL\*Plus). Блок с `BEGIN … END;` выполняется целиком как PL/SQL,
остальные режутся по `;` на отдельные команды. Поэтому в SQL-файлах модуля
после каждого триггера и анонимного блока стоит `/`.

**Повторный запуск.** Файлы `84` и `88` содержат `ALTER TABLE … ADD` — на уже
развёрнутой схеме повторный прогон даст ошибки «столбец существует». Это
ожидаемо и безопасно: скрипт продолжает работу и в конце печатает счётчик
ошибок. Файлы с `CREATE OR REPLACE VIEW` можно перезапускать сколько угодно.

**Проверка после установки:**

```bash
venv/bin/python -c "
from models.database import DatabaseModel
with DatabaseModel() as db:
    print(dict(db.execute_query(\"SELECT OBJECT_TYPE, COUNT(*) FROM USER_OBJECTS WHERE OBJECT_NAME LIKE 'PLG%' OR OBJECT_NAME LIKE 'V_PLG%' GROUP BY OBJECT_TYPE\")['data']))
    print('невалидных:', db.execute_query(\"SELECT COUNT(*) FROM USER_OBJECTS WHERE (OBJECT_NAME LIKE 'PLG%' OR OBJECT_NAME LIKE 'V_PLG%') AND STATUS<>'VALID'\")['data'][0][0])"
```

Ожидается: 54 таблицы, 30 представлений, 45 триггеров, 40 последовательностей,
невалидных — 0.

> `ALTER TABLE` в файлах `84` и `88` инвалидирует зависимые представления.
> В конце `84_plg_testdata.sql` стоит блок рекомпиляции — **не удалять его**,
> иначе объекты останутся в статусе `INVALID`.

---

## 4. Запуск приложения

### 4.1 Локально: `run_local.sh`

```bash
./run_local.sh
```

Что делает: создаёт `venv`, если его нет; ставит зависимости из
`requirements.txt`, если их нет; выставляет `ENVIRONMENT=LOCAL`, `PORT=3003`,
`SERVER_HOST=0.0.0.0`; печатает адреса и запускает `app.py`.

Модуль доступен по `http://localhost:3003/UNA.md/orasldev/planograms`
(после входа через `/login`).

### 4.2 На сервере: systemd

Приложение на nufarul запускается **только** через systemd:

```bash
sudo systemctl restart artgranit     # перезапуск
sudo systemctl status artgranit      # состояние
journalctl -u artgranit -f           # логи
```

`pkill` + `nohup` использовать нельзя — процесс уходит из-под systemd
и не поднимется после перезагрузки сервера.

---

## 5. Развёртывание на боевой контур

### 5.1 Скрипт: `deploy_to_remote.sh`

```bash
./deploy_to_remote.sh
```

Покрывает **только** контур nufarul (`92.5.3.187`, `/home/ubuntu/artgranit`).
Семь шагов:

1. Резервная копия на сервере — вызывает `backup_remote.sh`
2. Архив локального проекта — вызывает `backup_local.sh`
3. Сборка архива передачи с исключениями (`.git`, `venv`, `.env`, wallet, `backups/`, `AccountingDemoXcode`, `.claude`, WP-деревья)
4. Копирование архива на сервер по scp
5. Распаковка: **venv переносится в сторону и возвращается**, `.env` и относительный wallet сохраняются и восстанавливаются
6. Oracle-объекты — **пропускаются по умолчанию** (база общая с локальной)
7. `pip install -r requirements.txt` и `sudo systemctl restart artgranit`

| Переменная | Эффект |
|---|---|
| `DEPLOY_ORACLE_ON_REMOTE=1` | Выполнить шаг 6 — прогнать `deploy_oracle_objects.py` на сервере. Для модуля обычно **не нужно**: Oracle общая, схема ставится один раз с локальной машины |

> **Почему venv переносится, а не пересобирается.** 31.07.2026 сайт дважды падал
> с 500 на ~2 минуты: скрипт делал `rm -rf` каталога проекта вместе с venv,
> и работающий процесс умирал на ленивых импортах. Причина устранена; логику
> сохранения venv в скрипте трогать нельзя.

### 5.2 Второй контур: officeplus.md

`deploy_to_remote.sh` его **не покрывает**. Обновление точечным патчем:

```bash
cd /Users/pt/Projects.AI/Artgranit
tar -czf /tmp/patch.tar.gz <только изменённые файлы>
scp -i <ключ> /tmp/patch.tar.gz <user@host>:/tmp/patch.tar.gz
ssh -i <ключ> <user@host> 'cd /home/ubuntu/artgranit && tar -xzf /tmp/patch.tar.gz \
  && rm -f /tmp/patch.tar.gz && sudo systemctl restart artgranit'
```

Деплой на officeplus выполняется только после явного разрешения владельца.

---

## 6. Резервное копирование

| Скрипт | Что делает |
|---|---|
| `backup_local.sh` | Архивирует локальный проект в `backups/Artgranit_local_<timestamp>.tar.gz` |
| `backup_remote.sh` | Снимает копию каталога проекта на сервере перед деплоем |
| `backup.sh` | Общий архив проекта (используется установщиком `install.py`) |

Каталог `backups/` в архив деплоя не входит.

---

## 7. Проверка после установки

Обязательная последовательность после **любого** изменения на сервере:

```bash
# 1. Flask отвечает локально на сервере
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/login      # → 200

# 2. Домен отвечает через nginx + SSL
curl -I https://nufarul.eminescu.md/login                                  # → HTTP/2 200

# 3. Страница модуля (без сессии — редирект на вход, это норма)
curl -s -o /dev/null -w '%{http_code}\n' \
     https://nufarul.eminescu.md/UNA.md/orasldev/planograms                # → 302

# 4. Служба под systemd
sudo systemctl status artgranit --no-pager                                 # → active
```

Если домен начал отдавать 502/504/403 или неверный сертификат — первая задача
восстановить `https://nufarul.eminescu.md/`, а не продолжать разработку.

---

## 8. Наполнение данными

Схема ставится пустой (кроме демо-магазина из `82_plg_demo_data.sql`).
Рабочие данные создаёт **генератор в админке модуля** — см. раздел
«Генератор данных» в [USER_GUIDE.md](USER_GUIDE.md).

Из командной строки то же самое:

```bash
venv/bin/python - <<'EOF'
import time
from controllers.planogram_controller import PlanogramController as C
r = C.start_generation({"name": "Сеть 10×400×365", "code": "NET-10-400",
                        "store_count": 10, "sku_count": 400, "days": 365,
                        "seed": 20260815, "gantt_days": 21})
print(r)
while True:                      # ждём в этом же процессе: поток демонический
    time.sleep(3)
    s = C.get_gen_run(r['run_id'])['data']
    print(s['status'], s.get('stage'), s.get('progress_pct'), s.get('rows_written'))
    if s['status'] != 'running':
        break
EOF
```

> Прогон идёт в фоновом потоке **внутри процесса Flask**. Скрипт, который
> запустил генерацию и сразу завершился, убьёт поток вместе с процессом —
> поэтому в примере есть цикл ожидания.

Полный прогон 10 магазинов × 400 SKU × 365 дней — около 918 тыс. строк,
6–8 минут.

---

## 9. Прочие скрипты репозитория

Не относятся к модулю, но соседствуют в корне — чтобы не путать:

| Скрипт | Модуль |
|---|---|
| `deploy_credite_oracle.py`, `deploy_credite_docs.py` | Кредитование Biro26 (`TMS_CREDITE_*`) |
| `deploy_biro26_*.py` | Biro26: витрина, склад, источники |
| `deploy_servouts26_oracle.py` | ServOuts26 |
| `seed_agro_demo_data.py`, `load_demo_data.py`, `generate_bulk_demo_data.py` | Демо-данные других модулей |
| `install.py` | GUI-установщик приложения целиком (Tkinter) |
| `setup-https.sh`, `fix_permissions.sh`, `full_restart*.sh` | Обслуживание сервера |

Модулю «Планограммы» из них нужен только `deploy_oracle_objects.py`.

---

## 10. Удаление модуля

Порядок обязателен: планограммы не каскадируются от магазина, а позиции
выкладки ссылаются на товар без каскада.

```sql
-- 1. Данные наборов (кроме защищённого DEMO) — лучше через админку,
--    кнопкой удаления набора: она соблюдает порядок сама.

-- 2. Объекты схемы
DROP TABLE PLG_FCT_RESULTS       CASCADE CONSTRAINTS;
DROP TABLE PLG_FCT_RUNS          CASCADE CONSTRAINTS;
DROP TABLE PLG_FCT_MODELS        CASCADE CONSTRAINTS;
DROP TABLE PLG_FCT_ALGORITHMS    CASCADE CONSTRAINTS;
-- … и так далее по всем PLG_*; представления V_PLG_* удаляются отдельно.
```

Практически удаление модуля целиком не требовалось ни разу — если нужно
почистить только тестовые данные, достаточно удалить набор в админке.

---

## 11. Публичная документация модуля

Вся документация отдаётся приложением по адресу самого модуля — отдельный
хостинг не нужен, файлы читаются из `docs/Planograms/` при каждом запросе,
поэтому правка `.md` сразу видна на сайте.

| Адрес | Что открывает | Доступ |
|---|---|---|
| `/UNA.md/orasldev/planograms/docs` | Хаб: карточки всех документов | без входа |
| `/UNA.md/orasldev/planograms/docs/user-guide` | Руководство пользователя | без входа |
| `/UNA.md/orasldev/planograms/docs/presentation-plan` | План презентации | без входа |
| `/UNA.md/orasldev/planograms/presentation` | Презентация, 14 слайдов | без входа |
| `/UNA.md/orasldev/planograms/docs/module` | Техническое описание | **требует входа** |
| `/UNA.md/orasldev/planograms/docs/install` | Этот документ | **требует входа** |

**Почему два документа закрыты.** Техническое описание и инструкция по установке
содержат путь развёртывания на сервере, размещение Oracle wallet, имя
systemd-юнита и перечень ключей окружения. В анонимном доступе это готовые
разведданные для атакующего, поэтому по умолчанию они за входом.

Управление доступом — реестр `PLG_DOCS` в `app.py`: флаг `public` у каждой
записи. Чтобы открыть документ всем, достаточно поставить `'public': True`;
чтобы закрыть открытый — `False`. Ничего больше менять не нужно.

Добавление нового документа: положить `.md` в `docs/Planograms/` и дописать
строку в `PLG_DOCS` (slug, файл, иконка, заголовок, описание, аудитория).
Ссылки между документами вида `[текст](ДРУГОЙ.md)` переписываются на маршруты
приложения автоматически.

Рендеринг — общий для проекта помощник `_docs_md_to_html()` на пакете
`markdown` (уже в `requirements.txt`), шаблон — `templates/planograms_docs.html`.
Оглавление документа собирается на стороне браузера из заголовков.
