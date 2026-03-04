"""Top-level evaluation pipeline orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

from .config import EvalConfig
from .constants import ALL_TRACKED_FIELDS
from .reporting import write_artifacts
from .stats import (
    build_field_metrics,
    build_overall_metrics,
    build_rollout_decision,
    build_stratum_metrics,
    validate_parse_error_thresholds,
)
from .validation import (
    check_duplicate_keys,
    check_join_coverage,
    prepare_paired,
    read_input_csv,
)

JOIN_MISMATCH_THRESHOLD = 0.0


def run_evaluation(
    baseline_csv: Path,
    new_csv: Path,
    output_dir: Path,
    cfg: EvalConfig,
) -> Dict[str, str]:
    """Execute full paired evaluation and persist all deliverables."""
    cfg.validate()

    base_df = read_input_csv(baseline_csv)
    new_df = read_input_csv(new_csv)
    check_duplicate_keys(base_df, "baseline")
    check_duplicate_keys(new_df, "new")

    join_stats = check_join_coverage(base_df, new_df, JOIN_MISMATCH_THRESHOLD)
    paired, mismatch_counts = prepare_paired(base_df, new_df)

    untracked_row_count = len(base_df.merge(new_df, on=["deal_id", "field_name"], how="inner")) - len(paired)
    present_fields = set(paired["field_name"].unique().tolist())
    missing_tracked_fields = [field for field in ALL_TRACKED_FIELDS if field not in present_fields]

    parse_stats = validate_parse_error_thresholds(paired)
    overall_metrics = build_overall_metrics(
        paired=paired,
        join_stats=join_stats,
        mismatch_counts=mismatch_counts,
        parse_stats=parse_stats,
        missing_tracked_fields=missing_tracked_fields,
        untracked_row_count=untracked_row_count,
        cfg=cfg,
    )

    field_metrics = build_field_metrics(paired, cfg)
    stratum_metrics = build_stratum_metrics(paired)
    rollout = build_rollout_decision(field_metrics, overall_metrics["overall_lift_gate_pass"])

    mismatch_rows = None
    if mismatch_counts["deal_type_mismatch_count"] or mismatch_counts["template_mismatch_count"]:
        mismatch_rows = paired[(paired["deal_type_mismatch"] == 1) | (paired["template_mismatch"] == 1)].copy()

    return write_artifacts(
        output_dir=output_dir,
        paired=paired,
        overall_metrics=overall_metrics,
        field_metrics=field_metrics,
        stratum_metrics=stratum_metrics,
        rollout=rollout,
        mismatch_rows=mismatch_rows,
    )
