"""Input validation and pairing preparation."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple

import pandas as pd

from .constants import ALL_TRACKED_FIELDS, REQUIRED_COLUMNS, resolve_field_type, resolve_tier
from .normalize import canonical_missing_or_text, is_missing, score_pair


def read_input_csv(path: Path) -> pd.DataFrame:
    """Read and validate required schema columns."""
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    missing_cols = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_cols:
        raise ValueError(f"{path} missing required columns: {missing_cols}")
    return df[REQUIRED_COLUMNS].copy()


def check_duplicate_keys(df: pd.DataFrame, side: str) -> None:
    """Fail when (record_id, field_name) duplicates are present."""
    dup_mask = df.duplicated(subset=["record_id", "field_name"], keep=False)
    if dup_mask.any():
        sample = df.loc[dup_mask, ["record_id", "field_name"]].head(10).to_dict(orient="records")
        raise ValueError(f"{side} has duplicate (record_id, field_name) keys. Sample: {sample}")


def check_join_coverage(base_df: pd.DataFrame, new_df: pd.DataFrame, threshold: float) -> Dict[str, float]:
    """Validate join key coverage and return coverage stats."""
    base_keys = set(zip(base_df["record_id"], base_df["field_name"]))
    new_keys = set(zip(new_df["record_id"], new_df["field_name"]))

    only_base = base_keys - new_keys
    only_new = new_keys - base_keys
    union_n = max(len(base_keys | new_keys), 1)
    mismatch_ratio = (len(only_base) + len(only_new)) / union_n

    if mismatch_ratio > threshold:
        raise ValueError(
            "Join key coverage mismatch exceeded threshold: "
            f"ratio={mismatch_ratio:.6f}, threshold={threshold:.6f}, "
            f"baseline_only={len(only_base)}, new_only={len(only_new)}"
        )

    return {
        "baseline_key_count": len(base_keys),
        "new_key_count": len(new_keys),
        "baseline_only_key_count": len(only_base),
        "new_only_key_count": len(only_new),
        "join_mismatch_ratio": mismatch_ratio,
    }


def prepare_paired(base_df: pd.DataFrame, new_df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, int]]:
    """Create paired row-level evaluation table with correctness/regression flags."""
    merged = base_df.merge(
        new_df,
        on=["record_id", "field_name"],
        how="inner",
        suffixes=("_base", "_new"),
    )

    merged["expected_base_canon"] = merged["expected_value_base"].map(canonical_missing_or_text).fillna("<MISSING>")
    merged["expected_new_canon"] = merged["expected_value_new"].map(canonical_missing_or_text).fillna("<MISSING>")
    expected_mismatch = merged["expected_base_canon"] != merged["expected_new_canon"]
    if expected_mismatch.any():
        sample = merged.loc[expected_mismatch, ["record_id", "field_name"]].head(10).to_dict(orient="records")
        raise ValueError(f"expected_value mismatch between baseline and new for same keys. Sample: {sample}")

    merged["record_type_mismatch"] = merged["record_type_base"] != merged["record_type_new"]
    merged["document_group_mismatch"] = merged["document_group_base"] != merged["document_group_new"]

    mismatch_counts = {
        "record_type_mismatch_count": int(merged["record_type_mismatch"].sum()),
        "document_group_mismatch_count": int(merged["document_group_mismatch"].sum()),
    }

    paired = pd.DataFrame(
        {
            "record_id": merged["record_id"],
            "field_name": merged["field_name"],
            "field_type": merged["field_name"].map(resolve_field_type),
            "tier": merged["field_name"].map(resolve_tier),
            "record_type": merged["record_type_base"],
            "document_group": merged["document_group_base"],
            "expected_value": merged["expected_value_base"],
            "old_value": merged["generated_value_base"],
            "new_value": merged["generated_value_new"],
            "record_type_new": merged["record_type_new"],
            "document_group_new": merged["document_group_new"],
            "record_type_mismatch": merged["record_type_mismatch"].astype(int),
            "document_group_mismatch": merged["document_group_mismatch"].astype(int),
        }
    )

    old_scored = paired.apply(
        lambda row: score_pair(row["field_type"], row["expected_value"], row["old_value"]),
        axis=1,
    )
    new_scored = paired.apply(
        lambda row: score_pair(row["field_type"], row["expected_value"], row["new_value"]),
        axis=1,
    )

    paired["old_correct"] = [s.correct for s in old_scored]
    paired["new_correct"] = [s.correct for s in new_scored]
    paired["old_parse_error"] = [int(s.parse_error) for s in old_scored]
    paired["new_parse_error"] = [int(s.parse_error) for s in new_scored]

    paired["expected_present"] = (~paired["expected_value"].map(is_missing)).astype(int)
    paired["old_missing"] = (
        (paired["old_value"].map(is_missing)) & (~paired["expected_value"].map(is_missing))
    ).astype(int)
    paired["new_missing"] = (
        (paired["new_value"].map(is_missing)) & (~paired["expected_value"].map(is_missing))
    ).astype(int)

    paired["improvement"] = ((paired["old_correct"] == 0) & (paired["new_correct"] == 1)).astype(int)
    paired["regression"] = ((paired["old_correct"] == 1) & (paired["new_correct"] == 0)).astype(int)
    paired["tie"] = 1 - paired["improvement"] - paired["regression"]

    tracked_mask = paired["field_name"].isin(ALL_TRACKED_FIELDS)
    tracked = paired[tracked_mask].copy()
    if tracked.empty:
        raise ValueError("No tracked rows found after filtering to configured 20 fields.")

    return tracked, mismatch_counts
