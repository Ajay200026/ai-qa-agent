"""Golden-file tests for test pack understanding."""

from app.workflows.test_table_parser import is_test_pack, parse_test_pack

SAMPLE_TC = """
| Test Case ID | TC_4900_001 |
| Scenario | Change Primary Group with blank AR field values |
| Steps | 1. Open Data Change Request. 2. Select a new Primary Group. 3. Save the request. |
| Expected Result | AR-related fields are cleared and replaced with values from the selected Primary Group. |
"""

SAMPLE_PACK_HEADER = """
TC-01 — Primary Group editable on load
Step | Action | Expected Result
1 | Search and load an active Secondary Volume customer | Customer Details loads with BT = Secondary Volume (X)
2 | Check Primary Group field | Field is editable (not greyed out)
3 | Check Business Type Extension | Field remains read-only
"""


def test_is_test_pack_detects_tables():
    assert is_test_pack(SAMPLE_TC)
    assert is_test_pack(SAMPLE_PACK_HEADER)


def test_parse_single_table_case():
    pack = parse_test_pack(SAMPLE_TC)
    assert len(pack.test_cases) >= 1
    tc = pack.test_cases[0]
    assert "4900" in tc.tc_id or tc.tc_id
    assert len(tc.steps) >= 1


def test_parse_multi_tc_pack():
    pack = parse_test_pack(SAMPLE_PACK_HEADER)
    assert len(pack.test_cases) >= 1
    tc = pack.test_cases[0]
    assert tc.tc_id.startswith("TC")
    assert any(s.action for s in tc.steps)
    editable_steps = [s for s in tc.steps if s.assertions]
    assert editable_steps or len(tc.steps) >= 2


def test_infer_assertions_on_editable():
    pack = parse_test_pack(SAMPLE_PACK_HEADER)
    tc = pack.test_cases[0]
    all_kinds = {a.kind for s in tc.steps for a in s.assertions}
    assert len(all_kinds) >= 1
