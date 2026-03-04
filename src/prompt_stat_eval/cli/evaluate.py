"""CLI for paired evaluation."""

from __future__ import annotations

import argparse
from pathlib import Path

from prompt_stat_eval.config import EvalConfig
from prompt_stat_eval.pipeline import run_evaluation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Paired evaluation with McNemar evidence and per-field rollout gates."
    )
    parser.add_argument("--baseline", type=Path, default=Path("data/baseline.csv"), help="Path to baseline.csv")
    parser.add_argument("--new", type=Path, default=Path("data/new.csv"), help="Path to new.csv")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"), help="Output directory")
    parser.add_argument(
        "--bootstrap-samples",
        type=int,
        default=5000,
        help="Bootstrap samples for lift CI (default: 5000)",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed for bootstrap")
    parser.add_argument("--release-id", type=str, default="local-eval", help="Release identifier")
    parser.add_argument("--date-range", type=str, default="N/A", help="Date range label")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    cfg = EvalConfig(
        bootstrap_samples=args.bootstrap_samples,
        seed=args.seed,
        release_id=args.release_id,
        date_range=args.date_range,
    )

    outputs = run_evaluation(
        baseline_csv=args.baseline,
        new_csv=args.new,
        output_dir=args.output_dir,
        cfg=cfg,
    )
    for key, value in outputs.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
