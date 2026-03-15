#!/usr/bin/env python3
import os
import sys
import json
import getpass
import subprocess
import secrets
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import uvicorn

from iptables_manager import IPTablesManager
from auth import AuthManager, get_current_user, hash_password

CONFIG_FILE = "config.json"
DEFAULT_PORT = 8443
SERVICE_NAME = "ip-access-manager"
SERVICE_PATH = f"/etc/systemd/system/{SERVICE_NAME}.service"

iptables = None
auth_manager = None
config = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    global iptables, auth_manager, config
    config = load_config()
    iptables = IPTablesManager()
    auth_manager = AuthManager(config.get("admin_password", ""))
    app.state.auth_manager = auth_manager
    
    iptables.setup_initial_rules()
    
    if config.get("allowed_ips"):
        iptables.apply_allowed_ips(config["allowed_ips"])
    
    yield

app = FastAPI(lifespan=lifespan)
templates = Jinja2Templates(directory="templates")

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if "allowed_ips" not in data:
                    data["allowed_ips"] = []
                return data
        except:
            return {"allowed_ips": [], "admin_password": ""}
    return {"allowed_ips": [], "admin_password": ""}

def save_config():
    global config
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4)

@app.get("/", response_class=HTMLResponse)
async def admin_page(request: Request, user=Depends(get_current_user)):
    return templates.TemplateResponse(
        "index.html", 
        {"request": request, "allowed_ips": config.get("allowed_ips", [])}
    )

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if username == "admin" and auth_manager.verify_password(password):
        token = secrets.token_urlsafe(32)
        auth_manager.create_session(token)
        response = RedirectResponse(url="/", status_code=303)
        response.set_cookie(key="session", value=token)
        return response
    raise HTTPException(status_code=401, detail="Invalid credentials")

@app.post("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("session")
    return response

@app.post("/api/ips/add")
async def add_ip(ip: str = Form(...), description: str = Form(...), user=Depends(get_current_user)):
    global config
    if not iptables.validate_ip(ip):
        raise HTTPException(status_code=400, detail="Invalid IP address format")
    
    if "allowed_ips" not in config:
        config["allowed_ips"] = []
    
    for item in config["allowed_ips"]:
        if item["ip"] == ip:
            raise HTTPException(status_code=400, detail="IP already exists")
    
    config["allowed_ips"].append({"ip": ip, "description": description})
    save_config()
    return {"status": "success"}

@app.post("/api/ips/remove")
async def remove_ip(ip: str = Form(...), user=Depends(get_current_user)):
    global config
    config["allowed_ips"] = [item for item in config["allowed_ips"] if item["ip"] != ip]
    save_config()
    return {"status": "success"}

@app.post("/api/apply")
async def apply_rules(user=Depends(get_current_user)):
    try:
        allowed_ips = [item["ip"] for item in config.get("allowed_ips", [])]
        success = iptables.apply_allowed_ips(allowed_ips)
        if success:
            return {"status": "success"}
        raise HTTPException(status_code=500, detail="Failed to apply rules")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/status")
async def get_status(user=Depends(get_current_user)):
    return {
        "allowed_ips": config.get("allowed_ips", []),
        "rules_applied": iptables.check_rules_applied()
    }

@app.post("/api/change_password")
async def change_password(old_password: str = Form(...), new_password: str = Form(...), user=Depends(get_current_user)):
    global config
    if not auth_manager.verify_password(old_password):
        raise HTTPException(status_code=400, detail="Invalid current password")
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    
    config["admin_password"] = hash_password(new_password)
    save_config()
    auth_manager.admin_password = config["admin_password"]
    return {"status": "success"}

def check_prerequisites():
    result = subprocess.run(["which", "iptables"], capture_output=True)
    if result.returncode != 0:
        print("Error: iptables not found. Install with: apt-get install iptables")
        sys.exit(1)
    
    if os.geteuid() != 0:
        print("Error: Root privileges required. Run with sudo")
        sys.exit(1)

def create_systemd_service():
    service_content = f"""[Unit]
Description=IP Access Manager
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory={os.getcwd()}
ExecStart={os.getcwd()}/venv/bin/python3 {os.getcwd()}/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
    with open(SERVICE_PATH, 'w') as f:
        f.write(service_content)
    
    subprocess.run(["systemctl", "daemon-reload"])
    subprocess.run(["systemctl", "enable", SERVICE_NAME])
    subprocess.run(["systemctl", "start", SERVICE_NAME])
    print(f"Service {SERVICE_NAME} created and started")

def remove_system():
    print("Removing IP Access Manager...")
    
    if iptables:
        iptables.cleanup()
    
    subprocess.run(["systemctl", "stop", SERVICE_NAME], stderr=subprocess.DEVNULL)
    subprocess.run(["systemctl", "disable", SERVICE_NAME], stderr=subprocess.DEVNULL)
    
    if os.path.exists(SERVICE_PATH):
        os.remove(SERVICE_PATH)
    
    subprocess.run(["systemctl", "daemon-reload"])
    
    config_files = [CONFIG_FILE, "iptables_rules.backup"]
    for file in config_files:
        if os.path.exists(file):
            os.remove(file)
    
    print("IP Access Manager removed successfully")

def first_time_setup():
    print("\n=== FIRST TIME SETUP ===")
    while True:
        password = getpass.getpass("Create admin password: ")
        confirm = getpass.getpass("Confirm password: ")
        if password == confirm and len(password) >= 6:
            config["admin_password"] = hash_password(password)
            config["allowed_ips"] = []
            save_config()
            print("Password saved successfully!")
            break
        print("Passwords don't match or too short (min 6 characters)")

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--remove":
        check_prerequisites()
        remove_system()
        return
    
    check_prerequisites()
    
    if not os.path.exists(CONFIG_FILE) or not load_config().get("admin_password"):
        first_time_setup()
    
    if not os.path.exists(SERVICE_PATH):
        print("Creating systemd service...")
        create_systemd_service()
        print("Service created. Use: systemctl status ip-access-manager")
        return
    
    try:
        host_ip = subprocess.check_output(["hostname", "-I"]).decode().strip().split()[0]
    except:
        host_ip = "localhost"
    
    print(f"\nIP ACCESS MANAGER STARTED")
    print(f"Web interface: http://{host_ip}:{DEFAULT_PORT}")
    print(f"Login: admin, password: your password")
    print(f"Press Ctrl+C to stop\n")
    
    uvicorn.run(app, host="0.0.0.0", port=DEFAULT_PORT)

if __name__ == "__main__":
    main()