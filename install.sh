#!/bin/bash

if [ "$EUID" -ne 0 ]; then 
    echo "Please run with sudo"
    exit 1
fi

echo "Installing IP Access Manager..."

# Установка системных зависимостей
apt-get update
apt-get install -y python3 python3-pip python3-venv iptables iptables-persistent

# Создание директории
mkdir -p /opt/ip-access-manager/templates

# Копирование файлов из текущей директории
cp main.py iptables_manager.py auth.py /opt/ip-access-manager/
cp templates/* /opt/ip-access-manager/templates/ 2>/dev/null || true
cp requirements.txt /opt/ip-access-manager/ 2>/dev/null || echo "No requirements.txt found"

cd /opt/ip-access-manager

# Создание виртуального окружения
echo "Creating virtual environment..."
python3 -m venv venv
if [ $? -ne 0 ]; then
    echo "Failed to create virtual environment"
    exit 1
fi

# Активация и установка пакетов
echo "Installing Python packages..."
/opt/ip-access-manager/venv/bin/pip install --upgrade pip
/opt/ip-access-manager/venv/bin/pip install fastapi uvicorn python-multipart jinja2 passlib bcrypt

# Проверка установки
if [ $? -ne 0 ]; then
    echo "Failed to install Python packages"
    exit 1
fi

# Проверка что python3 работает
if [ ! -f "/opt/ip-access-manager/venv/bin/python3" ]; then
    echo "Virtual environment python not found!"
    exit 1
fi

# Первый запуск для настройки пароля
echo "Starting first-time setup..."
/opt/ip-access-manager/venv/bin/python3 /opt/ip-access-manager/main.py

# Создание systemd сервиса
echo "Creating systemd service..."
cat > /etc/systemd/system/ip-access-manager.service << EOF
[Unit]
Description=IP Access Manager
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/ip-access-manager
ExecStart=/opt/ip-access-manager/venv/bin/python3 /opt/ip-access-manager/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable ip-access-manager
systemctl start ip-access-manager

sleep 3
if systemctl is-active --quiet ip-access-manager; then
    echo "✅ Service started successfully"
else
    echo "❌ Service failed to start"
    systemctl status ip-access-manager --no-pager
    exit 1
fi

IP=$(hostname -I | awk '{print $1}')

echo ""
echo "================================================"
echo "✅ INSTALLATION COMPLETE!"
echo "================================================"
echo "🌐 Web interface: http://$IP:8443"
echo "🔑 Login: admin (password you just set)"
echo ""
echo "📋 Commands:"
echo "   systemctl status ip-access-manager  - Check status"
echo "   journalctl -u ip-access-manager -f  - View logs"
echo "   /opt/ip-access-manager/venv/bin/python3 /opt/ip-access-manager/main.py --remove  - Uninstall"
echo "================================================"