"""Chroma vector store for knowledge entity search."""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from langchain_chroma import Chroma
from langchain_core.documents import Document

from app.core.config import get_settings
from app.core.llm import get_embeddings
from app.models.knowledge import KnowledgeEntity

logger = logging.getLogger(__name__)

_INDEX_BATCH_SIZE = 64
_INDEX_MAX_RETRIES = 3

_collection_cache: dict[str, Chroma] = {}


def _collection_name(module_id: UUID) -> str:
    return f"ke_module_{str(module_id).replace('-', '_')}"


def _embedding_connection_hint() -> str:
    settings = get_settings()
    return (
        f"Check that LM Studio is running with the embedding model loaded and "
        f"LMSTUDIO_API_BASE is reachable from the backend ({settings.lmstudio_api_base}). "
        "Use http://host.docker.internal:1234/v1 when the backend runs in Docker."
    )


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


def _entity_document(entity: KnowledgeEntity) -> Document | None:
    extracted = entity.extracted or {}
    facts = []
    for key, value in extracted.items():
        if value is not None and value != "":
            facts.append(f"{key}: {value}")
    name = (entity.name or "").strip() or "Unknown"
    entity_type = (entity.entity_type or "").strip() or "Entity"
    content = f"{entity_type} {name}\n"
    if entity.summary:
        content += f"Summary: {entity.summary}\n"
    if facts:
        content += "\n".join(facts[:30])
    if entity.business_rules:
        content += "\nBusiness rules: " + "; ".join(str(r) for r in entity.business_rules)

    page_content = content.strip()
    if not page_content:
        return None

    return Document(
        page_content=page_content,
        metadata={
            "entity_id": str(entity.id),
            "entity_type": entity_type,
            "name": name,
            "file_path": entity.file_path or "",
            "module_id": str(entity.module_id),
        },
    )


def _add_documents_batched(
    store: Chroma, module_id: UUID, docs: list[Document], ids: list[str]
) -> int:
    if not docs:
        return 0

    indexed = 0
    for start in range(0, len(docs), _INDEX_BATCH_SIZE):
        batch_docs = docs[start : start + _INDEX_BATCH_SIZE]
        batch_ids = ids[start : start + _INDEX_BATCH_SIZE]
        batch_no = start // _INDEX_BATCH_SIZE + 1
        total_batches = (len(docs) + _INDEX_BATCH_SIZE - 1) // _INDEX_BATCH_SIZE
        texts = [doc.page_content for doc in batch_docs]
        if not all(isinstance(text, str) and text.strip() for text in texts):
            raise RuntimeError(
                f"Vector indexing batch {batch_no}/{total_batches} contains invalid document text."
            )

        for attempt in range(_INDEX_MAX_RETRIES):
            try:
                store.add_documents(batch_docs, ids=batch_ids)
                indexed += len(batch_docs)
                break
            except Exception as exc:
                err_text = str(exc).strip() or exc.__class__.__name__
                if attempt >= _INDEX_MAX_RETRIES - 1:
                    raise RuntimeError(
                        f"Vector indexing failed on batch {batch_no}/{total_batches}: {err_text}. "
                        f"{_embedding_connection_hint()}"
                    ) from exc
                logger.warning(
                    "Vector batch %s/%s failed (attempt %s/%s): %s",
                    batch_no,
                    total_batches,
                    attempt + 1,
                    _INDEX_MAX_RETRIES,
                    err_text,
                )
                _collection_cache.pop(_collection_name(module_id), None)
                store = _get_store(module_id)
                if store is None:
                    raise RuntimeError(
                        f"Embeddings not configured. {_embedding_connection_hint()}"
                    ) from exc
    return indexed


async def index_entities(module_id: UUID, entities: list[KnowledgeEntity]) -> int:
    store = _get_store(module_id)
    if store is None:
        logger.warning("Embeddings not configured; skipping vector indexing")
        return 0

    try:
        store.delete_collection()
    except Exception:
        pass

    _collection_cache.pop(_collection_name(module_id), None)
    store = _get_store(module_id)
    if store is None:
        return 0

    docs: list[Document] = []
    ids: list[str] = []
    for entity in entities:
        doc = _entity_document(entity)
        if doc is not None:
            docs.append(doc)
            ids.append(str(entity.id))
    if not docs:
        return 0
    return await asyncio.to_thread(_add_documents_batched, store, module_id, docs, ids)


async def index_function_chunks(module_id: UUID, extractions: list) -> int:
    """Index function-level code chunks for semantic search."""
    store = _get_store(module_id)
    if store is None:
        return 0

    docs: list[Document] = []
    ids: list[str] = []
    seen_ids: set[str] = set()
    for ext in extractions:
        for fn in (ext.data or {}).get("functions", []):
            fn_name = fn.get("name", "")
            if not fn_name:
                continue
            file_path = fn.get("file_path", ext.file_path or "")
            line_start = fn.get("line_start", "")
            doc_id = f"fn-{ext.name}-{fn_name}-{file_path}-{line_start}"
            if doc_id in seen_ids:
                doc_id = f"{doc_id}-{len(seen_ids)}"
            seen_ids.add(doc_id)
            content = (
                f"Function {fn_name} in {ext.name}\n"
                f"Signature: {fn.get('signature', '')}\n"
                f"File: {file_path}"
                f" Line: {line_start}"
            )
            docs.append(
                Document(
                    page_content=content,
                    metadata={
                        "entity_type": "Function",
                        "name": fn_name,
                        "component": ext.name,
                        "file_path": file_path,
                        "line_start": fn.get("line_start"),
                        "line_end": fn.get("line_end"),
                        "module_id": str(module_id),
                        "chunk_type": "function",
                    },
                )
            )
            ids.append(doc_id)

    if not docs:
        return 0
    return await asyncio.to_thread(_add_documents_batched, store, module_id, docs, ids)


async def search_entities(
    module_id: UUID, query: str, k: int = 8, entity_ids: list[str] | None = None
) -> list[dict]:
    store = _get_store(module_id)
    if store is None:
        return []

    results = store.similarity_search_with_score(query, k=k * 2)
    output = [
        {
            "content": doc.page_content,
            "score": score,
            "entity_id": doc.metadata.get("entity_id"),
            "entity_type": doc.metadata.get("entity_type"),
            "name": doc.metadata.get("name"),
            "file_path": doc.metadata.get("file_path"),
            "line_start": doc.metadata.get("line_start"),
            "chunk_type": doc.metadata.get("chunk_type"),
        }
        for doc, score in results
    ]
    if entity_ids:
        filtered = [r for r in output if r.get("entity_id") in entity_ids]
        if filtered:
            return filtered[:k]
    return output[:k]


def vector_status(module_id: UUID) -> str:
    store = _get_store(module_id)
    if store is None:
        return "not_configured"
    try:
        count = store._collection.count()  # noqa: SLF001
        return "ready" if count > 0 else "empty"
    except Exception:
        return "error"


def delete_module_vectors(module_id: UUID) -> None:
    """Remove Chroma collection without initializing the embedding client (avoids LM Studio hangs)."""
    name = _collection_name(module_id)
    _collection_cache.pop(name, None)
    try:
        import chromadb

        settings = get_settings()
        settings.chroma_dir.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(settings.chroma_dir))
        client.delete_collection(name)
    except Exception:
        logger.debug("Chroma collection %s not found or already deleted", name)
