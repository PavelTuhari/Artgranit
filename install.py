#!/usr/bin/env python3
"""
================================================================================
УНИВЕРСАЛЬНЫЙ ИНСТАЛЛЯЦИОННЫЙ СКРИПТ ДЛЯ ORACLE SQL DEVELOPER WEB
================================================================================

ОПИСАНИЕ:
---------
Этот скрипт автоматизирует установку веб-приложения Oracle SQL Developer Web
на Linux и macOS. Использует графический интерфейс (Tkinter) для ввода параметров
подключения к Oracle Database.

ТРЕБОВАНИЯ:
----------
1. Python 3.8+ (проверка: python3 --version)
2. Tkinter (GUI библиотека):
   - macOS: обычно установлен по умолчанию
   - Linux (Ubuntu/Debian): sudo apt-get install python3-tk
   - Linux (CentOS/RHEL): sudo yum install python3-tkinter
3. Архив проекта (созданный через backup.sh)
4. Oracle Wallet ZIP файл

ИСПОЛЬЗОВАНИЕ:
-------------
1. Создайте бэкап проекта:
   ./backup.sh
   
2. Запустите установщик:
   python3 install.py
   
3. В открывшемся окне:
   a) Выберите архив проекта (.tar.gz) - нажмите "Обзор..." рядом с "Архив проекта"
   b) Выберите папку для установки (по умолчанию ~/oracle_test_app)
   c) Введите параметры подключения к Oracle:
      - DB User: имя пользователя БД (по умолчанию: ADMIN)
      - DB Password: пароль пользователя БД
      - Wallet Password: пароль для Oracle Wallet
      - Connect String: строка подключения к Oracle Cloud
      - Wallet ZIP файл: путь к файлу Wallet_HXPAVUNKCLU9HE7Q.zip
   d) Нажмите "🚀 Начать установку"
   
4. Дождитесь завершения установки (все шаги отображаются в логе)

5. После установки запустите приложение:
   cd ~/oracle_test_app
   source venv/bin/activate
   python3 app.py
   
   Или используйте скрипт перезапуска:
   ./full_restart.sh

ЧТО ДЕЛАЕТ СКРИПТ:
-----------------
1. Распаковывает архив проекта в указанную папку
2. Копирует Wallet ZIP файл в папку проекта
3. Создает виртуальное окружение Python (venv)
4. Устанавливает все зависимости из requirements.txt
5. Генерирует config.py с вашими параметрами подключения
6. Распаковывает Oracle Wallet в папку wallet_HXPAVUNKCLU9HE7Q

ПАРАМЕТРЫ ПО УМОЛЧАНИЮ:
----------------------
DB User: ADMIN
DB Password: <your-db-password>
Wallet Password: UniSim2025UNAmd__
Connect String: (description= (retry_count=20)(retry_delay=3)(address=(protocol=tcps)
                (port=1522)(host=adb.eu-frankfurt-1.oraclecloud.com))
                (connect_data=(service_name=g47056ff8b1b3d4_hxpavunkclu9he7q_high.adb.oraclecloud.com))
                (security=(ssl_server_dn_match=yes)))

ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ:
---------------------
# Установка в стандартную папку
python3 install.py

# Установка в другую папку (через GUI)
python3 install.py
# Затем в окне выберите другую папку через "Обзор..."

TROUBLESHOOTING:
---------------
1. Ошибка "tkinter не установлен":
   Linux: sudo apt-get install python3-tk
   macOS: обычно не требуется, но если нужно: brew install python-tk

2. Ошибка "Архив не найден":
   Убедитесь, что вы выбрали правильный .tar.gz файл, созданный через backup.sh

3. Ошибка при установке зависимостей:
   Проверьте подключение к интернету
   Убедитесь, что Python 3.8+ установлен
   Попробуйте обновить pip: python3 -m pip install --upgrade pip

4. Ошибка "Wallet не найден":
   Убедитесь, что вы указали правильный путь к Wallet ZIP файлу
   Файл должен быть доступен для чтения

5. Приложение не запускается после установки:
   Проверьте логи: tail -f ~/oracle_test_app/app.log
   Убедитесь, что порт 8000 свободен: lsof -i :8000
   Проверьте, что Wallet распакован: ls ~/oracle_test_app/wallet_HXPAVUNKCLU9HE7Q

СТРУКТУРА ПОСЛЕ УСТАНОВКИ:
--------------------------
~/oracle_test_app/
├── app.py
├── config.py (сгенерирован с вашими параметрами)
├── requirements.txt
├── venv/ (виртуальное окружение)
├── controllers/
├── models/
├── templates/
├── wallet_HXPAVUNKCLU9HE7Q/ (распакованный Wallet)
├── Wallet_HXPAVUNKCLU9HE7Q.zip
└── full_restart.sh

ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ:
-------------------------
- Документация проекта: README.md
- Скрипт бэкапа: backup.sh
- Скрипт перезапуска: full_restart.sh
- Веб-интерфейс: http://localhost:8000 (после запуска)
- Страница диагностики: http://localhost:8000/test.html

АВТОР: Разработано в рамках проекта Artgranit OCI
ВЕРСИЯ: 1.0
ДАТА: 2025-11-26
================================================================================
"""

import os
import sys
import subprocess
import shutil
import tarfile
import zipfile
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

# Значения по умолчанию из проекта
DEFAULT_DB_USER = "ADMIN"
DEFAULT_DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
DEFAULT_WALLET_PASSWORD = "UniSim2025UNAmd__"
DEFAULT_CONNECT_STRING = '(description= (retry_count=20)(retry_delay=3)(address=(protocol=tcps)(port=1522)(host=adb.eu-frankfurt-1.oraclecloud.com))(connect_data=(service_name=g47056ff8b1b3d4_hxpavunkclu9he7q_high.adb.oraclecloud.com))(security=(ssl_server_dn_match=yes)))'
DEFAULT_WALLET_ZIP = "Wallet_HXPAVUNKCLU9HE7Q.zip"
DEFAULT_WALLET_DIR = "wallet_HXPAVUNKCLU9HE7Q"


class InstallerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Oracle SQL Developer Web - Установка")
        self.root.geometry("700x600")
        
        # Переменные
        self.archive_path = tk.StringVar()
        self.install_dir = tk.StringVar(value=os.path.expanduser("~/oracle_test_app"))
        self.db_user = tk.StringVar(value=DEFAULT_DB_USER)
        self.db_password = tk.StringVar(value=DEFAULT_DB_PASSWORD)
        self.wallet_password = tk.StringVar(value=DEFAULT_WALLET_PASSWORD)
        self.connect_string = tk.StringVar(value=DEFAULT_CONNECT_STRING)
        self.wallet_zip_path = tk.StringVar()
        
        self.create_widgets()
    
    def create_widgets(self):
        # Заголовок
        title = tk.Label(self.root, text="Oracle SQL Developer Web", font=("Arial", 16, "bold"))
        title.pack(pady=10)
        
        subtitle = tk.Label(self.root, text="Универсальный установщик", font=("Arial", 10))
        subtitle.pack()
        
        # Фрейм для полей
        frame = ttk.Frame(self.root, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Архив проекта
        ttk.Label(frame, text="Архив проекта (.tar.gz):").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(frame, textvariable=self.archive_path, width=50).grid(row=0, column=1, padx=5)
        ttk.Button(frame, text="Обзор...", command=self.browse_archive).grid(row=0, column=2)
        
        # Папка установки
        ttk.Label(frame, text="Папка установки:").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(frame, textvariable=self.install_dir, width=50).grid(row=1, column=1, padx=5)
        ttk.Button(frame, text="Обзор...", command=self.browse_install_dir).grid(row=1, column=2)
        
        # Разделитель
        ttk.Separator(frame, orient=tk.HORIZONTAL).grid(row=2, column=0, columnspan=3, sticky=tk.EW, pady=10)
        
        # Параметры БД
        ttk.Label(frame, text="Параметры подключения к Oracle:", font=("Arial", 10, "bold")).grid(row=3, column=0, columnspan=3, sticky=tk.W, pady=5)
        
        ttk.Label(frame, text="DB User:").grid(row=4, column=0, sticky=tk.W, pady=5)
        ttk.Entry(frame, textvariable=self.db_user, width=50).grid(row=4, column=1, padx=5)
        
        ttk.Label(frame, text="DB Password:").grid(row=5, column=0, sticky=tk.W, pady=5)
        ttk.Entry(frame, textvariable=self.db_password, width=50, show="*").grid(row=5, column=1, padx=5)
        
        ttk.Label(frame, text="Wallet Password:").grid(row=6, column=0, sticky=tk.W, pady=5)
        ttk.Entry(frame, textvariable=self.wallet_password, width=50, show="*").grid(row=6, column=1, padx=5)
        
        ttk.Label(frame, text="Connect String:").grid(row=7, column=0, sticky=tk.W, pady=5)
        connect_entry = ttk.Entry(frame, textvariable=self.connect_string, width=50)
        connect_entry.grid(row=7, column=1, padx=5)
        
        ttk.Label(frame, text="Wallet ZIP файл:").grid(row=8, column=0, sticky=tk.W, pady=5)
        ttk.Entry(frame, textvariable=self.wallet_zip_path, width=50).grid(row=8, column=1, padx=5)
        ttk.Button(frame, text="Обзор...", command=self.browse_wallet).grid(row=8, column=2)
        
        # Кнопка установки
        install_btn = ttk.Button(frame, text="🚀 Начать установку", command=self.start_installation)
        install_btn.grid(row=9, column=0, columnspan=3, pady=20)
        
        # Лог
        log_label = ttk.Label(frame, text="Лог установки:")
        log_label.grid(row=10, column=0, columnspan=3, sticky=tk.W, pady=5)
        
        self.log_text = tk.Text(frame, height=8, width=70)
        self.log_text.grid(row=11, column=0, columnspan=3, pady=5)
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.log_text.yview)
        scrollbar.grid(row=11, column=3, sticky=tk.NS)
        self.log_text.configure(yscrollcommand=scrollbar.set)
    
    def log(self, message):
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.root.update()
    
    def browse_archive(self):
        filename = filedialog.askopenfilename(
            title="Выберите архив проекта",
            filetypes=[("Tar GZ", "*.tar.gz"), ("All files", "*.*")]
        )
        if filename:
            self.archive_path.set(filename)
    
    def browse_install_dir(self):
        dirname = filedialog.askdirectory(title="Выберите папку для установки")
        if dirname:
            self.install_dir.set(dirname)
    
    def browse_wallet(self):
        filename = filedialog.askopenfilename(
            title="Выберите Wallet ZIP файл",
            filetypes=[("ZIP files", "*.zip"), ("All files", "*.*")]
        )
        if filename:
            self.wallet_zip_path.set(filename)
    
    def start_installation(self):
        # Валидация
        if not self.archive_path.get():
            messagebox.showerror("Ошибка", "Укажите путь к архиву проекта!")
            return
        
        if not os.path.exists(self.archive_path.get()):
            messagebox.showerror("Ошибка", "Архив не найден!")
            return
        
        if not self.wallet_zip_path.get() or not os.path.exists(self.wallet_zip_path.get()):
            messagebox.showerror("Ошибка", "Укажите путь к Wallet ZIP файлу!")
            return
        
        # Запуск установки в отдельном потоке
        import threading
        thread = threading.Thread(target=self.install)
        thread.daemon = True
        thread.start()
    
    def install(self):
        try:
            self.log("=== Начало установки ===")
            
            # 1. Распаковка архива
            self.log(f"[1/6] Распаковка архива в {self.install_dir.get()}...")
            install_path = Path(self.install_dir.get())
            install_path.mkdir(parents=True, exist_ok=True)
            
            with tarfile.open(self.archive_path.get(), 'r:gz') as tar:
                tar.extractall(install_path)
            
            self.log("✅ Архив распакован")
            
            # 2. Копирование Wallet
            self.log("[2/6] Копирование Wallet файла...")
            wallet_dest = install_path / Path(self.wallet_zip_path.get()).name
            shutil.copy(self.wallet_zip_path.get(), wallet_dest)
            self.log(f"✅ Wallet скопирован: {wallet_dest}")
            
            # 3. Создание виртуального окружения
            self.log("[3/6] Создание виртуального окружения...")
            venv_path = install_path / "venv"
            if venv_path.exists():
                shutil.rmtree(venv_path)
            
            subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True)
            self.log("✅ Виртуальное окружение создано")
            
            # 4. Установка зависимостей
            self.log("[4/6] Установка зависимостей...")
            pip_path = venv_path / "bin" / "pip"
            if sys.platform == "win32":
                pip_path = venv_path / "Scripts" / "pip.exe"
            
            requirements = install_path / "requirements.txt"
            subprocess.run([str(pip_path), "install", "-r", str(requirements)], check=True)
            self.log("✅ Зависимости установлены")
            
            # 5. Создание config.py
            self.log("[5/6] Создание config.py...")
            config_content = f'''"""
Конфигурация приложения
"""
import os
from pathlib import Path

class Config:
    """Базовый класс конфигурации"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Oracle Database конфигурация
    DB_USER = "{self.db_user.get()}"
    DB_PASSWORD = "{self.db_password.get()}"
    WALLET_PASSWORD = "{self.wallet_password.get()}"
    WALLET_ZIP = "{Path(self.wallet_zip_path.get()).name}"
    WALLET_DIR = "{DEFAULT_WALLET_DIR}"
    TNS_ALIAS = "hxpavunkclu9he7q_high"
    CONNECT_STRING = r"{self.connect_string.get()}"
    
    # WebSocket конфигурация
    SOCKETIO_ASYNC_MODE = 'threading'
    SOCKETIO_CORS_ALLOWED_ORIGINS = "*"
    
    # Dashboard обновления (в секундах)
    DASHBOARD_UPDATE_INTERVAL = 60
    
    # Аутентификация
    DEFAULT_USERNAME = "{self.db_user.get()}"
    DEFAULT_PASSWORD = "{self.db_password.get()}"
    
    @staticmethod
    def init_app(app):
        pass
'''
            config_file = install_path / "config.py"
            with open(config_file, 'w', encoding='utf-8') as f:
                f.write(config_content)
            self.log("✅ config.py создан")
            
            # 6. Распаковка Wallet
            self.log("[6/6] Распаковка Wallet...")
            wallet_dir = install_path / DEFAULT_WALLET_DIR
            wallet_dir.mkdir(exist_ok=True)
            
            with zipfile.ZipFile(wallet_dest, 'r') as zip_ref:
                zip_ref.extractall(wallet_dir)
            self.log("✅ Wallet распакован")
            
            self.log("\n=== Установка завершена успешно! ===")
            self.log(f"Приложение установлено в: {install_path}")
            self.log(f"\nДля запуска выполните:")
            self.log(f"  cd {install_path}")
            self.log(f"  source venv/bin/activate")
            self.log(f"  python3 app.py")
            
            messagebox.showinfo("Успех", f"Установка завершена!\n\nПриложение установлено в:\n{install_path}")
            
        except Exception as e:
            error_msg = f"Ошибка установки: {str(e)}"
            self.log(f"❌ {error_msg}")
            messagebox.showerror("Ошибка", error_msg)
            import traceback
            traceback.print_exc()


def main():
    # Проверка наличия tkinter
    try:
        import tkinter
    except ImportError:
        print("Ошибка: tkinter не установлен!")
        print("Для Ubuntu/Debian: sudo apt-get install python3-tk")
        print("Для macOS: tkinter должен быть установлен по умолчанию")
        sys.exit(1)
    
    root = tk.Tk()
    app = InstallerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
