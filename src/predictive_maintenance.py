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
)
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore", category=FutureWarning)


# ============================================================
# 1. CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

CSV_PATH = BASE_DIR / "data" / "m100_node1_digital_twin.csv"

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

def load_data():
    """Load and clean the telemetry dataset."""

    if not CSV_PATH.exists():
        raise FileNotFoundError(
            f"Telemetry dataset not found:\n{CSV_PATH}"
        )

    df = pd.read_csv(CSV_PATH)

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
    # This prevents features and future targets from crossing gaps.
    gap_threshold = 1.5 * median_interval_seconds

    df["_segment"] = (
        intervals > gap_threshold
    ).cumsum()

    print("\nDATASET INFORMATION")
    print("-" * 60)
    print(f"Dataset: {CSV_PATH}")
    print(f"Rows: {len(df)}")
    print(f"Available metrics: {available_metrics}")
    print(
        "Median sampling interval: "
        f"{median_interval_seconds:.2f} seconds"
    )
    print(
        f"Approximate samples per minute: "
        f"{60 / median_interval_seconds:.2f}"
    )

    return df, available_metrics, median_interval_seconds


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
            n_estimators=100,
            max_depth=12,
            min_samples_leaf=2,
            random_state=RANDOM_STATE,
            n_jobs=-1,
        )

    elif model_name == "HistGradientBoosting":

        estimator = HistGradientBoostingRegressor(
            max_iter=100,
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

    return {
        "MAE": float(mae),
        "RMSE": float(rmse),
        "R2": float(r2),
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

    # Chronological split: 70% train, 15% validation, 15% test.
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

    # Select the model with the lowest validation MAE.
    candidate_results = [
        item for item in candidate_results
        if np.isfinite(item["validation_MAE"])
    ]

    if not candidate_results:
        print("No valid forecasting candidate was produced.")
        return None

    best_candidate = min(
        candidate_results,
        key=lambda item: item["validation_MAE"],
    )

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

    return {
        "target": target,
        "horizon": horizon_name,
        "horizon_steps": horizon_steps,
        "horizon_minutes": horizon_minutes,
        "selected_model": best_name,
        "test_metrics": test_metrics,
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
):
    """
    Train Isolation Forest on the first 70% of observations.
    Generate anomaly labels and scores for the telemetry.
    """

    anomaly_metrics = [
        metric for metric in available_metrics
        if df[metric].notna().sum() > 0
    ]

    if not anomaly_metrics:
        print("\nNo usable metrics for anomaly detection.")
        return

    X = df[anomaly_metrics].replace(
        [np.inf, -np.inf],
        np.nan,
    )

    split_index = int(len(df) * 0.70)

    if split_index < 10:
        print(
            "\nNot enough observations for anomaly detection."
        )
        return

    # Impute using training data only.
    imputer = SimpleImputer(
        strategy="median"
    )

    X_train = imputer.fit_transform(
        X.iloc[:split_index]
    )

    X_all = imputer.transform(X)

    detector = IsolationForest(
        n_estimators=100,
        contamination="auto",
        random_state=RANDOM_STATE,
    )

    detector.fit(X_train)

    # Isolation Forest returns -1 for anomalies and 1 for normal.
    labels = detector.predict(X_all)

    scores = detector.decision_function(X_all)

    anomaly_df = pd.DataFrame(
        {
            "timestamp": df["timestamp"],
            "anomaly_label": labels,
            "anomaly_score": scores,
            "is_anomaly": labels == -1,
        }
    )

    for metric in anomaly_metrics:
        anomaly_df[metric] = df[metric].to_numpy()

    anomaly_df.to_csv(
        OUTPUT_DIR / "anomaly_detection_results.csv",
        index=False,
    )

    plt.figure(figsize=(12, 5))

    plt.plot(
        df["timestamp"],
        scores,
        label="Anomaly score",
        linewidth=1,
    )

    anomaly_positions = np.flatnonzero(
        labels == -1
    )

    if len(anomaly_positions) > 0:

        plt.scatter(
            df["timestamp"].iloc[anomaly_positions],
            scores[anomaly_positions],
            label="Detected anomaly",
            s=15,
        )

    plt.title("Isolation Forest Anomaly Detection")
    plt.xlabel("Timestamp")
    plt.ylabel("Decision Function Score")
    plt.legend()
    plt.xticks(rotation=30)
    plt.tight_layout()

    plt.savefig(
        OUTPUT_DIR / "anomaly_detection_plot.png",
        dpi=150,
    )

    plt.close()

    joblib.dump(
        {
            "imputer": imputer,
            "detector": detector,
            "metrics": anomaly_metrics,
        },
        OUTPUT_DIR / "anomaly_detection_model.joblib",
    )

    print(
        "\nAnomaly detection results saved."
    )


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

    # Load telemetry.
    df, available_metrics, median_interval_seconds = (
        load_data()
    )

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
            )

            if result is None:
                continue

            metrics = result["test_metrics"]

            all_results.append(
                {
                    "target": result["target"],
                    "horizon": result["horizon"],
                    "horizon_steps": result["horizon_steps"],
                    "horizon_minutes": result["horizon_minutes"],
                    "selected_model": result["selected_model"],
                    "MAE": metrics["MAE"],
                    "RMSE": metrics["RMSE"],
                    "R2": metrics["R2"],
                }
            )

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

    run_anomaly_detection(
        df,
        available_metrics,
    )

    generate_temperature_warnings(
        df,
        available_metrics,
    )

    generate_future_temperature_warnings(
        df,
        available_metrics,
    )

    print("\n" + "=" * 65)
    print("PREDICTIVE MAINTENANCE WORKFLOW COMPLETED")
    print(f"Output directory: {OUTPUT_DIR}")
    print("=" * 65)


if __name__ == "__main__":
    main()