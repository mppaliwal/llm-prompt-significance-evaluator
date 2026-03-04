"""Statistical routines and metric table builders."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
from scipy.stats import beta, binomtest

from .config import EvalConfig
from .constants import ALL_TRACKED_FIELDS, CRITICAL_FIELDS, resolve_tier

PARSE_ERROR_THRESHOLD = 0.05


def mcnemar_p_value(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    return float(binomtest(k=b, n=n, p=0.5, alternative="greater").pvalue)


def bootstrap_lift_ci(df: pd.DataFrame, n_boot: int, seed: int) -> Tuple[float, float]:
    n = len(df)
    rng = np.random.default_rng(seed)
    old = df["old_correct"].to_numpy(dtype=float)
    new = df["new_correct"].to_numpy(dtype=float)

    lifts = np.zeros(n_boot, dtype=float)
    for i in range(n_boot):
        idx = rng.integers(0, n, size=n)
        lifts[i] = float(np.mean(new[idx] - old[idx]))

    lo, hi = np.percentile(lifts, [2.5, 97.5])
    return float(lo), float(hi)


def clopper_pearson_upper(c: int, n: int, alpha: float = 0.05) -> float:
    if n == 0:
        return float("nan")
    if c >= n:
        return 1.0
    return float(beta.ppf(1 - alpha, c + 1, n - c))


def safe_mean(series: pd.Series) -> float:
    return float(series.mean()) if len(series) > 0 else float("nan")


def validate_parse_error_thresholds(paired: pd.DataFrame) -> Dict[str, dict]:
    stats: Dict[str, dict] = {}
    for ftype in ["date", "amount", "rate"]:
        base_mask = (paired["field_type"] == ftype) & (paired["gold_present"] == 1)
        denom = int(base_mask.sum())
        old_count = int((base_mask & (paired["old_parse_error"] == 1)).sum())
        new_count = int((base_mask & (paired["new_parse_error"] == 1)).sum())
        old_rate = (old_count / denom) if denom else 0.0
        new_rate = (new_count / denom) if denom else 0.0
        stats[ftype] = {
            "denominator": denom,
            "old_parse_error_count": old_count,
            "new_parse_error_count": new_count,
            "old_parse_error_rate": old_rate,
            "new_parse_error_rate": new_rate,
        }
        if denom and (old_rate > PARSE_ERROR_THRESHOLD or new_rate > PARSE_ERROR_THRESHOLD):
            raise ValueError(
                f"Parse failure rate exceeded threshold for {ftype}: "
                f"old_rate={old_rate:.4f}, new_rate={new_rate:.4f}, threshold={PARSE_ERROR_THRESHOLD:.4f}"
            )
    return stats


def build_overall_metrics(
    paired: pd.DataFrame,
    join_stats: Dict[str, float],
    mismatch_counts: Dict[str, int],
    parse_stats: Dict[str, dict],
    missing_tracked_fields: Iterable[str],
    untracked_row_count: int,
    cfg: EvalConfig,
) -> dict:
    acc_old = float(paired["old_correct"].mean())
    acc_new = float(paired["new_correct"].mean())
    lift = acc_new - acc_old
    b = int(paired["improvement"].sum())
    c = int(paired["regression"].sum())
    n_disagree = b + c
    p_val = mcnemar_p_value(b, c)
    ci_lo, ci_hi = bootstrap_lift_ci(paired, cfg.bootstrap_samples, cfg.seed)

    return {
        "run_timestamp_utc": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "release_id": cfg.release_id,
        "date_range": cfg.date_range,
        "n_rows_joined": int(len(paired)),
        "tracked_row_count": int(len(paired)),
        "untracked_row_count": int(untracked_row_count),
        "missing_tracked_fields": sorted(list(missing_tracked_fields)),
        "acc_old": acc_old,
        "acc_new": acc_new,
        "lift": lift,
        "lift_gate_abs_threshold": cfg.abs_lift_gate,
        "overall_lift_gate_pass": bool(lift >= cfg.abs_lift_gate),
        "b_improvements": b,
        "c_regressions": c,
        "n_disagree": n_disagree,
        "mcnemar_p_one_sided": p_val,
        "alpha": cfg.alpha,
        "mcnemar_significant_at_alpha": bool(p_val < cfg.alpha),
        "bootstrap_samples": cfg.bootstrap_samples,
        "bootstrap_seed": cfg.seed,
        "lift_ci_95": [ci_lo, ci_hi],
        "join_stats": join_stats,
        "metadata_mismatch_counts": mismatch_counts,
        "parse_error_stats": parse_stats,
    }


def build_field_metrics(paired: pd.DataFrame, cfg: EvalConfig) -> pd.DataFrame:
    rows: List[dict] = []

    for field_name in ALL_TRACKED_FIELDS:
        sub = paired[paired["field_name"] == field_name]
        tier = resolve_tier(field_name)
        n = int(len(sub))

        b = int(sub["improvement"].sum()) if n > 0 else 0
        c = int(sub["regression"].sum()) if n > 0 else 0
        n_disagree = b + c

        acc_old = safe_mean(sub["old_correct"])
        acc_new = safe_mean(sub["new_correct"])
        lift = (acc_new - acc_old) if n > 0 else float("nan")

        record = {
            "field_name": field_name,
            "tier": tier,
            "N": n,
            "Acc_old": acc_old,
            "Acc_new": acc_new,
            "Lift": lift,
            "b": b,
            "c": c,
            "n_disagree": n_disagree,
            "mcnemar_p": mcnemar_p_value(b, c) if n > 0 else float("nan"),
            "old_missing_count": int(sub["old_missing"].sum()) if n > 0 else 0,
            "new_missing_count": int(sub["new_missing"].sum()) if n > 0 else 0,
            "regression_ub_95": float("nan"),
            "critical_gate_pass": float("nan"),
        }

        if tier == "CRITICAL":
            crit_base = sub[sub["gold_present"] == 1]
            n_f = int(len(crit_base))
            c_f = int(crit_base["regression"].sum()) if n_f > 0 else 0
            ub = clopper_pearson_upper(c_f, n_f, alpha=cfg.alpha)
            record["regression_ub_95"] = ub
            record["critical_gate_pass"] = int(n_f > 0 and ub <= cfg.critical_ub_gate)

        rows.append(record)

    return pd.DataFrame(rows)


def build_stratum_metrics(paired: pd.DataFrame) -> pd.DataFrame:
    rows: List[dict] = []

    for (deal_type, template), sub in paired.groupby(["deal_type", "template"], dropna=False):
        b = int(sub["improvement"].sum())
        c = int(sub["regression"].sum())

        crit_ubs: List[float] = []
        for field in CRITICAL_FIELDS:
            crit_sub = sub[(sub["field_name"] == field) & (sub["gold_present"] == 1)]
            n_f = int(len(crit_sub))
            if n_f == 0:
                continue
            c_f = int(crit_sub["regression"].sum())
            crit_ubs.append(clopper_pearson_upper(c_f, n_f, alpha=0.05))

        acc_old = safe_mean(sub["old_correct"])
        acc_new = safe_mean(sub["new_correct"])
        rows.append(
            {
                "deal_type": deal_type,
                "template": template,
                "N": int(len(sub)),
                "Acc_old": acc_old,
                "Acc_new": acc_new,
                "Lift": acc_new - acc_old,
                "b": b,
                "c": c,
                "n_disagree": b + c,
                "mcnemar_p": mcnemar_p_value(b, c),
                "critical_max_regression_ub_95": float(max(crit_ubs)) if crit_ubs else float("nan"),
            }
        )

    return pd.DataFrame(rows).sort_values(["deal_type", "template"]).reset_index(drop=True)


def build_rollout_decision(field_metrics: pd.DataFrame, overall_lift_pass: bool) -> pd.DataFrame:
    rows: List[dict] = []

    for _, row in field_metrics.iterrows():
        field_name = str(row["field_name"])
        tier = str(row["tier"])
        n = int(row["N"])

        if n == 0:
            rows.append(
                {
                    "field_name": field_name,
                    "tier": tier,
                    "decision": "BLOCK",
                    "reason": "NOT_IN_DATA",
                }
            )
            continue

        if tier == "CRITICAL":
            if int(row["critical_gate_pass"]) == 1:
                decision, reason = "ALLOW", ""
            else:
                decision, reason = "BLOCK", "CRITICAL_UB_FAIL"
        else:
            if float(row["Acc_new"]) >= float(row["Acc_old"]):
                decision, reason = "ALLOW", ""
            else:
                decision, reason = "BLOCK", "GENERAL_ACCURACY_DROP"

        rows.append(
            {
                "field_name": field_name,
                "tier": tier,
                "decision": decision,
                "reason": reason,
            }
        )

    if not overall_lift_pass:
        rows.append(
            {
                "field_name": "__OVERALL__",
                "tier": "SUMMARY",
                "decision": "BLOCK",
                "reason": "OVERALL_GATE_FAIL",
            }
        )

    return pd.DataFrame(rows)
