from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class KnowledgeRepoCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    source_type: Literal["azure", "local"] = "azure"
    path: str | None = None
    connection_id: UUID | None = None
    azure_project: str | None = None
    azure_repo: str | None = None
    azure_repo_id: str | None = None
    branch: str | None = None

    @model_validator(mode="after")
    def validate_source(self) -> "KnowledgeRepoCreate":
        if self.source_type == "azure":
            if not self.connection_id or not self.azure_project or not self.azure_repo:
                raise ValueError(
                    "Azure repos require connection_id, azure_project, and azure_repo"
                )
            if not self.branch:
                raise ValueError("branch is required for Azure repos")
        elif not self.path:
            raise ValueError("path is required for local repos")
        return self


class KnowledgeRepoResponse(BaseModel):
    id: UUID
    name: str
    path: str
    source_type: str
    azure_connection_id: UUID | None
    azure_project: str | None
    azure_repo: str | None
    azure_repo_id: str | None
    branch: str | None
    last_synced_commit: str | None
    owner_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class KnowledgeModuleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    scope_path: str | None = None


class KnowledgeModuleResponse(BaseModel):
    id: UUID
    repo_id: UUID
    name: str
    scope_path: str | None
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
    orbit_level: int | None = None
    line_start: int | None = None


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
    scope_path: str | None = None


class ValidateScopeResponse(BaseModel):
    valid: bool
    normalized_path: str | None = None
    file_count: int = 0
    breakdown: dict[str, int] = Field(default_factory=dict)
    suggestion: str | None = None
    message: str | None = None


class RepoFolderEntry(BaseModel):
    name: str
    path: str
    file_count: int
    breakdown: dict[str, int]
    is_selectable: bool = False
    is_current: bool = False


class UploadedFileInfo(BaseModel):
    path: str
    type: str
    size: int


class FolderUploadBatchResponse(BaseModel):
    session_id: str
    repo_id: UUID
    files_received: int
    bytes_received: int


class FolderUploadResponse(KnowledgeRepoResponse):
    success: bool = True
    projectName: str
    totalFiles: int
    uploadedFiles: list[UploadedFileInfo] = Field(default_factory=list)


class RepoFileEntry(BaseModel):
    name: str
    path: str
    is_directory: bool
    size: int | None = None


class FileContentResponse(BaseModel):
    path: str
    content: str
    language: str
    size: int
    truncated: bool = False
