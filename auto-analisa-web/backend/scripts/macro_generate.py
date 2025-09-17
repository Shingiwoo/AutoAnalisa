#!/usr/bin/env python3
import asyncio
import argparse
import fcntl, os, sys, json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.config import settings
from app.models import Base, MacroDaily
from app.services.llm import ask_llm
from sqlalchemy import select


def _wib_slot() -> str:
    try:
        jkt = ZoneInfo("Asia/Jakarta")
        now_wib = datetime.now(timezone.utc).astimezone(jkt)
        return "pagi" if now_wib.hour < 12 else "malam"
    except Exception:
        return "pagi"


async def main():
    ap = argparse.ArgumentParser(description="Generate MacroDaily for a slot (pagi/malam)")
    ap.add_argument("--slot", choices=["pagi","malam"], default=None)
    args = ap.parse_args()
    slot = (args.slot or _wib_slot()).lower()

    # File lock per slot to prevent concurrent runs
    lock_path = f"/tmp/autoanalisa_macro_{slot}.lock"
    with open(lock_path, "w") as lf:
        try:
            fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("Another macro_generate is running for this slot.")
            sys.exit(0)

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

            # Parse JSON if possible
            narrative = text
            sources: str | list | None = ""
            sections: list | dict | str | None = []
            try:
                parsed = json.loads(text)
                narrative = parsed.get("summary") or parsed.get("narrative") or narrative
                sections = parsed.get("sections") or []
                sources = parsed.get("sources") or ""
                if isinstance(sections, str):
                    try:
                        sections = json.loads(sections)
                    except Exception:
                        sections = []
                if isinstance(sections, dict):
                    sections = [sections]
            except Exception:
                pass

            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            q = await db.execute(select(MacroDaily).where(MacroDaily.date_utc == today, MacroDaily.slot == slot))
            row = q.scalar_one_or_none()
            def _src_to_text(src):
                if isinstance(src, list):
                    try:
                        return "\n".join(map(str, src))
                    except Exception:
                        return "\n".join([str(x) for x in src])
                return str(src or "")

            if row:
                row.narrative = narrative
                row.sources = _src_to_text(sources)
                try:
                    row.sections = sections if isinstance(sections, list) else []
                    row.last_run_status = "ok"
                except Exception:
                    pass
            else:
                row = MacroDaily(date_utc=today, slot=slot, narrative=narrative, sources=_src_to_text(sources))
                try:
                    row.sections = sections if isinstance(sections, list) else []
                    row.last_run_status = "ok"
                except Exception:
                    pass
                db.add(row)
            await db.commit()
            print(f"OK MacroDaily generated for {today} slot={slot} (sections={len(sections)})")


if __name__ == "__main__":
    asyncio.run(main())
