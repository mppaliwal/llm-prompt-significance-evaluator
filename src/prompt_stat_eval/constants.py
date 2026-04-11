"""Constants and field maps for structured field evaluation."""

from __future__ import annotations

from typing import Dict

CRITICAL_FIELDS: Dict[str, str] = {
    "primary_date": "date",
    "amount_value": "number",
    "completion_date": "date",
    "end_date": "date",
    "category_code": "code",
}

GENERAL_FIELDS: Dict[str, str] = {
    "secondary_date": "date",
    "start_date": "date",
    "effective_date": "date",
    "rate_value": "rate",
    "rate_frequency": "text",
    "rule_type": "text",
    "adjustment_rule": "text",
    "reference_code": "text",
    "delta_value": "rate",
    "value_type": "text",
    "price_value": "number",
    "derived_amount": "number",
    "total_value": "number",
    "direction_label": "text",
    "entity_name": "text",
}

ALL_TRACKED_FIELDS = list(CRITICAL_FIELDS.keys()) + list(GENERAL_FIELDS.keys())

FIELD_TYPE_MAP: Dict[str, str] = {}
FIELD_TYPE_MAP.update(CRITICAL_FIELDS)
FIELD_TYPE_MAP.update(GENERAL_FIELDS)

REQUIRED_COLUMNS = [
    "record_id",
    "record_type",
    "document_group",
    "field_name",
    "expected_value",
    "generated_value",
]

MISSING_TOKENS = {"", "NO_DATA_FOUND", "NULL", "N/A"}


def resolve_field_type(field_name: str) -> str:
    return FIELD_TYPE_MAP.get(field_name, "text")


def resolve_tier(field_name: str) -> str:
    if field_name in CRITICAL_FIELDS:
        return "CRITICAL"
    if field_name in GENERAL_FIELDS:
        return "GENERAL"
    return "OTHER"
