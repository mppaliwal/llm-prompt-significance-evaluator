# Prompt Stat Eval Architecture Presentation

## 1. Objective
- Evaluate a new prompt set vs baseline for structured field extraction.
- Use paired statistical analysis to support rollout decisions.
- Protect high-priority fields using strict regression-risk gates.

## 2. Problem Statement
- Overall quality may improve while important fields regress.
- A single aggregate score is not enough for release decisions.
- Need explainable, auditable, and field-level rollout control.

## 3. System Scope
- Inputs:
  - `baseline.csv`
  - `new.csv`
- Core processing:
  - validation
  - normalization
  - paired scoring
  - statistics
  - rollout gating
  - reporting
- Outputs:
  - `paired_eval.csv`
  - `overall_metrics.json`
  - `field_metrics.csv`
  - `segment_metrics.csv`
  - `rollout_decision.csv`
  - `review_checklist.md`

## 4. High-Level Architecture
```mermaid
flowchart LR
    A[baseline.csv] --> V[Validation + Pair Join]
    B[new.csv] --> V
    V --> N[Normalization + Correctness Scoring]
    N --> S[Stats Engine]
    S --> G[Gate Engine]
    G --> R[Report Writers]
    R --> O1[overall_metrics.json]
    R --> O2[field_metrics.csv]
    R --> O3[rollout_decision.csv]
    R --> O4[segment_metrics.csv]
    R --> O5[paired_eval.csv]
    R --> O6[review_checklist.md]
```

## 5. Code Component Map
- Package root: `src/prompt_stat_eval/`
- `config.py`
  - runtime configuration (`EvalConfig`)
- `validation.py`
  - schema checks, duplicate keys, join coverage, paired dataset construction
- `normalize.py`
  - missing handling, date/number/code/text normalization + correctness logic
- `stats.py`
  - McNemar, bootstrap CI, Clopper-Pearson, metric tables, parse-threshold fail-fast
- `reporting.py`
  - writes CSV/JSON/Markdown deliverables
- `pipeline.py`
  - orchestrates end-to-end run
- UI:
  - `streamlit_app.py`
- Optional local generator (outside main codebase):
  - `local_tools/synthesize_sample_data.py`

## 6. Data Contract
- Required columns in both input CSVs:
  - `record_id`, `record_type`, `document_group`, `field_name`, `expected_value`, `generated_value`
- Join key:
  - `(record_id, field_name)`
- Fail-fast checks:
  - missing required columns
  - duplicate keys
  - join key mismatch above threshold
  - expected value mismatch for same joined key
  - parse-failure rate above threshold

## 7. Field Model
- Tier 1 (Critical, 5 fields):
  - `primary_date`, `amount_value`, `completion_date`, `end_date`, `category_code`
- Tier 2 (General, 15 fields):
  - `secondary_date`, `start_date`, `effective_date`, `rate_value`, `rate_frequency`, `rule_type`, `adjustment_rule`, `reference_code`, `delta_value`, `value_type`, `price_value`, `derived_amount`, `total_value`, `direction_label`, `entity_name`
- Field type mapping:
  - hardcoded by `field_name`
  - fallback type: `text`

## 8. Correctness Logic
- Missing token handling:
  - `""`, `NO_DATA_FOUND`, `NULL`, `N/A` (case-insensitive)
- Date:
  - parse as `DD/MM/YYYY` (minor day/month width variation accepted)
  - compare canonical date values
- Number/Rate:
  - parse numeric values from realistic formatted strings
  - tolerance:
    - `abs(x - y) <= max(0.01, 1e-4 * max(1, |y|))`
- Code:
  - normalized exact match
- Text:
  - normalized exact match
- Missing expected-value policy:
  - missing/missing = correct
  - missing/present = incorrect
  - present/missing = incorrect

## 9. Statistical Engine
- Paired accuracy:
  - `Acc_old`, `Acc_new`, `Lift = Acc_new - Acc_old`
- Disagreement counts:
  - `b = improvements`, `c = regressions`
- Evidence:
  - exact one-sided McNemar via binomial
- Uncertainty:
  - paired bootstrap 95% CI for lift

## 10. Gate Design
- Overall gate:
  - pass if `Lift >= 0.01`
- Critical field safety gate:
  - for each critical field, compute regression upper bound (95% Clopper-Pearson)
  - pass if `ub <= 0.02`
- General field rollout rule:
  - `ALLOW` if `Acc_new >= Acc_old`, else `BLOCK`
- Important:
  - overall gate and critical gates are independent checks

## 11. Decision Flow
```mermaid
flowchart TD
    A[Compute overall lift] --> B{Lift >= 1%?}
    B -- No --> C[Overall Gate Fail]
    B -- Yes --> D[Overall Gate Pass]
    D --> E[Evaluate critical UB per field]
    C --> E
    E --> F{Any critical UB > 2%?}
    F -- Yes --> G[Block failing critical fields]
    F -- No --> H[Critical fields pass]
    G --> I[General field allow/block by accuracy delta]
    H --> I
    I --> J[Publish rollout_decision.csv]
```

## 12. Output Artifacts
- `paired_eval.csv`
  - row-level paired correctness + improvement/regression flags
- `overall_metrics.json`
  - global accuracy, lift, CI, McNemar, join/parse diagnostics
- `field_metrics.csv`
  - per-field performance, missing stats, critical UB/pass
- `segment_metrics.csv`
  - grouped by `record_type` and `document_group`
- `rollout_decision.csv`
  - field-level `ALLOW/BLOCK` + reason
- `review_checklist.md`
  - release-ready summary

## 13. Runtime Interfaces
- CLI:
  - `prompt-stat-eval --baseline data/baseline.csv --new data/new.csv --output-dir outputs`
- UI:
  - `streamlit run streamlit_app.py`

## 14. Operational Considerations
- Reproducibility:
  - controlled bootstrap seed
- Auditability:
  - deterministic outputs for same inputs/config
- Safety:
  - fail-fast on bad joins, expected-value mismatches, or excessive parse failures
- Usability:
  - simplified Streamlit flow: upload files and run with code defaults
