"""Extract structured knowledge from Salesforce Flow metadata."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from app.knowledge_engine.types import ExtractionResult

NS = {"sf": "http://soap.sforce.com/2006/04/metadata"}


def _local(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def _text(elem: ET.Element | None) -> str | None:
    return elem.text.strip() if elem is not None and elem.text else None


def extract_flow(source: str, file_path: str) -> list[ExtractionResult]:
    try:
        root = ET.fromstring(source)
    except ET.ParseError:
        return []

    from pathlib import Path

    name = Path(file_path).stem.replace(".flow-meta", "")
    label = _text(root.find("sf:label", NS)) or name
    process_type = _text(root.find("sf:processType", NS))
    trigger_object = None
    start = root.find("sf:start", NS)
    if start is not None:
        obj_elem = start.find("sf:object", NS)
        trigger_object = _text(obj_elem)

    decisions = []
    record_updates = []
    apex_actions = []

    for elem in root.iter():
        tag = _local(elem.tag)
        if tag == "decisions":
            decision_name = _text(elem.find("sf:name", NS))
            if decision_name:
                decisions.append(decision_name)
        elif tag in {"recordUpdates", "recordCreates", "recordDeletes"}:
            obj = _text(elem.find("sf:object", NS))
            if obj:
                record_updates.append({"operation": tag, "object": obj})
        elif tag == "actionName":
            action = _text(elem)
            if action and "." in (action or ""):
                apex_actions.append(action)

    references = set()
    if trigger_object:
        references.add(trigger_object)
    for upd in record_updates:
        references.add(upd["object"])
    for action in apex_actions:
        references.add(action.split(".")[0])

    relationships = []
    for upd in record_updates:
        relationships.append({"type": "WRITES", "source": name, "target": upd["object"]})
    for action in apex_actions:
        class_name = action.split(".")[0]
        relationships.append({"type": "CALLS", "source": name, "target": class_name})
    if trigger_object:
        relationships.append({"type": "TRIGGERS", "source": name, "target": trigger_object})

    return [
        ExtractionResult(
            entity_type="Flow",
            name=name,
            file_path=file_path,
            data={
                "label": label,
                "process_type": process_type,
                "trigger_object": trigger_object,
                "decisions": decisions,
                "record_updates": record_updates,
                "apex_actions": apex_actions,
            },
            references=list(references),
            relationships=relationships,
        )
    ]
