#!/usr/bin/env python3
"""
================================================================================
КОНФИГУРАЦИЯ ПОДКЛЮЧЕНИЙ К ORACLE OCI DATABASE (SQL DEVELOPER STYLE)
================================================================================

ОПИСАНИЕ:
---------
Графический интерфейс для управления несколькими подключениями к Oracle OCI 
Autonomous Database. Интерфейс аналогичен Oracle SQL Developer.

ТРЕБОВАНИЯ:
----------
1. Python 3.8+
2. Tkinter (обычно установлен по умолчанию)
3. python-dotenv (устанавливается через requirements.txt)
4. oracledb (для тестирования подключений)

ИСПОЛЬЗОВАНИЕ:
-------------
python3 configure_oracle_db.py

ФУНКЦИОНАЛ:
----------
- Управление несколькими подключениями (как в SQL Developer)
- Левая панель: список подключений
- Правая панель: редактирование параметров выбранного подключения
- Создание нового подключения
- Редактирование существующего подключения
- Удаление подключения
- Тестирование подключения
- Сохранение подключений в JSON файл
- Сохранение выбранного подключения в .env (как активное)

АВТОР: Разработано в рамках проекта Artgranit OCI
ВЕРСИЯ: 2.0
ДАТА: 2025-12-06
================================================================================
"""

import os
import sys
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from pathlib import Path
from dotenv import load_dotenv, dotenv_values

# Загружаем существующие настройки
load_dotenv()

# Файл для хранения подключений
CONNECTIONS_FILE = 'oracle_connections.json'


class OracleConnection:
    """Класс для хранения параметров подключения"""
    def __init__(self, name="New Connection", db_user="", db_password="", 
                 wallet_password="", wallet_zip="", wallet_dir="", 
                 tns_alias="", connect_string=""):
        self.name = name
        self.db_user = db_user
        self.db_password = db_password
        self.wallet_password = wallet_password
        self.wallet_zip = wallet_zip
        self.wallet_dir = wallet_dir
        self.tns_alias = tns_alias
        self.connect_string = connect_string
    
    def to_dict(self):
        """Преобразует подключение в словарь для JSON"""
        return {
            'name': self.name,
            'db_user': self.db_user,
            'db_password': self.db_password,
            'wallet_password': self.wallet_password,
            'wallet_zip': self.wallet_zip,
            'wallet_dir': self.wallet_dir,
            'tns_alias': self.tns_alias,
            'connect_string': self.connect_string
        }
    
    @classmethod
    def from_dict(cls, data):
        """Создает подключение из словаря"""
        return cls(
            name=data.get('name', 'New Connection'),
            db_user=data.get('db_user', ''),
            db_password=data.get('db_password', ''),
            wallet_password=data.get('wallet_password', ''),
            wallet_zip=data.get('wallet_zip', ''),
            wallet_dir=data.get('wallet_dir', ''),
            tns_alias=data.get('tns_alias', ''),
            connect_string=data.get('connect_string', '')
        )
    
    @classmethod
    def from_env(cls, name="From .env"):
        """Создает подключение из .env файла"""
        env_vars = dotenv_values('.env')
        return cls(
            name=name,
            db_user=env_vars.get('DB_USER', ''),
            db_password=env_vars.get('DB_PASSWORD', ''),
            wallet_password=env_vars.get('WALLET_PASSWORD', ''),
            wallet_zip=env_vars.get('WALLET_ZIP', ''),
            wallet_dir=env_vars.get('WALLET_DIR', ''),
            tns_alias=env_vars.get('TNS_ALIAS', ''),
            connect_string=env_vars.get('CONNECT_STRING', '')
        )


class OracleConfigGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Oracle OCI Database Connections Manager")
        self.root.geometry("1000x750")
        self.root.resizable(True, True)
        
        # Хранилище подключений
        self.connections = {}
        self.current_connection_name = None
        self.current_connection = None
        
        # Загружаем подключения
        self.load_connections()
        
        # Если нет подключений, создаем из .env
        if not self.connections:
            self.load_from_env()
        
        self.create_widgets()
        self.refresh_connections_list()
        
        # Выбираем первое подключение, если есть
        if self.connections:
            first_name = list(self.connections.keys())[0]
            self.select_connection(first_name)
    
    def load_connections(self):
        """Загружает подключения из JSON файла"""
        connections_file = Path(CONNECTIONS_FILE)
        if connections_file.exists():
            try:
                with open(connections_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for name, conn_data in data.items():
                        self.connections[name] = OracleConnection.from_dict(conn_data)
            except Exception as e:
                messagebox.showerror("Ошибка", 
                    f"Не удалось загрузить подключения:\n{str(e)}")
    
    def save_connections(self):
        """Сохраняет подключения в JSON файл"""
        try:
            data = {}
            for name, conn in self.connections.items():
                data[name] = conn.to_dict()
            
            with open(CONNECTIONS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            return True
        except Exception as e:
            messagebox.showerror("Ошибка", 
                f"Не удалось сохранить подключения:\n{str(e)}")
            return False
    
    def load_from_env(self):
        """Загружает подключение из .env файла"""
        env_file = Path('.env')
        if env_file.exists():
            try:
                conn = OracleConnection.from_env("Default Connection")
                if conn.db_user:
                    self.connections[conn.name] = conn
            except Exception as e:
                print(f"Ошибка при загрузке из .env: {e}")
    
    def create_widgets(self):
        """Создает интерфейс в стиле SQL Developer"""
        # Главный контейнер
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # ===== ЛЕВАЯ ПАНЕЛЬ: Список подключений =====
        left_frame = ttk.Frame(main_paned)
        main_paned.add(left_frame, weight=1)
        
        # Заголовок левой панели
        left_header = ttk.Label(left_frame, text="🔌 Connections", 
                               font=("Arial", 12, "bold"))
        left_header.pack(pady=(0, 5))
        
        # Кнопки управления подключениями
        buttons_frame = ttk.Frame(left_frame)
        buttons_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Button(buttons_frame, text="➕ New", 
                  command=self.new_connection, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(buttons_frame, text="🗑️ Delete", 
                  command=self.delete_connection, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(buttons_frame, text="📥 Import", 
                  command=self.import_from_env, width=8).pack(side=tk.LEFT, padx=2)
        
        # Список подключений (Treeview)
        list_frame = ttk.Frame(left_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.connections_tree = ttk.Treeview(list_frame, 
                                            yscrollcommand=scrollbar.set,
                                            selectmode=tk.BROWSE)
        self.connections_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.connections_tree.yview)
        
        self.connections_tree.heading('#0', text='Connection Name', anchor=tk.W)
        
        # Привязываем выбор подключения
        self.connections_tree.bind('<<TreeviewSelect>>', self.on_connection_select)
        
        # ===== ПРАВАЯ ПАНЕЛЬ: Редактирование подключения =====
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=3)
        
        # Настраиваем grid для right_frame
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(1, weight=1)
        
        # Заголовок правой панели
        right_header = ttk.Label(right_frame, text="⚙️ Connection Properties", 
                                font=("Arial", 12, "bold"))
        right_header.grid(row=0, column=0, pady=(0, 10), sticky=tk.W)
        
        # Контейнер с прокруткой для формы
        canvas_frame = ttk.Frame(right_frame)
        canvas_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        canvas_frame.columnconfigure(0, weight=1)
        canvas_frame.rowconfigure(0, weight=1)
        
        canvas = tk.Canvas(canvas_frame)
        scrollbar_right = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar_right.set)
        
        canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar_right.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Форма редактирования
        form_frame = scrollable_frame
        
        # Connection Name
        ttk.Label(form_frame, text="Connection Name:", 
                 font=("Arial", 10, "bold")).grid(row=0, column=0, sticky=tk.W, pady=5, padx=5)
        self.conn_name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.conn_name_var, width=50).grid(
            row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        
        # DB User
        ttk.Label(form_frame, text="Database User:", 
                 font=("Arial", 10, "bold")).grid(row=1, column=0, sticky=tk.W, pady=5, padx=5)
        self.db_user_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.db_user_var, width=50).grid(
            row=1, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        
        # DB Password
        ttk.Label(form_frame, text="Database Password:", 
                 font=("Arial", 10, "bold")).grid(row=2, column=0, sticky=tk.W, pady=5, padx=5)
        password_frame = ttk.Frame(form_frame)
        password_frame.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        password_frame.columnconfigure(0, weight=1)
        
        self.db_password_var = tk.StringVar()
        self.db_password_entry = ttk.Entry(password_frame, textvariable=self.db_password_var, 
                                          width=40, show="*")
        self.db_password_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(password_frame, text="👁", width=3,
                  command=lambda: self.toggle_password(self.db_password_entry)).pack(side=tk.LEFT, padx=2)
        
        # Wallet Password
        ttk.Label(form_frame, text="Wallet Password:", 
                 font=("Arial", 10, "bold")).grid(row=3, column=0, sticky=tk.W, pady=5, padx=5)
        wallet_pass_frame = ttk.Frame(form_frame)
        wallet_pass_frame.grid(row=3, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        wallet_pass_frame.columnconfigure(0, weight=1)
        
        self.wallet_password_var = tk.StringVar()
        self.wallet_password_entry = ttk.Entry(wallet_pass_frame, 
                                              textvariable=self.wallet_password_var, 
                                              width=40, show="*")
        self.wallet_password_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(wallet_pass_frame, text="👁", width=3,
                  command=lambda: self.toggle_password(self.wallet_password_entry)).pack(side=tk.LEFT, padx=2)
        
        # Wallet ZIP
        ttk.Label(form_frame, text="Wallet ZIP File:", 
                 font=("Arial", 10, "bold")).grid(row=4, column=0, sticky=tk.W, pady=5, padx=5)
        wallet_zip_frame = ttk.Frame(form_frame)
        wallet_zip_frame.grid(row=4, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        wallet_zip_frame.columnconfigure(0, weight=1)
        
        self.wallet_zip_var = tk.StringVar()
        ttk.Entry(wallet_zip_frame, textvariable=self.wallet_zip_var, width=40).pack(
            side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(wallet_zip_frame, text="Browse...", 
                  command=self.browse_wallet_file, width=10).pack(side=tk.LEFT, padx=2)
        
        # Wallet Directory
        ttk.Label(form_frame, text="Wallet Directory:", 
                 font=("Arial", 10, "bold")).grid(row=5, column=0, sticky=tk.W, pady=5, padx=5)
        self.wallet_dir_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.wallet_dir_var, width=50).grid(
            row=5, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        
        # TNS Alias
        ttk.Label(form_frame, text="TNS Alias:", 
                 font=("Arial", 10, "bold")).grid(row=6, column=0, sticky=tk.W, pady=5, padx=5)
        self.tns_alias_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.tns_alias_var, width=50).grid(
            row=6, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        
        # Connect String
        ttk.Label(form_frame, text="Connect String:", 
                 font=("Arial", 10, "bold")).grid(row=7, column=0, sticky=tk.W, pady=5, padx=5)
        self.connect_string_text = scrolledtext.ScrolledText(form_frame, width=50, 
                                                            height=5, wrap=tk.WORD)
        self.connect_string_text.grid(row=7, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        
        # Настройка растягивания колонок
        form_frame.columnconfigure(1, weight=1)
        
        # Кнопки действий (внизу)
        action_frame = ttk.Frame(right_frame)
        action_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=10)
        
        ttk.Button(action_frame, text="🧪 Test Connection", 
                  command=self.test_connection, width=18).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="💾 Save Connection", 
                  command=self.save_current_connection, width=18).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="💾 Save to .env", 
                  command=self.save_to_env, width=18).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="❌ Exit", 
                  command=self.root.quit, width=12).pack(side=tk.LEFT, padx=5)
        
        # Статусная строка (внизу под кнопками)
        self.status_label = ttk.Label(right_frame, text="Ready", 
                                     foreground="green", font=("Arial", 9))
        self.status_label.grid(row=3, column=0, pady=5, sticky=tk.W)
    
    def toggle_password(self, entry):
        """Переключает видимость пароля"""
        if entry.cget('show') == '*':
            entry.config(show='')
        else:
            entry.config(show='*')
    
    def refresh_connections_list(self):
        """Обновляет список подключений"""
        # Очищаем список
        for item in self.connections_tree.get_children():
            self.connections_tree.delete(item)
        
        # Добавляем подключения
        for name in sorted(self.connections.keys()):
            self.connections_tree.insert('', tk.END, text=name, values=(name,))
    
    def on_connection_select(self, event):
        """Обработчик выбора подключения"""
        selection = self.connections_tree.selection()
        if selection:
            item = self.connections_tree.item(selection[0])
            name = item['text']
            self.select_connection(name)
    
    def select_connection(self, name):
        """Загружает подключение для редактирования"""
        if name in self.connections:
            self.current_connection_name = name
            self.current_connection = self.connections[name]
            
            # Заполняем форму
            self.conn_name_var.set(self.current_connection.name)
            self.db_user_var.set(self.current_connection.db_user)
            self.db_password_var.set(self.current_connection.db_password)
            self.wallet_password_var.set(self.current_connection.wallet_password)
            self.wallet_zip_var.set(self.current_connection.wallet_zip)
            self.wallet_dir_var.set(self.current_connection.wallet_dir)
            self.tns_alias_var.set(self.current_connection.tns_alias)
            
            self.connect_string_text.delete('1.0', tk.END)
            self.connect_string_text.insert('1.0', self.current_connection.connect_string)
            
            self.status_label.config(text=f"Selected: {name}", foreground="blue")
    
    def new_connection(self):
        """Создает новое подключение"""
        # Генерируем уникальное имя
        base_name = "New Connection"
        name = base_name
        counter = 1
        while name in self.connections:
            name = f"{base_name} {counter}"
            counter += 1
        
        # Создаем новое подключение
        new_conn = OracleConnection(name=name)
        self.connections[name] = new_conn
        
        # Сохраняем и обновляем
        self.save_connections()
        self.refresh_connections_list()
        
        # Выбираем новое подключение
        self.select_connection(name)
        
        # Выделяем в дереве
        for item in self.connections_tree.get_children():
            if self.connections_tree.item(item)['text'] == name:
                self.connections_tree.selection_set(item)
                self.connections_tree.see(item)
                break
        
        self.status_label.config(text=f"Created new connection: {name}", foreground="green")
    
    def delete_connection(self):
        """Удаляет выбранное подключение"""
        selection = self.connections_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a connection to delete.")
            return
        
        item = self.connections_tree.item(selection[0])
        name = item['text']
        
        if messagebox.askyesno("Confirm Delete", 
                              f"Are you sure you want to delete connection '{name}'?"):
            # Удаляем подключение
            if name in self.connections:
                del self.connections[name]
                
                # Если это было текущее подключение, очищаем форму
                if self.current_connection_name == name:
                    self.current_connection_name = None
                    self.current_connection = None
                    self.clear_form()
                
                # Сохраняем и обновляем
                self.save_connections()
                self.refresh_connections_list()
                
                self.status_label.config(text=f"Deleted: {name}", foreground="orange")
            else:
                messagebox.showerror("Error", f"Connection '{name}' not found.")
    
    def import_from_env(self):
        """Импортирует подключение из .env файла"""
        conn = OracleConnection.from_env("From .env")
        if not conn.db_user:
            messagebox.showwarning("Warning", 
                                  "No connection data found in .env file.")
            return
        
        # Генерируем уникальное имя
        base_name = conn.name
        name = base_name
        counter = 1
        while name in self.connections:
            name = f"{base_name} {counter}"
            counter += 1
        conn.name = name
        
        self.connections[name] = conn
        self.save_connections()
        self.refresh_connections_list()
        self.select_connection(name)
        
        self.status_label.config(text=f"Imported: {name}", foreground="green")
    
    def clear_form(self):
        """Очищает форму"""
        self.conn_name_var.set("")
        self.db_user_var.set("")
        self.db_password_var.set("")
        self.wallet_password_var.set("")
        self.wallet_zip_var.set("")
        self.wallet_dir_var.set("")
        self.tns_alias_var.set("")
        self.connect_string_text.delete('1.0', tk.END)
    
    def browse_wallet_file(self):
        """Открывает диалог выбора Wallet ZIP файла"""
        filename = filedialog.askopenfilename(
            title="Select Oracle Wallet ZIP file",
            filetypes=[("ZIP files", "*.zip"), ("All files", "*.*")]
        )
        if filename:
            # Сохраняем только имя файла, если он в текущей директории
            if os.path.dirname(filename) == os.getcwd():
                self.wallet_zip_var.set(os.path.basename(filename))
            else:
                self.wallet_zip_var.set(filename)
    
    def get_form_data(self):
        """Получает данные из формы"""
        return {
            'name': self.conn_name_var.get().strip(),
            'db_user': self.db_user_var.get().strip(),
            'db_password': self.db_password_var.get().strip(),
            'wallet_password': self.wallet_password_var.get().strip(),
            'wallet_zip': self.wallet_zip_var.get().strip(),
            'wallet_dir': self.wallet_dir_var.get().strip(),
            'tns_alias': self.tns_alias_var.get().strip(),
            'connect_string': self.connect_string_text.get('1.0', tk.END).strip()
        }
    
    def save_current_connection(self):
        """Сохраняет текущее подключение"""
        data = self.get_form_data()
        
        if not data['name']:
            messagebox.showerror("Error", "Connection name cannot be empty!")
            return
        
        # Если имя изменилось, проверяем на дубликаты
        new_name = data['name']
        if new_name != self.current_connection_name:
            if new_name in self.connections:
                messagebox.showerror("Error", 
                    f"Connection '{new_name}' already exists!")
                return
            
            # Удаляем старое подключение, если имя изменилось
            if self.current_connection_name:
                del self.connections[self.current_connection_name]
        
        # Обновляем или создаем подключение
        conn = OracleConnection(
            name=new_name,
            db_user=data['db_user'],
            db_password=data['db_password'],
            wallet_password=data['wallet_password'],
            wallet_zip=data['wallet_zip'],
            wallet_dir=data['wallet_dir'],
            tns_alias=data['tns_alias'],
            connect_string=data['connect_string']
        )
        
        self.connections[new_name] = conn
        self.current_connection_name = new_name
        self.current_connection = conn
        
        if self.save_connections():
            self.refresh_connections_list()
            self.select_connection(new_name)
            self.status_label.config(text=f"✅ Saved: {new_name}", foreground="green")
            messagebox.showinfo("Success", f"Connection '{new_name}' saved successfully!")
    
    def test_connection(self):
        """Тестирует подключение"""
        data = self.get_form_data()
        
        if not data['db_user'] or not data['connect_string']:
            messagebox.showerror("Error", 
                "Please fill in at least Database User and Connect String.")
            return
        
        self.status_label.config(text="Testing connection...", foreground="blue")
        self.root.update()
        
        try:
            import oracledb
            import zipfile
            
            # Проверяем наличие wallet файла
            wallet_zip = data['wallet_zip']
            if wallet_zip and not os.path.exists(wallet_zip):
                messagebox.showerror("Error", 
                    f"Wallet ZIP file not found: {wallet_zip}\n\n"
                    "Please check the file path.")
                self.status_label.config(text="Error: Wallet file not found", foreground="red")
                return
            
            # Распаковываем wallet временно
            wallet_dir = data['wallet_dir'] or "wallet_test"
            temp_wallet_dir = f"{wallet_dir}_test"
            
            try:
                if os.path.exists(temp_wallet_dir):
                    import shutil
                    shutil.rmtree(temp_wallet_dir)
                
                if wallet_zip and os.path.exists(wallet_zip):
                    with zipfile.ZipFile(wallet_zip, 'r') as zip_ref:
                        zip_ref.extractall(temp_wallet_dir)
                    wallet_path = os.path.abspath(temp_wallet_dir)
                else:
                    wallet_path = None
                
                # Пытаемся подключиться
                try:
                    if wallet_path:
                        connection = oracledb.connect(
                            user=data['db_user'],
                            password=data['db_password'],
                            dsn=data['connect_string'],
                            wallet_location=wallet_path,
                            wallet_password=data['wallet_password']
                        )
                    else:
                        connection = oracledb.connect(
                            user=data['db_user'],
                            password=data['db_password'],
                            dsn=data['connect_string']
                        )
                    
                    # Выполняем простой запрос
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT SYSDATE, SYS_CONTEXT('USERENV', 'SERVER_HOST') FROM DUAL")
                        result = cursor.fetchone()
                    
                    connection.close()
                    
                    # Удаляем временный wallet
                    if os.path.exists(temp_wallet_dir):
                        import shutil
                        shutil.rmtree(temp_wallet_dir)
                    
                    messagebox.showinfo("Success", 
                        f"✅ Connection successful!\n\n"
                        f"Server Date: {result[0]}\n"
                        f"Server Host: {result[1]}\n\n"
                        "Connection parameters are correct.")
                    self.status_label.config(text="✅ Connection successful!", foreground="green")
                    
                except Exception as e:
                    # Удаляем временный wallet при ошибке
                    if os.path.exists(temp_wallet_dir):
                        import shutil
                        shutil.rmtree(temp_wallet_dir)
                    raise e
                    
            except zipfile.BadZipFile:
                messagebox.showerror("Error", 
                    "Invalid ZIP file format.\n\n"
                    "Please select a valid Oracle Wallet file.")
                self.status_label.config(text="Error: Invalid ZIP file", foreground="red")
            except Exception as e:
                error_msg = str(e)
                messagebox.showerror("Connection Error", 
                    f"Failed to connect to database:\n\n{error_msg}\n\n"
                    "Please check:\n"
                    "• Username and password\n"
                    "• Wallet password\n"
                    "• Connect String\n"
                    "• Internet connection")
                self.status_label.config(text=f"❌ Error: {error_msg[:50]}...", foreground="red")
                
        except ImportError:
            messagebox.showerror("Error", 
                "Module 'oracledb' is not installed.\n\n"
                "Install it with:\n"
                "pip install oracledb")
            self.status_label.config(text="Error: oracledb not installed", foreground="red")
        except Exception as e:
            messagebox.showerror("Error", f"Unexpected error: {str(e)}")
            self.status_label.config(text=f"❌ Error: {str(e)[:50]}...", foreground="red")
    
    def save_to_env(self):
        """Сохраняет текущее подключение в .env файл"""
        data = self.get_form_data()
        
        if not data['db_user']:
            messagebox.showerror("Error", "Please fill in connection parameters first.")
            return
        
        try:
            # Читаем существующий .env
            env_vars = {}
            env_file = Path('.env')
            if env_file.exists():
                env_vars = dotenv_values('.env')
            
            # Обновляем Oracle параметры
            env_vars['DB_USER'] = data['db_user']
            env_vars['DB_PASSWORD'] = data['db_password']
            env_vars['WALLET_PASSWORD'] = data['wallet_password']
            env_vars['WALLET_ZIP'] = data['wallet_zip']
            env_vars['WALLET_DIR'] = data['wallet_dir']
            env_vars['TNS_ALIAS'] = data['tns_alias']
            env_vars['CONNECT_STRING'] = data['connect_string']
            
            # Обновляем DEFAULT_USERNAME и DEFAULT_PASSWORD
            env_vars['DEFAULT_USERNAME'] = data['db_user']
            env_vars['DEFAULT_PASSWORD'] = data['db_password']
            
            # Сохраняем все остальные параметры
            env_content = f"""# ============================================================================
# Oracle OCI Database Configuration
# ============================================================================
# Этот файл обновлен через configure_oracle_db.py
# НЕ КОММИТЬ В GIT! (уже добавлен в .gitignore)
# ============================================================================

# Oracle Database User
DB_USER={env_vars.get('DB_USER', '')}

# Oracle Database Password (НЕ КОММИТЬ В GIT!)
DB_PASSWORD={env_vars.get('DB_PASSWORD', '')}

# Oracle Wallet Password (НЕ КОММИТЬ В GIT!)
WALLET_PASSWORD={env_vars.get('WALLET_PASSWORD', '')}

# Oracle Wallet ZIP файл (имя файла или полный путь)
WALLET_ZIP={env_vars.get('WALLET_ZIP', '')}

# Oracle Wallet директория (папка после распаковки)
WALLET_DIR={env_vars.get('WALLET_DIR', '')}

# TNS Alias (опционально)
TNS_ALIAS={env_vars.get('TNS_ALIAS', '')}

# Oracle Connect String (TNS connect string)
CONNECT_STRING={env_vars.get('CONNECT_STRING', '')}

# ============================================================================
# Application Configuration
# ============================================================================

# Secret Key для Flask (сгенерируйте уникальный ключ для production)
SECRET_KEY={env_vars.get('SECRET_KEY', 'dev-secret-key-change-in-production')}

# Environment: LOCAL или REMOTE
ENVIRONMENT={env_vars.get('ENVIRONMENT', 'LOCAL')}

# Server Host (0.0.0.0 для доступа из сети)
SERVER_HOST={env_vars.get('SERVER_HOST', '0.0.0.0')}

# Server Port
PORT={env_vars.get('PORT', '3003')}

# ============================================================================
# Authentication (опционально, если отличается от DB_USER/DB_PASSWORD)
# ============================================================================

# Default Username для веб-интерфейса
DEFAULT_USERNAME={env_vars.get('DEFAULT_USERNAME', env_vars.get('DB_USER', ''))}

# Default Password для веб-интерфейса
DEFAULT_PASSWORD={env_vars.get('DEFAULT_PASSWORD', env_vars.get('DB_PASSWORD', ''))}

# ============================================================================
# Remote Server Configuration (опционально)
# ============================================================================

REMOTE_SERVER_HOST={env_vars.get('REMOTE_SERVER_HOST', '92.5.3.187')}
REMOTE_SERVER_PORT={env_vars.get('REMOTE_SERVER_PORT', '8000')}
"""
            
            with open('.env', 'w', encoding='utf-8') as f:
                f.write(env_content)
            
            messagebox.showinfo("Success", 
                f"✅ Connection '{data['name']}' saved to .env file!\n\n"
                "The application will now use these connection parameters.")
            self.status_label.config(text=f"✅ Saved to .env: {data['name']}", foreground="green")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save to .env:\n\n{str(e)}")
            self.status_label.config(text=f"❌ Error saving to .env: {str(e)[:50]}...", foreground="red")


def main():
    """Главная функция"""
    root = tk.Tk()
    app = OracleConfigGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()
