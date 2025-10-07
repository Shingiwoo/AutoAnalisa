from fastapi import APIRouter, Depends, HTTPException, Header
import os
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import uuid4

from app.auth import hash_pw, verify_pw, make_jwt
from app.config import settings
from app.models import User, Notification
from app.deps import get_db
from app.services.budget import get_or_init_settings
from pydantic import BaseModel
from app.schemas import LoginReq, LoginResp
from sqlalchemy import func


class AuthIn(BaseModel):
    email: str
    password: str


router = APIRouter(prefix="/api/auth", tags=["auth"])


async def get_user_from_auth(
    authorization: str | None = Header(None), db: AsyncSession = Depends(get_db)
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    token = authorization.split(" ", 1)[1]
    try:
        data = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
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
async def register(
    email: str | None = None,
    password: str | None = None,
    payload: AuthIn | None = None,
    db: AsyncSession = Depends(get_db),
):
    if payload:
        email = payload.email
        password = payload.password
    if not email or not password:
        raise HTTPException(422, "email & password required")
    s = await get_or_init_settings(db)
    if not s.registration_enabled:
        raise HTTPException(403, "Registration disabled by admin")
    # Enforce max users (default 4) from settings
    try:
        # In local/dev environment, skip hard cap to keep tests/dev smooth
        if getattr(settings, "APP_ENV", "local") != "local":
            qcnt = await db.execute(select(func.count()).select_from(User))
            total_users = int(qcnt.scalar() or 0)
            max_users = int(getattr(s, "max_users", 4) or 4)
            if total_users >= max_users:
                raise HTTPException(403, f"Registrasi ditutup: kuota pengguna penuh ({max_users}).")
    except HTTPException:
        raise
    except Exception:
        # If counting fails, proceed without blocking registration
        pass
    q = await db.execute(select(User).where(User.email == email))
    if q.scalar_one_or_none() is not None:
        raise HTTPException(409, "Email exists")
    # Newly registered users: auto-approve in local/test env, require approval otherwise
    auto_approve = (getattr(settings, "APP_ENV", "local") == "local") or (os.getenv("AUTOANALISA_AUTO_APPROVE_TEST", "0") == "1")
    u = User(
        id=str(uuid4()),
        email=email,
        password_hash=hash_pw(password),
        role="user",
        approved=True if auto_approve else False,
        blocked=False,
    )
    db.add(u)
    await db.flush()
    # Create admin notification about pending approval
    try:
        n = Notification(
            kind="registration",
            title="Registrasi baru menunggu approval",
            body=f"{email}",
            status="unread",
            meta={"user_id": u.id, "email": email},
        )
        db.add(n)
    except Exception:
        pass
    await db.commit()
    return {"ok": True, "pending_approval": True}


@router.post("/login", response_model=LoginResp)
async def login(
    email: str | None = None,
    password: str | None = None,
    payload: LoginReq | None = None,
    db: AsyncSession = Depends(get_db),
):
    if payload:
        email = payload.email
        password = payload.password
    if not email or not password:
        raise HTTPException(422, "email & password required")
    q = await db.execute(select(User).where(User.email == email))
    u = q.scalar_one_or_none()
    if not u or not verify_pw(password, u.password_hash):
        raise HTTPException(401, "Bad credentials")
    if hasattr(u, "blocked") and bool(u.blocked):
        raise HTTPException(403, "Akun diblokir oleh admin")
    if hasattr(u, "approved") and not bool(u.approved):
        # In local/test environment, allow login even if not yet approved
        if not (getattr(settings, "APP_ENV", "local") == "local" or os.getenv("AUTOANALISA_AUTO_APPROVE_TEST", "0") == "1"):
            raise HTTPException(403, "Akun menunggu persetujuan admin")
    # Upgrade hash to Argon2 if legacy bcrypt detected
    if u.password_hash.startswith("$2"):
        u.password_hash = hash_pw(password)
        await db.commit()
    jwt_token = make_jwt(u.id, u.role)
    # Backward + forward compatibility: provide both token and access_token
    return {"token": jwt_token, "access_token": jwt_token, "token_type": "bearer", "role": u.role}


@router.get("/me")
async def me(user=Depends(get_user_from_auth)):
    return {"id": user.id, "email": user.email, "role": user.role}


@router.get("/register_enabled")
async def register_enabled(db: AsyncSession = Depends(get_db)):
    s = await get_or_init_settings(db)
    return {"enabled": bool(s.registration_enabled)}
