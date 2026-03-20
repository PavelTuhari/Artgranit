#!/bin/bash
# Setup HTTPS on remote server using Let's Encrypt and Certbot
# Run this script on the remote server after deploying the project

set -e

REMOTE_HOST="${1:-92.5.3.187}"
PROJECT_PATH="${2:-/home/ubuntu/artgranit}"
NGINX_SITES_AVAILABLE="/etc/nginx/sites-available"
NGINX_SITES_ENABLED="/etc/nginx/sites-enabled"

echo "=========================================="
echo "Настройка HTTPS для Artgranit"
echo "=========================================="
echo "Хост: $REMOTE_HOST"
echo "Проект: $PROJECT_PATH"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Скрипт должен запуститься как root (используйте sudo)"
    exit 1
fi

# Step 1: Install nginx and certbot
echo "Шаг 1: Установка nginx и certbot..."
apt-get update -qq
apt-get install -y -qq nginx certbot python3-certbot-nginx

echo "✓ nginx и certbot установлены"
echo ""

# Step 2: Create temporary HTTP-only nginx config for certificate generation
echo "Шаг 2: Создание временной конфигурации nginx (HTTP only)..."

cat > "$NGINX_SITES_AVAILABLE/artgranit" << 'NGINX_TEMP'
upstream artgranit_backend {
    server 127.0.0.1:3003;
    keepalive 32;
}

server {
    listen 80;
    listen [::]:80;
    server_name _;
    
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }
    
    location / {
        proxy_pass http://artgranit_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
NGINX_TEMP

ln -sf "$NGINX_SITES_AVAILABLE/artgranit" "$NGINX_SITES_ENABLED/artgranit" || true
rm -f "$NGINX_SITES_ENABLED/default"

# Test temporary nginx config
echo "Проверка временной конфигурации nginx..."
if ! nginx -t; then
    echo "❌ Ошибка в конфигурации nginx"
    exit 1
fi

echo "✓ Временная конфигурация создана"
echo ""

# Step 3: Start nginx
echo "Шаг 3: Запуск nginx (HTTP only)..."
systemctl restart nginx
systemctl enable nginx

echo "✓ nginx запущен на порту 80"
echo ""

# Step 4: Generate Let's Encrypt certificate (or self-signed if IP address)
echo "Шаг 4: Генерация сертификата SSL/TLS..."
echo "Это может занять несколько минут..."

# Create certbot webroot directory
mkdir -p /var/www/certbot

# Try Let's Encrypt first
certbot_success=false
if [[ $REMOTE_HOST =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "⚠️ $REMOTE_HOST - это IP адрес. Let's Encrypt не выдает сертификаты для IP адресов."
    echo "   Используем самоподписанный сертификат вместо этого."
else
    # Try Let's Encrypt for domain names
    certbot certonly \
        --webroot \
        --webroot-path /var/www/certbot \
        --non-interactive \
        --agree-tos \
        --no-eff-email \
        --email admin@$REMOTE_HOST \
        -d $REMOTE_HOST 2>&1
    
    if [ $? -eq 0 ]; then
        certbot_success=true
        echo "✓ Let's Encrypt сертификат создан"
    fi
fi

if [ "$certbot_success" = false ]; then
    # Generate self-signed certificate
    echo "Генерация самоподписанного сертификата..."
    mkdir -p /etc/letsencrypt/live/$REMOTE_HOST
    
    # Check if certificate already exists
    if [ ! -f "/etc/letsencrypt/live/$REMOTE_HOST/privkey.pem" ]; then
        # Generate private key and self-signed certificate
        openssl req -x509 -newkey rsa:4096 -nodes \
            -keyout /etc/letsencrypt/live/$REMOTE_HOST/privkey.pem \
            -out /etc/letsencrypt/live/$REMOTE_HOST/fullchain.pem \
            -days 365 \
            -subj "/CN=$REMOTE_HOST/O=Artgranit/C=MD"
        
        echo "✓ Самоподписанный сертификат создан"
    else
        echo "✓ Самоподписанный сертификат уже существует"
    fi
fi

echo ""

# Step 5: Copy final nginx configuration with SSL
echo "Шаг 5: Применение финальной конфигурации nginx (с HTTPS)..."
if [ ! -f "$PROJECT_PATH/nginx.conf" ]; then
    echo "⚠️ Файл nginx.conf не найден в $PROJECT_PATH, используем встроенную конфигурацию"
else
    cp "$PROJECT_PATH/nginx.conf" "$NGINX_SITES_AVAILABLE/artgranit"
    echo "✓ Конфигурация nginx скопирована из проекта"
fi

# Test final nginx config
echo "Проверка финальной конфигурации nginx..."
if ! nginx -t; then
    echo "⚠️ Ошибка в конфигурации nginx, откат на временную версию"
    cat > "$NGINX_SITES_AVAILABLE/artgranit" << 'NGINX_FALLBACK'
upstream artgranit_backend {
    server 127.0.0.1:3003;
    keepalive 32;
}

server {
    listen 80;
    listen [::]:80;
    server_name _;
    location / {
        proxy_pass http://artgranit_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
NGINX_FALLBACK
fi

# Reload nginx with final config
echo "Перезагрузка nginx с финальной конфигурацией..."
systemctl reload nginx

echo "✓ nginx перезагружен"
echo ""

# Step 6: Setup automatic certificate renewal
echo "Шаг 6: Настройка автоматического обновления сертификата..."

# Create renewal hooks directory if it doesn't exist
mkdir -p /etc/letsencrypt/renewal-hooks/post

# Create a renewal script
cat > /etc/letsencrypt/renewal-hooks/post/nginx-reload.sh << 'EOF'
#!/bin/bash
systemctl reload nginx
EOF

chmod +x /etc/letsencrypt/renewal-hooks/post/nginx-reload.sh

# Setup certbot renewal timer (already done by certbot, but ensure it's active)
systemctl enable certbot.timer 2>/dev/null || true
systemctl start certbot.timer 2>/dev/null || true

echo "✓ Автоматическое обновление сертификата настроено"
echo ""

# Step 7: Create systemd service for Flask app
echo "Шаг 7: Создание systemd service для Artgranit..."

cat > /etc/systemd/system/artgranit.service << EOF
[Unit]
Description=Artgranit Flask Application
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=$PROJECT_PATH
Environment="PATH=$PROJECT_PATH/venv/bin"
Environment="ENVIRONMENT=REMOTE"
Environment="SERVER_HOST=127.0.0.1"
Environment="PORT=3003"
ExecStart=$PROJECT_PATH/venv/bin/python3 app.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable artgranit
systemctl restart artgranit

sleep 2
if systemctl is-active --quiet artgranit; then
    echo "✓ Artgranit service создан и запущен"
else
    echo "⚠️ Ошибка при запуске artgranit service, проверьте: sudo systemctl status artgranit"
fi

echo ""
echo "=========================================="
echo "✓ Настройка HTTPS завершена успешно!"
echo "=========================================="
echo ""
echo "📝 Информация о сертификате:"
openssl x509 -in /etc/letsencrypt/live/$REMOTE_HOST/cert.pem -text -noout | grep -E "Subject:|Issuer:|Not Before|Not After"
echo ""
echo "🔗 Доступ к приложению:"
echo "   https://$REMOTE_HOST"
echo "   (камера будет работать через HTTPS)"
echo ""
echo "📋 Логи:"
echo "   Flask: sudo journalctl -u artgranit -f"
echo "   Nginx: sudo tail -f /var/log/nginx/error.log"
echo ""
echo "🔄 Обновление сертификата:"
echo "   Автоматическое: проверяется ежедневно"
echo "   Ручное: sudo certbot renew"
echo ""
