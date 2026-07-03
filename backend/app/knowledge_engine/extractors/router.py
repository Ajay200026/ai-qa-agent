"""Route scanned files to the appropriate extractor."""

from pathlib import Path

from app.knowledge_engine.extractors.apex_extractor import extract_apex
from app.knowledge_engine.extractors.flow_extractor import extract_flow
from app.knowledge_engine.extractors.lwc_extractor import extract_lwc
from app.knowledge_engine.extractors.metadata_extractor import extract_metadata
from app.knowledge_engine.types import ExtractionResult, SalesforceFileType, ScannedFile


def extract_file(scanned: ScannedFile) -> list[ExtractionResult]:
    path = scanned.path
    rel = scanned.relative_path

    if scanned.file_type == SalesforceFileType.APEX_CLASS:
        return [extract_apex(path.read_text(encoding="utf-8", errors="replace"), rel)]
    if scanned.file_type == SalesforceFileType.APEX_TRIGGER:
        result = extract_apex(path.read_text(encoding="utf-8", errors="replace"), rel)
        result.entity_type = "ApexTrigger"
        return [result]
    if scanned.file_type == SalesforceFileType.LWC:
        if path.suffix == ".html":
            return extract_lwc(path.parent, rel)
        return []
    if scanned.file_type in {
        SalesforceFileType.OBJECT,
        SalesforceFileType.FIELD,
        SalesforceFileType.VALIDATION_RULE,
        SalesforceFileType.LAYOUT,
        SalesforceFileType.PERMISSION_SET,
        SalesforceFileType.LABEL,
        SalesforceFileType.CUSTOM_METADATA,
    }:
        return extract_metadata(
            path.read_text(encoding="utf-8", errors="replace"),
            rel,
            scanned.file_type,
        )
    if scanned.file_type == SalesforceFileType.FLOW:
        return extract_flow(path.read_text(encoding="utf-8", errors="replace"), rel)
    return []


def collect_references(results: list[ExtractionResult]) -> set[str]:
    refs: set[str] = set()
    for result in results:
        refs.update(result.references)
        for rel in result.relationships:
            target = rel.get("target")
            if target:
                refs.add(target)
    return refs
