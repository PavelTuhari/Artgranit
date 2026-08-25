# Репозиторий приложений Rogob для AltStore

Свой «магазин приложений» на нашем сервере: AltStore (и совместимые — SideStore,
AltStore PAL) умеют подключать сторонние источники по URL и показывать приложения
каталогом с обновлениями.

## Адрес источника

```
https://nufarul.eminescu.md/apps/source.json
```

Добавляется в AltStore: **Browse → Sources → + → вставить адрес**.
Либо ссылкой-схемой с самого телефона:
`altstore://source?url=https://nufarul.eminescu.md/apps/source.json`

## Что внутри

| Файл | Адрес | Назначение |
|---|---|---|
| `source.json` | `/apps/source.json` | манифест репозитория (apiVersion v2) |
| `UNAMarket.ipa` | `/apps/UNAMarket.ipa` | сборка приложения, 8,2 МБ |
| `icon.png` | `/apps/icon.png` | иконка |

Приложение в каталоге: **UNA Market** `md.una.retail`, версия 1.0.0, минимум iOS 16.4.

Файлы лежат в `/var/www/rogob-apps` на 92.5.3.187, раздаются nginx как `location /apps/`
из конфига `nufarul.eminescu.md` (бэкапы конфига — `~/nginx_nufarul.bak.*`).

## Обновление версии приложения

```bash
# 1. собрать новый .ipa
cd mobile-app/mobile
TEAM_ID=F878X57C7Z UNA_API_BASE_URL=https://nufarul.eminescu.md/una-api \
  ./scripts/build-ios-device.sh development

# 2. выложить и поправить version/size/date в source.json
scp -i ~/Downloads/ssh-key-2024-10-06.key build-device/UNAMarket.ipa ubuntu@92.5.3.187:/tmp/
ssh -i ~/Downloads/ssh-key-2024-10-06.key ubuntu@92.5.3.187 \
  'sudo mv /tmp/UNAMarket.ipa /var/www/rogob-apps/ && sudo chown www-data:www-data /var/www/rogob-apps/UNAMarket.ipa'
```

Размер файла в `source.json` должен совпадать с реальным, иначе AltStore ругается на загрузку.

## Важное ограничение: одного репозитория мало

Репозиторий — это витрина. Чтобы приложение из него **установилось**, нужен способ его подписать:

| Магазин | Подпись | Что требуется | Ограничения |
|---|---|---|---|
| **AltStore classic** | вашим Apple ID через AltServer | AltServer на Mac, ПК рядом при установке и раз в 7 дней | 3 приложения, 7 дней (бесплатный Apple ID) |
| **SideStore** | так же, но продление по Wi-Fi | разовая настройка с ПК | те же лимиты Apple ID |
| **AltStore PAL** (ЕС, DMA) | нотаризация Apple | Developer Program 99 USD/год, ЕС-адендум, нотаризация | ПК не нужен, лимитов нет |

**Состояние на 25.08.2026:** AltStore на телефоне установлен (v2.2.1), но не запускается —
истёк семидневный срок подписи бесплатного профиля (`invalid code signature`).

### AltServer установлен на рабочий Mac

`/Applications/AltServer.app` (скачан с `cdn.altstore.io`, 6,7 МБ архив → 18 МБ).
Подпись проверена: `Developer ID Application: Yvette Testut (6XVY5G3U44)` → Apple Root CA.
Значок живёт в меню-баре.

**Порядок оживления AltStore** (шаги с Apple ID выполняет владелец Mac):

1. iPhone подключён кабелем и разблокирован.
2. Значок AltServer в меню-баре → **Install AltStore** → выбрать устройство.
3. Ввести Apple ID и пароль — AltServer подпишет AltStore этим аккаунтом.
   *(Пароли вводит только человек.)*
4. На iPhone: Настройки → Основные → VPN и управление устройством → доверять разработчику.
5. Открыть AltStore → **Browse → Sources → +** → вставить адрес источника.
6. Установить **UNA Market** из источника «Rogob Apps».

Дальше AltStore напоминает о продлении подписи (раз в 7 дней при бесплатном аккаунте,
раз в год — при платном); Mac с AltServer должен быть в той же сети.

**Про лимит:** бесплатный профиль разрешает 3 приложения на устройство. Установка
UNA Market из AltStore не добавит четвёртое — это тот же bundle ID `md.una.retail`,
приложение переустановится поверх.

## Что это даёт по сравнению с прямой установкой

Приложение и так ставится через `devicectl device install`. Репозиторий добавляет:

- каталог с описанием, иконкой и историей версий;
- обновления «по кнопке» у всех, кто подключил источник, без кабеля;
- готовность к переезду в AltStore PAL: тот же `source.json` подойдёт, когда появится
  платный аккаунт и нотаризация.

См. также: `MOBILE_APP.md`, `OWN_APP_STORE.md`, `IOS_BUILD_AND_EU_DISTRIBUTION.md`.
