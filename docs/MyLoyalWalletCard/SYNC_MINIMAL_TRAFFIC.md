# Синхронизация изменений с минимальным трафиком — myloyalwalletcard.eminescu.md

Как доставлять изменения из `/Users/pt/Projects.AI/MyLoyalWalletCard/loyalty-platform`
на прод (92.5.3.187) не гоняя каждый раз 43-мегабайтный архив.
**Типовой апдейт кода = 1–3 MB и ~30 секунд.**

Готовый скрипт: `loyalty-platform/scripts/sync-to-server.sh` (весь документ — объяснение того, что он делает и почему).

---

## 1. Почему полный архив — плохо, а rsync — правильно

Полный деплой (как при первом развёртывании) отправляет ~43 MB: standalone-сборка Next.js
включает урезанный `node_modules` (~120 MB на диске). Но между релизами меняется крошечная доля файлов:

| Что меняется | Где лежит | Типовой объём изменений |
|---|---|---|
| Ваш код (страницы, API, либы) | `.next/standalone/.next/server/**` | 0,2–2 MB |
| Клиентские чанки (хэшированные) | `.next/static/chunks/**` | 0,1–1 MB |
| `node_modules` внутри standalone | `.next/standalone/node_modules/**` | **0**, пока не менялись зависимости |
| Статика (картинки, презентация) | `public/**` | 0, если не трогали |
| Движок Prisma (linux) | `node_modules/.prisma/client/*.so.node` | 0, пока не обновляли Prisma (~17 MB при обновлении) |

`rsync -az --delete` передаёт **только изменившиеся файлы** (сравнение по размеру+mtime — быстро),
сжимает поток (`-z`) и удаляет на сервере то, чего больше нет локально (`--delete`).
Хэшированные имена чанков Next.js идеально дружат с rsync: новый код = новые имена файлов,
старые удаляются, неизменившиеся не передаются вовсе.

## 2. Штатный цикл обновления (кода)

```bash
cd /Users/pt/Projects.AI/MyLoyalWalletCard/loyalty-platform
./scripts/sync-to-server.sh              # build → rsync → restart → smoke-тест
./scripts/sync-to-server.sh --dry-run    # посмотреть, что уедет, не отправляя
SKIP_BUILD=1 ./scripts/sync-to-server.sh # если сборка уже сделана
```

Что скрипт делает по шагам:

```bash
# 1. Сборка (standalone уже включён в next.config.ts)
npx next build

# 2. Код сервера + node_modules — только дельта
rsync -az --delete -e "ssh -i ~/Downloads/ssh-key-2024-10-06.key" \
  --exclude '.next/static' \
  .next/standalone/  ubuntu@92.5.3.187:/home/ubuntu/myloyalwalletcard/

# 3. Клиентская статика — новые хэш-чанки
rsync -az --delete -e "ssh -i …" \
  .next/static/  ubuntu@92.5.3.187:/home/ubuntu/myloyalwalletcard/.next/static/

# 4. public/ (презентация, иконки)
rsync -az --delete -e "ssh -i …" \
  public/  ubuntu@92.5.3.187:/home/ubuntu/myloyalwalletcard/public/

# 5. Linux-движок Prisma (не входит в mac-сборку; rsync шлёт его только если версия сменилась)
rsync -az -e "ssh -i …" \
  node_modules/.prisma/client/libquery_engine-debian-openssl-3.0.x.so.node \
  ubuntu@92.5.3.187:/home/ubuntu/myloyalwalletcard/node_modules/.prisma/client/

# 6. Рестарт + проверка
ssh -i … ubuntu@92.5.3.187 'sudo systemctl restart myloyalwallet \
  && sleep 3 && curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:3010/api/health'
```

### Сколько это трафика на практике

| Сценарий | Передано |
|---|---|
| Правка одной страницы/route | ~0,3–0,8 MB |
| Новая фича на несколько файлов | ~1–3 MB |
| Обновление зависимостей (`npm i`) | 5–40 MB (меняется node_modules) |
| Обновление версии Prisma | +17 MB (движок) |
| Ничего не менялось (проверка) | ~50 KB служебного обмена |

## 3. Изменения схемы БД — SQL-патчем, не дампом

Полный дамп не нужен. Prisma умеет посчитать дельту схемы локально и выдать чистый SQL (килобайты):

```bash
# 1. Локально применяем изменение схемы к своей БД как обычно
npx prisma db push

# 2. Генерируем SQL-дельту: что нужно выполнить на проде
npx prisma migrate diff \
  --from-url "mysql://loyalty:loyalty123@127.0.0.1:3306/loyalty_platform_prod_snapshot" \
  --to-schema-datamodel prisma/schema.prisma \
  --script > /tmp/patch.sql
# (проще: держать prod_snapshot = копию прод-схемы; либо diff от предыдущей версии schema.prisma из git)

# 3. Бэкап прод-БД (обязательно) и применение патча — всё по ssh, трафик = размер SQL
ssh -i ~/Downloads/ssh-key-2024-10-06.key ubuntu@92.5.3.187 \
  'sudo mysqldump --no-tablespaces loyalty_platform | gzip > ~/mlwc_db_$(date +%Y%m%d_%H%M%S).sql.gz'
scp -i ~/Downloads/ssh-key-2024-10-06.key /tmp/patch.sql ubuntu@92.5.3.187:/tmp/
ssh -i ~/Downloads/ssh-key-2024-10-06.key ubuntu@92.5.3.187 'sudo mysql loyalty_platform < /tmp/patch.sql'
```

Данные (не схему) между стендом и продом **не** синхронизируем: прод живёт своей жизнью.
Если нужно перезалить демо-данные: локальный `mysqldump | gzip` (у нас 16 KB) → импорт, как при первом деплое.

## 4. Приёмы дальнейшей экономии трафика

- **`--dry-run --itemize-changes`** перед большим апдейтом: видно каждый файл и причину отправки.
- **Слабый канал:** добавить `--compress-level=9` и `--partial` (докачка после обрыва).
- **Много мелких файлов:** rsync и так батчит; ssh-мультиплекс (`ControlMaster auto`) убирает
  повторные рукопожатия — полезно, т.к. скрипт делает 4 rsync-сессии:
  ```
  # ~/.ssh/config
  Host 92.5.3.187
    ControlMaster auto
    ControlPath ~/.ssh/cm-%r@%h:%p
    ControlPersist 5m
  ```
- **Подозрение на рассинхрон** (mtime сбит, файлы «те же, но не те»): разово `rsync -azc` (checksum) —
  медленнее по CPU, но передаёт по-прежнему только реальные отличия.
- **Git-вариант** (альтернатива rsync, если появится git-репозиторий с доступом с сервера):
  `git push` на сервер (bare-репо + hook со сборкой) передаёт только пакет коммитов, но требует
  `npm install`/`next build` НА сервере — при 1 GB RAM это риск, поэтому для этого сервера
  выбран rsync готовой сборки: сервер вообще ничего не собирает.
- **Что НЕ делать:** не слать полный tar.gz на каждое изменение (43 MB), не запускать `npm install`
  на сервере (память), не удалять `/home/ubuntu/myloyalwalletcard` перед синком (ломает дельту rsync
  и сервис на время копирования).

## 5. Чек-лист после каждого синка

```bash
SSH='ssh -i ~/Downloads/ssh-key-2024-10-06.key ubuntu@92.5.3.187'
$SSH 'curl -s -o /dev/null -w "app %{http_code}\n"    http://127.0.0.1:3010/'
$SSH 'curl -s -o /dev/null -w "health %{http_code}\n" http://127.0.0.1:3010/api/health'
$SSH 'curl -s -o /dev/null -w "artgranit %{http_code}\n" http://127.0.0.1:8000/login'  # сосед жив
$SSH 'sudo journalctl -u myloyalwallet -n 5 --no-pager'                                # нет ошибок
```

Правило сервера (унаследовано от Artgranit/CLAUDE.md): после любой операции проверяем соседей;
конфиги nginx других доменов не трогаем.
