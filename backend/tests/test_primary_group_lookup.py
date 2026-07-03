"""Primary Group search field option matching."""

import re

from app.automation.form_field import FORM_FIELDS


def test_primary_group_placeholder_matches_enter_primary():
    spec = FORM_FIELDS["Primary Group"]
    assert spec.placeholder.search("Enter Primary Group")
    assert not spec.placeholder.search("Search customer")


def test_primary_group_code_pattern():
    code = "A0168"
    pattern = re.compile(r"[AB]\d{4}", re.I)
    assert pattern.search("A0168-INDY CR LBW TRADE LETTER")
    assert not pattern.search("0501856969 - NEWPORT MOBIL")
