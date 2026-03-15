#!/bin/bash

if [ "$EUID" -ne 0 ]; then 
    echo "Please run with sudo"
    exit 1
fi

cd /opt/ip-access-manager
source venv/bin/activate
python3 main.py --remove

rm -rf /opt/ip-access-manager
rm -f /etc/systemd/system/ip-access-manager.service

systemctl daemon-reload

echo "IP Access Manager uninstalled"