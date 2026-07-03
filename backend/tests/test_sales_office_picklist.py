"""Sales Office picklist option patterns."""

from app.knowledge.sales_office_rules import office_option_pattern


def test_office_option_matches_s_prefix_5000():
    pattern = office_option_pattern("5000")
    assert pattern.search("S003 Granite State, NH")
    assert not pattern.search("Q003 Pittsburgh")


def test_office_option_matches_q_prefix_4900():
    pattern = office_option_pattern("4900")
    assert pattern.search("Q003 Pittsburgh, PA")
    assert not pattern.search("S003 Granite State, NH")


def test_office_option_matches_k_prefix_4600():
    pattern = office_option_pattern("4600")
    assert pattern.search("K003 West Dundee")


def test_office_option_includes_payer():
    pattern = office_option_pattern("5000")
    assert pattern.search("Payer")


def test_office_option_matches_fsv_recipient():
    pattern = office_option_pattern("4900")
    assert pattern.search("FSV Recipient")
