import os
from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


def create_access_token(subject: str) -> str:
    secret = os.getenv("JWT_SECRET")
    alg = os.getenv("JWT_ALG", "HS256")
    exp_minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

    if not secret:
        raise RuntimeError("JWT_SECRET is not set in .env")

    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=exp_minutes)).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=alg)


def decode_token(token: str) -> dict:
    secret = os.getenv("JWT_SECRET")
    alg = os.getenv("JWT_ALG", "HS256")
    if not secret:
        raise RuntimeError("JWT_SECRET is not set in .env")
    return jwt.decode(token, secret, algorithms=[alg])
