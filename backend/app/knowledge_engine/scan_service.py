"""Orchestrate module scanning, extraction, graph building, and vector indexing."""

from __future__ import annotations

import logging
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge_engine.events import scan_event_manager
from app.knowledge_engine.extractors.router import collect_references, extract_file
from app.knowledge_engine.graph_writer import write_module_graph
from app.knowledge_engine.scanner.repo_scanner import (
    enumerate_all_files,
    filter_module_files,
    resolve_reference_files,
)
from app.knowledge_engine.summarizer import summarize_extraction
from app.knowledge_engine.types import ExtractionResult, ScannedFile
from app.knowledge_engine.vector_store import index_entities
from app.models.knowledge import KnowledgeEntity, KnowledgeModule, ScanStatus
from app.repositories.knowledge_repository import (
    KnowledgeEntityRepository,
    KnowledgeModuleRepository,
)

logger = logging.getLogger(__name__)

MAX_CLOSURE_ITERATIONS = 5


class ScanService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.module_repo = KnowledgeModuleRepository(db)
        self.entity_repo = KnowledgeEntityRepository(db)

    async def scan_module(self, module_id: UUID) -> KnowledgeModule:
        module = await self.module_repo.get_with_entities(module_id)
        if not module or not module.repo:
            raise ValueError("Module not found")

        repo_path = Path(module.repo.path)
        if not repo_path.is_dir():
            await self.module_repo.update_status(
                module, status=ScanStatus.FAILED, error=f"Repository path not found: {repo_path}"
            )
            await self.db.commit()
            raise ValueError(f"Repository path not found: {repo_path}")

        await self.module_repo.update_status(module, status=ScanStatus.SCANNING)
        await self.db.commit()
        await scan_event_manager.publish(
            module_id, {"event_type": "scan_started", "message": f"Scanning module {module.name}"}
        )

        try:
            all_files = enumerate_all_files(repo_path)
            indexed_paths: set[str] = set()
            extractions: list[ExtractionResult] = []
            scanned_files: list[ScannedFile] = filter_module_files(all_files, module.name)

            await scan_event_manager.publish(
                module_id,
                {
                    "event_type": "files_discovered",
                    "message": f"Found {len(scanned_files)} files in module",
                    "count": len(scanned_files),
                },
            )

            for iteration in range(MAX_CLOSURE_ITERATIONS):
                new_files = [f for f in scanned_files if f.relative_path not in indexed_paths]
                if not new_files:
                    break

                for scanned in new_files:
                    indexed_paths.add(scanned.relative_path)
                    results = extract_file(scanned)
                    extractions.extend(results)

                refs = collect_references(extractions)
                unresolved = refs - {e.name for e in extractions}
                dependency_files = resolve_reference_files(all_files, unresolved, indexed_paths)
                if dependency_files:
                    scanned_files.extend(dependency_files)
                    await scan_event_manager.publish(
                        module_id,
                        {
                            "event_type": "dependency_closure",
                            "message": f"Iteration {iteration + 1}: added {len(dependency_files)} dependency files",
                            "count": len(dependency_files),
                        },
                    )
                else:
                    break

            await self.entity_repo.delete_by_module(module_id)

            entities: list[KnowledgeEntity] = []
            for i, extraction in enumerate(extractions):
                summary, rules = await summarize_extraction(extraction)
                entity = KnowledgeEntity(
                    module_id=module_id,
                    entity_type=extraction.entity_type,
                    name=extraction.name,
                    file_path=extraction.file_path,
                    extracted=extraction.data,
                    summary=summary,
                    business_rules=rules or None,
                )
                entities.append(entity)
                if (i + 1) % 10 == 0:
                    await scan_event_manager.publish(
                        module_id,
                        {
                            "event_type": "summarizing",
                            "message": f"Processed {i + 1}/{len(extractions)} entities",
                            "progress": i + 1,
                            "total": len(extractions),
                        },
                    )

            if entities:
                await self.entity_repo.bulk_create(entities)

            await scan_event_manager.publish(
                module_id, {"event_type": "graph_building", "message": "Building knowledge graph"}
            )
            await write_module_graph(module, entities, extractions)

            await scan_event_manager.publish(
                module_id, {"event_type": "vector_indexing", "message": "Indexing vector store"}
            )
            indexed_count = await index_entities(module_id, entities)

            type_counts = Counter(e.entity_type for e in entities)
            stats = {
                "indexed_files": len(indexed_paths),
                "entities": len(entities),
                "dependencies": sum(len(e.references) for e in extractions),
                "objects": type_counts.get("SObject", 0),
                "fields": type_counts.get("Field", 0),
                "business_rules": sum(len(e.business_rules or []) for e in entities),
                "apex_classes": type_counts.get("ApexClass", 0),
                "lwc_components": type_counts.get("LwcComponent", 0),
                "flows": type_counts.get("Flow", 0),
                "validation_rules": type_counts.get("ValidationRule", 0),
                "vector_indexed": indexed_count,
                "graph_status": "ready",
                "vector_status": "ready" if indexed_count > 0 else "empty",
                "ai_status": "ready",
            }

            module.scanned_at = datetime.now(UTC)
            await self.module_repo.update_status(
                module, status=ScanStatus.COMPLETED, stats=stats
            )
            await self.db.commit()

            await scan_event_manager.publish(
                module_id,
                {"event_type": "scan_completed", "message": "Scan completed", "stats": stats},
            )
            return module

        except Exception as exc:
            logger.exception("Scan failed for module %s", module_id)
            await self.module_repo.update_status(
                module, status=ScanStatus.FAILED, error=str(exc)
            )
            await self.db.commit()
            await scan_event_manager.publish(
                module_id, {"event_type": "scan_failed", "message": str(exc)}
            )
            raise
