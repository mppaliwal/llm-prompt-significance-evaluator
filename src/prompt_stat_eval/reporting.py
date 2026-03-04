"""Output writers for CSV/JSON/Markdown artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

import pandas as pd


def write_signed_off_checklist(
    out_path: Path,
    overall: dict,
    field_metrics: pd.DataFrame,
    rollout: pd.DataFrame,
    stratum_metrics: pd.DataFrame,
) -> None:
    crit = field_metrics[field_metrics["tier"] == "CRITICAL"].copy()
    blocked_general = rollout[
        (rollout["tier"] == "GENERAL") & (rollout["decision"] == "BLOCK")
    ]["field_name"].tolist()

    lines: List[str] = []
    lines.append("# Signed Off Checklist")
    lines.append("")
    lines.append(f"- Release ID: {overall['release_id']}")
    lines.append(f"- Date range: {overall['date_range']}")
    lines.append(f"- Run timestamp (UTC): {overall['run_timestamp_utc']}")
    lines.append("")
    lines.append("## Record Counts and Join Coverage")
    lines.append(f"- Joined rows: {overall['n_rows_joined']}")

    js = overall["join_stats"]
    lines.append(f"- Baseline key count: {js['baseline_key_count']}")
    lines.append(f"- New key count: {js['new_key_count']}")
    lines.append(f"- Baseline-only keys: {js['baseline_only_key_count']}")
    lines.append(f"- New-only keys: {js['new_only_key_count']}")
    lines.append(f"- Join mismatch ratio: {js['join_mismatch_ratio']:.6f}")

    mm = overall["metadata_mismatch_counts"]
    lines.append(f"- deal_type mismatch count: {mm['deal_type_mismatch_count']}")
    lines.append(f"- template mismatch count: {mm['template_mismatch_count']}")
    lines.append("")

    lines.append("## Overall Metrics")
    lines.append(f"- Acc_old: {overall['acc_old']:.6f}")
    lines.append(f"- Acc_new: {overall['acc_new']:.6f}")
    lines.append(f"- Lift: {overall['lift']:.6f}")
    lines.append(f"- Lift 95% CI: [{overall['lift_ci_95'][0]:.6f}, {overall['lift_ci_95'][1]:.6f}]")
    lines.append(f"- McNemar p (one-sided exact): {overall['mcnemar_p_one_sided']:.6g}")
    lines.append(f"- Alpha (significance level): {overall['alpha']:.2f}")
    lines.append(
        "- McNemar significance at alpha: "
        f"{int(overall['mcnemar_significant_at_alpha'])} "
        f"({'significant' if overall['mcnemar_significant_at_alpha'] else 'not significant'})"
    )
    lines.append(
        "- Interpretation: if McNemar p-value is below alpha, there is directional statistical "
        "evidence that the new system wins more paired disagreements than baseline."
    )
    lines.append(f"- Overall lift gate pass: {int(overall['overall_lift_gate_pass'])}")
    lines.append("")

    lines.append("## Critical Regression Risk")
    lines.append("- Critical gate rule: pass only when regression UB_95 <= 2.00%.")
    lines.append("- Any critical field with UB_95 > 2.00% is marked as failed/blocked.")
    lines.append("")
    lines.append("| field_name | N_f | c_f | ub_95 | pass | old_missing | new_missing |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for _, row in crit.iterrows():
        ub = row["regression_ub_95"]
        p = int(row["critical_gate_pass"]) if not pd.isna(row["critical_gate_pass"]) else 0
        lines.append(
            f"| {str(row['field_name'])} | {int(row['N'])} | {int(row['c'])} | {ub:.6f} | {p} | "
            f"{int(row['old_missing_count'])} | {int(row['new_missing_count'])} |"
        )
    lines.append("")

    lines.append("## Blocked General Fields")
    if blocked_general:
        for field_name in blocked_general:
            lines.append(f"- {field_name}")
    else:
        lines.append("- None")

    lines.append("")
    lines.append("## Stratified Summary (deal_type/template)")
    lines.append("| deal_type | template | N | Acc_old | Acc_new | Lift | b | c | McNemar p |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for _, row in stratum_metrics.iterrows():
        lines.append(
            f"| {row['deal_type']} | {row['template']} | {int(row['N'])} | "
            f"{float(row['Acc_old']):.6f} | {float(row['Acc_new']):.6f} | {float(row['Lift']):.6f} | "
            f"{int(row['b'])} | {int(row['c'])} | {float(row['mcnemar_p']):.6g} |"
        )

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_artifacts(
    output_dir: Path,
    paired: pd.DataFrame,
    overall_metrics: dict,
    field_metrics: pd.DataFrame,
    stratum_metrics: pd.DataFrame,
    rollout: pd.DataFrame,
    mismatch_rows: pd.DataFrame | None,
) -> Dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)

    paired_out = output_dir / "paired_eval.csv"
    overall_out = output_dir / "overall_metrics.json"
    field_out = output_dir / "field_metrics.csv"
    stratum_out = output_dir / "stratum_metrics.csv"
    rollout_out = output_dir / "rollout_decision.csv"
    checklist_out = output_dir / "signed_off_checklist.md"

    paired.to_csv(paired_out, index=False)
    field_metrics.to_csv(field_out, index=False)
    stratum_metrics.to_csv(stratum_out, index=False)
    rollout.to_csv(rollout_out, index=False)
    overall_out.write_text(json.dumps(overall_metrics, indent=2), encoding="utf-8")
    write_signed_off_checklist(checklist_out, overall_metrics, field_metrics, rollout, stratum_metrics)

    outputs = {
        "paired_eval_csv": str(paired_out),
        "overall_metrics_json": str(overall_out),
        "field_metrics_csv": str(field_out),
        "stratum_metrics_csv": str(stratum_out),
        "rollout_decision_csv": str(rollout_out),
        "signed_off_checklist_md": str(checklist_out),
    }

    if mismatch_rows is not None and not mismatch_rows.empty:
        mismatch_out = output_dir / "metadata_mismatch_report.csv"
        mismatch_rows.to_csv(mismatch_out, index=False)
        outputs["metadata_mismatch_report_csv"] = str(mismatch_out)

    return outputs
