#!/usr/bin/env python3
"""
AI Helper для генерации SQL скриптов создания таблиц Oracle
Поддерживает работу через Selenium на localhost и заглушку на сервере
"""
import os
import json
import time
import platform
from typing import Dict, Any, Optional

# URL для LLM чата
LLM_CHAT_URL = "https://llm-chat-app-template.support-621.workers.dev/"

# Определяем, работаем ли мы на сервере (Linux без GUI) или на localhost
IS_SERVER = os.environ.get('IS_SERVER', 'false').lower() == 'true' or \
            (platform.system() == 'Linux' and not os.environ.get('DISPLAY'))


def ask_llm_via_selenium(question: str, timeout: int = 30) -> Optional[str]:
    """
    Задает вопрос LLM через Selenium (только для localhost)
    
    Args:
        question: Вопрос для ИИ
        timeout: Таймаут в секундах
        
    Returns:
        Ответ от ИИ или None в случае ошибки
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        
        # Настройка Chrome
        options = Options()
        options.add_argument("--headless")  # Работаем в фоне
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-software-rasterizer")
        options.add_argument("--disable-extensions")
        
        # Используем selenium-manager для автоматического управления драйверами
        # Это избавляет от проблем с карантином macOS
        driver = None
        try:
            # Selenium 4.6+ автоматически использует selenium-manager
            # Если chromedriver в PATH заблокирован, selenium-manager скачает свой
            driver = webdriver.Chrome(options=options)
            driver.get(LLM_CHAT_URL)
            
            # Ждем загрузки страницы
            time.sleep(3)
            
            # JavaScript функция для отправки вопроса
            ask_js = """
            function askLLM(question) {
              return new Promise((resolve) => {
                const input = document.querySelector("#user-input");
                const button = document.querySelector("#send-button");
                const chat = document.querySelector("#chat-messages");
                
                if (!input || !button || !chat) {
                  resolve("Error: Page elements not found");
                  return;
                }
                
                let lastMessageLength = 0;
                const observer = new MutationObserver(() => {
                  const messages = chat.querySelectorAll(".assistant-message");
                  if (messages.length > 0) {
                    const lastMsg = messages[messages.length - 1];
                    // Используем textContent для сохранения переносов строк
                    const msgText = lastMsg.textContent || lastMsg.innerText || '';
                    
                    // Проверяем, что сообщение не "AI is thinking" и что оно изменилось
                    if (msgText && !msgText.includes("AI is thinking") && msgText.length > lastMessageLength) {
                      lastMessageLength = msgText.length;
                      
                      // Ждем еще немного, чтобы убедиться что ответ полностью получен
                      setTimeout(() => {
                        const finalMsg = lastMsg.textContent || lastMsg.innerText || '';
                        if (finalMsg.length === lastMessageLength) {
                          // Сообщение перестало изменяться - ответ получен полностью
                          observer.disconnect();
                          resolve(finalMsg);
                        }
                      }, 2000);
                    }
                  }
                });
                
                observer.observe(chat, { childList: true, subtree: true, characterData: true });
                
                input.value = question;
                input.dispatchEvent(new Event("input", { bubbles: true }));
                button.click();
                
                // Увеличенный таймаут для длинных ответов (60 секунд)
                setTimeout(() => {
                  observer.disconnect();
                  const messages = chat.querySelectorAll(".assistant-message");
                  if (messages.length > 0) {
                    const lastMsg = messages[messages.length - 1];
                    const msgText = lastMsg.textContent || lastMsg.innerText || '';
                    resolve(msgText || "Timeout: No response received");
                  } else {
                    resolve("Timeout: No response received");
                  }
                }, 60000);
              });
            }
            
            return askLLM(arguments[0]);
            """
            
            # Выполняем JavaScript
            answer = driver.execute_script(ask_js, question)
            
            return answer if answer else None
            
        finally:
            if driver:
                driver.quit()
                
    except ImportError:
        print("Selenium not installed. Install with: pip install selenium")
        return None
    except Exception as e:
        error_msg = str(e)
        # Специальная обработка ошибки macOS карантина
        if "chromedriver" in error_msg.lower() or "malware" in error_msg.lower():
            print(f"⚠️ macOS blocked chromedriver. Try one of these solutions:")
            print(f"   1. Run: xattr -d com.apple.quarantine $(which chromedriver)")
            print(f"   2. Or allow in System Settings > Privacy & Security")
            print(f"   3. Selenium will try to use selenium-manager automatically")
        print(f"Error in Selenium-based LLM request: {e}")
        return None


def generate_table_sql_stub(description: str) -> str:
    """
    Заглушка для генерации SQL на сервере (без Selenium)
    Генерирует базовый шаблон CREATE TABLE на основе описания
    
    Args:
        description: Описание таблицы на русском или английском
        
    Returns:
        SQL скрипт для создания таблицы Oracle
    """
    # Простая заглушка - генерирует базовый шаблон
    table_name = "NEW_TABLE"
    
    # Попытка извлечь имя таблицы из описания
    description_lower = description.lower()
    if "таблица" in description_lower or "table" in description_lower:
        # Пытаемся найти имя таблицы
        words = description.split()
        for i, word in enumerate(words):
            if word.lower() in ["таблица", "table", "таблицу", "таблицы"]:
                if i + 1 < len(words):
                    table_name = words[i + 1].upper().replace(",", "").replace(".", "")
                    break
    
    sql_template = f"""-- Generated SQL for: {description}
-- ⚠️ This is a stub template. For full AI generation, use localhost version.

CREATE TABLE {table_name} (
    ID NUMBER PRIMARY KEY,
    NAME VARCHAR2(100),
    CREATED_DATE DATE DEFAULT SYSDATE,
    STATUS VARCHAR2(20) DEFAULT 'ACTIVE'
);

-- Add your columns here based on the description:
-- {description}

COMMENT ON TABLE {table_name} IS '{description}';
"""
    return sql_template


def generate_table_sql(description: str, use_ai: bool = True) -> Dict[str, Any]:
    """
    Генерирует SQL скрипт для создания таблицы Oracle на основе описания
    
    Args:
        description: Описание таблицы (на русском или английском)
        use_ai: Использовать ли ИИ для генерации (True) или заглушку (False)
        
    Returns:
        Словарь с результатом:
        {
            "success": bool,
            "sql": str,  # SQL скрипт
            "error": str  # Сообщение об ошибке (если success=False)
        }
    """
    if not description or not description.strip():
        return {
            "success": False,
            "error": "Описание таблицы не может быть пустым"
        }
    
    # Формируем промпт для ИИ
    prompt = f"""Создай SQL скрипт для Oracle Database для создания таблицы со следующим описанием:

{description}

Требования:
1. Используй синтаксис Oracle SQL (CREATE TABLE)
2. Добавь PRIMARY KEY
3. Используй подходящие типы данных Oracle (NUMBER, VARCHAR2, DATE, CLOB, BLOB и т.д.)
4. Добавь комментарии к таблице и колонкам (COMMENT ON TABLE, COMMENT ON COLUMN)
5. Используй разумные ограничения (NOT NULL где нужно)
6. Верни только SQL код без дополнительных объяснений

SQL скрипт:"""
    
    # Если это сервер или use_ai=False, используем заглушку
    if IS_SERVER or not use_ai:
        sql = generate_table_sql_stub(description)
        return {
            "success": True,
            "sql": sql,
            "note": "Generated using stub (server mode or AI disabled)"
        }
    
    # Для localhost используем Selenium
    try:
        answer = ask_llm_via_selenium(prompt, timeout=30)
        
        if answer and answer.strip():
            # Очищаем ответ от лишнего текста, оставляем только SQL
            sql = answer.strip()
            
            # Убираем markdown код блоки если есть
            if "```sql" in sql:
                sql = sql.split("```sql")[1].split("```")[0].strip()
            elif "```" in sql:
                sql = sql.split("```")[1].split("```")[0].strip()
            
            # Исправляем проблему: комментарии в одной строке с командами
            # Разделяем комментарии и команды на отдельные строки
            sql_lines = sql.split('\n')
            cleaned_lines = []
            
            for line in sql_lines:
                line = line.strip()
                if not line:
                    continue
                
                # Если строка содержит комментарий и команду в одной строке
                # Например: "-- Создание таблицы CREATE TABLE..."
                if line.startswith('--') and len(line) > 2:
                    # Ищем SQL ключевое слово в любой части строки после комментария
                    rest_after_comment = line[2:]  # Все после "--"
                    sql_keywords = ['CREATE', 'INSERT', 'SELECT', 'UPDATE', 'DELETE', 'ALTER', 'DROP', 'COMMENT', 'GRANT', 'REVOKE']
                    
                    found_keyword = None
                    keyword_pos = -1
                    rest_upper = rest_after_comment.upper()
                    
                    for keyword in sql_keywords:
                        pos = rest_upper.find(keyword)
                        if pos >= 0:
                            # Проверяем, что это начало слова (не часть другого слова)
                            if pos == 0 or not rest_after_comment[pos-1].isalnum():
                                found_keyword = keyword
                                keyword_pos = pos
                                break
                    
                    if found_keyword:
                        # Нашли команду после комментария - разделяем
                        comment = line[:2 + keyword_pos].strip()  # Комментарий до команды
                        command = rest_after_comment[keyword_pos:].strip()  # Команда
                        cleaned_lines.append(comment)
                        cleaned_lines.append(command)
                    else:
                        # Просто комментарий без команды
                        cleaned_lines.append(line)
                else:
                    cleaned_lines.append(line)
            
            sql = '\n'.join(cleaned_lines)
            
            return {
                "success": True,
                "sql": sql
            }
        else:
            # Если ИИ не ответил, используем заглушку
            sql = generate_table_sql_stub(description)
            return {
                "success": True,
                "sql": sql,
                "note": "AI did not respond, using stub template"
            }
            
    except Exception as e:
        # В случае ошибки используем заглушку
        sql = generate_table_sql_stub(description)
        return {
            "success": True,
            "sql": sql,
            "error": f"AI request failed: {str(e)}. Using stub template."
        }


def is_ai_available() -> bool:
    """
    Проверяет, доступен ли ИИ (Selenium установлен и работает)
    
    Returns:
        True если ИИ доступен, False иначе
    """
    if IS_SERVER:
        return False
    
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        
        # Проверяем, можем ли мы создать драйвер
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        
        # Не создаем драйвер, просто проверяем импорт
        return True
    except ImportError:
        return False
    except Exception:
        return False


if __name__ == "__main__":
    # Тестирование
    print("Testing AI Helper...")
    print(f"IS_SERVER: {IS_SERVER}")
    print(f"AI Available: {is_ai_available()}")
    
    test_description = "Таблица для хранения пользователей с полями: id, имя, email, дата регистрации"
    result = generate_table_sql(test_description, use_ai=is_ai_available())
    
    print("\nResult:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
