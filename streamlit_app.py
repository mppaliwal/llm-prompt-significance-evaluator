"""Streamlit UI for paired prompt statistical evaluation."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from prompt_stat_eval.config import EvalConfig  # noqa: E402
from prompt_stat_eval.pipeline import run_evaluation  # noqa: E402


def _to_percent(x: float) -> str:
    return f"{x * 100:.2f}%"


st.set_page_config(page_title="Prompt Stat Eval", layout="wide")
st.title("Trade Confirmation Prompt Evaluation")
st.caption("Compare baseline vs new prompt outputs and get clear rollout decisions.")

st.markdown("### Step 1: Upload Input Files")
left, right = st.columns(2)
with left:
    baseline_file = st.file_uploader("Baseline CSV (`baseline.csv`)", type=["csv"])
with right:
    new_file = st.file_uploader("New Prompt CSV (`new.csv`)", type=["csv"])

st.markdown("### Step 2: Evaluate")
run_clicked = st.button("Run Evaluation", type="primary")

if run_clicked:
    if baseline_file is None or new_file is None:
        st.error("Upload both baseline.csv and new.csv before running evaluation.")
    else:
        try:
            cfg = EvalConfig()

            with tempfile.TemporaryDirectory(prefix="prompt_stat_eval_") as tmp_dir:
                tmp_path = Path(tmp_dir)
                baseline_path = tmp_path / "baseline.csv"
                new_path = tmp_path / "new.csv"
                output_dir = tmp_path / "outputs"

                baseline_path.write_bytes(baseline_file.getvalue())
                new_path.write_bytes(new_file.getvalue())

                output_paths = run_evaluation(
                    baseline_csv=baseline_path,
                    new_csv=new_path,
                    output_dir=output_dir,
                    cfg=cfg,
                )

                overall = json.loads((output_dir / "overall_metrics.json").read_text(encoding="utf-8"))
                field_metrics = pd.read_csv(output_dir / "field_metrics.csv")
                rollout = pd.read_csv(output_dir / "rollout_decision.csv")
                stratum_metrics = pd.read_csv(output_dir / "stratum_metrics.csv")

                st.success("Evaluation completed.")
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Baseline Accuracy", _to_percent(overall["acc_old"]))
                m2.metric("New Prompt Accuracy", _to_percent(overall["acc_new"]))
                m3.metric("Accuracy Improvement", _to_percent(overall["lift"]))
                m4.metric("Overall Gate", "Pass" if overall["overall_lift_gate_pass"] else "Fail")

                signif_text = "Significant" if overall["mcnemar_significant_at_alpha"] else "Not Significant"
                st.info(
                    "Statistical Evidence: "
                    f"McNemar one-sided p-value = {overall['mcnemar_p_one_sided']:.6g}, "
                    f"alpha = {overall['alpha']:.2f}, result = {signif_text}."
                )
                st.caption(
                    "Interpretation: if p-value < alpha, there is directional statistical evidence "
                    "that the new system wins more paired disagreements than baseline."
                )

                tabs = st.tabs(
                    [
                        "Rollout Decision",
                        "Field Metrics",
                        "Segment Metrics",
                        "Download Results",
                    ]
                )
                with tabs[0]:
                    st.dataframe(rollout, use_container_width=True)
                with tabs[1]:
                    st.dataframe(field_metrics, use_container_width=True)
                with tabs[2]:
                    st.dataframe(stratum_metrics, use_container_width=True)
                with tabs[3]:
                    for name, path_str in output_paths.items():
                        file_path = Path(path_str)
                        st.download_button(
                            label=f"Download {name}",
                            data=file_path.read_bytes(),
                            file_name=file_path.name,
                            mime="text/csv" if file_path.suffix == ".csv" else "application/json",
                            key=name,
                        )
        except ValueError as exc:
            msg = str(exc)
            if "Parse failure rate exceeded threshold" in msg:
                st.error(
                    f"{msg}\n\nTip: regenerate cleaner synthetic data or validate date/amount/rate formats in input files."
                )
            else:
                st.error(msg)
        except Exception as exc:
            st.exception(exc)
