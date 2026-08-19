-- ============================================================
-- PECO: демо-станция (AZS-001) для локальной разработки/UAT.
--
-- ЭТО ДЕМО-ДАННЫЕ. НЕ ЗАПУСКАТЬ НА PRODUCTION.
--
-- Вставляет фиктивную станцию, резервуары, колонки, пистолеты, двух
-- сотрудников с заведомо нерабочим PIN и стартовые цены. На боевой сети
-- 46 реальных станций это создаст лишнюю 47-ю станцию, которой не должно
-- существовать.
--
-- Этот файл НЕ входит в безусловный список deploy_oracle_objects.py и
-- запускается ТОЛЬКО вручную, только на dev/UAT-схеме:
--
--     python deploy_oracle_objects.py --only 105_peco_demo_station
--
-- Не идемпотентен: уникальный индекс на PECO_STATIONS.CODE ('AZS-001')
-- не даст выполнить файл повторно на той же схеме — это осознанный выбор,
-- чтобы повторный запуск был громкой ошибкой, а не тихим дублированием.
-- ============================================================

INSERT INTO PECO_STATIONS (ID, CODE, NAME, ADDRESS, REGION)
VALUES (PECO_STATIONS_SEQ.NEXTVAL, 'AZS-001', 'АЗС №1 Кишинёв-Центр', 'бул. Штефан чел Маре 1', 'Кишинёв');

INSERT INTO PECO_TANKS (ID, STATION_ID, GRADE_CODE, CODE, CAPACITY_L, CURRENT_L, MIN_ALARM_L)
SELECT PECO_TANKS_SEQ.NEXTVAL, s.ID, g.CODE, 'T-' || g.CODE, 20000, 12000, 2000
  FROM PECO_STATIONS s CROSS JOIN PECO_REF_FUEL_GRADES g
 WHERE s.CODE = 'AZS-001';

INSERT INTO PECO_PUMPS (ID, STATION_ID, CODE, SELF_SERVICE)
SELECT PECO_PUMPS_SEQ.NEXTVAL, ID, 'P-1', 1 FROM PECO_STATIONS WHERE CODE = 'AZS-001';
INSERT INTO PECO_PUMPS (ID, STATION_ID, CODE, SELF_SERVICE)
SELECT PECO_PUMPS_SEQ.NEXTVAL, ID, 'P-2', 0 FROM PECO_STATIONS WHERE CODE = 'AZS-001';

-- По одному пистолету каждого вида топлива на первой колонке.
-- STATION_ID заполняется явно: составные внешние ключи не дают привязать
-- пистолет к колонке одной станции и резервуару другой.
INSERT INTO PECO_NOZZLES (ID, PUMP_ID, TANK_ID, STATION_ID, GRADE_CODE, CODE, METER_TOTAL)
SELECT PECO_NOZZLES_SEQ.NEXTVAL, p.ID, t.ID, p.STATION_ID, t.GRADE_CODE,
       'N-' || t.GRADE_CODE, 0
  FROM PECO_PUMPS p
  JOIN PECO_TANKS t ON t.STATION_ID = p.STATION_ID
 WHERE p.CODE = 'P-1';

-- PIN_HASH заведомо невалиден: демо-сотрудники не должны иметь рабочий PIN.
-- Реальный PIN задаётся через бэк-офис, который считает PBKDF2 с новой солью.
INSERT INTO PECO_EMPLOYEES (ID, STATION_ID, FULL_NAME, ROLE_CODE, PIN_SALT, PIN_HASH)
SELECT PECO_EMPLOYEES_SEQ.NEXTVAL, ID, 'Оператор Демо', 'ATTENDANT',
       'NO_SALT_SET', 'NO_PIN_SET'
  FROM PECO_STATIONS WHERE CODE = 'AZS-001';
INSERT INTO PECO_EMPLOYEES (ID, STATION_ID, FULL_NAME, ROLE_CODE, PIN_SALT, PIN_HASH)
SELECT PECO_EMPLOYEES_SEQ.NEXTVAL, ID, 'Менеджер Демо', 'MANAGER',
       'NO_SALT_SET', 'NO_PIN_SET'
  FROM PECO_STATIONS WHERE CODE = 'AZS-001';

INSERT INTO PECO_PRICES (ID, STATION_ID, GRADE_CODE, PRICE)
SELECT PECO_PRICES_SEQ.NEXTVAL, s.ID, g.CODE,
       CASE g.CODE WHEN 'A92' THEN 22.50 WHEN 'A95' THEN 23.90
                   WHEN 'A98' THEN 26.40 ELSE 21.80 END
  FROM PECO_STATIONS s CROSS JOIN PECO_REF_FUEL_GRADES g
 WHERE s.CODE = 'AZS-001';

COMMIT;
