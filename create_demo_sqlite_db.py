#!/usr/bin/env python3
"""
Скрипт для создания демо SQLite базы данных с тестовыми данными
"""
import sqlite3
import os
from datetime import datetime, timedelta

# Путь к демо БД
DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'demo_database.db')

def create_demo_database():
    """Создает демо SQLite базу данных с тестовыми данными"""
    
    # Удаляем существующую БД, если есть
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Удалена существующая БД: {DB_PATH}")
    
    # Создаем подключение
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Создаем таблицу Employees (Сотрудники)
        cursor.execute("""
            CREATE TABLE employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                department TEXT NOT NULL,
                position TEXT NOT NULL,
                salary REAL,
                hire_date DATE NOT NULL,
                status TEXT DEFAULT 'active'
            )
        """)
        
        # Создаем таблицу Departments (Отделы)
        cursor.execute("""
            CREATE TABLE departments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                location TEXT,
                manager_id INTEGER,
                budget REAL,
                FOREIGN KEY (manager_id) REFERENCES employees(id)
            )
        """)
        
        # Создаем таблицу Projects (Проекты)
        cursor.execute("""
            CREATE TABLE projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                start_date DATE,
                end_date DATE,
                status TEXT DEFAULT 'planning',
                budget REAL
            )
        """)
        
        # Создаем таблицу Project_Assignments (Назначения на проекты)
        cursor.execute("""
            CREATE TABLE project_assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                employee_id INTEGER NOT NULL,
                role TEXT,
                assigned_date DATE,
                hours_allocated REAL,
                FOREIGN KEY (project_id) REFERENCES projects(id),
                FOREIGN KEY (employee_id) REFERENCES employees(id)
            )
        """)
        
        # Вставляем данные в таблицу Departments
        departments_data = [
            ('IT', 'Building A, Floor 3', None, 500000.00),
            ('Sales', 'Building B, Floor 1', None, 300000.00),
            ('Marketing', 'Building B, Floor 2', None, 250000.00),
            ('HR', 'Building A, Floor 1', None, 150000.00),
            ('Finance', 'Building A, Floor 2', None, 400000.00)
        ]
        
        cursor.executemany("""
            INSERT INTO departments (name, location, manager_id, budget)
            VALUES (?, ?, ?, ?)
        """, departments_data)
        
        # Вставляем данные в таблицу Employees
        employees_data = [
            ('Иван', 'Иванов', 'ivan.ivanov@company.com', 'IT', 'Senior Developer', 95000.00, '2020-01-15', 'active'),
            ('Петр', 'Петров', 'petr.petrov@company.com', 'IT', 'Database Administrator', 105000.00, '2019-06-01', 'active'),
            ('Мария', 'Сидорова', 'maria.sidorova@company.com', 'Sales', 'Sales Manager', 75000.00, '2021-03-10', 'active'),
            ('Анна', 'Козлова', 'anna.kozlova@company.com', 'Marketing', 'Marketing Specialist', 65000.00, '2022-01-20', 'active'),
            ('Сергей', 'Смирнов', 'sergey.smirnov@company.com', 'HR', 'HR Manager', 70000.00, '2020-09-05', 'active'),
            ('Елена', 'Волкова', 'elena.volkova@company.com', 'Finance', 'Financial Analyst', 80000.00, '2021-11-15', 'active'),
            ('Дмитрий', 'Новиков', 'dmitry.novikov@company.com', 'IT', 'Junior Developer', 55000.00, '2023-02-01', 'active'),
            ('Ольга', 'Морозова', 'olga.morozova@company.com', 'Sales', 'Sales Representative', 60000.00, '2022-05-12', 'active'),
            ('Алексей', 'Лебедев', 'alexey.lebedev@company.com', 'IT', 'DevOps Engineer', 110000.00, '2020-07-20', 'active'),
            ('Наталья', 'Соколова', 'natalya.sokolova@company.com', 'Marketing', 'Marketing Manager', 85000.00, '2021-04-03', 'active')
        ]
        
        cursor.executemany("""
            INSERT INTO employees (first_name, last_name, email, department, position, salary, hire_date, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, employees_data)
        
        # Получаем ID отделов для обновления manager_id
        cursor.execute("SELECT id, name FROM departments")
        dept_dict = {name: id for id, name in cursor.fetchall()}
        
        # Обновляем manager_id в departments
        cursor.execute("UPDATE departments SET manager_id = 1 WHERE name = 'IT'")
        cursor.execute("UPDATE departments SET manager_id = 3 WHERE name = 'Sales'")
        cursor.execute("UPDATE departments SET manager_id = 10 WHERE name = 'Marketing'")
        cursor.execute("UPDATE departments SET manager_id = 5 WHERE name = 'HR'")
        cursor.execute("UPDATE departments SET manager_id = 6 WHERE name = 'Finance'")
        
        # Вставляем данные в таблицу Projects
        projects_data = [
            ('E-Commerce Platform', 'Разработка новой платформы электронной торговли', '2024-01-01', '2024-12-31', 'in_progress', 250000.00),
            ('Mobile App', 'Создание мобильного приложения для клиентов', '2024-03-01', '2024-09-30', 'in_progress', 180000.00),
            ('Data Analytics System', 'Система аналитики данных и отчетности', '2024-02-15', '2024-11-30', 'planning', 220000.00),
            ('Website Redesign', 'Обновление корпоративного сайта', '2023-10-01', '2024-06-30', 'completed', 95000.00),
            ('CRM Implementation', 'Внедрение системы управления клиентами', '2024-04-01', '2024-10-31', 'in_progress', 150000.00)
        ]
        
        cursor.executemany("""
            INSERT INTO projects (name, description, start_date, end_date, status, budget)
            VALUES (?, ?, ?, ?, ?, ?)
        """, projects_data)
        
        # Вставляем данные в таблицу Project_Assignments
        assignments_data = [
            (1, 1, 'Lead Developer', '2024-01-01', 160.0),
            (1, 2, 'Database Architect', '2024-01-01', 120.0),
            (1, 7, 'Developer', '2024-01-15', 120.0),
            (2, 1, 'Technical Lead', '2024-03-01', 80.0),
            (2, 7, 'Mobile Developer', '2024-03-01', 160.0),
            (2, 10, 'Marketing Coordinator', '2024-03-01', 40.0),
            (3, 2, 'Data Architect', '2024-02-15', 100.0),
            (3, 6, 'Financial Analyst', '2024-02-15', 60.0),
            (4, 10, 'Project Manager', '2023-10-01', 80.0),
            (4, 4, 'Marketing Specialist', '2023-10-01', 120.0),
            (5, 3, 'Sales Coordinator', '2024-04-01', 80.0),
            (5, 8, 'Sales Representative', '2024-04-01', 100.0),
            (5, 5, 'HR Coordinator', '2024-04-01', 40.0)
        ]
        
        cursor.executemany("""
            INSERT INTO project_assignments (project_id, employee_id, role, assigned_date, hours_allocated)
            VALUES (?, ?, ?, ?, ?)
        """, assignments_data)
        
        # Создаем индексы для оптимизации
        cursor.execute("CREATE INDEX idx_employees_department ON employees(department)")
        cursor.execute("CREATE INDEX idx_project_assignments_project ON project_assignments(project_id)")
        cursor.execute("CREATE INDEX idx_project_assignments_employee ON project_assignments(employee_id)")
        
        # Сохраняем изменения
        conn.commit()
        
        # Выводим статистику
        cursor.execute("SELECT COUNT(*) FROM employees")
        employee_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM departments")
        dept_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM projects")
        project_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM project_assignments")
        assignment_count = cursor.fetchone()[0]
        
        print(f"✅ Демо SQLite база данных создана успешно!")
        print(f"📁 Путь: {DB_PATH}")
        print(f"")
        print(f"📊 Статистика:")
        print(f"   - Отделов: {dept_count}")
        print(f"   - Сотрудников: {employee_count}")
        print(f"   - Проектов: {project_count}")
        print(f"   - Назначений: {assignment_count}")
        print(f"")
        print(f"📋 Таблицы:")
        print(f"   - employees (Сотрудники)")
        print(f"   - departments (Отделы)")
        print(f"   - projects (Проекты)")
        print(f"   - project_assignments (Назначения на проекты)")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Ошибка при создании БД: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    create_demo_database()

