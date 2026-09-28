# Исправление проблемы с chromedriver на macOS

## Проблема
macOS блокирует запуск chromedriver с сообщением:
> "chromedriver" Not Opened Apple could not verify "chromedriver" is free of malware

## Решения

### Решение 1: Снять карантин (быстрое)
```bash
xattr -d com.apple.quarantine /opt/homebrew/bin/chromedriver
```

Или если chromedriver установлен в другом месте:
```bash
xattr -d com.apple.quarantine $(which chromedriver)
```

### Решение 2: Разрешить в настройках системы
1. Откройте **System Settings** (Системные настройки)
2. Перейдите в **Privacy & Security** (Конфиденциальность и безопасность)
3. Найдите сообщение о блокировке chromedriver
4. Нажмите **"Allow Anyway"** (Разрешить в любом случае)

### Решение 3: Использовать selenium-manager (автоматически)
Selenium 4.6+ автоматически использует `selenium-manager`, который:
- Автоматически скачивает нужный драйвер
- Не требует ручной установки chromedriver
- Избегает проблем с карантином macOS

Код уже обновлен для использования selenium-manager автоматически.

### Решение 4: Переустановить chromedriver через Homebrew
```bash
brew uninstall chromedriver
brew install chromedriver
xattr -d com.apple.quarantine /opt/homebrew/bin/chromedriver
```

## Проверка
После применения решения, проверьте:
```bash
chromedriver --version
```

Если команда выполняется без ошибок - проблема решена!

## Примечание
Если проблемы продолжаются, приложение автоматически переключится на режим заглушки (stub mode), который генерирует базовые SQL шаблоны без использования ИИ.
