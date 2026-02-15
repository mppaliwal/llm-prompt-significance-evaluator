#!/usr/bin/env python3
"""Evaluate v2 vs v1 structured extraction scores with paired analysis.

Input must be JSON and contain one row per (doc, field) unit with keys:
- doc_id
- field
- v1_score
- v2_score
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List


@dataclass
class UnitScore:
    doc_id: str
    field: str
    v1_score: float
    v2_score: float

    @property
    def diff(self) -> float:
        return self.v2_score - self.v1_score


def _validate_score(value: float, row_desc: str, allow_any: bool) -> float:
    if value not in (0.0, 0.5, 1.0) and not allow_any:
        raise ValueError(
            f"Invalid score {value!r} for {row_desc}. Allowed scores are 0.0, 0.5, 1.0 "
            "(or pass --allow-any-score)."
        )
    return float(value)


def load_json(path: Path, allow_any_score: bool) -> List[UnitScore]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("JSON input must be a list of objects.")

    rows: List[UnitScore] = []
    for i, r in enumerate(data, start=1):
        if not isinstance(r, dict):
            raise ValueError(f"JSON item {i} is not an object.")
        required = {"doc_id", "field", "v1_score", "v2_score"}
        missing = required - set(r.keys())
        if missing:
            raise ValueError(f"JSON item {i} is missing required keys: {sorted(missing)}")
        row_desc = f"JSON item {i}"
        rows.append(
            UnitScore(
                doc_id=str(r["doc_id"]),
                field=str(r["field"]),
                v1_score=_validate_score(float(r["v1_score"]), row_desc, allow_any_score),
                v2_score=_validate_score(float(r["v2_score"]), row_desc, allow_any_score),
            )
        )
    return rows


def load_units(path: Path, allow_any_score: bool) -> List[UnitScore]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return load_json(path, allow_any_score=allow_any_score)
    raise ValueError("Unsupported input file format. Use .json")


def one_sided_p_value_from_t(t_stat: float, df: int) -> float:
    """Compute one-sided p-value P(T >= t_stat), with SciPy required."""
    try:
        from scipy.stats import t as t_dist
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "SciPy is required for t-test p-value. Install with `pip install scipy`."
        ) from exc
    return float(1 - t_dist.cdf(t_stat, df))


def bootstrap_ci(diff_list: List[float], n_boot: int, rng: random.Random) -> tuple[float, float]:
    n = len(diff_list)
    boot_means: List[float] = []
    for _ in range(n_boot):
        sample = rng.choices(diff_list, k=n)
        boot_means.append(sum(sample) / n)
    boot_means.sort()
    lower_idx = int(0.025 * len(boot_means))
    upper_idx = int(0.975 * len(boot_means))
    return boot_means[lower_idx], boot_means[upper_idx]


def evaluate(units: Iterable[UnitScore], n_boot: int, seed: int, alpha: float) -> dict:
    unit_list = list(units)
    if not unit_list:
        raise ValueError("No rows found in input.")

    diffs = [u.diff for u in unit_list]
    v1_scores = [u.v1_score for u in unit_list]
    v2_scores = [u.v2_score for u in unit_list]

    n_total = len(diffs)
    mean_diff = sum(diffs) / n_total
    v1_mean = sum(v1_scores) / n_total
    v2_mean = sum(v2_scores) / n_total

    sd = statistics.pstdev(diffs)
    se = sd / math.sqrt(n_total) if n_total else float("nan")

    if se == 0.0:
        t_stat = math.inf if mean_diff > 0 else (-math.inf if mean_diff < 0 else 0.0)
        p_value = 0.0 if mean_diff > 0 else (1.0 if mean_diff < 0 else 0.5)
    else:
        t_stat = mean_diff / se
        p_value = one_sided_p_value_from_t(t_stat, n_total - 1)

    rng = random.Random(seed)
    ci_lower, ci_upper = bootstrap_ci(diffs, n_boot=n_boot, rng=rng)

    is_statistically_significant = (p_value < alpha) and (ci_lower > 0.0)

    return {
        "n_total": n_total,
        "v1_mean": v1_mean,
        "v2_mean": v2_mean,
        "mean_diff": mean_diff,
        "sd": sd,
        "se": se,
        "t_stat": t_stat,
        "df": n_total - 1,
        "p_value_one_sided": p_value,
        "bootstrap_ci_95": [ci_lower, ci_upper],
        "alpha": alpha,
        "is_statistically_significant": is_statistically_significant,
        "diff_list": diffs,
    }


def format_report(result: dict) -> str:
    ci = result["bootstrap_ci_95"]
    significant = "YES" if result["is_statistically_significant"] else "NO"
    lines = [
        f"n_total = {result['n_total']}",
        (
            "v1 mean = "
            f"{result['v1_mean']:.6f}, v2 mean = {result['v2_mean']:.6f}, "
            f"delta = {result['mean_diff']:.6f}"
        ),
        (
            "paired t-test (one-sided, H1: v2 > v1): "
            f"t = {result['t_stat']:.6f}, df = {result['df']}, p = {result['p_value_one_sided']:.6g}"
        ),
        f"bootstrap 95% CI (mean diff) = [{ci[0]:.6f}, {ci[1]:.6f}]",
        (
            "statistically significant improvement at "
            f"alpha={result['alpha']:.3f}: {significant}"
        ),
    ]
    return "\n".join(lines)


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Evaluate v2 vs v1 structured extraction scores with paired analysis."
    )
    p.add_argument("input", type=Path, help="Path to input .json")
    p.add_argument(
        "--bootstrap-samples",
        type=int,
        default=10_000,
        help="Number of bootstrap resamples (default: 10000)",
    )
    p.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    p.add_argument(
        "--alpha",
        type=float,
        default=0.05,
        help="Significance level for statistical decision (default: 0.05)",
    )
    p.add_argument(
        "--allow-any-score",
        action="store_true",
        help="Allow scores other than {0.0, 0.5, 1.0}",
    )
    p.add_argument(
        "--write-json",
        type=Path,
        help="Optional path to write machine-readable summary JSON",
    )
    return p


def main() -> None:
    args = build_arg_parser().parse_args()
    if not (0.0 < args.alpha < 1.0):
        raise ValueError("--alpha must be between 0 and 1.")
    units = load_units(args.input, allow_any_score=args.allow_any_score)
    result = evaluate(units, n_boot=args.bootstrap_samples, seed=args.seed, alpha=args.alpha)

    print(format_report(result))

    if args.write_json:
        args.write_json.write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
