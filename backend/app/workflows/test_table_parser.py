"""Deterministic parser for multi-test-case packs (LLM fallback)."""

from __future__ import annotations

import re

from app.schemas.test_case import Assertion, AssertionKind, TestCase, TestPack, TestStep
from app.workflows.action_mapping import infer_action_from_text, infer_assertions_from_expected

TC_HEADER = re.compile(
    r"^(?:TC[-_]\s*)?((?:TC[-_])?\d+(?:_\d+)?)\s*(?:[—\-–]\s*(.+))?$",
    re.I | re.M,
)
TC_ID_INLINE = re.compile(r"\b(TC[-_]?\d+(?:_\d+)?)\b", re.I)
BOTTLER_RE = re.compile(r"(?:bottler|log\s*in\s*as)\s*[:\s]*([^(]+)?\(?(\d{4})\)?", re.I)
ROLE_RE = re.compile(
    r"(?:role|log\s*in\s*as)\s*[:\s]*([A-Za-z][A-Za-z\s/]+?)(?:\s+role|\s+user|\(|$)",
    re.I,
)
SMOKE_RE = re.compile(r"minimum\s+test\s+pack.*?[:]\s*(.+)$", re.I | re.S)


def parse_test_pack(text: str) -> TestPack:
    text = (text or "").strip()
    if not text:
        return TestPack()

    title = _extract_title(text)
    module = _extract_module(text)
    bottler = _extract_bottler(text)
    shared_preconditions = _extract_shared_preconditions(text)
    smoke_subset = _extract_smoke_subset(text)

    test_cases: list[TestCase] = []
    sections = _split_tc_sections(text)

    for section in sections:
        tc = _parse_tc_section(section, shared_preconditions, bottler)
        if tc and tc.steps:
            test_cases.append(tc)

    if not test_cases:
        single = _parse_single_table_case(text, shared_preconditions, bottler)
        if single:
            test_cases.append(single)

    return TestPack(
        title=title,
        module=module,
        bottler=bottler,
        shared_preconditions=shared_preconditions,
        test_cases=test_cases,
        smoke_subset=smoke_subset,
    )


def is_test_pack(text: str) -> bool:
    if not text or len(text.strip()) < 40:
        return False
    lower = text.lower()
    if TC_HEADER.search(text) or "tc-" in lower or "tc_" in lower:
        return True
    if "| test case id |" in lower or "| scenario |" in lower:
        return True
    if "step" in lower and "expected result" in lower and "action" in lower:
        return True
    return False


def _extract_title(text: str) -> str:
    for line in text.splitlines()[:5]:
        line = line.strip()
        if line and not line.startswith("|"):
            return line[:200]
    return ""


def _extract_module(text: str) -> str | None:
    m = re.search(r"module\s*:\s*([^\n|]+)", text, re.I)
    return m.group(1).strip() if m else None


def _extract_bottler(text: str) -> str | None:
    m = BOTTLER_RE.search(text)
    if m:
        name = (m.group(1) or "").strip()
        code = m.group(2)
        return f"{name} ({code})".strip() if name else code
    return None


def _extract_shared_preconditions(text: str) -> list[str]:
    pre: list[str] = []
    block = re.search(
        r"preconditions?\s*\([^)]*\)\s*\n(.+?)(?=\n\s*TC[-_]|\n\s*TC_\d|\Z)",
        text,
        re.I | re.S,
    )
    if block:
        for line in block.group(1).splitlines():
            line = line.strip().lstrip("•-*1234567890. ")
            if line and len(line) > 3:
                pre.append(line)
    return pre


def _extract_smoke_subset(text: str) -> list[str]:
    m = SMOKE_RE.search(text)
    if not m:
        return []
    ids = re.findall(r"TC[-_]?\d+", m.group(1), re.I)
    return [i.upper().replace("_", "-") if "-" not in i else i for i in ids]


def _split_tc_sections(text: str) -> list[str]:
    parts = re.split(r"(?=^TC[-_]\s*\d+)", text, flags=re.I | re.M)
    return [p.strip() for p in parts if p.strip() and re.match(r"^TC[-_]", p.strip(), re.I)]


def _parse_tc_section(section: str, shared: list[str], default_bottler: str | None) -> TestCase | None:
    lines = section.splitlines()
    header = lines[0].strip() if lines else ""
    m = TC_HEADER.match(header)
    if not m:
        return None

    tc_id = m.group(1).upper().replace("_", "-")
    if not tc_id.startswith("TC"):
        tc_id = f"TC-{tc_id.lstrip('TC-')}"

    title = (m.group(2) or "").strip() or tc_id
    role = None
    bottler = default_bottler

    for line in lines[1:6]:
        rm = ROLE_RE.search(line)
        if rm:
            role = rm.group(1).strip()
        bm = BOTTLER_RE.search(line)
        if bm:
            name = (bm.group(1) or "").strip()
            code = bm.group(2)
            bottler = f"{name} ({code})".strip() if name else code

    preconditions = list(shared)
    steps = _parse_steps_table(section)
    if not steps:
        steps = _parse_numbered_steps(section)

    return TestCase(
        tc_id=tc_id,
        title=title,
        role=role,
        bottler=bottler,
        preconditions=preconditions,
        steps=steps,
        expected_summary=[s.description for s in steps if s.assertions],
    )


def _parse_single_table_case(text: str, shared: list[str], bottler: str | None) -> TestCase | None:
    tc_id = "TC-001"
    scenario = ""
    m = re.search(r"test\s*case\s*id\s*\|\s*([^\n|]+)", text, re.I)
    if m:
        tc_id = m.group(1).strip()
    m = re.search(r"scenario\s*\|\s*([^\n|]+)", text, re.I)
    if m:
        scenario = m.group(1).strip()

    steps = _parse_field_table(text)
    if not steps:
        return None

    return TestCase(
        tc_id=tc_id,
        title=scenario or tc_id,
        bottler=bottler,
        preconditions=shared,
        steps=steps,
    )


def _parse_field_table(text: str) -> list[TestStep]:
    steps_block = re.search(r"steps\s*\|\s*(.+?)(?:\n\||\nexpected)", text, re.I | re.S)
    expected_block = re.search(r"expected\s*result\s*\|\s*(.+?)(?:\n\||\Z)", text, re.I | re.S)
    if not steps_block:
        return []

    raw_steps = re.sub(r"<br\s*/?>", "\n", steps_block.group(1), flags=re.I)
    step_lines = [s.strip() for s in re.split(r"\d+\.\s*", raw_steps) if s.strip()]
    expected_text = expected_block.group(1).strip() if expected_block else ""

    steps: list[TestStep] = []
    for i, line in enumerate(step_lines, start=1):
        action = infer_action_from_text(line)
        assertions = infer_assertions_from_expected(expected_text) if i == len(step_lines) else []
        steps.append(
            TestStep(
                seq=i,
                action=action or "set_field",
                description=line,
                value=_extract_value_from_action(line),
                target=_extract_field_from_action(line),
                assertions=assertions,
            )
        )
    return steps


def _parse_steps_table(section: str) -> list[TestStep]:
    rows: list[tuple[str, str, str]] = []
    in_table = False
    for line in section.splitlines():
        if re.search(r"step\s*\|.*action\s*\|.*expected", line, re.I):
            in_table = True
            continue
        if not in_table:
            continue
        if not line.strip() or line.strip().startswith("---"):
            continue
        if "|" not in line:
            if rows:
                break
            continue
        cols = [c.strip() for c in line.split("|") if c.strip()]
        if len(cols) >= 3 and cols[0].isdigit():
            rows.append((cols[0], cols[1], cols[2]))
        elif len(cols) >= 2 and cols[0].isdigit():
            rows.append((cols[0], cols[1], cols[-1]))

    steps: list[TestStep] = []
    for seq_s, action_text, expected_text in rows:
        action = infer_action_from_text(action_text) or "set_field"
        assertions = infer_assertions_from_expected(expected_text)
        steps.append(
            TestStep(
                seq=int(seq_s),
                action=action,
                description=action_text,
                target=_extract_field_from_action(action_text),
                value=_extract_value_from_action(action_text),
                assertions=assertions,
                params={"expected_text": expected_text},
            )
        )
    return steps


def _parse_numbered_steps(section: str) -> list[TestStep]:
    steps: list[TestStep] = []
    for m in re.finditer(r"^(\d+)\.\s+(.+)$", section, re.M):
        seq = int(m.group(1))
        text = m.group(2).strip()
        action = infer_action_from_text(text) or "set_field"
        steps.append(
            TestStep(
                seq=seq,
                action=action,
                description=text,
                target=_extract_field_from_action(text),
                value=_extract_value_from_action(text),
            )
        )
    return steps


def _extract_field_from_action(text: str) -> str | None:
    for field in (
        "Primary Group",
        "Business Type",
        "Business Type Extension",
        "Sales Office",
        "Customer Number",
    ):
        if field.lower() in text.lower():
            return field
    return None


def _extract_value_from_action(text: str) -> str | None:
    m = re.search(r"(?:to|as|=\s*|select\s+)([A-Za-z0-9\s\-_/]+?)(?:\.|$|\)|,)", text, re.I)
    if m:
        val = m.group(1).strip()
        if val.lower() not in ("a", "the", "an"):
            return val
    m = re.search(r"\((\d{2,4}|X|01)\)", text)
    return m.group(1) if m else None
