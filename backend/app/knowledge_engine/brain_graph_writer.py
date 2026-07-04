"""Write typed Code Brain nodes and relationships to Neo4j."""

from __future__ import annotations

import logging
from uuid import UUID

from app.knowledge.neo4j_client import neo4j_client
from app.knowledge_engine.brain_schema import BRAIN_CONSTRAINTS, BRAIN_RELATIONSHIPS, ORBIT_LEVELS
from app.knowledge_engine.types import ExtractionResult
from app.models.knowledge import KnowledgeEntity, KnowledgeModule, KnowledgeRepo

logger = logging.getLogger(__name__)


async def init_brain_schema() -> None:
    for constraint in BRAIN_CONSTRAINTS:
        try:
            await neo4j_client.run_query(constraint)
        except Exception as exc:
            logger.debug("Brain constraint may exist: %s", exc)


def _node_id(prefix: str, *parts: str) -> str:
    return f"{prefix}:{':'.join(parts)}"


def _orbit_level(node_type: str) -> int:
    return ORBIT_LEVELS.get(node_type, 3)


async def _merge_node(
    node_id: str,
    labels: list[str],
    props: dict,
) -> None:
    label_str = ":".join(["KeNode"] + labels)
    await neo4j_client.run_query(
        f"""
        MERGE (n:{label_str} {{id: $id}})
        SET n += $props
        """,
        {"id": node_id, "props": props},
    )


async def _merge_rel(source_id: str, target_id: str, rel_type: str) -> None:
    if rel_type not in BRAIN_RELATIONSHIPS:
        rel_type = "CONTAINS"
    await neo4j_client.run_query(
        f"""
        MATCH (a:KeNode {{id: $source_id}})
        MATCH (b:KeNode {{id: $target_id}})
        MERGE (a)-[r:{rel_type}]->(b)
        """,
        {"source_id": source_id, "target_id": target_id},
    )


async def write_repository_node(repo: KnowledgeRepo) -> str:
    await init_brain_schema()
    repo_id = str(repo.id)
    node_id = _node_id("repo", repo_id)
    await _merge_node(
        node_id,
        ["Repository"],
        {
            "name": repo.name,
            "path": repo.path,
            "repo_id": repo_id,
            "type": "Repository",
            "label": repo.name,
            "orbit_level": 0,
        },
    )
    return node_id


async def clear_module_brain(module_id: UUID) -> None:
    mid = str(module_id)
    await neo4j_client.run_query(
        "MATCH (n:KeNode {module_id: $module_id}) DETACH DELETE n",
        {"module_id": mid},
    )


async def write_brain_graph(
    repo: KnowledgeRepo | None,
    module: KnowledgeModule,
    entities: list[KnowledgeEntity],
    extractions: list[ExtractionResult],
    enrichment: dict | None = None,
) -> None:
    """Write typed brain graph for a scanned module."""
    await init_brain_schema()
    module_id = str(module.id)
    repo_id = str(module.repo_id)

    repo_node_id = _node_id("repo", repo_id)
    if repo:
        await write_repository_node(repo)

    module_node_id = _node_id("mod", module_id, module.name)
    await _merge_node(
        module_node_id,
        ["Module"],
        {
            "module_id": module_id,
            "repo_id": repo_id,
            "name": module.name,
            "type": "Module",
            "label": module.name,
            "summary": f"Salesforce module: {module.name}",
            "orbit_level": 1,
        },
    )
    await _merge_rel(repo_node_id, module_node_id, "HAS_MODULE")

    name_to_id: dict[str, str] = {}
    extraction_by_name = {e.name.lower(): e for e in extractions}

    for entity in entities:
        kind = entity.entity_type
        brain_type = "Component" if kind in ("ApexClass", "LwcComponent", "Flow", "ApexTrigger") else kind
        comp_id = _node_id("ent", module_id, kind, entity.name)
        name_to_id[entity.name.lower()] = comp_id

        await _merge_node(
            comp_id,
            ["Component"] if brain_type == "Component" else [brain_type],
            {
                "module_id": module_id,
                "repo_id": repo_id,
                "name": entity.name,
                "type": kind,
                "kind": kind,
                "label": entity.name,
                "summary": entity.summary or "",
                "file_path": entity.file_path or "",
                "entity_id": str(entity.id),
                "orbit_level": _orbit_level(kind),
            },
        )
        await _merge_rel(module_node_id, comp_id, "HAS_COMPONENT")

        extraction = extraction_by_name.get(entity.name.lower())
        if not extraction:
            continue

        await _write_files_and_functions(module_id, repo_id, comp_id, entity, extraction, name_to_id)
        await _write_field_nodes(module_id, repo_id, comp_id, extraction, name_to_id)

    for extraction in extractions:
        source_id = name_to_id.get(extraction.name.lower())
        if not source_id:
            continue
        for rel in extraction.relationships:
            rel_type = rel.get("type", "CONTAINS")
            target_name = rel.get("target", "")
            if not target_name:
                continue
            target_id = name_to_id.get(target_name.lower()) or _node_id(
                "ref", module_id, target_name
            )
            if target_id not in name_to_id.values():
                await _merge_node(
                    target_id,
                    ["Component"],
                    {
                        "module_id": module_id,
                        "name": target_name,
                        "type": "Reference",
                        "label": target_name,
                        "orbit_level": 3,
                    },
                )
            brain_rel = _map_relationship(rel_type)
            await _merge_rel(source_id, target_id, brain_rel)

    if enrichment:
        await _write_enrichment_nodes(module_id, repo_id, module_node_id, enrichment, name_to_id)


def _map_relationship(rel_type: str) -> str:
    mapping = {
        "CALLS": "CALLS",
        "USES": "USES",
        "READS": "QUERIES",
        "WRITES": "UPDATES",
        "REFERENCES": "TOUCHES",
        "RENDERS": "TOUCHES",
        "BELONGS_TO": "DEFINES",
        "QUERIES": "QUERIES",
        "UPDATES": "UPDATES",
        "CONTROLS": "CONTROLS",
        "IMPLEMENTED_BY": "IMPLEMENTED_BY",
        "EXECUTES": "EXECUTES",
        "CAUSED_BY": "CAUSED_BY",
    }
    return mapping.get(rel_type, rel_type if rel_type in BRAIN_RELATIONSHIPS else "CONTAINS")


async def _write_files_and_functions(
    module_id: str,
    repo_id: str,
    comp_id: str,
    entity: KnowledgeEntity,
    extraction: ExtractionResult,
    name_to_id: dict[str, str],
) -> None:
    files = extraction.data.get("files", [])
    if not files and entity.file_path:
        files = [{"path": entity.file_path, "language": _guess_lang(entity.entity_type)}]

    for f in files:
        fpath = f.get("path", entity.file_path)
        file_id = _node_id("file", module_id, fpath.replace("/", "_"))
        await _merge_node(
            file_id,
            ["File"],
            {
                "module_id": module_id,
                "repo_id": repo_id,
                "name": fpath.split("/")[-1],
                "path": fpath,
                "language": f.get("language", ""),
                "type": "File",
                "label": fpath.split("/")[-1],
                "orbit_level": 2,
            },
        )
        await _merge_rel(comp_id, file_id, "HAS_FILE")

    for fn in extraction.data.get("functions", []):
        fn_name = fn.get("name", "")
        if not fn_name:
            continue
        fn_id = _node_id("fn", module_id, entity.name, fn_name)
        name_to_id[f"{entity.name}.{fn_name}".lower()] = fn_id
        await _merge_node(
            fn_id,
            ["Function"],
            {
                "module_id": module_id,
                "repo_id": repo_id,
                "name": fn_name,
                "type": "Function",
                "label": fn_name,
                "signature": fn.get("signature", ""),
                "line_start": fn.get("line_start"),
                "line_end": fn.get("line_end"),
                "decorators": fn.get("decorators", []),
                "file_path": fn.get("file_path", entity.file_path),
                "orbit_level": 3,
            },
        )
        file_path = fn.get("file_path", entity.file_path)
        file_id = _node_id("file", module_id, (file_path or "").replace("/", "_"))
        await _merge_rel(file_id, fn_id, "DEFINES")
        await _merge_rel(comp_id, fn_id, "DEFINES")

        for field in fn.get("queries_fields", []):
            field_id = name_to_id.get(field.lower()) or _node_id("field", module_id, field)
            if field_id not in name_to_id.values():
                await _merge_node(
                    field_id,
                    ["Field"],
                    {
                        "module_id": module_id,
                        "name": field,
                        "type": "Field",
                        "label": field,
                        "orbit_level": 4,
                    },
                )
                name_to_id[field.lower()] = field_id
            await _merge_rel(fn_id, field_id, "QUERIES")

        for field in fn.get("updates_fields", []):
            field_id = name_to_id.get(field.lower()) or _node_id("field", module_id, field)
            if field_id not in name_to_id.values():
                await _merge_node(
                    field_id,
                    ["Field"],
                    {
                        "module_id": module_id,
                        "name": field,
                        "type": "Field",
                        "label": field,
                        "orbit_level": 4,
                    },
                )
                name_to_id[field.lower()] = field_id
            await _merge_rel(fn_id, field_id, "UPDATES")


async def _write_field_nodes(
    module_id: str,
    repo_id: str,
    comp_id: str,
    extraction: ExtractionResult,
    name_to_id: dict[str, str],
) -> None:
    for field in extraction.data.get("fields", []):
        field_name = field if isinstance(field, str) else field.get("name", "")
        if not field_name:
            continue
        field_id = name_to_id.get(field_name.lower()) or _node_id("field", module_id, field_name)
        if field_id not in name_to_id.values():
            await _merge_node(
                field_id,
                ["Field"],
                {
                    "module_id": module_id,
                    "repo_id": repo_id,
                    "name": field_name,
                    "type": "Field",
                    "label": field_name,
                    "orbit_level": 4,
                },
            )
            name_to_id[field_name.lower()] = field_id
        await _merge_rel(comp_id, field_id, "TOUCHES")


async def _write_enrichment_nodes(
    module_id: str,
    repo_id: str,
    module_node_id: str,
    enrichment: dict,
    name_to_id: dict[str, str],
) -> None:
    for logic in enrichment.get("business_logic", []):
        logic_id = _node_id("logic", module_id, logic.get("name", "logic")[:40])
        await _merge_node(
            logic_id,
            ["BusinessLogic"],
            {
                "module_id": module_id,
                "repo_id": repo_id,
                "name": logic.get("name", ""),
                "type": "BusinessLogic",
                "label": logic.get("name", ""),
                "description": logic.get("description", ""),
                "rules": logic.get("rules", []),
                "source_files": logic.get("source_files", []),
                "orbit_level": 4,
            },
        )
        for comp in logic.get("components", []):
            comp_id = name_to_id.get(comp.lower())
            if comp_id:
                await _merge_rel(logic_id, comp_id, "CONTROLS")
        for fn in logic.get("functions", []):
            fn_id = name_to_id.get(fn.lower())
            if fn_id:
                await _merge_rel(logic_id, fn_id, "IMPLEMENTED_BY")

    for scenario in enrichment.get("scenarios", []):
        scen_id = _node_id("scen", module_id, scenario.get("name", "scenario")[:40])
        await _merge_node(
            scen_id,
            ["Scenario"],
            {
                "module_id": module_id,
                "repo_id": repo_id,
                "name": scenario.get("name", ""),
                "type": "Scenario",
                "label": scenario.get("name", ""),
                "steps": scenario.get("steps", []),
                "expected": scenario.get("expected", ""),
                "orbit_level": 5,
            },
        )
        await _merge_rel(module_node_id, scen_id, "CONTAINS")
        for logic_name in scenario.get("business_logic", []):
            logic_id = _node_id("logic", module_id, logic_name[:40])
            await _merge_rel(scen_id, logic_id, "EXECUTES")

    for defect in enrichment.get("defects", []):
        defect_id = _node_id("defect", module_id, defect.get("ticket", defect.get("name", "defect")))
        await _merge_node(
            defect_id,
            ["Defect"],
            {
                "module_id": module_id,
                "repo_id": repo_id,
                "name": defect.get("name", defect.get("ticket", "")),
                "type": "Defect",
                "label": defect.get("ticket", defect.get("name", "")),
                "ticket": defect.get("ticket", ""),
                "summary": defect.get("summary", ""),
                "orbit_level": 5,
            },
        )


def _guess_lang(entity_type: str) -> str:
    return {
        "ApexClass": "apex",
        "ApexTrigger": "apex",
        "LwcComponent": "javascript",
        "Flow": "xml",
    }.get(entity_type, "")


async def get_repo_brain_graph(repo_id: UUID) -> dict:
    rid = str(repo_id)
    node_records = await neo4j_client.run_query(
        """
        MATCH (n:KeNode)
        WHERE n.repo_id = $repo_id OR n.id STARTS WITH 'repo:' + $repo_id
        RETURN n.id as id, n.label as label, n.type as type, n.name as name,
               n.summary as summary, n.file_path as file_path, n.entity_id as entity_id,
               n.orbit_level as orbit_level, n.line_start as line_start
        """,
        {"repo_id": rid},
    )
    edge_records = await neo4j_client.run_query(
        """
        MATCH (a:KeNode)-[r]->(b:KeNode)
        WHERE a.repo_id = $repo_id OR b.repo_id = $repo_id
           OR a.module_id IS NOT NULL
        RETURN a.id as source, b.id as target, type(r) as relationship
        LIMIT 2000
        """,
        {"repo_id": rid},
    )
    nodes = [
        {
            "id": r["id"],
            "label": r.get("label") or r.get("name"),
            "type": r.get("type"),
            "name": r.get("name"),
            "summary": r.get("summary"),
            "file_path": r.get("file_path"),
            "entity_id": r.get("entity_id"),
            "orbit_level": r.get("orbit_level", 3),
            "line_start": r.get("line_start"),
        }
        for r in node_records
    ]
    edges = [
        {
            "id": f"{e['source']}-{e['relationship']}-{e['target']}",
            "source": e["source"],
            "target": e["target"],
            "relationship": e["relationship"],
        }
        for e in edge_records
        if e.get("source") and e.get("target")
    ]
    return {"nodes": nodes, "edges": edges}


async def get_brain_node_detail(node_id: str) -> dict | None:
    records = await neo4j_client.run_query(
        """
        MATCH (n:KeNode {id: $node_id})
        OPTIONAL MATCH (n)-[r]-(m:KeNode)
        RETURN n, collect(DISTINCT {rel: type(r), direction: CASE WHEN startNode(r)=n
               THEN 'out' ELSE 'in' END, node: m.name, node_type: m.type, node_id: m.id,
               file_path: m.file_path, line_start: m.line_start}) as neighbors
        """,
        {"node_id": node_id},
    )
    if not records:
        return None
    rec = records[0]
    node = rec.get("n")
    if not node:
        return None
    props = dict(node)
    return {
        "id": props.get("id"),
        "name": props.get("name"),
        "type": props.get("type"),
        "label": props.get("label"),
        "summary": props.get("summary"),
        "description": props.get("description"),
        "file_path": props.get("file_path"),
        "line_start": props.get("line_start"),
        "line_end": props.get("line_end"),
        "orbit_level": props.get("orbit_level"),
        "steps": props.get("steps"),
        "rules": props.get("rules"),
        "neighbors": [n for n in (rec.get("neighbors") or []) if n.get("node")],
    }


async def get_brain_path(source_id: str, target_id: str) -> list[dict]:
    records = await neo4j_client.run_query(
        """
        MATCH path = shortestPath((a:KeNode {id: $source})-[*..8]-(b:KeNode {id: $target}))
        RETURN [n IN nodes(path) | {id: n.id, name: n.name, type: n.type}] as path
        """,
        {"source": source_id, "target": target_id},
    )
    if records and records[0].get("path"):
        return records[0]["path"]
    return []


def _serialize_graph(records: list) -> dict:
    nodes_map: dict[str, dict] = {}
    edges: list[dict] = []
    for record in records or []:
        for node in record.get("nodes") or []:
            if node:
                nid = node.get("id")
                if nid and nid not in nodes_map:
                    nodes_map[nid] = {
                        "id": nid,
                        "label": node.get("label") or node.get("name"),
                        "type": node.get("type"),
                        "name": node.get("name"),
                        "summary": node.get("summary"),
                        "file_path": node.get("file_path"),
                        "entity_id": node.get("entity_id"),
                        "orbit_level": node.get("orbit_level", 3),
                        "line_start": node.get("line_start"),
                    }
        for edge in record.get("edges") or []:
            if edge and edge.get("source"):
                edges.append(
                    {
                        "id": f"{edge['source']}-{edge['relationship']}-{edge['target']}",
                        "source": edge["source"],
                        "target": edge["target"],
                        "relationship": edge["relationship"],
                    }
                )
    if not edges and nodes_map:
        # fallback edge query
        pass
    return {"nodes": list(nodes_map.values()), "edges": edges}
