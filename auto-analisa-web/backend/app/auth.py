from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import jwt, JWTError
from passlib.hash import argon2
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.deps import get_db
from app.models import User


def hash_pw(p: str) -> str:
    return argon2.hash(p)


def verify_pw(p: str, h: str) -> bool:
    # Backward compatibility: if existing hash is bcrypt ($2... prefix), verify with bcrypt
    if isinstance(h, str) and h.startswith("$2"):
        try:
            from passlib.hash import bcrypt

            return bcrypt.verify(p, h)
        except Exception:
            return False
    return argon2.verify(p, h)


def make_jwt(user_id: str, role: str) -> str:
    minutes = settings.JWT_EXPIRE_MIN or settings.JWT_EXPIRE_MINUTES or 43200
    exp = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    return jwt.encode({"sub": user_id, "role": role, "exp": exp}, settings.JWT_SECRET, algorithm="HS256")


def get_token_from_request(req: Request) -> Optional[str]:
    # Authorization: Bearer <token>
    h = req.headers.get("Authorization")
    if h and h.lower().startswith("bearer "):
        return h.split(" ", 1)[1].strip()
    # Cookie: access_token
    return req.cookies.get("access_token")


async def get_current_user(req: Request, db: AsyncSession = Depends(get_db)) -> User:
    token = get_token_from_request(req)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    u = await db.get(User, user_id)
    if not u:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return u


class _PublicUser:
    def __init__(self):
        self.id = "public"
        self.email = "public@example.com"
        self.role = "user"


async def require_user(req: Request, db: AsyncSession = Depends(get_db)) -> User:
    """Return authenticated user, or a public stub if REQUIRE_LOGIN is False.
    Admin endpoints should still use strict checks (e.g., require_admin).
    """
    if not settings.REQUIRE_LOGIN:
        try:
            token = get_token_from_request(req)
            if token:
                return await get_current_user(req, db)
        except HTTPException:
            pass
        return _PublicUser()  # type: ignore[return-value]
    return await get_current_user(req, db)
