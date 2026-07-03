"""Extract structured knowledge from Salesforce metadata XML."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from app.knowledge_engine.types import ExtractionResult, SalesforceFileType

NS = {"sf": "http://soap.sforce.com/2006/04/metadata"}


def _local(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def _text(elem: ET.Element | None) -> str | None:
    return elem.text.strip() if elem is not None and elem.text else None


def extract_metadata(
    source: str, file_path: str, file_type: SalesforceFileType
) -> list[ExtractionResult]:
    try:
        root = ET.fromstring(source)
    except ET.ParseError:
        return []

    if file_type == SalesforceFileType.OBJECT:
        return [_extract_object(root, file_path)]
    if file_type == SalesforceFileType.FIELD:
        return [_extract_field(root, file_path)]
    if file_type == SalesforceFileType.VALIDATION_RULE:
        return [_extract_validation_rule(root, file_path)]
    if file_type == SalesforceFileType.LAYOUT:
        return [_extract_layout(root, file_path)]
    if file_type == SalesforceFileType.PERMISSION_SET:
        return [_extract_permission_set(root, file_path)]
    if file_type == SalesforceFileType.FLOW:
        return []
    return [_extract_generic_metadata(root, file_path, file_type)]


def _extract_object(root: ET.Element, file_path: str) -> ExtractionResult:
    label = _text(root.find("sf:label", NS)) or _text(root.find("label"))
    name = PathStem(file_path).replace(".object-meta", "")
    fields = [
        _local(child.tag)
        for child in root
        if _local(child.tag) not in {"label", "pluralLabel", "nameField"}
    ]
    return ExtractionResult(
        entity_type="SObject",
        name=name,
        file_path=file_path,
        data={"label": label, "child_elements": fields[:20]},
        references=[],
        relationships=[{"type": "BELONGS_TO", "source": name, "target": name}],
    )


def _extract_field(root: ET.Element, file_path: str) -> ExtractionResult:
    full_name = _text(root.find("sf:fullName", NS)) or _text(root.find("fullName"))
    field_type = _text(root.find("sf:type", NS)) or _text(root.find("type"))
    label = _text(root.find("sf:label", NS)) or _text(root.find("label"))
    picklist_values = []
    for pv in root.iter():
        if _local(pv.tag) == "fullName" and pv != root.find("sf:fullName", NS):
            if pv.text and pv.text not in {full_name}:
                picklist_values.append(pv.text.strip())

    obj_name = Path(file_path).parent.parent.name if "/fields/" in file_path else "Unknown"
    field_name = full_name or PathStem(file_path).split(".")[0]

    return ExtractionResult(
        entity_type="Field",
        name=field_name or "Unknown",
        file_path=file_path,
        data={
            "label": label,
            "type": field_type,
            "picklist_values": picklist_values[:50],
            "object": obj_name,
        },
        references=[obj_name] if obj_name != "Unknown" else [],
        relationships=[
            {"type": "BELONGS_TO", "source": field_name or "", "target": obj_name},
        ],
    )


def _extract_validation_rule(root: ET.Element, file_path: str) -> ExtractionResult:
    full_name = _text(root.find("sf:fullName", NS)) or PathStem(file_path)
    formula = _text(root.find("sf:errorConditionFormula", NS))
    message = _text(root.find("sf:errorMessage", NS))
    active = _text(root.find("sf:active", NS))
    return ExtractionResult(
        entity_type="ValidationRule",
        name=full_name or "Unknown",
        file_path=file_path,
        data={"formula": formula, "error_message": message, "active": active},
        references=_formula_refs(formula or ""),
        relationships=[],
    )


def _extract_layout(root: ET.Element, file_path: str) -> ExtractionResult:
    name = PathStem(file_path)
    fields_on_layout = []
    for elem in root.iter():
        if _local(elem.tag) == "field" and elem.text:
            fields_on_layout.append(elem.text.strip())
    return ExtractionResult(
        entity_type="Layout",
        name=name,
        file_path=file_path,
        data={"fields": fields_on_layout[:100]},
        references=fields_on_layout,
        relationships=[],
    )


def _extract_permission_set(root: ET.Element, file_path: str) -> ExtractionResult:
    label = _text(root.find("sf:label", NS))
    name = PathStem(file_path)
    object_perms = []
    for elem in root.iter():
        if _local(elem.tag) == "object":
            obj = _text(elem.find("sf:object", NS)) or _text(elem.find("object"))
            if obj:
                object_perms.append(obj)
    return ExtractionResult(
        entity_type="PermissionSet",
        name=name,
        file_path=file_path,
        data={"label": label, "objects": object_perms},
        references=object_perms,
        relationships=[],
    )


def _extract_generic_metadata(
    root: ET.Element, file_path: str, file_type: SalesforceFileType
) -> ExtractionResult:
    name = PathStem(file_path)
    return ExtractionResult(
        entity_type="Metadata",
        name=name,
        file_path=file_path,
        data={"metadata_type": file_type.value},
        references=[],
        relationships=[],
    )


def _formula_refs(formula: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"\b([A-Za-z_]\w*__c)\b", formula)))


def PathStem(file_path: str) -> str:
    from pathlib import Path

    return Path(file_path).name.replace("-meta.xml", "").replace(".xml", "")


def Path(file_path: str):
    from pathlib import Path as P

    return P(file_path)
