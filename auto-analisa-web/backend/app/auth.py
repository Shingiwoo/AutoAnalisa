from datetime import datetime, timedelta
import os
from jose import jwt
from passlib.hash import argon2


JWT_SECRET = os.getenv("JWT_SECRET", "change-me")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "43200"))  # 30 days


def hash_pw(p: str) -> str:
    return argon2.hash(p)


def verify_pw(p: str, h: str) -> bool:
    # Backward compatibility: if existing hash is bcrypt ($2... prefix), verify with bcrypt
    if h.startswith("$2"):
        try:
            from passlib.hash import bcrypt
            return bcrypt.verify(p, h)
        except Exception:
            return False
    return argon2.verify(p, h)


def make_jwt(user_id: str, role: str) -> str:
    exp = datetime.utcnow() + timedelta(minutes=JWT_EXPIRE_MINUTES)
    return jwt.encode({"sub": user_id, "role": role, "exp": exp}, JWT_SECRET, algorithm="HS256")
