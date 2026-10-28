"""Experimental regression comparison for future data-center temperature forecasting.

Compares Random Forest, HistGradientBoosting, Ridge, Gradient Boosting, a
VotingRegressor containing all four trial models, and a persistence baseline.
This file is intentionally separate from predictive_maintenance.py. It reuses the
project's existing data loader and lag/rolling feature engineering, but writes its
results to outputs/regression_experiments/ so existing outputs are not overwritten.

Run from the repository root:
    python -m src.compare_regression_models
    python -m src.compare_regression_models --target p0_vdd_temp --horizon 45
"""
from pathlib import Path
import argparse
import warnings

import numpy as np
import pandas as pd
from sklearn.ensemble import (
    RandomForestRegressor,
    HistGradientBoostingRegressor,
    GradientBoostingRegressor,
    VotingRegressor,
)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    balanced_accuracy_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.predictive_maintenance import load_data, create_features, RANDOM_STATE

warnings.filterwarnings("ignore", category=FutureWarning)
ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "outputs" / "regression_experiments"
# Alert threshold is estimated from TRAINING targets only (95th percentile).
# This is an experimental high-temperature event definition, not a hardware-validated alarm.


def make_pipeline(estimator, scale=False):
    """Impute missing feature values; scale only where useful."""
    steps = [("imputer", SimpleImputer(strategy="median"))]
    if scale:
        steps.append(("scaler", StandardScaler()))
    steps.append(("model", estimator))
    return Pipeline(steps)


def build_models():
    """Return all trial regressors and an ensemble containing all four."""
    random_forest = make_pipeline(
        RandomForestRegressor(
            n_estimators=200,
            min_samples_leaf=2,
            n_jobs=-1,
            random_state=RANDOM_STATE,
        )
    )
    hist_gradient_boosting = make_pipeline(
        HistGradientBoostingRegressor(
            max_iter=150,
            learning_rate=0.05,
            max_leaf_nodes=15,
            l2_regularization=1.0,
            random_state=RANDOM_STATE,
        )
    )
    ridge = make_pipeline(Ridge(alpha=1.0), scale=True)
    gradient_boosting = make_pipeline(
        GradientBoostingRegressor(
            n_estimators=80,
            learning_rate=0.05,
            max_depth=2,
            loss="squared_error",
            random_state=RANDOM_STATE,
        )
    )

    # Equal-weight averaging across every trial model. Each estimator is fitted
    # only on the training data; the test set is reserved for final evaluation.
    ensemble = VotingRegressor(
        estimators=[
            ("random_forest", random_forest),
            ("hist_gradient_boosting", hist_gradient_boosting),
            ("ridge", ridge),
            ("gradient_boosting", gradient_boosting),
        ]
    )
    return {
        "RandomForestRegressor": random_forest,
        "HistGradientBoostingRegressor": hist_gradient_boosting,
        "RidgeRegression": ridge,
        "GradientBoostingRegressor": gradient_boosting,
        "VotingEnsemble_AllFour": ensemble,
    }


def chronological_split(data, horizon_steps):
    """Use the project's supplied splits when available; otherwise split by time."""
    if "split" in data.columns:
        split = data["split"].astype(str).str.lower()
        train_mask = split.eq("train")
        val_mask = split.isin(["val", "validation"])
        test_mask = split.eq("test")
        if train_mask.any() and test_mask.any():
            # Train final comparison models on train + validation; reserve test.
            train_idx = np.flatnonzero((train_mask | val_mask).to_numpy())
            test_idx = np.flatnonzero(test_mask.to_numpy())
            if len(train_idx) >= 20 and len(test_idx) >= 5:
                return train_idx, test_idx

    # Fallback: earliest 85% for training and latest 15% for testing, with a
    # horizon-sized gap so training labels do not reach into the test period.
    n = len(data)
    test_start = int(n * 0.85)
    train_end = max(0, test_start - horizon_steps)
    train_idx = np.arange(0, train_end)
    test_idx = np.arange(test_start, n)
    if len(train_idx) < 20 or len(test_idx) < 5:
        raise ValueError("Not enough rows for a chronological train/test split.")
    return train_idx, test_idx



def metric_row(name, actual, predicted, alert_threshold):
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)

    valid = np.isfinite(actual) & np.isfinite(predicted)
    actual, predicted = actual[valid], predicted[valid]

    if not len(actual):
        raise ValueError(f"No valid predictions to evaluate for {name}.")

    # Regression metrics: compare predicted temperatures with actual values.
    mae = mean_absolute_error(actual, predicted)
    rmse = float(np.sqrt(mean_squared_error(actual, predicted)))
    r2 = r2_score(actual, predicted) if len(actual) > 1 else np.nan

    nonzero = actual != 0
    mape = (
        float(
            np.mean(
                np.abs(
                    (actual[nonzero] - predicted[nonzero])
                    / actual[nonzero]
                )
            ) * 100
        )
        if nonzero.any()
        else np.nan
    )

    # Supplementary event-detection metrics. The same threshold, estimated from
    # training targets only, is used for every model and the persistence baseline.
    actual_alert = (actual >= alert_threshold).astype(int)
    predicted_alert = (predicted >= alert_threshold).astype(int)
    actual_events = int(actual_alert.sum())
    predicted_events = int(predicted_alert.sum())
    tp = int(np.sum((actual_alert == 1) & (predicted_alert == 1)))
    tn = int(np.sum((actual_alert == 0) & (predicted_alert == 0)))
    fp = int(np.sum((actual_alert == 0) & (predicted_alert == 1)))
    fn = int(np.sum((actual_alert == 1) & (predicted_alert == 0)))

    accuracy = accuracy_score(actual_alert, predicted_alert)
    # Precision is undefined when the model predicts no events; recall is
    # undefined when the test set contains no actual events. Report NaN rather
    # than presenting those undefined cases as a genuine zero score.
    precision = (
        float(precision_score(actual_alert, predicted_alert, zero_division=0))
        if predicted_events > 0 else np.nan
    )
    recall = (
        float(recall_score(actual_alert, predicted_alert, zero_division=0))
        if actual_events > 0 else np.nan
    )
    f1 = (
        float(f1_score(actual_alert, predicted_alert, zero_division=0))
        if actual_events > 0 and predicted_events > 0 else np.nan
    )
    balanced_accuracy = (
        float(balanced_accuracy_score(actual_alert, predicted_alert))
        if len(np.unique(actual_alert)) == 2 else np.nan
    )

    return {
        "model": name,
        "test_samples": int(len(actual)),
        "MAE": float(mae),
        "RMSE": rmse,
        "R2": float(r2),
        "MAPE_percent": mape,
        "Accuracy": float(accuracy),
        "Precision": float(precision),
        "Recall": float(recall),
        "F1": f1,
        "BalancedAccuracy": balanced_accuracy,
        "AlertThreshold_C": float(alert_threshold),
        "ActualHighTempEvents": actual_events,
        "PredictedHighTempEvents": predicted_events,
        "TP": tp,
        "TN": tn,
        "FP": fp,
        "FN": fn,
    }



def run(target="p0_vdd_temp", horizon_steps=45):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df, available_metrics, median_interval_seconds = load_data()
    if target not in available_metrics:
        raise ValueError(f"Target '{target}' is unavailable. Available targets: {available_metrics}")

    featured, feature_columns = create_features(df, available_metrics)
    grouped = featured.groupby("_segment", sort=False)
    featured["future_target"] = grouped[target].shift(-horizon_steps)
    featured["target_timestamp"] = grouped["timestamp"].shift(-horizon_steps)

    # If the source has official train/validation/test splits, do not let a
    # training label look into a different partition. The source also has purge
    # rows; those rows are excluded from model fitting/evaluation below.
    if "split" in featured.columns:
        future_split = grouped["split"].shift(-horizon_steps)
        featured.loc[featured["split"].astype(str) != future_split.astype(str), "future_target"] = np.nan
        featured.loc[featured["split"].astype(str) != future_split.astype(str), "target_timestamp"] = pd.NaT

    # Drop rows without a future target/time. Missing feature values are handled
    # inside each model pipeline, not by dropping potentially useful rows.
    data = featured.dropna(subset=["future_target", "target_timestamp"]).copy()
    if "split" in data.columns:
        data = data[data["split"].astype(str).str.lower().isin(["train", "val", "validation", "test"])].copy()
    data = data.reset_index(drop=True)
    if len(data) < 50:
        raise ValueError(f"Only {len(data)} rows have a valid future target; need more data.")

    train_idx, test_idx = chronological_split(data, horizon_steps)
    X = data[feature_columns].replace([np.inf, -np.inf], np.nan)
    y = data["future_target"].astype(float)
    X_train, y_train = X.iloc[train_idx], y.iloc[train_idx]
    X_test, y_test = X.iloc[test_idx], y.iloc[test_idx]

    models = build_models()
    # Do not hard-code 50 C without a documented hardware/policy basis. Define
    # an experimental high-temperature event using the 95th percentile of the
    # training targets only; this avoids leaking test-set information.
    alert_threshold = float(np.quantile(y_train, 0.95))
    print(
        f"\nExperimental high-temperature threshold: {alert_threshold:.3f} C "
        "(95th percentile of training targets; not a validated hardware alarm)"
    )
    results = []
    predictions = pd.DataFrame({
        "timestamp": data.loc[test_idx, "timestamp"].astype(str).to_numpy(),
        "target_timestamp": data.loc[test_idx, "target_timestamp"].astype(str).to_numpy(),
        "actual_future_temperature": y_test.to_numpy(),
        "persistence_prediction": data.loc[test_idx, target].to_numpy(),
    })
    results.append(metric_row("PersistenceBaseline", y_test, predictions["persistence_prediction"], alert_threshold))

    for name, model in models.items():
        print(f"Training {name}...")
        model.fit(X_train, y_train)
        pred = model.predict(X_test)
        predictions[f"pred_{name}"] = pred
        results.append(metric_row(name, y_test, pred, alert_threshold))

    results_df = pd.DataFrame(results).sort_values("RMSE").reset_index(drop=True)
    results_df.insert(1, "target", target)
    results_df.insert(2, "horizon_steps", horizon_steps)
    results_df.insert(3, "approx_horizon_minutes", round(horizon_steps * median_interval_seconds / 60, 2))

    metrics_path = OUTPUT_DIR / f"regression_metrics_{target}_{horizon_steps}_steps.csv"
    predictions_path = OUTPUT_DIR / f"regression_predictions_{target}_{horizon_steps}_steps.csv"
    results_df.to_csv(metrics_path, index=False)
    predictions.to_csv(predictions_path, index=False)

    print("\nRegression comparison (lower MAE/RMSE is better; higher R2 is better):")
    print(
    results_df[
        [
            "model",
            "test_samples",
            "MAE",
            "RMSE",
            "R2",
            "MAPE_percent",
            "Accuracy",
            "Precision",
            "Recall",
            "F1",
            "BalancedAccuracy",
            "AlertThreshold_C",
            "ActualHighTempEvents",
            "PredictedHighTempEvents",
            "TP",
            "TN",
            "FP",
            "FN",
        ]
    ].to_string(index=False)
)
    print(f"\nMetrics saved to: {metrics_path}")
    print(f"Predictions saved to: {predictions_path}")
    print(
        "Note: MAE/RMSE/R2 are the primary regression metrics. Classification "
        "metrics describe an experimental training-derived threshold and are "
        "not a validated hardware alarm. Offline outputs only; production was unchanged."
    )
    return results_df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare regression models for future telemetry temperature forecasting.")
    parser.add_argument("--target", default="p0_vdd_temp", help="Telemetry target column, e.g. p0_vdd_temp or p1_vdd_temp")
    parser.add_argument("--horizon", type=int, default=45, help="Number of rows ahead to predict; default 45 (the existing 15-minute horizon)")
    args = parser.parse_args()
    run(target=args.target, horizon_steps=args.horizon)