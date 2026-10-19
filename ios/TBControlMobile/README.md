# TBControl Mobile (iPhone)

Приложение-«сторож» для всего хозяйства: Zabbix 3.4 (серверы, t° CPU,
проблемы), TBControl (магазины, кассы, события). Главное — **само привлекает
внимание**, когда долго нет связи с Zabbix или температура вышла за режим.
ТЗ: `docs/TBControl/MOBILE_APP_TZ.md`.

## Сборка

```bash
cd ios/TBControlMobile
xcodegen generate
xcodebuild -project TBControlMobile.xcodeproj -scheme TBControlMobile \
  -destination 'platform=iOS Simulator,name=iPhone 17' \
  CODE_SIGNING_ALLOWED=NO build
```

Для установки на свой iPhone: открыть `TBControlMobile.xcodeproj` в Xcode,
выбрать Team в Signing, запустить на устройстве. Без внешних зависимостей.

## Первый запуск

1. Настройки → Zabbix: пароль `Admin` (Keychain: `security find-generic-password -a Admin -s zabbix-web -w`).
   Работает только через VPN93; вне VPN включите «Я вне VPN».
2. Настройки → TBControl: хэш инвайта (панель TBControl → Инвайты,
   note «TBControl Mobile (iPhone)»).
3. Разрешить уведомления. Фоновое обновление — Background App Refresh в iOS.
4. «Тест сигнала» — увидеть критичный режим.

## Структура

| Файл | Что |
|---|---|
| `Sources/Models.swift` | уровни внимания, состояние связи, модели Zabbix/TBControl |
| `Sources/ZabbixClient.swift` | JSON-RPC: login, trigger.get, host.get, item.get (`cpu.temp[1|2]`, uptime) |
| `Sources/TBCClient.swift` | вход по хэш-инвайту, `/api/tbc/stats`, `events`, `cassa` |
| `Sources/MonitorStore.swift` | опрос, watchdog связи, движок внимания, уведомления, haptic/звук, повтор сигнала |
| `Sources/ContentView.swift` | вкладки, полоса внимания, красная заслонка «Понял» |
| `Sources/*View.swift` | Обзор, Температура (датчики + история), Проблемы, Кассы, Настройки |
| `Sources/AppSettings.swift`, `Keychain.swift` | настройки; секреты только в Keychain |
