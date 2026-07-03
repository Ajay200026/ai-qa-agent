"""Knowledge Engine API — repository scanning, graph, and Ask AI."""

import asyncio
import json
import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse

from app.core.database import AsyncSessionLocal
from app.core.deps import CurrentUser, DbSession
from app.knowledge_engine.ask_service import AskService
from app.knowledge_engine.events import scan_event_manager
from app.knowledge_engine.graph_writer import find_navigation_path, get_module_graph
from app.knowledge_engine.scan_service import ScanService
from app.repositories.knowledge_repository import KnowledgeEntityRepository, KnowledgeModuleRepository
from app.schemas.knowledge_engine import (
    AskRequest,
    AskResponse,
    DiscoveredModule,
    EntityDetailResponse,
    GraphEdge,
    GraphNode,
    GraphResponse,
    KnowledgeModuleCreate,
    KnowledgeModuleResponse,
    KnowledgeRepoCreate,
    KnowledgeRepoResponse,
    ModuleStatusResponse,
)
from app.services.knowledge_repo_service import KnowledgeRepoService

logger = logging.getLogger(__name__)

router = APIRouter()


async def _run_scan(module_id: UUID) -> None:
    async with AsyncSessionLocal() as db:
        try:
            service = ScanService(db)
            await service.scan_module(module_id)
        except Exception:
            logger.exception("Background scan failed for module %s", module_id)


# --- Repositories ---


@router.post("/repos", response_model=KnowledgeRepoResponse)
async def create_repo(body: KnowledgeRepoCreate, current_user: CurrentUser, db: DbSession):
    service = KnowledgeRepoService(db)
    try:
        repo = await service.create_repo(current_user.id, body.name, body.path)
        return repo
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/repos", response_model=list[KnowledgeRepoResponse])
async def list_repos(current_user: CurrentUser, db: DbSession):
    service = KnowledgeRepoService(db)
    return await service.list_repos(current_user.id)


@router.get("/repos/{repo_id}/discover", response_model=list[DiscoveredModule])
async def discover_repo_modules(repo_id: UUID, current_user: CurrentUser, db: DbSession):
    service = KnowledgeRepoService(db)
    try:
        return await service.discover_modules(repo_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/repos/{repo_id}/modules", response_model=KnowledgeModuleResponse)
async def create_module(
    repo_id: UUID, body: KnowledgeModuleCreate, current_user: CurrentUser, db: DbSession
):
    service = KnowledgeRepoService(db)
    try:
        return await service.create_module(repo_id, body.name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/repos/{repo_id}/modules", response_model=list[KnowledgeModuleResponse])
async def list_modules(repo_id: UUID, current_user: CurrentUser, db: DbSession):
    service = KnowledgeRepoService(db)
    return await service.list_modules(repo_id)


# --- Scanning ---


@router.post("/modules/{module_id}/scan")
async def start_scan(
    module_id: UUID,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser,
    db: DbSession,
):
    module_repo = KnowledgeModuleRepository(db)
    module = await module_repo.get_by_id(module_id)
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
    background_tasks.add_task(_run_scan, module_id)
    return {"status": "scanning", "module_id": str(module_id)}


@router.get("/modules/{module_id}/status", response_model=ModuleStatusResponse)
async def get_module_status(module_id: UUID, current_user: CurrentUser, db: DbSession):
    service = KnowledgeRepoService(db)
    try:
        return await service.get_module_status(module_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/modules/{module_id}/scan/stream")
async def scan_stream(module_id: UUID, current_user: CurrentUser):
    async def event_generator():
        queue = await scan_event_manager.subscribe(module_id)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(event)}\n\n"
                    if event.get("event_type") in {"scan_completed", "scan_failed"}:
                        break
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'event_type': 'heartbeat'})}\n\n"
        finally:
            await scan_event_manager.unsubscribe(module_id, queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# --- Graph ---


@router.get("/modules/{module_id}/graph", response_model=GraphResponse)
async def get_graph(module_id: UUID, current_user: CurrentUser, db: DbSession):
    module_repo = KnowledgeModuleRepository(db)
    module = await module_repo.get_by_id(module_id)
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
    raw = await get_module_graph(module_id)
    nodes = [GraphNode(**n) for n in raw.get("nodes", [])]
    edges = [GraphEdge(**e) for e in raw.get("edges", [])]
    return GraphResponse(nodes=nodes, edges=edges)


# --- Entities ---


@router.get("/entities/{entity_id}", response_model=EntityDetailResponse)
async def get_entity(entity_id: UUID, current_user: CurrentUser, db: DbSession):
    entity_repo = KnowledgeEntityRepository(db)
    entity = await entity_repo.get_by_id(entity_id)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    from app.knowledge_engine.graph_writer import find_entity_neighbors

    neighbors_raw = await find_entity_neighbors(entity.module_id, entity.name)
    dependencies = []
    for record in neighbors_raw:
        for n in record.get("neighbors") or []:
            if n and n.get("target"):
                dependencies.append(
                    GraphNode(
                        id=n.get("target", ""),
                        label=n.get("target", ""),
                        type=n.get("target_type", "Reference"),
                        name=n.get("target", ""),
                    )
                )

    nav = await find_navigation_path(entity.module_id, entity.name)
    related_files = [entity.file_path] if entity.file_path else []

    return EntityDetailResponse(
        id=entity.id,
        entity_type=entity.entity_type,
        name=entity.name,
        file_path=entity.file_path,
        summary=entity.summary,
        extracted=entity.extracted,
        business_rules=entity.business_rules,
        dependencies=dependencies,
        related_files=related_files,
        navigation_path=nav,
    )


# --- Ask AI ---


@router.post("/ask", response_model=AskResponse)
async def ask_question(body: AskRequest, current_user: CurrentUser, db: DbSession):
    service = AskService(db)
    try:
        result = await service.ask(body.module_id, body.question)
        return AskResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/ask/stream")
async def ask_stream(body: AskRequest, current_user: CurrentUser, db: DbSession):
    service = AskService(db)

    async def event_generator():
        try:
            async for chunk in service.ask_stream(body.module_id, body.question):
                yield f"data: {chunk}\n\n"
        except ValueError as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
