from fastapi import APIRouter, Depends, HTTPException, Header
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import uuid4

from app.auth import hash_pw, verify_pw, make_jwt, JWT_SECRET
from app.models import User
from app.deps import get_db
from app.services.budget import get_or_init_settings


router = APIRouter(prefix="/api/auth", tags=["auth"])


async def get_user_from_auth(
    authorization: str | None = Header(None), db: AsyncSession = Depends(get_db)
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    token = authorization.split(" ", 1)[1]
    try:
        data = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except JWTError:
        raise HTTPException(401, "Invalid token")
    user_id = data.get("sub")
    if not user_id:
        raise HTTPException(401, "Invalid token")
    u = await db.get(User, user_id)
    if not u:
        raise HTTPException(401, "User not found")
    return u


@router.post("/register")
async def register(email: str, password: str, db: AsyncSession = Depends(get_db)):
    s = await get_or_init_settings(db)
    if not s.registration_enabled:
        raise HTTPException(403, "Registration disabled by admin")
    q = await db.execute(select(User).where(User.email == email))
    if q.scalar_one_or_none() is not None:
        raise HTTPException(409, "Email exists")
    u = User(id=str(uuid4()), email=email, password_hash=hash_pw(password), role="user")
    db.add(u)
    await db.commit()
    return {"ok": True}


@router.post("/login")
async def login(email: str, password: str, db: AsyncSession = Depends(get_db)):
    q = await db.execute(select(User).where(User.email == email))
    u = q.scalar_one_or_none()
    if not u or not verify_pw(password, u.password_hash):
        raise HTTPException(401, "Bad credentials")
    return {"token": make_jwt(u.id, u.role), "role": u.role}


@router.get("/me")
async def me(user=Depends(get_user_from_auth)):
    return {"id": user.id, "email": user.email, "role": user.role}


@router.get("/register_enabled")
async def register_enabled(db: AsyncSession = Depends(get_db)):
    s = await get_or_init_settings(db)
    return {"enabled": bool(s.registration_enabled)}
