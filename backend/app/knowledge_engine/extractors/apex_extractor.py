"""Extract structured knowledge from Apex classes and triggers."""

from __future__ import annotations

import re

from app.knowledge_engine.types import ExtractionResult

METHOD_PATTERN = re.compile(
    r"(?:@\w+(?:\([^)]*\))?\s*)*"
    r"(?:public|private|protected|global)\s+"
    r"(?:static\s+)?(?:virtual\s+)?(?:override\s+)?"
    r"([\w<>,\s\[\]]+?)\s+(\w+)\s*\(([^)]*)\)",
    re.MULTILINE,
)
SOQL_PATTERN = re.compile(
    r"\[SELECT\s+.+?\s+FROM\s+(\w+)(?:\s+WHERE|\s+LIMIT|\s+ORDER|\s+GROUP|\s+FOR|\s*;|\s*\])",
    re.IGNORECASE | re.DOTALL,
)
FIELD_IN_SOQL = re.compile(r"(?:SELECT\s+.+?\s+FROM\s+\w+\s+)?([\w.]+__c|\w+\.\w+)", re.IGNORECASE)
DML_PATTERN = re.compile(r"\b(insert|update|upsert|delete|undelete)\s+(\w+)", re.IGNORECASE)
CLASS_CALL_PATTERN = re.compile(r"\b([A-Z][A-Za-z0-9_]*)\s*\.\s*([a-zA-Z_]\w*)\s*\(")
TYPE_REF_PATTERN = re.compile(r"\b(?:new\s+)?([A-Z][A-Za-z0-9_]*)\s*(?:\(|\[|;)")


def extract_apex(source: str, file_path: str) -> ExtractionResult:
    class_match = re.search(r"\bclass\s+(\w+)", source)
    name = class_match.group(1) if class_match else PathStem(file_path)

    methods = []
    for match in METHOD_PATTERN.finditer(source):
        return_type, method_name, params = match.groups()
        methods.append(
            {
                "name": method_name,
                "return_type": return_type.strip(),
                "parameters": _parse_params(params),
            }
        )

    soql_queries = SOQL_PATTERN.findall(source)
    objects_read = list(dict.fromkeys(soql_queries))
    fields_read = list(
        dict.fromkeys(
            f for f in FIELD_IN_SOQL.findall(source) if "__c" in f or "." in f
        )
    )

    dml_ops = []
    objects_written: list[str] = []
    for op, obj in DML_PATTERN.findall(source):
        dml_ops.append({"operation": op.lower(), "object": obj})
        objects_written.append(obj)
    objects_written = list(dict.fromkeys(objects_written))

    called_classes = list(
        dict.fromkeys(m.group(1) for m in CLASS_CALL_PATTERN.finditer(source))
    )
    type_refs = list(dict.fromkeys(m.group(1) for m in TYPE_REF_PATTERN.finditer(source)))
    dependencies = list(dict.fromkeys(called_classes + type_refs))

    annotations = re.findall(r"@(\w+)", source)
    sharing = re.search(r"\b(with|without)\s+sharing\b", source, re.IGNORECASE)
    sharing_mode = sharing.group(0) if sharing else None

    references = set(objects_read + objects_written + dependencies)

    relationships = []
    for cls in called_classes:
        relationships.append({"type": "CALLS", "source": name, "target": cls})
    for obj in objects_read:
        relationships.append({"type": "READS", "source": name, "target": obj})
    for obj in objects_written:
        relationships.append({"type": "WRITES", "source": name, "target": obj})

    for method in methods:
        relationships.append(
            {
                "type": "BELONGS_TO",
                "source": f"{name}.{method['name']}",
                "target": name,
            }
        )

    return ExtractionResult(
        entity_type="ApexClass",
        name=name,
        file_path=file_path,
        data={
            "methods": methods,
            "soql_objects": objects_read,
            "fields_read": fields_read,
            "dml": dml_ops,
            "objects_written": objects_written,
            "called_classes": called_classes,
            "dependencies": dependencies,
            "annotations": annotations,
            "sharing": sharing_mode,
        },
        references=list(references),
        relationships=relationships,
    )


def _parse_params(params: str) -> list[dict[str, str]]:
    if not params.strip():
        return []
    parts = []
    for part in params.split(","):
        part = part.strip()
        if not part:
            continue
        tokens = part.split()
        if len(tokens) >= 2:
            parts.append({"type": " ".join(tokens[:-1]), "name": tokens[-1]})
        else:
            parts.append({"type": tokens[0], "name": ""})
    return parts


def PathStem(file_path: str) -> str:
    from pathlib import Path

    return Path(file_path).stem
