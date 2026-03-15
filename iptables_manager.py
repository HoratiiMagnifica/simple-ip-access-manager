#!/usr/bin/env python3
import subprocess
import ipaddress
import os

class IPTablesManager:
    def __init__(self):
        self.chain_name = "IP_ACCESS"
        self.web_port = 8443
        self.services = [
            {"port": 22, "protocol": "tcp", "name": "SSH"},
            {"port": 21, "protocol": "tcp", "name": "FTP"}
        ]
    
    def _run_cmd(self, cmd):
        try:
            return subprocess.run(cmd, shell=True, capture_output=True, text=True)
        except:
            return None
    
    def setup_initial_rules(self):
        self._run_cmd(f"iptables -N {self.chain_name} 2>/dev/null || true")
        self._run_cmd(f"iptables -F {self.chain_name}")
        
        for service in self.services:
            self._run_cmd(f"iptables -D INPUT -p {service['protocol']} --dport {service['port']} -j {self.chain_name} 2>/dev/null || true")
        
        self._run_cmd(f"iptables -A {self.chain_name} -i lo -j ACCEPT")
        self._run_cmd(f"iptables -A {self.chain_name} -m state --state ESTABLISHED,RELATED -j ACCEPT")
        
        self._run_cmd(f"iptables -D INPUT -p tcp --dport {self.web_port} -j ACCEPT 2>/dev/null || true")
        self._run_cmd(f"iptables -I INPUT 1 -p tcp --dport {self.web_port} -j ACCEPT")
        
        for service in self.services:
            self._run_cmd(f"iptables -I INPUT 1 -p {service['protocol']} --dport {service['port']} -j {self.chain_name}")
        
        self._run_cmd(f"iptables -A {self.chain_name} -m limit --limit 5/min -j LOG --log-prefix 'IP_ACCESS_BLOCKED: '")
        for service in self.services:
            self._run_cmd(f"iptables -A {self.chain_name} -p {service['protocol']} --dport {service['port']} -j DROP")
        
        self._save_rules()
    
    def apply_allowed_ips(self, allowed_ips):
        self._run_cmd(f"iptables -F {self.chain_name}")
        
        self._run_cmd(f"iptables -A {self.chain_name} -i lo -j ACCEPT")
        self._run_cmd(f"iptables -A {self.chain_name} -m state --state ESTABLISHED,RELATED -j ACCEPT")
        
        for item in allowed_ips:
            ip = item["ip"] if isinstance(item, dict) else item
            if self.validate_ip(ip):
                for service in self.services:
                    self._run_cmd(f"iptables -A {self.chain_name} -s {ip} -p {service['protocol']} --dport {service['port']} -j ACCEPT")
        
        self._run_cmd(f"iptables -A {self.chain_name} -m limit --limit 5/min -j LOG --log-prefix 'IP_ACCESS_BLOCKED: '")
        for service in self.services:
            self._run_cmd(f"iptables -A {self.chain_name} -p {service['protocol']} --dport {service['port']} -j DROP")
        
        self._save_rules()
        return True
    
    def _save_rules(self):
        try:
            if os.path.exists("/etc/init.d/netfilter-persistent"):
                self._run_cmd("netfilter-persistent save")
            else:
                self._run_cmd("mkdir -p /etc/iptables")
                self._run_cmd("iptables-save > /etc/iptables/rules.v4")
        except:
            pass
    
    def validate_ip(self, ip):
        try:
            ipaddress.ip_network(ip, strict=False)
            return True
        except:
            return False
    
    def check_rules_applied(self):
        result = self._run_cmd(f"iptables -L {self.chain_name} -n")
        return result and "Chain" in result.stdout and "DROP" in result.stdout
    
    def cleanup(self):
        for service in self.services:
            self._run_cmd(f"iptables -D INPUT -p {service['protocol']} --dport {service['port']} -j {self.chain_name} 2>/dev/null || true")
        
        self._run_cmd(f"iptables -F {self.chain_name} 2>/dev/null || true")
        self._run_cmd(f"iptables -X {self.chain_name} 2>/dev/null || true")