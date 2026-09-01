# UNA Market — мобильное приложение (Android + iOS)

Клиентское приложение сети: каталог, акции, список покупок, магазины и **карта лояльности
со штрихкодом** — альтернатива Apple/Google Wallet, когда карта нужна внутри своего приложения.

- Исходники: `MyLoyalWalletCard/mobile-app/mobile`
- Ветка-источник: `claude/una-md-mobile-app-fevqbc` (репозиторий `PavelTuhari/cursor25`)
- Стек: Expo SDK 57, React Native 0.86, TypeScript, SQLite (offline-first), JSON-конфигурация
- Bundle ID: `md.una.retail`

---

## 1. Настройки без пересборки — главное правило

**Адрес API меняется прямо в приложении.** Ничего перекомпилировать не нужно:

> Профиль → Настройки → **Адрес API** → вписать адрес → «Сохранить адрес» → перезапустить приложение

| Что | Где хранится | Приоритет |
|---|---|---|
| Адрес, введённый в «Настройках» | SQLite устройства, ключ `settings:apiBaseUrl` | **1 (главный)** |
| `UNA_API_BASE_URL` при сборке | зашивается в бандл | 2 |
| `extra.apiBaseUrl` из `app.json` | зашивается в бандл | 3 |

Кнопка «Вернуть адрес из сборки» очищает настройку — приложение снова берёт адрес из сборки.
Тот же экран управляет языком (RO/RU/EN), темой и ручной синхронизацией.

Реализация: `src/bootstrap.ts` (константа `API_BASE_URL_SETTING`, чтение до создания
`ApiClient`) и `src/ui/screens/SettingsScreen.tsx` (поле ввода + сохранение).

### Что ещё настраивается без пересборки

Приложение целиком описано JSON-конфигурацией в `config/`: вкладки, экраны, блоки,
сущности БД, тексты, тема, правила синхронизации. Тот же формат отдаётся сервером через
`GET /app-config`, поэтому **новая раскладка главной или новый набор экранов не требуют
релиза в сторах** — достаточно обновить конфигурацию на сервере.

---

## 2. Демо-бэкенд

| Назначение | Адрес |
|---|---|
| Для реального телефона (интернет, HTTPS) | `https://nufarul.eminescu.md/una-api` |
| Для симулятора / эмулятора на этом Mac | `http://localhost:4000` |
| Для Android-эмулятора | `http://localhost:4000` + `adb reverse tcp:4000 tcp:4000` |

Серверный экземпляр: systemd-сервис `una-api` на 92.5.3.187, порт 4010,
каталог `/home/ubuntu/una-api`, проксируется nginx как `/una-api/`.
Проверка: `curl https://nufarul.eminescu.md/una-api/health` → `{"ok":true}`.

Демо-вход: любой корректный номер (например `+37360123456`), код из SMS — **1234**
(мок возвращает его в поле `dev_code`, экран показывает подсказку).

---

## 3. Сборка

### Android

```bash
cd mobile-app/mobile
npm ci
npx expo prebuild --platform android --no-install
cd android && ./gradlew assembleDebug
# → android/app/build/outputs/apk/debug/app-debug.apk
```

Требуется Android SDK (`~/Library/Android/sdk`) и JDK 21. Эмулятор: AVD `una_test`.

Release для раздачи — с собственным ключом подписи, см. `OWN_APP_STORE.md`.

### iOS

```bash
cd mobile-app/mobile
npm ci
./scripts/fix-xcode26.sh          # обязательно: патч совместимости с Xcode 26
npx expo prebuild --platform ios --no-install
cd ios && pod install
```

Дальше — либо симулятор, либо устройство (см. `IOS_BUILD_AND_EU_DISTRIBUTION.md`):

```bash
# на свой iPhone (подпись автоматическая)
TEAM_ID=F878X57C7Z ./scripts/build-ios-device.sh development
xcrun devicectl device install app --device <UDID> build-device/UNAMarket.ipa
```

---

## 4. Проверенные сценарии

| Сценарий | Android | iOS |
|---|---|---|
| Главная: категории, «Лучшие цены», акции | ✅ | ✅ |
| Каталог и поиск | ✅ | ✅ |
| Вход по SMS-коду (демо 1234) | ✅ | — |
| Карта лояльности: штрихкод Code128, баллы, уровень | ✅ | — |
| Электронные чеки и история покупок | ✅ | — |
| Автономная работа без Metro (Release) | ✅ | ✅ |
| Дельта-синхронизация по курсору `updated_since` | ✅ | ✅ |
| Установка на реальный iPhone 16 Pro | — | ✅ |

Собственные тесты приложения: `npm test` — **112 тестов**, `npm run validate-config` — проверка JSON.

На iOS интерактивные сценарии не прокликаны из-за ограничений рабочей машины
(панель симулятора требует `sudo xcode-select -s /Applications/Xcode.app/Contents/Developer`,
клики — доступа Accessibility). Кодовая база JS общая с Android, расхождений не ожидается.

---

## 5. Свой магазин приложений

**https://nufarul.eminescu.md/apps/** — витрина с установкой под обе платформы:

| Платформа | Способ | Бесплатно навсегда |
|---|---|---|
| Android | APK, подписан ключом Rogob | ✅ да |
| iPhone | PWA (карта на домашний экран) | ✅ да |
| iPhone | нативное приложение через AltStore | ❌ подпись 7 дней |

Подробности и ограничения Apple — в `OWN_APP_STORE.md`, репозиторий AltStore — в `ALTSTORE_REPO.md`.

---

## 6. Известные грабли

| Симптом | Причина и лечение |
|---|---|
| iOS: `SWIFT_RETURNS_RETAINED … not a SWIFT_SHARED_REFERENCE` | Expo 57 несовместим с Xcode 26 → `./scripts/fix-xcode26.sh` |
| iOS: `ENOTEMPTY: ReactNativeDependencies/framework` | остатки конфигурации симулятора + `.DS_Store` → очистка встроена в `build-ios-device.sh` |
| iOS: `maximum number of installed apps using a free developer profile` | лимит 3 приложения у бесплатного Apple ID → удалить лишнее или оформить Developer Program |
| iOS: `profile has not been explicitly trusted` | Настройки → Основные → VPN и управление устройством → доверять разработчику |
| Мок на сервере падает с `SyntaxError` | в архив попали AppleDouble `._*` → `find … -name "._*" -delete` |
| Приложение на телефоне не видит API ноутбука | изоляция клиентов в Wi-Fi → указать в настройках `https://nufarul.eminescu.md/una-api` |
| Android: изменения `app.json` не применяются | значение зашито в APK при сборке → менять адрес в «Настройках» приложения |

---

## 7. Чего в приложении пока нет

Триггер присутствия по Wi-Fi/BLE (телефон сообщает кассе о входе в магазин, та подтягивает
баланс из центральной БД заранее). Сейчас синхронизация идёт по расписанию и при запуске,
а offline-first хранилище уже обеспечивает «баланс виден на кассе без сети» — видна и дата
последней синхронизации. Добавление BLE-маячка — отдельная задача на стороне приложения и кассы.
