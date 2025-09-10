from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from .. import models
from ..config import settings


engine = create_async_engine(settings.SQLITE_URL, echo=False, future=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)

