# PROJECT: MyLoyalWalletCard — платформа лояльности Rogob

**Продакшен:** https://nufarul.eminescu.md/myloyalwalletcard (свой поддомен — после DNS, см. DEPLOY_EMINESCU.md)
**Исходники:** `/Users/pt/Projects.AI/MyLoyalWalletCard/loyalty-platform`
**Локальный стенд:** http://localhost:3000 (`npm run dev`)
**Дата деплоя:** 2026-08-03

## Что это

Платформа цифровой лояльности (аналог Loyaltyfy.io) для сети Rogob: карты в Apple/Google Wallet,
кэшбэк + штампы, бэк-офис, PWA кассира, POS API для касс UnaCommerce (100% совместим с Loyaltyfy POS API v1),
демо-касса UNA, вебхуки, сверка чеков.

- Стек: **Next.js 16** (standalone) + TypeScript + Tailwind + **Prisma 6** + **MariaDB/MySQL**
- ТЗ: `/Users/pt/Projects.AI/MyLoyalWalletCard/TZ/TZ_Loyalty_Platform_Rogob.md`
- Схема с кассами UNA согласована с Unisim-Soft 23.07.2026 (синхронное списание до печати чека)

## Ключевые URL (prod = nufarul.eminescu.md/myloyalwalletcard + путь, локально = localhost:3000 + путь)

| Что | Путь |
|---|---|
| Лендинг / регистрация клиента | `/` · `/join/rogob` |
| Веб-карта клиента (QR + Code128) | `/card/{code}` |
| PWA кассира | `/cashier` |
| Демо-касса UnaCommerce | `/una-pos` |
| Бэк-офис (8 разделов) | `/admin` |
| Хаб документации | `/docs` |
| Справочник POS API · OpenAPI | `/docs/pos-api` · `/api/pos/v1/openapi.json` |
| Интеграция UNA · план тестирования | `/docs/una` · `/docs/testing` |
| Презентация (18 слайдов) | `/integration-presentation.html` |
| Health | `/api/health` |

## Доступы (демо)

| Роль | Логин / пароль |
|---|---|
| Владелец | owner@rogob.md / owner123 |
| Super Admin | admin@platform.md / admin123 |
| Кассиры | cashier1@rogob.md, cashier2@rogob.md / cashier123 |
| POS API sandbox | Bearer `sk_test_2409fc063bea3cc0686cd3e7a549f7e8afc87d1972493fca`, карта `9131618479561` |
| UNA API | `X-Una-Key: una_demo_rogob_2026` |

## Скрытый тех-режим демо-кассы

По умолчанию журнал HTTP-вызовов API скрыт у ВСЕХ посетителей (чистый вид для клиентов).
Увидеть вызовы можно только по спец-ссылке (запоминается в браузере посетителя):
https://nufarul.eminescu.md/myloyalwalletcard/una-pos?tech=rogob2026
Выключение: `…/una-pos?tech=off`.

## Тесты

- `npm run test:pos` — 29 e2e-проверок POS API (нужен запущенный сервер)
- Полный план: `loyalty-platform/TESTING.md` = `/docs/testing`

## Документы этой папки

- `PROJECT_MYLOYALWALLETCARD.md` — этот файл (обзор, ссылки)
- `DEPLOY_EMINESCU.md` — как развёрнут прод: systemd, nginx, БД, SSL, откат
- `SYNC_MINIMAL_TRAFFIC.md` — синхронизация изменений с минимальным трафиком (главный рабочий документ)
- **`WALLET_ENROLLMENT_UNISIM.md`** — пошаговая регистрация для **Unisim-Soft SRL**: готовые значения для всех форм, CSR уже создан
- **`WALLET_ISSUER_STATUS.md`** — как получить статус эмитента карт: Apple Wallet (99 USD/год + D-U-N-S) и Google Wallet (бесплатно). Код выпуска карт уже готов и ждёт учётных данных
- `OWN_APP_STORE.md` — портал приложений `https://nufarul.eminescu.md/apps/`: 4 приложения на 5 платформ
- `MOBILE_APP.md` — приложение UNA Market (Android + iOS): настройки без пересборки, сборка, грабли
- `IOS_BUILD_AND_EU_DISTRIBUTION.md` — iOS-сборка, установка на iPhone, альтернативные магазины ЕС
- `ALTSTORE_REPO.md` — репозиторий приложений для AltStore

## Мобильные и десктопные приложения

- **UNA Market** (Android + iOS) — `MyLoyalWalletCard/mobile-app/mobile`, адрес API меняется в настройках приложения
- **Rogob POS** (Windows/macOS/Linux) — `MyLoyalWalletCard/desktop-pos`, кассовый терминал на Python без зависимостей
- Портал раздачи: **https://nufarul.eminescu.md/apps/**
