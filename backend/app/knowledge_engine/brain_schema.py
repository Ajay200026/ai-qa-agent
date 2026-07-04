"""Neo4j schema for the Code Brain graph (typed labels + KeNode base)."""

BRAIN_CONSTRAINTS = [
    "CREATE CONSTRAINT ke_node_id IF NOT EXISTS FOR (n:KeNode) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT brain_repo_id IF NOT EXISTS FOR (n:Repository) REQUIRE n.id IS UNIQUE",
]

BRAIN_NODE_TYPES = {
    "Repository",
    "Module",
    "Component",
    "File",
    "Function",
    "Field",
    "BusinessLogic",
    "Scenario",
    "Defect",
    "VisionMemory",
}

BRAIN_RELATIONSHIPS = {
    "HAS_MODULE",
    "HAS_COMPONENT",
    "HAS_FILE",
    "DEFINES",
    "CALLS",
    "QUERIES",
    "UPDATES",
    "CONTROLS",
    "IMPLEMENTED_BY",
    "EXECUTES",
    "TOUCHES",
    "CAUSED_BY",
    "AFFECTS",
    "VALIDATED",
    "FAILED_ON",
    "CONTAINS",
    "READS",
    "WRITES",
    "USES",
    "REFERENCES",
    "RENDERS",
}

# Orbit level for 3D globe layout
ORBIT_LEVELS: dict[str, int] = {
    "Repository": 0,
    "Module": 1,
    "Component": 2,
    "File": 2,
    "ApexClass": 3,
    "LwcComponent": 3,
    "Flow": 3,
    "Function": 3,
    "BusinessLogic": 4,
    "Field": 4,
    "Scenario": 5,
    "Defect": 5,
    "VisionMemory": 5,
}
