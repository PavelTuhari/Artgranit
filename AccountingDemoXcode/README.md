# AccountingDemoXcode

Демо-проект под macOS на стандартных компонентах Xcode:
- AppKit + XIB (рантайм-формы через `NSViewController`)
- SwiftUI (встроенный контент вкладок внутри AppKit-контейнера)
- SQLite3 (локальная БД)
- без сторонних библиотек

## Что перенесено из донора `Project1test`

Источник: `/Users/pt/Documents/Embarcadero/Studio/Projects/Project1test.dproj`

Перенесены ключевые блоки:
- `Accounting`: документы, строки документа, проводки
- `Cashier`: продажа по штрихкоду, чеки и позиции чека
- `Admin`: карточки товаров и закупочные документы
- очередь фоновых операций (`DbApi`, аналог `uDbApi`)
- SQLite-схема и seed-данные (`accounts`, `products`, `barcodes`, `price_list`, ...)

## Где лежит БД

База создается автоматически при первом запуске:

`~/Library/Application Support/AccountingDemoXcode/bookkeeping_demo.db`

## Запуск в Xcode

Используйте полноценный Xcode-проект:

1. Откройте `AccountingDemoXcode/AccountingDemoXcodeApp.xcodeproj`.
2. Выберите схему `AccountingDemoXcodeApp`.
3. Target: `My Mac`.
4. Нажмите Run.

В этом режиме используются явные:
- `INFOPLIST_FILE = App/Info.plist`
- `PRODUCT_BUNDLE_IDENTIFIER = local.artgranit.accountingdemoxcode`

## Сборка через CLI (xcodeproj)

```bash
cd AccountingDemoXcode
xcodebuild -project AccountingDemoXcodeApp.xcodeproj \
  -scheme AccountingDemoXcodeApp \
  -configuration Release \
  -derivedDataPath .derived-release \
  build
```

Готовый `.app` после сборки:

`AccountingDemoXcode/.derived-release/Build/Products/Release/AccountingDemoXcodeApp.app`

Копия для быстрого запуска:

`AccountingDemoXcode/dist/AccountingDemoXcodeApp.app`

## Сборка через CLI (Swift Package, legacy)

```bash
cd AccountingDemoXcode
swift build --disable-sandbox
```

Готовый бинарь:

`AccountingDemoXcode/.build/arm64-apple-macosx/debug/AccountingDemoXcode`

Собранный `.app` bundle:

`AccountingDemoXcode/dist/AccountingDemoXcode.app`

## Основные файлы

- `AccountingDemoXcode/Sources/AccountingDemoXcode/App.swift`
- `AccountingDemoXcode/Sources/AccountingDemoXcode/AppKitRuntime.swift`
- `AccountingDemoXcode/Sources/AccountingDemoXcode/TabViews.swift`
- `AccountingDemoXcode/Sources/AccountingDemoXcode/ContentView.swift`
- `AccountingDemoXcode/Sources/AccountingDemoXcode/AppViewModel.swift`
- `AccountingDemoXcode/Sources/AccountingDemoXcode/DbApi.swift`
- `AccountingDemoXcode/Sources/AccountingDemoXcode/SQLiteStore.swift`
- `AccountingDemoXcode/Sources/AccountingDemoXcode/Models.swift`
- `AccountingDemoXcode/App/VisualForms/AccountingForm.xib`
- `AccountingDemoXcode/App/VisualForms/CashierForm.xib`
- `AccountingDemoXcode/App/VisualForms/AdminForm.xib`
