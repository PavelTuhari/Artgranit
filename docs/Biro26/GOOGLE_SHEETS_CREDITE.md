# Синхронизация кредитных документов с Google Sheets — параметры подключения

Файл для передачи в Gemini: по нему нужно **создать сервисный аккаунт Google и
тестовую таблицу**, а обратно вернуть данные, перечисленные в разделе
[«Что нужно вернуть»](#что-нужно-вернуть).

Модуль: Biro26 → кредитные документы (`TMDB_CREDITE_M` / `TMDB_CREDITE_D`,
представления `VMDB_CREDITE_M` / `VMDB_CREDITE_D`).
Страница в бэк-офисе: `/UNA.md/orasldev/biro26-credite-docs`.

---

## 1. Что синхронизируем

Односторонняя выгрузка **из Oracle в Google Sheets** (ERP — источник истины;
правки в таблице обратно не заливаются).

| Лист таблицы | Источник | Строк | Обновление |
|---|---|---|---|
| `Credite` | `VMDB_CREDITE_M` — шапки документов | до ~5000 | полная перезапись листа |
| `Credite_linii` | `VMDB_CREDITE_D` — строки документов | до ~20000 | полная перезапись листа |

### Колонки листа `Credite`

`COD`, `NRMANUAL`, `DATAMANUAL`, `ORDER_NRMANUAL`, `CLIENT_COD`, `CLIENT_NAME`,
`NNP`, `IDNP`, `PHONE`, `ADRESA`, `BIRTH_DATE`, `ORG_ID`, `ORG_NAME`,
`PLAN_NAME`, `MONTHS`, `AVANS`, `AMOUNT`, `CREDIT_PRICE`, `MONTHLY`,
`PROVIDER_CODE`, `EXT_REF`, `API_STATUS`, `REQ_ID`, `LINES`, `CREATED`

### Колонки листа `Credite_linii`

`NRDOC`, `COD1`, `SC`, `CODVECHI`, `DENUMIREA`, `UM`, `CANT`, `PRET`,
`PRET_CREDIT`, `SUMA`, `TXTCOMENT`

> **Персональные данные.** `IDNP` хранится в маскированном виде (`09*******58`),
> когда заявка пришла через API кредитора. `PHONE`, `ADRESA`, `BIRTH_DATE` —
> открытым текстом, поэтому таблица **не должна** быть публичной: доступ только
> по сервисному аккаунту и явно указанным адресам.

---

## 2. Способ подключения

**Google Sheets API v4 + сервисный аккаунт (JWT, без OAuth-консента.)**
Выбран потому, что синхронизация идёт с сервера без участия человека.

- API: `https://sheets.googleapis.com/v4/spreadsheets`
- Scope: `https://www.googleapis.com/auth/spreadsheets`
- Аутентификация: сервисный аккаунт, ключ JSON, подпись JWT `RS256`,
  обмен на access token через `https://oauth2.googleapis.com/token`
- Метод записи: `spreadsheets.values.update` (`valueInputOption=RAW`)
  с предварительным `spreadsheets.values.clear` по диапазону листа
- Библиотеки: только `requests` + стандартный `cryptography` (уже в venv);
  без `gspread` и `google-api-python-client`

### Что нужно создать на стороне Google

1. Проект в Google Cloud (название на ваше усмотрение, например `officeplus-erp`).
2. Включить **Google Sheets API** в этом проекте.
3. Сервисный аккаунт, например `biro26-credite@<project>.iam.gserviceaccount.com`.
4. Ключ к нему в формате **JSON**.
5. Google-таблицу с двумя листами: `Credite` и `Credite_linii`.
6. Дать сервисному аккаунту право **«Редактор»** на эту таблицу
   (кнопка «Поделиться» → вставить email сервисного аккаунта).

---

## 3. Что нужно вернуть

Ответ от Gemini должен содержать ровно эти значения:

```
GSHEET_SPREADSHEET_ID   = <id таблицы из её URL: docs.google.com/spreadsheets/d/ЭТО/edit>
GSHEET_SHEET_MASTER     = Credite
GSHEET_SHEET_DETAIL     = Credite_linii
GSHEET_SA_EMAIL         = <...>@<project>.iam.gserviceaccount.com
GSHEET_SA_PRIVATE_KEY   = -----BEGIN PRIVATE KEY-----\n…\n-----END PRIVATE KEY-----\n
GSHEET_SA_KEY_ID        = <private_key_id из JSON>
GSHEET_PROJECT_ID       = <project_id из JSON>
```

Проще всего — приложить **файл ключа JSON целиком**: в нём уже есть
`client_email`, `private_key`, `private_key_id`, `project_id`.

Плюс:

- ссылка на созданную **тестовую** таблицу;
- подтверждение, что сервисный аккаунт добавлен в неё как редактор.

---

## 4. Куда это попадёт в проекте

Реквизиты **не хранятся в git**. Они лягут в те же нормализованные таблицы
настроек, что и кредитные провайдеры (`TMS_CREDITE_PROVIDER_PARAM`,
секретные значения помечаются `IS_SECRET='1'` и в UI показываются маской),
либо в `.env` production-сервера как `GSHEET_*`.

Тестовый и боевой аккаунт — **разные**: тестовая таблица нужна, чтобы
проверить выгрузку, не трогая рабочие данные.

---

## 5. Проверка после подключения

1. В бэк-офисе `/UNA.md/orasldev/biro26-credite-docs` → кнопка «Sincronizare Google Sheets».
2. В листе `Credite` появляется столько же строк, сколько в гриде мастера.
3. Выбранный документ в гриде detail совпадает со строками `Credite_linii`
   по `NRDOC`.
4. `curl -I https://nufarul.eminescu.md/login` → `200` (обязательная проверка
   production после любых изменений, см. `CLAUDE.md`).

## result

https://aistudio.google.com/apps/7e61c522-b6ba-4e30-8fb5-9931555e3dc7?showPreview=true&showAssistant=true

https://ai.studio/apps/7e61c522-b6ba-4e30-8fb5-9931555e3dc7


GSHEET_SPREADSHEET_ID   = 1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms
GSHEET_SHEET_MASTER     = Credite
GSHEET_SHEET_DETAIL     = Credite_linii
GSHEET_SA_EMAIL         = biro26-credite@officeplus-erp.iam.gserviceaccount.com
GSHEET_SA_PRIVATE_KEY   = -----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC8x1...\n-----END PRIVATE KEY-----
GSHEET_SA_KEY_ID        = 9f8e7d6c5b4a3f2e1d0c9b8a7f6e5d4c
GSHEET_PROJECT_ID       = officeplus-erp
