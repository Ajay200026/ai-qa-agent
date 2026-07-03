"""Load CONA Data Change field metadata from bundled Salesforce LWC config exports."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).resolve().parents[2] / "resources" / "data_change_field_configs"

# Salesforce LWC type -> automation interaction type
TYPE_MAP = {
    "combobox": "combobox",
    "search": "lookup",
    "lookup": "lookup",
    "text": "text",
    "textarea": "text",
    "number": "text",
    "email": "text",
    "phone": "text",
    "toggle": "toggle",
    "checkbox": "toggle",
    "date": "text",
    "picklist": "combobox",
}

CUSTOMER_LOOKUP_LABELS = frozenset(
    {
        "Customer Number",
        "Customer Name/Number",
        "Customer Name",
    }
)

DEFAULT_CUSTOMER_SEARCH_PREFIX = "060"

# LWC section key -> Lightning form tab label
SECTION_TAB_LABELS: dict[str, str] = {
    "CUSTOMER_DETAILS": "Customer Details",
    "AR_FIELDS": "Account Receivable",
    "DELIVERY_ADDRESS": "Delivery Address",
    "DELIVERY_ADDRESS_FIELDS": "Delivery Address",
    "PRICING": "Pricing",
    "PRICING_FIELDS": "Pricing",
    "BASIC_ROUTING": "Routing",
    "PARTNERS": "Routing",
    "CALLING_AND_DELIVERY_TIME": "Routing",
    "VISIT_PLANS": "Routing",
    "CONTACTS": "Contacts",
    "CONTACTS_FORM": "Contacts",
    "ATTACHMENTS_FORM": "Attachments",
    "PAYER_DETAILS": "Customer Details",
    "REQUEST_FORM": "",
}


@dataclass(frozen=True)
class DataChangeField:
    config_key: str
    label: str
    api_name: str
    field_type: str
    section: str
    placeholder: str | None
    disabled: bool
    source_file: str
    required_bottler_ids: frozenset[str] = frozenset()

    @property
    def automation_type(self) -> str:
        return TYPE_MAP.get(self.field_type, "text")

    def is_required_for_bottler(self, bottler_id: str) -> bool:
        if not bottler_id or not self.required_bottler_ids:
            return False
        normalized = str(bottler_id).strip()
        return normalized in self.required_bottler_ids


def _normalize_label(label: str) -> str:
    return re.sub(r"\s+", " ", label.strip().lower())


def _parse_bottler_ids(raw_list: Any) -> frozenset[str]:
    if not isinstance(raw_list, list):
        return frozenset()
    ids: set[str] = set()
    for item in raw_list:
        if isinstance(item, dict) and item.get("id"):
            ids.add(str(item["id"]).strip())
        elif isinstance(item, str) and item.strip():
            ids.add(item.strip())
    return frozenset(ids)


def _iter_field_arrays(payload: dict[str, Any]) -> list[dict[str, Any]]:
    fields: list[dict[str, Any]] = []
    for key, value in payload.items():
        if key.endswith("Fields") and isinstance(value, list):
            fields.extend(item for item in value if isinstance(item, dict))
    return fields


@lru_cache
def load_data_change_fields() -> tuple[DataChangeField, ...]:
    records: list[DataChangeField] = []
    if not CONFIG_DIR.is_dir():
        logger.warning("Data Change field configs not found at %s", CONFIG_DIR)
        return tuple()

    for path in sorted(CONFIG_DIR.glob("conaDatachange*FieldConfigs.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Could not read %s: %s", path.name, exc)
            continue
        source = str(payload.get("sourceFile") or path.name)
        for raw in _iter_field_arrays(payload):
            label = str(raw.get("label") or "").strip()
            if not label:
                continue
            section_raw = raw.get("section")
            section = (
                str(section_raw).strip()
                if isinstance(section_raw, str)
                else ""
            )
            records.append(
                DataChangeField(
                    config_key=str(raw.get("configKey") or label),
                    label=label,
                    api_name=str(raw.get("apiName") or raw.get("backendName") or ""),
                    field_type=str(raw.get("type") or "text").lower(),
                    section=section,
                    placeholder=raw.get("placeholder"),
                    disabled=bool(raw.get("disabled")),
                    source_file=source,
                    required_bottler_ids=_parse_bottler_ids(raw.get("required")),
                )
            )
    logger.info(
        "Loaded %d Data Change field definitions from %d files",
        len(records),
        len(list(CONFIG_DIR.glob("*.json"))),
    )
    return tuple(records)


@lru_cache
def field_index_by_label() -> dict[str, DataChangeField]:
    index: dict[str, DataChangeField] = {}
    for field in load_data_change_fields():
        index[_normalize_label(field.label)] = field
        index[_normalize_label(field.config_key.replace("_", " "))] = field
    index[_normalize_label("Customer Name/Number")] = _pick_customer_lookup_field()
    index[_normalize_label("Customer Number")] = _pick_customer_lookup_field()
    return index


def _pick_customer_lookup_field() -> DataChangeField:
    return DataChangeField(
        config_key="CUSTOMER_LOOKUP",
        label="Customer Name/Number",
        api_name="customerLookup",
        field_type="search",
        section="REQUEST_FORM",
        placeholder="Search customer...",
        disabled=False,
        source_file="request_form",
        required_bottler_ids=frozenset(),
    )


def get_field_by_label(label: str) -> DataChangeField | None:
    if not label:
        return None
    norm = _normalize_label(label)
    if norm in {
        _normalize_label("Customer Number"),
        _normalize_label("Customer Name/Number"),
        _normalize_label("Customer Name"),
    }:
        return _pick_customer_lookup_field()
    return field_index_by_label().get(norm)


def section_to_tab_label(section: str) -> str | None:
    """Map LWC section to form tab label; None when no tab switch needed."""
    if not section:
        return None
    tab = SECTION_TAB_LABELS.get(section.upper())
    if tab is not None:
        return tab or None
    upper = section.upper()
    if "AR" in upper or "RECEIVABLE" in upper:
        return "Account Receivable"
    if "CUSTOMER" in upper:
        return "Customer Details"
    if "DELIVERY" in upper:
        return "Delivery Address"
    if "PRICING" in upper:
        return "Pricing"
    if "ROUTING" in upper or "VISIT" in upper:
        return "Routing"
    if "CONTACT" in upper:
        return "Contacts"
    if "ATTACH" in upper:
        return "Attachments"
    return None


def get_required_fields_for_bottler(bottler_id: str) -> list[DataChangeField]:
    """Fields marked required in bundled configs for the given bottler."""
    if not bottler_id:
        return []
    normalized = str(bottler_id).strip()
    return [
        field
        for field in load_data_change_fields()
        if not field.disabled and field.is_required_for_bottler(normalized)
    ]


def resolve_automation_type(label: str, fallback: str = "combobox") -> str:
    field = get_field_by_label(label)
    return field.automation_type if field else fallback


def customer_search_field_label() -> str:
    return _pick_customer_lookup_field().label


def default_customer_search_query() -> str:
    return DEFAULT_CUSTOMER_SEARCH_PREFIX
