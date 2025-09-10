from datetime import datetime, timedelta
import os
from jose import jwt
from passlib.hash import bcrypt


JWT_SECRET = os.getenv("JWT_SECRET", "change-me")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "43200"))  # 30 days


def hash_pw(p: str) -> str:
    return bcrypt.hash(p)


def verify_pw(p: str, h: str) -> bool:
    return bcrypt.verify(p, h)


def make_jwt(user_id: str, role: str) -> str:
    exp = datetime.utcnow() + timedelta(minutes=JWT_EXPIRE_MINUTES)
    return jwt.encode({"sub": user_id, "role": role, "exp": exp}, JWT_SECRET, algorithm="HS256")

