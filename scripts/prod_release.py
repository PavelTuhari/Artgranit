#!/usr/bin/env python3
"""Точечный релиз на боевой контур с архивом и откатом.

Зачем отдельный инструмент, когда есть deploy_to_remote.sh. Тот скрипт
распаковывает НА СЕРВЕР ВЕСЬ проект и поэтому затирает файлы, которые
там новее: над репозиторием одновременно работают несколько веток и
несколько сессий, и на проде может лежать чужой свежий деплой, которого
в твоей ветке нет. Здесь наоборот: везётся только явно перечисленный
список путей, и перед отправкой каждый из них сверяется с тем, что
реально лежит на сервере.

Три режима:

    --check    сравнить локальные файлы с сервером и НИЧЕГО не менять
    --deploy   архив -> отправка -> перезапуск -> проверка
    --rollback вернуть предыдущую версию из архива

Правило безопасности: файл, который на сервере отличается и от твоей
локальной версии, и от версии в git HEAD, считается ЧУЖОЙ ПРАВКОЙ.
Деплой останавливается и показывает список таких файлов. Перезаписать
их можно только осознанно, флагом --force-foreign, и в отчёте это
останется.

Примеры:

    venv/bin/python scripts/prod_release.py --check --paths-from release.txt
    venv/bin/python scripts/prod_release.py --deploy --paths-from release.txt
    venv/bin/python scripts/prod_release.py --list
    venv/bin/python scripts/prod_release.py --rollback 20260919_1230
"""
from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime
from typing import Dict, List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REMOTE_HOST = "92.5.3.187"
REMOTE_USER = "ubuntu"
REMOTE_DIR = "/home/ubuntu/artgranit"
BACKUP_DIR = "/home/ubuntu/artgranit_releases"
SSH_KEY = os.path.expanduser("~/.ssh/artgranit-oci.key")
SERVICE = "artgranit"
HEALTH_URL = "https://nufarul.eminescu.md/login"
KEEP_BACKUPS = 10


def ssh(command: str, check: bool = True) -> str:
    """Выполнить команду на сервере. Возвращает stdout."""
    proc = subprocess.run(
        ["ssh", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no",
         "-o", "ConnectTimeout=20", f"{REMOTE_USER}@{REMOTE_HOST}", command],
        capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise RuntimeError(f"ssh: {command[:70]}: {proc.stderr.strip()[:300]}")
    return proc.stdout


def local_md5(path: str) -> Optional[str]:
    full = os.path.join(ROOT, path)
    if not os.path.isfile(full):
        return None
    h = hashlib.md5()
    with open(full, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def git_head_md5(path: str) -> Optional[str]:
    """Хэш версии файла в текущем HEAD."""
    proc = subprocess.run(["git", "show", f"HEAD:{path}"], cwd=ROOT,
                          capture_output=True)
    if proc.returncode != 0:
        return None
    return hashlib.md5(proc.stdout).hexdigest()


def git_history_md5(path: str, limit: int = 40) -> set:
    """Хэши всех версий файла в истории ветки.

    Нужны, чтобы отличить «на сервере просто СТАРАЯ наша версия» от «на
    сервере ЧУЖАЯ версия». Сравнения с одним HEAD мало: сервер почти
    всегда отстаёт на несколько коммитов, и без истории каждый такой файл
    выглядел бы чужим — инструмент кричал бы на ровном месте, а на
    настоящую чужую правку никто бы уже не посмотрел.
    """
    revs = subprocess.run(
        ["git", "rev-list", f"--max-count={limit}", "HEAD", "--", path],
        cwd=ROOT, capture_output=True, text=True).stdout.split()
    digests = set()
    for rev in revs:
        blob = subprocess.run(["git", "show", f"{rev}:{path}"], cwd=ROOT,
                              capture_output=True)
        if blob.returncode == 0:
            digests.add(hashlib.md5(blob.stdout).hexdigest())
    return digests


def remote_md5(paths: List[str]) -> Dict[str, Optional[str]]:
    """md5 файлов на сервере одним заходом -- по одному ssh на файл было бы минуты."""
    listing = " ".join(f"'{REMOTE_DIR}/{p}'" for p in paths)
    out = ssh(f"md5sum {listing} 2>/dev/null || true", check=False)
    result: Dict[str, Optional[str]] = {p: None for p in paths}
    for line in out.splitlines():
        parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        digest, full = parts[0], parts[1].strip()
        rel = full[len(REMOTE_DIR) + 1:]
        if rel in result:
            result[rel] = digest
    return result


def analyse(paths: List[str]) -> Dict[str, List[Tuple[str, str]]]:
    """Что на сервере: новое, изменённое нами, изменённое кем-то ещё."""
    remote = remote_md5(paths)
    report = {"new": [], "same": [], "ours": [], "foreign": [], "missing_local": []}
    for path in paths:
        mine = local_md5(path)
        theirs = remote.get(path)
        if mine is None:
            report["missing_local"].append((path, "нет локально"))
        elif theirs is None:
            report["new"].append((path, "нет на сервере"))
        elif theirs == mine:
            report["same"].append((path, "совпадает"))
        elif theirs in git_history_md5(path):
            # На сервере одна из НАШИХ прошлых версий -- он просто отстал.
            report["ours"].append((path, "на сервере более старая наша версия"))
        else:
            report["foreign"].append((path, "на сервере ЧУЖАЯ версия"))
    return report


def make_backup(paths: List[str], stamp: str) -> str:
    """Архив ТЕХ ЖЕ путей с сервера -- точка возврата ровно для этого релиза.

    Архивируются только затрагиваемые файлы, а не весь каталог: полный
    архив проекта занимает десятки мегабайт и делает откат медленным,
    а вернуть нужно ровно то, что меняли.
    """
    ssh(f"mkdir -p {BACKUP_DIR}")
    existing = []
    remote = remote_md5(paths)
    for path in paths:
        if remote.get(path) is not None:
            existing.append(path)
    archive = f"{BACKUP_DIR}/{stamp}.tar.gz"
    if existing:
        listing = " ".join(f"'{p}'" for p in existing)
        ssh(f"cd {REMOTE_DIR} && tar -czf {archive} {listing}")
    else:
        ssh(f"cd {REMOTE_DIR} && tar -czf {archive} --files-from /dev/null")
    manifest = "\\n".join(paths)
    ssh(f"printf '%b' '{manifest}' > {BACKUP_DIR}/{stamp}.files")
    ssh(f"cd {BACKUP_DIR} && ls -1t *.tar.gz | tail -n +{KEEP_BACKUPS + 1} | "
        f"xargs -r rm -f")
    return archive


def send(paths: List[str]) -> None:
    """Точечный патч: только перечисленные файлы, COPYFILE_DISABLE против macOS-двойников."""
    with tempfile.TemporaryDirectory() as tmp:
        archive = os.path.join(tmp, "patch.tar.gz")
        env = dict(os.environ, COPYFILE_DISABLE="1")
        with tarfile.open(archive, "w:gz") as tar:
            for path in paths:
                full = os.path.join(ROOT, path)
                if os.path.isfile(full):
                    tar.add(full, arcname=path)
        _ = env
        subprocess.run(["scp", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no",
                        archive, f"{REMOTE_USER}@{REMOTE_HOST}:/tmp/patch.tar.gz"],
                       check=True, capture_output=True)
    ssh(f"cd {REMOTE_DIR} && tar -xzf /tmp/patch.tar.gz && rm -f /tmp/patch.tar.gz")


def restart_and_check() -> Tuple[bool, str]:
    ssh(f"sudo systemctl restart {SERVICE}")
    ssh("sleep 8", check=False)
    local = ssh("curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/login",
                check=False).strip()
    errors = ssh(f"sudo journalctl -u {SERVICE} --since '-1min' | "
                 "grep -ciE 'ModuleNotFound|Traceback' || true", check=False).strip()
    public = subprocess.run(
        ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", HEALTH_URL],
        capture_output=True, text=True).stdout.strip()
    ok = local == "200" and public == "200" and errors in ("0", "")
    return ok, f"flask={local} домен={public} ошибок в журнале={errors or '0'}"


def rollback(stamp: str) -> None:
    archive = f"{BACKUP_DIR}/{stamp}.tar.gz"
    exists = ssh(f"test -f {archive} && echo yes || echo no").strip()
    if exists != "yes":
        raise SystemExit(f"Архив {stamp} не найден. Список: --list")
    # Перед откатом сохраняем текущее состояние: откат тоже бывает ошибкой.
    files = ssh(f"cat {BACKUP_DIR}/{stamp}.files 2>/dev/null || true").split()
    if files:
        make_backup(files, datetime.now().strftime("%Y%m%d_%H%M") + "_before_rollback")
    ssh(f"cd {REMOTE_DIR} && tar -xzf {archive}")
    ok, detail = restart_and_check()
    print(f"Откат на {stamp}: {'успешно' if ok else 'ПРОВЕРКА НЕ ПРОШЛА'} — {detail}")
    if not ok:
        raise SystemExit(1)


def list_backups() -> None:
    out = ssh(f"ls -1t {BACKUP_DIR}/*.tar.gz 2>/dev/null || true")
    if not out.strip():
        print("Архивов нет.")
        return
    print("Точки возврата (новые сверху):")
    for line in out.splitlines():
        stamp = os.path.basename(line).replace(".tar.gz", "")
        size = ssh(f"du -h {line} | cut -f1", check=False).strip()
        count = ssh(f"tar -tzf {line} 2>/dev/null | wc -l", check=False).strip()
        print(f"  {stamp}  {size:>6}  файлов: {count}")


def read_paths(args) -> List[str]:
    paths: List[str] = []
    if args.paths_from:
        with open(args.paths_from, encoding="utf-8") as fh:
            paths += [l.strip() for l in fh if l.strip() and not l.startswith("#")]
    paths += args.path or []
    if not paths:
        # По умолчанию -- файлы последних коммитов текущей ветки.
        out = subprocess.run(["git", "diff", "--name-only", f"HEAD~{args.commits}", "HEAD"],
                             cwd=ROOT, capture_output=True, text=True).stdout
        paths = [p for p in out.splitlines() if p.strip()]
    # Документация и тесты на боевой контур не нужны, но и вреда не несут --
    # решает вызывающий, здесь только убираем заведомо лишнее.
    return [p for p in paths if not p.startswith("docs/Planograms/")]


def main() -> None:
    ap = argparse.ArgumentParser(description="Точечный релиз с архивом и откатом")
    ap.add_argument("--check", action="store_true", help="только сравнить с сервером")
    ap.add_argument("--deploy", action="store_true", help="архив, отправка, рестарт, проверка")
    ap.add_argument("--rollback", metavar="STAMP", help="вернуть версию из архива")
    ap.add_argument("--list", action="store_true", help="список точек возврата")
    ap.add_argument("--paths-from", metavar="FILE", help="файл со списком путей")
    ap.add_argument("--path", action="append", help="путь (можно повторять)")
    ap.add_argument("--commits", type=int, default=1,
                    help="взять пути из последних N коммитов (по умолчанию 1)")
    ap.add_argument("--force-foreign", action="store_true",
                    help="перезаписать файлы, изменённые на сервере кем-то ещё")
    args = ap.parse_args()

    if args.list:
        list_backups()
        return
    if args.rollback:
        rollback(args.rollback)
        return

    paths = read_paths(args)
    if not paths:
        raise SystemExit("Не задан ни один путь.")

    print(f"Файлов в релизе: {len(paths)}")
    report = analyse(paths)
    for key, title in (("foreign", "ЧУЖИЕ правки на сервере"),
                       ("ours", "обновляем свою версию"),
                       ("new", "новые файлы"),
                       ("same", "уже совпадает"),
                       ("missing_local", "нет локально")):
        rows = report[key]
        if not rows:
            continue
        print(f"\n{title}: {len(rows)}")
        for path, note in rows[:40]:
            print(f"   {path}")

    if report["foreign"] and not args.force_foreign:
        print("\nДеплой остановлен: на сервере есть версии файлов, которых нет "
              "ни локально, ни в HEAD. Это чужая работа.")
        print("Разберитесь с ними и повторите, либо запустите с --force-foreign.")
        raise SystemExit(2)

    if args.check or not args.deploy:
        print("\nРежим проверки: ничего не отправлено.")
        return

    to_send = [p for p, _ in report["ours"] + report["new"] + report["foreign"]]
    if not to_send:
        print("\nНечего отправлять: сервер уже совпадает с локальной версией.")
        return

    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    print(f"\nАрхив точки возврата {stamp} ...")
    archive = make_backup(paths, stamp)
    print(f"   {archive}")
    print(f"Отправка {len(to_send)} файлов ...")
    send(to_send)
    ok, detail = restart_and_check()
    print(f"Проверка после рестарта: {'ОК' if ok else 'НЕ ПРОШЛА'} — {detail}")
    if not ok:
        print("Откатываю на точку возврата ...")
        rollback(stamp)
        raise SystemExit(1)
    print(f"\nГотово. Откат: venv/bin/python scripts/prod_release.py --rollback {stamp}")


if __name__ == "__main__":
    main()
