import os
import secrets
import time
from functools import wraps
from fastapi import HTTPException, Request

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

_tokens = {}
TOKEN_EXPIRY = 86400

def generate_token() -> str:
    token = secrets.token_urlsafe(32)
    _tokens[token] = time.time() + TOKEN_EXPIRY
    return token

def verify_token(token: str) -> bool:
    if token not in _tokens:
        return False
    if time.time() > _tokens[token]:
        del _tokens[token]
        return False
    return True

def check_password(password: str) -> bool:
    return password == ADMIN_PASSWORD

async def require_auth(request: Request):
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = auth_header[7:]
    if not verify_token(token):
        raise HTTPException(status_code=401, detail="Token expired or invalid")
    return token

def cleanup_expired():
    now = time.time()
    expired = [t for t, exp in _tokens.items() if now > exp]
    for t in expired:
        del _tokens[t]
