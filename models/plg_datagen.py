"""
Генератор тестового окружения данных сети магазинов для модуля «Планограммы».

Пять алгоритмов, запускаемых по отдельности или полным прогоном:

  network     сеть магазинов четырёх форматов с торговым залом
  assortment  ассортиментная матрица (SKU, цены, ABC, кратность заказа)
  events      акции, планограммы, задачи, уведомления
  demand      суточная история спроса — ядро окружения
  traffic     проходимость зон и дневные показатели магазина

Изоляция: всё пишется в именованный набор (PLG_DATASETS). Набор проставляется
на PLG_STORES.DATASET_ID и PLG_PRODUCTS.DATASET_ID, остальное достижимо через
магазин и удаляется каскадом. Набор DEMO защищён (IS_PROTECTED=1).

Воспроизводимость: весь случайный поток идёт из random.Random(seed) набора,
поэтому одинаковые (seed, параметры) дают идентичные данные.

Oracle-объекты: sql/84_plg_testdata.sql
"""
from __future__ import annotations

import json
import math
import os
import random
import sys
import threading
import time
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from models.database import DatabaseConnection

BATCH = 20000

# ==================== Профили форматов магазина ====================
# area — площадь зала, traffic — базовый суточный трафик,
# assortment_share — доля общей ассортиментной матрицы в магазине,
# checkouts — число касс.
STORE_FORMATS: Dict[str, Dict[str, Any]] = {
    'hyper':       {'area': (2400, 4200), 'traffic': (4200, 6800), 'assortment_share': 1.00, 'checkouts': (10, 16),
                    'ru': 'Гипермаркет', 'ro': 'Hipermarket',  'en': 'Hypermarket'},
    'super':       {'area': (900, 1600),  'traffic': (1800, 3200), 'assortment_share': 0.72, 'checkouts': (5, 8),
                    'ru': 'Супермаркет',  'ro': 'Supermarket',  'en': 'Supermarket'},
    'discounter':  {'area': (500, 900),   'traffic': (1100, 2100), 'assortment_share': 0.45, 'checkouts': (3, 5),
                    'ru': 'Дискаунтер',   'ro': 'Discounter',   'en': 'Discounter'},
    'convenience': {'area': (140, 380),   'traffic': (500, 1100),  'assortment_share': 0.30, 'checkouts': (2, 3),
                    'ru': 'Магазин у дома', 'ro': 'Magazin de proximitate', 'en': 'Convenience store'},
}

CITIES = [
    ('Chișinău', 'Кишинёв', 'Chișinău', 'Chisinau', 'MD-CHS'),
    ('Bălți',    'Бельцы',  'Bălți',    'Balti',    'MD-BLZ'),
    ('Cahul',    'Кагул',   'Cahul',    'Cahul',    'MD-CHL'),
    ('Orhei',    'Оргеев',  'Orhei',    'Orhei',    'MD-ORH'),
    ('Ungheni',  'Унгены',  'Ungheni',  'Ungheni',  'MD-UNG'),
    ('Comrat',   'Комрат',  'Comrat',   'Comrat',   'MD-CMR'),
]

STREETS = [
    ('ул. Штефан чел Маре', 'str. Ștefan cel Mare', 'Stefan cel Mare St.'),
    ('бул. Дачия',          'bd. Dacia',            'Dacia Blvd.'),
    ('ул. Индепенденцей',   'str. Independenței',   'Independentei St.'),
    ('ул. Мирча чел Бэтрын','str. Mircea cel Bătrân','Mircea cel Batran St.'),
    ('бул. Московский',     'bd. Moscova',          'Moscova Blvd.'),
    ('ул. Каля Ешилор',     'str. Calea Ieșilor',   'Calea Iesilor St.'),
]

# ==================== Шаблон торгового зала ====================
# Раскладка повторяет геометрию демо-магазина: верхний ряд отделов,
# левая стена с холодильным оборудованием, касса, вход, служебные помещения.
ZONE_TEMPLATE = [
    # (code, zone_type, category_code, x, y, w, h, color, sort)
    ('produce', 'dept', 'produce', 162,   8,  72, 55, '#16a34a', 1),
    ('drinks',  'dept', 'drinks',  242,   8,  72, 55, '#2563eb', 2),
    ('snacks',  'dept', 'snacks',  322,   8,  72, 55, '#d97706', 3),
    ('grocery', 'dept', 'grocery', 402,   8,  72, 55, '#7c3aed', 4),
    ('health',  'dept', 'health',  482,   8,  72, 55, '#0d9488', 5),
    ('coffee',  'dept', 'coffee',  562,   8,  72, 55, '#854d0e', 6),
    ('kids',    'dept', 'kids',    642,   8,  72, 55, '#db2777', 7),
    ('chem',    'dept', 'chem',    718,   8,  55, 55, '#475569', 8),
    ('bakery',  'dept', 'bakery',    8,  90, 130, 52, '#c2410c', 9),
    ('meat',    'dept', 'meat',      8, 152, 130, 52, '#991b1b', 10),
    ('fish',    'dept', 'fish',      8, 214, 130, 52, '#1d4ed8', 11),
    ('dairy',   'dept', 'dairy',     8, 276, 130, 52, '#0369a1', 12),
    ('frozen',  'dept', 'frozen',    8, 338, 130, 52, '#4338ca', 13),
    ('storage', 'storage', None,   718,  72,  55, 80, '#1a2a40', 14),
    ('service', 'service', None,   718, 162,  55, 55, '#1a2a40', 15),
    ('wc',      'wc',      None,   718, 228,  55, 45, '#1a2a40', 16),
    ('alcohol', 'dept', 'alcohol', 718, 283,  55, 80, '#6d28d9', 17),
    ('promo',   'promo_island', None, 162, 356, 70,  50, '#c2410c', 18),
    ('checkout','checkout',    None, 460, 348, 250, 100, '#f97316', 19),
    ('entrance','entrance',    None, 176, 435,  42,  22, '#16a34a', 20),
]

# Малые форматы не держат весь набор отделов
FORMAT_ZONE_LIMIT = {
    'hyper':       None,   # все
    'super':       {'produce','drinks','snacks','grocery','coffee','chem','bakery','meat','dairy','frozen',
                    'alcohol','storage','service','wc','promo','checkout','entrance'},
    'discounter':  {'produce','drinks','snacks','grocery','bakery','dairy','frozen','alcohol',
                    'storage','wc','promo','checkout','entrance'},
    'convenience': {'drinks','snacks','grocery','bakery','dairy','alcohol','storage','checkout','entrance'},
}

# Доля категории в ассортименте и её недельно-сезонный характер.
# yearly_phase — день года пика продаж; yearly_amp — глубина годовой волны.
CATEGORY_PROFILE = {
    'produce': {'share': 0.13, 'yearly_phase': 220, 'yearly_amp': 0.32, 'price': (8, 90),   'shelf_life': 5},
    'drinks':  {'share': 0.12, 'yearly_phase': 200, 'yearly_amp': 0.38, 'price': (7, 120),  'shelf_life': 240},
    'snacks':  {'share': 0.11, 'yearly_phase': 350, 'yearly_amp': 0.18, 'price': (9, 95),   'shelf_life': 120},
    'dairy':   {'share': 0.10, 'yearly_phase': 180, 'yearly_amp': 0.14, 'price': (10, 110), 'shelf_life': 14},
    'grocery': {'share': 0.13, 'yearly_phase': 20,  'yearly_amp': 0.12, 'price': (12, 180), 'shelf_life': 365},
    'health':  {'share': 0.05, 'yearly_phase': 15,  'yearly_amp': 0.22, 'price': (25, 220), 'shelf_life': 180},
    'coffee':  {'share': 0.05, 'yearly_phase': 15,  'yearly_amp': 0.25, 'price': (35, 350), 'shelf_life': 365},
    'kids':    {'share': 0.05, 'yearly_phase': 250, 'yearly_amp': 0.16, 'price': (30, 320), 'shelf_life': 365},
    'chem':    {'share': 0.06, 'yearly_phase': 90,  'yearly_amp': 0.10, 'price': (20, 260), 'shelf_life': 365},
    'bakery':  {'share': 0.05, 'yearly_phase': 350, 'yearly_amp': 0.12, 'price': (6, 60),   'shelf_life': 2},
    'meat':    {'share': 0.05, 'yearly_phase': 350, 'yearly_amp': 0.20, 'price': (45, 280), 'shelf_life': 7},
    'fish':    {'share': 0.03, 'yearly_phase': 350, 'yearly_amp': 0.24, 'price': (50, 320), 'shelf_life': 5},
    'frozen':  {'share': 0.04, 'yearly_phase': 200, 'yearly_amp': 0.20, 'price': (28, 190), 'shelf_life': 180},
    'alcohol': {'share': 0.03, 'yearly_phase': 355, 'yearly_amp': 0.30, 'price': (45, 400), 'shelf_life': 730},
}

# Недельный профиль торговли: пятница-суббота — пик, вторник — провал
WEEKDAY_PROFILE = [0.88, 0.84, 0.90, 0.97, 1.28, 1.42, 1.05]  # Пн..Вс

# Названия SKU собираются из основы + признака, чтобы 400 позиций
# читались как настоящая матрица, а не «Товар 137».
SKU_BASE = {
    'produce': [('Яблоки', 'Mere', 'Apples'), ('Бананы', 'Banane', 'Bananas'), ('Томаты', 'Roșii', 'Tomatoes'),
                ('Огурцы', 'Castraveți', 'Cucumbers'), ('Картофель', 'Cartofi', 'Potatoes'),
                ('Морковь', 'Morcovi', 'Carrots'), ('Виноград', 'Struguri', 'Grapes'), ('Груши', 'Pere', 'Pears')],
    'drinks':  [('Вода', 'Apă', 'Water'), ('Сок', 'Suc', 'Juice'), ('Лимонад', 'Limonadă', 'Lemonade'),
                ('Энергетик', 'Energizant', 'Energy drink'), ('Квас', 'Cvas', 'Kvass'), ('Чай холодный', 'Ceai rece', 'Iced tea')],
    'snacks':  [('Чипсы', 'Chipsuri', 'Chips'), ('Шоколад', 'Ciocolată', 'Chocolate'), ('Печенье', 'Biscuiți', 'Cookies'),
                ('Орехи', 'Nuci', 'Nuts'), ('Сухарики', 'Crutoane', 'Croutons'), ('Конфеты', 'Bomboane', 'Candy')],
    'dairy':   [('Молоко', 'Lapte', 'Milk'), ('Йогурт', 'Iaurt', 'Yogurt'), ('Сыр', 'Cașcaval', 'Cheese'),
                ('Кефир', 'Chefir', 'Kefir'), ('Сметана', 'Smântână', 'Sour cream'), ('Творог', 'Brânză de vaci', 'Cottage cheese')],
    'grocery': [('Макароны', 'Paste', 'Pasta'), ('Рис', 'Orez', 'Rice'), ('Масло подсолнечное', 'Ulei', 'Sunflower oil'),
                ('Сахар', 'Zahăr', 'Sugar'), ('Мука', 'Făină', 'Flour'), ('Гречка', 'Hrișcă', 'Buckwheat'),
                ('Соль', 'Sare', 'Salt'), ('Консервы', 'Conserve', 'Canned food')],
    'health':  [('Мюсли', 'Muesli', 'Muesli'), ('Протеин батончик', 'Baton proteic', 'Protein bar'),
                ('Отруби', 'Tărâțe', 'Bran'), ('Семена чиа', 'Semințe chia', 'Chia seeds')],
    'coffee':  [('Кофе зерновой', 'Cafea boabe', 'Coffee beans'), ('Кофе молотый', 'Cafea măcinată', 'Ground coffee'),
                ('Чай чёрный', 'Ceai negru', 'Black tea'), ('Чай зелёный', 'Ceai verde', 'Green tea')],
    'kids':    [('Подгузники', 'Scutece', 'Diapers'), ('Пюре детское', 'Piure pentru copii', 'Baby puree'),
                ('Смесь молочная', 'Formulă de lapte', 'Baby formula'), ('Салфетки влажные', 'Șervețele umede', 'Wet wipes')],
    'chem':    [('Гель для стирки', 'Detergent lichid', 'Laundry gel'), ('Порошок', 'Detergent praf', 'Washing powder'),
                ('Средство для посуды', 'Detergent vase', 'Dish soap'), ('Освежитель', 'Odorizant', 'Air freshener')],
    'bakery':  [('Хлеб белый', 'Pâine albă', 'White bread'), ('Хлеб ржаной', 'Pâine de secară', 'Rye bread'),
                ('Батон', 'Franzelă', 'Baguette'), ('Круассан', 'Croissant', 'Croissant')],
    'meat':    [('Филе куриное', 'Piept de pui', 'Chicken breast'), ('Свинина', 'Carne de porc', 'Pork'),
                ('Говядина', 'Carne de vită', 'Beef'), ('Колбаса', 'Salam', 'Sausage'), ('Фарш', 'Carne tocată', 'Minced meat')],
    'fish':    [('Сёмга', 'Somon', 'Salmon'), ('Скумбрия', 'Macrou', 'Mackerel'), ('Сельдь', 'Hering', 'Herring')],
    'frozen':  [('Пицца замороженная', 'Pizza congelată', 'Frozen pizza'), ('Пельмени', 'Colțunași', 'Dumplings'),
                ('Овощная смесь', 'Amestec de legume', 'Vegetable mix'), ('Мороженое', 'Înghețată', 'Ice cream')],
    'alcohol': [('Вино красное', 'Vin roșu', 'Red wine'), ('Вино белое', 'Vin alb', 'White wine'),
                ('Пиво', 'Bere', 'Beer'), ('Коньяк', 'Coniac', 'Cognac')],
}

SKU_VARIANT = [
    ('0.5 л', '0.5 l', '0.5 l'), ('1 л', '1 l', '1 l'), ('1.5 л', '1.5 l', '1.5 l'), ('2 л', '2 l', '2 l'),
    ('200 г', '200 g', '200 g'), ('330 г', '330 g', '330 g'), ('500 г', '500 g', '500 g'), ('1 кг', '1 kg', '1 kg'),
    ('кг', 'kg', 'kg'), ('уп.', 'pachet', 'pack'),
]

BRANDS = ['Local', 'Alfa', 'Nistru', 'Codru', 'Orhei-Vit', 'JLC', 'Bucuria', 'Franzeluța',
          'Floris', 'Cricova', 'Purcari', 'Vitanta', 'Aroma', 'Natur Bravo']

SUPPLIERS = ['Metro Cash & Carry', 'Trans-Oil Logistic', 'Rogob Distribution', 'Vinaria Nord',
             'Baltic Food', 'AgroStoc', 'DistriMol']

PROMO_TEMPLATES = [
    ('discount', '-20%', 20, ('Скидка', 'Reducere', 'Discount')),
    ('discount', '-15%', 15, ('Скидка', 'Reducere', 'Discount')),
    ('discount', '-30%', 30, ('Суперцена', 'Super preț', 'Super price')),
    ('bundle',   '2+1',  33, ('Комплект', 'Pachet', 'Bundle')),
    ('gift',     'GIFT',  0, ('Подарок', 'Cadou', 'Gift')),
    ('price_lock','FIX',  0, ('Фиксация цены', 'Preț fix', 'Price lock')),
    ('loyalty',  'CARD', 12, ('По карте', 'Cu card', 'Loyalty')),
]


class GeneratorCancelled(Exception):
    """Прогон остановлен оператором из админки."""


class DataGenerator:
    """Генератор тестового окружения. Один экземпляр = один прогон."""

    # Активные прогоны: run_id -> DataGenerator (для отмены из админки)
    _active: Dict[int, "DataGenerator"] = {}
    _lock = threading.Lock()

    STAGES = ['network', 'assortment', 'events', 'demand', 'traffic']

    def __init__(self, run_id: int, dataset_id: int, params: Dict[str, Any], stages: List[str]):
        self.run_id = run_id
        self.dataset_id = dataset_id
        self.params = params
        self.stages = stages
        self.seed = int(params.get('seed') or 20260815)
        self.rnd = random.Random(self.seed)
        self.rows = 0
        self.cancelled = False
        self.conn = None
        self._t0 = time.time()

    # ==================== Публичный запуск ====================

    @staticmethod
    def launch(dataset_id: int, params: Dict[str, Any], stages: List[str],
               username: str) -> Dict[str, Any]:
        """Создаёт запись прогона и запускает генерацию в фоновом потоке."""
        stages = [s for s in (stages or DataGenerator.STAGES) if s in DataGenerator.STAGES]
        if not stages:
            return {"success": False, "error": "Не выбран ни один алгоритм генерации"}

        conn = DatabaseConnection.get_connection()
        try:
            cur = conn.cursor()
            run_id_var = cur.var(int)
            cur.execute(
                "INSERT INTO PLG_GEN_RUNS (DATASET_ID, ALGORITHM, PARAMS_JSON, STATUS, STAGE, USERNAME) "
                "VALUES (:p_ds, :p_algo, :p_params, 'running', :p_stage, :p_user) "
                "RETURNING ID INTO :p_id",
                {"p_ds": dataset_id,
                 "p_algo": 'full' if len(stages) == len(DataGenerator.STAGES) else ','.join(stages),
                 "p_params": json.dumps(params, ensure_ascii=False)[:2000],
                 "p_stage": stages[0], "p_user": username[:150], "p_id": run_id_var})
            conn.commit()
            run_id = int(run_id_var.getvalue()[0])
        finally:
            conn.close()

        gen = DataGenerator(run_id, dataset_id, params, stages)
        with DataGenerator._lock:
            DataGenerator._active[run_id] = gen
        thread = threading.Thread(target=gen._run, name=f"plg-datagen-{run_id}", daemon=True)
        thread.start()
        return {"success": True, "run_id": run_id, "dataset_id": dataset_id, "stages": stages}

    @staticmethod
    def cancel(run_id: int) -> Dict[str, Any]:
        with DataGenerator._lock:
            gen = DataGenerator._active.get(int(run_id))
        if not gen:
            return {"success": False, "error": "Прогон не найден среди активных"}
        gen.cancelled = True
        return {"success": True}

    # ==================== Внутренняя механика ====================

    def _check_cancel(self):
        if self.cancelled:
            raise GeneratorCancelled()

    def _progress(self, stage: str, pct: int):
        try:
            cur = self.conn.cursor()
            cur.execute(
                "UPDATE PLG_GEN_RUNS SET STAGE = :p_stage, PROGRESS_PCT = :p_pct, "
                "ROWS_WRITTEN = :p_rows WHERE ID = :p_id",
                {"p_stage": stage[:60], "p_pct": max(0, min(100, int(pct))),
                 "p_rows": self.rows, "p_id": self.run_id})
            self.conn.commit()
        except Exception:
            pass

    def _finish(self, status: str, message: str = ""):
        try:
            cur = self.conn.cursor()
            cur.execute(
                "UPDATE PLG_GEN_RUNS SET STATUS = :p_status, PROGRESS_PCT = :p_pct, "
                "ROWS_WRITTEN = :p_rows, DURATION_SEC = :p_dur, MESSAGE = :p_msg, "
                "FINISHED_AT = SYSTIMESTAMP WHERE ID = :p_id",
                {"p_status": status, "p_pct": 100 if status == 'done' else None,
                 "p_rows": self.rows, "p_dur": round(time.time() - self._t0, 1),
                 "p_msg": (message or "")[:2000], "p_id": self.run_id})
            ds_status = {'done': 'ready', 'failed': 'failed', 'cancelled': 'failed'}.get(status, 'failed')
            cur.execute(
                "UPDATE PLG_DATASETS SET STATUS = :p_status, ROWS_TOTAL = ROWS_TOTAL + :p_rows, "
                "FINISHED_AT = SYSTIMESTAMP WHERE ID = :p_id",
                {"p_status": ds_status, "p_rows": self.rows, "p_id": self.dataset_id})
            self.conn.commit()
        except Exception:
            pass

    def _run(self):
        try:
            self.conn = DatabaseConnection.get_connection()
        except Exception as e:
            with DataGenerator._lock:
                DataGenerator._active.pop(self.run_id, None)
            return
        try:
            weights = {'network': 5, 'assortment': 8, 'events': 12, 'demand': 60, 'traffic': 15}
            total_weight = sum(weights[s] for s in self.stages) or 1
            done_weight = 0
            for stage in self.stages:
                self._check_cancel()
                self._progress(stage, int(done_weight / total_weight * 100))
                getattr(self, f"_gen_{stage}")(
                    lambda p, st=stage, dw=done_weight, w=weights[stage]:
                    self._progress(st, int((dw + w * p) / total_weight * 100)))
                done_weight += weights[stage]
            self._finish('done', f"Сгенерировано строк: {self.rows}")
        except GeneratorCancelled:
            self._finish('cancelled', 'Прогон остановлен оператором')
        except Exception as e:
            import traceback
            self._finish('failed', f"{e}\n{traceback.format_exc()[:1500]}")
        finally:
            try:
                self.conn.close()
            except Exception:
                pass
            with DataGenerator._lock:
                DataGenerator._active.pop(self.run_id, None)

    def _executemany(self, sql: str, rows: List[Tuple], batch: int = BATCH):
        if not rows:
            return
        cur = self.conn.cursor()
        for i in range(0, len(rows), batch):
            self._check_cancel()
            cur.executemany(sql, rows[i:i + batch])
            self.conn.commit()
        self.rows += len(rows)

    def _fetch(self, sql: str, params: Optional[Dict] = None) -> List[Tuple]:
        cur = self.conn.cursor()
        cur.execute(sql, params or {})
        return cur.fetchall()

    def _categories(self) -> Dict[str, int]:
        return {code: cid for cid, code in self._fetch("SELECT ID, CODE FROM PLG_CATEGORIES")}

    # ==================== 1. Сеть магазинов ====================

    def _gen_network(self, progress):
        count = int(self.params.get('store_count') or 10)
        formats = self.params.get('formats') or ['hyper', 'super', 'discounter', 'convenience']
        formats = [f for f in formats if f in STORE_FORMATS] or list(STORE_FORMATS)
        cats = self._categories()
        cur = self.conn.cursor()

        # Распределение форматов: гипермаркетов мало, «у дома» много
        weights = {'hyper': 1, 'super': 4, 'discounter': 3, 'convenience': 4}
        pool = [f for f in formats for _ in range(weights.get(f, 1))]

        for i in range(count):
            self._check_cancel()
            fmt = pool[i % len(pool)] if i < len(pool) else self.rnd.choice(pool)
            prof = STORE_FORMATS[fmt]
            city = self.rnd.choice(CITIES)
            street = self.rnd.choice(STREETS)
            house = self.rnd.randint(1, 180)
            code = f"{city[4]}-{fmt[:3].upper()}-{i + 1:03d}"
            area = round(self.rnd.uniform(*prof['area']), 1)
            checkouts = self.rnd.randint(*prof['checkouts'])

            store_var = cur.var(int)
            cur.execute(
                "INSERT INTO PLG_STORES (CODE, NAME_RU, NAME_RO, NAME_EN, CITY, "
                "ADDRESS_RU, ADDRESS_RO, ADDRESS_EN, AREA_SQM, MAP_WIDTH, MAP_HEIGHT, "
                "CHECKOUT_QTY, MANAGER_NAME, STATUS, DATASET_ID, STORE_FORMAT) "
                "VALUES (:p_code, :p_ru, :p_ro, :p_en, :p_city, :p_aru, :p_aro, :p_aen, "
                ":p_area, 780, 460, :p_ck, :p_mgr, 'active', :p_ds, :p_fmt) RETURNING ID INTO :p_id",
                {"p_code": code,
                 "p_ru": f"{prof['ru']} {city[1]} №{i + 1}",
                 "p_ro": f"{prof['ro']} {city[2]} nr. {i + 1}",
                 "p_en": f"{prof['en']} {city[3]} no. {i + 1}",
                 "p_city": city[0],
                 "p_aru": f"{street[0]}, {house}",
                 "p_aro": f"{street[1]}, {house}",
                 "p_aen": f"{house} {street[2]}",
                 "p_area": area, "p_ck": checkouts,
                 "p_mgr": self.rnd.choice(['Иван Петров', 'Мария Урсу', 'Сергей Ротару',
                                           'Виктория Мунтяну', 'Андрей Кожокару']),
                 "p_ds": self.dataset_id, "p_fmt": fmt, "p_id": store_var})
            store_id = int(store_var.getvalue()[0])
            self.rows += 1

            allowed = FORMAT_ZONE_LIMIT.get(fmt)
            zone_ids: Dict[str, int] = {}
            for (zcode, ztype, ccode, x, y, w, h, color, sort) in ZONE_TEMPLATE:
                if allowed is not None and zcode not in allowed:
                    continue
                zvar = cur.var(int)
                names = self._zone_names(zcode, ccode)
                cur.execute(
                    "INSERT INTO PLG_ZONES (STORE_ID, CODE, ZONE_TYPE, CATEGORY_ID, "
                    "NAME_RU, NAME_RO, NAME_EN, POS_X, POS_Y, WIDTH, HEIGHT, COLOR, AREA_SQM, SORT_ORDER) "
                    "VALUES (:p_st, :p_code, :p_type, :p_cat, :p_ru, :p_ro, :p_en, "
                    ":p_x, :p_y, :p_w, :p_h, :p_color, :p_area, :p_sort) RETURNING ID INTO :p_id",
                    {"p_st": store_id, "p_code": zcode, "p_type": ztype,
                     "p_cat": cats.get(ccode) if ccode else None,
                     "p_ru": names[0], "p_ro": names[1], "p_en": names[2],
                     "p_x": x, "p_y": y, "p_w": w, "p_h": h, "p_color": color,
                     "p_area": round(w * h / 100, 2), "p_sort": sort, "p_id": zvar})
                zone_ids[zcode] = int(zvar.getvalue()[0])
                self.rows += 1

            self._gen_fixtures(cur, store_id, fmt, zone_ids)
            self.conn.commit()
            progress((i + 1) / count)

    @staticmethod
    def _zone_names(zcode: str, ccode: Optional[str]) -> Tuple[str, str, str]:
        special = {
            'storage':  ('Склад', 'Depozit', 'Storage'),
            'service':  ('Служебное помещение', 'Încăpere de serviciu', 'Service room'),
            'wc':       ('Туалет', 'Toaletă', 'Restroom'),
            'promo':    ('Остров акций', 'Insula promoțiilor', 'Promo island'),
            'checkout': ('Кассовая зона', 'Zona de case', 'Checkout'),
            'entrance': ('Вход', 'Intrare', 'Entrance'),
        }
        if zcode in special:
            return special[zcode]
        names = {
            'produce': ('Овощи и фрукты', 'Legume și fructe', 'Fruits & vegetables'),
            'drinks':  ('Напитки', 'Băuturi', 'Beverages'),
            'snacks':  ('Снеки', 'Gustări', 'Snacks'),
            'grocery': ('Бакалея', 'Băcănie', 'Grocery'),
            'health':  ('Здоровое питание', 'Alimentație sănătoasă', 'Healthy food'),
            'coffee':  ('Кофе и чай', 'Cafea și ceai', 'Coffee & tea'),
            'kids':    ('Товары для детей', 'Produse pentru copii', 'Kids'),
            'chem':    ('Бытовая химия', 'Chimie de uz casnic', 'Household chem.'),
            'bakery':  ('Пекарня', 'Brutărie', 'Bakery'),
            'meat':    ('Мясо', 'Carne', 'Meat'),
            'fish':    ('Рыба', 'Pește', 'Fish'),
            'dairy':   ('Молочные продукты', 'Produse lactate', 'Dairy'),
            'frozen':  ('Замороженные', 'Produse congelate', 'Frozen'),
            'alcohol': ('Алкоголь', 'Alcool', 'Alcohol'),
        }
        return names.get(ccode or zcode, (zcode, zcode, zcode))

    def _gen_fixtures(self, cur, store_id: int, fmt: str, zone_ids: Dict[str, int]):
        rows_per_format = {'hyper': 4, 'super': 4, 'discounter': 3, 'convenience': 2}
        cols_per_format = {'hyper': 5, 'super': 5, 'discounter': 4, 'convenience': 3}
        centre_zones = [z for z in ('produce', 'drinks', 'grocery', 'snacks', 'coffee') if z in zone_ids]
        if not centre_zones:
            return
        idx = 0
        for r in range(rows_per_format.get(fmt, 3)):
            for c in range(cols_per_format.get(fmt, 4)):
                idx += 1
                zcode = centre_zones[c % len(centre_zones)]
                cur.execute(
                    "INSERT INTO PLG_FIXTURES (STORE_ID, ZONE_ID, CODE, FIXTURE_TYPE, "
                    "NAME_RU, NAME_RO, NAME_EN, POS_X, POS_Y, WIDTH, HEIGHT, ORIENTATION, "
                    "SHELF_COUNT, WIDTH_MM, HEIGHT_MM, DEPTH_MM, SERIAL_NUMBER) "
                    "VALUES (:p_st, :p_zone, :p_code, 'shelf', :p_ru, :p_ro, :p_en, "
                    ":p_x, :p_y, :p_w, 42, 'H', 5, :p_wmm, 1800, 500, :p_sn)",
                    {"p_st": store_id, "p_zone": zone_ids[zcode],
                     "p_code": f"ST-{store_id}-{chr(64 + r + 1)}{c + 1:02d}",
                     "p_ru": f"Стеллаж ряд {r + 1} модуль {c + 1}",
                     "p_ro": f"Raft rând {r + 1} modul {c + 1}",
                     "p_en": f"Shelving row {r + 1} unit {c + 1}",
                     "p_x": 170 + c * 110, "p_y": 82 + r * 72,
                     "p_w": 90 if c == 4 else 80, "p_wmm": (90 if c == 4 else 80) * 12,
                     "p_sn": f"SN-{store_id}-{idx:04d}"})
                self.rows += 1

        for zcode in ('bakery', 'meat', 'fish', 'dairy', 'frozen'):
            if zcode not in zone_ids:
                continue
            tmpl = next(z for z in ZONE_TEMPLATE if z[0] == zcode)
            cur.execute(
                "INSERT INTO PLG_FIXTURES (STORE_ID, ZONE_ID, CODE, FIXTURE_TYPE, "
                "NAME_RU, NAME_RO, NAME_EN, POS_X, POS_Y, WIDTH, HEIGHT, ORIENTATION, "
                "SHELF_COUNT, WIDTH_MM, HEIGHT_MM, DEPTH_MM, SERIAL_NUMBER) "
                "VALUES (:p_st, :p_zone, :p_code, :p_type, :p_ru, :p_ro, :p_en, "
                ":p_x, :p_y, :p_w, :p_h, 'V', 4, 1250, 2000, 700, :p_sn)",
                {"p_st": store_id, "p_zone": zone_ids[zcode],
                 "p_code": f"CL-{store_id}-{zcode[:3].upper()}",
                 "p_type": 'freezer' if zcode == 'frozen' else 'cooler',
                 "p_ru": f"Витрина {zcode}", "p_ro": f"Vitrină {zcode}", "p_en": f"Display {zcode}",
                 "p_x": tmpl[3], "p_y": tmpl[4], "p_w": tmpl[5], "p_h": tmpl[6],
                 "p_sn": f"SN-{store_id}-CL{zcode[:3].upper()}"})
            self.rows += 1

        if 'promo' in zone_ids:
            cur.execute(
                "INSERT INTO PLG_FIXTURES (STORE_ID, ZONE_ID, CODE, FIXTURE_TYPE, "
                "NAME_RU, NAME_RO, NAME_EN, POS_X, POS_Y, WIDTH, HEIGHT, ORIENTATION, "
                "SHELF_COUNT, WIDTH_MM, HEIGHT_MM, DEPTH_MM, SERIAL_NUMBER) "
                "VALUES (:p_st, :p_zone, :p_code, 'island', 'Остров акций', 'Insula promoțiilor', "
                "'Promo island', 162, 356, 70, 50, 'H', 2, 1800, 1000, 900, :p_sn)",
                {"p_st": store_id, "p_zone": zone_ids['promo'],
                 "p_code": f"IS-{store_id}-PR1", "p_sn": f"SN-{store_id}-IS01"})
            self.rows += 1

    # ==================== 2. Ассортиментная матрица ====================

    def _gen_assortment(self, progress):
        total = int(self.params.get('sku_count') or 400)
        cats = self._categories()
        abc_split = self.params.get('abc_split') or [0.2, 0.3, 0.5]
        cur = self.conn.cursor()

        plan: List[Tuple[str, int]] = []
        for ccode, prof in CATEGORY_PROFILE.items():
            if ccode not in cats:
                continue
            plan.append((ccode, max(1, round(total * prof['share']))))
        # Добираем/срезаем до ровного счёта
        diff = total - sum(n for _, n in plan)
        if plan and diff:
            plan[0] = (plan[0][0], max(1, plan[0][1] + diff))

        made = 0
        for ccode, qty in plan:
            prof = CATEGORY_PROFILE[ccode]
            bases = SKU_BASE.get(ccode, [(ccode, ccode, ccode)])
            for n in range(qty):
                self._check_cancel()
                base = bases[n % len(bases)]
                variant = SKU_VARIANT[self.rnd.randrange(len(SKU_VARIANT))]
                brand = self.rnd.choice(BRANDS)
                made += 1
                roll = self.rnd.random()
                abc = 'A' if roll < abc_split[0] else ('B' if roll < abc_split[0] + abc_split[1] else 'C')
                price = round(self.rnd.uniform(*prof['price']), 2)
                pack = self.rnd.choice([1, 1, 6, 6, 8, 12, 12, 24])
                cur.execute(
                    "INSERT INTO PLG_PRODUCTS (CODE, CATEGORY_ID, NAME_RU, NAME_RO, NAME_EN, "
                    "BARCODE, BRAND, UOM, PRICE, CURRENCY, WIDTH_MM, HEIGHT_MM, DEPTH_MM, "
                    "MIN_FACINGS, STATUS, DATASET_ID, ABC_CLASS, ORDER_MULTIPLE, LEAD_TIME_DAYS, "
                    "SHELF_LIFE_DAYS, SUPPLIER) "
                    "VALUES (:p_code, :p_cat, :p_ru, :p_ro, :p_en, :p_bc, :p_brand, 'pcs', "
                    ":p_price, 'MDL', :p_w, :p_h, :p_d, :p_mf, 'active', :p_ds, :p_abc, "
                    ":p_pack, :p_lead, :p_life, :p_sup)",
                    {"p_code": f"D{self.dataset_id}-{ccode[:3].upper()}-{n + 1:04d}",
                     "p_cat": cats[ccode],
                     "p_ru": f"{base[0]} {brand}, {variant[0]}",
                     "p_ro": f"{base[1]} {brand}, {variant[1]}",
                     "p_en": f"{base[2]} {brand}, {variant[2]}",
                     "p_bc": f"484{self.rnd.randrange(10 ** 9):010d}",
                     "p_brand": brand, "p_price": price,
                     "p_w": self.rnd.randint(50, 300), "p_h": self.rnd.randint(40, 340),
                     "p_d": self.rnd.randint(30, 260),
                     "p_mf": 3 if abc == 'A' else (2 if abc == 'B' else 1),
                     "p_ds": self.dataset_id, "p_abc": abc, "p_pack": pack,
                     "p_lead": self.rnd.choice([1, 1, 2, 2, 3, 5]),
                     "p_life": prof['shelf_life'], "p_sup": self.rnd.choice(SUPPLIERS)})
                self.rows += 1
                if made % 100 == 0:
                    self.conn.commit()
                    progress(made / total)
        self.conn.commit()
        cur.execute("UPDATE PLG_DATASETS SET SKU_COUNT = :p_n WHERE ID = :p_id",
                    {"p_n": made, "p_id": self.dataset_id})
        self.conn.commit()

    # ==================== 3. Акции, планограммы, задачи ====================

    def _gen_events(self, progress):
        stores = self._fetch(
            "SELECT ID, CODE FROM PLG_STORES WHERE DATASET_ID = :p_ds ORDER BY ID",
            {"p_ds": self.dataset_id})
        products = self._fetch(
            "SELECT ID, CATEGORY_ID, PRICE FROM PLG_PRODUCTS WHERE DATASET_ID = :p_ds",
            {"p_ds": self.dataset_id})
        if not stores or not products:
            return
        days = int(self.params.get('days') or 365)
        promo_per_store = int(self.params.get('promo_per_store') or 6)
        plg_per_store = int(self.params.get('planogram_per_store') or 5)
        task_per_store = int(self.params.get('task_per_store') or 8)
        today = date.today()
        cur = self.conn.cursor()

        for si, (store_id, store_code) in enumerate(stores):
            self._check_cancel()
            zones = self._fetch(
                "SELECT ID, CODE, CATEGORY_ID FROM PLG_ZONES WHERE STORE_ID = :p_st "
                "AND ZONE_TYPE IN ('dept','promo_island')", {"p_st": store_id})
            fixtures = self._fetch(
                "SELECT ID, ZONE_ID FROM PLG_FIXTURES WHERE STORE_ID = :p_st", {"p_st": store_id})
            if not zones:
                continue

            # --- Акции: раскиданы по всей глубине истории, часть активна сейчас
            promo_total = max(1, round(promo_per_store * days / 90))
            for p in range(promo_total):
                ptype, label, disc, name = PROMO_TEMPLATES[self.rnd.randrange(len(PROMO_TEMPLATES))]
                dur = self.rnd.choice([7, 10, 14, 14, 21])
                start_offset = self.rnd.randint(-days, 20)
                d_from = today + timedelta(days=start_offset)
                d_to = d_from + timedelta(days=dur)
                zone = self.rnd.choice(zones)
                status = ('active' if d_from <= today <= d_to
                          else ('planned' if d_from > today else 'finished'))
                pvar = cur.var(int)
                cur.execute(
                    "INSERT INTO PLG_PROMOS (CODE, STORE_ID, PROMO_TYPE, NAME_RU, NAME_RO, NAME_EN, "
                    "LABEL, DISCOUNT_PCT, DATE_FROM, DATE_TO, STATUS) "
                    "VALUES (:p_code, :p_st, :p_type, :p_ru, :p_ro, :p_en, :p_label, :p_disc, "
                    ":p_from, :p_to, :p_status) RETURNING ID INTO :p_id",
                    {"p_code": f"PR-{store_id}-{p + 1:04d}", "p_st": store_id, "p_type": ptype,
                     "p_ru": f"{name[0]}: {self._zone_names(zone[1], None)[0]}",
                     "p_ro": f"{name[1]}: {self._zone_names(zone[1], None)[1]}",
                     "p_en": f"{name[2]}: {self._zone_names(zone[1], None)[2]}",
                     "p_label": label, "p_disc": disc, "p_from": d_from, "p_to": d_to,
                     "p_status": status, "p_id": pvar})
                promo_id = int(pvar.getvalue()[0])
                self.rows += 1
                cur.execute("INSERT INTO PLG_PROMO_ZONES (PROMO_ID, ZONE_ID) VALUES (:p_pr, :p_z)",
                            {"p_pr": promo_id, "p_z": zone[0]})
                # Товары акции — из категории зоны, иначе случайные
                pool = [p2 for p2 in products if zone[2] and p2[1] == zone[2]] or products
                for prod in self.rnd.sample(pool, min(len(pool), self.rnd.randint(3, 12))):
                    cur.execute(
                        "INSERT INTO PLG_PROMO_PRODUCTS (PROMO_ID, PRODUCT_ID, PROMO_PRICE) "
                        "VALUES (:p_pr, :p_prod, :p_price)",
                        {"p_pr": promo_id, "p_prod": prod[0],
                         "p_price": round(float(prod[2] or 0) * (1 - disc / 100.0), 2)})
                    self.rows += 1

            # --- Планограммы по зонам
            for k, zone in enumerate(self.rnd.sample(zones, min(len(zones), plg_per_store))):
                status = self.rnd.choice(['active', 'active', 'approved', 'review', 'draft', 'archived'])
                zn = self._zone_names(zone[1], None)
                plvar = cur.var(int)
                cur.execute(
                    "INSERT INTO PLG_PLANOGRAMS (STORE_ID, ZONE_ID, NAME_RU, NAME_RO, NAME_EN, "
                    "VERSION_NO, STATUS, VALID_FROM, VALID_TO, AUTHOR, SHELF_SHARE_PCT) "
                    "VALUES (:p_st, :p_z, :p_ru, :p_ro, :p_en, :p_ver, :p_status, :p_from, :p_to, "
                    ":p_author, :p_share) RETURNING ID INTO :p_id",
                    {"p_st": store_id, "p_z": zone[0],
                     "p_ru": f"{zn[0]} — выкладка {store_code}",
                     "p_ro": f"{zn[1]} — expunere {store_code}",
                     "p_en": f"{zn[2]} — layout {store_code}",
                     "p_ver": self.rnd.randint(1, 4), "p_status": status,
                     "p_from": today - timedelta(days=self.rnd.randint(10, 120)),
                     "p_to": today + timedelta(days=self.rnd.randint(20, 180)),
                     "p_author": self.rnd.choice(['Мария Урсу', 'Сергей Ротару', 'Иван Петров']),
                     "p_share": round(self.rnd.uniform(3, 20), 2), "p_id": plvar})
                plg_id = int(plvar.getvalue()[0])
                self.rows += 1
                cur.execute(
                    "INSERT INTO PLG_PLANOGRAM_HISTORY (PLANOGRAM_ID, VERSION_NO, ACTION, "
                    "SUMMARY_RU, SUMMARY_RO, SUMMARY_EN, CHANGED_BY) "
                    "VALUES (:p_id, 1, 'created', 'Планограмма создана', 'Planogramă creată', "
                    "'Planogram created', 'generator')", {"p_id": plg_id})
                self.rows += 1

                zone_fixtures = [f for f in fixtures if f[1] == zone[0]]
                pool = [p2 for p2 in products if zone[2] and p2[1] == zone[2]] or products
                for pos, prod in enumerate(self.rnd.sample(pool, min(len(pool), self.rnd.randint(4, 10)))):
                    cur.execute(
                        "INSERT INTO PLG_PLANOGRAM_ITEMS (PLANOGRAM_ID, FIXTURE_ID, PRODUCT_ID, "
                        "SHELF_NO, POSITION_NO, FACINGS, DEPTH_QTY, IS_PROMO) "
                        "VALUES (:p_plg, :p_fx, :p_prod, :p_shelf, :p_pos, :p_fac, 3, 0)",
                        {"p_plg": plg_id,
                         "p_fx": zone_fixtures[pos % len(zone_fixtures)][0] if zone_fixtures else None,
                         "p_prod": prod[0], "p_shelf": pos // 4 + 1, "p_pos": pos % 4 + 1,
                         "p_fac": self.rnd.randint(1, 8)})
                    self.rows += 1

            # --- Задачи и уведомления
            task_types = ['relayout', 'restock', 'promo_setup', 'audit', 'price_tag', 'fix']
            titles = {
                'relayout':   ('Перевыкладка зоны', 'Reamplasarea zonei', 'Zone relayout'),
                'restock':    ('Пополнение полки', 'Reaprovizionarea raftului', 'Shelf restock'),
                'promo_setup':('Монтаж акции', 'Montarea promoției', 'Promo setup'),
                'audit':      ('Аудит выкладки', 'Auditul expunerii', 'Layout audit'),
                'price_tag':  ('Замена ценников', 'Schimbarea etichetelor', 'Price tag replacement'),
                'fix':        ('Ремонт оборудования', 'Reparația echipamentului', 'Equipment repair'),
            }
            for k in range(task_per_store):
                ttype = self.rnd.choice(task_types)
                zone = self.rnd.choice(zones)
                zn = self._zone_names(zone[1], None)
                cur.execute(
                    "INSERT INTO PLG_TASKS (STORE_ID, ZONE_ID, TASK_TYPE, TITLE_RU, TITLE_RO, TITLE_EN, "
                    "PRIORITY, STATUS, ASSIGNEE, DUE_DATE, CREATED_BY) "
                    "VALUES (:p_st, :p_z, :p_type, :p_ru, :p_ro, :p_en, :p_prio, :p_status, "
                    ":p_asg, :p_due, 'generator')",
                    {"p_st": store_id, "p_z": zone[0], "p_type": ttype,
                     "p_ru": f"{titles[ttype][0]}: {zn[0]}",
                     "p_ro": f"{titles[ttype][1]}: {zn[1]}",
                     "p_en": f"{titles[ttype][2]}: {zn[2]}",
                     "p_prio": self.rnd.choice(['high', 'medium', 'medium', 'low']),
                     "p_status": self.rnd.choice(['new', 'in_progress', 'review', 'done', 'done']),
                     "p_asg": self.rnd.choice(['Андрей Кожокару', 'Виктория Мунтяну', 'Тех. служба']),
                     "p_due": today + timedelta(days=self.rnd.randint(-10, 14))})
                self.rows += 1

            for k in range(self.rnd.randint(2, 5)):
                lvl = self.rnd.choice(['info', 'warn', 'alert'])
                texts = {
                    'info':  ('Планограмма обновлена', 'Planograma a fost actualizată', 'Planogram updated'),
                    'warn':  ('Отклонение от планограммы', 'Abatere de la planogramă', 'Planogram deviation'),
                    'alert': ('Низкий остаток по SKU категории A', 'Stoc redus la SKU clasa A', 'Low stock on A-class SKU'),
                }
                cur.execute(
                    "INSERT INTO PLG_NOTIFICATIONS (STORE_ID, LEVEL_CODE, ENTITY_TYPE, "
                    "TEXT_RU, TEXT_RO, TEXT_EN, IS_READ, CREATED_AT) "
                    "VALUES (:p_st, :p_lvl, 'planogram', :p_ru, :p_ro, :p_en, :p_read, "
                    "SYSTIMESTAMP - :p_ago)",
                    {"p_st": store_id, "p_lvl": lvl,
                     "p_ru": texts[lvl][0], "p_ro": texts[lvl][1], "p_en": texts[lvl][2],
                     "p_read": self.rnd.choice([0, 0, 1]), "p_ago": self.rnd.uniform(0, 20)})
                self.rows += 1

            self.conn.commit()
            progress((si + 1) / len(stores))

    # ==================== 4. История спроса ====================

    def _gen_demand(self, progress):
        """
        Ядро окружения. Для каждой пары «магазин × SKU» строится суточный ряд:

            qty = base × yearly(t) × weekday(t) × trend(t) × promo(t) × noise
                  с наложением out-of-stock и простой (s,S) политикой запаса.

        Ассортимент магазина зависит от формата: гипермаркет держит всю матрицу,
        «у дома» — только треть, поэтому сеть выглядит неоднородно, как настоящая.
        """
        days = int(self.params.get('days') or 365)
        noise_pct = float(self.params.get('noise_pct') or 18) / 100.0
        oos_rate = float(self.params.get('oos_rate') or 0.015)
        trend_year = float(self.params.get('trend_pct_year') or 6) / 100.0
        weekly_amp = float(self.params.get('weekly_amplitude') or 0.35)
        yearly_amp_k = float(self.params.get('yearly_amplitude') or 0.20)

        stores = self._fetch(
            "SELECT ID, STORE_FORMAT, AREA_SQM FROM PLG_STORES WHERE DATASET_ID = :p_ds ORDER BY ID",
            {"p_ds": self.dataset_id})
        products = self._fetch(
            "SELECT p.ID, c.CODE, p.PRICE, p.ABC_CLASS, p.ORDER_MULTIPLE "
            "FROM PLG_PRODUCTS p JOIN PLG_CATEGORIES c ON c.ID = p.CATEGORY_ID "
            "WHERE p.DATASET_ID = :p_ds ORDER BY p.ID", {"p_ds": self.dataset_id})
        if not stores or not products:
            return

        today = date.today()
        start = today - timedelta(days=days - 1)

        # Промо-календарь: (store_id, product_id) -> {date_ordinal: (promo_id, discount)}
        promo_map: Dict[Tuple[int, int], Dict[int, Tuple[int, float]]] = {}
        for (pid, store_id, d_from, d_to, disc, prod_id) in self._fetch(
                "SELECT pr.ID, pr.STORE_ID, pr.DATE_FROM, pr.DATE_TO, NVL(pr.DISCOUNT_PCT,0), pp.PRODUCT_ID "
                "FROM PLG_PROMOS pr JOIN PLG_PROMO_PRODUCTS pp ON pp.PROMO_ID = pr.ID "
                "JOIN PLG_STORES s ON s.ID = pr.STORE_ID WHERE s.DATASET_ID = :p_ds",
                {"p_ds": self.dataset_id}):
            key = (int(store_id), int(prod_id))
            bucket = promo_map.setdefault(key, {})
            d = d_from.date() if hasattr(d_from, 'date') else d_from
            end = d_to.date() if hasattr(d_to, 'date') else d_to
            while d <= end:
                bucket[d.toordinal()] = (int(pid), float(disc))
                d += timedelta(days=1)

        abc_base = {'A': (7.0, 26.0), 'B': (2.2, 8.0), 'C': (0.35, 2.6)}
        sql = ("INSERT INTO PLG_SALES_DAILY (ID, STORE_ID, PRODUCT_ID, SALES_DATE, QTY, AMOUNT, "
               "PRICE, PROMO_ID, STOCK_END, IS_OOS) "
               "VALUES (PLG_SALES_SEQ.NEXTVAL, :1, :2, :3, :4, :5, :6, :7, :8, :9)")

        total_pairs = 0
        for store_id, fmt, area in stores:
            share = STORE_FORMATS.get(fmt, STORE_FORMATS['super'])['assortment_share']
            total_pairs += max(1, int(len(products) * share))
        done_pairs = 0
        buffer: List[Tuple] = []

        for store_id, fmt, area in stores:
            self._check_cancel()
            prof = STORE_FORMATS.get(fmt, STORE_FORMATS['super'])
            share = prof['assortment_share']
            traffic_k = sum(prof['traffic']) / 2.0 / 3000.0   # нормировка к «среднему» супермаркету

            # Ассортимент магазина детерминирован seed'ом магазина
            srnd = random.Random(self.seed * 7919 + int(store_id))
            local_products = products if share >= 0.999 else srnd.sample(
                products, max(1, int(len(products) * share)))

            for (prod_id, ccode, price, abc, pack) in local_products:
                self._check_cancel()
                cprof = CATEGORY_PROFILE.get(ccode, CATEGORY_PROFILE['grocery'])
                lo, hi = abc_base.get(abc or 'C', abc_base['C'])
                prnd = random.Random(self.seed * 104729 + int(store_id) * 7919 + int(prod_id))
                base = prnd.uniform(lo, hi) * traffic_k
                yearly_amp = cprof['yearly_amp'] * (yearly_amp_k / 0.20)
                phase = cprof['yearly_phase']
                price_f = float(price or 10)
                pack = int(pack or 1)
                bucket = promo_map.get((int(store_id), int(prod_id)), {})

                stock = base * prnd.uniform(4, 9)
                reorder_point = base * 3
                target_stock = base * 10

                for i in range(days):
                    d = start + timedelta(days=i)
                    doy = d.timetuple().tm_yday
                    yearly = 1.0 + yearly_amp * math.sin(2 * math.pi * (doy - phase) / 365.0)
                    wd = WEEKDAY_PROFILE[d.weekday()]
                    weekday_f = 1.0 + (wd - 1.0) * (weekly_amp / 0.35)
                    trend = (1.0 + trend_year) ** (i / 365.0)

                    promo = bucket.get(d.toordinal())
                    if promo:
                        promo_id, disc = promo
                        uplift = 1.35 + (disc / 100.0) * 2.6
                    else:
                        promo_id, disc, uplift = None, 0.0, 1.0

                    noise = max(0.15, prnd.gauss(1.0, noise_pct))
                    demand = base * yearly * weekday_f * trend * uplift * noise

                    # Пополнение: (s,S) — при падении ниже точки заказа приходит партия
                    if stock < reorder_point:
                        stock += max(pack, math.ceil((target_stock - stock) / pack) * pack)

                    is_oos = 0
                    if prnd.random() < oos_rate:
                        # Разрыв поставки: продали только то, что было
                        demand *= prnd.uniform(0.0, 0.35)
                        is_oos = 1
                    if demand > stock:
                        demand = stock
                        is_oos = 1

                    qty = round(max(0.0, demand), 3)
                    stock = round(max(0.0, stock - qty), 3)
                    sell_price = round(price_f * (1 - disc / 100.0), 2)
                    buffer.append((int(store_id), int(prod_id), d, qty,
                                   round(qty * sell_price, 2), sell_price,
                                   promo_id, stock, is_oos))

                    if len(buffer) >= BATCH:
                        self._executemany(sql, buffer)
                        buffer = []

                done_pairs += 1
                if done_pairs % 200 == 0:
                    progress(done_pairs / max(1, total_pairs))

        if buffer:
            self._executemany(sql, buffer)
        cur = self.conn.cursor()
        cur.execute("UPDATE PLG_DATASETS SET DAYS_DEPTH = :p_d, STORE_COUNT = :p_s WHERE ID = :p_id",
                    {"p_d": days, "p_s": len(stores), "p_id": self.dataset_id})
        self.conn.commit()

    # ==================== 5. Трафик и показатели ====================

    def _gen_traffic(self, progress):
        """
        Метрики выводятся ИЗ продаж, а не генерируются независимо:
        выручка = сумма продаж дня, покупатели = выручка / средний чек,
        трафик = покупатели / конверсия. Поэтому дашборд и аналитика
        согласованы с историей спроса, а не живут своей жизнью.
        """
        conv_min = float(self.params.get('conversion_min') or 16)
        conv_max = float(self.params.get('conversion_max') or 21)
        stores = self._fetch("SELECT ID FROM PLG_STORES WHERE DATASET_ID = :p_ds ORDER BY ID",
                             {"p_ds": self.dataset_id})
        if not stores:
            return
        cur = self.conn.cursor()

        for si, (store_id,) in enumerate(stores):
            self._check_cancel()
            daily = self._fetch(
                "SELECT SALES_DATE, SUM(AMOUNT), SUM(QTY) FROM PLG_SALES_DAILY "
                "WHERE STORE_ID = :p_st GROUP BY SALES_DATE ORDER BY SALES_DATE",
                {"p_st": store_id})
            if not daily:
                continue

            srnd = random.Random(self.seed * 31 + int(store_id))
            metric_rows = []
            for (d, amount, qty) in daily:
                d = d.date() if hasattr(d, 'date') else d
                amount = float(amount or 0)
                conv = srnd.uniform(conv_min, conv_max)
                avg_check = max(45.0, srnd.gauss(amount / max(1.0, float(qty or 1)) * 6.5, 30))
                buyers = max(1, int(amount / avg_check))
                traffic = max(buyers, int(buyers / (conv / 100.0)))
                metric_rows.append((int(store_id), d, traffic, buyers, round(conv, 2),
                                    round(avg_check, 2), round(amount, 2)))
            self._executemany(
                "INSERT INTO PLG_STORE_METRICS (STORE_ID, METRIC_DATE, TRAFFIC, BUYERS, "
                "CONVERSION_PCT, AVG_CHECK, REVENUE, CURRENCY) "
                "VALUES (:1, :2, :3, :4, :5, :6, :7, 'MDL')", metric_rows)

            # Показатели по категориям — из продаж категории
            cat_rows = self._fetch(
                "SELECT sd.SALES_DATE, p.CATEGORY_ID, SUM(sd.QTY), SUM(sd.AMOUNT) "
                "FROM PLG_SALES_DAILY sd JOIN PLG_PRODUCTS p ON p.ID = sd.PRODUCT_ID "
                "WHERE sd.STORE_ID = :p_st AND p.CATEGORY_ID IS NOT NULL "
                "GROUP BY sd.SALES_DATE, p.CATEGORY_ID", {"p_st": store_id})
            self._executemany(
                "INSERT INTO PLG_CATEGORY_METRICS (STORE_ID, CATEGORY_ID, METRIC_DATE, "
                "VISITS, SALES_QTY, SALES_AMT) VALUES (:1, :2, :3, :4, :5, :6)",
                [(int(store_id), int(cid), (d.date() if hasattr(d, 'date') else d),
                  int(float(q or 0) * srnd.uniform(2.5, 4.5)), int(float(q or 0)), round(float(a or 0), 2))
                 for (d, cid, q, a) in cat_rows])

            # Проходимость зон: доля категории в продажах → нормируем в 0..100
            zones = self._fetch(
                "SELECT ID, CATEGORY_ID, ZONE_TYPE FROM PLG_ZONES WHERE STORE_ID = :p_st",
                {"p_st": store_id})
            cat_share = {}
            total_qty = sum(float(q or 0) for (_, _, q, _) in cat_rows) or 1.0
            for (_, cid, q, _) in cat_rows:
                cat_share[int(cid)] = cat_share.get(int(cid), 0.0) + float(q or 0)
            max_share = max(cat_share.values()) if cat_share else 1.0

            traffic_rows = []
            recent = sorted({(d.date() if hasattr(d, 'date') else d) for (d, _, _) in daily})[-14:]
            for (zone_id, cat_id, ztype) in zones:
                for d in recent:
                    if ztype in ('checkout', 'entrance'):
                        pct = 100.0
                    elif ztype in ('storage', 'service', 'wc'):
                        pct = round(srnd.uniform(2, 20), 2)
                    elif cat_id and cat_id in cat_share:
                        pct = round(min(98.0, 25 + 73 * cat_share[int(cat_id)] / max_share
                                        + srnd.uniform(-6, 6)), 2)
                    else:
                        pct = round(srnd.uniform(30, 70), 2)
                    traffic_rows.append((int(zone_id), d, round(pct, 2),
                                         int(srnd.uniform(300, 3000)),
                                         int(srnd.uniform(20, 240)), int(srnd.uniform(50, 900))))
            self._executemany(
                "INSERT INTO PLG_ZONE_TRAFFIC (ZONE_ID, METRIC_DATE, METRIC_HOUR, TRAFFIC_PCT, "
                "VISITORS, DWELL_SEC, PICKUPS) VALUES (:1, :2, NULL, :3, :4, :5, :6)",
                traffic_rows)

            progress((si + 1) / len(stores))
