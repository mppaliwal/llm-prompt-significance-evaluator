# Prompt v2 vs v1 Evaluation (Paired, Partial-Credit)

This repo contains a script to evaluate whether prompt **v2** improves structured extraction quality over **v1** using a paired design.

Each evaluation unit is `(doc_id, field)` with partial correctness scoring:
- `1.0` = fully correct
- `0.5` = partially correct
- `0.0` = incorrect

## What the script computes

For each unit:
- `diff = v2_score - v1_score`

Then it reports:
- `v1` mean score
- `v2` mean score
- mean paired difference (`delta`)
- paired one-sided t-test p-value (`H1: v2 > v1`)
- bootstrap 95% CI for mean difference
- final significance verdict (`YES`/`NO`)

A result is marked **statistically significant** when both are true:
- one-sided t-test p-value `< alpha`
- bootstrap CI lower bound `> 0`

Default `alpha = 0.05`.

## Input format (JSON only)

Use a JSON array of objects with these keys:
- `doc_id` (string)
- `field` (string)
- `v1_score` (float)
- `v2_score` (float)

Example:

```json
[
  {
    "doc_id": "D1",
    "field": "net_revenue",
    "v1_score": 0.0,
    "v2_score": 1.0
  }
]
```

By default, valid scores are restricted to `{0.0, 0.5, 1.0}`.
Use `--allow-any-score` to disable that check.

## Usage

Install dependency:

```bash
pip install scipy
```

Run evaluation:

```bash
python3 evaluate_prompt_versions.py prompt_scores.json
```

Write machine-readable output:

```bash
python3 evaluate_prompt_versions.py prompt_scores.json --write-json report.json
```

Optional arguments:
- `--bootstrap-samples 10000` (default `10000`)
- `--seed 42` (default `42`)
- `--alpha 0.05` (default `0.05`)
- `--allow-any-score`

## Files

- `evaluate_prompt_versions.py`: evaluation script
- `prompt_scores.json`: expanded sample dataset
- `report.json`: example output from running the script
