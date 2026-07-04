"""Graph-aware Ask AI using Code Brain retrieval."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import AsyncGenerator
from uuid import UUID

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.brain_llm_router import get_chat_agent_llm
from app.core.llm import is_llm_configured
from app.knowledge_engine.ask_service import AskService
from app.knowledge_engine.brain_queries import (
    find_defects_for_module,
    find_logic_for_field,
    find_pricing_logic,
)
from app.knowledge_engine.graph_writer import find_entity_neighbors, get_module_graph
from app.knowledge_engine.vector_store import search_entities
from app.repositories.knowledge_repository import KnowledgeModuleRepository
from app.schemas.knowledge_engine import AskCitation

logger = logging.getLogger(__name__)

BRAIN_SYSTEM = """You are a Salesforce Code Brain assistant.
Answer using ONLY the provided graph context, code chunks, and paths.
Format responses with sections when helpful:
Found / Module / Logic / Path / Scenario
Cite specific file names and line numbers from context. Never invent code."""


class BrainAskService(AskService):
    def __init__(self, db: AsyncSession):
        super().__init__(db)
        self.module_repo = KnowledgeModuleRepository(db)

    def _classify_intent(self, question: str) -> str:
        q = question.lower()
        if "defect" in q or "bug" in q or "us-" in q:
            return "defects"
        if "where is" in q or "find" in q or "pricing" in q:
            return "locate"
        if "depend" in q or "flow" in q or "what happens" in q:
            return "flow"
        return "general"

    async def _build_brain_context(self, module_id: UUID, question: str) -> tuple[str, list[AskCitation]]:
        module = await self.module_repo.get_with_entities(module_id)
        if not module:
            raise ValueError("Module not found")

        citations: list[AskCitation] = []
        parts: list[str] = [f"Module: {module.name}"]
        intent = self._classify_intent(question)

        if intent == "defects":
            records = await find_defects_for_module(module_id)
            for rec in records:
                parts.append(f"Defect {rec.get('ticket')}: {rec.get('summary')}")
                citations.append(
                    AskCitation(name=rec.get("defect", ""), entity_type="Defect")
                )

        if intent == "locate" or "pricing" in question.lower():
            records = await find_pricing_logic(module_id)
            for rec in records:
                line = f" - {rec.get('name')} ({rec.get('type')})"
                if rec.get("file_path"):
                    line += f" @ {rec['file_path']}"
                if rec.get("line_start"):
                    line += f":{rec['line_start']}"
                parts.append(line)
                citations.append(
                    AskCitation(
                        name=rec.get("name", ""),
                        entity_type=rec.get("type", ""),
                        file_path=rec.get("file_path"),
                    )
                )

        field_match = re.search(r"([\w]+__c)", question, re.IGNORECASE)
        if field_match:
            field = field_match.group(1)
            records = await find_logic_for_field(module_id, field)
            for rec in records:
                parts.append(f"Field {rec.get('field')}: logic={rec.get('logic_nodes')}")

        vector_hits = await search_entities(module_id, question, k=6)
        for hit in vector_hits:
            chunk = hit.get("content", "")[:400]
            parts.append(f"Code chunk ({hit.get('name')}): {chunk}")
            if hit.get("file_path"):
                citations.append(
                    AskCitation(
                        name=hit.get("name", ""),
                        entity_type=hit.get("entity_type", ""),
                        file_path=hit.get("file_path"),
                    )
                )

        keywords = [w for w in re.findall(r"\w+", question) if len(w) > 3][:3]
        for kw in keywords:
            neighbors = await find_entity_neighbors(module_id, kw)
            for rec in neighbors:
                parts.append(f"Graph neighbor: {rec.get('name')} ({rec.get('type')})")

        graph = await get_module_graph(module_id)
        parts.append(f"Graph size: {len(graph.get('nodes', []))} nodes")

        return "\n".join(parts), citations

    async def ask(self, module_id: UUID, question: str) -> dict:
        context, citations = await self._build_brain_context(module_id, question)
        llm = get_chat_agent_llm(temperature=0.2)
        if llm is None:
            return await super().ask(module_id, question)
        messages = [
            SystemMessage(content=BRAIN_SYSTEM),
            HumanMessage(content=f"Context:\n{context}\n\nQuestion: {question}"),
        ]
        response = await llm.ainvoke(messages)
        answer = response.content if isinstance(response.content, str) else str(response.content)
        return {"answer": answer, "citations": citations}

    async def ask_stream(self, module_id: UUID, question: str) -> AsyncGenerator[str, None]:
        context, citations = await self._build_brain_context(module_id, question)
        llm = get_chat_agent_llm(temperature=0.2)
        if llm is None:
            async for chunk in super().ask_stream(module_id, question):
                yield chunk
            return

        yield json.dumps({"type": "citations", "citations": [c.model_dump() for c in citations]})
        messages = [
            SystemMessage(content=BRAIN_SYSTEM),
            HumanMessage(content=f"Context:\n{context}\n\nQuestion: {question}"),
        ]
        try:
            async for chunk in llm.astream(messages):
                text = chunk.content if isinstance(chunk.content, str) else str(chunk.content)
                if text:
                    yield json.dumps({"type": "token", "content": text})
        except Exception as exc:
            yield json.dumps({"type": "error", "message": str(exc)})
            return
        yield json.dumps({"type": "done"})
