"""Constants and field maps for trade confirmation evaluation."""

from __future__ import annotations

from typing import Dict

CRITICAL_FIELDS: Dict[str, str] = {
    "trade_date": "date",
    "notional_amount": "amount",
    "settlement_date": "date",
    "maturity_date": "date",
    "currency": "currency",
}

GENERAL_FIELDS: Dict[str, str] = {
    "payment_date": "date",
    "issue_date": "date",
    "effective_date": "date",
    "coupon_rate": "rate",
    "coupon_frequency": "text",
    "day_count_convention": "text",
    "business_day_convention": "text",
    "reference_rate_index": "text",
    "spread_bps": "rate",
    "rate_type": "text",
    "clean_price": "amount",
    "accrued_interest": "amount",
    "settlement_amount": "amount",
    "trade_side": "text",
    "counterparty_name": "text",
}

ALL_TRACKED_FIELDS = list(CRITICAL_FIELDS.keys()) + list(GENERAL_FIELDS.keys())

FIELD_TYPE_MAP: Dict[str, str] = {}
FIELD_TYPE_MAP.update(CRITICAL_FIELDS)
FIELD_TYPE_MAP.update(GENERAL_FIELDS)

REQUIRED_COLUMNS = [
    "deal_id",
    "deal_type",
    "template",
    "field_name",
    "golden_truth",
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
