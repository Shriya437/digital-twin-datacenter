# M100 ExaData labeled datasets (heuristic + simulated)

Adds supervised-learning targets to the M100 node-1 telemetry **without modifying the original CSV**.
Three kinds of information are kept strictly apart:

| kind | where | trust |
|---|---|---|
| **observed telemetry** | the 14 original columns, unchanged | real |
| **derived heuristic labels** | `anomaly_label`, `fault_type`, `anomaly_within_next_15`, `rule_*` in the observed file | *proxy* from transparent rules; **not verified faults** |
| **simulated faults** | `m100_synthetic_fault_scenarios.csv` (`data_origin=synthetic`) | ground truth *only inside the simulation* |

There are no real failure, maintenance or RUL records, and none were invented.

## Layout (drop-in for the existing repo; same `BASE_DIR/data`, `BASE_DIR/outputs` convention)
```
ml_labeling/labeling.py              loader, segments, causal features, reference model, rules, splits
ml_labeling/simulation.py            fault injection on copies of observed windows
ml_labeling/build_labeled_dataset.py CLI: builds datasets, validation, schema, report, figures
ml_labeling/docs.py                  data dictionary + report writer
ml_labeling/train_baselines.py       baseline models (chronological protocol)
run_all.sh                           build + train
outputs/labeled_dataset/             all generated files
```
Existing modules are not touched. Only pandas, numpy, scikit-learn and matplotlib are used (`tabulate` is optional, for nicer markdown tables). `labeling.causal_features` mirrors the naming/gap rule of `feature_engineering_1.py` (the repo's `data_loader` was not uploaded, so it is re-implemented rather than imported).

## Reproduce
```bash
bash run_all.sh data/m100_node1_digital_twin.csv outputs/labeled_dataset
# or step by step
python ml_labeling/build_labeled_dataset.py --input data/m100_node1_digital_twin.csv --output-dir outputs/labeled_dataset
python ml_labeling/train_baselines.py --data-dir outputs/labeled_dataset
```
Seeded (42); a second run produces byte-identical files.

## Files in `outputs/labeled_dataset/`
- `m100_node1_labeled_observed.csv` - 4,917 rows; original columns first, then provenance/labels.
- `m100_synthetic_fault_scenarios.csv` - 16,200 rows, 90 scenarios x 180 steps; every row has `scenario_id`, `base_row_id`, `injected_fault_type`, `synthetic_label`.
- `label_schema.md/.csv` (data dictionary), `labeling_report.md` (counts, coverage, gaps, missing values, assumptions, limitations, validation), `labeling_params.json` (every threshold/parameter), `model_results.md/.json`, `figures/`.

## How to use for supervised learning
1. **Split with the `split` column** (`train`/`val`/`test`, chronological 60/20/20). **Drop `purge` rows.** For synthetic data use the scenario's own `split`; whole scenarios never cross splits.
2. **Binary detection:** train on `label_valid==1`, target `anomaly_label`. Blank labels (ambiguous / insufficient context) are *excluded*, not treated as normal.
3. **Features:** compute with `labeling.causal_features(df, segment_id)` (past-only, never crosses a gap). **Never use `rule_*` columns as features** - they are the labeler's evidence; the leakage check in `model_results.md` (T1b) shows PR-AUC rising from 0.24 to 0.91 when they are included.
4. **Future anomaly:** target `anomaly_within_next_15` (5 min), evaluated on rows with current `anomaly_label==0` (onset prediction). It is a heuristic-event horizon, not remaining life.
5. **Multiclass `fault_type`:** only fan/power classes exist in train; thermal/combined appear only in val/test (see limits). Use the synthetic file for class-balanced experiments.
6. **Synthetic vs observed:** report them separately. `synthetic_severity_stage` is injected intensity, not time-to-failure.

## Key limitations (details in `labeling_report.md`)
- Heuristic labels teach a model the rule; they are not evidence of real faults.
- Only ~27 h of samples in 4 segments; anomalies are 104 rows (2.3 %): train 23 (fan/power only), val 17, test 62 (mostly one heat event with ambient up to 37 and fan up to 10,100). Power anomalies: 4 rows.
- Units are undocumented; no manufacturer limits were used.
- Simulation couplings (fan->temperature, p1 = 0.8 x p0 offset, PSU drift ranges) are assumptions, not measured physics. The heuristic rules detect only ~53 % of injected-active rows (power 2.5 %), so synthetic labels are *not* a rule reproduction.
