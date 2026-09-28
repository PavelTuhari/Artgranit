#!/usr/bin/env python3
"""SEOForge — конфигурация модуля в дереве uniConf боевой ERP.

Контур `YSEO_*` хранит план, факт и метрики, но документы маркетинга живут
в общем учёте UNA. Чтобы они там появились, в конфигурации нужно завести
журнал и типовые документы: клиент UNA строит меню и списки по дереву
`A$ADM$V`, а не по коду.

## Как это устроено (проверено в базе 25.08.2026)

- `TMDB_DOCS.SYSFID` = свойство `DB ID` узла-документа (`OBJ_TYPE=1`,
  `OBJ_SUBTYPE=0`). Именно `SYSFID`, а не `TIPDOC`, различает типы
  документов: `TIPDOC` в этой базе пуст у всех 193 документов.
- Журнал (`OBJ_TYPE=2`, `OBJ_SUBTYPE=0`) отбирает документы свойствами
  `SQLFILTER` (по `SYSFID`) и `DOCTYPESFILTER` (по `id`), а `DOCTYPESDEFAULT`
  задаёт тип для кнопки «новый документ».
- Документ исполняется DLL: пара `DLL ID` + `DOCNAME`. Закупку услуг в этой
  базе ведёт DLL `20` / `201` — на ней сидят «Покупка услуг от фирм РМ»
  и «Акт закупки услуг».

## Почему копия, а не набор свойств с нуля

У рабочего документа 47–52 свойства, 5–9 дочерних узлов (Actions, PrintForm,
Total) и 3–6 LOB — форма, гриды, печатные шаблоны. Собрать это вручную
и не промахнуться нельзя, а промах виден пользователю как сломанная форма.
Поэтому типовые документы копируются с ближайших по смыслу работающих
документов, и меняются только имя, секция и `DB ID`.

## Диапазон

`DB ID` 60000..60099 зарезервирован за маркетингом: на момент установки
он свободен и в конфигурации, и в данных (проверяется перед записью).

    venv/bin/python scripts/seoforge_erp_config.py --dry-run
    venv/bin/python scripts/seoforge_erp_config.py --yes
"""
from __future__ import annotations

import argparse
import os
import sys

# Скрипт лежит в modules/seoforge/scripts/, корень проекта — на три уровня выше.
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.chdir(ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT, ".env"))

from models.biro26_db import Biro26DB  # noqa: E402

DBID_FROM, DBID_TO = 60000, 60099

JOURNAL_GROUP_SECTION = "J_SEO_MARKETING"
JOURNAL_SECTION = "J_SEO_DOCS"
DOCGROUP_SECTION = "SEO_MARKETING"

# Типовые документы: (секция, имя, DB ID, секция-источник для копии).
DOCUMENTS = (
    ("SEO_ACHIZ_RECLAMA", "Закупка рекламных услуг", 60001, "2:1:FS_48101"),
    ("SEO_ACT_PLASARE", "Акт о размещении рекламы", 60002, "2:0:FS_48106"),
)


class Cfg:
    def __init__(self, db):
        self.db = db

    def rows(self, sql, params=None):
        r = self.db.execute_query(sql, params or {})
        if not r.get("success"):
            raise RuntimeError(r.get("message", "")[:200])
        cols = [c.lower() for c in (r.get("columns") or [])]
        return [dict(zip(cols, row)) for row in (r.get("data") or [])]

    def scalar(self, sql, params=None):
        rows = self.rows(sql, params)
        return list(rows[0].values())[0] if rows else None

    def node_by_section(self, section):
        rows = self.rows(
            "SELECT OBJ_ID, NAME, PARENT_ID, OBJ_TYPE, OBJ_SUBTYPE "
            "FROM A$ADM$V WHERE UPPER(SECTION) = UPPER(:s)", {"s": section})
        return rows[0] if rows else None

    def next_id(self):
        return int(self.scalar("SELECT A$ADM$SQ.NEXTVAL FROM DUAL"))

    def children(self, obj_id):
        return self.rows(
            "SELECT OBJ_ID, OBJ_TYPE, OBJ_SUBTYPE, NAME, SECTION, NRORD, LINK_ID "
            "FROM A$ADM$V WHERE PARENT_ID = :p ORDER BY OBJ_SUBTYPE, NRORD",
            {"p": obj_id})


def node_insert(obj_id, obj_type, obj_subtype, parent_id, name, section, nrord=0):
    return ("INSERT INTO A$ADM$V (OBJ_ID, OBJ_TYPE, OBJ_SUBTYPE, PARENT_ID, "
            "NAME, NAME0, NAME1, NAME2, SECTION, NRORD) "
            "VALUES (:obj_id, :obj_type, :obj_subtype, :parent_id, "
            ":name, :name, :name, :name, :section, :nrord)",
            {"obj_id": obj_id, "obj_type": obj_type, "obj_subtype": obj_subtype,
             "parent_id": parent_id, "name": name,
             "section": section.upper(), "nrord": nrord})


def prop_insert(obj_id, name, vtype, value="", lvalue=""):
    return ("INSERT INTO A$ADP$V (OBJ_ID, NAME, HINT, GR, ATTR, VTYPE, "
            "VALUE, VALUE0, VALUE1, VALUE2, LVALUE) "
            "VALUES (:obj_id, :name, '', 'Общая', '', :vtype, "
            ":value, :value, :value, :value, :lvalue)",
            {"obj_id": obj_id, "name": name, "vtype": vtype,
             "value": value, "lvalue": lvalue})


def props_copy(new_id, src_id):
    return ("INSERT INTO A$ADP$V (OBJ_ID, NAME, HINT, GR, ATTR, VTYPE, "
            "VALUE, VALUE0, VALUE1, VALUE2, LVALUE) "
            "SELECT :new_id, NAME, HINT, GR, ATTR, VTYPE, "
            "VALUE, VALUE0, VALUE1, VALUE2, LVALUE "
            "FROM A$ADP$V WHERE OBJ_ID = :src_id",
            {"new_id": new_id, "src_id": src_id})


def lobs_copy(new_id, src_id):
    return ("INSERT INTO A$LOB (OBJ_ID, USER_ID, LOB_TYPE, LOB_NAME, "
            "LOB_VALUE, TIME_STAMP) "
            "SELECT :new_id, USER_ID, LOB_TYPE, LOB_NAME, LOB_VALUE, TIME_STAMP "
            "FROM A$LOB WHERE OBJ_ID = :src_id",
            {"new_id": new_id, "src_id": src_id})


def prop_set(obj_id, name, value):
    return ("UPDATE A$ADP$V SET VALUE = :value, VALUE0 = :value, "
            "VALUE1 = :value, VALUE2 = :value "
            "WHERE OBJ_ID = :obj_id AND UPPER(NAME) = UPPER(:name)",
            {"obj_id": obj_id, "name": name, "value": value})


def copy_subtree(cfg, src_id, new_id, new_section, statements, depth=0):
    """Свойства, LOB и детей узла — в новый узел.

    Секции детей получают префикс новой секции: SECTION уникален по всему
    дереву, а копия иначе столкнулась бы с оригиналом.
    """
    statements.append(props_copy(new_id, src_id))
    statements.append(lobs_copy(new_id, src_id))

    for kid in cfg.children(src_id):
        kid_new_id = cfg.next_id()
        kid_section = f"{new_section}:{kid['obj_subtype']}:{kid_new_id}"
        statements.append(node_insert(
            kid_new_id, kid["obj_type"], kid["obj_subtype"], new_id,
            kid["name"], kid_section, kid.get("nrord") or 0))
        copy_subtree(cfg, kid["obj_id"], kid_new_id, kid_section,
                     statements, depth + 1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Конфигурация SEOForge в дереве uniConf боевой ERP")
    parser.add_argument("--yes", action="store_true",
                        help="подтвердить запись в конфигурацию боевой ERP")
    parser.add_argument("--dry-run", action="store_true",
                        help="показать план, ничего не менять")
    args = parser.parse_args()

    if not args.yes and not args.dry_run:
        print("Это конфигурация БОЕВОЙ ERP. Запускайте с --yes либо --dry-run.")
        sys.exit(2)

    db = Biro26DB()
    probe = db.test_connection()
    if not probe.get("success"):
        print(f"Нет связи с ERP: {probe.get('error')}")
        sys.exit(1)
    cfg = Cfg(db)
    print(f"ERP: {probe.get('version')}")
    print(f"Схема: {cfg.scalar('SELECT USER FROM DUAL')}\n")

    # ── проверки до записи ───────────────────────────────────────────
    busy_cfg = cfg.scalar(
        "SELECT COUNT(*) FROM A$ADP$V WHERE UPPER(NAME) = 'DB ID' "
        "AND REGEXP_LIKE(VALUE, '^[0-9]+$') "
        "AND TO_NUMBER(VALUE) BETWEEN :a AND :b",
        {"a": DBID_FROM, "b": DBID_TO})
    busy_data = cfg.scalar(
        "SELECT COUNT(*) FROM TMDB_DOCS WHERE SYSFID BETWEEN :a AND :b",
        {"a": DBID_FROM, "b": DBID_TO})
    print(f"Диапазон DB ID {DBID_FROM}..{DBID_TO}: "
          f"в конфигурации занято {busy_cfg}, документов в данных {busy_data}")
    if busy_cfg or busy_data:
        print("Диапазон занят — установка остановлена, чтобы не перекрыть чужие типы.")
        sys.exit(1)

    existing = [s for s in (JOURNAL_GROUP_SECTION, JOURNAL_SECTION,
                            DOCGROUP_SECTION, *(d[0] for d in DOCUMENTS))
                if cfg.node_by_section(s)]
    if existing:
        print("Уже созданы, повторная установка не нужна: " + ", ".join(existing))
        sys.exit(0)

    sources = {}
    for section, name, dbid, src_section in DOCUMENTS:
        src = cfg.node_by_section(src_section)
        if not src:
            print(f"Не найден документ-источник {src_section}")
            sys.exit(1)
        sources[section] = src
        print(f"Источник для «{name}»: {src_section} "
              f"(OBJ_ID={src['obj_id']}, «{src['name']}»)")

    # ── план ─────────────────────────────────────────────────────────
    statements = []

    jgroup_id = cfg.next_id()
    statements.append(node_insert(jgroup_id, 2, -1, None,
                                  "Маркетинг", JOURNAL_GROUP_SECTION, jgroup_id))
    statements.append(prop_insert(jgroup_id, "ACTIVE", "B", "true"))
    statements.append(prop_insert(jgroup_id, "CAPTION", "C", "25. Маркетинг"))

    journal_id = cfg.next_id()
    statements.append(node_insert(journal_id, 2, 0, jgroup_id,
                                  "SEOForge: документы", JOURNAL_SECTION, journal_id))
    statements.append(prop_insert(journal_id, "ACTIVE", "B", "true"))
    statements.append(prop_insert(journal_id, "CAPTION", "S",
                                  "25.1 Документы маркетинга"))
    statements.append(prop_insert(journal_id, "DLL ID", "I", "0"))
    statements.append(prop_insert(
        journal_id, "SQLFILTER", "M", "",
        f"(SYSFID >= {DBID_FROM} and SYSFID <= {DBID_TO})"))
    statements.append(prop_insert(
        journal_id, "DOCTYPESFILTER", "M", "",
        f"(id >= {DBID_FROM} and id <= {DBID_TO})"))
    statements.append(prop_insert(journal_id, "DOCTYPESDEFAULT", "I",
                                  str(DOCUMENTS[0][2])))

    dgroup_id = cfg.next_id()
    statements.append(node_insert(dgroup_id, 1, -1, None,
                                  "Маркетинг", DOCGROUP_SECTION, dgroup_id))

    created_docs = []
    for section, name, dbid, src_section in DOCUMENTS:
        src = sources[section]
        doc_id = cfg.next_id()
        statements.append(node_insert(doc_id, 1, 0, dgroup_id, name, section, doc_id))
        copy_subtree(cfg, src["obj_id"], doc_id, section, statements)
        statements.append(prop_set(doc_id, "DB ID", str(dbid)))
        created_docs.append((doc_id, section, name, dbid, src_section))

    print(f"\nБудет выполнено команд: {len(statements)}")
    print(f"  группа журналов {JOURNAL_GROUP_SECTION} (OBJ_ID={jgroup_id})")
    print(f"  журнал {JOURNAL_SECTION} (OBJ_ID={journal_id}), "
          f"фильтр SYSFID {DBID_FROM}..{DBID_TO}")
    print(f"  группа документов {DOCGROUP_SECTION} (OBJ_ID={dgroup_id})")
    for doc_id, section, name, dbid, src_section in created_docs:
        print(f"  документ {section} (OBJ_ID={doc_id}, DB ID={dbid}) "
              f"— копия {src_section}, «{name}»")

    if args.dry_run:
        print("\n[dry-run] Ничего не записано.")
        return

    script = [{"sql": sql, "params": params, "kind": "dml"}
              for sql, params in statements]
    result = db.execute_script(script)
    if not result.get("success"):
        print("\nОШИБКА, транзакция откачена целиком:")
        print("  " + (result.get("message", "").splitlines() or [""])[0][:200])
        sys.exit(1)

    print("\nЗаписано. Проверка:")
    for section in (JOURNAL_GROUP_SECTION, JOURNAL_SECTION, DOCGROUP_SECTION,
                    *(d[0] for d in DOCUMENTS)):
        node = cfg.node_by_section(section)
        print(f"  {section}: OBJ_ID={node['obj_id'] if node else '—'}")

    for doc_id, section, name, dbid, _src in created_docs:
        got = cfg.scalar(
            "SELECT VALUE FROM A$ADP$V WHERE OBJ_ID = :o AND UPPER(NAME) = 'DB ID'",
            {"o": doc_id})
        kids = cfg.scalar("SELECT COUNT(*) FROM A$ADM$V WHERE PARENT_ID = :o",
                          {"o": doc_id})
        props = cfg.scalar("SELECT COUNT(*) FROM A$ADP$V WHERE OBJ_ID = :o",
                           {"o": doc_id})
        print(f"  {section}: DB ID={got} (ожидали {dbid}), "
              f"свойств {props}, дочерних узлов {kids}")


if __name__ == "__main__":
    main()
