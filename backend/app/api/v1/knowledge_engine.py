"""Knowledge Engine API — repository scanning, graph, and Ask AI."""

import asyncio
import json
import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse

from app.core.database import AsyncSessionLocal
from app.core.deps import CurrentUser, DbSession
from app.knowledge_engine.brain_ask_service import BrainAskService
from app.knowledge_engine.brain_graph_writer import (
    get_brain_node_detail,
    get_brain_path,
    get_repo_brain_graph,
)
from app.knowledge_engine.events import scan_event_manager
from app.knowledge_engine.graph_writer import find_navigation_path, get_module_graph
from app.knowledge_engine.scan_service import ScanService
from app.models.knowledge import RepoSourceType, ScanStatus
from app.repositories.knowledge_repository import KnowledgeEntityRepository, KnowledgeModuleRepository
from app.schemas.knowledge_engine import (
    AskRequest,
    AskResponse,
    DiscoveredModule,
    EntityDetailResponse,
    FolderUploadBatchResponse,
    FolderUploadResponse,
    GraphEdge,
    GraphNode,
    GraphResponse,
    KnowledgeModuleCreate,
    KnowledgeModuleResponse,
    KnowledgeRepoCreate,
    KnowledgeRepoResponse,
    ModuleStatusResponse,
    RepoFolderEntry,
    RepoFileEntry,
    FileContentResponse,
    ValidateScopeResponse,
)
from app.services.azure_repo_sync_service import AzureRepoSyncService
from app.services.knowledge_cleanup_service import KnowledgeCleanupService, cleanup_module_artifacts, cleanup_repo_artifacts
from app.services.knowledge_repo_service import KnowledgeRepoService
from app.services.local_upload_service import LocalUploadService
from app.services.upload_session import get_session

logger = logging.getLogger(__name__)

router = APIRouter()


async def _run_scan(module_id: UUID) -> None:
    async with AsyncSessionLocal() as db:
        module_repo = KnowledgeModuleRepository(db)
        try:
            await scan_event_manager.publish(
                module_id,
                {"event_type": "scan_preparing", "message": "Preparing scan…"},
            )
            module = await module_repo.get_with_entities(module_id)
            if not module:
                raise ValueError("Module not found")

            if module.repo and module.repo.source_type == RepoSourceType.AZURE.value:
                await scan_event_manager.publish(
                    module_id,
                    {
                        "event_type": "repo_syncing",
                        "message": "Syncing Azure DevOps repository (this may take a minute)…",
                    },
                )
                sync = AzureRepoSyncService(db)
                await sync.sync_repo(module.repo)

            service = ScanService(db)
            await service.scan_module(module_id)
        except Exception as exc:
            logger.exception("Background scan failed for module %s", module_id)
            try:
                module = await module_repo.get_by_id(module_id)
                if module and module.scan_status != ScanStatus.COMPLETED.value:
                    await module_repo.update_status(
                        module, status=ScanStatus.FAILED, error=str(exc)
                    )
                    await db.commit()
                await scan_event_manager.publish(
                    module_id, {"event_type": "scan_failed", "message": str(exc)}
                )
            except Exception:
                logger.exception("Failed to record scan failure for module %s", module_id)


async def _run_reindex_vectors(module_id: UUID) -> None:
    async with AsyncSessionLocal() as db:
        module_repo = KnowledgeModuleRepository(db)
        try:
            service = ScanService(db)
            await service.reindex_vectors(module_id)
        except Exception as exc:
            logger.exception("Background vector reindex failed for module %s", module_id)
            try:
                module = await module_repo.get_by_id(module_id)
                if module:
                    await module_repo.update_status(
                        module, status=ScanStatus.FAILED, error=str(exc)
                    )
                    await db.commit()
                await scan_event_manager.publish(
                    module_id, {"event_type": "scan_failed", "message": str(exc)}
                )
            except Exception:
                logger.exception("Failed to record vector reindex failure for module %s", module_id)


# --- Repositories ---


@router.post("/repos", response_model=KnowledgeRepoResponse)
async def create_repo(body: KnowledgeRepoCreate, current_user: CurrentUser, db: DbSession):
    service = KnowledgeRepoService(db)
    try:
        repo = await service.create_repo(current_user.id, body)
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
        return await service.discover_modules(repo_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/repos/{repo_id}/validate-scope", response_model=ValidateScopeResponse)
async def validate_repo_scope(
    repo_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
    path: str = Query(..., description="Folder scope path to validate"),
):
    service = KnowledgeRepoService(db)
    try:
        return await service.validate_scope(repo_id, current_user.id, path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/repos/{repo_id}", status_code=204)
async def delete_repo(
    repo_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
    background_tasks: BackgroundTasks,
):
    service = KnowledgeCleanupService(db)
    try:
        module_ids, workspace = await service.delete_repo(repo_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    background_tasks.add_task(cleanup_repo_artifacts, repo_id, module_ids, workspace)


@router.post("/repos/upload", response_model=KnowledgeRepoResponse)
async def upload_repo_zip(
    current_user: CurrentUser,
    db: DbSession,
    name: str = Form(...),
    file: UploadFile = File(...),
):
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Upload must be a .zip file")
    service = LocalUploadService(db)
    try:
        return await service.create_from_zip(current_user.id, name, file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/repos/upload-folder",
    response_model=FolderUploadResponse | FolderUploadBatchResponse,
)
async def upload_repo_folder(
    request: Request,
    current_user: CurrentUser,
    db: DbSession,
):
    form = await request.form()
    session_id = form.get("session_id")
    finalize = str(form.get("finalize", "")).lower() == "true"
    name = form.get("name")

    relative_paths_raw = form.get("relative_paths", "[]")
    try:
        path_list = json.loads(str(relative_paths_raw)) if relative_paths_raw else []
        if not isinstance(path_list, list):
            raise ValueError("relative_paths must be a JSON array")
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid relative_paths payload") from exc

    uploads = form.getlist("files")
    service = LocalUploadService(db)

    if session_id:
        session = get_session(str(session_id))
        if not session or session.owner_id != current_user.id:
            raise HTTPException(status_code=404, detail="Upload session not found")
    else:
        if not name or not str(name).strip():
            raise HTTPException(status_code=400, detail="Display name is required")
        if not uploads:
            raise HTTPException(
                status_code=400,
                detail="No files received. Select a folder that contains Salesforce code (LWC, Apex, metadata).",
            )
        session = await service.start_folder_session(current_user.id, str(name).strip())

    file_pairs: list[tuple[str, UploadFile]] = []
    for index, upload in enumerate(uploads):
        if not hasattr(upload, "read"):
            continue
        if index < len(path_list) and path_list[index]:
            rel = str(path_list[index]).replace("\\", "/")
        else:
            rel = (getattr(upload, "filename", None) or "").replace("\\", "/")
        if not rel:
            continue
        file_pairs.append((rel, upload))

    if file_pairs:
        try:
            await service.write_batch_files(session, file_pairs)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not finalize:
        return FolderUploadBatchResponse(
            session_id=session.session_id,
            repo_id=session.repo_id,
            files_received=session.files_written,
            bytes_received=session.bytes_written,
        )

    try:
        result = await service.finalize_folder_session(session.session_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    repo = result["repo"]
    return FolderUploadResponse(
        success=result["success"],
        projectName=result["projectName"],
        totalFiles=result["totalFiles"],
        uploadedFiles=result["uploadedFiles"],
        id=repo.id,
        name=repo.name,
        path=repo.path,
        source_type=repo.source_type,
        azure_connection_id=repo.azure_connection_id,
        azure_project=repo.azure_project,
        azure_repo=repo.azure_repo,
        azure_repo_id=repo.azure_repo_id,
        branch=repo.branch,
        last_synced_commit=repo.last_synced_commit,
        owner_id=repo.owner_id,
        created_at=repo.created_at,
    )


@router.post("/reset")
async def reset_knowledge(current_user: CurrentUser, db: DbSession):
    service = KnowledgeCleanupService(db)
    return await service.reset_all(current_user.id)


@router.get("/repos/{repo_id}/tree", response_model=list[RepoFolderEntry])
async def list_repo_tree(
    repo_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
    path: str = Query("", description="Relative folder path from repo root"),
):
    service = KnowledgeRepoService(db)
    try:
        return await service.list_repo_tree(repo_id, path)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/repos/{repo_id}/files", response_model=list[RepoFileEntry])
async def list_repo_files(
    repo_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
    path: str = Query("", description="Relative folder path"),
    scope_path: str | None = Query(None, description="Limit listing to module scope"),
):
    service = KnowledgeRepoService(db)
    try:
        return await service.list_repo_files(repo_id, current_user.id, path, scope_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/repos/{repo_id}/file-content", response_model=FileContentResponse)
async def read_repo_file(
    repo_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
    path: str = Query(..., description="Relative file path from repo root"),
):
    service = KnowledgeRepoService(db)
    try:
        return await service.read_repo_file(repo_id, current_user.id, path)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/repos/{repo_id}/modules", response_model=KnowledgeModuleResponse)
async def create_module(
    repo_id: UUID, body: KnowledgeModuleCreate, current_user: CurrentUser, db: DbSession
):
    service = KnowledgeRepoService(db)
    try:
        return await service.create_module(
            repo_id, body.name, body.scope_path, owner_id=current_user.id
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/modules/{module_id}", status_code=204)
async def delete_module(
    module_id: UUID,
    current_user: CurrentUser,
    db: DbSession,
    background_tasks: BackgroundTasks,
):
    service = KnowledgeCleanupService(db)
    try:
        await service.delete_module(module_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    background_tasks.add_task(cleanup_module_artifacts, module_id)


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


@router.post("/modules/{module_id}/reindex-vectors")
async def reindex_vectors(
    module_id: UUID,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser,
    db: DbSession,
):
    module_repo = KnowledgeModuleRepository(db)
    module = await module_repo.get_by_id(module_id)
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
    background_tasks.add_task(_run_reindex_vectors, module_id)
    return {"status": "indexing", "module_id": str(module_id)}


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


@router.get("/repos/{repo_id}/brain", response_model=GraphResponse)
async def get_repo_brain(repo_id: UUID, current_user: CurrentUser, db: DbSession):
    service = KnowledgeRepoService(db)
    repo = await service.get_repo(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    raw = await get_repo_brain_graph(repo_id)
    nodes = [GraphNode(**n) for n in raw.get("nodes", [])]
    edges = [GraphEdge(**e) for e in raw.get("edges", [])]
    return GraphResponse(nodes=nodes, edges=edges)


@router.get("/nodes/{node_id}")
async def get_brain_node(node_id: str, current_user: CurrentUser):
    detail = await get_brain_node_detail(node_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Node not found")
    return detail


@router.get("/nodes/{node_id}/path")
async def get_node_path(
    node_id: str, target_id: str, current_user: CurrentUser
):
    path = await get_brain_path(node_id, target_id)
    return {"path": path}


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
    service = BrainAskService(db)
    try:
        result = await service.ask(body.module_id, body.question)
        return AskResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/ask/stream")
async def ask_stream(body: AskRequest, current_user: CurrentUser, db: DbSession):
    service = BrainAskService(db)

    async def event_generator():
        try:
            async for chunk in service.ask_stream(body.module_id, body.question):
                yield f"data: {chunk}\n\n"
        except ValueError as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
