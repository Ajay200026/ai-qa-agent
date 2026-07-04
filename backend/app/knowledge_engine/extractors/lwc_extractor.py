"""Extract structured knowledge from LWC bundles with Function nodes."""

from __future__ import annotations

import re
from pathlib import Path

from app.knowledge_engine.types import ExtractionResult

APEX_IMPORT = re.compile(
    r"import\s+(\w+)\s+from\s+['\"]@salesforce/apex/([\w.]+)['\"]"
)
WIRE_PATTERN = re.compile(
    r"@wire\s*\(\s*(\w+)\s*,\s*([^)]+)\)"
)
DECORATOR_PATTERN = re.compile(r"@(\w+)(?:\(([^)]*)\))?\s*\n\s*(\w+)", re.MULTILINE)
HANDLER_PATTERN = re.compile(
    r"(?:async\s+)?(\w+)\s*\([^)]*\)\s*\{",
    re.MULTILINE,
)
SCHEMA_IMPORT = re.compile(
    r"import\s+(\w+)\s+from\s+['\"]@salesforce/schema/([\w.]+)['\"]"
)
CHILD_COMPONENT = re.compile(r"<c-([\w-]+)")
EVENT_DISPATCH = re.compile(r"(?:this\.)?dispatchEvent\s*\(\s*new\s+(\w+)")
EVENT_HANDLER = re.compile(r"on(\w+)=\{(\w+)\}")
NAVIGATION = re.compile(r"\[NavigationMixin\.Navigate\]|NavigationMixin")
LIGHTNING_INPUT = re.compile(
    r"<lightning-(?:input|combobox|record-picker|textarea)[^>]*(?:field-name|data-field)=['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)


def extract_lwc(bundle_dir: Path, html_relative: str) -> list[ExtractionResult]:
    component_name = bundle_dir.name
    html_path = bundle_dir / f"{component_name}.html"
    js_path = bundle_dir / f"{component_name}.js"

    html = ""
    js = ""
    if html_path.exists():
        html = html_path.read_text(encoding="utf-8", errors="replace")
    if js_path.exists():
        js = js_path.read_text(encoding="utf-8", errors="replace")

    apex_calls = [
        {"alias": m.group(1), "method": m.group(2)} for m in APEX_IMPORT.finditer(js)
    ]
    wire_methods = [
        {"adapter": m.group(1), "params": m.group(2).strip()} for m in WIRE_PATTERN.finditer(js)
    ]
    decorators = [
        {"decorator": m.group(1), "args": m.group(2) or "", "property": m.group(3)}
        for m in DECORATOR_PATTERN.finditer(js)
    ]
    schema_imports = [
        {"alias": m.group(1), "schema": m.group(2)} for m in SCHEMA_IMPORT.finditer(js)
    ]
    child_components = list(dict.fromkeys(CHILD_COMPONENT.findall(html)))
    events_dispatched = list(dict.fromkeys(EVENT_DISPATCH.findall(js)))
    events_handled = [
        {"event": m.group(1), "handler": m.group(2)} for m in EVENT_HANDLER.finditer(html)
    ]
    uses_navigation = bool(NAVIGATION.search(js))
    html_fields = list(dict.fromkeys(LIGHTNING_INPUT.findall(html)))

    objects: list[str] = []
    fields: list[str] = []
    for item in schema_imports:
        schema = item["schema"]
        if "." in schema:
            obj, field = schema.rsplit(".", 1)
            objects.append(obj)
            fields.append(field)
        else:
            objects.append(schema)

    functions = _extract_js_functions(js, js_path, html_relative, events_handled)

    references = set(child_components)
    references.update(a["method"].split(".")[0] for a in apex_calls)
    references.update(objects)
    references.update(fields)

    relationships = []
    for apex in apex_calls:
        class_name = apex["method"].split(".")[0]
        relationships.append({"type": "CALLS", "source": component_name, "target": class_name})
    for child in child_components:
        relationships.append({"type": "USES", "source": component_name, "target": child})
    for obj in objects:
        relationships.append({"type": "REFERENCES", "source": component_name, "target": obj})
    for field in fields:
        relationships.append({"type": "RENDERS", "source": component_name, "target": field})
    for fn in functions:
        relationships.append(
            {"type": "BELONGS_TO", "source": f"{component_name}.{fn['name']}", "target": component_name}
        )

    rel_base = str(Path(html_relative).parent)
    files = []
    if html_path.exists():
        files.append({"path": f"{rel_base}/{component_name}.html", "language": "html"})
    if js_path.exists():
        files.append({"path": f"{rel_base}/{component_name}.js", "language": "javascript"})

    return [
        ExtractionResult(
            entity_type="LwcComponent",
            name=component_name,
            file_path=rel_base,
            data={
                "html_fields": html_fields,
                "apex_calls": apex_calls,
                "wire_methods": wire_methods,
                "decorators": decorators,
                "schema_imports": schema_imports,
                "child_components": child_components,
                "events_dispatched": events_dispatched,
                "events_handled": events_handled,
                "uses_navigation": uses_navigation,
                "objects": list(dict.fromkeys(objects)),
                "fields": list(dict.fromkeys(fields)),
                "functions": functions,
                "files": files,
            },
            references=list(references),
            relationships=relationships,
        )
    ]


def _extract_js_functions(
    js: str, js_path: Path, html_relative: str, events_handled: list[dict]
) -> list[dict]:
    functions = []
    handler_names = {e["handler"] for e in events_handled}
    js_rel = f"{Path(html_relative).parent}/{js_path.name}"

    for match in HANDLER_PATTERN.finditer(js):
        name = match.group(1)
        if name in ("if", "for", "while", "switch", "catch"):
            continue
        line_start = js[: match.start()].count("\n") + 1
        decorators = []
        if name in handler_names:
            decorators.append("eventHandler")
        for wm in WIRE_PATTERN.finditer(js):
            if wm.group(1) == name:
                decorators.append("wire")
        functions.append(
            {
                "name": name,
                "signature": f"{name}()",
                "line_start": line_start,
                "line_end": line_start + 5,
                "file_path": js_rel,
                "decorators": decorators,
                "queries_fields": [],
                "updates_fields": [],
            }
        )
    return functions
