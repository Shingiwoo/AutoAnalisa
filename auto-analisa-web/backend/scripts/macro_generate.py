#!/usr/bin/env python3
import asyncio
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.config import settings
from app.models import Base, MacroDaily
from app.services.llm import ask_llm
from sqlalchemy import select


async def main():
    engine = create_async_engine(settings.SQLITE_URL, echo=False, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as db:
        prompt = (
            "Ringkas faktor makro relevan untuk pasar kripto 24-48 jam ke depan. "
            "Bahasa Indonesia, 5-8 poin, netral, tidak mengandung saran investasi."
        )
        text, _ = ask_llm(prompt)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        q = await db.execute(select(MacroDaily).where(MacroDaily.date_utc == today))
        row = q.scalar_one_or_none()
        if row:
            row.narrative = text
        else:
            row = MacroDaily(date_utc=today, narrative=text, sources="")
            db.add(row)
        await db.commit()
        print(f"OK MacroDaily generated for {today}")


if __name__ == "__main__":
    asyncio.run(main())

