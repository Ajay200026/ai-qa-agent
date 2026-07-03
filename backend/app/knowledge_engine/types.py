from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class SalesforceFileType(str, Enum):
    APEX_CLASS = "apex_class"
    APEX_TRIGGER = "apex_trigger"
    LWC = "lwc"
    OBJECT = "object"
    FIELD = "field"
    FLOW = "flow"
    VALIDATION_RULE = "validation_rule"
    LAYOUT = "layout"
    PERMISSION_SET = "permission_set"
    LABEL = "label"
    CUSTOM_METADATA = "custom_metadata"
    OTHER = "other"


@dataclass
class ScannedFile:
    path: Path
    relative_path: str
    file_type: SalesforceFileType
    module_hint: str | None = None


@dataclass
class ExtractionResult:
    entity_type: str
    name: str
    file_path: str
    data: dict = field(default_factory=dict)
    references: list[str] = field(default_factory=list)
    relationships: list[dict] = field(default_factory=list)
