#!/bin/bash

if [ "$EUID" -ne 0 ]; then 
    echo "Please run with sudo"
    exit 1
fi

echo "Installing IP Access Manager..."

apt-get update
apt-get install -y python3 python3-pip python3-venv iptables iptables-persistent

mkdir -p /opt/ip-access-manager/templates
cp main.py iptables_manager.py auth.py /opt/ip-access-manager/
cp templates/* /opt/ip-access-manager/templates/ 2>/dev/null || true

cd /opt/ip-access-manager
python3 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn python-multipart jinja2 passlib bcrypt

python3 main.py

echo "Installation complete!"