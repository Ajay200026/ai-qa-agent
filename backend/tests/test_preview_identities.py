"""Preview identities endpoint tests."""

from app.services.identity_preview import preview_identities_from_content

SAMPLE_PACK = """
US-21153 Data Change Tests
Module: Customer Details
Bottler: 5000

TC-01 — Requestor creates data change
Role: Requestor
| Step | Action | Expected |
| 1 | Login | Success |

TC-02 — Finance approves
Role: Finance
| Step | Action | Expected |
| 1 | Login | Success |

TC-03 — Requestor again
Role: Requestor
| Step | Action | Expected |
| 1 | Login | Success |
"""


def test_groups_unique_identities_with_tc_ids():
    result = preview_identities_from_content(SAMPLE_PACK)
    assert result.pack_bottler == "5000"
    keys = {(i.bottler, i.role) for i in result.identities}
    assert ("5000", "Requestor") in keys
    assert ("5000", "Finance") in keys

    requestor = next(i for i in result.identities if i.role == "Requestor")
    assert "TC-01" in requestor.tc_ids or any("01" in tc for tc in requestor.tc_ids)
    assert len(requestor.tc_ids) >= 1


def test_empty_content_returns_empty():
    result = preview_identities_from_content("")
    assert result.identities == []
