#!/usr/bin/env python3
from fastapi import Request, HTTPException
from passlib.context import CryptContext
from datetime import datetime, timedelta

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthManager:
    def __init__(self, admin_password):
        self.admin_password = admin_password
        self.sessions = {}
    
    def verify_password(self, password):
        return pwd_context.verify(password, self.admin_password)
    
    def create_session(self, token):
        self.sessions[token] = datetime.now() + timedelta(hours=24)
    
    def validate_session(self, token):
        if token in self.sessions:
            if self.sessions[token] > datetime.now():
                return True
            else:
                del self.sessions[token]
        return False

def hash_password(password):
    return pwd_context.hash(password)

async def get_current_user(request: Request):
    token = request.cookies.get("session")
    auth_manager = request.app.state.auth_manager if hasattr(request.app, 'state') else None
    
    if not token or not auth_manager or not auth_manager.validate_session(token):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    return {"username": "admin"}