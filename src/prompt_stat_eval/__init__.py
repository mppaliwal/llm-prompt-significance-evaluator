"""Prompt statistical evaluation package."""

from .config import EvalConfig
from .pipeline import run_evaluation

__all__ = ["EvalConfig", "run_evaluation"]
