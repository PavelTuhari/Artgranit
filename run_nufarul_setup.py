#!/usr/bin/env python3
"""
Выполняет миграцию 18 (NAME_EN), импорт услуг Nufarul и проверку.
Запуск из корня проекта с настроенным .env и Oracle.
"""
import os
import sys

root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

os.chdir(root_dir)


def _run_sql_file(db, filename, skip_ora_01430=True):
    """Выполняет SQL-файл (ALTER/CREATE). Пропускает ORA-01430 (уже существует)."""
    sql_dir = os.path.join(root_dir, "sql")
    path = os.path.join(sql_dir, filename)
    if not os.path.isfile(path):
        return False
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    # Убираем комментарии, разбиваем по ;
    lines = []
    for line in content.split("\n"):
        s = line.strip()
        if s.startswith("--") or not s:
            continue
        lines.append(s)
    full = " ".join(lines)
    stmts = [s.strip() for s in full.replace(";", ";\n").split(";") if s.strip()]
    for stmt in stmts:
        if not stmt or stmt.upper().startswith("COMMENT"):
            continue
        try:
            r = db.execute_query(stmt)
            msg = str(r.get("message") or "")
            if msg and "ORA-" in msg:
                if skip_ora_01430 and ("01430" in msg or "00955" in msg or "already exists" in msg.lower()):
                    continue
                raise RuntimeError(msg)
            db.connection.commit()
        except Exception as e:
            err = str(e).upper()
            if skip_ora_01430 and ("ORA-01430" in err or "ORA-00955" in err or "ALREADY EXISTS" in err):
                try:
                    db.connection.rollback()
                except Exception:
                    pass
                continue
            try:
                db.connection.rollback()
            except Exception:
                pass
            raise
    return True


def run_migration_17():
    """Добавляет колонку SERVICE_GROUP в NUF_SERVICES, если её нет."""
    from models.database import DatabaseModel

    with DatabaseModel() as db:
        try:
            _run_sql_file(db, "17_nufarul_service_groups.sql")
            print("Миграция 17 (SERVICE_GROUP): выполнено.")
        except Exception as e:
            if "01430" in str(e) or "already exists" in str(e).lower():
                print("Миграция 17: колонка SERVICE_GROUP уже есть.")
            else:
                raise
    return True


def run_migration_18():
    """Добавляет колонку NAME_EN в NUF_SERVICES, если её нет."""
    from models.database import DatabaseModel

    sql_dir = os.path.join(root_dir, "sql")
    path = os.path.join(sql_dir, "18_nufarul_name_en.sql")
    if not os.path.isfile(path):
        print("Файл 18_nufarul_name_en.sql не найден, пропуск миграции.")
        return True

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    # Убираем комментарии и разбиваем по ;
    lines = []
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("--") or not line:
            continue
        lines.append(line)
    full_sql = " ".join(lines)
    stmts = [s.strip() for s in full_sql.split(";") if s.strip() and "ALTER" in s.upper()]

    with DatabaseModel() as db:
        for stmt in stmts:
            if not stmt:
                continue
            try:
                r = db.execute_query(stmt)
                msg = str(r.get("message") or "")
                if msg and "ORA-" in msg:
                    if "01430" in msg or "already exists" in msg.lower():
                        print("Колонка NAME_EN уже есть, пропуск ALTER.")
                        db.connection.rollback()
                        return True
                    raise RuntimeError(msg)
                db.connection.commit()
                print("Миграция 18: выполнено.")
                return True
            except Exception as e:
                err = str(e).upper()
                if "ORA-01430" in err or "ALREADY EXISTS" in err:
                    print("Колонка NAME_EN уже есть.")
                    try:
                        db.connection.rollback()
                    except Exception:
                        pass
                    return True
                try:
                    db.connection.rollback()
                except Exception:
                    pass
                raise
    return True


def run_import():
    """Импорт услуг из import_nufarul_services."""
    from import_nufarul_services import run_import as do_import
    from models.database import DatabaseModel

    n = do_import(clear_first=True)
    print(f"Импорт: загружено услуг {n}.")
    # Проверка: считаем строки в той же БД
    with DatabaseModel() as db:
        r = db.execute_query("SELECT COUNT(*) AS CNT FROM NUF_SERVICES")
        cnt = (r.get("data") or [[0]])[0][0] if r.get("data") else 0
        print(f"Проверка БД: в таблице NUF_SERVICES строк: {cnt}.")
    return n


def verify():
    """Проверяет, что API возвращает услуги."""
    from controllers.nufarul_controller import NufarulController

    r = NufarulController.get_services(active_only=False)
    if not r.get("success"):
        raise RuntimeError("get_services failed: " + str(r.get("error", "")))
    data = r.get("data") or []
    if not data:
        raise RuntimeError("Список услуг пуст после импорта.")
    print(f"Проверка: в API {len(data)} услуг, группы: {list(r.get('group_labels_ru', {}).keys())[:3]}...")
    return len(data)


if __name__ == "__main__":
    print("=== Nufarul: миграция, импорт, проверка ===\n")
    try:
        run_migration_17()
        run_migration_18()
        n = run_import()
        verify()
        print("\nГотово. Услуги загружены, API отвечает.")
    except Exception as e:
        print(f"\nОшибка: {e}")
        sys.exit(1)
