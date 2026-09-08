#!/usr/bin/env python3
"""Загрузка готовых писем поставщикам (.eml + .xlsx) в FRZ_LETTER / FRZ_LETTER_FILE.

    python modules/furnizori/scripts/furnizori_load_letters.py --dir <папка> [--dry-run]

Папка — та, где лежат пары `Scrisoare_<КОД>.eml` и `Denumiri_de_corectat_<КОД>.xlsx`
(их готовит BIRO26). Тема, адрес и число позиций читаются из самого .eml, чтобы
руками ничего не переписывать и не разойтись с тем, что реально отправлено.

Повторный запуск не плодит дублей: письмо узнаётся по SHA-256 вложенного .eml.
"""
import argparse
import email
import hashlib
import re
import sys
from email import policy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def parse_eml(path: Path) -> dict:
    """Тема, получатель и число позиций — из самого письма."""
    msg = email.message_from_bytes(path.read_bytes(), policy=policy.default)
    to = str(msg.get("To") or "")
    addr = re.search(r"<([^>]+@[^>]+)>", to)
    subj = str(msg.get("Subject") or path.stem)
    n = re.search(r"(\d+)\s*pozitii", subj)
    name = re.sub(r"\s*<[^>]*>\s*$", "", to).strip().strip('"') \
        or path.stem.replace("Scrisoare_", "")
    return {"furnizor": name, "subiect": subj,
            "sent_to": addr.group(1) if addr else None,
            "n_pozitii": int(n.group(1)) if n else None}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="папка с Scrisoare_*.eml")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    src_dir = Path(args.dir).expanduser()
    emls = sorted(src_dir.glob("Scrisoare_*.eml"))
    if not emls:
        sys.exit(f"в {src_dir} нет файлов Scrisoare_*.eml")

    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    from modules.furnizori import store

    # Уже загруженные .eml — по отпечатку, чтобы повтор не создал второе письмо
    seen = set()
    if not args.dry_run:
        from models.database import DatabaseModel
        with DatabaseModel() as db:
            r = db.execute_query(
                "SELECT FILE_SHA256 FROM FRZ_LETTER_FILE WHERE FILE_KIND = 'EML'")
            seen = {row[0] for row in (r.get("data") or [])}

    # Имя файла = наш рабочий код, а в реестре источник называется иначе:
    # грузили мы из объединённого retail+angro, «голый» OFFICESHOP выключен.
    ALIAS = {"OFFICESHOP": "OFFICESHOP_MERGED"}

    created = skipped = 0
    for eml in emls:
        fcode = eml.stem.replace("Scrisoare_", "")   # как называются файлы
        code = ALIAS.get(fcode, fcode)               # как называется источник
        blob = eml.read_bytes()
        sha = hashlib.sha256(blob).hexdigest()
        meta = parse_eml(eml)
        xlsx = src_dir / f"Denumiri_de_corectat_{fcode}.xlsx"

        if sha in seen:
            print(f"  = {fcode:12s} уже загружено, пропуск")
            skipped += 1
            continue
        print(f"  + {fcode:12s} {meta['furnizor'][:22]:22s} позиций={meta['n_pozitii']} "
              f"файлы: eml{' + xlsx' if xlsx.exists() else ''}")
        if args.dry_run:
            continue

        lid = store.create_letter({
            "src_code": code, "furnizor": meta["furnizor"], "subiect": meta["subiect"],
            "tip": "DENUMIRI", "n_pozitii": meta["n_pozitii"],
            "sent_to": meta["sent_to"], "status": "NOU",
            "notes": "Письмо об исправлении наименований (смешанные алфавиты). "
                     "Подготовлено BIRO26, аудит гомоглифов.",
        }, user="import")
        store.add_file(lid, eml.name, blob, user="import")
        if xlsx.exists():
            store.add_file(lid, xlsx.name, xlsx.read_bytes(), user="import")
        created += 1

    print(f"\nсоздано писем: {created}, пропущено: {skipped}")


if __name__ == "__main__":
    main()
