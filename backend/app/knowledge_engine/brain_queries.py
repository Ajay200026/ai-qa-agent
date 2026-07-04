"""Parameterized Cypher queries for Code Brain retrieval."""

from __future__ import annotations

from uuid import UUID

from app.knowledge.neo4j_client import neo4j_client


async def find_logic_for_field(module_id: UUID, field_name: str) -> list[dict]:
    return await neo4j_client.run_query(
        """
        MATCH (f:KeNode)
        WHERE f.module_id = $module_id AND f.type = 'Field'
          AND toLower(f.name) CONTAINS toLower($field)
        OPTIONAL MATCH path = (logic:KeNode)-[:CONTROLS|IMPLEMENTED_BY*1..3]->(f)
        WHERE logic.type = 'BusinessLogic' OR logic.type = 'Function'
        RETURN f.name as field, collect(DISTINCT logic.name) as logic_nodes,
               [n IN nodes(path) | n.name] as paths
        LIMIT 10
        """,
        {"module_id": str(module_id), "field": field_name},
    )


async def find_pricing_logic(module_id: UUID) -> list[dict]:
    return await neo4j_client.run_query(
        """
        MATCH (n:KeNode {module_id: $module_id})
        WHERE toLower(n.name) CONTAINS 'pric' OR toLower(n.summary) CONTAINS 'pric'
           OR toLower(n.description) CONTAINS 'pric'
        OPTIONAL MATCH (n)-[r]-(m:KeNode {module_id: $module_id})
        RETURN n.name as name, n.type as type, n.file_path as file_path,
               n.line_start as line_start, collect(DISTINCT m.name) as related
        LIMIT 15
        """,
        {"module_id": str(module_id)},
    )


async def find_defects_for_module(module_id: UUID) -> list[dict]:
    return await neo4j_client.run_query(
        """
        MATCH (d:KeNode {module_id: $module_id})
        WHERE d.type = 'Defect'
        OPTIONAL MATCH (d)-[:CAUSED_BY|AFFECTS]->(logic:KeNode)
        RETURN d.name as defect, d.ticket as ticket, d.summary as summary,
               collect(DISTINCT logic.name) as related_logic
        """,
        {"module_id": str(module_id)},
    )


async def find_path_between(module_id: UUID, source_name: str, target_name: str) -> list[dict]:
    return await neo4j_client.run_query(
        """
        MATCH (a:KeNode {module_id: $module_id}), (b:KeNode {module_id: $module_id})
        WHERE toLower(a.name) CONTAINS toLower($source) AND toLower(b.name) CONTAINS toLower($target)
        MATCH path = shortestPath((a)-[*..8]-(b))
        RETURN [n IN nodes(path) | {name: n.name, type: n.type, id: n.id}] as path
        LIMIT 3
        """,
        {"module_id": str(module_id), "source": source_name, "target": target_name},
    )


async def get_scenario_brain_subgraph(scenario_id: str) -> dict:
    node_records = await neo4j_client.run_query(
        """
        MATCH (s:KeNode)
        WHERE s.type = 'Scenario' AND (s.scenario_id = $sid OR s.name CONTAINS $sid)
        OPTIONAL MATCH (s)-[r*1..3]-(n:KeNode)
        RETURN collect(DISTINCT s) + collect(DISTINCT n) as nodes
        """,
        {"sid": scenario_id},
    )
    edge_records = await neo4j_client.run_query(
        """
        MATCH (s:KeNode)-[r]-(n:KeNode)
        WHERE s.scenario_id = $sid OR s.type = 'Scenario'
        RETURN s.id as source, n.id as target, type(r) as relationship
        LIMIT 100
        """,
        {"sid": scenario_id},
    )
    nodes = []
    for record in node_records:
        for node in record.get("nodes") or []:
            if node:
                nodes.append(
                    {
                        "id": node.get("id"),
                        "name": node.get("name"),
                        "type": node.get("type"),
                        "label": node.get("label"),
                    }
                )
    edges = [
        {"source": e["source"], "target": e["target"], "relationship": e["relationship"]}
        for e in edge_records
        if e.get("source")
    ]
    return {"nodes": nodes, "edges": edges}
