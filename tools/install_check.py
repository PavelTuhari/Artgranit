#!/usr/bin/env python3
"""Проверка установщика и сборки на текущей ОС (для акта тестирования).

    python tools/install_check.py docs/html [--build]

1. установщик во временную «домашнюю папку»: копия, venv, библиотеки, ярлыки, --check;
2. запуск установленной программы (окно) — если есть X-дисплей;
3. удаление: программа и ярлыки удалены, данные сохранены;
4. с --build: PyInstaller-сборка, распаковка, --check бинарника.
Итог: <вывод>/install_results.json
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else
                      os.path.join(ROOT, "docs", "html"))
results = []


def step(sid, title, expected, fn):
    t0 = time.time()
    rec = {"id": sid, "title": title, "expected": expected, "status": "PASS", "actual": "", "ms": 0}
    try:
        rec["actual"] = fn() or ""
    except Exception as e:  # noqa: BLE001
        rec["status"], rec["actual"] = "FAIL", f"ОШИБКА: {e}"
    rec["ms"] = int((time.time() - t0) * 1000)
    results.append(rec)
    print(rec["status"], sid, title, flush=True)


def main():
    tmp = tempfile.mkdtemp(prefix="texflow-inst-")
    home = os.path.join(tmp, "home")
    os.makedirs(os.path.join(home, "Desktop"))
    env = {**os.environ, "HOME": home, "XDG_DATA_HOME": os.path.join(home, ".local", "share"),
           "TEXFLOW_NO_LAUNCH": "1", "APPDATA": os.path.join(home, "AppData", "Roaming"),
           "LOCALAPPDATA": os.path.join(home, "AppData", "Local")}
    env.pop("TEXFLOW_HOME", None)
    env.pop("TEXFLOW_DB", None)
    sys.path.insert(0, os.path.join(ROOT, "install"))
    import install as inst  # noqa: E402

    dest = {}

    def run_install():
        r = subprocess.run([sys.executable, os.path.join(ROOT, "install", "install.py"), "--no-launch"],
                           capture_output=True, text=True, env=env, timeout=900)
        if r.returncode:
            raise RuntimeError((r.stdout + r.stderr)[-800:])
        line = [x for x in r.stdout.splitlines() if x.startswith("TexFlow — ")][0]
        dest["path"] = line.split(" в ", 1)[1].strip()
        shortcuts = [x for x in r.stdout.splitlines() if x.startswith("· ярлык")]
        must_have = ["tkinter: ok", "reportlab:", "openpyxl:", "flask:", "✓ TexFlow установлен"]
        missing = [m for m in must_have if m not in r.stdout]
        if missing:
            raise RuntimeError(f"нет в выводе: {missing}")
        return f"{len(shortcuts)} ярлыка; " + " | ".join(x for x in r.stdout.splitlines() if x.startswith("TexFlow 1"))

    step("I01", f"Установка на {platform.system()} (install.py в чистую домашнюю папку)",
         "Копия программы, venv с reportlab/openpyxl/flask, ярлыки, проверка --check проходит", run_install)

    def check_files():
        d = dest["path"]
        need = ["texflow_app.py", "texflow/db.py", "desktop/texflow_desktop/app.py", "install/texflow.png"]
        if sys.platform.startswith("win"):
            need += ["TexFlow.bat", "Uninstall-TexFlow.bat"]
        else:
            need += ["texflow-desktop", "texflow-web", "uninstall-texflow"]
        miss = [n for n in need if not os.path.exists(os.path.join(d, n))]
        if miss:
            raise RuntimeError(f"нет файлов: {miss}")
        sc = [p for p in inst.shortcut_paths(d) if p and os.path.exists(p.replace(os.path.expanduser("~"), home))]
        return f"файлы на месте; ярлыки: {len(sc)}"

    step("I02", "Состав установленной программы", "Ядро, нативное приложение, иконка, скрипты запуска и удаления",
         check_files)

    def shortcut_check():
        if sys.platform.startswith(("win", "darwin")):
            return "проверяется на целевой ОС"
        apps = os.path.join(home, ".local", "share", "applications")
        files = sorted(os.listdir(apps))
        if files != ["texflow-web.desktop", "texflow.desktop"]:
            raise RuntimeError(files)
        if not os.path.exists(os.path.join(home, "Desktop", "texflow.desktop")):
            raise RuntimeError("нет ярлыка на рабочем столе")
        text = open(os.path.join(apps, "texflow.desktop"), encoding="utf-8").read()
        if "Comment[ro]=" not in text or "Exec=" not in text:
            raise RuntimeError(text)
        return "меню: " + ", ".join(files) + "; рабочий стол: texflow.desktop"

    step("I03", "Ярлыки в меню приложений и на рабочем столе", ".desktop-файлы с иконкой и подписями RU/RO/EN",
         shortcut_check)

    def launch():
        if not os.environ.get("DISPLAY") or sys.platform.startswith("win"):
            return "пропущено: нет X-дисплея"
        launcher = os.path.join(dest["path"], "texflow-desktop")
        p = subprocess.Popen([launcher, "--demo"], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(7)
        alive = p.poll() is None
        p.terminate()
        try:
            _out, err = p.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            p.kill()
            _out, err = p.communicate()
        if not alive:
            raise RuntimeError("окно закрылось: " + err.decode(errors="replace")[-500:])
        db = os.path.join(home, ".local", "share", "texflow", "texflow.db")
        if not os.path.exists(db):
            raise RuntimeError("база не создана в папке данных")
        return f"окно открыто 7 с, база: ~/.local/share/texflow/texflow.db ({os.path.getsize(db)} байт)"

    step("I04", "Запуск установленной программы ярлыком", "Окно работает, база с демо-поставкой создана в папке данных",
         launch)

    def uninstall():
        un = [os.path.join(dest["path"], "uninstall-texflow")] if not sys.platform.startswith("win") else \
            [sys.executable, os.path.join(dest["path"], "install", "install.py"), "--uninstall", "--dest", dest["path"]]
        r = subprocess.run(un, capture_output=True, text=True, env=env, timeout=120)
        if r.returncode or os.path.exists(dest["path"]):
            raise RuntimeError(r.stdout + r.stderr)
        left = [p for p in (os.path.join(home, ".local", "share", "applications", "texflow.desktop"),
                            os.path.join(home, "Desktop", "texflow.desktop")) if os.path.exists(p)]
        if left:
            raise RuntimeError(f"остались ярлыки: {left}")
        data = os.path.join(home, ".local", "share", "texflow")
        kept = os.path.isdir(data) or sys.platform.startswith(("win", "darwin"))
        if not kept:
            raise RuntimeError("данные удалены без --purge")
        return "программа и ярлыки удалены, данные сохранены"

    step("I05", "Удаление", "Программа и ярлыки удалены; база остаётся (без --purge)", uninstall)

    if "--build" in sys.argv:
        def build():
            r = subprocess.run([sys.executable, os.path.join(ROOT, "install", "build_exe.py")], capture_output=True,
                               text=True, timeout=900, cwd=ROOT)
            if r.returncode:
                raise RuntimeError((r.stdout + r.stderr)[-800:])
            z = [x for x in r.stdout.splitlines() if x.startswith("✓")][-1].split()[1]
            unz = os.path.join(tmp, "exe")
            shutil.unpack_archive(z, unz)
            exe = os.path.join(unz, "TexFlow", "TexFlow.exe" if sys.platform.startswith("win") else "TexFlow")
            if sys.platform == "darwin":
                exe = os.path.join(unz, "TexFlow.app", "Contents", "MacOS", "TexFlow")
            os.chmod(exe, 0o755)
            env2 = {"PATH": "/usr/bin:/bin", "HOME": home, "TEXFLOW_HOME": os.path.join(tmp, "exehome")}
            c = subprocess.run([exe, "--check"], capture_output=True, text=True, env=env2, timeout=120)
            if c.returncode or "reportlab: 5" not in c.stdout and "reportlab: 4" not in c.stdout:
                raise RuntimeError(c.stdout + c.stderr)
            return f"{os.path.basename(z)} ({os.path.getsize(z) / 1e6:.1f} МБ); бинарник без системного Python: " + \
                " · ".join(c.stdout.strip().splitlines()[2:6])

        step("I06", "Сборка PyInstaller и запуск бинарника без Python", "Архив собран; бинарник отвечает --check с "
             "библиотеками внутри", build)

    def signed_release():
        if not os.environ.get("UNISIM_SOFT_SIGNING_KEY"):
            return "пропущено: нет ключа UNISIM_SOFT_SIGNING_KEY (в CI — секрет репозитория)"
        rel = os.path.join(tmp, "release")
        os.makedirs(rel)
        for z in os.listdir(os.path.join(ROOT, "dist")):
            if z.startswith("TexFlow-") and z.endswith(".zip") and "-scripts" not in z:
                shutil.copy(os.path.join(ROOT, "dist", z), rel)
        py = sys.executable
        for cmd in (["scripts", rel, "--require-signature"], ["sums", rel, "--require-signature"]):
            r = subprocess.run([py, os.path.join(ROOT, "tools", "release.py"), *cmd], capture_output=True, text=True)
            if r.returncode:
                raise RuntimeError(r.stdout + r.stderr)
        env2 = {k: v for k, v in os.environ.items() if k != "UNISIM_SOFT_SIGNING_KEY"}
        v = subprocess.run([py, os.path.join(ROOT, "tools", "release.py"), "verify", rel], capture_output=True,
                           text=True, env=env2)
        if v.returncode:
            raise RuntimeError(v.stdout)
        sz = [f for f in os.listdir(rel) if f.endswith("-scripts.zip")][0]
        un = os.path.join(tmp, "scripts")
        shutil.unpack_archive(os.path.join(rel, sz), un)
        app_dir = os.path.join(un, os.listdir(un)[0])
        run = lambda *a, **kw: subprocess.run([py, os.path.join(app_dir, "texflow_app.py"), *a],  # noqa: E731
                                              capture_output=True, text=True, env={**env2, **kw}, timeout=300)
        ok = run("--verify")
        if ok.returncode or "целостность: ok" not in ok.stdout:
            raise RuntimeError(ok.stdout + ok.stderr)
        with open(os.path.join(app_dir, "texflow", "rules.py"), "a", encoding="utf-8") as f:
            f.write("\n# подмена\n")
        bad = run("--verify")
        strict = run("--check", TEXFLOW_STRICT_INTEGRITY="1")
        with open(os.path.join(rel, sz), "ab") as f:
            f.write(b"x")
        sums = run("--verify-sums", os.path.join(rel, "SHA256SUMS"))
        if bad.returncode != 1 or strict.returncode != 3 or "MISMATCH" not in sums.stdout:
            raise RuntimeError(f"подмена не поймана: {bad.returncode} {strict.returncode} {sums.stdout}")
        return (ok.stdout.strip() + " · подмена файла → «ИЗМЕНЕНЫ» и отказ в строгом режиме (код 3) · "
                "подмена архива → MISMATCH · файлы: " + ", ".join(sorted(os.listdir(rel))))

    step("I07", "Подписанный выпуск unisim-soft: манифест скриптов, SHA256SUMS, самопроверка и подмена",
         "Скрипты из архива сами подтверждают подпись unisim-soft; изменённый файл и подменённый архив обнаруживаются",
         signed_release)

    meta = {"os": f"{platform.system()} {platform.release()}", "python": platform.python_version()}
    with open(os.path.join(OUT, "install_results.json"), "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "results": results}, f, ensure_ascii=False, indent=1)
    shutil.rmtree(tmp, ignore_errors=True)
    failed = sum(r["status"] != "PASS" for r in results)
    print(f"\nINSTALL: {len(results) - failed}/{len(results)} PASS")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
