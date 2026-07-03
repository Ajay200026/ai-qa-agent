"""Chroma vector store for knowledge entity search."""

from __future__ import annotations

import logging
from uuid import UUID

from langchain_chroma import Chroma
from langchain_core.documents import Document

from app.core.config import get_settings
from app.core.llm import get_embeddings
from app.models.knowledge import KnowledgeEntity

logger = logging.getLogger(__name__)

_collection_cache: dict[str, Chroma] = {}


def _collection_name(module_id: UUID) -> str:
    return f"ke_module_{str(module_id).replace('-', '_')}"


def _get_store(module_id: UUID) -> Chroma | None:
    embeddings = get_embeddings()
    if embeddings is None:
        return None
    name = _collection_name(module_id)
    if name not in _collection_cache:
        settings = get_settings()
        settings.chroma_dir.mkdir(parents=True, exist_ok=True)
        _collection_cache[name] = Chroma(
            collection_name=name,
            embedding_function=embeddings,
            persist_directory=str(settings.chroma_dir),
        )
    return _collection_cache[name]


def _entity_document(entity: KnowledgeEntity) -> Document:
    extracted = entity.extracted or {}
    facts = []
    for key, value in extracted.items():
        if value:
            facts.append(f"{key}: {value}")
    content = f"{entity.entity_type} {entity.name}\n"
    if entity.summary:
        content += f"Summary: {entity.summary}\n"
    content += "\n".join(facts[:30])
    if entity.business_rules:
        content += "\nBusiness rules: " + "; ".join(str(r) for r in entity.business_rules)

    return Document(
        page_content=content,
        metadata={
            "entity_id": str(entity.id),
            "entity_type": entity.entity_type,
            "name": entity.name,
            "file_path": entity.file_path or "",
            "module_id": str(entity.module_id),
        },
    )


async def index_entities(module_id: UUID, entities: list[KnowledgeEntity]) -> int:
    store = _get_store(module_id)
    if store is None:
        logger.warning("Embeddings not configured; skipping vector indexing")
        return 0

    try:
        store.delete_collection()
    except Exception:
        pass

    store = _get_store(module_id)
    if store is None:
        return 0

    docs = [_entity_document(e) for e in entities]
    if not docs:
        return 0

    ids = [str(e.id) for e in entities]
    store.add_documents(docs, ids=ids)
    return len(docs)


async def search_entities(module_id: UUID, query: str, k: int = 8) -> list[dict]:
    store = _get_store(module_id)
    if store is None:
        return []

    results = store.similarity_search_with_score(query, k=k)
    return [
        {
            "content": doc.page_content,
            "score": score,
            "entity_id": doc.metadata.get("entity_id"),
            "entity_type": doc.metadata.get("entity_type"),
            "name": doc.metadata.get("name"),
            "file_path": doc.metadata.get("file_path"),
        }
        for doc, score in results
    ]


def vector_status(module_id: UUID) -> str:
    store = _get_store(module_id)
    if store is None:
        return "not_configured"
    try:
        count = store._collection.count()  # noqa: SLF001
        return "ready" if count > 0 else "empty"
    except Exception:
        return "error"
