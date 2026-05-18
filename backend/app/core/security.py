from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException, status

SECRET_KEY = "dashboard-lmd-sistemas-super-secret-key-2026-v1"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 8


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado"
        )