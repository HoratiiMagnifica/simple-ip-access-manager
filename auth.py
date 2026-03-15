#!/usr/bin/env python3
from fastapi import Request, HTTPException
from datetime import datetime, timedelta
import bcrypt
import secrets

class AuthManager:
    def __init__(self, admin_password):
        self.admin_password = admin_password
        self.sessions = {}
    
    def verify_password(self, password):
        try:
            if not self.admin_password or not password:
                return False
            stored = self.admin_password
            if isinstance(stored, str):
                stored = stored.encode('utf-8')
            return bcrypt.checkpw(
                password.encode('utf-8'),
                stored
            )
        except Exception:
            return False
    
    def create_session(self, token):
        self.sessions[token] = datetime.now() + timedelta(hours=24)
    
    def validate_session(self, token):
        if token in self.sessions:
            if self.sessions[token] > datetime.now():
                return True
            del self.sessions[token]
        return False

def hash_password(password):
    try:
        password_bytes = password.encode('utf-8')
        if len(password_bytes) > 72:
            password_bytes = password_bytes[:72]
        salt = bcrypt.gensalt(rounds=12)
        hashed = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode('utf-8')
    except Exception as e:
        print(f"Hash error: {e}")
        return None

async def get_current_user(request: Request):
    token = request.cookies.get("session")
    auth_manager = request.app.state.auth_manager if hasattr(request.app, 'state') else None
    
    if not token or not auth_manager or not auth_manager.validate_session(token):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    return {"username": "admin"}