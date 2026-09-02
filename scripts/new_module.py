#!/usr/bin/env python3
"""Новый проект-модуль Artgranit одной командой (docs/GIT_WORKFLOW.md, раздел 4).

    python scripts/new_module.py carwash "Автомойка" --prefix CWS --icon 🚿

Делает ровно то, что требует CLAUDE.md для изолированного модуля:
  1. worktree ../Artgranit-<ключ> на ветке feat/<ключ> от свежего origin/main;
  2. каркас modules/<ключ>/ (blueprint, routes, controller, store, rules,
     templates, sql, scripts/<ключ>_deploy.py, module.json);
  3. tests/test_<ключ>.py с двумя тестами изоляции;
  4. docs/<Модуль>/README.md + docs.json;
  5. первый коммит и push ветки.

В общий код (app.py, deploy_oracle_objects.py, меню) не пишет ничего —
ядро core/module_loader.py подключает модуль само.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sh(cmd: list[str], cwd: Path = ROOT, check: bool = True) -> str:
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        sys.exit(f"✗ {' '.join(cmd)}\n{r.stderr.strip()}")
    return r.stdout.strip()


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.lstrip("\n"), encoding="utf-8")
    print(f"   + {path.relative_to(path.parents[len(path.relative_to(ROOT.parent).parts) - 1])}")


# --------------------------------------------------------------------------- шаблоны

def t_init(key: str, title: str) -> str:
    return f'''
"""{title} — изолированный модуль Artgranit.

Весь код модуля лежит здесь, в modules/{key}/. В общем коде портала модуль
не оставляет ничего: ядро (core/module_loader.py) находит пакет само и
подключает под /UNA.md/orasldev/{key}. Ядру нужен ровно один объект —
`blueprint`; маршруты объявлены в routes.py и импортируются ниже.
"""
from flask import Blueprint

blueprint = Blueprint("{key}", __name__, template_folder="templates")

from modules.{key} import routes  # noqa: E402,F401  (регистрирует маршруты)

__all__ = ["blueprint"]
'''


def t_routes(key: str, title: str) -> str:
    return f'''
"""Маршруты модуля {title}.

Адреса БЕЗ префикса /UNA.md/orasldev/{key} — его подставляет ядро.
Здесь только разбор запроса и код ответа; логика — в controller.py.
"""
from flask import jsonify, redirect, render_template, request, url_for

from controllers.auth_controller import AuthController
from modules.{key} import blueprint
from modules.{key}.controller import {key.capitalize()}Controller


def _guard():
    if AuthController.is_authenticated():
        return None
    return jsonify({{"success": False, "message": "Требуется вход в систему"}}), 401


@blueprint.route("")
@blueprint.route("/")
def index():
    if not AuthController.is_authenticated():
        return redirect(url_for("login"))
    return render_template("{key}.html")


@blueprint.route("/api/status")
def api_status():
    if (g := _guard()) is not None:
        return g
    payload, status = {key.capitalize()}Controller.status()
    return jsonify(payload), status
'''


def t_controller(key: str, title: str) -> str:
    return f'''
"""Контроллер модуля {title}: валидация и сборка ответов.

Возвращает (payload, http_status). SQL — только в store.py, чистые правила —
в rules.py (тестируются без wallet).
"""
from modules.{key} import rules, store


class {key.capitalize()}Controller:
    @staticmethod
    def status():
        try:
            data = store.counters()
        except Exception as e:  # noqa: BLE001 — наружу только текст
            return {{"success": False, "message": str(e)}}, 500
        return {{"success": True, "data": data, "rules_version": rules.VERSION}}, 200
'''


def t_store(key: str, prefix: str) -> str:
    return f'''
"""Хранилище модуля: весь SQL к таблицам {prefix}_* — только здесь."""
from models.database import DatabaseModel


def _rows(r):
    return r.get("data") if isinstance(r, dict) else r


def counters() -> dict:
    with DatabaseModel() as db:
        r = db.execute_query(
            "SELECT COUNT(*) FROM USER_TABLES WHERE TABLE_NAME LIKE '{prefix}\\\\_%' ESCAPE '\\\\'"
        )
        rows = _rows(r) or [[0]]
    return {{"tables": rows[0][0]}}
'''


def t_rules(key: str) -> str:
    return f'''
"""Чистые правила модуля {key}: без импорта БД, тестируются без wallet."""

VERSION = "1.0"


def normalize_code(value: str) -> str:
    """Код сущности: без пробелов, верхний регистр."""
    return (value or "").strip().upper()
'''


def t_template(key: str, title: str) -> str:
    return f'''
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    body {{ font-family: -apple-system, system-ui, sans-serif; margin: 0; background: #0f1419; color: #e6edf3; }}
    header {{ padding: 14px 18px; background: #161b22; border-bottom: 1px solid #30363d; }}
    main {{ padding: 18px; }}
    .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 14px; max-width: 520px; }}
  </style>
</head>
<body>
  <header><strong>{title}</strong></header>
  <main>
    <div class="card">
      <p>Модуль <code>{key}</code> подключён ядром. Статус API: <span id="st">…</span></p>
    </div>
  </main>
  <script>
    // Базу адреса берём у сервера, не пишем строкой: модуль не привязан к точке монтирования
    fetch("{{{{ url_for('{key}.api_status') }}}}")
      .then(r => r.json()).then(j => document.getElementById("st").textContent = JSON.stringify(j.data || j));
  </script>
</body>
</html>
'''


def t_sql(key: str, prefix: str, num: int) -> str:
    return f'''
-- {prefix}_: Oracle-объекты модуля {key}. Нормализованная схема, свой префикс.
-- Ставится ТОЛЬКО своим установщиком modules/{key}/scripts/{key}_deploy.py.
-- '/' обязателен и ПЕРЕД, и ПОСЛЕ каждого PL/SQL-блока (CLAUDE.md, §2 п.5).

CREATE TABLE {prefix}_SETTINGS (
  ID          NUMBER        NOT NULL,
  CODE        VARCHAR2(50)  NOT NULL,
  VALUE       VARCHAR2(500),
  UPDATED_AT  TIMESTAMP     DEFAULT SYSTIMESTAMP,
  CONSTRAINT PK_{prefix}_SETTINGS PRIMARY KEY (ID),
  CONSTRAINT UK_{prefix}_SETTINGS_CODE UNIQUE (CODE)
);

CREATE SEQUENCE {prefix}_SETTINGS_SEQ START WITH 1 INCREMENT BY 1 NOCACHE;
/
CREATE OR REPLACE TRIGGER {prefix}_SETTINGS_BI
BEFORE INSERT ON {prefix}_SETTINGS FOR EACH ROW
BEGIN
  IF :NEW.ID IS NULL THEN
    SELECT {prefix}_SETTINGS_SEQ.NEXTVAL INTO :NEW.ID FROM DUAL;
  END IF;
END;
/
'''


def t_deploy(key: str, sql_file: str) -> str:
    return f'''
#!/usr/bin/env python3
"""Установщик DDL модуля {key} — СВОЙ, общий deploy_oracle_objects.py не трогаем.

    python modules/{key}/scripts/{key}_deploy.py            # установить
    python modules/{key}/scripts/{key}_deploy.py --dry-run  # только разбор

--dry-run не доказывает, что схема встанет (CLAUDE.md §2 п.5): прогнать вживую.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

# Разбор SQL берём у общего установщика, чтобы не дублировать логику
from deploy_oracle_objects import _is_comment_only, _is_plsql_block, _split_ddl_dml, _sql_blocks  # noqa: E402

FILES = ["{sql_file}"]
SQL_DIR = Path(__file__).resolve().parents[1] / "sql"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    stmts = []
    for name in FILES:
        text = (SQL_DIR / name).read_text(encoding="utf-8")
        for block in _sql_blocks(text):
            if _is_comment_only(block):
                continue
            stmts += [block] if _is_plsql_block(block) else [s for s in _split_ddl_dml(block) if not _is_comment_only(s)]
    print(f"команд к выполнению: {{len(stmts)}}")
    if args.dry_run:
        return

    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    from models.database import DatabaseConnection
    conn = DatabaseConnection.get_connection()
    cur = conn.cursor()
    ok = err = 0
    for s in stmts:
        try:
            cur.execute(s.rstrip().rstrip("/").rstrip())
            conn.commit()
            ok += 1
        except Exception as e:  # noqa: BLE001
            print(f"  ошибка: {{str(e)[:160]}}")
            err += 1
    print(f"готово: успешно {{ok}}, ошибок {{err}}")
    sys.exit(1 if err else 0)


if __name__ == "__main__":
    main()
'''


def t_module_json(key: str, title: str, prefix: str, icon: str, doc_dir: str) -> str:
    return json.dumps({
        "title": {"ru": title, "ro": title, "en": title},
        "icon": icon,
        "order": 200,
        "url": f"/UNA.md/orasldev/{key}",
        "sql_prefix": f"{prefix}_",
        "descr": f"Модуль {title}",
        "docs": doc_dir,
        "pages": {key: {"ru": title, "ro": title, "en": title}},
    }, ensure_ascii=False, indent=2) + "\n"


def t_tests(key: str, prefix: str) -> str:
    return f'''
"""Тесты модуля {key}. Два первых — обязательные тесты изоляции (CLAUDE.md, правило №1)."""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


def test_shared_app_py_does_not_mention_the_module():
    # Модуль подключает ядро; в app.py ему делать нечего.
    src = _read("app.py")
    assert not re.search(r"\\b{key}\\b", src), "app.py упоминает модуль — нарушена изоляция"


def test_shared_deploy_script_is_untouched_by_the_module():
    src = _read("deploy_oracle_objects.py")
    assert "{prefix}_" not in src and "{key}" not in src.lower(), \\
        "общий установщик знает о модуле — у модуля должен быть свой scripts/{key}_deploy.py"


def test_module_exports_blueprint_named_after_key():
    from modules.{key} import blueprint
    assert blueprint.name == "{key}"


def test_rules_are_pure():
    from modules.{key} import rules
    assert rules.normalize_code("  ab c ") == "AB C"
'''


def t_readme(key: str, title: str, prefix: str) -> str:
    return f'''
# {title} (`{key}`)

Изолированный модуль Artgranit поверх общего ядра. Создан `scripts/new_module.py`.

| Что | Где |
|---|---|
| URL | `/UNA.md/orasldev/{key}` |
| Пакет | `modules/{key}/` |
| Oracle-префикс | `{prefix}_` (DDL в `modules/{key}/sql/`, установщик `modules/{key}/scripts/{key}_deploy.py`) |
| Тесты | `tests/test_{key}.py` (изоляция + правила) |
| Ветка / worktree | `feat/{key}` / `../Artgranit-{key}` |

## Журнал изменений

- **создание каркаса** — worktree, ветка, пакет, тесты изоляции, документация.
  Проверка: `pytest tests/test_{key}.py`; `git diff --name-only main HEAD` — только свои пути.
'''


def t_docs_json(title: str) -> str:
    return json.dumps({"README.md": {"slug": "readme", "public": False, "icon": "◆", "cls": "g", "order": 10,
                                     "title": title, "audience": "для разработчиков",
                                     "descr": "Паспорт модуля: адреса, префикс Oracle, тесты, журнал изменений."}},
                      ensure_ascii=False, indent=2) + "\n"


# --------------------------------------------------------------------------- main

def main() -> None:
    ap = argparse.ArgumentParser(description="Новый изолированный модуль Artgranit")
    ap.add_argument("key", help="ключ модуля: латиница, цифры, подчёркивание (carwash)")
    ap.add_argument("title", help="название для меню и документации")
    ap.add_argument("--prefix", help="префикс Oracle-объектов (по умолчанию из ключа, до 5 букв)")
    ap.add_argument("--icon", default="🧩")
    ap.add_argument("--no-git", action="store_true", help="без worktree/коммита — только файлы в текущем каталоге")
    a = ap.parse_args()

    key = a.key.lower()
    if not re.fullmatch(r"[a-z][a-z0-9_]{1,30}", key):
        sys.exit("ключ: латиница/цифры/подчёркивание, начиная с буквы")
    if (ROOT / "modules" / key).exists():
        sys.exit(f"modules/{key} уже существует")
    prefix = (a.prefix or re.sub(r"[^A-Z]", "", key.upper())[:5]).upper().rstrip("_")
    doc_dir = key.capitalize()

    # 1. worktree + ветка от свежего main
    if a.no_git:
        base = ROOT
    else:
        base = ROOT.parent / f"Artgranit-{key}"
        branch = f"feat/{key}"
        if base.exists():
            sys.exit(f"{base} уже существует")
        sh(["git", "fetch", "origin", "main"])
        sh(["git", "worktree", "add", "-b", branch, str(base), "origin/main"])
        print(f"✓ worktree {base} на ветке {branch}")

    m = base / "modules" / key
    sql_file = f"200_{prefix.lower()}_tables.sql"
    print("каркас модуля:")
    write(m / "__init__.py", t_init(key, a.title))
    write(m / "routes.py", t_routes(key, a.title))
    write(m / "controller.py", t_controller(key, a.title))
    write(m / "store.py", t_store(key, prefix))
    write(m / "rules.py", t_rules(key))
    write(m / "module.json", t_module_json(key, a.title, prefix, a.icon, doc_dir))
    write(m / "templates" / f"{key}.html", t_template(key, a.title))
    write(m / "sql" / sql_file, t_sql(key, prefix, 200))
    write(m / "scripts" / "__init__.py", "")
    write(m / "scripts" / f"{key}_deploy.py", t_deploy(key, sql_file))
    write(base / "tests" / f"test_{key}.py", t_tests(key, prefix))
    write(base / "docs" / doc_dir / "README.md", t_readme(key, a.title, prefix))
    write(base / "docs" / doc_dir / "docs.json", t_docs_json(a.title))

    if a.no_git:
        print("✓ файлы созданы (без git)")
        return

    # 2. первый коммит и push
    sh(["git", "add", f"modules/{key}", f"tests/test_{key}.py", f"docs/{doc_dir}"], cwd=base)
    sh(["git", "commit", "-q", "-m", f"{key}: каркас изолированного модуля «{a.title}»\n\n"
        f"Создан scripts/new_module.py: blueprint, тесты изоляции, docs/{doc_dir}/, DDL {prefix}_."], cwd=base)
    sh(["git", "push", "-u", "origin", branch], cwd=base)
    print(f"✓ коммит и push {branch}")
    print(f"\nДальше работать ТОЛЬКО в {base}\n"
          f"  cd {base} && pytest tests/test_{key}.py\n"
          f"  python modules/{key}/scripts/{key}_deploy.py --dry-run")


if __name__ == "__main__":
    main()
'''
