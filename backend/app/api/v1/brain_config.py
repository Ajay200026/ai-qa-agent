"""Brain agent mode configuration API."""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.brain_llm_router import check_brain_llm_health, invalidate_agent_mode_cache, set_agent_mode_cache
from app.core.deps import CurrentUser, DbSession
from app.services.brain_settings_service import get_brain_settings, update_agent_mode

router = APIRouter()


class BrainConfigResponse(BaseModel):
    agent_mode: str
    routing_mode: str = "hybrid"
    models: dict[str, str]
    scan_available: bool = False
    chat_available: bool = False
    analysis_available: bool = False
    automation_available: bool = False
    brain_available: bool
    rca_available: bool
    vision_available: bool
    degraded: bool


class BrainConfigUpdate(BaseModel):
    agent_mode: str = Field(..., pattern="^(single|multi)$")


@router.get("/config/brain", response_model=BrainConfigResponse)
async def get_brain_config(current_user: CurrentUser, db: DbSession):
    row = await get_brain_settings(db)
    health = await check_brain_llm_health()
    health["agent_mode"] = row.agent_mode
    return BrainConfigResponse(**health)


@router.patch("/config/brain", response_model=BrainConfigResponse)
async def patch_brain_config(
    body: BrainConfigUpdate, current_user: CurrentUser, db: DbSession
):
    await update_agent_mode(db, body.agent_mode)
    invalidate_agent_mode_cache()
    set_agent_mode_cache(body.agent_mode)
    health = await check_brain_llm_health()
    health["agent_mode"] = body.agent_mode
    return BrainConfigResponse(**health)
