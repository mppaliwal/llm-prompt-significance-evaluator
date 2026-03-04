# Prompt Stat Eval

Paired evaluation framework for trade confirmation field extraction (`baseline.csv` vs `new.csv`).

## Project layout

- `src/prompt_stat_eval/`
  - `config.py`: runtime config model
  - `validation.py`: schema checks, join coverage, paired row construction
  - `normalize.py`: missing/date/amount/rate/currency/text normalization and matching
  - `stats.py`: McNemar, bootstrap CI, Clopper-Pearson, metric tables
  - `reporting.py`: CSV/JSON/Markdown output writers
  - `pipeline.py`: orchestrates full evaluation run
  - `cli/`: package-native CLI entry points
- `streamlit_app.py`: UI for upload, run, and output download
- `pyproject.toml`: packaging + tooling config

## Quick setup (venv + install)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
```

## Input schema

Both CSV files must include:

- `deal_id`
- `deal_type`
- `template`
- `field_name`
- `golden_truth`
- `generated_value`

## CLI usage

Run evaluation:

```bash
prompt-stat-eval \
  --baseline data/baseline.csv \
  --new data/new.csv \
  --output-dir outputs \
  --bootstrap-samples 5000 \
  --seed 42 \
  --release-id R2026-03-03 \
  --date-range "2026-01-01 to 2026-02-29"
```

## Streamlit UI

```bash
prompt-stat-ui
```

Or:

```bash
streamlit run streamlit_app.py
```

## Outputs

Generated artifacts:

- `paired_eval.csv`
- `overall_metrics.json`
- `field_metrics.csv`
- `stratum_metrics.csv`
- `rollout_decision.csv`
- `signed_off_checklist.md`
- `metadata_mismatch_report.csv` (only when metadata mismatch exists)

## Quality gates and fail-fast behavior

- overall lift gate: `Lift >= 0.01`
- one-sided exact McNemar test (reported)
- default significance level fixed at `alpha = 0.05`
- McNemar interpretation rule: significant only if `p-value < alpha`
- critical fields: Clopper-Pearson upper 95% bound `<= 0.02`
- join mismatch threshold fixed at `0.0` (fail on any mismatch)
- parse-error threshold fixed at `5%` for `date`, `amount`, `rate`
- golden truth mismatch across baseline/new keys causes hard fail

## Dev workflows

```bash
ruff check src streamlit_app.py
mypy src
```

## Architecture Document

- `docs/architecture_presentation.md`
