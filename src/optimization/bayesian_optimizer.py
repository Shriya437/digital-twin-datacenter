"""Run Optuna tuning and compare fixed baseline vs tuned model on the same test set."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import optuna
from joblib import dump
from sklearn.metrics import (
    accuracy_score, f1_score, mean_absolute_error,
    mean_squared_error, r2_score, classification_report,
)

ROOT = Path(__file__).resolve().parents[2]
ML_LABELING_DIR = ROOT / "data" / "m100_labeling" / "ml_labeling"
sys.path.insert(0, str(ML_LABELING_DIR))

from src.optimization.model_spaces import (
    ALL_MODELS, REGRESSION_MODELS, CLASSIFICATION_MODELS, ANOMALY_MODELS,
    make_baseline_estimator, suggest_estimator,
)


def _classification_data(dataset: str, task: str):
    from classification_common import load_task, get_splits
    data_dir = ROOT / "data" / "m100_labeling" / "outputs" / "labeled_dataset"
    X, y, split = load_task(data_dir, dataset=dataset, task=task)
    tr, va, te = get_splits(split)
    return X, y, tr, va, te


def _regression_data(target: str, horizon: int):
    from src.predictive_maintenance import load_data, create_features
    df, available_metrics, median_interval_seconds = load_data()
    if target not in available_metrics:
        raise ValueError(f"Target '{target}' unavailable. Available: {available_metrics}")
    featured, feature_columns = create_features(df, available_metrics)
    grouped = featured.groupby("_segment", sort=False)
    featured["__future_target"] = grouped[target].shift(-horizon)
    if "split" in featured.columns:
        future_split = grouped["split"].shift(-horizon)
        same_split = featured["split"].astype(str).str.lower().eq(future_split.astype(str).str.lower())
        featured.loc[~same_split, "__future_target"] = np.nan
    data = featured.dropna(subset=["__future_target"]).copy()
    if "split" in data.columns:
        split = data["split"].astype(str).str.lower()
        data = data[split.isin(["train", "val", "validation", "test"])].copy()
        split = data["split"].astype(str).str.lower()
        tr = np.flatnonzero(split.eq("train").to_numpy())
        va = np.flatnonzero(split.isin(["val", "validation"]).to_numpy())
        te = np.flatnonzero(split.eq("test").to_numpy())
    else:
        n = len(data)
        a, b = int(n * .70), int(n * .85)
        tr, va, te = np.arange(a), np.arange(a, b), np.arange(b, n)
    if min(len(tr), len(va), len(te)) == 0:
        raise ValueError("Regression needs non-empty train, validation, and test splits.")
    X = data[feature_columns].replace([np.inf, -np.inf], np.nan).reset_index(drop=True)
    y = data["__future_target"].astype(float).reset_index(drop=True)
    return X, y, tr, va, te, median_interval_seconds


def _macro_f1(y_true, pred):
    return float(f1_score(y_true, pred, average="macro", zero_division=0))


def _regression_metrics(y_true, pred, target, horizon, interval):
    return {
        "MAE": float(mean_absolute_error(y_true, pred)),
        "RMSE": float(np.sqrt(mean_squared_error(y_true, pred))),
        "R2": float(r2_score(y_true, pred)) if len(y_true) > 1 else None,
        "target": target,
        "horizon_steps": int(horizon),
        "approx_horizon_minutes": round(horizon * interval / 60, 2),
    }


def _classification_metrics(y_true, pred, dataset, classification_task):
    return {
        "accuracy": float(accuracy_score(y_true, pred)),
        "macro_f1": _macro_f1(y_true, pred),
        "classification_report": classification_report(
            y_true, pred, output_dict=True, zero_division=0
        ),
        "dataset": dataset,
        "classification_task": classification_task,
    }


def _comparison(model_name, task, baseline_metrics, tuned_metrics):
    """Return a compact before/after comparison; positive improvement is better."""
    if task == "regression":
        keys = ("MAE", "RMSE", "R2")
        primary = "RMSE"
        direction = "lower_is_better"
    else:
        keys = ("accuracy", "macro_f1")
        primary = "macro_f1"
        direction = "higher_is_better"

    metrics = {}
    for key in keys:
        before = baseline_metrics.get(key)
        after = tuned_metrics.get(key)
        if before is None or after is None:
            metrics[key] = {"before": before, "after": after, "change": None}
            continue
        change = float(after - before)
        metrics[key] = {"before": float(before), "after": float(after), "change_after_minus_before": change}

    before_primary = float(baseline_metrics[primary])
    after_primary = float(tuned_metrics[primary])
    improved = after_primary < before_primary if direction == "lower_is_better" else after_primary > before_primary
    # Positive improvement means better regardless of metric direction.
    improvement = before_primary - after_primary if direction == "lower_is_better" else after_primary - before_primary
    percent = (improvement / abs(before_primary) * 100) if before_primary != 0 else None
    return {
        "model": model_name,
        "task": task,
        "primary_metric": primary,
        "optimization_direction": direction,
        "baseline_primary_score": before_primary,
        "optimized_primary_score": after_primary,
        "improved": bool(improved),
        "improvement_absolute": float(improvement),
        "improvement_percent_of_baseline": float(percent) if percent is not None else None,
        "metrics": metrics,
        "baseline_test_metrics": baseline_metrics,
        "optimized_test_metrics": tuned_metrics,
        "comparison_note": "Both versions use the same train+validation fit rows and the same held-out test rows.",
    }


def run_optimization(
    model_name: str,
    task: str = "auto",
    n_trials: int = 30,
    target: str = "p0_vdd_temp",
    horizon: int = 45,
    dataset: str = "synthetic",
    seed: int = 42,
    output_dir: str | Path | None = None,
):
    """Tune one model and compare its fixed baseline with tuned version on test data."""
    if model_name not in ALL_MODELS:
        raise ValueError(f"Unknown model '{model_name}'. Choose from: {sorted(ALL_MODELS)}")
    if n_trials < 1:
        raise ValueError("n_trials must be >= 1")

    if task == "auto":
        task = "regression" if model_name in REGRESSION_MODELS else (
            "anomaly" if model_name in ANOMALY_MODELS else "classification"
        )
    expected = (
        (model_name in REGRESSION_MODELS and task == "regression")
        or (model_name in CLASSIFICATION_MODELS and task == "classification")
        or (model_name in ANOMALY_MODELS and task == "anomaly")
    )
    if not expected:
        raise ValueError(f"{model_name} is not compatible with task='{task}'.")

    out = Path(output_dir) if output_dir else ROOT / "optimization_results"
    out.mkdir(parents=True, exist_ok=True)

    if task == "regression":
        X, y, tr, va, te, interval = _regression_data(target, horizon)
        X_train, y_train = X.iloc[tr], y.iloc[tr]
        X_val, y_val = X.iloc[va], y.iloc[va]
        X_test, y_test = X.iloc[te], y.iloc[te]
        direction = "minimize"

        def objective(trial):
            model = suggest_estimator(trial, model_name, seed, len(X_train))
            model.fit(X_train, y_train)
            pred = model.predict(X_val)
            return float(np.sqrt(mean_squared_error(y_val, pred)))

        study = optuna.create_study(direction=direction, sampler=optuna.samplers.TPESampler(seed=seed))
        study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
        X_fit, y_fit = pd.concat([X_train, X_val]), pd.concat([y_train, y_val])

        # Baseline: fixed, unoptimized hyperparameters, trained on the exact same rows.
        baseline_model = make_baseline_estimator(model_name, seed)
        baseline_model.fit(X_fit, y_fit)
        baseline_pred = baseline_model.predict(X_test)
        baseline_metrics = _regression_metrics(y_test, baseline_pred, target, horizon, interval)

        best_model = suggest_estimator(_FixedTrial(study.best_params), model_name, seed, len(X_fit))
        best_model.fit(X_fit, y_fit)
        tuned_pred = best_model.predict(X_test)
        tuned_metrics = _regression_metrics(y_test, tuned_pred, target, horizon, interval)
    else:
        classification_task = "binary" if task == "anomaly" else (
            "multiclass" if dataset == "synthetic" else "binary"
        )
        X, y, tr, va, te = _classification_data(dataset, classification_task)
        X_train, y_train = X.iloc[tr], y.iloc[tr]
        X_val, y_val = X.iloc[va], y.iloc[va]
        X_test, y_test = X.iloc[te], y.iloc[te]
        direction = "maximize"

        if task == "anomaly":
            normal_mask = np.asarray(y_train == 0)
            if normal_mask.sum() < 10:
                raise ValueError("Too few normal training samples for Isolation Forest.")
            X_fit_normal = X_train.iloc[np.flatnonzero(normal_mask)]

            def objective(trial):
                model = suggest_estimator(trial, model_name, seed, len(X_fit_normal))
                model.fit(X_fit_normal)
                pred = (model.predict(X_val) == -1).astype(int)
                return _macro_f1(y_val.astype(int), pred)
        else:
            def objective(trial):
                model = suggest_estimator(trial, model_name, seed, len(X_train))
                model.fit(X_train, y_train)
                pred = model.predict(X_val)
                return _macro_f1(y_val, pred)

        study = optuna.create_study(direction=direction, sampler=optuna.samplers.TPESampler(seed=seed))
        study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
        X_fit, y_fit = pd.concat([X_train, X_val]), pd.concat([y_train, y_val])

        baseline_model = make_baseline_estimator(model_name, seed)
        best_model = suggest_estimator(_FixedTrial(study.best_params), model_name, seed, len(X_fit))
        if task == "anomaly":
            # Isolation Forest is fitted on normal rows only for both baseline and tuned models.
            normal_fit_mask = np.asarray(y_fit == 0)
            X_fit_normal = X_fit.iloc[np.flatnonzero(normal_fit_mask)]
            baseline_model.fit(X_fit_normal)
            baseline_pred = (baseline_model.predict(X_test) == -1).astype(int)
            tuned_model_fit = X_fit_normal
            best_model.fit(tuned_model_fit)
            tuned_pred = (best_model.predict(X_test) == -1).astype(int)
            y_test_eval = y_test.astype(int)
        else:
            baseline_model.fit(X_fit, y_fit)
            baseline_pred = baseline_model.predict(X_test)
            best_model.fit(X_fit, y_fit)
            tuned_pred = best_model.predict(X_test)
            y_test_eval = y_test

        baseline_metrics = _classification_metrics(y_test_eval, baseline_pred, dataset, classification_task)
        tuned_metrics = _classification_metrics(y_test_eval, tuned_pred, dataset, classification_task)

    comparison = _comparison(model_name, task, baseline_metrics, tuned_metrics)
    stem = f"{model_name}_{task}"
    dump(best_model, out / f"{stem}_best_model.joblib")
    (out / f"{stem}_best_params.json").write_text(json.dumps(study.best_params, indent=2))
    (out / f"{stem}_test_metrics.json").write_text(json.dumps(tuned_metrics, indent=2, default=str))
    (out / f"{stem}_baseline_test_metrics.json").write_text(json.dumps(baseline_metrics, indent=2, default=str))
    (out / f"{stem}_before_after_comparison.json").write_text(json.dumps(comparison, indent=2, default=str))
    trials = study.trials_dataframe(attrs=("number", "value", "params", "state"))
    trials.to_csv(out / f"{stem}_trials.csv", index=False)
    summary = {
        "model": model_name, "task": task, "n_trials": n_trials,
        "best_validation_score": float(study.best_value),
        "optimization_direction": direction, "best_params": study.best_params,
        "baseline_test_metrics": baseline_metrics,
        "optimized_test_metrics": tuned_metrics,
        "before_after_comparison": comparison,
        "output_directory": str(out.resolve()),
    }
    (out / f"{stem}_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print("\nBEFORE vs AFTER BAYESIAN OPTIMIZATION")
    print(json.dumps(comparison, indent=2, default=str))
    print(f"Comparison saved to: {out / f'{stem}_before_after_comparison.json'}")
    return summary


class _FixedTrial:
    """Adapter using Optuna's FixedTrial to instantiate the selected parameters."""
    def __new__(cls, params):
        return optuna.trial.FixedTrial(params)
