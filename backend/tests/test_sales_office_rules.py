"""Bottler-aware sales office selection rules."""

from app.knowledge.sales_office_rules import (
    BOTTLER_OFFICE_PREFIX,
    choose_office_option,
    office_option_js_pattern,
    rank_office_options,
    resolve_bottler_id,
)


def test_bottler_prefixes():
    assert BOTTLER_OFFICE_PREFIX["5000"] == "S"
    assert BOTTLER_OFFICE_PREFIX["4900"] == "Q"
    assert BOTTLER_OFFICE_PREFIX["4600"] == "K"


def test_office_pattern_4900_matches_q_codes():
    pattern = office_option_js_pattern("4900")
    assert "Q" in pattern
    assert "Payer" in pattern


def test_rank_prefers_bottler_prefix_over_payer():
    options = ["Payer", "Q003 Pittsburgh", "Q008 Erie"]
    ranked = rank_office_options(options, "4900")
    assert ranked[0].startswith("Q")


def test_rank_5000_prefers_s_over_payer():
    options = ["Payer", "S003 Granite State, NH", "S008 Waterford, CT"]
    ranked = rank_office_options(options, "5000")
    assert ranked[0].startswith("S")


def test_choose_explicit_payer():
    options = ["Payer", "S003 Granite State, NH"]
    assert choose_office_option(options, "Payer", bottler_id="5000") == "Payer"


def test_choose_auto_picks_coded_office():
    options = ["Payer", "Q003 Pittsburgh, PA"]
    assert choose_office_option(options, "__any__", bottler_id="4900") == "Q003 Pittsburgh, PA"


def test_resolve_bottler_from_step_params():
    assert resolve_bottler_id(step_params={"bottler_id": "5000"}) == "5000"
