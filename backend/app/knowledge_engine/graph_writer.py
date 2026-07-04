"""Write application knowledge graph nodes and relationships to Neo4j."""

from __future__ import annotations

import logging
from uuid import UUID

from app.knowledge.neo4j_client import neo4j_client
from app.knowledge_engine.graph_schema import KNOWLEDGE_CONSTRAINTS
from app.knowledge_engine.types import ExtractionResult
from app.models.knowledge import KnowledgeEntity, KnowledgeModule

logger = logging.getLogger(__name__)

RELATIONSHIP_TYPES = {
    "CALLS",
    "USES",
    "READS",
    "WRITES",
    "DEPENDS_ON",
    "BELONGS_TO",
    "REFERENCES",
    "RENDERS",
    "TRIGGERS",
    "IMPLEMENTS",
}


async def init_knowledge_schema() -> None:
    for constraint in KNOWLEDGE_CONSTRAINTS:
        try:
            await neo4j_client.run_query(constraint)
        except Exception as exc:
            logger.debug("Knowledge constraint may exist: %s", exc)


def _node_id(module_id: UUID, entity_type: str, name: str) -> str:
    return f"{module_id}:{entity_type}:{name}"


async def clear_module_graph(module_id: UUID) -> None:
    await neo4j_client.run_query(
        "MATCH (n:KeNode {module_id: $module_id}) DETACH DELETE n",
        {"module_id": str(module_id)},
    )


async def write_module_graph(
    module: KnowledgeModule,
    entities: list[KnowledgeEntity],
    extractions: list[ExtractionResult],
) -> None:
    await init_knowledge_schema()
    module_id = str(module.id)
    await clear_module_graph(module.id)

    # Module root node
    await neo4j_client.run_query(
        """
        MERGE (m:KeNode:Module {id: $id})
        SET m.module_id = $module_id, m.name = $name, m.type = 'Module',
            m.label = $name, m.summary = $summary
        """,
        {
            "id": f"{module_id}:Module:{module.name}",
            "module_id": module_id,
            "name": module.name,
            "summary": f"Salesforce module: {module.name}",
        },
    )

    name_to_id: dict[str, str] = {}

    for entity in entities:
        node_id = _node_id(module.id, entity.entity_type, entity.name)
        name_to_id[entity.name.lower()] = node_id
        await neo4j_client.run_query(
            """
            MERGE (n:KeNode {id: $id})
            SET n.module_id = $module_id, n.name = $name, n.type = $type,
                n.label = $name, n.summary = $summary, n.file_path = $file_path,
                n.entity_id = $entity_id
            WITH n
            MATCH (m:KeNode {id: $module_node_id})
            MERGE (m)-[:CONTAINS]->(n)
            """,
            {
                "id": node_id,
                "module_id": module_id,
                "name": entity.name,
                "type": entity.entity_type,
                "summary": entity.summary or "",
                "file_path": entity.file_path or "",
                "entity_id": str(entity.id),
                "module_node_id": f"{module_id}:Module:{module.name}",
            },
        )

    for extraction in extractions:
        source_id = name_to_id.get(extraction.name.lower())
        if not source_id:
            source_id = _node_id(module.id, extraction.entity_type, extraction.name)
        for rel in extraction.relationships:
            rel_type = rel.get("type", "DEPENDS_ON")
            if rel_type not in RELATIONSHIP_TYPES:
                rel_type = "DEPENDS_ON"
            target_name = rel.get("target", "")
            if not target_name:
                continue
            target_id = name_to_id.get(target_name.lower()) or _node_id(
                module.id, "Reference", target_name
            )
            if target_id not in name_to_id.values():
                await neo4j_client.run_query(
                    """
                    MERGE (n:KeNode {id: $id})
                    SET n.module_id = $module_id, n.name = $name, n.type = 'Reference',
                        n.label = $name
                    """,
                    {
                        "id": target_id,
                        "module_id": module_id,
                        "name": target_name,
                    },
                )
            await neo4j_client.run_query(
                f"""
                MATCH (a:KeNode {{id: $source_id}})
                MATCH (b:KeNode {{id: $target_id}})
                MERGE (a)-[r:{rel_type}]->(b)
                """,
                {"source_id": source_id, "target_id": target_id},
            )


def _graph_node_from_record(record: dict) -> dict | None:
    node_id = record.get("id")
    if not node_id:
        return None
    label = record.get("label") or record.get("name") or "Unknown"
    name = record.get("name") or record.get("label") or "Unknown"
    return {
        "id": node_id,
        "label": label,
        "type": record.get("type") or "Reference",
        "name": name,
        "summary": record.get("summary"),
        "file_path": record.get("file_path"),
        "entity_id": record.get("entity_id"),
    }


async def get_module_graph(module_id: UUID) -> dict:
    module_key = str(module_id)
    node_records = await neo4j_client.run_query(
        """
        MATCH (n:KeNode {module_id: $module_id})
        RETURN n.id as id, n.label as label, n.type as type, n.name as name,
               n.summary as summary, n.file_path as file_path, n.entity_id as entity_id
        """,
        {"module_id": module_key},
    )
    edge_records = await neo4j_client.run_query(
        """
        MATCH (a:KeNode {module_id: $module_id})-[r]->(b:KeNode {module_id: $module_id})
        RETURN a.id as source, b.id as target, type(r) as relationship
        """,
        {"module_id": module_key},
    )

    nodes = [
        node
        for record in node_records
        if (node := _graph_node_from_record(record)) is not None
    ]
    edges = [
        {
            "id": f"edge-{index}",
            "source": record["source"],
            "target": record["target"],
            "relationship": record.get("relationship") or "RELATED",
        }
        for index, record in enumerate(edge_records)
        if record.get("source") and record.get("target")
    ]
    return {"nodes": nodes, "edges": edges}


async def find_entity_neighbors(module_id: UUID, name: str) -> list[dict]:
    return await neo4j_client.run_query(
        """
        MATCH (n:KeNode {module_id: $module_id})
        WHERE toLower(n.name) CONTAINS toLower($name)
        OPTIONAL MATCH (n)-[r]-(m:KeNode {module_id: $module_id})
        RETURN n.name as name, n.type as type, n.file_path as file_path,
               collect(DISTINCT {rel: type(r), target: m.name, target_type: m.type}) as neighbors
        LIMIT 20
        """,
        {"module_id": str(module_id), "name": name},
    )


async def find_impact(module_id: UUID, name: str) -> list[dict]:
    return await neo4j_client.run_query(
        """
        MATCH (target:KeNode {module_id: $module_id})
        WHERE toLower(target.name) = toLower($name)
        OPTIONAL MATCH (dependent:KeNode {module_id: $module_id})-[:DEPENDS_ON|CALLS|USES|REFERENCES*1..3]->(target)
        RETURN target.name as target, collect(DISTINCT dependent.name) as dependents
        """,
        {"module_id": str(module_id), "name": name},
    )


async def find_navigation_path(module_id: UUID, field_name: str) -> list[str]:
    records = await neo4j_client.run_query(
        """
        MATCH path = (m:KeNode:Module {module_id: $module_id})-[:CONTAINS*1..5]->(f:KeNode)
        WHERE toLower(f.name) CONTAINS toLower($field) OR f.type = 'Field'
        WITH path, f
        ORDER BY length(path)
        LIMIT 1
        RETURN [n IN nodes(path) | n.name + ' (' + n.type + ')'] as steps
        """,
        {"module_id": str(module_id), "field": field_name},
    )
    if records and records[0].get("steps"):
        return records[0]["steps"]
    return []
