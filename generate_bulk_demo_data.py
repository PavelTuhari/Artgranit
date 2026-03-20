#!/usr/bin/env python3
"""
Генерация массовых демо-данных: ~100 категорий, ~2000 товаров,
20 кредитных программ на банк, матрица категория×программа.
Электроника и быттехника типичного мега-портала.
"""
import sys
import os
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

# --- Категории (~100): электроника, быттехника, гаджеты ---
CATEGORIES = [
    "Холодильники", "Морозильники", "Стиральные машины", "Сушильные машины",
    "Посудомоечные машины", "Плиты газовые", "Плиты электрические", "Духовые шкафы",
    "Микроволновые печи", "Вытяжки", "Варочные панели", "Кофемашины", "Чайники электрические",
    "Тостеры", "Блендеры", "Мясорубки", "Кухонные комбайны", "Соковыжималки",
    "Утюги", "Отпариватели", "Пылесосы", "Роботы-пылесосы", "Швейные машины",
    "Телевизоры", "Мониторы", "Проекторы", "ТВ-приставки", "Медиаплееры",
    "Смартфоны", "Планшеты", "Ноутбуки", "Нетбуки", "Моноблоки", "Системные блоки",
    "Наушники", "Колонки", "Саундбары", "Микрофоны", "Веб-камеры",
    "Роутеры", "Сетевые хранилища", "Powerbank", "Зарядные устройства",
    "Клавиатуры", "Мыши", "Геймпады", "Руль рулевой", "VR-шлемы",
    "Принтеры", "МФУ", "Картриджи", "Кабели и адаптеры", "Флешки", "Карты памяти",
    "Умные часы", "Фитнес-браслеты", "Электросамокаты", "Гироскутеры",
    "Обогреватели", "Кондиционеры", "Вентиляторы", "Увлажнители", "Очистители воздуха",
    "Весы напольные", "Термометры", "Тонометры", "Массажёры", "Эпиляторы",
    "Электробритвы", "Триммеры", "Фены", "Стайлеры", "Щипцы для завивки",
    "Детские мониторы", "Радионяни", "Стерилизаторы", "Подогреватели",
    "Игровые консоли", "Игры для консолей", "Настольные игры", "Книги электронные",
    "Чехлы и плёнки", "Аккумуляторы", "Батарейки", "Лампы и светильники",
    "Термосы", "Кружки подогрев", "Грили", "Аэрогрили", "Йогуртницы", "Хлебопечки",
    "Машинки для стрижки", "Маникюрные наборы", "Зубные щётки электрические",
    "Счётчики купюр", "Детекторы валют", "Шредеры", "Ламинаторы",
]

# --- Бренды (~50) ---
BRANDS = [
    "Samsung", "Apple", "LG", "Beko", "ASUS", "Sony", "Xiaomi", "Huawei", "Honor",
    "Bosch", "Siemens", "Philips", "Braun", "De'Longhi", "Tefal", "Redmond",
    "Lenovo", "Acer", "HP", "Dell", "MSI", "Razer", "Logitech", "JBL", "Jabra",
    "Dyson", "Electrolux", "Indesit", "Ariston", "Hotpoint", "Gorenje", "Miele",
    "Haier", "BBK", "Supra", "Scarlett", "Polaris", "Vitek", "Rolsen", "Kenwood",
    "KitchenAid", "Moulinex", "Rowenta", "Remington", "Panasonic", "Canon", "Epson",
    "Realme", "OnePlus", "OPPO", "Vivo",
]

# Банки (должны уже быть в БД после 10_demo_data)
BANK_CODES = ["Maib", "Victoriabank", "Moldindconbank", "Express Credit"]


def run_sql(cursor, sql, commit=True):
    cursor.execute(sql)
    if commit:
        cursor.connection.commit()


def main():
    print("=" * 60)
    print("Генерация массовых демо-данных (категории, товары, программы)")
    print("=" * 60)

    try:
        from models.database import DatabaseConnection
        conn = DatabaseConnection.get_connection()
        cur = conn.cursor()
    except Exception as e:
        print(f"✗ Ошибка подключения: {e}")
        return 1

    force = "--force" in sys.argv or "-f" in sys.argv
    skip_delete = "--append" in sys.argv
    quick = "--quick" in sys.argv
    n_categories = 20 if quick else len(CATEGORIES)
    n_brands = 15 if quick else len(BRANDS)
    n_programs_per_bank = 5 if quick else 20
    n_products = 300 if quick else 2100

    if not skip_delete and not force:
        cur.execute("SELECT COUNT(*) FROM CRED_PRODUCTS")
        n = cur.fetchone()[0]
        if n > 20:
            print(f"⚠ В БД уже {n} товаров. Запустите с --force для перезаписи или --append для добавления.")
            cur.close()
            conn.close()
            return 0

    # --- 1. Удаление (если не append) ---
    if not skip_delete:
        print("\n1. Удаление старых кредитных данных...")
        for t in ["CRED_APPLICATIONS", "CRED_PROGRAM_EXCLUDED_BRANDS", "CRED_PROGRAM_CATEGORIES",
                  "CRED_PRODUCTS", "CRED_PROGRAMS", "CRED_BRANDS", "CRED_CATEGORIES", "CRED_BANKS"]:
            try:
                cur.execute(f"DELETE FROM {t}")
                conn.commit()
            except Exception as e:
                conn.rollback()
                print(f"   skip {t}: {e}")
        print("   ✓ Готово")

    # --- 2. Банки ---
    print("\n2. Банки...")
    for code in BANK_CODES:
        try:
            cur.execute(
                "INSERT INTO CRED_BANKS (CODE, NAME) VALUES (:1, :2)",
                (code, code)
            )
            conn.commit()
        except Exception as e:
            if "ORA-00001" not in str(e) and "unique" not in str(e).lower():
                conn.rollback()
                print(f"   {code}: {e}")
    cur.execute("SELECT ID, CODE FROM CRED_BANKS ORDER BY ID")
    banks = list(cur.fetchall())
    print(f"   ✓ Банков: {len(banks)}")

    # --- 3. Категории ---
    print("\n3. Категории...")
    for name in CATEGORIES[:n_categories]:
        try:
            cur.execute("INSERT INTO CRED_CATEGORIES (NAME) VALUES (:1)", (name,))
            conn.commit()
        except Exception as e:
            conn.rollback()
            if "ORA-00001" not in str(e):
                print(f"   {name}: {e}")
    cur.execute("SELECT ID, NAME FROM CRED_CATEGORIES ORDER BY ID")
    categories = list(cur.fetchall())
    print(f"   ✓ Категорий: {len(categories)}")

    # --- 4. Бренды ---
    print("\n4. Бренды...")
    for name in BRANDS[:n_brands]:
        try:
            cur.execute("INSERT INTO CRED_BRANDS (NAME) VALUES (:1)", (name,))
            conn.commit()
        except Exception as e:
            conn.rollback()
            if "ORA-00001" not in str(e):
                print(f"   {name}: {e}")
    cur.execute("SELECT ID, NAME FROM CRED_BRANDS ORDER BY ID")
    brands = list(cur.fetchall())
    print(f"   ✓ Брендов: {len(brands)}")

    # --- 5. Программы: 20 на банк ---
    print("\n5. Кредитные программы (20 на банк)...")
    terms = [6, 12, 18, 24, 36]
    rates = [0, 0, 0, 5.9, 9.9, 12.9]
    first_pct = [0, 10, 20, 30]
    min_max = [(500, 15000), (1000, 30000), (2000, 50000), (3000, 80000), (5000, 150000)]
    for (bank_id, code) in banks:
        for i in range(n_programs_per_bank):
            t = random.choice(terms)
            r = random.choice(rates)
            fp = random.choice(first_pct)
            mn, mx = random.choice(min_max)
            name = f"{code} {r}-{fp}-{t}"
            comm = round(random.uniform(0, 2), 1) if r > 0 else 0
            active = "Y" if random.random() > 0.15 else "N"
            try:
                cur.execute("""
                    INSERT INTO CRED_PROGRAMS (NAME, BANK_ID, TERM_MONTHS, RATE_PCT, FIRST_PAYMENT_PCT, MIN_SUM, MAX_SUM, COMMISSION_PCT, ACTIVE)
                    VALUES (:1, :2, :3, :4, :5, :6, :7, :8, :9)
                """, (name, bank_id, t, r, fp, mn, mx, comm, active))
                conn.commit()
            except Exception as e:
                conn.rollback()
                print(f"   program {code} #{i}: {e}")
    cur.execute("SELECT ID, BANK_ID FROM CRED_PROGRAMS ORDER BY BANK_ID, ID")
    programs = list(cur.fetchall())
    print(f"   ✓ Программ: {len(programs)}")

    # --- 6. Матрица: категория × программа (все активные) ---
    print("\n6. Матрица доступности (категория × программа)...")
    cur.execute("SELECT ID FROM CRED_PROGRAMS WHERE ACTIVE = 'Y'")
    active_prog_ids = [r[0] for r in cur.fetchall()]
    cat_ids = [c[0] for c in categories]
    matrix_rows = [(pid, cid) for cid in cat_ids for pid in active_prog_ids if random.random() < 0.7]
    for i in range(0, len(matrix_rows), 200):
        batch = matrix_rows[i:i+200]
        try:
            cur.executemany(
                "INSERT INTO CRED_PROGRAM_CATEGORIES (PROGRAM_ID, CATEGORY_ID) VALUES (:1, :2)",
                batch
            )
            conn.commit()
        except Exception as e:
            conn.rollback()
            for pid, cid in batch:
                try:
                    cur.execute(
                        "INSERT INTO CRED_PROGRAM_CATEGORIES (PROGRAM_ID, CATEGORY_ID) VALUES (:1, :2)",
                        (pid, cid)
                    )
                    conn.commit()
                except Exception:
                    conn.rollback()
    print(f"   ✓ Записей матрицы: {len(matrix_rows)}")

    # --- 7. Товары ~2000 ---
    print("\n7. Товары (~2000)...")
    articles = set()
    def uniq_article():
        while True:
            a = f"{random.choice('ABCDEFGHKLMNPQR')}{random.randint(100, 9999)}"
            if a not in articles:
                articles.add(a)
                return a

    base_barcodes = [4600000000000 + i for i in range(200000)]
    random.shuffle(base_barcodes)
    bc_iter = iter(base_barcodes)

    vol = ["50л", "100л", "200л", "256ГБ", "512ГБ", "1ТБ", "43\"", "55\"", "65\"", "15.6\"", "27\"", "10.5\"", "6.1\"", "20L", "30L"]

    product_rows = []
    for _ in range(n_products):
        cat_id, cat_name = random.choice(categories)
        brand_id, brand_name = random.choice(brands)
        n = random.randint(1, 999)
        model = f"модель {n}" if random.random() > 0.3 else f"{random.choice(vol)}"
        if random.random() > 0.5:
            name = f"{cat_name} {brand_name} {model}"
        else:
            name = f"{brand_name} {cat_name} {model}"
        name = name.replace("  ", " ").strip()[:300]
        article = uniq_article()
        barcode = str(next(bc_iter))
        price = round(random.randint(500, 250000) / 100) * 100
        product_rows.append((name, article, barcode, price, cat_id, brand_id))
    for i in range(0, len(product_rows), 150):
        batch = product_rows[i:i+150]
        try:
            cur.executemany("""
                INSERT INTO CRED_PRODUCTS (NAME, ARTICLE, BARCODE, PRICE, CATEGORY_ID, BRAND_ID)
                VALUES (:1, :2, :3, :4, :5, :6)
            """, batch)
            conn.commit()
        except Exception as e:
            conn.rollback()
            for row in batch:
                try:
                    cur.execute("""
                        INSERT INTO CRED_PRODUCTS (NAME, ARTICLE, BARCODE, PRICE, CATEGORY_ID, BRAND_ID)
                        VALUES (:1, :2, :3, :4, :5, :6)
                    """, row)
                    conn.commit()
                except Exception:
                    conn.rollback()
    print(f"   ✓ Товаров: {len(product_rows)}")

    # --- 8. Заявки (немного) ---
    print("\n8. Демо-заявки...")
    cur.execute("SELECT ID FROM (SELECT ID FROM CRED_PRODUCTS ORDER BY ID) WHERE ROWNUM <= 50")
    pids = [r[0] for r in cur.fetchall()]
    cur.execute("SELECT ID FROM (SELECT ID FROM CRED_PROGRAMS WHERE ACTIVE = 'Y' ORDER BY ID) WHERE ROWNUM <= 20")
    prog_ids = [r[0] for r in cur.fetchall()]
    fios = ["Иванов И.И.", "Петрова А.С.", "Сидоров П.П.", "Козлова М.В.", "Новиков Д.А."]
    for _ in range(15):
        try:
            phone = "+37369" + str(random.randint(100000, 999999))
            st = random.choice(["pending", "approved", "rejected", "on_review"])
            approved = random.randint(5000, 30000) if st == "approved" and random.random() > 0.3 else None
            cur.execute("""
                INSERT INTO CRED_APPLICATIONS (PRODUCT_ID, PROGRAM_ID, CLIENT_FIO, CLIENT_PHONE, STATUS, APPROVED_AMOUNT)
                VALUES (:1, :2, :3, :4, :5, :6)
            """, (random.choice(pids), random.choice(prog_ids), random.choice(fios), phone, st, approved))
            conn.commit()
        except Exception as e:
            conn.rollback()
    print("   ✓ Готово")

    cur.execute("SELECT COUNT(*) FROM CRED_CATEGORIES")
    nc = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM CRED_PRODUCTS")
    np = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM CRED_PROGRAMS")
    nprog = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM CRED_BANKS")
    nb = cur.fetchone()[0]

    cur.close()
    conn.close()

    print("\n" + "=" * 60)
    print(f"Итого: категорий {nc}, товаров {np}, программ {nprog}, банков {nb}.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
