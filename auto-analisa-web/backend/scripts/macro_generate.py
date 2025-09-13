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
            "Balas dalam JSON dengan kunci: {date_utc (opsional), summary, "
            "sections:[{title,bullets:[]}], sources}. Bahasa Indonesia, netral, ringkas. "
            "Cakup 24-48 jam: DXY, yield riil, likuiditas kripto, ETF/flow, berita utama."
        )
        text, _ = ask_llm(prompt)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        q = await db.execute(select(MacroDaily).where(MacroDaily.date_utc == today))
        row = q.scalar_one_or_none()
        # Parse JSON if possible
        narrative = text
        sources = ""
        sections = []
        try:
            import json as _json
            parsed = _json.loads(text)
            narrative = parsed.get("summary") or parsed.get("narrative") or narrative
            sections = parsed.get("sections") or []
            sources = parsed.get("sources") or ""
            if isinstance(sections, dict):
                sections = [sections]
        except Exception:
            pass
        if row:
            row.narrative = narrative
            row.sources = sources
            try:
                row.sections = sections
            except Exception:
                pass
        else:
            row = MacroDaily(date_utc=today, narrative=narrative, sources=sources)
            try:
                row.sections = sections
            except Exception:
                pass
            db.add(row)
        await db.commit()
        print(f"OK MacroDaily generated for {today} (sections={len(sections)})")


if __name__ == "__main__":
    asyncio.run(main())
