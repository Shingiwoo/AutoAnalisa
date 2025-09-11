from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.deps import get_db
from app.routers.auth import get_user_from_auth, hash_pw
from app.models import PasswordChangeRequest

router = APIRouter(prefix="/api/user", tags=["user"])


@router.post("/password_request")
async def password_request(new_password: str, db: AsyncSession = Depends(get_db), user=Depends(get_user_from_auth)):
    nh = hash_pw(new_password)
    db.add(PasswordChangeRequest(user_id=user.id, new_hash=nh))
    await db.commit()
    return {"ok": True}

