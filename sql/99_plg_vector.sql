-- ============================================================
-- Планограммы: векторный контур ИИ-мониторинга (Oracle AI Database 26ai)
--
-- Альтернативный базовый вариант мониторинга: вместо порогов по каждому
-- признаку — ВЕКТОР ПОВЕДЕНИЯ SKU. Двенадцать нормированных признаков
-- (уровни спроса, волатильность, тренд, подъём выходных, промо-аплифт,
-- OOS, покрытие, списания) складываются в колонку типа VECTOR, и дальше
-- работают две вещи, которых пороговые детекторы не умеют:
--
--   1. ВЫБРОС СРЕДИ СОСЕДЕЙ (сигнал peer_outlier): SKU, чей вектор далёк
--      от товаров СВОЕЙ ЖЕ категории в том же магазине. Пороговый детектор
--      смотрит на каждый признак отдельно; векторный ловит товар, у которого
--      каждый признак по отдельности «в норме», а сочетание — аномально.
--      Расстояния считает сама база: VECTOR_DISTANCE(..., COSINE).
--
--   2. ПОХОЖИЕ SKU (API /api/plg/ai/similar): поиск ближайших соседей
--      по HNSW-индексу — «какие товары ведут себя как этот». Применения:
--      прогноз для новинки по поведению аналогов, поиск кандидатов
--      на ту же промо-механику, ранняя диагностика «поведение стало
--      как у товара X перед его провалом».
--
-- Векторы лежат в той же таблице и той же транзакции, что и признаки, —
-- никакой второй базы и синхронизации. Это и есть практический аргумент
-- Oracle 26ai из методички, теперь работающий в системе.
--
-- Расчёт вектора: models/plg_ai_monitor.py (_behavior_vector).
-- Префикс объектов: PLG_
-- ============================================================

-- Колонка вектора поведения: 12 признаков, FLOAT32.
-- Guard-блок — файл рассчитан на повторный запуск.
DECLARE
  v_n NUMBER;
BEGIN
  SELECT COUNT(*) INTO v_n FROM USER_TAB_COLUMNS
   WHERE TABLE_NAME = 'PLG_AI_FEATURES' AND COLUMN_NAME = 'EMB';
  IF v_n = 0 THEN
    EXECUTE IMMEDIATE 'ALTER TABLE PLG_AI_FEATURES ADD (EMB VECTOR(12, FLOAT32))';
  END IF;
END;
/

-- Новый тип сигнала peer_outlier: пересоздаём check-констрейнт
DECLARE
  v_n NUMBER;
BEGIN
  SELECT COUNT(*) INTO v_n FROM USER_CONSTRAINTS
   WHERE CONSTRAINT_NAME = 'CHK_PLG_AIS_TYPE';
  IF v_n > 0 THEN
    EXECUTE IMMEDIATE 'ALTER TABLE PLG_AI_SIGNALS DROP CONSTRAINT CHK_PLG_AIS_TYPE';
  END IF;
  EXECUTE IMMEDIATE q'[ALTER TABLE PLG_AI_SIGNALS ADD CONSTRAINT CHK_PLG_AIS_TYPE
    CHECK (SIGNAL_TYPE IN ('oos_risk','spike','drop','waste_risk','bias_drift',
                           'dead_stock','peer_outlier'))]';
END;
/

-- HNSW-индекс для поиска ближайших соседей (FETCH APPROX ... ROWS ONLY).
-- Выбросы считаются точным VECTOR_DISTANCE внутри категории — там пар мало;
-- индекс нужен интерактивному «найди похожие», где сравнение идёт со всеми.
DECLARE
  v_n NUMBER;
BEGIN
  SELECT COUNT(*) INTO v_n FROM USER_INDEXES WHERE INDEX_NAME = 'IX_PLG_AI_FEAT_EMB';
  IF v_n = 0 THEN
    EXECUTE IMMEDIATE 'CREATE VECTOR INDEX IX_PLG_AI_FEAT_EMB ON PLG_AI_FEATURES (EMB) '
                   || 'ORGANIZATION INMEMORY NEIGHBOR GRAPH DISTANCE COSINE';
  END IF;
END;
/
