"""Brain settings row + agent mode persistence."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.brain_llm_router import invalidate_agent_mode_cache, set_agent_mode_cache
from app.core.config import get_settings
from app.models.brain_settings import BrainSettings


async def get_brain_settings(db: AsyncSession) -> BrainSettings:
    result = await db.execute(select(BrainSettings).limit(1))
    row = result.scalar_one_or_none()
    if row is None:
        settings = get_settings()
        row = BrainSettings(agent_mode=settings.brain_agent_mode)
        db.add(row)
        await db.commit()
        await db.refresh(row)
    set_agent_mode_cache(row.agent_mode)
    return row


async def update_agent_mode(db: AsyncSession, mode: str) -> BrainSettings:
    row = await get_brain_settings(db)
    row.agent_mode = mode
    await db.commit()
    await db.refresh(row)
    invalidate_agent_mode_cache()
    set_agent_mode_cache(mode)
    return row
