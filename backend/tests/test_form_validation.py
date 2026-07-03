"""Tests for submit outcome detection."""

from app.automation.form_validation import (
    SubmitOutcome,
    _extract_field_labels_from_text,
    is_empty_field_value,
)


def test_extract_field_labels_from_toast():
    text = "Terms of Payment is required. Please select a value."
    labels = _extract_field_labels_from_text(text)
    assert any("Terms of Payment" in label for label in labels)


def test_is_empty_field_value():
    assert is_empty_field_value("")
    assert is_empty_field_value("Select an option")
    assert is_empty_field_value("Enter Primary Group", "Enter Primary Group")
    assert not is_empty_field_value("A0168-TEST GROUP")


def test_submit_outcome_dataclass():
    outcome = SubmitOutcome(
        status="validation_error",
        message="required",
        missing_field_labels=["Payment Options"],
    )
    assert outcome.status == "validation_error"
    assert outcome.missing_field_labels == ["Payment Options"]
