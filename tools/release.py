#!/usr/bin/env python3
"""Выпуск TexFlow: скриптовая версия с подписанным манифестом, SHA256SUMS с подписью, проверка.

    python tools/release.py scripts OUT_DIR      # TexFlow-<версия>-scripts.zip (MANIFEST.sha256 + .sig внутри)
    python tools/release.py sums OUT_DIR         # SHA256SUMS и SHA256SUMS.sig для всех архивов в OUT_DIR
    python tools/release.py verify OUT_DIR       # проверить подпись и суммы
    python tools/release.py keygen               # новая пара ключей (закрытый — в секрет GitHub)

Закрытый ключ берётся из переменной окружения UNISIM_SOFT_SIGNING_KEY (секрет GitHub Actions).
Без ключа файлы создаются неподписанными; --require-signature превращает это в ошибку.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from texflow import __version__, integrity as I  # noqa: E402


def seed_or_none(require: bool) -> bytes | None:
    text = os.environ.get("UNISIM_SOFT_SIGNING_KEY", "").strip()
    if not text:
        if require:
            raise SystemExit("нет секрета UNISIM_SOFT_SIGNING_KEY — подписать нечем")
        print("ВНИМАНИЕ: UNISIM_SOFT_SIGNING_KEY не задан — файлы НЕ подписаны", flush=True)
        return None
    seed = I.seed_from_text(text)
    pub = I.known_key()
    if pub and I.public_key(seed) != pub:
        raise SystemExit("закрытый ключ не соответствует открытому ключу unisim-soft в программе "
                         f"(в программе {I.fingerprint(pub)}, у ключа {I.fingerprint(I.public_key(seed))})")
    return seed


def git(*a) -> str:
    try:
        return subprocess.run(["git", "-C", ROOT, *a], capture_output=True, text=True, timeout=20).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def tracked_files() -> list[str]:
    out = git("ls-files", "-z", ".")
    files = [f for f in out.split("\0") if f] if out else I.walk(ROOT)
    return [f for f in files if os.path.isfile(os.path.join(ROOT, f))]


def cmd_scripts(out_dir: str, require: bool) -> str:
    seed = seed_or_none(require)
    commit = os.environ.get("GITHUB_SHA", git("rev-parse", "HEAD"))[:12] or "local"
    name = f"TexFlow-{__version__}-scripts"
    stage = os.path.join(tempfile.mkdtemp(prefix="texflow-rel-"), name)
    for rel in tracked_files():
        dst = os.path.join(stage, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(os.path.join(ROOT, rel), dst)
    text = I.make_manifest(stage, f"TexFlow {__version__} · commit {commit} · scripts (Windows / macOS / Linux)")
    with open(os.path.join(stage, I.MANIFEST), "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    if seed:
        with open(os.path.join(stage, I.SIGNATURE), "w", encoding="utf-8", newline="\n") as f:
            f.write(I.sign_text(seed, text) + "\n")
    res = I.check_tree(stage)
    if seed and res["status"] != "ok":
        raise SystemExit(f"самопроверка не прошла: {res}")
    os.makedirs(out_dir, exist_ok=True)
    zpath = os.path.join(out_dir, f"{name}.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for dirpath, _d, files in os.walk(stage):
            for fn in sorted(files):
                full = os.path.join(dirpath, fn)
                info = zipfile.ZipInfo.from_file(full, os.path.join(name, os.path.relpath(full, stage)))
                with open(full, "rb") as fh:
                    z.writestr(info, fh.read(), zipfile.ZIP_DEFLATED)
    shutil.rmtree(os.path.dirname(stage), ignore_errors=True)
    print(f"✓ {zpath} · {len(I.parse_sums(text))} файлов · {I.describe(res) if seed else 'без подписи'}")
    return zpath


def cmd_sums(out_dir: str, require: bool) -> str:
    seed = seed_or_none(require)
    commit = os.environ.get("GITHUB_SHA", git("rev-parse", "HEAD"))[:12] or "local"
    files = sorted(f for f in os.listdir(out_dir) if f.endswith((".zip", ".tar.gz", ".dmg", ".exe", ".msi")))
    if not files:
        raise SystemExit("нет архивов для SHA256SUMS")
    lines = [f"# TexFlow {__version__} · commit {commit} · signer {I.SIGNER}"]
    lines += [f"{I.sha256_file(os.path.join(out_dir, f))}  {f}" for f in files]
    text = "\n".join(lines) + "\n"
    sums = os.path.join(out_dir, "SHA256SUMS")
    with open(sums, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    if seed:
        with open(sums + ".sig", "w", encoding="utf-8", newline="\n") as f:
            f.write(I.sign_text(seed, text) + "\n")
    pub = I.known_key()
    with open(os.path.join(out_dir, "SIGNER-unisim-soft.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(f"signer: {I.SIGNER}\nalgorithm: Ed25519\npublic key (base64): {I.b64(pub) if pub else '-'}\n"
                f"fingerprint: {I.fingerprint(pub) if pub else '-'}\ncommit: {commit}\n"
                f"verify: python texflow_app.py --verify-sums SHA256SUMS\n")
    print(text, end="")
    print("✓ SHA256SUMS" + (" + подпись unisim-soft" if seed else " (без подписи)"))
    return sums


def cmd_verify(out_dir: str) -> int:
    res = I.check_sums_file(os.path.join(out_dir, "SHA256SUMS"))
    print("подпись SHA256SUMS:", res["signature"])
    bad = 0
    for name, st in res["files"].items():
        print(f"  {st:9} {name}")
        bad += st != "ok"
        if st == "ok" and name.endswith("-scripts.zip"):
            tmp = tempfile.mkdtemp()
            with zipfile.ZipFile(os.path.join(out_dir, name)) as z:
                z.extractall(tmp)
            inner = os.path.join(tmp, os.listdir(tmp)[0])
            r = I.check_tree(inner)
            print("           манифест скриптов:", I.describe(r))
            bad += r["status"] != "ok"
            shutil.rmtree(tmp, ignore_errors=True)
    return 0 if res["signature"] == "ok" and not bad else 1


def cmd_keygen():
    seed = os.urandom(32)
    pub = I.public_key(seed)
    print("# ОТКРЫТЫЙ ключ — в texflow/integrity.py (PUBLIC_KEYS) и install/signing/unisim-soft.pub:")
    print(I.b64(pub), " fingerprint", I.fingerprint(pub))
    print("# ЗАКРЫТЫЙ ключ — ТОЛЬКО в секрет GitHub UNISIM_SOFT_SIGNING_KEY:")
    print(I.b64(seed))


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    require = "--require-signature" in argv
    argv = [a for a in argv if a != "--require-signature"]
    cmd = argv[0]
    if cmd == "keygen":
        cmd_keygen()
        return 0
    out = os.path.abspath(argv[1] if len(argv) > 1 else os.path.join(ROOT, "dist", "release"))
    if cmd == "scripts":
        cmd_scripts(out, require)
    elif cmd == "sums":
        cmd_sums(out, require)
    elif cmd == "verify":
        return cmd_verify(out)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
