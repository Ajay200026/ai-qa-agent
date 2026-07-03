from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class KnowledgeRepoCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    path: str = Field(..., min_length=1)


class KnowledgeRepoResponse(BaseModel):
    id: UUID
    name: str
    path: str
    owner_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class KnowledgeModuleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class KnowledgeModuleResponse(BaseModel):
    id: UUID
    repo_id: UUID
    name: str
    scan_status: str
    scan_error: str | None
    stats: dict | None
    scanned_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ModuleStatusResponse(BaseModel):
    module_id: UUID
    scan_status: str
    scan_error: str | None
    stats: dict | None
    graph_status: str
    vector_status: str
    ai_status: str


class GraphNode(BaseModel):
    id: str
    label: str
    type: str
    name: str
    summary: str | None = None
    file_path: str | None = None
    entity_id: str | None = None


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    relationship: str


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class EntityDetailResponse(BaseModel):
    id: UUID
    entity_type: str
    name: str
    file_path: str | None
    summary: str | None
    extracted: dict | None
    business_rules: list | None
    dependencies: list[GraphNode]
    related_files: list[str]
    navigation_path: list[str]


class AskRequest(BaseModel):
    module_id: UUID
    question: str = Field(..., min_length=1)


class AskCitation(BaseModel):
    entity_id: str | None = None
    name: str
    entity_type: str
    file_path: str | None = None


class AskResponse(BaseModel):
    answer: str
    citations: list[AskCitation]


class DiscoveredModule(BaseModel):
    name: str
    file_count: int
