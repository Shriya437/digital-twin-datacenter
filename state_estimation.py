# -*- coding: utf-8 -*-
"""Machine Learning Module: Feature engineering, models, controlled experiments, plots, gates, and persistence."""

import os
import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from sklearn.ensemble import (
    RandomForestRegressor,
    HistGradientBoostingRegressor
)
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score
)
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.base import clone

from config import (
    DATA_PATH,
    OUTPUT_DIR,
    METRICS,
    TARGETS,
    RANDOM_STATE,
    MODEL_PATH
)

def interpolation_baseline(series):
    return series.interpolate(method="linear", limit_area="inside")

def get_feature_columns(target):
    return [col for col in METRICS if col != target] + ["time_sin", "time_cos"]

def build_models():
    rf = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("model", RandomForestRegressor(
            n_estimators=200,
            min_samples_leaf=3,
            random_state=RANDOM_STATE,
            n_jobs=-1
        ))
    ])
    hgb = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("model", HistGradientBoostingRegressor(
            max_iter=150,
            max_leaf_nodes=15,
            l2_regularization=1.0,
            random_state=RANDOM_STATE
        ))
    ])
    return {
        "Random Forest": rf,
        "HistGradientBoosting": hgb
    }

def calculate_metrics(y_true, y_pred):
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    valid = np.isfinite(y_true) & np.isfinite(y_pred)
    y_true, y_pred = y_true[valid], y_pred[valid]

    if len(y_true) == 0:
        return {"n": 0, "MAE": np.nan, "RMSE": np.nan, "R2": np.nan}
    return {
        "n": len(y_true),
        "MAE": mean_absolute_error(y_true, y_pred),
        "RMSE": np.sqrt(mean_squared_error(y_true, y_pred)),
        "R2": r2_score(y_true, y_pred) if len(y_true) >= 2 else np.nan
    }

def estimate_temperature(target, input_frame, models_by_target, uncertainty_margins, model_name="Random Forest"):
    if target not in TARGETS:
        raise ValueError(f"Target '{target}' not supported. Expected one of: {TARGETS}")

    features = get_feature_columns(target)
    model = models_by_target[target][model_name]

    X = input_frame.copy()
    if "time_sin" not in X.columns or "time_cos" not in X.columns:
        if "timestamp" in X.columns:
            ts = pd.to_datetime(X["timestamp"], utc=True)
            secs = ts.dt.hour * 3600 + ts.dt.minute * 60 + ts.dt.second
            X["time_sin"] = np.sin(2 * np.pi * secs / 86400)
            X["time_cos"] = np.cos(2 * np.pi * secs / 86400)
        else:
            X["time_sin"] = 0.0
            X["time_cos"] = 0.0

    X_in = X[features]
    predictions = model.predict(X_in)
    margin = uncertainty_margins[(target, model_name)]

    result = pd.DataFrame(index=input_frame.index)
    result["asset_id"] = "M100_NODE_1"
    result["target_metric"] = target
    result["estimated_value"] = predictions
    result["lower_estimate"] = predictions - margin
    result["upper_estimate"] = predictions + margin
    result["uncertainty_margin"] = margin
    result["estimate_method"] = model_name
    result["is_estimated"] = True
    result["is_simulated"] = False
    result["missing_feature_count"] = X_in.isna().sum(axis=1)
    result["quality_warning"] = result["missing_feature_count"] > 0
    result["confidence_status"] = np.where(
        result["quality_warning"],
        "input_quality_warning",
        "nominal_input_quality"
    )
    return result

def apply_estimation_gate(estimate_result, max_missing_features=2):
    result = estimate_result.copy()
    defer = result["missing_feature_count"] > max_missing_features

    result["estimate_status"] = np.where(defer, "estimate_deferred", "estimate_available")
    result.loc[defer, ["estimated_value", "lower_estimate", "upper_estimate"]] = np.nan
    return result

def run_state_estimation_pipeline():
    df = pd.read_csv(DATA_PATH)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)

    for col in METRICS:
        df[col] = pd.to_numeric(df[col], errors="coerce")
        df[col] = df[col].replace([np.inf, -np.inf], np.nan)

    model_df = df.copy()

    # Time features
    seconds_of_day = (
        model_df["timestamp"].dt.hour * 3600
        + model_df["timestamp"].dt.minute * 60
        + model_df["timestamp"].dt.second
    )
    model_df["time_sin"] = np.sin(2 * np.pi * seconds_of_day / 86400)
    model_df["time_cos"] = np.cos(2 * np.pi * seconds_of_day / 86400)

    # Chronological Split
    n = len(model_df)
    train_end = int(n * 0.70)
    val_end = int(n * 0.85)

    train_df = model_df.iloc[:train_end].copy()
    val_df = model_df.iloc[train_end:val_end].copy()
    test_df = model_df.iloc[val_end:].copy()

    print(f"Dataset Split: Train={len(train_df)}, Val={len(val_df)}, Test={len(test_df)}")

    # Model training
    models_by_target = {}
    validation_residuals = {}
    uncertainty_margins = {}

    for target in TARGETS:
        features = get_feature_columns(target)
        X_train = train_df[features]
        y_train = train_df[target]
        valid_train = y_train.notna()

        X_val = val_df[features]
        y_val = val_df[target]
        valid_val = y_val.notna()

        models_by_target[target] = {}

        for model_name, model_template in build_models().items():
            model = clone(model_template)
            model.fit(X_train.loc[valid_train], y_train.loc[valid_train])
            models_by_target[target][model_name] = model

            val_pred = model.predict(X_val.loc[valid_val])
            residuals = y_val.loc[valid_val].to_numpy() - val_pred
            validation_residuals[(target, model_name)] = residuals

            q90 = float(np.quantile(np.abs(residuals), 0.90))
            uncertainty_margins[(target, model_name)] = q90
            print(f"[{target}] Trained {model_name} | Val 90% Empirical Margin: {q90:.4f}°C")

    # Experiment 1: Random Missingness
    missing_rates = [0.05, 0.10, 0.20]
    results = []

    for target in TARGETS:
        features = get_feature_columns(target)
        target_test = test_df[target].copy()
        valid_positions = np.flatnonzero(target_test.notna().to_numpy())

        rng = np.random.default_rng(RANDOM_STATE)
        shuffled_positions = rng.permutation(valid_positions)

        for rate in missing_rates:
            n_mask = max(1, int(round(rate * len(valid_positions))))
            masked_positions = shuffled_positions[:n_mask]
            mask = np.zeros(len(test_df), dtype=bool)
            mask[masked_positions] = True
            y_true = target_test.to_numpy()[mask]

            masked_series = target_test.copy()
            masked_series.iloc[masked_positions] = np.nan
            interpolated = interpolation_baseline(masked_series)
            y_interp = interpolated.iloc[masked_positions].to_numpy()

            results.append({
                "target": target,
                "missing_rate": rate,
                "method": "Interpolation",
                **calculate_metrics(y_true, y_interp),
                "interval_coverage": np.nan,
                "interval_margin": np.nan
            })

            X_test = test_df[features]
            for model_name, model in models_by_target[target].items():
                y_pred = model.predict(X_test)[mask]
                metrics = calculate_metrics(y_true, y_pred)
                margin = uncertainty_margins[(target, model_name)]
                lower, upper = y_pred - margin, y_pred + margin
                coverage = float(np.mean((y_true >= lower) & (y_true <= upper)))

                results.append({
                    "target": target,
                    "missing_rate": rate,
                    "method": model_name,
                    **metrics,
                    "interval_coverage": coverage,
                    "interval_margin": margin
                })

    evaluation_results = pd.DataFrame(results)
    evaluation_results.to_csv(OUTPUT_DIR / "random_missingness_evaluation.csv", index=False)

    # Experiment 2: Contiguous Gaps
    typical_interval = df["timestamp"].diff().dt.total_seconds().loc[lambda x: x > 0].median()

    def evaluate_contiguous_gap(target, gap_minutes):
        features = get_feature_columns(target)
        target_series = test_df[target].reset_index(drop=True)
        X_test = test_df[features].reset_index(drop=True)

        rows_per_gap = max(1, int(round(gap_minutes * 60 / typical_interval)))
        start = (len(test_df) - rows_per_gap) // 2
        end = start + rows_per_gap

        if start < 1 or end >= len(test_df):
            raise ValueError("Test set is too short for contiguous gap evaluation.")

        true_values = target_series.iloc[start:end].to_numpy()

        masked_series = target_series.copy()
        masked_series.iloc[start:end] = np.nan
        interp_pred = interpolation_baseline(masked_series).iloc[start:end].to_numpy()

        output = [{
            "target": target,
            "gap_minutes": gap_minutes,
            "method": "Interpolation",
            **calculate_metrics(true_values, interp_pred)
        }]

        for model_name, model in models_by_target[target].items():
            preds = model.predict(X_test.iloc[start:end])
            output.append({
                "target": target,
                "gap_minutes": gap_minutes,
                "method": model_name,
                **calculate_metrics(true_values, preds)
            })
        return output

    gap_results = []
    for target in TARGETS:
        for gap_min in [1, 5, 15]:
            gap_results.extend(evaluate_contiguous_gap(target, gap_min))

    gap_evaluation = pd.DataFrame(gap_results)
    gap_evaluation.to_csv(OUTPUT_DIR / "contiguous_gap_evaluation.csv", index=False)

    # Experiment 3: Predictor Reliability
    def evaluate_missing_predictors(target, predictor_missing_rate=0.20):
        features = get_feature_columns(target)
        X_test = test_df[features].copy().reset_index(drop=True)
        y_true = test_df[target].to_numpy()

        rng = np.random.default_rng(RANDOM_STATE)
        for col in features:
            if col in ["time_sin", "time_cos"]:
                continue
            mask = rng.random(len(X_test)) < predictor_missing_rate
            X_test.loc[mask, col] = np.nan

        output = []
        for model_name, model in models_by_target[target].items():
            predictions = model.predict(X_test)
            output.append({
                "target": target,
                "predictor_missing_rate": predictor_missing_rate,
                "method": model_name,
                **calculate_metrics(y_true, predictions)
            })
        return output

    predictor_missing_results = []
    for target in TARGETS:
        for rate in [0.0, 0.10, 0.20, 0.40]:
            predictor_missing_results.extend(evaluate_missing_predictors(target, rate))

    predictor_missing_df = pd.DataFrame(predictor_missing_results)
    predictor_missing_df.to_csv(OUTPUT_DIR / "predictor_reliability_evaluation.csv", index=False)

    # Visualizations
    plt.figure(figsize=(14, 5))
    features_p0 = get_feature_columns("p0_vdd_temp")
    y_true_p0 = test_df["p0_vdd_temp"].to_numpy()
    y_pred_rf = models_by_target["p0_vdd_temp"]["Random Forest"].predict(test_df[features_p0])

    plt.plot(test_df["timestamp"], y_true_p0, label="Actual Temperature", alpha=0.8)
    plt.plot(test_df["timestamp"], y_pred_rf, label="Random Forest Estimate", linestyle="--", alpha=0.8)
    plt.xlabel("Timestamp")
    plt.ylabel("Temperature (°C)")
    plt.title("p0_vdd_temp: Actual vs ML State Estimates (Held-out Test Period)")
    plt.legend()
    plt.xticks(rotation=30)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "actual_vs_estimate_p0.png", dpi=150)
    plt.close()

    fig, axes = plt.subplots(1, 2, figsize=(14, 5), sharey=True)
    for idx, target in enumerate(TARGETS):
        subset = evaluation_results[evaluation_results["target"] == target]
        for method in subset["method"].unique():
            method_data = subset[subset["method"] == method].sort_values("missing_rate")
            axes[idx].plot(method_data["missing_rate"] * 100, method_data["MAE"], marker="o", label=method)
        axes[idx].set_xlabel("Missing Target Readings (%)")
        axes[idx].set_ylabel("MAE (°C)")
        axes[idx].set_title(f"Missingness Impact — {target}")
        axes[idx].legend()
        axes[idx].grid(True, linestyle=":", alpha=0.6)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "missingness_evaluation_plot.png", dpi=150)
    plt.close()

    fig, axes = plt.subplots(1, 2, figsize=(14, 5), sharey=True)
    for idx, target in enumerate(TARGETS):
        subset = gap_evaluation[gap_evaluation["target"] == target]
        for method in subset["method"].unique():
            method_data = subset[subset["method"] == method].sort_values("gap_minutes")
            axes[idx].plot(method_data["gap_minutes"], method_data["MAE"], marker="o", label=method)
        axes[idx].set_xlabel("Outage Gap Duration (Minutes)")
        axes[idx].set_ylabel("MAE (°C)")
        axes[idx].set_title(f"Gap Outage Sensitivity — {target}")
        axes[idx].legend()
        axes[idx].grid(True, linestyle=":", alpha=0.6)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "contiguous_gap_plot.png", dpi=150)
    plt.close()

    # Reusable Interface & Gating Demonstration
    test_sample = test_df.iloc[:5].copy()
    test_sample.loc[test_sample.index[2], "ambient"] = np.nan
    test_sample.loc[test_sample.index[3], ["ambient", "p1_vdd_temp", "fan0_0"]] = np.nan

    raw_estimates = estimate_temperature("p0_vdd_temp", test_sample, models_by_target, uncertainty_margins, model_name="Random Forest")
    gated_estimates = apply_estimation_gate(raw_estimates, max_missing_features=2)
    print("Demo: Reusable Function with Gate Applied")
    print(gated_estimates[[
        "asset_id", "target_metric", "estimated_value", "lower_estimate",
        "upper_estimate", "uncertainty_margin", "missing_feature_count", "estimate_status"
    ]].to_string())

    # Save Bundle Artifact
    model_bundle = {
        "models_by_target": models_by_target,
        "features_by_target": {t: get_feature_columns(t) for t in TARGETS},
        "uncertainty_margins": uncertainty_margins,
        "training_period": [str(train_df["timestamp"].min()), str(train_df["timestamp"].max())],
        "validation_period": [str(val_df["timestamp"].min()), str(val_df["timestamp"].max())],
        "targets": TARGETS,
        "model_version": "member1-state-estimation-v1",
        "dataset_source": "M100 ExaData",
        "is_simulated": False
    }
    joblib.dump(model_bundle, MODEL_PATH)
    print(f"Model Bundle persisted: {MODEL_PATH}")

if __name__ == "__main__":
    run_state_estimation_pipeline()