# Интерфейс UNA: что проверено в боевой базе

Кусок C (документы и согласование) был заблокирован тем, что состав
`TMDB_DOCS_ADD`/`TMDB_DOCS_LOG`, выдача `TMDB_DOCS.COD`, кодировка
`DOCCOLOR` и вызов `UN$GFC` в опубликованной документации UNA не раскрыты.
ТЗ платформы (`seo-platform/db/oracle/README.md`) выписало по ним
предположения и потребовало сверки до первой установки.

Сверка сделана **25.08.2026 прямо в боевой базе** `OFFICEPLUS`
(`orange.una.md:4024/cloudbd.world`, Oracle 11.2.0.4) — чтением словаря
данных и исходников триггеров и пакетов. Ниже факты, а не предположения.

> Три предположения из четырёх не подтвердились. Код, написанный по ТЗ
> без этой сверки, писал бы мусор в боевой учёт. Поэтому таблица ниже
> заменяет соответствующий раздел ТЗ.

## Сводка

| Что | Предполагало ТЗ | Что в базе |
|---|---|---|
| `TMDB_DOCS_ADD` | колонки `CAMP_CODE`, `RUN_ID`, `PLAYBOOK_SHA`, `NOTE` | **не совпало** — таких колонок нет |
| `TMDB_DOCS_LOG` | `COD`, `USERID`, `DATAOPER`, `STATUS_FROM`, `STATUS_TO`, `NOTE` | **не совпало** — это журнал «старое/новое», ведётся триггером |
| `TMDB_DOCS.COD` | `MAX(COD)+1` | **опасно** — есть последовательность и триггер |
| `DOCCOLOR` | `NUMBER`: 1 жёлтый, 2 серый, 3 голубой | **не совпало** — `VARCHAR2(1)`, другие значения и другой смысл |
| `UN$GFC` | существует, интерфейс неизвестен | **подтверждён**, интерфейс снят |

## 1. Выдача номера документа

`TMDB_DOCS.COD` выдаёт триггер `TRIG_BFINS_TMDB_DOCS` из последовательности
`ID_TMDB_DOCS`:

```sql
IF :NEW.COD IS NULL THEN
  SELECT ID_TMDB_DOCS.NEXTVAL INTO :NEW.COD FROM DUAL;
END IF;
```

**Как работать:** вставлять документ с `COD = NULL` и забирать номер
`RETURNING COD INTO`. Считать `MAX(COD)+1` нельзя: при одновременной работе
двух сессий это даёт дубль ключа, а на 11g ещё и обходит остальную логику
того же триггера.

Тот же триггер задаёт ещё две вещи, которые приложение не должно трогать:

```sql
IF :NEW.ISGFC IS NULL THEN :NEW.ISGFC := 0; END IF;
IF :NEW.USERID IS NULL THEN :NEW.USERID := ATOI(GET_ENV('PARAM_USERID')); END IF;
```

**Следствие:** авторство документа берётся из сессионного параметра
`PARAM_USERID`. Если модуль его не выставит, документы уйдут в учёт без
автора либо с чужим. Это же ломает требование ТЗ «автор не может быть
согласующим»: без корректного `USERID` правило не на чем держать.

## 2. `TMDB_DOCS_ADD` — фактический состав

| Колонка | Тип |
|---|---|
| `COD` | `NUMBER` NOT NULL |
| `ATTR_CLNRDOCS` | `VARCHAR2(5)` |
| `TXTCOMMENT` | `VARCHAR2(4000)` |
| `DATA_SLR_CALC` | `DATE` |
| `STATE_ERROR` | `NUMBER` |
| `STATE_ADMIN_OK` | `NUMBER` |
| `FIRST_USERID` | `NUMBER` |
| `PARENT_NRDOC` | `NUMBER` |
| `RECALC_NRDOC` | `NUMBER` |
| `RECALC_TIP` | `NUMBER` |
| `TEST_COD` | `VARCHAR2(30)` |
| `SOLD_TIME` | `DATE` |
| `ALT_COLOR` | `VARCHAR2(1)` |

Полей `CAMP_CODE`, `RUN_ID`, `PLAYBOOK_SHA`, `NOTE` нет. Ближайший по смыслу —
`TXTCOMMENT`, но это свободный текст на 4000 символов, а не ключ, по которому
можно связать документ с кампанией.

**Вывод:** привязку документа к кампании и к запуску AI-сессии складывать
в `TMDB_DOCS_ADD` нельзя. Для этого уже есть `YSEO_XREF`
(`ENTITY_TYPE`, `ENTITY_COD` → `ERP_DOC_COD`, `ERP_NRMANUAL`) — она и должна
стать местом связи. Добавлять свои колонки в `TMDB_DOCS_ADD` не нужно:
это чужая таблица, её трогают штатные триггеры и обновления UNA.

## 3. `TMDB_DOCS_LOG` — фактический состав

Это **журнал изменений «старое/новое»**, а не журнал смены статусов:

`NRDOC`, `NRORD`, `DATA`, `USERID`, `USERNAME`,
`OLD_DATA`/`NEW_DATA`, `OLD_NRSET`/`NEW_NRSET`, `OLD_SYSFID`/`NEW_SYSFID`,
`OLD_AT1`/`NEW_AT1`, `OLD_NRMANUAL`/`NEW_NRMANUAL`, `OLD_USERID`/`NEW_USERID`,
`OLD_AT2`/`NEW_AT2`, `OLD_AT3`/`NEW_AT3`, `OLD_F`/`NEW_F`, `OLD_M`/`NEW_M`,
`OLD_DIV`/`NEW_DIV`, `OLD_STATUS`/`NEW_STATUS`,
`ACTION`, `TERMINAL`, `MACHINE`, `OS_USER`, `IP_ADDR`, `MODULE`.

Заполняется триггером `TMDB_DOCS_TRLOG` (`AFTER INSERT OR UPDATE OR DELETE`)
автоматически.

**Вывод:** писать в `TMDB_DOCS_LOG` руками не нужно и вредно — база ведёт его
сама. История согласования маркетинговых документов должна жить в собственном
журнале контура (`YSEO_EVENT_LOG`), а `TMDB_DOCS_LOG` использовать только для
чтения: пара `OLD_STATUS`/`NEW_STATUS` как раз даёт историю движения документа.

## 4. `DOCCOLOR` — тип и смысл

Тип — `VARCHAR2(1)`, не `NUMBER`. Фактические значения в базе:

| Значение | Строк |
|---|---|
| `` ` `` | 183 |
| `NULL` | 8 |
| `<` | 2 |

Ставится триггером `TRG_DOCS_COLOR` (`BEFORE INSERT OR UPDATE`, срабатывает
только при `AT1 IS NULL` и пустом контексте `envun4.dont_fire_trigger`):

```sql
SELECT '-' INTO :NEW.DOCCOLOR FROM VMDB_DOCS_ADD
WHERE COD = :NEW.COD AND RECALC_NRDOC IS NOT NULL AND NVL(RECALC_TIP,0) >= 0;
EXCEPTION WHEN NO_DATA_FOUND THEN
  SELECT '' INTO :NEW.DOCCOLOR FROM VMDB_CMI WHERE NRDOC = :NEW.COD AND ROWNUM = 1;
EXCEPTION WHEN NO_DATA_FOUND THEN
  :NEW.DOCCOLOR := '`';
```

То есть цвет означает **«пересчитан / есть проводки / ни то ни другое»**,
а вовсе не «черновик / на согласовании / утверждён».

**Вывод:** статус согласования на `DOCCOLOR` вешать нельзя — ни по типу,
ни по смыслу, ни по владению (значение перетирает чужой триггер).
Для маршрута согласования нужен собственный признак в контуре `YSEO_*`.

## 5. `UN$GFC` — подтверждён, интерфейс снят

Пакет существует и валиден (`OFFICEPLUS.UN$GFC`, версия 1.04 от 02.06.2009).
Публичная часть:

```sql
PROCEDURE GENERAREA_FCB   (inrdoc NUMBER, sSQL VARCHAR2);
PROCEDURE setDoc_UNGFC    (inrdoc NUMBER);
PROCEDURE setDoc_GFC      (inrdoc NUMBER);
PROCEDURE setDoc_Incorrect(inrdoc NUMBER, vIsGfc NUMBER DEFAULT -1);
PROCEDURE setDoc_Correct  (inrdoc NUMBER);
FUNCTION  getFunctIDsForGFC(inrdoc INTEGER) RETURN VARCHAR2;
PROCEDURE checkCont       (inCONT NUMBER);
PROCEDURE chkContSC       (vCont INT, vSC INT, vTipSC INT, vErrorGenerate INT := 3);
PROCEDURE chkContSCAll    (vCont INT, vSC1 INT, vSC0 INT, vSC2 INT, vErrorGenerate INT := 3);
PROCEDURE chkContCM       (vNrdoc INT, vErrorGenerate INT := 0);
```

Штатный порядок проведения — из живого кода схемы (`PKG_SALES`,
`PKG_ORDERS_DOCS`, `PKG_EDI`):

```sql
un$gfc.setDoc_GFC(v_nrdoc);
un$gfc.setDoc_Correct(v_nrdoc);
```

`vErrorGenerate` задаёт поведение проверок: `0` — сообщение, `1` —
предупреждение, `2` — исключение, `3`/`4` — мягко администратору и жёстко
остальным.

**Вывод:** предположение ТЗ подтвердилось. Проводки генерируются вызовом
`setDoc_GFC(nrdoc)` по настройкам самого документа, прямых `INSERT` в
`TMDB_CM` не нужно. Отказ ТЗ реализовывать проводки вручную был правильным.

## 6. Что осталось не выясненным

Это не «не посмотрел», а «в базе такого ответа нет» — здесь нужны решения
владельца учёта.

1. **Тип документа.** `TMDB_DOCS.TIPDOC` в этой базе пуст у всех 193
   документов, то есть тип различается не им, а комбинацией
   `TIP`/`SYSFID`/`AT1`. Какие значения должны стоять у маркетинговых
   документов (бюджет, кампания, акт, счёт) — вопрос настройки учёта.
2. **Нумерация `NRMANUAL`.** `UN$G$UTIL.TextIncrement` из ТЗ в схеме
   отсутствует: слова `TextIncrement` нет ни в одном исходнике. При этом
   `NRMANUAL` формируют пакеты `Y_AI_BIRO26`, `Y_AI_BIRO26_CREDITE`,
   `Y_INVENTORY_PKG`, `Z_BEFGCC_PK_PDFACTURA` — то есть у каждого контура
   своя нумерация. Какую взять маркетингу — решение, а не факт.
3. **План счетов.** Счета 712 / 521 / 261 в ТЗ взяты «по общей логике НСБУ».
   Рабочий план счетов предприятия нужно подтвердить отдельно; в контуре
   они меняются `UPDATE` в `YSEO_SETUP`, правки кода не требуют.
4. **Маршрут согласования.** Кто согласует маркетинговые документы и на
   каких суммах — организационное решение.

## 7. Как это меняет план куска C

- Связь документа с кампанией и запуском — через `YSEO_XREF`, а не через
  колонки в `TMDB_DOCS_ADD`.
- Статус согласования — собственный признак в контуре `YSEO_*`, `DOCCOLOR`
  не трогаем.
- История согласования — `YSEO_EVENT_LOG`; `TMDB_DOCS_LOG` читаем, но не пишем.
- Номер документа — вставка с `COD = NULL` и `RETURNING COD INTO`.
- Перед вставкой выставлять сессионный `PARAM_USERID`, иначе авторство
  документов будет неверным и правило «автор не согласует сам себя»
  окажется беспредметным.
- Проведение — `un$gfc.setDoc_GFC(nrdoc)` + `un$gfc.setDoc_Correct(nrdoc)`.

Пункты раздела 6 остаются входными данными: без них кусок C можно
спроектировать, но не запустить в боевой учёт.
