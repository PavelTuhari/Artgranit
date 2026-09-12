# Портал приложений Rogob

**https://nufarul.eminescu.md/apps/** — витрина с поиском, фильтром по платформам и
автоопределением системы посетителя. Четыре приложения на пяти платформах.

| Приложение | Кому | Платформы | Файл | Бесплатно навсегда |
|---|---|---|---|---|
| **UNA Market** | покупателям | Android 7.0+ | `UNAMarket.apk` (81 МБ) | ✅ |
| **Rogob Card** (PWA) | покупателям | iPhone, Android | ссылка на карту | ✅ |
| **UNA Market для iPhone** | покупателям | iOS 16.4+ | `UNAMarket.ipa` (8,2 МБ) | ❌ подпись 7 дней |
| **Rogob POS** | кассирам | Windows, macOS, Linux | `RogobPOS-macOS.zip`, `RogobPOS.pyz` | ✅ |

Файлы лежат в `/var/www/rogob-apps` на 92.5.3.187, раздаются nginx как `location /apps/`.
Исходник страницы — `MyLoyalWalletCard/desktop-pos/portal-index.html`.

---

## Rogob POS — кассовый терминал для компьютеров

Десктопное рабочее место кассира на Python: поиск клиента, чек со списанием кэшбэка,
возврат, журнал операций. Использует тот же POS API, что кассы UnaCommerce.

| Платформа | Файл | Что нужно |
|---|---|---|
| macOS | `RogobPOS-macOS.zip` (10 МБ) | ничего — Python внутри сборки |
| Windows | `RogobPOS.pyz` (20 КБ) | Python 3.8+ с python.org |
| Linux | `RogobPOS.pyz` (20 КБ) | `python3` + `python3-tk` |
| любая | `rogob_pos.py` | исходный код, запуск `python3 rogob_pos.py` |

Написан на стандартной библиотеке (tkinter + urllib) — на кассе не нужно ставить
зависимости. Адрес API, ключ и номер кассы задаются в самом приложении
(кнопка «Настройки», хранятся в `~/.rogob-pos.json`).

Проверено на живом сервере: поиск клиента, 404 по неизвестной карте, проведение чека
(списание 10 лей → начислено 4% от net), возврат с восстановлением баланса.

Сборка и детали: `MyLoyalWalletCard/desktop-pos/README.md`.
PyInstaller не умеет кросс-компиляцию, поэтому `.exe` для Windows собирается на Windows;
для неё и для Linux раздаётся универсальный `.pyz`.

---

## Честная картина по платформам

| Способ | Бесплатно | Навсегда | Ограничения |
|---|---|---|---|
| **Android APK с нашего сайта** | ✅ | ✅ | нет — это штатный механизм Android |
| **PWA на домашний экран (iOS/Android)** | ✅ | ✅ | веб-приложение: нет доступа к NFC и фоновым задачам |
| AltStore classic + бесплатный Apple ID | ✅ | ❌ | подпись 7 дней, 3 приложения, нужен ПК для продления |
| SideStore | ✅ | ❌ | те же лимиты Apple ID, продление по Wi-Fi без кабеля |
| AltStore PAL (ЕС, DMA) | ❌ | ✅ | Developer Program €99/год + нотаризация Apple |
| App Store | ❌ | ✅ | €99/год + модерация |
| TrollStore (вечная подпись) | ✅ | ✅ | **только старые iOS**; на iOS 26 не работает |

**Вывод:** для iOS бесплатного и бессрочного способа поставить *нативное* приложение
не существует — это ограничение Apple, а не нашей инфраструктуры. Бессрочно и бесплатно
на iPhone работает только PWA. На Android бесплатно и бессрочно работает всё.

---

## 1. Android — полноценный свой магазин

```
https://nufarul.eminescu.md/apps/UNAMarket.apk
```

- Размер 81 МБ, версия 1.0.0, Android 7.0+
- Подписан **собственным ключом Rogob**: `CN=Rogob, OU=IT, O=Rogob SRL, L=Chisinau, C=MD`
- Обновления — просто заменой файла на сервере

### Ключ подписи — беречь

Файл: `mobile-app/mobile/android/rogob-release.keystore`, alias `rogob`,
пароль `RogobStore2026!` (для стенда; в проде замените и храните в секретнице).

**Потеря ключа = невозможность выпускать обновления** — Android не даст установить
новую версию поверх старой, если она подписана другим ключом. Сделайте резервную копию.

Пересборка и подпись:

```bash
cd mobile-app/mobile/android
./gradlew assembleRelease
~/Library/Android/sdk/build-tools/36.0.0/apksigner sign \
  --ks rogob-release.keystore --ks-key-alias rogob \
  --ks-pass pass:RogobStore2026! --key-pass pass:RogobStore2026! \
  app/build/outputs/apk/release/app-release.apk
```

Проверка подписи: `apksigner verify --print-certs <apk>` — должно быть `CN=Rogob`,
а не `CN=Android Debug` (Gradle по умолчанию подписывает отладочным ключом — так раздавать нельзя).

---

## 2. iPhone — PWA, единственный бессрочно-бесплатный путь

Карта лояльности ставится на домашний экран как приложение:

1. Открыть в **Safari**: `https://nufarul.eminescu.md/myloyalwalletcard/join/rogob`
2. Зарегистрироваться — откроется карта со штрихкодом
3. «Поделиться» ⬆️ → **«На экран Домой»**

Что работает: штрихкод для кассы, баланс, история, полноэкранный режим без адресной строки,
собственная иконка. Ничего не истекает, Apple ID и сертификаты не нужны.

Реализация в платформе:
- `src/app/manifest.ts` — манифест (`display: standalone`, иконки, цвета бренда)
- `src/app/layout.tsx` — `appleWebApp` (заголовок, статус-бар) и `viewport.themeColor`
- `public/icon-192.png`, `icon-512.png`, `apple-touch-icon.png`

Проверка: `curl https://nufarul.eminescu.md/myloyalwalletcard/manifest.webmanifest`

---

## 3. iPhone — нативное приложение через AltStore

Витрина даёт две кнопки: добавить наш источник в AltStore и скачать `.ipa` напрямую.
Источник: `https://nufarul.eminescu.md/apps/source.json` (подробности — `ALTSTORE_REPO.md`).

Помните про семидневный срок бесплатной подписи: это ограничение Apple, обойти его
бесплатно на актуальной iOS нельзя.

---

## Грабли: страница скачивалась вместо открытия

Первая версия конфига содержала внутри `location /apps/`:

```nginx
types { application/json json; image/png png; }   # ← так делать нельзя
default_type application/octet-stream;
```

Блок `types` **заменяет** глобальную таблицу `mime.types` целиком, а не дополняет её.
HTML переставал определяться, уходил в `default_type` и браузер скачивал `index.html`
файлом вместо отображения портала. Код ответа при этом был 200, и по содержимому через
`curl` всё выглядело правильно — ловится только по заголовку `Content-Type`.

Рабочий вариант — перечислять в `types` все нужные расширения, включая `html`:

```nginx
location /apps/ {
    alias /var/www/rogob-apps/;
    index index.html;
    types {
        text/html                               html htm;
        application/json                        json;
        image/png                               png;
        text/plain                              py txt;
        application/zip                         zip;
        application/vnd.android.package-archive apk;
    }
    default_type application/octet-stream;   # для .ipa и .pyz
    add_header Access-Control-Allow-Origin *;
}
```

Проверка после любой правки раздачи:

```bash
curl -I https://nufarul.eminescu.md/apps/ | grep -i content-type   # → text/html
```

---

## Обновление витрины

```bash
scp -i ~/Downloads/ssh-key-2024-10-06.key index.html ubuntu@92.5.3.187:/tmp/
ssh -i ~/Downloads/ssh-key-2024-10-06.key ubuntu@92.5.3.187 \
  'sudo mv /tmp/index.html /var/www/rogob-apps/ && sudo chown www-data:www-data /var/www/rogob-apps/index.html'
```

При замене `.apk` или `.ipa` не забудьте поправить `size` в `source.json` — AltStore
сверяет размер и откажется ставить при расхождении.
