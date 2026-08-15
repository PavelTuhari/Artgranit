#!/usr/bin/env python3
"""Шаг 3 (опционально). GUI-мастер миграции officeplus: ‹Назад› / ‹Далее›.

Проводит весь процесс из README по шагам: параметры -> архив с боевого
сервера -> проверка архива -> разворачивание на новый сервер -> проверка ->
DNS и TLS. Под капотом запускает make_archive.py и deploy_archive.py из этой
же папки и показывает их вывод вживую.

Только стандартная библиотека (tkinter). Запуск:

    python3 wizard.py

Параметры сохраняются в migration.json рядом (без паролей — их тут и нет,
только пути к SSH-ключам).
"""
import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = os.path.join(HERE, "migration.json")


class Wizard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Миграция officeplus.md — мастер")
        self.geometry("880x640")
        self.minsize(760, 540)

        self.vars = {
            "src_ip": tk.StringVar(value="92.5.130.1"),
            "src_key": tk.StringVar(value=os.path.expanduser(
                "~/Keys/oracle-ecommerce-web")),
            "out_dir": tk.StringVar(value=os.path.join(HERE, "archives")),
            "archive": tk.StringVar(value=""),
            "new_ip": tk.StringVar(value=""),
            "new_key": tk.StringVar(value=""),
            "domain": tk.StringVar(value="officeplus.md"),
        }
        self._load_cfg()

        self.proc = None
        self.q = queue.Queue()
        self.step = 0
        self.steps = [
            ("Введение", self._page_intro),
            ("Параметры", self._page_params),
            ("Архив с боевого сервера", self._page_archive),
            ("Проверка архива", self._page_verify),
            ("Разворачивание", self._page_deploy),
            ("Проверка и DNS", self._page_check),
            ("TLS (после DNS)", self._page_tls),
        ]

        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")
        self.lbl_step = ttk.Label(top, font=("", 15, "bold"))
        self.lbl_step.pack(side="left")
        self.lbl_num = ttk.Label(top, foreground="#666")
        self.lbl_num.pack(side="right")

        self.body = ttk.Frame(self, padding=(12, 4))
        self.body.pack(fill="both", expand=True)

        bottom = ttk.Frame(self, padding=10)
        bottom.pack(fill="x")
        self.btn_prev = ttk.Button(bottom, text="‹ Назад", command=self.prev)
        self.btn_prev.pack(side="left")
        self.btn_next = ttk.Button(bottom, text="Далее ›", command=self.next)
        self.btn_next.pack(side="right")
        self.status = ttk.Label(bottom, foreground="#666")
        self.status.pack(side="right", padx=12)

        self._render()
        self.after(120, self._drain_log)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── навигация ──────────────────────────────────────────────────────
    def _render(self):
        for w in self.body.winfo_children():
            w.destroy()
        name, page = self.steps[self.step]
        self.lbl_step.config(text=f"{name}")
        self.lbl_num.config(text=f"шаг {self.step + 1} / {len(self.steps)}")
        self.btn_prev.state(["!disabled"] if self.step else ["disabled"])
        self.btn_next.config(
            text="Готово" if self.step == len(self.steps) - 1 else "Далее ›")
        self.log = None
        page()

    def prev(self):
        if self.proc:
            return messagebox.showinfo("Идёт процесс",
                                       "Дождитесь завершения шага.")
        if self.step:
            self.step -= 1
            self._render()

    def next(self):
        if self.proc:
            return messagebox.showinfo("Идёт процесс",
                                       "Дождитесь завершения шага.")
        ok = getattr(self, "_validate", lambda: True)()
        if not ok:
            return
        self._save_cfg()
        if self.step == len(self.steps) - 1:
            return self._on_close()
        self.step += 1
        self._render()

    # ── страницы ───────────────────────────────────────────────────────
    def _page_intro(self):
        self._validate = lambda: True
        t = ("Мастер проведёт полный перенос officeplus.md на новый сервер.\n\n"
             "Что понадобится:\n"
             "  • SSH-ключ к БОЕВОМУ серверу (источник архива);\n"
             "  • чистый Ubuntu 24.04 (например, Oracle Always Free) и его SSH-ключ;\n"
             "  • ~1.5 ГБ на диске под архив;\n"
             "  • доступ к DNS домена (nic.md) — на последнем шаге.\n\n"
             "Что будет сделано:\n"
             "  1. Полный архив: Flask-код, .env, Oracle wallet и Instant Client,\n"
             "     файлы и база WordPress, конфиги nginx и systemd.\n"
             "  2. Разворачивание всего на новом сервере одним прогоном.\n"
             "  3. Проверки, переключение DNS, выпуск сертификата.\n\n"
             "Архив содержит секреты — храните папку archives под правами 700.\n"
             "Боевой сервер при этом НЕ изменяется — только чтение.")
        ttk.Label(self.body, text=t, justify="left", wraplength=800).pack(
            anchor="w", pady=8)

    def _row(self, parent, label, var, browse=None, width=52):
        f = ttk.Frame(parent)
        f.pack(fill="x", pady=3)
        ttk.Label(f, text=label, width=28).pack(side="left")
        ttk.Entry(f, textvariable=var, width=width).pack(
            side="left", fill="x", expand=True)
        if browse:
            ttk.Button(f, text="…", width=3,
                       command=lambda: self._browse(var, browse)).pack(side="left")

    def _browse(self, var, kind):
        p = (filedialog.askdirectory() if kind == "dir"
             else filedialog.askopenfilename())
        if p:
            var.set(p)

    def _page_params(self):
        b = self.body
        ttk.Label(b, text="Источник (боевой сервер):",
                  font=("", 12, "bold")).pack(anchor="w", pady=(6, 2))
        self._row(b, "IP боевого сервера", self.vars["src_ip"])
        self._row(b, "SSH-ключ боевого", self.vars["src_key"], "file")
        self._row(b, "Куда класть архивы", self.vars["out_dir"], "dir")
        ttk.Label(b, text="Назначение (новый сервер):",
                  font=("", 12, "bold")).pack(anchor="w", pady=(14, 2))
        self._row(b, "IP нового сервера", self.vars["new_ip"])
        self._row(b, "SSH-ключ нового", self.vars["new_key"], "file")
        self._row(b, "Домен", self.vars["domain"])
        ttk.Label(b, foreground="#666", wraplength=780, justify="left", text=(
            "IP и ключ нового сервера можно заполнить позже — до шага "
            "«Разворачивание». Ключи не копируются и никуда не отправляются.")
        ).pack(anchor="w", pady=8)

        def validate():
            if not os.path.exists(os.path.expanduser(self.vars["src_key"].get())):
                messagebox.showerror("Ошибка", "SSH-ключ боевого сервера не найден.")
                return False
            return True
        self._validate = validate

    # ── лог-панель + запуск подпроцессов ───────────────────────────────
    def _log_pane(self):
        self.log = tk.Text(self.body, height=18, bg="#111", fg="#d8f0d8",
                           insertbackground="#fff", font=("Menlo", 11))
        self.log.pack(fill="both", expand=True, pady=6)
        self.log.configure(state="disabled")

    def _append(self, line):
        self.log.configure(state="normal")
        self.log.insert("end", line)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _run(self, cmd, on_done=None):
        if self.proc:
            return
        self._append("$ " + " ".join(cmd) + "\n\n")
        self.status.config(text="выполняется…")

        def worker():
            try:
                p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, text=True,
                                     cwd=HERE, bufsize=1)
                self.proc = p
                for line in p.stdout:
                    self.q.put(line)
                p.wait()
                self.q.put(f"\n=== код завершения: {p.returncode} ===\n")
                self.q.put(("DONE", p.returncode, on_done))
            except Exception as e:                           # noqa: BLE001
                self.q.put(f"\nОШИБКА запуска: {e}\n")
                self.q.put(("DONE", 1, on_done))
        threading.Thread(target=worker, daemon=True).start()

    def _drain_log(self):
        try:
            while True:
                item = self.q.get_nowait()
                if isinstance(item, tuple) and item[0] == "DONE":
                    self.proc = None
                    rc, cb = item[1], item[2]
                    self.status.config(
                        text="успешно" if rc == 0 else f"ошибка (код {rc})")
                    if cb:
                        cb(rc)
                elif self.log is not None:
                    self._append(item)
        except queue.Empty:
            pass
        self.after(120, self._drain_log)

    def _page_archive(self):
        self._validate = lambda: bool(self.vars["archive"].get()) or \
            messagebox.askyesno("Архив не создан",
                                "Архив ещё не создан. Перейти дальше без него?")
        ttk.Label(self.body, wraplength=800, justify="left", text=(
            "Сейчас с боевого сервера будет собран полный архив (~200–400 МБ). "
            "Боевой сервер не изменяется. Уже существующий архив можно выбрать "
            "кнопкой ниже и не собирать заново.")).pack(anchor="w")
        f = ttk.Frame(self.body)
        f.pack(fill="x", pady=6)
        ttk.Button(f, text="▶ Создать архив",
                   command=self._do_archive).pack(side="left")
        ttk.Button(f, text="Выбрать существующий…",
                   command=self._pick_archive).pack(side="left", padx=8)
        ttk.Label(f, textvariable=self.vars["archive"],
                  foreground="#0a6").pack(side="left", padx=8)
        self._log_pane()

    def _do_archive(self):
        cmd = [sys.executable, os.path.join(HERE, "make_archive.py"),
               "--src-ip", self.vars["src_ip"].get(),
               "--src-key", self.vars["src_key"].get(),
               "--out", self.vars["out_dir"].get()]

        def done(rc):
            if rc == 0:
                out = self.vars["out_dir"].get()
                try:
                    latest = max(
                        (os.path.join(out, d) for d in os.listdir(out)
                         if d.startswith("officeplus_")),
                        key=os.path.getmtime)
                    self.vars["archive"].set(latest)
                except ValueError:
                    pass
        self._run(cmd, done)

    def _pick_archive(self):
        p = filedialog.askdirectory(initialdir=self.vars["out_dir"].get())
        if p:
            self.vars["archive"].set(p)

    def _page_verify(self):
        arch = self.vars["archive"].get()
        self._validate = lambda: True
        man = os.path.join(arch, "MANIFEST.json") if arch else ""
        txt = tk.Text(self.body, height=20, font=("Menlo", 11))
        txt.pack(fill="both", expand=True, pady=6)
        if man and os.path.exists(man):
            m = json.load(open(man))
            txt.insert("end", f"Архив:  {arch}\n"
                              f"Источник: {m.get('source_ip')}  "
                              f"создан: {m.get('created')}  "
                              f"коммит: {m.get('commit') or '—'}\n\n")
            total = 0
            for f, info in m.get("files", {}).items():
                total += info["size"]
                txt.insert("end", f"  {f:<22} {info['size']/1048576:8.1f} MB"
                                  f"   sha256 {info['sha256'][:16]}…\n")
            txt.insert("end", f"\n  {'ИТОГО':<22} {total/1048576:8.1f} MB\n")
            need = ["code.tar.gz", "wallets.tar.gz", "ic.tar.gz",
                    "wp_files.tar.gz", "wp_db.sql.gz", "nginx_site.conf",
                    "artgranit.service"]
            miss = [f for f in need if f not in m.get("files", {})]
            txt.insert("end", ("\n⚠ НЕ ХВАТАЕТ: " + ", ".join(miss) + "\n")
                       if miss else "\n✓ Все обязательные артефакты на месте.\n")
        else:
            txt.insert("end", "Архив не выбран — вернитесь на шаг назад.")
        txt.configure(state="disabled")

    def _page_deploy(self):
        def validate():
            for k, msg in (("archive", "Не выбран архив (шаг 3)."),
                           ("new_ip", "Не задан IP нового сервера (шаг 2)."),
                           ("new_key", "Не задан SSH-ключ нового сервера (шаг 2).")):
                if not self.vars[k].get():
                    messagebox.showerror("Ошибка", msg)
                    return False
            return True
        self._validate = validate
        ttk.Label(self.body, wraplength=800, justify="left", text=(
            f"Разворачивание на {self.vars['new_ip'].get() or '<IP не задан>'} "
            "(шаги: base, upload, flask, wp, nginx, harden, check). Повторный "
            "запуск безопасен — шаги идемпотентны. Пароль MySQL для WordPress "
            "будет сгенерирован заново.")).pack(anchor="w")
        f = ttk.Frame(self.body)
        f.pack(fill="x", pady=6)
        ttk.Button(f, text="▶ Развернуть всё",
                   command=self._do_deploy).pack(side="left")
        self._log_pane()

    def _do_deploy(self):
        if not self._validate():
            return
        self._run([sys.executable, os.path.join(HERE, "deploy_archive.py"),
                   "--archive", self.vars["archive"].get(),
                   "--ip", self.vars["new_ip"].get(),
                   "--key", self.vars["new_key"].get(),
                   "--domain", self.vars["domain"].get()])

    def _page_check(self):
        self._validate = lambda: True
        ip, d = self.vars["new_ip"].get(), self.vars["domain"].get()
        ttk.Label(self.body, wraplength=800, justify="left", text=(
            "Проверка нового сервера по IP (до переключения DNS) и инструкция "
            "по DNS:\n\n"
            f"  1. Кнопка ниже дёргает http://{ip}/cos с Host: {d} — нужно 200.\n"
            f"  2. В личном кабинете регистратора (nic.md) переключите A-записи\n"
            f"     {d} и www.{d} на {ip}.\n"
            "  3. Дождитесь обновления DNS (обычно минуты, до часа) и переходите\n"
            "     к шагу TLS.\n\n"
            "Старый сервер выключайте только после успешного шага TLS.")).pack(anchor="w")
        f = ttk.Frame(self.body)
        f.pack(fill="x", pady=6)
        ttk.Button(f, text="▶ Проверить по IP",
                   command=self._do_check).pack(side="left")
        self._log_pane()

    def _do_check(self):
        ip, d = self.vars["new_ip"].get(), self.vars["domain"].get()
        self._run(["bash", "-c",
                   f"for p in / /cos /login /api/biro26/health; do "
                   f"printf '%-28s %s\\n' \"$p\" "
                   f"\"$(curl -s -o /dev/null -w '%{{http_code}}' "
                   f"--max-time 20 -H 'Host: {d}' http://{ip}$p)\"; done"])

    def _page_tls(self):
        self._validate = lambda: True
        d = self.vars["domain"].get()
        ttk.Label(self.body, wraplength=800, justify="left", text=(
            f"Выпуск сертификата Let's Encrypt для {d}. Запускать ТОЛЬКО после "
            "того, как DNS уже указывает на новый сервер (иначе проверка ACME "
            "не пройдёт). Сертификат продлевается автоматически (certbot timer)."
        )).pack(anchor="w")
        f = ttk.Frame(self.body)
        f.pack(fill="x", pady=6)
        ttk.Button(f, text="▶ Выпустить сертификат (шаг tls)",
                   command=self._do_tls).pack(side="left")
        ttk.Button(f, text="Проверить https",
                   command=lambda: self._run(
                       ["curl", "-s", "-o", "/dev/null", "-w",
                        "https://" + d + "/cos -> %{http_code}\n",
                        f"https://{d}/cos"])).pack(side="left", padx=8)
        self._log_pane()

    def _do_tls(self):
        self._run([sys.executable, os.path.join(HERE, "deploy_archive.py"),
                   "--archive", self.vars["archive"].get(),
                   "--ip", self.vars["new_ip"].get(),
                   "--key", self.vars["new_key"].get(),
                   "--domain", self.vars["domain"].get(), "tls"])

    # ── конфиг ─────────────────────────────────────────────────────────
    def _load_cfg(self):
        try:
            for k, v in json.load(open(CFG)).items():
                if k in self.vars:
                    self.vars[k].set(v)
        except (OSError, ValueError):
            pass

    def _save_cfg(self):
        try:
            json.dump({k: v.get() for k, v in self.vars.items()},
                      open(CFG, "w"), indent=2, ensure_ascii=False)
        except OSError:
            pass

    def _on_close(self):
        if self.proc and not messagebox.askyesno(
                "Процесс не завершён", "Шаг ещё выполняется. Прервать и выйти?"):
            return
        if self.proc:
            self.proc.terminate()
        self._save_cfg()
        self.destroy()


if __name__ == "__main__":
    Wizard().mainloop()
