#!/bin/bash

if [ "$EUID" -ne 0 ]; then 
    echo "Please run with sudo"
    exit 1
fi

echo "Uninstalling IP Access Manager..."

systemctl stop ip-access-manager 2>/dev/null
systemctl disable ip-access-manager 2>/dev/null
rm -f /etc/systemd/system/ip-access-manager.service
systemctl daemon-reload

echo "Cleaning iptables rules..."
iptables -D INPUT -p tcp --dport 21 -j IP_ACCESS 2>/dev/null
iptables -D INPUT -p tcp --dport 22 -j IP_ACCESS 2>/dev/null
iptables -D INPUT -p tcp --dport 8443 -j ACCEPT 2>/dev/null
iptables -D INPUT -p tcp --dport 8443 -j ACCEPT 2>/dev/null
iptables -D INPUT -p tcp --dport 8443 -j ACCEPT 2>/dev/null
iptables -F IP_ACCESS 2>/dev/null
iptables -X IP_ACCESS 2>/dev/null

if command -v netfilter-persistent &> /dev/null; then
    netfilter-persistent save
else
    iptables-save > /etc/iptables/rules.v4 2>/dev/null || true
fi

rm -rf /opt/ip-access-manager

echo "✅ IP Access Manager uninstalled successfully"
echo "✅ iptables rules cleaned"