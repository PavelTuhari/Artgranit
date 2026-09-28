#!/bin/bash
# Скрипт для создания GitHub репозитория и push кода

echo "🔍 Проверяю авторизацию GitHub..."
gh auth status

if [ $? -eq 0 ]; then
    echo "✅ Авторизация успешна!"
    echo "📦 Создаю репозиторий на GitHub..."
    
    gh repo create PavelTuhari/Artgranit \
        --public \
        --description "Oracle SQL Developer Web Application - Web-based interface for Oracle Database with SQL Worksheet, Dashboard, and Object Browser" \
        --source=. \
        --remote=origin \
        --push
    
    if [ $? -eq 0 ]; then
        echo "✅ Репозиторий создан и код отправлен!"
        echo "🌐 Репозиторий доступен по адресу: https://github.com/PavelTuhari/Artgranit"
    else
        echo "❌ Ошибка при создании репозитория"
        exit 1
    fi
else
    echo "❌ Необходима авторизация в GitHub"
    echo ""
    echo "Выполните:"
    echo "  gh auth login --web"
    echo ""
    echo "Или откройте в браузере: https://github.com/login/device"
    echo "И введите код, который покажет команда выше"
    exit 1
fi

