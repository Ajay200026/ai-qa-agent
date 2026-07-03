"""Ask AI pipeline: graph + vector retrieval -> local LLM answer."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import AsyncGenerator
from uuid import UUID

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import get_chat_llm, is_llm_configured
from app.knowledge_engine.graph_writer import (
    find_entity_neighbors,
    find_impact,
    find_navigation_path,
    get_module_graph,
)
from app.knowledge_engine.vector_store import search_entities
from app.repositories.knowledge_repository import KnowledgeEntityRepository, KnowledgeModuleRepository
from app.schemas.knowledge_engine import AskCitation

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a Principal Salesforce Architect with deep knowledge of the application.
Answer questions using ONLY the provided context from the indexed knowledge graph.
Be specific: mention component names, Apex classes, fields, flows, and business rules.
If navigation is asked, provide numbered steps.
Cite entity names from the context. Do not invent components not in the context."""


class AskService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.module_repo = KnowledgeModuleRepository(db)
        self.entity_repo = KnowledgeEntityRepository(db)

    async def ask(self, module_id: UUID, question: str) -> dict:
        context, citations = await self._build_context(module_id, question)
        answer = await self._generate_answer(question, context)
        return {"answer": answer, "citations": citations}

    async def ask_stream(self, module_id: UUID, question: str) -> AsyncGenerator[str, None]:
        context, citations = await self._build_context(module_id, question)
        llm = get_chat_llm(temperature=0.2)
        if llm is None:
            yield json.dumps({"type": "error", "message": "LLM not configured"})
            return

        yield json.dumps({"type": "citations", "citations": [c.model_dump() for c in citations]})

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=f"Context:\n{context}\n\nQuestion: {question}"),
        ]
        try:
            async for chunk in llm.astream(messages):
                text = chunk.content if isinstance(chunk.content, str) else str(chunk.content)
                if text:
                    yield json.dumps({"type": "token", "content": text})
        except Exception as exc:
            logger.exception("Streaming ask failed")
            yield json.dumps({"type": "error", "message": str(exc)})
            return

        yield json.dumps({"type": "done"})

    async def _build_context(
        self, module_id: UUID, question: str
    ) -> tuple[str, list[AskCitation]]:
        module = await self.module_repo.get_with_entities(module_id)
        if not module:
            raise ValueError("Module not found")

        citations: list[AskCitation] = []
        context_parts: list[str] = [f"Module: {module.name}"]

        # Entity keyword detection
        keywords = self._extract_keywords(question)
        for keyword in keywords[:5]:
            matches = await self.entity_repo.search_by_name(module_id, keyword)
            for entity in matches[:3]:
                citations.append(
                    AskCitation(
                        entity_id=str(entity.id),
                        name=entity.name,
                        entity_type=entity.entity_type,
                        file_path=entity.file_path,
                    )
                )
                context_parts.append(self._format_entity(entity))

        # Vector search
        vector_results = await search_entities(module_id, question, k=6)
        for result in vector_results:
            if result.get("entity_id") and not any(
                c.entity_id == result["entity_id"] for c in citations
            ):
                citations.append(
                    AskCitation(
                        entity_id=result.get("entity_id"),
                        name=result.get("name", ""),
                        entity_type=result.get("entity_type", ""),
                        file_path=result.get("file_path"),
                    )
                )
            context_parts.append(result.get("content", ""))

        # Graph queries
        for keyword in keywords[:3]:
            neighbors = await find_entity_neighbors(module_id, keyword)
            for record in neighbors:
                context_parts.append(
                    f"Graph: {record.get('name')} ({record.get('type')}) neighbors: {record.get('neighbors')}"
                )
            impact = await find_impact(module_id, keyword)
            for record in impact:
                if record.get("dependents"):
                    context_parts.append(
                        f"Impact on {record.get('target')}: dependents {record.get('dependents')}"
                    )
            nav = await find_navigation_path(module_id, keyword)
            if nav:
                context_parts.append(f"Navigation path to {keyword}: " + " -> ".join(nav))

        if "dependenc" in question.lower() or "graph" in question.lower():
            graph = await get_module_graph(module_id)
            context_parts.append(
                f"Graph summary: {len(graph.get('nodes', []))} nodes, {len(graph.get('edges', []))} edges"
            )

        context = "\n\n".join(context_parts)[:12000]
        return context, citations[:15]

    async def _generate_answer(self, question: str, context: str) -> str:
        llm = get_chat_llm(temperature=0.2)
        if llm is None:
            if not is_llm_configured():
                return "LLM is not configured. Set LLM_PROVIDER=lmstudio and ensure LM Studio is running."
            return "Unable to connect to LLM."

        response = await llm.ainvoke(
            [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=f"Context:\n{context}\n\nQuestion: {question}"),
            ]
        )
        return response.content if isinstance(response.content, str) else str(response.content)

    def _extract_keywords(self, question: str) -> list[str]:
        # Salesforce-style identifiers and quoted strings
        keywords = re.findall(r"\b([A-Z][A-Za-z0-9_]*__c)\b", question)
        keywords += re.findall(r"\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b", question)
        keywords += re.findall(r"['\"]([^'\"]+)['\"]", question)
        words = [w for w in re.findall(r"\b[A-Za-z]{4,}\b", question) if w.lower() not in STOP_WORDS]
        keywords.extend(words)
        return list(dict.fromkeys(keywords))

    def _format_entity(self, entity) -> str:
        parts = [f"{entity.entity_type}: {entity.name}"]
        if entity.summary:
            parts.append(f"Summary: {entity.summary}")
        if entity.business_rules:
            parts.append(f"Rules: {entity.business_rules}")
        if entity.extracted:
            parts.append(f"Details: {json.dumps(entity.extracted, default=str)[:1500]}")
        if entity.file_path:
            parts.append(f"File: {entity.file_path}")
        return "\n".join(parts)


STOP_WORDS = {
    "what", "where", "which", "when", "does", "this", "that", "with", "from",
    "explain", "show", "find", "used", "uses", "flow", "button", "complete",
    "execution", "module", "about", "tell", "give", "list", "have", "there",
}
