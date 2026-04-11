"""Configuration models for prompt statistical evaluation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EvalConfig:
    """Runtime configuration for paired evaluation."""

    bootstrap_samples: int = 5000
    seed: int = 42
    abs_lift_gate: float = 0.01
    critical_ub_gate: float = 0.02
    alpha: float = 0.05
    release_id: str = "local-eval"
    date_range: str = "N/A"

    def validate(self) -> None:
        if self.bootstrap_samples <= 0:
            raise ValueError("bootstrap_samples must be > 0")
        if not (0.0 < self.alpha < 1.0):
            raise ValueError("alpha must be in (0, 1)")
