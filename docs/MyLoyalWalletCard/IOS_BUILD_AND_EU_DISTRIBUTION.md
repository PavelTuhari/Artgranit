# iOS-сборка UNA Market и способы установки на iPhone (включая ЕС / альтернативные магазины)

Проект: `MyLoyalWalletCard/mobile-app/mobile` (Expo SDK 57 / React Native 0.86).
Нативный iOS-проект сгенерирован (`ios/UNAMarket.xcworkspace`), CocoaPods установлены.

---

## 1. Что собрано

| Сборка | Подпись | JS-бандл | Статус |
|---|---|---|---|
| Debug, симулятор | не нужна | из Metro | ✅ работает (iPhone 17 Pro, iOS 26.2), 96 МБ |
| **Release, симулятор** | не нужна | **вшит внутрь (2,2 МБ)** | ✅ **работает без Metro**, 59 МБ |
| Release, устройство (`iphoneos`) | нужна | вшит внутрь | ✅ установлено на iPhone 16 Pro, `.ipa` 8,2 МБ |

Автономность Release проверена буквально: процесс Metro убит (`:8081` не отвечает),
приложение запущено заново и продолжает работать — JS читается из `main.jsbundle`.

Команды сборки для симулятора:

```bash
cd mobile-app/mobile/ios

# Debug — требует запущенного Metro (npx expo start)
xcodebuild -workspace UNAMarket.xcworkspace -scheme UNAMarket \
  -configuration Debug -sdk iphonesimulator \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro' \
  -derivedDataPath build CODE_SIGNING_ALLOWED=NO

# Release — автономный, JS внутри, Metro не нужен
xcodebuild -workspace UNAMarket.xcworkspace -scheme UNAMarket \
  -configuration Release -sdk iphonesimulator \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro' \
  -derivedDataPath build-release CODE_SIGNING_ALLOWED=NO

xcrun simctl install booted build-release/Build/Products/Release-iphonesimulator/UNAMarket.app
xcrun simctl launch booted md.una.retail
```

Bundle ID: `md.una.retail`. Движок JS: Hermes. Минимальная версия: iOS 16.4.

---

## ⚠️ Патч совместимости с Xcode 26

Expo SDK 57 не собирается на Xcode 26.3 «из коробки»:

```
expo-modules-jsi/.../RuntimeScheduler.h:53:26: error: 'RuntimeScheduler' cannot be annotated
with either SWIFT_RETURNS_RETAINED or SWIFT_RETURNS_UNRETAINED because it is not returning
a SWIFT_SHARED_REFERENCE type
```

Clang в Xcode 26 больше не принимает `SWIFT_RETURNS_RETAINED` на **конструкторах** класса.

Что проверено:
1. Перенос `SWIFT_SHARED_REFERENCE` из хвоста класса в его объявление — **не помогает**.
2. Обновление пакета — **недоступно**: стоит последняя стабильная `expo-modules-jsi@57.0.5`.
3. **Рабочее решение:** удалить `SWIFT_RETURNS_RETAINED` с обоих конструкторов.

Плата: Swift сделает лишний `retain`, один объект `RuntimeScheduler` не освободится
за время жизни процесса. Создаётся один раз при старте — влияния нет.

**Патч закреплён в репозитории:**

```bash
cd mobile-app/mobile
npm ci
./scripts/fix-xcode26.sh     # ← обязательно после каждого npm ci, до pod install
cd ios && pod install
```

- `scripts/fix-xcode26.sh` — идемпотентный скрипт
- `patches/expo-modules-jsi-xcode26.patch` — сам diff

---

## ⚠️ Вторая ловушка: ENOTEMPTY при переключении симулятор → устройство

```
Error: ENOTEMPTY, Directory not empty: ReactNativeDependencies/framework
** ARCHIVE FAILED **
```

React Native 0.86 подменяет пребилд-фреймворки при смене конфигурации и вызывает
`fs.rmSync(..., {recursive: true})`. На Node 25 + macOS этот вызов спотыкается о файлы
`.DS_Store`, которые Finder насыпает в папки Pods.

Очистка встроена в `scripts/build-ios-device.sh`:

```bash
find ios/Pods -name ".DS_Store" -delete
rm -rf ios/Pods/ReactNativeDependencies/framework ios/Pods/React-Core-prebuilt/framework
```

---

## 2. Установка на личный iPhone — 3 пути

### Путь A. Бесплатно, через Xcode (7 дней)

Не нужен платный аккаунт. Ограничения: приложение живёт **7 дней**, максимум 3 своих
приложения на устройстве.

**Готовый скрипт сборки под устройство:**

```bash
cd mobile-app/mobile
TEAM_ID=ВАШ_TEAM_ID ./scripts/build-ios-device.sh development
```

- `TEAM_ID` берётся в Xcode → Settings → Accounts → ваш аккаунт → Team ID
  (для Unisim-Soft: `F878X57C7Z`)
- Методы: `development` (свои устройства), `ad-hoc` (до 100 устройств), `app-store` (TestFlight)
- Адрес API задаётся переменной, а не правкой файлов:
  `UNA_API_BASE_URL=https://nufarul.eminescu.md/una-api TEAM_ID=... ./scripts/build-ios-device.sh`
- Результат: `build-device/UNAMarket.ipa`

Установка:

```bash
xcrun devicectl list devices                                    # найти UDID
xcrun devicectl device install app --device <UDID> build-device/UNAMarket.ipa
xcrun devicectl device process launch --device <UDID> md.una.retail
```

После установки на iPhone: **Настройки → Основные → VPN и управление устройством →
доверять разработчику**, иначе запуск отклоняется с `profile has not been explicitly trusted`.

### Путь B. Apple Developer Program (99 USD/год) + TestFlight

Самый практичный способ для команды: подпись на год (не 7 дней), до 10 000 тестировщиков
по ссылке, установка «по воздуху». Работает по всему ЕС.

### Путь C. Альтернативные магазины ЕС (DMA)

iOS с 17.4 в ЕС разрешает установку вне App Store. Что нужно разработчику для размещения
в альтернативном маркетплейсе (AltStore PAL, Epic Games Store, Setapp Mobile, Aptoide):

1. **Членство в Apple Developer Program** (99 USD/год) — бесплатный аккаунт не подойдёт.
2. **Принять «Alternative Terms Addendum for Apps in the EU»** — отдельные коммерческие
   условия ЕС, стоит прочитать до подписания.
3. **Нотаризация приложения Apple** — автоматическая проверка; без неё iOS не установит сборку.
4. **Договориться с самим маркетплейсом** о размещении.

**Чего НЕ нужно:** банковская гарантия 1 000 000 € требуется только тем, кто **создаёт
собственный маркетплейс**, а не размещает в нём своё приложение.

**Web Distribution** (раздача со своего сайта) жёстче: нужен аккаунт в Developer Program
не менее 2 лет **и** более 1 млн первых установок в ЕС за прошлый год.

> Условия Apple по ЕС/DMA менялись несколько раз. Перед подписанием сверьтесь
> с актуальной страницей Apple Developer по ЕС.

---

## 3. Что рекомендую

| Задача | Способ |
|---|---|
| Показать приложение на своём iPhone | Путь A (бесплатно, 7 дней) |
| Тестирование кассирами и менеджерами | Путь B — TestFlight |
| Массовая раздача покупателям | App Store либо PWA (см. `OWN_APP_STORE.md`) |
| Раздача в обход App Store принципиально | Путь C, после оценки ЕС-адендума |

Альтернативные магазины дают заметно меньший охват, чем App Store. Для карты лояльности
проще и дешевле PWA — она бесплатна и бессрочна.

---

## 4. Ограничения рабочей машины

- Панель симулятора (MCP) требует `sudo xcode-select -s /Applications/Xcode.app/Contents/Developer`
- Автоматические клики по симулятору требуют доступа Accessibility
- Оба ограничения снимаются только владельцем Mac; проверка сборок делалась через
  `xcrun simctl` и `devicectl` без интерактивных кликов.
