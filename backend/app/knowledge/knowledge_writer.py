import logging
from uuid import UUID

from app.knowledge.graph_schema import FIELDS, SECTIONS
from app.knowledge.neo4j_client import Neo4jClient
from app.schemas.agent import ExecutionReport, PlannedStep, StepResult

logger = logging.getLogger(__name__)

ACTION_SECTION_MAP = {
    "login": "login",
    "open_queues": "customer_lifecycle",
    "create_data_change_request": "customer_lifecycle",
    "search_select_customer": "data_change",
    "open_customer_details": "data_change",
    "modify_primary_group": "data_change",
    "submit": "data_change",
    "click_new_button": "customer_lifecycle",
    "select_request_module": "customer_lifecycle",
    "open_customer_search": "data_change",
    "validate_expected": "validation",
    "set_field": "data_change",
    "wait_for_customer_dropdown": "data_change",
    "select_first_customer": "data_change",
    "open_app_launcher": "app_launcher",
    "open_app": "onboarding",
    "open_tab": "customer_lifecycle",
    "click_new": "customer_lifecycle",
    "select_module": "data_change",
    "select_sales_office": "data_change",
    "enter_customer_number": "data_change",
    "search": "data_change",
    "wait_for_data": "data_change",
    "save_draft": "data_change",
}

ACTION_FIELD_MAP = {
    "modify_primary_group": "primary_group",
    "search_select_customer": "customer_number",
    "select_module": "module_selection",
    "select_sales_office": "sales_office",
    "enter_customer_number": "customer_number",
}


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
            MERGE (s:Scenario {id: $scenario_id})
            SET s.name = $scenario_name
            MERGE (e:Execution {id: $execution_id})
            SET e.status = $status, e.passed_count = $passed_count, e.failed_count = $failed_count
            MERGE (s)-[:EXECUTED]->(e)
            MERGE (r:Result {id: $result_id})
            SET r.passed = $passed, r.summary = $summary
            MERGE (e)-[:PRODUCED]->(r)
            """,
            {
                "scenario_id": str(scenario_id),
                "scenario_name": scenario_name,
                "execution_id": str(execution_id),
                "result_id": f"{execution_id}-result",
                "status": "passed" if report.passed else "failed",
                "passed_count": report.passed_count,
                "failed_count": report.failed_count,
                "passed": report.passed,
                "summary": report.summary[:2000],
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
