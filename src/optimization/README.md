# Bayesian optimization with before/after comparison

Place these files under the repository root in `src/optimization/` and merge `optuna>=3.6` into the root `requirements.txt`.

## Run

```powershell
python -m pip install -r requirements.txt
python -m src.optimization.run_optimization --model random_forest_regressor --trials 3
python -m src.optimization.run_optimization --model all --trials 3
```

Increase to `--trials 30` or more for a broader search after the quick test works.

## What is compared?

For each model, this code evaluates two versions on the **same held-out test rows**:

1. **Before / baseline:** a fixed, unoptimized model configuration.
2. **After / tuned:** the model instantiated with the best hyperparameters found by Optuna.

Both versions are fitted on the same training + validation rows. Optuna uses validation data only; the test set is held out from trial selection.

- Regression: the main comparison metric is RMSE (lower is better), with MAE and R² also reported.
- Classification: the main comparison metric is macro-F1 (higher is better), with accuracy also reported.
- Isolation Forest: both versions are fitted only on normal training + validation rows, then evaluated against binary anomaly labels.

## Output files

The `optimization_results/` directory contains the usual trial and model artifacts plus:

- `<model>_<task>_baseline_test_metrics.json` — baseline test metrics
- `<model>_<task>_test_metrics.json` — tuned model test metrics
- `<model>_<task>_before_after_comparison.json` — detailed side-by-side comparison
- `before_after_comparison.csv` — combined comparison for every model in the run

`improved` is based on RMSE for regression and macro-F1 for classification/anomaly. `improvement_percent_of_baseline` is positive when the primary metric improves, regardless of whether the metric is minimized or maximized. A true value means the tuned model improved the primary test metric compared with the fixed baseline. Test scores are for comparison after tuning, not for choosing Optuna trials.

## Dataset notes

Regression uses `src.predictive_maintenance.load_data()` and `create_features()`. Classification uses `data/m100_labeling/ml_labeling/classification_common.py`. The default classification dataset is synthetic; observed labels are heuristic proxies, not verified hardware-fault ground truth.

This is an experimental module and does not replace models used by the dashboard or production API automatically.
