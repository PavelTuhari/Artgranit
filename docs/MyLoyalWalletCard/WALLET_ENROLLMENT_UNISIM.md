# Регистрация эмитента карт — Unisim-Soft SRL: готовые данные для форм

Рабочая шпаргалка: что вписывать в каждое поле. Данные собраны с сайта компании
и проверены 25.08.2026.

## Реквизиты компании

| Поле | Значение |
|---|---|
| Юридическое название | **Unisim-Soft SRL** |
| Юридический адрес | MD-2071, Chișinău, str. Alba Iulia 75, Moldova |
| Телефон | +373 79 144 604 |
| Рабочая почта | mail@unisim-soft.com |
| Сайт | https://unisim-soft.com |
| Директор (право подписи) | Pavel Tuhari |
| Страна | Moldova (MD) |

Модель: **Unisim-Soft SRL — эмитент-провайдер**. Один статус обслуживает всех клиентов
платформы (Rogob и последующих), карты брендируются под каждого клиента отдельно —
так же работают Loyaltyfy и другие SaaS-платформы лояльности.

---

## ⚠️ Проблему нужно решить до подачи в Apple

Apple проверяет сайт на домене компании и **не принимает** страницы-заглушки:
формулировка из требований — сайт должен быть «publicly available and functional»,
ссылки на соцсети и минимальные страницы отклоняются.

Сейчас `https://unisim-soft.com` отдаёт **87 байт** — только `meta refresh` на
`unisim-soft.una.md`. Содержательный сайт (100 КБ) живёт по второму адресу.
С высокой вероятностью проверяющий увидит пустую страницу и отклонит заявку.

**Что сделать (любой вариант):**
1. Разместить полноценный сайт прямо на `unisim-soft.com` (лучший вариант).
2. Либо заменить `meta refresh` на серверный редирект 301 — тогда посетитель и робот
   сразу попадают на рабочий сайт:
   ```nginx
   server {
       server_name unisim-soft.com www.unisim-soft.com;
       return 301 http://unisim-soft.una.md$request_uri;
   }
   ```
3. Либо (минимум) сделать на `unisim-soft.com` настоящую страницу с описанием компании,
   услугами, контактами и юридическими реквизитами — без редиректа.

Для Google Wallet это не критично, там таких требований к сайту нет.

---

## Шаг 1. D-U-N-S номер (бесплатно, самое долгое)

Проверка и запрос — на странице Apple:
**https://developer.apple.com/enroll/duns-lookup/**

Вписать ровно так:

```
Legal Entity Name:  Unisim-Soft SRL
Country / Region:   Moldova
Street Address:     str. Alba Iulia 75
City:               Chișinău
Postal Code:        MD-2071
Phone:              +373 79 144 604
Work Email:         mail@unisim-soft.com
Website:            https://unisim-soft.com
```

Если номер уже есть — форма покажет его сразу. Если нет — запрос уходит в Dun & Bradstreet,
ответ приходит на почту от 5 рабочих дней до 3–4 недель. Плата не взимается.

**Частая причина отказа:** расхождение названия или адреса с государственным реестром.
Название должно совпадать с регистрационными документами вплоть до формы «SRL».

---

## Шаг 2. Apple Developer Program (99 USD в год)

1. https://developer.apple.com/programs/enroll/ → **Start Enrollment**
2. Войти под Apple ID **с включённой двухфакторной аутентификацией**.
   Имя и фамилия в Apple ID должны быть настоящими — «Pavel Tuhari», без псевдонимов.
3. Тип регистрации: **Company / Organization**
4. Заполнить данными из таблицы выше + полученный D-U-N-S.
5. В поле роли указать, что вы директор с правом подписи.
6. Дождаться проверки (2–7 дней; Apple может позвонить на +373 79 144 604 —
   отвечать должен человек, подтверждающий ваши полномочия).
7. Оплатить 99 USD.

**Оплату и ввод пароля выполняете вы лично** — это учётные данные и платёж,
их нельзя доверять ни агенту, ни третьим лицам.

---

## Шаг 3. Сертификат Pass Type ID

Запрос на сертификат **уже создан** — файл готов:

```
loyalty-platform/wallet-certs/pass.csr
```

Подписан на `CN=Unisim-Soft SRL, emailAddress=mail@unisim-soft.com, C=MD`.
Приватный ключ `pass-key.pem` лежит рядом, в git не попадает (внесён в `.gitignore`).

Порядок в аккаунте разработчика:

1. **Certificates, Identifiers & Profiles → Identifiers → «+» → Pass Type IDs**
   Описание: `Rogob Loyalty` · Identifier: `pass.md.rogob.loyalty`
2. **Certificates → «+» → Pass Type ID Certificate** → выбрать созданный Pass Type ID
3. Загрузить `pass.csr` → скачать `pass.cer`
4. Скачать промежуточный сертификат **Apple WWDR G4**:
   https://www.apple.com/certificateauthority/
5. Положить оба файла в `loyalty-platform/wallet-certs/` и выполнить:
   ```bash
   cd loyalty-platform && npm run wallet:apple-pem
   ```
   Скрипт проверит, что ключ подходит к сертификату, и создаст `apple-env.txt`
   с готовыми строками для systemd.

---

## Шаг 4. Google Wallet — автоматизировано

Google Cloud CLI установлен на рабочий Mac (`/opt/homebrew/share/google-cloud-sdk`).
Почти всё делает скрипт, от человека нужен один вход и одна форма.

### 4.1. Разовый вход (только владелец аккаунта)

```bash
export PATH=/opt/homebrew/share/google-cloud-sdk/bin:$PATH
gcloud auth login
```

Откроется браузер с формой Google — логин и пароль вводит человек.
Пароли не передаются агенту и нигде не сохраняются: gcloud кладёт в
`~/.config/gcloud` только OAuth-токен.

### 4.2. Автоматическая часть

```bash
cd loyalty-platform && npm run wallet:google-setup
```

Скрипт создаёт проект, включает Google Wallet API, заводит сервис-аккаунт
и скачивает JSON-ключ в `wallet-certs/google-wallet-sa.json` (права 600, вне git).

### 4.3. Две операции в веб-консоли

Их нельзя выполнить из CLI — Google требует принятия условий человеком:

1. https://goo.gle/wallet-console → создать Issuer-аккаунт
   Public business name: **Unisim-Soft SRL** → записать **Issuer ID** (19 цифр)
2. Там же: **Users** → добавить сервис-аккаунт (email из ключа) с ролью **Developer**

### 4.4. Шаблон карты и включение

```bash
cd loyalty-platform
GOOGLE_WALLET_ISSUER_ID=<19 цифр> \
GOOGLE_WALLET_SA_EMAIL=$(python3 -c "import json;print(json.load(open('wallet-certs/google-wallet-sa.json'))['client_email'])") \
GOOGLE_WALLET_SA_PRIVATE_KEY="$(python3 -c "import json;print(json.load(open('wallet-certs/google-wallet-sa.json'))['private_key'])")" \
WALLET_BRAND_NAME="Rogob" \
npm run wallet:google-class
```

Дальше те же значения прописываются в systemd-юнит (шаг 5) — и кнопка
«Сохранить в Google Wallet» на карте становится активной.

## Шаг 4-старый. Google Wallet вручную (справочно)

1. https://goo.gle/wallet-console — войти рабочим Google-аккаунтом.
2. Public business name: **Unisim-Soft SRL**
3. Принять условия Google Wallet API → «Create a pass» → «Build your first pass».
   Появится **Issuer ID** (19 цифр) — записать.
4. https://console.cloud.google.com → создать проект → включить **Google Wallet API**.
5. IAM → Service Accounts → создать сервис-аккаунт → Keys → **Add key → JSON** → скачать.
6. Вернуться в Wallet Console → Users → добавить `client_email` из JSON с ролью **Developer**.
7. Создать шаблон карты:
   ```bash
   cd loyalty-platform
   GOOGLE_WALLET_ISSUER_ID=<19 цифр> \
   GOOGLE_WALLET_SA_EMAIL=<client_email из JSON> \
   GOOGLE_WALLET_SA_PRIVATE_KEY="<private_key из JSON>" \
   WALLET_BRAND_NAME="Rogob" \
   npm run wallet:google-class
   ```
8. Когда программа выйдет на реальных покупателей — запросить **production access**
   в Google Wallet API Dashboard (до этого карты сохраняются только у тестовых аккаунтов).

---

## Шаг 5. Включение на сервере

Полученные значения добавляются в юнит платформы:

```bash
ssh -i ~/Downloads/ssh-key-2024-10-06.key ubuntu@92.5.3.187
sudo nano /etc/systemd/system/myloyalwallet.service    # вставить строки Environment=
sudo systemctl daemon-reload && sudo systemctl restart myloyalwallet
```

Проверка, что заработало:

```bash
curl -I https://nufarul.eminescu.md/myloyalwalletcard/api/wallet/apple/<код-карты>
# → Content-Type: application/vnd.apple.pkpass  (сейчас отдаёт 503 без сертификатов)
```

Кнопки на веб-карте активируются автоматически — менять код не требуется.

---

## Что уже сделано с нашей стороны

| Готово | Где |
|---|---|
| Выпуск карт Google Wallet (подписанная ссылка) | `src/lib/wallet.ts` |
| Выпуск `.pkpass` с подписью PKCS#7 | `src/app/api/wallet/apple/[code]/route.ts` |
| Кнопки на карте с автоопределением готовности | `src/app/card/[code]/page.tsx` |
| Запрос на сертификат Apple | `wallet-certs/pass.csr` ✅ создан |
| Конвертация сертификатов в переменные | `npm run wallet:apple-pem` |
| Создание шаблона карты Google | `npm run wallet:google-class` |

Ожидание только внешнее: D-U-N-S → членство Apple → сертификат.
Google можно запускать в любой момент.
