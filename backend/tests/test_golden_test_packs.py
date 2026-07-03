"""Golden expectations for US-21153-style test pack parsing."""

US_21153_SNIPPET = """
US-21153 — Test Cases
Module: Data Change | Bottler: Northeast (5000)

Preconditions (all scenarios)
Log in as a Northeast (5000) user with Data Change access.

TC-01 — Primary Group editable on load (Requestor)
Step | Action | Expected Result
1 | Search and load an active Secondary Volume customer | Customer Details loads with BT = Secondary Volume (X)
2 | Check Primary Group field | Field is editable (not greyed out)
3 | Check Business Type Extension | Field remains read-only

TC-03 — Toast when Business Type changed away from SV without PG update (positive)
Step | Action | Expected Result
1 | Load SV customer; do not change Primary Group | PG unchanged from SAP baseline
2 | Change Business Type from Secondary Volume (X) to DSD (01) | Error-style toast appears
3 | Read toast message | Text: "If you intend to convert a Secondary Volume customer to DSD, please ensure the Primary Group is updated."

Minimum test pack (smoke): TC-01, TC-02, TC-03, TC-04, TC-06, TC-07.
"""


def test_us_21153_parses_multiple_tcs():
    from app.workflows.test_table_parser import parse_test_pack

    pack = parse_test_pack(US_21153_SNIPPET)
    assert len(pack.test_cases) >= 2
    ids = {tc.tc_id for tc in pack.test_cases}
    assert any("01" in i for i in ids)
    assert pack.smoke_subset or len(pack.test_cases) >= 2


def test_us_21153_tc03_has_toast_assertion():
    from app.workflows.test_table_parser import parse_test_pack

    pack = parse_test_pack(US_21153_SNIPPET)
    tc03 = next((tc for tc in pack.test_cases if "03" in tc.tc_id), None)
    assert tc03 is not None
    toast_assertions = [
        a for s in tc03.steps for a in s.assertions if "toast" in a.kind.value
    ]
    assert len(toast_assertions) >= 1
