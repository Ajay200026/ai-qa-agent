from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.core.deps import CurrentUser
from app.knowledge.neo4j_client import neo4j_client

router = APIRouter()


@router.get("/scenarios/{scenario_id}/graph")
async def get_scenario_graph(scenario_id: UUID, current_user: CurrentUser):
    try:
        graph = await neo4j_client.get_scenario_graph(str(scenario_id))
        return graph
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
