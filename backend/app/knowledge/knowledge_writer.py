import logging
from uuid import UUID

from app.knowledge.action_registry import ACTION_FIELD_MAP, ACTION_SECTION_MAP, resolve_field_for_action
from app.knowledge.graph_schema import FIELDS, SECTIONS
from app.knowledge.neo4j_client import Neo4jClient
from app.schemas.agent import ExecutionReport, PlannedStep, StepResult

logger = logging.getLogger(__name__)


class KnowledgeWriter:
    def __init__(self, client: Neo4jClient):
        self.client = client

    async def ensure_base_graph(self) -> None:
        for section in SECTIONS:
            await self.client.run_query(
                "MERGE (a:AppSection {id: $id}) SET a.name = $name, a.app = $app",
                section,
            )
        for field in FIELDS:
            await self.client.run_query(
                """
                MERGE (f:Field {id: $id}) SET f.name = $name
                WITH f
                MATCH (a:AppSection {id: $section})
                MERGE (a)-[:CONTAINS]->(f)
                """,
                field,
            )

    async def store_execution(
        self,
        scenario_id: UUID,
        scenario_name: str,
        execution_id: UUID,
        report: ExecutionReport,
        planned_steps: list[PlannedStep],
        step_results: list[StepResult],
    ) -> None:
        await self.ensure_base_graph()

        await self.client.run_query(
            """
            MERGE (s:KeNode:Scenario {id: $brain_scenario_id})
            SET s.scenario_id = $scenario_id, s.name = $scenario_name, s.type = 'Scenario',
                s.label = $scenario_name, s.expected = $expected, s.actual = $actual,
                s.orbit_level = 5
            MERGE (s2:Scenario {id: $scenario_id})
            SET s2.name = $scenario_name
            MERGE (e:Execution {id: $execution_id})
            SET e.status = $status, e.passed_count = $passed_count, e.failed_count = $failed_count
            MERGE (s2)-[:EXECUTED]->(e)
            MERGE (e)-[:VALIDATED]->(s)
            MERGE (r:Result {id: $result_id})
            SET r.passed = $passed, r.summary = $summary
            MERGE (e)-[:PRODUCED]->(r)
            """,
            {
                "brain_scenario_id": f"brain-scenario:{scenario_id}",
                "scenario_id": str(scenario_id),
                "scenario_name": scenario_name,
                "execution_id": str(execution_id),
                "result_id": f"{execution_id}-result",
                "status": "passed" if report.passed else "failed",
                "passed_count": report.passed_count,
                "failed_count": report.failed_count,
                "passed": report.passed,
                "summary": report.summary[:2000],
                "expected": report.summary[:500],
                "actual": "passed" if report.passed else "failed",
            },
        )

        for step_result in step_results:
            if step_result.status == "passed":
                continue
            defect_id = f"defect:{execution_id}:{step_result.seq}"
            await self.client.run_query(
                """
                MERGE (d:KeNode:Defect {id: $defect_id})
                SET d.type = 'Defect', d.name = $name, d.label = $name,
                    d.summary = $error, d.ticket = $ticket, d.orbit_level = 5
                WITH d
                MATCH (s:KeNode {id: $scenario_brain_id})
                MERGE (d)-[:AFFECTS]->(s)
                """,
                {
                    "defect_id": defect_id,
                    "name": f"Step {step_result.seq} failure",
                    "error": (step_result.error or "")[:1000],
                    "ticket": defect_id,
                    "scenario_brain_id": f"brain-scenario:{scenario_id}",
                },
            )
            field_name = resolve_field_for_action(step_result.action, step_result.params if hasattr(step_result, "params") else None)
            if field_name:
                await self.client.run_query(
                    """
                    MATCH (d:KeNode {id: $defect_id})
                    MATCH (f:KeNode)
                    WHERE f.type = 'Field' AND toLower(f.name) CONTAINS toLower($field)
                    MERGE (e:Execution {id: $execution_id})
                    MERGE (e)-[:FAILED_ON]->(f)
                    MERGE (d)-[:CAUSED_BY]->(f)
                    LIMIT 1
                    """,
                    {
                        "defect_id": defect_id,
                        "field": field_name,
                        "execution_id": str(execution_id),
                    },
                )

        navigated_sections: set[str] = set()
        for step in planned_steps:
            section_id = ACTION_SECTION_MAP.get(step.action)
            if section_id and section_id not in navigated_sections:
                navigated_sections.add(section_id)
                await self.client.run_query(
                    """
                    MATCH (e:Execution {id: $execution_id})
                    MATCH (a:AppSection {id: $section_id})
                    MERGE (e)-[:NAVIGATED]->(a)
                    """,
                    {"execution_id": str(execution_id), "section_id": section_id},
                )

            field_id = ACTION_FIELD_MAP.get(step.action)
            if field_id:
                await self.client.run_query(
                    """
                    MATCH (e:Execution {id: $execution_id})
                    MATCH (f:Field {id: $field_id})
                    MERGE (e)-[:INTERACTED_WITH]->(f)
                    """,
                    {"execution_id": str(execution_id), "field_id": field_id},
                )

        logger.info("Stored execution knowledge for %s", execution_id)
