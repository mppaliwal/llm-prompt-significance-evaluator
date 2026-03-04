"""Normalization and correctness rules for field evaluation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import pandas as pd

from .constants import MISSING_TOKENS


@dataclass(frozen=True)
class ScoredResult:
    correct: int
    parse_error: bool


def is_missing(value: object) -> bool:
    if value is None:
        return True
    if pd.isna(value):
        return True
    text = str(value).strip()
    return text.upper() in MISSING_TOKENS


def canonical_missing_or_text(value: object) -> Optional[str]:
    if is_missing(value):
        return None
    return str(value).strip()


def normalize_text(value: object) -> str:
    text = str(value).lower().strip()
    return re.sub(r"\s+", " ", text)


def normalize_currency(value: object) -> str:
    text = str(value).upper().strip()
    return re.sub(r"[^A-Z0-9]", "", text)


def parse_date_ddmmyyyy(value: object) -> Optional[str]:
    if is_missing(value):
        return None
    text = str(value).strip()
    if not re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", text):
        raise ValueError(f"Invalid date format: {value!r}")
    dt = datetime.strptime(text, "%d/%m/%Y")
    return dt.strftime("%Y-%m-%d")


def parse_numeric(value: object) -> Optional[float]:
    if is_missing(value):
        return None

    text = str(value).strip()
    text = text.replace("\u2212", "-")

    is_paren_negative = text.startswith("(") and text.endswith(")")
    if is_paren_negative:
        text = text[1:-1].strip()

    text_no_sep = text.replace(",", "")
    has_percent = "%" in text_no_sep
    text_no_sep = text_no_sep.replace("%", "")

    tokens = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", text_no_sep)
    if len(tokens) != 1:
        raise ValueError(f"Unable to parse numeric value: {value!r}")

    number = float(tokens[0])
    if is_paren_negative and number > 0:
        number = -number
    if has_percent:
        number = number / 100.0
    return number


def numeric_match(x: float, y: float, abs_tol: float = 0.01, rel_tol: float = 1e-4) -> bool:
    return abs(x - y) <= max(abs_tol, rel_tol * max(1.0, abs(y)))


def rate_match(x: float, y: float) -> bool:
    if numeric_match(x, y):
        return True
    if numeric_match(x * 100.0, y):
        return True
    if numeric_match(x, y * 100.0):
        return True
    return False


def score_pair(field_type: str, gold_value: object, gen_value: object) -> ScoredResult:
    gold_missing = is_missing(gold_value)
    gen_missing = is_missing(gen_value)

    if gold_missing and gen_missing:
        return ScoredResult(correct=1, parse_error=False)
    if gold_missing and not gen_missing:
        return ScoredResult(correct=0, parse_error=False)
    if not gold_missing and gen_missing:
        return ScoredResult(correct=0, parse_error=False)

    if field_type == "date":
        try:
            gold_dt = parse_date_ddmmyyyy(gold_value)
            gen_dt = parse_date_ddmmyyyy(gen_value)
        except Exception:
            return ScoredResult(correct=0, parse_error=True)
        return ScoredResult(correct=int(gold_dt == gen_dt), parse_error=False)

    if field_type == "currency":
        return ScoredResult(
            correct=int(normalize_currency(gold_value) == normalize_currency(gen_value)),
            parse_error=False,
        )

    if field_type in {"amount", "rate"}:
        try:
            gold_num = parse_numeric(gold_value)
            gen_num = parse_numeric(gen_value)
        except Exception:
            return ScoredResult(correct=0, parse_error=True)

        if gold_num is None or gen_num is None:
            return ScoredResult(correct=0, parse_error=False)

        if field_type == "rate":
            return ScoredResult(correct=int(rate_match(gen_num, gold_num)), parse_error=False)
        return ScoredResult(correct=int(numeric_match(gen_num, gold_num)), parse_error=False)

    return ScoredResult(
        correct=int(normalize_text(gold_value) == normalize_text(gen_value)),
        parse_error=False,
    )

