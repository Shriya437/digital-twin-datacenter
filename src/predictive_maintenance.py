"""
Predictive Maintenance Module
Data Center Digital Twin

Features:
1. Temperature forecasting
2. Persistence baseline comparison
3. Random Forest and HistGradientBoosting models
4. Forecast evaluation using MAE, RMSE and R2
5. Standardized prediction output
6. Degradation indicators
7. Isolation Forest anomaly detection
8. Temperature early warnings
9. Future temperature warnings
10. Model and output artifact saving
"""

from pathlib import Path
import warnings

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from sklearn.ensemble import (
    RandomForestRegressor,
    HistGradientBoostingRegressor,
    IsolationForest,
    RandomForestClassifier,
    HistGradientBoostingClassifier,
)
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    average_precision_score,
    confusion_matrix,
    classification_report,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore", category=FutureWarning)


# ============================================================
# 1. CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

CSV_PATH = BASE_DIR / "data" / "m100_node1_digital_twin.csv"
OBSERVED_LABELED_PATH = (
    BASE_DIR
    / "data"
    / "m100_labeling"
    / "outputs"
    / "labeled_dataset"
    / "m100_node1_labeled_observed.csv"
)
SYNTHETIC_SCENARIOS_PATH = (
    BASE_DIR
    / "data"
    / "m100_labeling"
    / "outputs"
    / "labeled_dataset"
    / "m100_synthetic_fault_scenarios.csv"
)

OUTPUT_DIR = BASE_DIR / "outputs" / "predictive_maintenance_op"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ASSET_ID = "M100_NODE_1"
MODEL_VERSION = "temperature-forecast-v1"

TARGETS = [
    "p0_vdd_temp",
    "p1_vdd_temp",
]

METRICS = [
    "ambient",
    "p0_vdd_temp",
    "p1_vdd_temp",
    "fan0_0",
    "fan1_0",
    "p0_power",
    "p1_power",
    "ps0_input_power",
    "ps1_input_power",
    "total_power",
]

DEGRADATION_METRICS = [
    "p0_vdd_temp",
    "p1_vdd_temp",
    "fan0_0",
    "fan1_0",
    "p0_power",
    "p1_power",
]

# These are forecast horizons expressed in rows.
# Their actual duration is calculated from the timestamp interval.
HORIZONS = {
    "1min": 3,
    "5min": 15,
    "15min": 45,
}

LAGS = [1, 2, 3, 5, 10, 15]

ROLLING_WINDOW = 5

RANDOM_STATE = 42


# ============================================================
# 2. LOAD AND CLEAN DATA
# ============================================================

def load_data(csv_path=None):
    """
    Load and clean the telemetry dataset.
    Automatically prioritizes the validated labeled dataset if present.
    """
    if csv_path is not None:
        target_path = Path(csv_path)
    elif OBSERVED_LABELED_PATH.exists():
        target_path = OBSERVED_LABELED_PATH
    else:
        target_path = CSV_PATH

    if not target_path.exists():
        raise FileNotFoundError(
            f"Telemetry dataset not found:\n{target_path}"
        )

    df = pd.read_csv(target_path)

    if "timestamp" not in df.columns:
        raise ValueError(
            "The dataset must contain a 'timestamp' column."
        )

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        errors="coerce",
        utc=True,
    )

    df = df.dropna(subset=["timestamp"])

    df = (
        df.sort_values("timestamp")
        .drop_duplicates(subset=["timestamp"])
        .reset_index(drop=True)
    )

    available_metrics = [
        metric for metric in METRICS
        if metric in df.columns
    ]

    if not available_metrics:
        raise ValueError(
            "None of the configured telemetry metrics "
            "were found in the dataset."
        )

    for metric in available_metrics:
        df[metric] = pd.to_numeric(
            df[metric],
            errors="coerce",
        )

        df[metric] = df[metric].replace(
            [np.inf, -np.inf],
            np.nan,
        )

    if len(df) < 30:
        raise ValueError(
            "The dataset contains too few timestamped rows "
            "for reliable forecasting."
        )

    # Estimate the typical sampling interval.
    intervals = (
        df["timestamp"]
        .diff()
        .dt.total_seconds()
    )

    valid_intervals = intervals[
        intervals > 0
    ].dropna()

    if valid_intervals.empty:
        raise ValueError(
            "Could not determine the telemetry sampling interval."
        )

    median_interval_seconds = float(
        valid_intervals.median()
    )

    # Separate data segments when there is a large time gap.
    # Preserve continuous segment_id from labeled data if available.
    if "segment_id" in df.columns:
        df["_segment"] = pd.to_numeric(df["segment_id"], errors="coerce").fillna(0).astype(int)
    else:
        gap_threshold = 1.5 * median_interval_seconds
        df["_segment"] = (
            intervals > gap_threshold
        ).cumsum()

    print("\nDATASET INFORMATION")
    print("-" * 60)
    print(f"Dataset: {target_path}")
    print(f"Rows: {len(df)}")
    print(f"Available metrics: {available_metrics}")
    if "split" in df.columns:
        print(f"Split distribution: {dict(df['split'].value_counts())}")
    if "anomaly_label" in df.columns:
        print(f"Anomaly label counts: {dict(df['anomaly_label'].value_counts())}")
    print(
        "Median sampling interval: "
        f"{median_interval_seconds:.2f} seconds"
    )
    print(
        f"Approximate samples per minute: "
        f"{60 / median_interval_seconds:.2f}"
    )

    return df, available_metrics, median_interval_seconds


def load_synthetic_data(synthetic_path=None):
    """
    Load and clean synthetic fault injection scenarios dataset.
    """
    target_path = Path(synthetic_path) if synthetic_path else SYNTHETIC_SCENARIOS_PATH
    if not target_path.exists():
        print(f"Notice: Synthetic scenarios dataset not found at {target_path}")
        return None

    df_syn = pd.read_csv(target_path)
    if "base_timestamp" in df_syn.columns and "timestamp" not in df_syn.columns:
        step_offsets = pd.to_numeric(df_syn.get("step_in_scenario", 0), errors="coerce").fillna(0)
        df_syn["timestamp"] = pd.to_datetime(
            df_syn["base_timestamp"], errors="coerce", utc=True
        ) + pd.to_timedelta(step_offsets * 20, unit="s")
    elif "timestamp" in df_syn.columns:
        df_syn["timestamp"] = pd.to_datetime(
            df_syn["timestamp"], errors="coerce", utc=True
        )

    for metric in METRICS:
        if metric in df_syn.columns:
            df_syn[metric] = pd.to_numeric(df_syn[metric], errors="coerce").replace([np.inf, -np.inf], np.nan)

    if "scenario_id" in df_syn.columns:
        df_syn["_segment"] = df_syn["scenario_id"]
    else:
        df_syn["_segment"] = 0

    print("\nSYNTHETIC SCENARIOS INFORMATION")
    print("-" * 60)
    print(f"Dataset: {target_path}")
    print(f"Rows: {len(df_syn)}")
    if "scenario_id" in df_syn.columns:
        print(f"Scenarios: {df_syn['scenario_id'].nunique()}")
    if "synthetic_fault_type" in df_syn.columns:
        print(f"Fault types: {dict(df_syn['synthetic_fault_type'].value_counts())}")

    return df_syn


# ============================================================
# 3. TELEMETRY VISUALIZATION
# ============================================================

def plot_telemetry(df, available_metrics):
    """Plot available telemetry metrics over time."""

    for metric in available_metrics:

        if df[metric].notna().sum() == 0:
            continue

        plt.figure(figsize=(12, 5))

        plt.plot(
            df["timestamp"],
            df[metric],
            linewidth=1,
        )

        plt.title(f"Telemetry Over Time: {metric}")
        plt.xlabel("Timestamp")
        plt.ylabel(metric)
        plt.xticks(rotation=30)
        plt.tight_layout()

        plt.savefig(
            OUTPUT_DIR / f"telemetry_{metric}.png",
            dpi=150,
        )

        plt.close()


# ============================================================
# 4. FEATURE ENGINEERING
# ============================================================

def create_features(df, available_metrics):
    """
    Generate historical lag and rolling-statistic features.

    All rolling features are shifted by one row so that the
    current row's values are not accidentally included.
    """

    df = df.copy()

    feature_columns = []

    for metric in available_metrics:

        grouped = df.groupby(
            "_segment",
            sort=False,
        )[metric]

        for lag in LAGS:

            feature_name = f"{metric}_lag_{lag}"

            df[feature_name] = grouped.shift(lag)

            feature_columns.append(feature_name)

        rolling_mean_name = f"{metric}_rolling_mean"

        df[rolling_mean_name] = (
            grouped.transform(
                lambda series: series.shift(1).rolling(
                    window=ROLLING_WINDOW,
                    min_periods=ROLLING_WINDOW,
                ).mean()
            )
        )

        rolling_std_name = f"{metric}_rolling_std"

        df[rolling_std_name] = (
            grouped.transform(
                lambda series: series.shift(1).rolling(
                    window=ROLLING_WINDOW,
                    min_periods=ROLLING_WINDOW,
                ).std()
            )
        )

        feature_columns.extend(
            [
                rolling_mean_name,
                rolling_std_name,
            ]
        )

    return df, feature_columns


# ============================================================
# 5. MODEL CREATION AND EVALUATION
# ============================================================

def create_model(model_name):
    """Create a forecasting model with median imputation."""

    if model_name == "RandomForest":

        estimator = RandomForestRegressor(
            n_estimators=35,
            max_depth=12,
            min_samples_leaf=2,
            random_state=RANDOM_STATE,
            n_jobs=-1,
        )

    elif model_name == "HistGradientBoosting":

        estimator = HistGradientBoostingRegressor(
            max_iter=60,
            max_leaf_nodes=15,
            random_state=RANDOM_STATE,
        )

    else:
        raise ValueError(
            f"Unknown model: {model_name}"
        )

    return Pipeline(
        steps=[
            (
                "imputer",
                SimpleImputer(strategy="median"),
            ),
            ("model", estimator),
        ]
    )


def create_classifier(model_name, n_classes=2):
    """Create a supervised classification model with median imputation."""
    if model_name == "RandomForest":
        estimator = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_leaf=2,
            class_weight="balanced" if n_classes == 2 else "balanced_subsample",
            random_state=RANDOM_STATE,
            n_jobs=-1,
        )
    elif model_name == "HistGradientBoosting":
        estimator = HistGradientBoostingClassifier(
            max_iter=100,
            max_depth=5,
            learning_rate=0.08,
            class_weight="balanced",
            random_state=RANDOM_STATE,
        )
    else:
        raise ValueError(
            f"Unknown classifier model: {model_name}"
        )

    return Pipeline(
        steps=[
            (
                "imputer",
                SimpleImputer(strategy="median"),
            ),
            ("model", estimator),
        ]
    )


def calculate_metrics(actual, predicted):
    """Calculate regression evaluation metrics."""

    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)

    valid = (
        np.isfinite(actual)
        & np.isfinite(predicted)
    )

    actual = actual[valid]
    predicted = predicted[valid]

    if len(actual) == 0:
        return {
            "MAE": np.nan,
            "RMSE": np.nan,
            "R2": np.nan,
            "MAPE": np.nan,
            "Accuracy_Pct": np.nan,
        }

    mae = mean_absolute_error(
        actual,
        predicted,
    )

    rmse = np.sqrt(
        mean_squared_error(
            actual,
            predicted,
        )
    )

    r2 = (
        r2_score(actual, predicted)
        if len(actual) >= 2
        else np.nan
    )

    non_zero = actual != 0
    if np.any(non_zero):
        mape = float(np.mean(np.abs((actual[non_zero] - predicted[non_zero]) / actual[non_zero])) * 100.0)
        acc_pct = float(max(0.0, 100.0 - mape))
    else:
        mape = np.nan
        acc_pct = np.nan

    return {
        "MAE": float(mae),
        "RMSE": float(rmse),
        "R2": float(r2),
        "MAPE": float(mape),
        "Accuracy_Pct": float(acc_pct),
    }


# ============================================================
# 6. STANDARDIZED PREDICTION OUTPUT
# ============================================================

def create_standardized_prediction(
    predicted_value,
    asset_id,
    target_metric,
    horizon_minutes,
    model_version,
    current_timestamp,
    target_timestamp,
    model_name,
    data_quality_status="not_independently_verified",
):
    """
    Convert a forecast into a standardized prediction record.

    This function formats a prediction that has already been
    generated by the selected forecasting method.
    """

    return {
        "asset_id": str(asset_id),
        "prediction_type": "future_temperature",
        "target_metric": target_metric,
        "horizon_minutes": float(horizon_minutes),
        "predicted_value": float(predicted_value),
        "current_timestamp": str(current_timestamp),
        "target_timestamp": str(target_timestamp),
        "prediction_timestamp": pd.Timestamp.now(
            tz="UTC"
        ).isoformat(),
        "model_version": model_version,
        "selected_model": model_name,
        "data_quality_status": data_quality_status,
        "is_estimated": True,
        "is_simulated": False,
        "interpretation": (
            "Forecast, not a confirmed failure"
        ),
    }


# ============================================================
# 7. TEMPERATURE FORECASTING
# ============================================================

def run_forecast(
    df,
    feature_columns,
    target,
    horizon_name,
    horizon_steps,
    median_interval_seconds,
    synthetic_df=None,
):
    """
    Train and evaluate forecasting models using chronological
    train, validation and test splits.

    The target is the temperature horizon_steps rows in the
    future within the same continuous data segment.
    """

    print("\n" + "=" * 65)
    print(f"Target: {target}")
    print(f"Horizon label: {horizon_name}")
    print(f"Horizon steps: {horizon_steps}")
    print("=" * 65)

    if target not in df.columns:
        print(f"Skipping missing target: {target}")
        return None

    working = df.copy()

    # Future target and timestamp must stay inside each segment.
    grouped_target = working.groupby(
        "_segment",
        sort=False,
    )[target]

    grouped_timestamp = working.groupby(
        "_segment",
        sort=False,
    )["timestamp"]

    working["future_target"] = grouped_target.shift(
        -horizon_steps
    )

    working["target_timestamp"] = (
        grouped_timestamp.shift(-horizon_steps)
    )

    # Current observed target provides the persistence baseline.
    working["persistence_prediction"] = working[target]

    # Exclude rows without a future target timestamp/value.
    valid_rows = working.dropna(
        subset=[
            "future_target",
            "target_timestamp",
        ]
    ).copy()

    if len(valid_rows) < 60:
        print(
            "Not enough valid rows for chronological "
            "train/validation/test evaluation."
        )
        return None

    X = valid_rows[feature_columns].replace(
        [np.inf, -np.inf],
        np.nan,
    )

    y = valid_rows["future_target"].astype(float)

    persistence = (
        valid_rows["persistence_prediction"].astype(float)
    )

    # Chronological split: use dataset 'split' column if present, otherwise 70/15/15 ratio.
    has_split_column = (
        "split" in valid_rows.columns
        and (valid_rows["split"] == "train").any()
        and (valid_rows["split"] == "test").any()
    )

    if has_split_column:
        train_mask = valid_rows["split"] == "train"
        val_mask = valid_rows["split"] == "val"
        test_mask = valid_rows["split"] == "test"

        train_idx = np.flatnonzero(train_mask.to_numpy())
        validation_idx = np.flatnonzero(val_mask.to_numpy())
        test_idx = np.flatnonzero(test_mask.to_numpy())

        if len(validation_idx) == 0 and len(train_idx) > 10:
            n_tr = len(train_idx)
            val_split = int(n_tr * 0.8)
            validation_idx = train_idx[val_split:]
            train_idx = train_idx[:val_split]
    else:
        n = len(valid_rows)

        train_end = int(n * 0.70)
        validation_end = int(n * 0.85)

        # Exclude horizon-sized gaps between partitions to reduce
        # overlap between training labels and later evaluation labels.
        gap = min(
            horizon_steps,
            max(0, (n - 3) // 6),
        )

        train_end_adjusted = max(
            1,
            train_end - gap,
        )

        validation_start = min(
            train_end + gap,
            n,
        )

        validation_end_adjusted = max(
            validation_start,
            validation_end - gap,
        )

        test_start = min(
            validation_end + gap,
            n,
        )

        train_idx = np.arange(
            0,
            train_end_adjusted,
        )

        validation_idx = np.arange(
            validation_start,
            validation_end_adjusted,
        )

        test_idx = np.arange(
            test_start,
            n,
        )

    if (
        len(train_idx) < 20
        or len(validation_idx) < 5
        or len(test_idx) < 5
    ):
        print(
            "Not enough rows in one or more chronological "
            "partitions. Reduce the horizon or use more data."
        )
        return None

    X_train = X.iloc[train_idx]
    y_train = y.iloc[train_idx]

    X_validation = X.iloc[validation_idx]
    y_validation = y.iloc[validation_idx]

    X_test = X.iloc[test_idx]
    y_test = y.iloc[test_idx]

    validation_persistence = (
        persistence.iloc[validation_idx]
    )

    # Keep only validation rows with a valid persistence value
    # when comparing the baseline.
    baseline_mask = np.isfinite(
        validation_persistence.to_numpy(dtype=float)
    )

    validation_persistence_valid = (
        validation_persistence.iloc[
            np.flatnonzero(baseline_mask)
        ]
    )

    validation_y_for_baseline = (
        y_validation.iloc[
            np.flatnonzero(baseline_mask)
        ]
    )

    if len(validation_y_for_baseline) == 0:
        print(
            "No valid persistence predictions in validation data."
        )
        return None

    candidate_results = []

    persistence_metrics = calculate_metrics(
        validation_y_for_baseline,
        validation_persistence_valid,
    )

    candidate_results.append(
        {
            "name": "Persistence",
            "validation_MAE": persistence_metrics["MAE"],
        }
    )

    trained_models = {}

    # Train the candidate machine-learning models.
    for model_name in [
        "RandomForest",
        "HistGradientBoosting",
    ]:

        try:
            model = create_model(model_name)

            model.fit(
                X_train,
                y_train,
            )

            validation_predictions = model.predict(
                X_validation
            )

            validation_metrics = calculate_metrics(
                y_validation,
                validation_predictions,
            )

            candidate_results.append(
                {
                    "name": model_name,
                    "validation_MAE": validation_metrics["MAE"],
                }
            )

            trained_models[model_name] = model

            print(
                f"{model_name} validation MAE: "
                f"{validation_metrics['MAE']:.4f}"
            )

        except Exception as exc:
            print(
                f"{model_name} could not be trained: {exc}"
            )

    print(
        "Persistence validation MAE: "
        f"{persistence_metrics['MAE']:.4f}"
    )

    # Dashboard forecasts must be produced by a trained ML model when one is
    # available. Keep Persistence in the evaluation report as a baseline, but do
    # not silently present baseline persistence as an ML prediction.
    candidate_results = [
        item for item in candidate_results
        if np.isfinite(item["validation_MAE"])
    ]

    if not candidate_results:
        print("No valid forecasting candidate was produced.")
        return None

    ml_candidates = [item for item in candidate_results if item["name"] != "Persistence"]
    selection_pool = ml_candidates if ml_candidates else candidate_results
    best_candidate = min(
        selection_pool,
        key=lambda item: item["validation_MAE"],
    )
    if not ml_candidates:
        print("WARNING: ML candidates failed; Persistence baseline is the only available fallback and is not an ML model.")

    best_name = best_candidate["name"]

    print(f"\nSelected model: {best_name}")

    # Fit the selected ML model on train + validation data.
    # Persistence does not require a fitted model.
    best_model = None

    if best_name != "Persistence":

        X_train_validation = pd.concat(
            [
                X_train,
                X_validation,
            ],
            axis=0,
        )

        y_train_validation = pd.concat(
            [
                y_train,
                y_validation,
            ],
            axis=0,
        )

        best_model = create_model(best_name)

        best_model.fit(
            X_train_validation,
            y_train_validation,
        )

        test_predictions = best_model.predict(
            X_test
        )

    else:
        # Persistence forecasts the current observed temperature
        # as the future temperature.
        test_predictions = (
            persistence.iloc[test_idx]
            .to_numpy(dtype=float)
        )

    # Evaluate the chosen method on the untouched test partition.
    test_metrics = calculate_metrics(
        y_test,
        test_predictions,
    )

    print("\nTEST METRICS")
    print(f"MAE:  {test_metrics['MAE']:.4f}")
    print(f"RMSE: {test_metrics['RMSE']:.4f}")
    print(f"R2:   {test_metrics['R2']:.4f}")
    if np.isfinite(test_metrics.get("MAPE", np.nan)):
        print(f"MAPE: {test_metrics['MAPE']:.2f}%")
        print(f"Forecast Accuracy: {test_metrics['Accuracy_Pct']:.2f}%")

    # Calculate the real approximate forecast duration.
    horizon_minutes = (
        horizon_steps
        * median_interval_seconds
        / 60.0
    )

    # Save test predictions.
    prediction_df = pd.DataFrame(
        {
            "timestamp": valid_rows["timestamp"].iloc[
                test_idx
            ].to_numpy(),
            "target_timestamp": valid_rows[
                "target_timestamp"
            ].iloc[test_idx].to_numpy(),
            "target": target,
            "horizon_label": horizon_name,
            "horizon_steps": horizon_steps,
            "horizon_minutes": horizon_minutes,
            "actual": y_test.to_numpy(),
            "predicted": np.asarray(
                test_predictions,
                dtype=float,
            ),
            "selected_model": best_name,
        }
    )

    prediction_path = (
        OUTPUT_DIR
        / f"predictions_{target}_{horizon_name}.csv"
    )

    prediction_df.to_csv(
        prediction_path,
        index=False,
    )

    # Save selected ML model and its feature metadata.
    if best_model is not None:

        model_bundle = {
            "model": best_model,
            "feature_columns": feature_columns,
            "target": target,
            "horizon_label": horizon_name,
            "horizon_steps": horizon_steps,
            "horizon_minutes": horizon_minutes,
            "model_version": MODEL_VERSION,
            "asset_id": ASSET_ID,
        }

        joblib.dump(
            model_bundle,
            OUTPUT_DIR
            / f"model_{target}_{horizon_name}.joblib",
        )

    # Plot actual versus predicted test values.
    plt.figure(figsize=(12, 5))

    plt.plot(
        prediction_df["target_timestamp"],
        prediction_df["actual"],
        label="Actual",
        linewidth=1.5,
    )

    plt.plot(
        prediction_df["target_timestamp"],
        prediction_df["predicted"],
        label="Predicted",
        linewidth=1.5,
    )

    plt.title(
        f"Forecast: {target} ({horizon_name})"
    )

    plt.xlabel("Target Timestamp")
    plt.ylabel("Temperature")
    plt.legend()
    plt.xticks(rotation=30)
    plt.tight_layout()

    plt.savefig(
        OUTPUT_DIR
        / f"forecast_{target}_{horizon_name}.png",
        dpi=150,
    )

    plt.close()

    synthetic_test_metrics = None
    if synthetic_df is not None and target in synthetic_df.columns and best_model is not None:
        try:
            syn_working = synthetic_df.copy()
            syn_working["future_target"] = syn_working.groupby("_segment", sort=False)[target].shift(-horizon_steps)
            syn_feat_df, _ = create_features(
                syn_working,
                [m for m in METRICS if m in syn_working.columns]
            )
            common_cols = [c for c in feature_columns if c in syn_feat_df.columns]
            if len(common_cols) == len(feature_columns):
                syn_valid = syn_feat_df.dropna(subset=["future_target"] + feature_columns).copy()
                if "split" in syn_valid.columns and (syn_valid["split"] == "test").any():
                    syn_test = syn_valid[syn_valid["split"] == "test"]
                else:
                    syn_test = syn_valid
                if len(syn_test) >= 10:
                    X_syn_test = syn_test[feature_columns].replace([np.inf, -np.inf], np.nan)
                    y_syn_test = syn_test["future_target"].astype(float)
                    syn_preds = best_model.predict(X_syn_test)
                    synthetic_test_metrics = calculate_metrics(y_syn_test, syn_preds)
                    print(
                        f"Synthetic Fault Scenarios Test MAE ({target}, {horizon_name}): "
                        f"{synthetic_test_metrics['MAE']:.4f} (RMSE: {synthetic_test_metrics['RMSE']:.4f}, R2: {synthetic_test_metrics['R2']:.4f})"
                    )
        except Exception as exc:
            print(f"Notice: Synthetic evaluation could not be completed for {target}: {exc}")

    return {
        "target": target,
        "horizon": horizon_name,
        "horizon_steps": horizon_steps,
        "horizon_minutes": horizon_minutes,
        "selected_model": best_name,
        "test_metrics": test_metrics,
        "synthetic_test_metrics": synthetic_test_metrics,
        "model": best_model,
        "test_features": X_test.reset_index(drop=True),
        "test_timestamps": (
            valid_rows["timestamp"]
            .iloc[test_idx]
            .reset_index(drop=True)
        ),
        "target_timestamps": (
            valid_rows["target_timestamp"]
            .iloc[test_idx]
            .reset_index(drop=True)
        ),
        "test_predictions": np.asarray(
            test_predictions,
            dtype=float,
        ),
        "test_actual": y_test.reset_index(drop=True),
    }


# ============================================================
# 8. DEGRADATION INDICATORS
# ============================================================

def generate_degradation_indicators(
    df,
    available_metrics,
):
    """
    Generate rolling statistics and changes for selected
    temperature, fan and power metrics.
    """

    selected_metrics = [
        metric for metric in DEGRADATION_METRICS
        if metric in available_metrics
    ]

    if not selected_metrics:
        print(
            "\nNo configured degradation metrics are available."
        )
        return

    result = df[
        ["timestamp", "_segment"] + selected_metrics
    ].copy()

    for metric in selected_metrics:

        grouped = result.groupby(
            "_segment",
            sort=False,
        )[metric]

        result[f"{metric}_rolling_mean"] = (
            grouped.transform(
                lambda series: series.rolling(
                    window=ROLLING_WINDOW,
                    min_periods=1,
                ).mean()
            )
        )

        result[f"{metric}_rolling_std"] = (
            grouped.transform(
                lambda series: series.rolling(
                    window=ROLLING_WINDOW,
                    min_periods=2,
                ).std()
            )
        )

        result[f"{metric}_change"] = grouped.diff()

    result.drop(
        columns=["_segment"],
        inplace=True,
    )

    result.to_csv(
        OUTPUT_DIR / "degradation_indicators.csv",
        index=False,
    )

    print(
        "\nDegradation indicators saved."
    )


# ============================================================
# 9. ANOMALY DETECTION
# ============================================================

def run_anomaly_detection(
    df,
    available_metrics,
    feature_df=None,
    feature_columns=None,
    synthetic_df=None,
):
    """
    Train and evaluate Supervised Anomaly Detection and Diagnostic Classification
    models alongside an Isolation Forest unsupervised baseline.

    Uses chronological train/val/test splits, tunes decision threshold on validation data,
    evaluates Precision, Recall, F1, PR-AUC on test data, and exports standardized predictions.
    """
    print("\n" + "=" * 65)
    print("ANOMALY DETECTION & FAULT DIAGNOSTICS (SUPERVISED + BASELINE)")
    print("=" * 65)

    anomaly_metrics = [
        metric for metric in available_metrics
        if df[metric].notna().sum() > 0
    ]

    if not anomaly_metrics:
        print("\nNo usable metrics for anomaly detection.")
        return

    # Check if supervised labels are present in the dataset
    has_labels = "anomaly_label" in df.columns and df["anomaly_label"].notna().sum() > 0

    # 1. Train Unsupervised Baseline: Isolation Forest
    split_index = int(len(df) * 0.70)
    if "split" in df.columns and (df["split"] == "train").any():
        iso_train_mask = (df["split"] == "train").to_numpy()
    else:
        iso_train_mask = np.zeros(len(df), dtype=bool)
        iso_train_mask[:split_index] = True

    imputer = SimpleImputer(strategy="median")
    X_raw = df[anomaly_metrics].replace([np.inf, -np.inf], np.nan)
    X_raw_imputed = imputer.fit_transform(X_raw[iso_train_mask])
    X_all_raw = imputer.transform(X_raw)

    detector = IsolationForest(
        n_estimators=100,
        contamination="auto",
        random_state=RANDOM_STATE,
    )
    detector.fit(X_raw_imputed)

    # Isolation Forest: decision function (lower means more anomalous)
    scores = detector.decision_function(X_all_raw)
    iso_labels = detector.predict(X_all_raw)

    best_supervised_clf = None
    best_clf_name = None
    best_threshold = 0.5
    fault_classifier = None
    supervised_metrics_summary = []

    # 2. Supervised Training (if labels present)
    if has_labels:
        if feature_df is not None and feature_columns is not None:
            feat_cols = [c for c in feature_columns if c in feature_df.columns]
            feat_matrix = feature_df[feat_cols].replace([np.inf, -np.inf], np.nan)
        else:
            feat_cols = anomaly_metrics
            feat_matrix = X_raw

        # Valid rows for anomaly label training
        valid_mask = df["anomaly_label"].notna()
        if "label_valid" in df.columns:
            valid_mask = valid_mask & (df["label_valid"] == 1)

        valid_df = df[valid_mask].copy()
        X_valid = feat_matrix.loc[valid_mask]
        y_valid = valid_df["anomaly_label"].astype(int)

        if "split" in valid_df.columns and (valid_df["split"] == "train").any() and (valid_df["split"] == "test").any():
            train_mask = valid_df["split"] == "train"
            val_mask = valid_df["split"] == "val"
            test_mask = valid_df["split"] == "test"

            if val_mask.sum() == 0:
                tr_idx = np.flatnonzero(train_mask.to_numpy())
                cut = int(len(tr_idx) * 0.8)
                val_mask = pd.Series(False, index=valid_df.index)
                val_mask.iloc[tr_idx[cut:]] = True
                train_mask = pd.Series(False, index=valid_df.index)
                train_mask.iloc[tr_idx[:cut]] = True
        else:
            n_v = len(valid_df)
            train_mask = pd.Series(False, index=valid_df.index)
            val_mask = pd.Series(False, index=valid_df.index)
            test_mask = pd.Series(False, index=valid_df.index)
            train_mask.iloc[:int(n_v * 0.7)] = True
            val_mask.iloc[int(n_v * 0.7):int(n_v * 0.85)] = True
            test_mask.iloc[int(n_v * 0.85):] = True

        X_train_sub = X_valid[train_mask]
        y_train_sub = y_valid[train_mask]
        X_val_sub = X_valid[val_mask]
        y_val_sub = y_valid[val_mask]
        X_test_sub = X_valid[test_mask]
        y_test_sub = y_valid[test_mask]

        print(f"Supervised anomaly training samples: {len(X_train_sub)}, validation: {len(X_val_sub)}, test: {len(X_test_sub)}")
        print(f"Training positive anomalies: {y_train_sub.sum()}, Test positive anomalies: {y_test_sub.sum()}")

        # Candidate Supervised Models
        candidates = {
            "HistGradientBoosting": create_classifier("HistGradientBoosting", n_classes=2),
            "RandomForest": create_classifier("RandomForest", n_classes=2),
        }

        best_val_f1 = -1.0

        for name, clf in candidates.items():
            try:
                clf.fit(X_train_sub, y_train_sub)
                val_probs = clf.predict_proba(X_val_sub)[:, 1] if hasattr(clf, "predict_proba") else clf.predict(X_val_sub)

                # Threshold optimization on validation partition
                thresholds = np.linspace(0.1, 0.9, 17)
                opt_thr = 0.5
                max_f1 = 0.0
                for th in thresholds:
                    f1_cand = f1_score(y_val_sub, (val_probs >= th).astype(int), zero_division=0)
                    if f1_cand > max_f1:
                        max_f1 = f1_cand
                        opt_thr = th

                test_probs = clf.predict_proba(X_test_sub)[:, 1]
                test_preds = (test_probs >= opt_thr).astype(int)
                acc = accuracy_score(y_test_sub, test_preds)
                prec = precision_score(y_test_sub, test_preds, zero_division=0)
                rec = recall_score(y_test_sub, test_preds, zero_division=0)
                f1 = f1_score(y_test_sub, test_preds, zero_division=0)
                pr_auc = average_precision_score(y_test_sub, test_probs) if y_test_sub.sum() > 0 else 0.0
                try:
                    roc_auc = roc_auc_score(y_test_sub, test_probs) if len(np.unique(y_test_sub)) > 1 else np.nan
                except Exception:
                    roc_auc = np.nan

                supervised_metrics_summary.append({
                    "model": name,
                    "type": "Supervised",
                    "best_threshold": round(opt_thr, 4),
                    "test_accuracy": round(acc, 4),
                    "test_accuracy_pct": round(acc * 100.0, 2),
                    "test_precision": round(prec, 4),
                    "test_recall": round(rec, 4),
                    "test_f1": round(f1, 4),
                    "test_pr_auc": round(pr_auc, 4),
                    "test_roc_auc": round(roc_auc, 4) if np.isfinite(roc_auc) else np.nan,
                })

                if max_f1 > best_val_f1 or best_supervised_clf is None:
                    best_val_f1 = max_f1
                    best_supervised_clf = clf
                    best_clf_name = name
                    best_threshold = opt_thr

            except Exception as exc:
                print(f"Notice: {name} classifier training error: {exc}")

        # Baseline evaluation on the exact same test partition
        iso_test_preds = (detector.predict(imputer.transform(df.loc[valid_df.index[test_mask], anomaly_metrics])) == -1).astype(int)
        iso_acc = accuracy_score(y_test_sub, iso_test_preds)
        iso_prec = precision_score(y_test_sub, iso_test_preds, zero_division=0)
        iso_rec = recall_score(y_test_sub, iso_test_preds, zero_division=0)
        iso_f1 = f1_score(y_test_sub, iso_test_preds, zero_division=0)
        supervised_metrics_summary.append({
            "model": "IsolationForest_Baseline",
            "type": "Unsupervised",
            "best_threshold": 0.0,
            "test_accuracy": round(iso_acc, 4),
            "test_accuracy_pct": round(iso_acc * 100.0, 2),
            "test_precision": round(iso_prec, 4),
            "test_recall": round(iso_rec, 4),
            "test_f1": round(iso_f1, 4),
            "test_pr_auc": np.nan,
            "test_roc_auc": np.nan,
        })

        # Save comparative supervised metrics
        sup_metrics_df = pd.DataFrame(supervised_metrics_summary)
        sup_metrics_df.to_csv(OUTPUT_DIR / "supervised_anomaly_metrics.csv", index=False)
        print("\nSUPERVISED ANOMALY DETECTION EVALUATION (TEST PARTITION):")
        print("-" * 65)
        print(sup_metrics_df.to_string(index=False))

        # 3. Supervised Diagnostic Multiclass Fault Classification (if fault_type present)
        if "fault_type" in valid_df.columns:
            fault_labels = valid_df.loc[train_mask, "fault_type"].dropna()
            if fault_labels.nunique() > 1:
                try:
                    fault_clf = create_classifier("RandomForest", n_classes=fault_labels.nunique())
                    X_fault_tr = X_train_sub.loc[fault_labels.index]
                    fault_clf.fit(X_fault_tr, fault_labels)
                    fault_classifier = fault_clf

                    test_fault_actual = valid_df.loc[test_mask, "fault_type"].dropna()
                    if not test_fault_actual.empty:
                        X_fault_te = X_test_sub.loc[test_fault_actual.index]
                        test_fault_preds = fault_clf.predict(X_fault_te)
                        fault_acc = accuracy_score(test_fault_actual, test_fault_preds)
                        fault_rep = classification_report(test_fault_actual, test_fault_preds, output_dict=True, zero_division=0)
                        fault_rep_df = pd.DataFrame(fault_rep).transpose().reset_index()
                        fault_rep_df.to_csv(OUTPUT_DIR / "fault_classification_report.csv", index=False)

                        fault_summary_df = pd.DataFrame([{
                            "model": "RandomForest_Fault_Classifier",
                            "task": "Multiclass Fault Classification",
                            "test_samples": len(test_fault_actual),
                            "test_accuracy": round(fault_acc, 4),
                            "test_accuracy_pct": round(fault_acc * 100.0, 2),
                            "weighted_precision": round(fault_rep.get("weighted avg", {}).get("precision", 0.0), 4),
                            "weighted_recall": round(fault_rep.get("weighted avg", {}).get("recall", 0.0), 4),
                            "weighted_f1": round(fault_rep.get("weighted avg", {}).get("f1-score", 0.0), 4),
                            "macro_f1": round(fault_rep.get("macro avg", {}).get("f1-score", 0.0), 4),
                        }])
                        fault_summary_df.to_csv(OUTPUT_DIR / "fault_diagnostic_metrics.csv", index=False)

                        print("\nDIAGNOSTIC FAULT CLASSIFICATION REPORT:")
                        print("-" * 65)
                        print(fault_summary_df.to_string(index=False))
                except Exception as exc:
                    print(f"Notice: Fault type classification skipped: {exc}")

    # Generate full-dataset predictions
    if feature_df is not None and feature_columns is not None:
        full_X = feature_df[[c for c in feature_columns if c in feature_df.columns]].replace([np.inf, -np.inf], np.nan)
    else:
        full_X = X_raw

    if best_supervised_clf is not None:
        supervised_probs = best_supervised_clf.predict_proba(full_X)[:, 1]
        supervised_flags = (supervised_probs >= best_threshold)
    else:
        supervised_probs = np.where(scores < 0, 1.0, 0.0)
        supervised_flags = (iso_labels == -1)

    predicted_fault_types = (
        fault_classifier.predict(full_X) if fault_classifier is not None else np.where(supervised_flags, "anomaly", "normal")
    )

    is_anomaly = supervised_flags | (iso_labels == -1)

    anomaly_df = pd.DataFrame(
        {
            "timestamp": df["timestamp"],
            "anomaly_label": df["anomaly_label"] if "anomaly_label" in df.columns else supervised_flags.astype(int),
            "anomaly_score": scores,  # Preserves IsolationForest continuous decision score
            "supervised_anomaly_score": np.round(supervised_probs, 4),
            "is_anomaly": is_anomaly,
            "supervised_is_anomaly": supervised_flags,
            "predicted_fault_type": predicted_fault_types,
        }
    )

    for metric in anomaly_metrics:
        anomaly_df[metric] = df[metric].to_numpy()

    anomaly_df.to_csv(
        OUTPUT_DIR / "anomaly_detection_results.csv",
        index=False,
    )

    # Plot
    plt.figure(figsize=(12, 5))
    plt.plot(
        df["timestamp"],
        scores,
        label="Isolation Forest Score",
        linewidth=1,
        color="#1f77b4",
        alpha=0.7,
    )

    anomaly_positions = np.flatnonzero(is_anomaly)
    if len(anomaly_positions) > 0:
        plt.scatter(
            df["timestamp"].iloc[anomaly_positions],
            scores[anomaly_positions],
            label="Flagged Anomaly (Supervised / IF)",
            color="#d62728",
            s=16,
        )

    plt.title(f"Anomaly Detection (Selected Model: {best_clf_name or 'IsolationForest'})")
    plt.xlabel("Timestamp")
    plt.ylabel("Anomaly Decision Score")
    plt.legend()
    plt.xticks(rotation=30)
    plt.tight_layout()

    plt.savefig(
        OUTPUT_DIR / "anomaly_detection_plot.png",
        dpi=150,
    )
    plt.close()

    # Save model bundle
    joblib.dump(
        {
            "imputer": imputer,
            "detector": detector,
            "supervised_model": best_supervised_clf,
            "supervised_model_name": best_clf_name,
            "supervised_threshold": best_threshold,
            "fault_classifier": fault_classifier,
            "metrics": anomaly_metrics,
        },
        OUTPUT_DIR / "anomaly_detection_model.joblib",
    )

    print("\nAnomaly detection results and model artifacts saved.")


def generate_supervised_early_warnings(
    df,
    feature_df,
    feature_columns,
    synthetic_df=None,
):
    """
    Train and evaluate a supervised prognostic classifier targeting anomaly_within_next_15
    (impending anomaly within 5 minutes) evaluated on currently normal telemetry (anomaly_label == 0).
    """
    if "anomaly_within_next_15" not in df.columns:
        print("\nNotice: 'anomaly_within_next_15' not found in dataset. Skipping supervised early warnings.")
        return

    print("\n" + "=" * 65)
    print("SUPERVISED EARLY-WARNING PROGNOSTIC MODEL")
    print("=" * 65)

    # Filter rows with current normal state (onset subset)
    current_normal_mask = (df["anomaly_label"] == 0) if "anomaly_label" in df.columns else pd.Series(True, index=df.index)
    valid_target_mask = df["anomaly_within_next_15"].notna() & current_normal_mask

    if valid_target_mask.sum() < 30:
        print("Not enough samples for prognostic training.")
        return

    feat_cols = [c for c in feature_columns if c in feature_df.columns]
    X_sub = feature_df.loc[valid_target_mask, feat_cols].replace([np.inf, -np.inf], np.nan)
    y_sub = df.loc[valid_target_mask, "anomaly_within_next_15"].astype(int)

    if "split" in df.columns and (df["split"] == "train").any() and (df["split"] == "test").any():
        tr_mask = df.loc[valid_target_mask, "split"] == "train"
        te_mask = df.loc[valid_target_mask, "split"] == "test"
    else:
        n_sub = len(X_sub)
        tr_mask = pd.Series(False, index=X_sub.index)
        te_mask = pd.Series(False, index=X_sub.index)
        tr_mask.iloc[:int(n_sub * 0.75)] = True
        te_mask.iloc[int(n_sub * 0.75):] = True

    try:
        clf = create_classifier("HistGradientBoosting", n_classes=2)
        clf.fit(X_sub[tr_mask], y_sub[tr_mask])

        y_test_actual = y_sub[te_mask]
        test_probs = clf.predict_proba(X_sub[te_mask])[:, 1]
        test_preds = (test_probs >= 0.5).astype(int)
        acc = accuracy_score(y_test_actual, test_preds)
        prec = precision_score(y_test_actual, test_preds, zero_division=0)
        rec = recall_score(y_test_actual, test_preds, zero_division=0)
        f1 = f1_score(y_test_actual, test_preds, zero_division=0)
        pr_auc = average_precision_score(y_test_actual, test_probs) if y_test_actual.sum() > 0 else 0.0
        try:
            roc_auc = roc_auc_score(y_test_actual, test_probs) if len(np.unique(y_test_actual)) > 1 else np.nan
        except Exception:
            roc_auc = np.nan

        eval_df = pd.DataFrame([{
            "target": "anomaly_within_next_15",
            "model": "HistGradientBoostingClassifier",
            "test_samples": len(y_test_actual),
            "positives": int(y_test_actual.sum()),
            "accuracy": round(acc, 4),
            "accuracy_pct": round(acc * 100.0, 2),
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1_score": round(f1, 4),
            "pr_auc": round(pr_auc, 4),
            "roc_auc": round(roc_auc, 4) if np.isfinite(roc_auc) else np.nan,
        }])
        eval_df.to_csv(OUTPUT_DIR / "early_warning_evaluation.csv", index=False)
        print("EARLY WARNING PROGNOSTIC EVALUATION (5-MINUTE LOOKAHEAD ONSET):")
        print(eval_df.to_string(index=False))

        # Predict early warning risk across all normal telemetry
        full_X = feature_df[feat_cols].replace([np.inf, -np.inf], np.nan)
        full_probs = clf.predict_proba(full_X)[:, 1]

        warning_mask = (full_probs >= 0.5) & current_normal_mask
        early_warnings_df = pd.DataFrame({
            "timestamp": df.loc[warning_mask, "timestamp"],
            "asset_id": ASSET_ID,
            "warning_type": "supervised_5min_anomaly_onset",
            "predicted_onset_probability": np.round(full_probs[warning_mask], 4),
            "current_anomaly_label": 0,
            "is_warning": True,
        })
        for m in ["p0_vdd_temp", "p1_vdd_temp", "fan0_0", "total_power"]:
            if m in df.columns:
                early_warnings_df[m] = df.loc[warning_mask, m].to_numpy()

        early_warnings_df.to_csv(OUTPUT_DIR / "supervised_early_warnings.csv", index=False)
        print(f"Supervised early warnings saved ({len(early_warnings_df)} warnings flagged).")

    except Exception as exc:
        print(f"Supervised early warning generation skipped: {exc}")


# ============================================================
# 10. OBSERVED TEMPERATURE EARLY WARNINGS
# ============================================================

def generate_temperature_warnings(
    df,
    available_metrics,
):
    """
    Flag observed temperature readings above the 95th percentile
    calculated from the first 70% of the telemetry.
    """

    warning_frames = []

    for target in TARGETS:

        if target not in available_metrics:
            continue

        training_end = max(
            1,
            int(len(df) * 0.70),
        )

        training_values = df[target].iloc[
            :training_end
        ].dropna()

        if training_values.empty:
            continue

        threshold = float(
            training_values.quantile(0.95)
        )

        valid_mask = df[target].notna()

        warning_mask = (
            valid_mask
            & (df[target] > threshold)
        )

        warning_df = df.loc[
            warning_mask,
            ["timestamp", target],
        ].copy()

        warning_df.rename(
            columns={target: "observed_temperature"},
            inplace=True,
        )

        warning_df["asset_id"] = ASSET_ID
        warning_df["target_metric"] = target
        warning_df["warning_threshold"] = threshold
        warning_df["warning_type"] = "observed_temperature"
        warning_df["is_warning"] = True

        warning_frames.append(warning_df)

    if warning_frames:
        warnings_df = pd.concat(
            warning_frames,
            ignore_index=True,
        )
    else:
        warnings_df = pd.DataFrame(
            columns=[
                "timestamp",
                "observed_temperature",
                "asset_id",
                "target_metric",
                "warning_threshold",
                "warning_type",
                "is_warning",
            ]
        )

    warnings_df.to_csv(
        OUTPUT_DIR / "temperature_early_warnings.csv",
        index=False,
    )

    print(
        "\nObserved temperature warnings saved."
    )


# ============================================================
# 11. FUTURE TEMPERATURE WARNINGS
# ============================================================

def generate_future_temperature_warnings(
    df,
    available_metrics,
):
    """
    Compare saved forecasts with thresholds calculated from
    the first 70% of the corresponding observed temperature.
    """

    warning_frames = []

    for target in TARGETS:

        if target not in available_metrics:
            continue

        training_end = max(
            1,
            int(len(df) * 0.70),
        )

        training_values = df[target].iloc[
            :training_end
        ].dropna()

        if training_values.empty:
            continue

        threshold = float(
            training_values.quantile(0.95)
        )

        for horizon_name in HORIZONS:

            prediction_path = (
                OUTPUT_DIR
                / f"predictions_{target}_{horizon_name}.csv"
            )

            if not prediction_path.exists():
                continue

            predictions_df = pd.read_csv(
                prediction_path
            )

            if "predicted" not in predictions_df.columns:
                continue

            warning_mask = (
                pd.to_numeric(
                    predictions_df["predicted"],
                    errors="coerce",
                ) > threshold
            )

            warning_df = predictions_df.loc[
                warning_mask
            ].copy()

            if warning_df.empty:
                continue

            warning_df["asset_id"] = ASSET_ID
            warning_df["target_metric"] = target
            warning_df["warning_threshold"] = threshold
            warning_df["warning_type"] = "future_temperature"
            warning_df["is_warning"] = True

            warning_frames.append(warning_df)

    if warning_frames:
        warnings_df = pd.concat(
            warning_frames,
            ignore_index=True,
        )
    else:
        warnings_df = pd.DataFrame(
            columns=[
                "asset_id",
                "target_metric",
                "warning_threshold",
                "warning_type",
                "is_warning",
            ]
        )

    warnings_df.to_csv(
        OUTPUT_DIR / "future_temperature_warnings.csv",
        index=False,
    )

    print(
        "\nFuture temperature warnings saved."
    )


# ============================================================
# 12. MAIN WORKFLOW
# ============================================================

def main():

    print("\nDATA CENTER PREDICTIVE MAINTENANCE")
    print("=" * 65)

    # Load telemetry (prioritizing labeled dataset).
    df, available_metrics, median_interval_seconds = (
        load_data()
    )

    # Load synthetic fault scenarios dataset if available.
    synthetic_df = load_synthetic_data()

    # Plot the available telemetry.
    plot_telemetry(
        df,
        available_metrics,
    )

    # Create lag and rolling features.
    feature_df, feature_columns = create_features(
        df,
        available_metrics,
    )

    all_results = []
    standardized_records = []

    # Run forecasting for every configured target and horizon.
    for target in TARGETS:

        if target not in available_metrics:
            print(
                f"\nSkipping unavailable target: {target}"
            )
            continue

        for horizon_name, horizon_steps in HORIZONS.items():

            result = run_forecast(
                df=feature_df,
                feature_columns=feature_columns,
                target=target,
                horizon_name=horizon_name,
                horizon_steps=horizon_steps,
                median_interval_seconds=median_interval_seconds,
                synthetic_df=synthetic_df,
            )

            if result is None:
                continue

            metrics = result["test_metrics"]
            syn_metrics = result.get("synthetic_test_metrics")

            result_entry = {
                "target": result["target"],
                "horizon": result["horizon"],
                "horizon_steps": result["horizon_steps"],
                "horizon_minutes": result["horizon_minutes"],
                "selected_model": result["selected_model"],
                "MAE": round(metrics["MAE"], 4),
                "RMSE": round(metrics["RMSE"], 4),
                "R2": round(metrics["R2"], 4),
                "MAPE_Pct": round(metrics.get("MAPE", np.nan), 3),
                "Forecast_Accuracy_Pct": round(metrics.get("Accuracy_Pct", np.nan), 2),
            }
            if syn_metrics:
                result_entry["synthetic_MAE"] = round(syn_metrics["MAE"], 4)
                result_entry["synthetic_RMSE"] = round(syn_metrics["RMSE"], 4)
                result_entry["synthetic_R2"] = round(syn_metrics["R2"], 4)
                result_entry["synthetic_MAPE_Pct"] = round(syn_metrics.get("MAPE", np.nan), 3)
                result_entry["synthetic_Forecast_Accuracy_Pct"] = round(syn_metrics.get("Accuracy_Pct", np.nan), 2)

            all_results.append(result_entry)

            # Convert every selected-method test prediction
            # into the standardized schema.
            predictions = result["test_predictions"]

            timestamps = result["test_timestamps"]

            target_timestamps = result["target_timestamps"]

            for i, predicted_value in enumerate(predictions):

                if not np.isfinite(predicted_value):
                    continue

                record = create_standardized_prediction(
                    predicted_value=predicted_value,
                    asset_id=ASSET_ID,
                    target_metric=target,
                    horizon_minutes=result["horizon_minutes"],
                    model_version=MODEL_VERSION,
                    current_timestamp=timestamps.iloc[i],
                    target_timestamp=target_timestamps.iloc[i],
                    model_name=result["selected_model"],
                )

                standardized_records.append(record)

    # Save evaluation metrics separately from prediction records.
    if all_results:

        results_df = pd.DataFrame(
            all_results
        )

        results_df.to_csv(
            OUTPUT_DIR / "forecast_metrics.csv",
            index=False,
        )

        print("\nFORECAST EVALUATION METRICS")
        print("-" * 65)
        print(
            results_df.to_string(index=False)
        )

    else:
        print(
            "\nNo forecasting experiments completed successfully."
        )

    # Save standardized prediction records.
    if standardized_records:

        standardized_df = pd.DataFrame(
            standardized_records
        )

        standardized_df.to_csv(
            OUTPUT_DIR / "standardized_predictions.csv",
            index=False,
        )

        print(
            "\nStandardized predictions saved to:"
        )

        print(
            OUTPUT_DIR / "standardized_predictions.csv"
        )

        print("\nSAMPLE STANDARDIZED RECORDS")
        print(
            standardized_df.head().to_string(index=False)
        )

    else:
        print(
            "\nNo standardized predictions were generated."
        )

    # Generate the remaining maintenance outputs.
    generate_degradation_indicators(
        df,
        available_metrics,
    )

    # Supervised anomaly detection & fault diagnostics + baseline
    run_anomaly_detection(
        df,
        available_metrics,
        feature_df=feature_df,
        feature_columns=feature_columns,
        synthetic_df=synthetic_df,
    )

    # Supervised 5-minute onset early warnings
    generate_supervised_early_warnings(
        df,
        feature_df,
        feature_columns,
        synthetic_df=synthetic_df,
    )

    generate_temperature_warnings(
        df,
        available_metrics,
    )

    generate_future_temperature_warnings(
        df,
        available_metrics,
    )

    save_consolidated_evaluation_metrics(OUTPUT_DIR)

    print("\n" + "=" * 65)
    print("PREDICTIVE MAINTENANCE WORKFLOW COMPLETED")
    print(f"Output directory: {OUTPUT_DIR}")
    print("=" * 65)


def save_consolidated_evaluation_metrics(output_dir):
    """
    Consolidates all predictive maintenance model evaluation metrics into a single
    structured evaluation table and saves as all_model_evaluation_metrics.csv.
    """
    output_dir = Path(output_dir)
    master_records = []

    # 1. Forecasting Metrics
    fc_file = output_dir / "forecast_metrics.csv"
    if fc_file.exists():
        fc_df = pd.read_csv(fc_file)
        for _, row in fc_df.iterrows():
            master_records.append({
                "module": "predictive_maintenance",
                "model_name": row.get("selected_model", "Unknown"),
                "task_type": "Regression / Forecasting",
                "target_variable": f"{row.get('target', '')} ({row.get('horizon', '')})",
                "condition": "Observed Telemetry",
                "accuracy_pct": row.get("Forecast_Accuracy_Pct", np.nan),
                "mae": row.get("MAE", np.nan),
                "rmse": row.get("RMSE", np.nan),
                "r2_score": row.get("R2", np.nan),
                "mape_pct": row.get("MAPE_Pct", np.nan),
                "precision": np.nan,
                "recall": np.nan,
                "f1_score": np.nan,
                "pr_auc": np.nan,
                "roc_auc": np.nan,
            })
            if pd.notna(row.get("synthetic_MAE")):
                master_records.append({
                    "module": "predictive_maintenance",
                    "model_name": row.get("selected_model", "Unknown"),
                    "task_type": "Regression / Forecasting",
                    "target_variable": f"{row.get('target', '')} ({row.get('horizon', '')})",
                    "condition": "Synthetic Fault Scenarios",
                    "accuracy_pct": row.get("synthetic_Forecast_Accuracy_Pct", np.nan),
                    "mae": row.get("synthetic_MAE", np.nan),
                    "rmse": row.get("synthetic_RMSE", np.nan),
                    "r2_score": row.get("synthetic_R2", np.nan),
                    "mape_pct": row.get("synthetic_MAPE_Pct", np.nan),
                    "precision": np.nan,
                    "recall": np.nan,
                    "f1_score": np.nan,
                    "pr_auc": np.nan,
                    "roc_auc": np.nan,
                })

    # 2. Supervised Anomaly Detection
    anom_file = output_dir / "supervised_anomaly_metrics.csv"
    if anom_file.exists():
        anom_df = pd.read_csv(anom_file)
        for _, row in anom_df.iterrows():
            master_records.append({
                "module": "predictive_maintenance",
                "model_name": row.get("model", "Unknown"),
                "task_type": f"Binary Classification ({row.get('type', 'Supervised')})",
                "target_variable": "anomaly_label",
                "condition": "Observed Telemetry (Test Set)",
                "accuracy_pct": row.get("test_accuracy_pct", np.nan),
                "mae": np.nan,
                "rmse": np.nan,
                "r2_score": np.nan,
                "mape_pct": np.nan,
                "precision": row.get("test_precision", np.nan),
                "recall": row.get("test_recall", np.nan),
                "f1_score": row.get("test_f1", np.nan),
                "pr_auc": row.get("test_pr_auc", np.nan),
                "roc_auc": row.get("test_roc_auc", np.nan),
            })

    # 3. Fault Diagnostic Classifier
    fault_file = output_dir / "fault_diagnostic_metrics.csv"
    if fault_file.exists():
        f_df = pd.read_csv(fault_file)
        for _, row in f_df.iterrows():
            master_records.append({
                "module": "predictive_maintenance",
                "model_name": row.get("model", "RandomForest_Fault_Classifier"),
                "task_type": "Multiclass Fault Classification",
                "target_variable": "fault_type",
                "condition": "Observed Telemetry (Test Set)",
                "accuracy_pct": row.get("test_accuracy_pct", np.nan),
                "mae": np.nan,
                "rmse": np.nan,
                "r2_score": np.nan,
                "mape_pct": np.nan,
                "precision": row.get("weighted_precision", np.nan),
                "recall": row.get("weighted_recall", np.nan),
                "f1_score": row.get("weighted_f1", np.nan),
                "pr_auc": np.nan,
                "roc_auc": np.nan,
            })

    # 4. Supervised Early Warning
    ew_file = output_dir / "early_warning_evaluation.csv"
    if ew_file.exists():
        ew_df = pd.read_csv(ew_file)
        for _, row in ew_df.iterrows():
            master_records.append({
                "module": "predictive_maintenance",
                "model_name": row.get("model", "HistGradientBoostingClassifier"),
                "task_type": "Prognostic Early Warning (5-min lookahead)",
                "target_variable": row.get("target", "anomaly_within_next_15"),
                "condition": "Normal Telemetry Onset (Test Set)",
                "accuracy_pct": row.get("accuracy_pct", np.nan),
                "mae": np.nan,
                "rmse": np.nan,
                "r2_score": np.nan,
                "mape_pct": np.nan,
                "precision": row.get("precision", np.nan),
                "recall": row.get("recall", np.nan),
                "f1_score": row.get("f1_score", np.nan),
                "pr_auc": row.get("pr_auc", np.nan),
                "roc_auc": row.get("roc_auc", np.nan),
            })

    if master_records:
        all_metrics_df = pd.DataFrame(master_records)
        all_metrics_path = output_dir / "all_model_evaluation_metrics.csv"
        all_metrics_df.to_csv(all_metrics_path, index=False)
        print("\n" + "=" * 65)
        print(f"CONSOLIDATED PREDICTIVE MAINTENANCE EVALUATION TABLE:")
        print(f"Saved: {all_metrics_path}")
        print("=" * 65)
        print(all_metrics_df[["model_name", "task_type", "target_variable", "accuracy_pct", "f1_score", "mae", "r2_score"]].to_string(index=False))


if __name__ == "__main__":
    main()