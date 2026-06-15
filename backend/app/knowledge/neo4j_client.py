import logging
from typing import Any

from neo4j import AsyncGraphDatabase, AsyncDriver

from app.core.config import get_settings
from app.knowledge.graph_schema import CONSTRAINTS

logger = logging.getLogger(__name__)


class Neo4jClient:
    def __init__(self) -> None:
        self._driver: AsyncDriver | None = None
        self.settings = get_settings()

    async def connect(self) -> None:
        if self._driver is None:
            self._driver = AsyncGraphDatabase.driver(
                self.settings.neo4j_uri,
                auth=(self.settings.neo4j_user, self.settings.neo4j_password),
            )
            await self.init_schema()
            logger.info("Neo4j connected")

    async def close(self) -> None:
        if self._driver:
            await self._driver.close()
            self._driver = None
            logger.info("Neo4j disconnected")

    async def init_schema(self) -> None:
        assert self._driver is not None
        async with self._driver.session() as session:
            for constraint in CONSTRAINTS:
                try:
                    await session.run(constraint)
                except Exception as exc:
                    logger.debug("Constraint may already exist: %s", exc)

    async def run_query(self, query: str, parameters: dict[str, Any] | None = None) -> list[dict]:
        if not self._driver:
            await self.connect()
        assert self._driver is not None
        async with self._driver.session() as session:
            result = await session.run(query, parameters or {})
            records = await result.data()
            return records

    async def get_scenario_graph(self, scenario_id: str) -> dict:
        query = """
        MATCH (s:Scenario {id: $scenario_id})-[:EXECUTED]->(e:Execution)-[:PRODUCED]->(r:Result)
        OPTIONAL MATCH (e)-[:NAVIGATED]->(a:AppSection)
        OPTIONAL MATCH (e)-[:INTERACTED_WITH]->(f:Field)
        RETURN s, collect(DISTINCT e) as executions, collect(DISTINCT r) as results,
               collect(DISTINCT a) as sections, collect(DISTINCT f) as fields
        """
        records = await self.run_query(query, {"scenario_id": scenario_id})
        if not records:
            return {"nodes": [], "relationships": []}
        return records[0]


neo4j_client = Neo4jClient()
