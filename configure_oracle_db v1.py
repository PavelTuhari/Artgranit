#!/usr/bin/env python3
"""
================================================================================
КОНФИГУРАЦИЯ ПОДКЛЮЧЕНИЯ К ORACLE OCI DATABASE
================================================================================

ОПИСАНИЕ:
---------
Графический интерфейс для настройки параметров подключения к Oracle OCI 
Autonomous Database. Сохраняет настройки в .env файл с защитой паролей.

ТРЕБОВАНИЯ:
----------
1. Python 3.8+
2. Tkinter (обычно установлен по умолчанию)
3. python-dotenv (устанавливается через requirements.txt)

ИСПОЛЬЗОВАНИЕ:
-------------
python3 configure_oracle_db.py

ФУНКЦИОНАЛ:
----------
- Ввод всех параметров подключения к Oracle OCI
- Выбор Oracle Wallet ZIP файла
- Тестирование подключения
- Сохранение настроек в .env файл
- Загрузка существующих настроек из .env

АВТОР: Разработано в рамках проекта Artgranit OCI
ВЕРСИЯ: 1.0
ДАТА: 2025-12-03
================================================================================
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from pathlib import Path
from dotenv import load_dotenv, dotenv_values

# Загружаем существующие настройки
load_dotenv()

# Значения по умолчанию (только из .env файла - безопасно!)
# Все значения читаются из защищенного .env файла, без захардкоженных паролей
DEFAULT_DB_USER = os.environ.get('DB_USER', '')
DEFAULT_DB_PASSWORD = os.environ.get('DB_PASSWORD', '')
DEFAULT_WALLET_PASSWORD = os.environ.get('WALLET_PASSWORD', '')
DEFAULT_WALLET_ZIP = os.environ.get('WALLET_ZIP', '')
DEFAULT_WALLET_DIR = os.environ.get('WALLET_DIR', '')
DEFAULT_TNS_ALIAS = os.environ.get('TNS_ALIAS', '')
DEFAULT_CONNECT_STRING = os.environ.get('CONNECT_STRING', '')


class OracleConfigGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Oracle OCI Database Configuration")
        self.root.geometry("800x700")
        self.root.resizable(True, True)
        
        # Переменные
        self.db_user = tk.StringVar(value=DEFAULT_DB_USER)
        self.db_password = tk.StringVar(value=DEFAULT_DB_PASSWORD)
        self.wallet_password = tk.StringVar(value=DEFAULT_WALLET_PASSWORD)
        self.wallet_zip_path = tk.StringVar(value=DEFAULT_WALLET_ZIP)
        self.wallet_dir = tk.StringVar(value=DEFAULT_WALLET_DIR)
        self.tns_alias = tk.StringVar(value=DEFAULT_TNS_ALIAS)
        self.connect_string = tk.StringVar(value=DEFAULT_CONNECT_STRING)
        
        # Загружаем существующие настройки из .env
        self.load_existing_config()
        
        self.create_widgets()
    
    def load_existing_config(self):
        """Загружает существующие настройки из .env файла"""
        env_file = Path('.env')
        if env_file.exists():
            try:
                env_vars = dotenv_values('.env')
                if env_vars.get('DB_USER'):
                    self.db_user.set(env_vars['DB_USER'])
                if env_vars.get('DB_PASSWORD'):
                    self.db_password.set(env_vars['DB_PASSWORD'])
                if env_vars.get('WALLET_PASSWORD'):
                    self.wallet_password.set(env_vars['WALLET_PASSWORD'])
                if env_vars.get('WALLET_ZIP'):
                    self.wallet_zip_path.set(env_vars['WALLET_ZIP'])
                if env_vars.get('WALLET_DIR'):
                    self.wallet_dir.set(env_vars['WALLET_DIR'])
                if env_vars.get('TNS_ALIAS'):
                    self.tns_alias.set(env_vars['TNS_ALIAS'])
                if env_vars.get('CONNECT_STRING'):
                    self.connect_string.set(env_vars['CONNECT_STRING'])
            except Exception as e:
                print(f"Ошибка при загрузке .env: {e}")
    
    def create_widgets(self):
        # Главный контейнер с прокруткой
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Заголовок
        title = ttk.Label(main_frame, text="🔧 Oracle OCI Database Configuration", 
                         font=("Arial", 16, "bold"))
        title.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # Разделитель
        separator = ttk.Separator(main_frame, orient='horizontal')
        separator.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 20))
        
        row = 2
        
        # DB User
        ttk.Label(main_frame, text="Database User:", font=("Arial", 10, "bold")).grid(
            row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(main_frame, textvariable=self.db_user, width=40).grid(
            row=row, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        row += 1
        
        # DB Password
        ttk.Label(main_frame, text="Database Password:", font=("Arial", 10, "bold")).grid(
            row=row, column=0, sticky=tk.W, pady=5)
        password_entry = ttk.Entry(main_frame, textvariable=self.db_password, 
                                   width=40, show="*")
        password_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        # Кнопка показать/скрыть пароль
        show_pass_btn = ttk.Button(main_frame, text="👁", width=3, 
                                  command=lambda: self.toggle_password(password_entry))
        show_pass_btn.grid(row=row, column=2, sticky=tk.W, pady=5)
        row += 1
        
        # Wallet Password
        ttk.Label(main_frame, text="Wallet Password:", font=("Arial", 10, "bold")).grid(
            row=row, column=0, sticky=tk.W, pady=5)
        wallet_pass_entry = ttk.Entry(main_frame, textvariable=self.wallet_password, 
                                     width=40, show="*")
        wallet_pass_entry.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        show_wallet_btn = ttk.Button(main_frame, text="👁", width=3,
                                    command=lambda: self.toggle_password(wallet_pass_entry))
        show_wallet_btn.grid(row=row, column=2, sticky=tk.W, pady=5)
        row += 1
        
        # Wallet ZIP
        ttk.Label(main_frame, text="Wallet ZIP File:", font=("Arial", 10, "bold")).grid(
            row=row, column=0, sticky=tk.W, pady=5)
        wallet_frame = ttk.Frame(main_frame)
        wallet_frame.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        wallet_frame.columnconfigure(0, weight=1)
        ttk.Entry(wallet_frame, textvariable=self.wallet_zip_path, width=30).grid(
            row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        ttk.Button(wallet_frame, text="Обзор...", 
                  command=self.browse_wallet_file).grid(row=0, column=1)
        row += 1
        
        # Wallet Directory
        ttk.Label(main_frame, text="Wallet Directory:", font=("Arial", 10, "bold")).grid(
            row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(main_frame, textvariable=self.wallet_dir, width=40).grid(
            row=row, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        row += 1
        
        # TNS Alias
        ttk.Label(main_frame, text="TNS Alias:", font=("Arial", 10, "bold")).grid(
            row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(main_frame, textvariable=self.tns_alias, width=40).grid(
            row=row, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        row += 1
        
        # Connect String
        ttk.Label(main_frame, text="Connect String:", font=("Arial", 10, "bold")).grid(
            row=row, column=0, sticky=tk.W, pady=5)
        connect_text = scrolledtext.ScrolledText(main_frame, width=50, height=4, wrap=tk.WORD)
        connect_text.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        connect_text.insert('1.0', self.connect_string.get())
        connect_text.bind('<KeyRelease>', lambda e: self.update_connect_string(connect_text))
        self.connect_text_widget = connect_text
        row += 1
        
        # Кнопки действий
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=row, column=0, columnspan=3, pady=20)
        
        ttk.Button(button_frame, text="🧪 Тест подключения", 
                  command=self.test_connection, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="💾 Сохранить настройки", 
                  command=self.save_config, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="❌ Выход", 
                  command=self.root.quit, width=15).pack(side=tk.LEFT, padx=5)
        
        row += 1
        
        # Статусная строка
        self.status_label = ttk.Label(main_frame, text="Готов к настройке", 
                                     foreground="green", font=("Arial", 9))
        self.status_label.grid(row=row, column=0, columnspan=3, pady=10)
    
    def toggle_password(self, entry):
        """Переключает видимость пароля"""
        if entry.cget('show') == '*':
            entry.config(show='')
        else:
            entry.config(show='*')
    
    def update_connect_string(self, text_widget):
        """Обновляет переменную connect_string при изменении текста"""
        self.connect_string.set(text_widget.get('1.0', tk.END).strip())
    
    def browse_wallet_file(self):
        """Открывает диалог выбора Wallet ZIP файла"""
        filename = filedialog.askopenfilename(
            title="Выберите Oracle Wallet ZIP файл",
            filetypes=[("ZIP files", "*.zip"), ("All files", "*.*")]
        )
        if filename:
            # Сохраняем только имя файла, если он в текущей директории
            if os.path.dirname(filename) == os.getcwd():
                self.wallet_zip_path.set(os.path.basename(filename))
            else:
                self.wallet_zip_path.set(filename)
    
    def test_connection(self):
        """Тестирует подключение к Oracle Database"""
        self.status_label.config(text="Тестирование подключения...", foreground="blue")
        self.root.update()
        
        try:
            import oracledb
            import zipfile
            
            # Проверяем наличие wallet файла
            wallet_zip = self.wallet_zip_path.get()
            if not os.path.exists(wallet_zip):
                messagebox.showerror("Ошибка", 
                    f"Wallet ZIP файл не найден: {wallet_zip}\n\n"
                    "Убедитесь, что файл существует и путь указан правильно.")
                self.status_label.config(text="Ошибка: Wallet файл не найден", foreground="red")
                return
            
            # Распаковываем wallet временно
            wallet_dir = self.wallet_dir.get()
            temp_wallet_dir = f"{wallet_dir}_test"
            
            try:
                if os.path.exists(temp_wallet_dir):
                    import shutil
                    shutil.rmtree(temp_wallet_dir)
                
                with zipfile.ZipFile(wallet_zip, 'r') as zip_ref:
                    zip_ref.extractall(temp_wallet_dir)
                
                wallet_path = os.path.abspath(temp_wallet_dir)
                
                # Пытаемся подключиться
                try:
                    connection = oracledb.connect(
                        user=self.db_user.get(),
                        password=self.db_password.get(),
                        dsn=self.connect_string.get(),
                        wallet_location=wallet_path,
                        wallet_password=self.wallet_password.get()
                    )
                    
                    # Выполняем простой запрос
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT SYSDATE FROM DUAL")
                        result = cursor.fetchone()
                    
                    connection.close()
                    
                    # Удаляем временный wallet
                    import shutil
                    shutil.rmtree(temp_wallet_dir)
                    
                    messagebox.showinfo("Успех", 
                        f"Подключение успешно!\n\n"
                        f"Время сервера: {result[0]}\n\n"
                        "Настройки корректны. Можете сохранить их.")
                    self.status_label.config(text="✅ Подключение успешно!", foreground="green")
                    
                except Exception as e:
                    # Удаляем временный wallet при ошибке
                    if os.path.exists(temp_wallet_dir):
                        import shutil
                        shutil.rmtree(temp_wallet_dir)
                    raise e
                    
            except zipfile.BadZipFile:
                messagebox.showerror("Ошибка", 
                    "Неверный формат ZIP файла.\n\n"
                    "Убедитесь, что выбран правильный Oracle Wallet файл.")
                self.status_label.config(text="Ошибка: Неверный ZIP файл", foreground="red")
            except Exception as e:
                error_msg = str(e)
                messagebox.showerror("Ошибка подключения", 
                    f"Не удалось подключиться к базе данных:\n\n{error_msg}\n\n"
                    "Проверьте:\n"
                    "• Правильность имени пользователя и пароля\n"
                    "• Правильность Wallet пароля\n"
                    "• Правильность Connect String\n"
                    "• Наличие интернет-соединения")
                self.status_label.config(text=f"❌ Ошибка: {error_msg[:50]}...", foreground="red")
                
        except ImportError:
            messagebox.showerror("Ошибка", 
                "Модуль oracledb не установлен.\n\n"
                "Установите его командой:\n"
                "pip install oracledb")
            self.status_label.config(text="Ошибка: oracledb не установлен", foreground="red")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Неожиданная ошибка: {str(e)}")
            self.status_label.config(text=f"❌ Ошибка: {str(e)[:50]}...", foreground="red")
    
    def save_config(self):
        """Сохраняет настройки в .env файл"""
        try:
            env_content = f"""# ============================================================================
# Oracle OCI Database Configuration
# ============================================================================
# Этот файл создан автоматически через configure_oracle_db.py
# НЕ КОММИТЬ В GIT! (уже добавлен в .gitignore)
# ============================================================================

# Oracle Database User
DB_USER={self.db_user.get()}

# Oracle Database Password (НЕ КОММИТЬ В GIT!)
DB_PASSWORD={self.db_password.get()}

# Oracle Wallet Password (НЕ КОММИТЬ В GIT!)
WALLET_PASSWORD={self.wallet_password.get()}

# Oracle Wallet ZIP файл (имя файла или полный путь)
WALLET_ZIP={self.wallet_zip_path.get()}

# Oracle Wallet директория (папка после распаковки)
WALLET_DIR={self.wallet_dir.get()}

# TNS Alias (опционально)
TNS_ALIAS={self.tns_alias.get()}

# Oracle Connect String (TNS connect string)
CONNECT_STRING={self.connect_string.get()}

# ============================================================================
# Application Configuration
# ============================================================================

# Secret Key для Flask (сгенерируйте уникальный ключ для production)
SECRET_KEY={os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')}

# Environment: LOCAL или REMOTE
ENVIRONMENT={os.environ.get('ENVIRONMENT', 'LOCAL')}

# Server Host (0.0.0.0 для доступа из сети)
SERVER_HOST={os.environ.get('SERVER_HOST', '0.0.0.0')}

# Server Port
PORT={os.environ.get('PORT', '3003')}

# ============================================================================
# Authentication (опционально, если отличается от DB_USER/DB_PASSWORD)
# ============================================================================

# Default Username для веб-интерфейса
DEFAULT_USERNAME={self.db_user.get()}

# Default Password для веб-интерфейса
DEFAULT_PASSWORD={self.db_password.get()}

# ============================================================================
# Remote Server Configuration (опционально)
# ============================================================================

REMOTE_SERVER_HOST={os.environ.get('REMOTE_SERVER_HOST', '92.5.3.187')}
REMOTE_SERVER_PORT={os.environ.get('REMOTE_SERVER_PORT', '8000')}
"""
            
            with open('.env', 'w', encoding='utf-8') as f:
                f.write(env_content)
            
            messagebox.showinfo("Успех", 
                "Настройки успешно сохранены в файл .env\n\n"
                "Теперь приложение будет использовать эти параметры подключения.")
            self.status_label.config(text="✅ Настройки сохранены в .env", foreground="green")
            
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить настройки:\n\n{str(e)}")
            self.status_label.config(text=f"❌ Ошибка сохранения: {str(e)[:50]}...", foreground="red")


def main():
    """Главная функция"""
    root = tk.Tk()
    app = OracleConfigGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()

