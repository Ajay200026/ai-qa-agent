"""Orchestrate module scanning, extraction, graph building, and vector indexing."""

from __future__ import annotations

import logging
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.brain_llm_router import is_scan_llm_available
from app.knowledge_engine.events import scan_event_manager
from app.knowledge_engine.brain_enricher import enrich_module_extractions
from app.knowledge_engine.brain_graph_writer import write_brain_graph
from app.knowledge_engine.extractors.router import collect_references, extract_file
from app.knowledge_engine.extractors.scenario_extractor import extract_scenario_docs
from app.knowledge_engine.graph_writer import write_module_graph
from app.knowledge_engine.scanner.repo_scanner import (
    enumerate_all_files,
    preflight_scope_files,
    resolve_scan_root,
)
from app.knowledge_engine.summarizer import summarize_extraction
from app.knowledge_engine.types import ExtractionResult, ScannedFile
from app.knowledge_engine.vector_store import index_entities, index_function_chunks
from app.models.knowledge import KnowledgeEntity, KnowledgeModule, ScanStatus
from app.repositories.knowledge_repository import (
    KnowledgeEntityRepository,
    KnowledgeModuleRepository,
)
from app.services.knowledge_repo_service import KnowledgeRepoService

logger = logging.getLogger(__name__)

MAX_CLOSURE_ITERATIONS = 5


class ScanService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.module_repo = KnowledgeModuleRepository(db)
        self.entity_repo = KnowledgeEntityRepository(db)

    async def _persist_interim_stats(self, module: KnowledgeModule, stats: dict) -> None:
        module.stats = stats
        module.scan_status = ScanStatus.SCANNING.value
        await self.db.flush()
        await self.db.commit()

    async def scan_module(self, module_id: UUID) -> KnowledgeModule:
        module = await self.module_repo.get_with_entities(module_id)
        if not module or not module.repo:
            raise ValueError("Module not found")

        repo_service = KnowledgeRepoService(self.db)
        try:
            repo_path = await repo_service.ensure_repo_path(module.repo)
        except ValueError as exc:
            await self.module_repo.update_status(
                module, status=ScanStatus.FAILED, error=str(exc)
            )
            await self.db.commit()
            raise

        scan_root = resolve_scan_root(repo_path)
        scanned_files, repaired_scope = preflight_scope_files(
            repo_path, module.name, module.scope_path
        )

        if repaired_scope and repaired_scope != module.scope_path:
            module.scope_path = repaired_scope
            await self.db.flush()

        if not scanned_files:
            scope_label = module.scope_path or module.name
            error = (
                f"No Salesforce files matched scope '{scope_label}'. "
                "Delete this module and re-select the folder (e.g. Data Change)."
            )
            logger.warning(
                "Scan preflight found 0 files for module %s scope=%s",
                module_id,
                scope_label,
            )
            await self.module_repo.update_status(
                module, status=ScanStatus.FAILED, error=error
            )
            await self.db.commit()
            await scan_event_manager.publish(
                module_id, {"event_type": "scan_failed", "message": error}
            )
            raise ValueError(error)

        use_llm = await is_scan_llm_available()
        logger.info(
            "Scan module %s scope=%s files=%d use_llm=%s",
            module_id,
            module.scope_path or module.name,
            len(scanned_files),
            use_llm,
        )

        await self.module_repo.update_status(module, status=ScanStatus.SCANNING)
        module.scan_error = None
        await self.db.flush()
        await self.db.commit()
        await scan_event_manager.publish(
            module_id, {"event_type": "scan_started", "message": f"Scanning module {module.name}"}
        )

        try:
            all_files = enumerate_all_files(scan_root)
            indexed_paths: set[str] = set()
            extractions: list[ExtractionResult] = []
            processed_lwc_bundles: set[str] = set()

            await scan_event_manager.publish(
                module_id,
                {
                    "event_type": "files_discovered",
                    "message": f"Found {len(scanned_files)} Salesforce files in module",
                    "count": len(scanned_files),
                },
            )
            await self._persist_interim_stats(
                module,
                {
                    "phase": "extracting",
                    "files_discovered": len(scanned_files),
                    "entities": 0,
                    "use_llm": use_llm,
                },
            )

            for iteration in range(MAX_CLOSURE_ITERATIONS):
                new_files = [f for f in scanned_files if f.relative_path not in indexed_paths]
                if not new_files:
                    break

                for scanned in new_files:
                    indexed_paths.add(scanned.relative_path)
                    results = extract_file(scanned, processed_lwc_bundles)
                    extractions.extend(results)

                refs = collect_references(extractions)
                unresolved = refs - {e.name for e in extractions}
                dependency_files = resolve_reference_files_from_all(
                    all_files, unresolved, indexed_paths
                )
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

            # Scenario docs scoped to module folder
            if module.scope_path:
                scope_prefix = module.scope_path.replace("\\", "/").strip("/")
                for doc_path in scan_root.rglob("*.md"):
                    rel = str(doc_path.relative_to(scan_root)).replace("\\", "/")
                    if rel in indexed_paths:
                        continue
                    if rel == scope_prefix or rel.startswith(scope_prefix + "/"):
                        extractions.extend(extract_scenario_docs(doc_path, rel))

            await scan_event_manager.publish(
                module_id,
                {
                    "event_type": "entities_extracted",
                    "message": f"Extracted {len(extractions)} components from code",
                    "count": len(extractions),
                },
            )
            await self._persist_interim_stats(
                module,
                {
                    "phase": "summarizing",
                    "files_discovered": len(scanned_files),
                    "entities": len(extractions),
                    "use_llm": use_llm,
                },
            )

            await self.entity_repo.delete_by_module(module_id)

            entities: list[KnowledgeEntity] = []
            for i, extraction in enumerate(extractions):
                summary, rules = await summarize_extraction(extraction, use_llm=use_llm)
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
                module_id, {"event_type": "brain_enrichment", "message": "Enriching Code Brain with AI"}
            )
            enrichment = await enrich_module_extractions(
                module.name, extractions, use_llm=use_llm
            )
            await write_brain_graph(module.repo, module, entities, extractions, enrichment)

            await scan_event_manager.publish(
                module_id, {"event_type": "vector_indexing", "message": "Indexing vector store"}
            )
            vector_error: str | None = None
            indexed_count = 0
            fn_indexed = 0
            try:
                indexed_count = await index_entities(module_id, entities)
                fn_indexed = await index_function_chunks(module_id, extractions)
                indexed_count += fn_indexed
            except Exception as exc:
                vector_error = str(exc).strip() or exc.__class__.__name__
                logger.exception("Vector indexing failed for module %s", module_id)

            type_counts = Counter(e.entity_type for e in entities)
            stats = {
                "phase": "completed",
                "indexed_files": len(indexed_paths),
                "files_discovered": len(scanned_files),
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
                "function_chunks_indexed": fn_indexed,
                "brain_status": "ready",
                "graph_status": "ready",
                "vector_status": (
                    "ready"
                    if indexed_count > 0
                    else ("error" if vector_error else "empty")
                ),
                "vector_error": vector_error,
                "ai_status": "ready" if use_llm else "fallback",
                "use_llm": use_llm,
            }

            module.scanned_at = datetime.now(UTC)
            final_status = ScanStatus.COMPLETED if not vector_error else ScanStatus.FAILED
            await self.module_repo.update_status(
                module,
                status=final_status,
                stats=stats,
                error=vector_error,
            )
            await self.db.commit()

            if vector_error:
                await scan_event_manager.publish(
                    module_id,
                    {"event_type": "scan_failed", "message": vector_error, "stats": stats},
                )
                raise RuntimeError(vector_error)

            await scan_event_manager.publish(
                module_id,
                {"event_type": "scan_completed", "message": "Scan completed", "stats": stats},
            )
            return module

        except Exception as exc:
            if str(exc).strip() == (module.scan_error or "").strip():
                raise
            logger.exception("Scan failed for module %s", module_id)
            await self.module_repo.update_status(
                module, status=ScanStatus.FAILED, error=str(exc)
            )
            await self.db.commit()
            await scan_event_manager.publish(
                module_id, {"event_type": "scan_failed", "message": str(exc)}
            )
            raise

    async def reindex_vectors(self, module_id: UUID) -> KnowledgeModule:
        """Rebuild Chroma vectors from persisted entities without re-scanning code."""
        module = await self.module_repo.get_with_entities(module_id)
        if not module:
            raise ValueError("Module not found")

        entities = list(module.entities or [])
        if not entities:
            raise ValueError("No entities found for this module. Run a full scan first.")

        await self.module_repo.update_status(module, status=ScanStatus.SCANNING)
        module.scan_error = None
        await self.db.commit()
        await scan_event_manager.publish(
            module_id,
            {"event_type": "vector_indexing", "message": "Re-indexing vector store"},
        )

        class _ExtractionStub:
            __slots__ = ("name", "file_path", "data")

            def __init__(self, name: str, file_path: str | None, data: dict | None):
                self.name = name
                self.file_path = file_path
                self.data = data or {}

        extractions = [
            _ExtractionStub(entity.name, entity.file_path, entity.extracted)
            for entity in entities
        ]

        indexed_count = await index_entities(module_id, entities)
        fn_indexed = 0
        try:
            fn_indexed = await index_function_chunks(module_id, extractions)
        except Exception as exc:
            logger.warning("Function chunk indexing failed for module %s: %s", module_id, exc)
        indexed_count += fn_indexed

        stats = dict(module.stats or {})
        stats.update(
            {
                "phase": "completed",
                "entities": len(entities),
                "vector_indexed": indexed_count,
                "function_chunks_indexed": fn_indexed,
                "graph_status": stats.get("graph_status") or "ready",
                "brain_status": stats.get("brain_status") or "ready",
                "vector_status": "ready" if indexed_count > 0 else "empty",
                "vector_error": None,
            }
        )

        module.scanned_at = datetime.now(UTC)
        await self.module_repo.update_status(
            module, status=ScanStatus.COMPLETED, stats=stats, error=None
        )
        await self.db.commit()
        await scan_event_manager.publish(
            module_id,
            {"event_type": "scan_completed", "message": "Vector indexing completed", "stats": stats},
        )
        return module


def resolve_reference_files_from_all(
    all_files: list[ScannedFile],
    references: set[str],
    already_indexed: set[str],
) -> list[ScannedFile]:
    from app.knowledge_engine.scanner.repo_scanner import resolve_reference_files

    return resolve_reference_files(all_files, references, already_indexed)
