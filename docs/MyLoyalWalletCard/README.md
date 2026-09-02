# Документация MyLoyalWalletCard

**Первоисточник — этот каталог в git.** Работа ведётся по
[`docs/GIT_WORKFLOW.md`](../GIT_WORKFLOW.md) и [`AGENTS.md`](../../AGENTS.md).

## Рабочий каталог задачи

| Что | Где |
|---|---|
| worktree и ветка документации | `/Users/pt/Projects.AI/Artgranit-myloyalwalletcard`, ветка `feat/myloyalwalletcard` |
| пути задачи (правило B) | только `docs/MyLoyalWalletCard/**` |
| исходники платформы (не в этом репозитории) | `/Users/pt/Projects.AI/MyLoyalWalletCard` |

Создание worktree, если его нет:

```bash
cd /Users/pt/Projects.AI/Artgranit
git worktree add ../Artgranit-myloyalwalletcard -b feat/myloyalwalletcard origin/main
```

В `/Users/pt/Projects.AI/Artgranit` не работать и ветку там не переключать:
каталог общий, у коллег бывают незакоммиченные правки.

## Цикл правки документа

```bash
cd /Users/pt/Projects.AI/Artgranit-myloyalwalletcard
git pull --rebase=false origin main          # подтянуть main в ветку через merge
# правка файлов в docs/MyLoyalWalletCard/
git add docs/MyLoyalWalletCard/
git diff --cached --name-only | grep -cv '^docs/MyLoyalWalletCard/'   # должно быть 0
git commit -m "myloyalwalletcard: что сделано"
git push -u origin feat/myloyalwalletcard
git log --oneline origin/feat/myloyalwalletcard..HEAD                  # должно быть пусто
```

Влить в `main`, когда документ готов (из общего каталога, он стоит на main):

```bash
cd /Users/pt/Projects.AI/Artgranit
git checkout main && git pull --ff-only
git merge --no-ff feat/myloyalwalletcard && git push
```

Копия в `/Users/pt/Projects.AI/MyLoyalWalletCard/docs/` остаётся как удобный
локальный доступ к тем же файлам; после правки в ветке синхронизировать:

```bash
cp docs/MyLoyalWalletCard/*.md /Users/pt/Projects.AI/MyLoyalWalletCard/docs/
```

## Почему такой порядок — цена ошибки

25.08.2026 четыре документа (`MOBILE_APP.md`, `OWN_APP_STORE.md`,
`IOS_BUILD_AND_EU_DISTRIBUTION.md`, `ALTSTORE_REPO.md`) лежали в общем каталоге
Artgranit **незакоммиченными**, репозиторий стоял на чужой ветке
`feat/sda-core-module`. При возврате ветки в исходное состояние файлы стёрло:
в git они не попадали, в stash их не было — восстанавливались вручную.

Отсюда правило C из `GIT_WORKFLOW.md`: **каждый законченный шаг — commit и push.**
Незапушенный документ не существует.

## Состав

| Документ | О чём |
|---|---|
| `PROJECT_MYLOYALWALLETCARD.md` | обзор проекта, все ссылки и доступы |
| `DEPLOY_EMINESCU.md` | как развёрнут прод: systemd, nginx, БД, откат |
| `SYNC_MINIMAL_TRAFFIC.md` | обновление прода rsync-ом за 1–3 МБ вместо 43 МБ |
| `WALLET_ISSUER_STATUS.md` | статус эмитента карт: требования Apple и Google |
| `WALLET_ENROLLMENT_UNISIM.md` | пошаговая регистрация для Unisim-Soft SRL, готовые значения форм |
| `MOBILE_APP.md` | приложение UNA Market: настройки без пересборки, сборка, грабли |
| `IOS_BUILD_AND_EU_DISTRIBUTION.md` | iOS-сборка, установка на iPhone, магазины ЕС (DMA) |
| `ALTSTORE_REPO.md` | репозиторий приложений для AltStore |
| `OWN_APP_STORE.md` | портал `https://nufarul.eminescu.md/apps/`: 4 приложения, 5 платформ |
| `docs.json` | карточки для хаба документации |

Плюс в самом проекте: `loyalty-platform/TESTING.md` (план тестирования, он же
`/docs/testing` на проде), `loyalty-platform/README.md`, `desktop-pos/README.md`,
`mobile-app/mobile/README_SETTINGS.md`.
