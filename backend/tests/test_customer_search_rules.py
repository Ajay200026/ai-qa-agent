"""Unit tests for bottler-aware customer search rules."""

from app.knowledge.customer_search_rules import (
    default_soql_for_bottler,
    is_valid_combo,
    valid_combinations,
    known_account_groups,
)


def _combo_set(combos):
    return {(c["account_group"], c["distribution_channel"]) for c in combos}


def test_unknown_bottler_returns_empty():
    assert valid_combinations(None) == []
    assert valid_combinations("9999") == []


def test_5000_default_includes_z001_and_z003():
    combos = _combo_set(valid_combinations("5000"))
    assert ("Z001", None) in combos
    assert ("Z003", None) in combos


def test_5000_payer_only_z003():
    combos = _combo_set(valid_combinations("5000", "Payer"))
    assert combos == {("Z003", None)}


def test_4900_no_office_full_matrix():
    combos = _combo_set(valid_combinations("4900"))
    assert ("Z001", "Z1") in combos
    assert ("ZFSV", "Z3") in combos
    assert ("Z003", "Z1") in combos
    assert ("Z003", "Z3") in combos


def test_4900_with_office_strict():
    combos = _combo_set(valid_combinations("4900", "K045"))
    assert combos == {("Z001", "Z1"), ("ZFSV", "Z3")}


def test_4900_fsv_recipient_office():
    combos = _combo_set(valid_combinations("4900", "FSV Recipient"))
    assert combos == {("Z003", "Z3")}


def test_4600_default_groups():
    combos = _combo_set(valid_combinations("4600"))
    assert ("Z001", None) in combos
    assert ("ZFSV", None) in combos
    assert ("Z003", None) in combos


def test_4600_payer():
    combos = _combo_set(valid_combinations("4600", "Payer"))
    assert combos == {("Z003", "Z1")}


def test_is_valid_combo():
    assert is_valid_combo("4900", "K045", "Z001", "Z1")
    assert not is_valid_combo("4900", "K045", "Z001", "Z3")
    assert is_valid_combo("5000", None, "Z001", None)


def test_known_account_groups():
    assert set(known_account_groups("4900")) == {"Z001", "ZFSV", "Z003"}
    assert set(known_account_groups("5000")) == {"Z001", "Z003"}


def test_default_soql_includes_bottler_filter():
    soql_4900 = default_soql_for_bottler("4900")
    assert "Z001" in soql_4900 and "ZFSV" in soql_4900
    assert "FROM Account" in soql_4900
    assert "LIMIT" in soql_4900


def test_default_soql_5000_includes_customer_number_and_limit_50():
    soql = default_soql_for_bottler("5000")
    assert "cfs_ob__u_CustomerNumber__c" in soql
    assert "cfs_ob__u_SalesOffice__c" in soql
    assert "cfs_ob__Bottler__c = '5000'" in soql
    assert "LIMIT 50" in soql
