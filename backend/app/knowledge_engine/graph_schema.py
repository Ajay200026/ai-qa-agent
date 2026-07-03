"""Neo4j schema constraints for the application knowledge graph."""

KNOWLEDGE_CONSTRAINTS = [
    "CREATE CONSTRAINT ke_node_id IF NOT EXISTS FOR (n:KeNode) REQUIRE n.id IS UNIQUE",
]
