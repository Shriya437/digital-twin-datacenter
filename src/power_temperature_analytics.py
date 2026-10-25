"""
================================================================================
MODULE 6: POWER AND TEMPERATURE ANALYTICS
Data Center Digital Twin Telemetry Analysis & Forecasting Pipeline
================================================================================

Features implemented:
6.1 — Power trend visualization:
      Plots all available power metrics (total_power, p0_power, p1_power,
      ps0_input_power, ps1_input_power) against timestamps, properly breaking
      across data gaps, and exports power metrics statistical summary.
6.2 — Temperature vs. power comparison:
      Generates both:
      a) Timestamp-based dual-axis comparison plot of power and temperatures.
      b) Scatter plot with linear regression trendline and Spearman/Pearson
         correlation annotations.
      Exports power-temperature quartile comparison CSV.
6.3 — Correlation analysis:
      Computes Spearman rank correlation (proposed workflow for monotonic
      coupling) and Pearson correlation, handles missing values pairwise with
      observation counts, generates an annotated heatmap, and provides an
      automated physical interpretation of key sensor relationships.
6.4 — Rolling summaries:
      Calculates rolling mean and rolling standard deviation for Power,
      Temperature, Fan Speed, and Ambient metrics, strictly respecting
      segment boundaries so rolling windows never cross telemetry gaps.
      Exports both long-form and wide-form CSVs and plots rolling trends.
6.5 — Energy consumption estimation:
      Integrates power over time using trapezoidal integration.
      Crucially computes dt and segment boundaries on the complete chronological
      timeline before filtering, validates endpoint readings per interval,
      performs power unit verification against telemetry plausibility, and
      exports interval energy_analysis.csv and energy_integration_summary.csv.
6.6 — What-if power analysis:
      Compares baseline power consumption against hypothetical reductions (5%,
      10%, 15%, 20%), computes estimated energy savings, documents assumptions
      (mathematical scenario vs. thermodynamic simulation), and saves CSV & chart.
6.7 — Future temperature forecasting:
      End-to-end Machine Learning forecasting pipeline:
      - Feature engineering with lags, rolling statistics, and cooling signals.
      - Chronological train/test split (no future data leakage).
      - Trains HistGradientBoostingRegressor / RandomForest model.
      - Evaluates forecast accuracy against persistence baseline (MAE, RMSE, R2, MAPE).
      - Generates predictions across the test set and for latest telemetry.
      - Saves future_temperature_predictions.csv, evaluation metrics CSV,
        standardized prediction record (JSON & CSV), and forecast plot.
Additional Analytics:
      - Processor temperature difference (P0 - P1) analysis & plot.
      - Fan speed trends analysis & plots.
      - PUE measurement requirements safeguard report.
"""

import argparse
import json
from pathlib import Path
import warnings

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

from sklearn.ensemble import (
    HistGradientBoostingRegressor,
    RandomForestRegressor,
    HistGradientBoostingClassifier,
    RandomForestClassifier,
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
    classification_report,
    confusion_matrix,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

# ============================================================
# CONFIGURATION & TELEMETRY DEFINITIONS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DEFAULT_LABELED_INPUT = (
    BASE_DIR
    / "data"
    / "m100_labeling"
    / "outputs"
    / "labeled_dataset"
    / "m100_node1_labeled_observed.csv"
)

DEFAULT_SYNTHETIC_INPUT = (
    BASE_DIR
    / "data"
    / "m100_labeling"
    / "outputs"
    / "labeled_dataset"
    / "m100_synthetic_fault_scenarios.csv"
)

POWER_METRICS = [
    "total_power",
    "p0_power",
    "p1_power",
    "ps0_input_power",
    "ps1_input_power",
]

TEMPERATURE_METRICS = [
    "p0_vdd_temp",
    "p1_vdd_temp",
]

FAN_METRICS = [
    "fan0_0",
    "fan1_0",
]

ENVIRONMENT_METRICS = [
    "ambient",
]

CORRELATION_METRICS = [
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

ROLLING_METRICS = [
    "total_power",
    "p0_power",
    "p1_power",
    "ps0_input_power",
    "ps1_input_power",
    "p0_vdd_temp",
    "p1_vdd_temp",
    "fan0_0",
    "fan1_0",
    "ambient",
]

DEFAULT_MAX_GAP_SECONDS = 60.0
ROLLING_WINDOW = 5
ROLLING_MIN_PERIODS = 3
DEFAULT_FORECAST_HORIZON_STEPS = 15  # ~5 minutes when sampling is 20s
RANDOM_STATE = 42


# ============================================================
# CLI ARGUMENT PARSER
# ============================================================

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Data center power and temperature analytics pipeline"
    )

    parser.add_argument(
        "--input",
        default="data/m100_node1_digital_twin.csv",
        help="Path to the telemetry CSV file (default: data/m100_node1_digital_twin.csv)",
    )

    parser.add_argument(
        "--synthetic-input",
        default=str(DEFAULT_SYNTHETIC_INPUT),
        help="Path to the synthetic fault scenarios CSV file (default: data/m100_labeling/outputs/labeled_dataset/m100_synthetic_fault_scenarios.csv)",
    )

    parser.add_argument(
        "--output-dir",
        default="outputs/member3_outputs",
        help="Directory for generated analytics outputs (default: outputs/member3_outputs)",
    )

    parser.add_argument(
        "--max-gap-seconds",
        type=float,
        default=DEFAULT_MAX_GAP_SECONDS,
        help="Maximum permitted gap between consecutive samples in seconds (default: 60.0)",
    )

    parser.add_argument(
        "--confirm-power-unit",
        choices=["W", "kW", "mW", "auto"],
        default="W",
        help="Power unit verified from dataset documentation (default: W with plausibility verification)",
    )

    parser.add_argument(
        "--energy-column",
        default="total_power",
        help="Power column to integrate for energy estimation (default: total_power)",
    )

    parser.add_argument(
        "--forecast-target",
        default="p0_vdd_temp",
        help="Target temperature metric for forecasting (default: p0_vdd_temp)",
    )

    parser.add_argument(
        "--forecast-horizon-minutes",
        type=float,
        default=5.0,
        help="Forecasting horizon in minutes (default: 5.0 minutes)",
    )

    parser.add_argument(
        "--asset-id",
        default="M100_NODE_1",
        help="Identifier of the monitored physical asset (default: M100_NODE_1)",
    )

    return parser.parse_args()


# ============================================================
# DATA INGESTION & QUALITY VALIDATION
# ============================================================

def load_telemetry(input_path):
    """Load, validate and chronologically sort telemetry dataframe."""
    input_path = Path(input_path)

    # Prefer labeled observed dataset if the default input was passed or not found
    if (not input_path.exists() or input_path.name == "m100_node1_digital_twin.csv") and DEFAULT_LABELED_INPUT.exists():
        input_path = DEFAULT_LABELED_INPUT

    if not input_path.exists():
        raise FileNotFoundError(f"Telemetry CSV not found: {input_path.resolve()}")

    df = pd.read_csv(input_path)

    if df.empty:
        raise ValueError("The input CSV contains no records.")

    if "timestamp" not in df.columns:
        raise ValueError("Required column 'timestamp' is missing. Check input CSV column names.")

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
    invalid_timestamps = int(df["timestamp"].isna().sum())

    # Invalid timestamps cannot be used in time-series analysis
    df = df.dropna(subset=["timestamp"]).copy()

    if df.empty:
        raise ValueError("No valid timestamps remain in the input CSV.")

    # Convert all telemetry metrics to numeric floats
    all_metrics = set(POWER_METRICS + TEMPERATURE_METRICS + FAN_METRICS + ENVIRONMENT_METRICS)
    for column in all_metrics.intersection(df.columns):
        df[column] = pd.to_numeric(df[column], errors="coerce")
        df[column] = df[column].replace([np.inf, -np.inf], np.nan)

    # Preserve and cast label and metadata columns if present
    for label_col in ["anomaly_label", "label_valid", "anomaly_within_next_15"]:
        if label_col in df.columns:
            df[label_col] = pd.to_numeric(df[label_col], errors="coerce")

    # Chronologically sort with stable mergesort
    df = df.sort_values("timestamp", kind="mergesort").reset_index(drop=True)

    print("\n" + "=" * 50)
    print("DATASET INGESTION SUMMARY")
    print("=" * 50)
    print(f"File path: {input_path}")
    print(f"Total valid timestamp records: {len(df)}")
    print(f"Invalid timestamps removed:    {invalid_timestamps}")
    if "split" in df.columns:
        print(f"Split distribution:            {dict(df['split'].value_counts())}")
    if "anomaly_label" in df.columns:
        print(f"Anomaly label counts:          {dict(df['anomaly_label'].value_counts())}")
    print(f"Start timestamp (UTC):         {df['timestamp'].min()}")
    print(f"End timestamp (UTC):           {df['timestamp'].max()}")

    return df, invalid_timestamps


def get_available_metrics(df, requested_metrics):
    """Return metrics from requested list that exist in dataframe."""
    available = [m for m in requested_metrics if m in df.columns]
    missing = [m for m in requested_metrics if m not in df.columns]
    if missing:
        print(f"Notice: Unavailable columns skipped: {missing}")
    return available


def save_data_quality_report(df, output_dir, invalid_timestamps):
    """Report missingness, duplicates and timestamp gaps."""
    report = []
    for column in df.columns:
        report.append({
            "column": column,
            "data_type": str(df[column].dtype),
            "missing_count": int(df[column].isna().sum()),
            "missing_percentage": float(df[column].isna().mean() * 100),
        })

    pd.DataFrame(report).to_csv(
        output_dir / "telemetry_missingness_report.csv",
        index=False,
    )

    timestamp_diff = df["timestamp"].diff().dt.total_seconds()
    positive_gaps = timestamp_diff[timestamp_diff > 0]

    gap_report = pd.DataFrame([{
        "total_rows": len(df),
        "invalid_timestamps_removed": invalid_timestamps,
        "duplicate_timestamp_rows": int(df["timestamp"].duplicated(keep=False).sum()),
        "nonpositive_timestamp_intervals": int((timestamp_diff <= 0).sum()),
        "positive_intervals": len(positive_gaps),
        "median_interval_seconds": float(positive_gaps.median()) if not positive_gaps.empty else np.nan,
        "maximum_interval_seconds": float(positive_gaps.max()) if not positive_gaps.empty else np.nan,
        "intervals_over_configured_limit": int((positive_gaps > DEFAULT_MAX_GAP_SECONDS).sum()),
    }])

    gap_report.to_csv(output_dir / "timestamp_quality_report.csv", index=False)
    print("Saved telemetry_missingness_report.csv and timestamp_quality_report.csv")


# ============================================================
# 6.1 — POWER TREND VISUALIZATION
# ============================================================

def plot_power_metrics(df, output_dir, max_gap_seconds=DEFAULT_MAX_GAP_SECONDS):
    """
    Plots all available power metrics against timestamps.
    Breaks lines across telemetry gaps exceeding max_gap_seconds.
    Exports power_metrics_summary.csv.
    """
    metrics = get_available_metrics(df, POWER_METRICS)

    if not metrics:
        print("No power-related columns found. Skipping power trend visualization.")
        return

    # Export statistical summary table
    summary_records = []
    for m in metrics:
        s = df[m].dropna()
        summary_records.append({
            "metric": m,
            "count_valid": int(s.count()),
            "missing_count": int(df[m].isna().sum()),
            "mean": float(s.mean()) if not s.empty else np.nan,
            "std": float(s.std()) if not s.empty else np.nan,
            "min": float(s.min()) if not s.empty else np.nan,
            "q25": float(s.quantile(0.25)) if not s.empty else np.nan,
            "median": float(s.median()) if not s.empty else np.nan,
            "q75": float(s.quantile(0.75)) if not s.empty else np.nan,
            "max": float(s.max()) if not s.empty else np.nan,
            "assumed_unit": "W (Watts)",
        })
    pd.DataFrame(summary_records).to_csv(output_dir / "power_metrics_summary.csv", index=False)

    # Plot lines with proper gap handling
    time_diff = df["timestamp"].diff().dt.total_seconds()
    gap_mask = (time_diff > max_gap_seconds) | (time_diff <= 0)

    fig, ax = plt.subplots(figsize=(14, 6))

    color_palette = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"]
    line_styles = ["-", "--", "-.", ":", "-"]

    for i, metric in enumerate(metrics):
        # Insert NaNs at gap locations to prevent artificial lines crossing gaps
        series = df[metric].copy()
        if gap_mask.any():
            series.loc[gap_mask] = np.nan

        color = color_palette[i % len(color_palette)]
        linestyle = line_styles[i % len(line_styles)]
        linewidth = 2.0 if metric == "total_power" else 1.2
        alpha = 1.0 if metric == "total_power" else 0.85

        ax.plot(
            df["timestamp"],
            series,
            label=f"{metric} (W)",
            color=color,
            linestyle=linestyle,
            linewidth=linewidth,
            alpha=alpha,
        )

    ax.set_title("Data Center Power Telemetry Trends (All Power Metrics)", fontsize=13, fontweight="bold")
    ax.set_xlabel("Timestamp (UTC)", fontsize=11)
    ax.set_ylabel("Power (Watts)", fontsize=11)
    ax.grid(True, linestyle="--", alpha=0.4)
    ax.legend(loc="upper right", framealpha=0.9)
    fig.autofmt_xdate()
    fig.tight_layout()

    fig.savefig(output_dir / "power_trends.png", dpi=180)
    plt.close(fig)

    print("Saved power_trends.png and power_metrics_summary.csv")


# ============================================================
# 6.2 — TEMPERATURE VS. POWER COMPARISON
# ============================================================

def plot_temperature_power(df, output_dir, max_gap_seconds=DEFAULT_MAX_GAP_SECONDS):
    """
    Generates BOTH:
    1. Timestamp-based dual-axis comparison plot of power and temperatures.
    2. Scatter plot with linear regression line and correlation annotations.
    Exports power_temperature_comparison.csv binned by power quartiles.
    """
    temp_cols = get_available_metrics(df, TEMPERATURE_METRICS)
    power_col = "total_power" if "total_power" in df.columns else None

    if not temp_cols or not power_col:
        print("Temperature-power comparison skipped: missing temperature or total_power.")
        return

    # 1. Timestamp-based Dual-Axis Comparison Plot
    fig, ax1 = plt.subplots(figsize=(14, 6))

    time_diff = df["timestamp"].diff().dt.total_seconds()
    gap_mask = (time_diff > max_gap_seconds) | (time_diff <= 0)

    # Left axis: Temperatures
    temp_colors = ["#d62728", "#ff7f0e"]
    for i, t_col in enumerate(temp_cols):
        t_series = df[t_col].copy()
        if gap_mask.any():
            t_series.loc[gap_mask] = np.nan
        ax1.plot(
            df["timestamp"],
            t_series,
            label=f"Temperature: {t_col} (°C)",
            color=temp_colors[i % len(temp_colors)],
            linewidth=1.2,
        )

    ax1.set_xlabel("Timestamp (UTC)", fontsize=11)
    ax1.set_ylabel("Processor Temperature (°C)", color="#d62728", fontsize=11)
    ax1.tick_params(axis="y", labelcolor="#d62728")
    ax1.grid(True, linestyle="--", alpha=0.3)

    # Right axis: Total Power
    ax2 = ax1.twinx()
    p_series = df[power_col].copy()
    if gap_mask.any():
        p_series.loc[gap_mask] = np.nan
    ax2.plot(
        df["timestamp"],
        p_series,
        label=f"Power: {power_col} (W)",
        color="#1f77b4",
        linewidth=1.4,
        alpha=0.75,
    )
    ax2.set_ylabel("Total Power (W)", color="#1f77b4", fontsize=11)
    ax2.tick_params(axis="y", labelcolor="#1f77b4")

    # Combine legends from both axes
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper right", framealpha=0.9)

    plt.title("Synchronized Temperature and Power Comparison Over Time", fontsize=13, fontweight="bold")
    fig.autofmt_xdate()
    fig.tight_layout()

    fig.savefig(output_dir / "temperature_power_comparison.png", dpi=180)
    plt.close(fig)

    # 2. Scatter Plot: Power vs. Temperature Relationship
    primary_temp = temp_cols[0]
    valid_pair = df[[power_col, primary_temp]].dropna()

    if len(valid_pair) > 2:
        fig, ax = plt.subplots(figsize=(9, 6))

        x = valid_pair[power_col]
        y = valid_pair[primary_temp]

        ax.scatter(x, y, alpha=0.45, color="#2b5c8f", edgecolors="none", s=22, label="Observed Telemetry")

        # Linear trendline
        poly_coeffs = np.polyfit(x, y, deg=1)
        poly_fn = np.poly1d(poly_coeffs)
        x_grid = np.linspace(x.min(), x.max(), 100)
        ax.plot(x_grid, poly_fn(x_grid), color="#d62728", linewidth=2.0, linestyle="--",
                label=f"Linear Fit (Slope: {poly_coeffs[0]:.4f} °C/W)")

        # Correlations
        spearman_rho = float(valid_pair[power_col].corr(valid_pair[primary_temp], method="spearman"))
        pearson_r = float(valid_pair[power_col].corr(valid_pair[primary_temp], method="pearson"))

        stats_box = (
            f"Spearman ρ: {spearman_rho:.3f}\n"
            f"Pearson r:  {pearson_r:.3f}\n"
            f"Slope:      {poly_coeffs[0]:.4f} °C/W\n"
            f"Samples:    {len(valid_pair)}"
        )
        ax.text(
            0.05, 0.95, stats_box,
            transform=ax.transAxes,
            verticalalignment="top",
            bbox=dict(boxstyle="round,pad=0.5", facecolor="#ffffff", edgecolor="#cccccc", alpha=0.9),
            fontsize=10,
        )

        ax.set_title(f"Thermal Response: Total Power vs. {primary_temp}", fontsize=13, fontweight="bold")
        ax.set_xlabel("Total Power (W)", fontsize=11)
        ax.set_ylabel(f"{primary_temp} (°C)", fontsize=11)
        ax.grid(True, linestyle="--", alpha=0.4)
        ax.legend(loc="lower right")
        fig.tight_layout()

        fig.savefig(output_dir / "power_temperature_relationship.png", dpi=180)
        plt.close(fig)

    # 3. Export quartile/regime comparison CSV
    if len(valid_pair) > 4:
        df_quartile = df[[power_col] + temp_cols].dropna().copy()
        try:
            df_quartile["power_regime"] = pd.qcut(df_quartile[power_col], q=4, duplicates="drop")
        except Exception:
            df_quartile["power_regime"] = pd.cut(df_quartile[power_col], bins=4)
        grouped = df_quartile.groupby("power_regime", observed=False).agg(["count", "mean", "std", "min", "median", "max"])
        grouped.columns = [f"{col}_{stat}" for col, stat in grouped.columns]
        grouped.reset_index().to_csv(output_dir / "power_temperature_comparison.csv", index=False)

    print("Saved temperature_power_comparison.png, power_temperature_relationship.png, and power_temperature_comparison.csv")


# ============================================================
# 6.3 — CORRELATION ANALYSIS (SPEARMAN & PEARSON + INTERPRETATION)
# ============================================================

def calculate_correlations(df, output_dir):
    """
    Computes Spearman rank correlation (primary proposed workflow) and Pearson correlation.
    Handles missing values pairwise and produces an annotated heatmap matrix.
    Generates automated physical interpretations of telemetry relationships.
    """
    metrics = get_available_metrics(df, CORRELATION_METRICS)

    if len(metrics) < 2:
        print("Correlation analysis skipped: fewer than 2 metrics available.")
        return

    # Spearman correlation: measures monotonic relationships, robust to nonlinearities
    spearman_corr = df[metrics].corr(method="spearman")
    spearman_corr.to_csv(output_dir / "metric_correlations.csv")

    # Pearson correlation for comparative reference
    pearson_corr = df[metrics].corr(method="pearson")
    pearson_corr.to_csv(output_dir / "metric_correlations_pearson.csv")

    # Pairwise sample counts
    counts_matrix = pd.DataFrame(index=metrics, columns=metrics, dtype=int)
    for m1 in metrics:
        for m2 in metrics:
            counts_matrix.loc[m1, m2] = int(df[[m1, m2]].dropna().shape[0])
    counts_matrix.to_csv(output_dir / "metric_correlation_counts.csv")

    # Heatmap visualization with cell values annotated
    fig, ax = plt.subplots(figsize=(11, 9))
    matrix_vals = spearman_corr.to_numpy(dtype=float)
    masked_matrix = np.ma.masked_invalid(matrix_vals)

    im = ax.imshow(masked_matrix, cmap="coolwarm", vmin=-1.0, vmax=1.0, aspect="auto")
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Spearman Rank Correlation (ρ)", fontsize=11)

    ax.set_xticks(range(len(metrics)))
    ax.set_yticks(range(len(metrics)))
    ax.set_xticklabels(metrics, rotation=45, ha="right", fontsize=9)
    ax.set_yticklabels(metrics, fontsize=9)

    # Annotate numeric values inside each cell
    for r in range(len(metrics)):
        for c in range(len(metrics)):
            val = matrix_vals[r, c]
            if np.isfinite(val):
                text_color = "white" if abs(val) > 0.6 else "black"
                ax.text(c, r, f"{val:.2f}", ha="center", va="center", color=text_color, fontsize=8)

    ax.set_title("Telemetry Metrics Spearman Correlation Matrix (Monotonic Association)", fontsize=12, fontweight="bold")
    fig.tight_layout()

    fig.savefig(output_dir / "metric_correlation_matrix.png", dpi=180)
    plt.close(fig)

    # Automated careful physical interpretation
    interpret_correlations(spearman_corr, output_dir)

    print("Saved metric_correlations.csv, metric_correlations_pearson.csv, and metric_correlation_matrix.png")


def interpret_correlations(corr_df, output_dir):
    """
    Carefully evaluates and documents physical couplings between key metrics.
    Exports correlation_interpretation.csv.
    """
    interpretations = []

    def get_corr(m1, m2):
        if m1 in corr_df.index and m2 in corr_df.columns:
            val = corr_df.loc[m1, m2]
            return float(val) if np.isfinite(val) else np.nan
        return np.nan

    def strength_category(val):
        if np.isnan(val):
            return "Undefined"
        abs_v = abs(val)
        if abs_v >= 0.8:
            return "Very Strong"
        elif abs_v >= 0.6:
            return "Strong"
        elif abs_v >= 0.4:
            return "Moderate"
        elif abs_v >= 0.2:
            return "Weak"
        else:
            return "Negligible"

    eval_pairs = [
        ("total_power", "p0_vdd_temp", "Total power vs Processor 0 temperature: Thermal dissipation coupling"),
        ("total_power", "p1_vdd_temp", "Total power vs Processor 1 temperature: Secondary socket thermal coupling"),
        ("p0_power", "p0_vdd_temp", "Processor 0 power vs Processor 0 temperature: Direct die dynamic heating"),
        ("p1_power", "p1_vdd_temp", "Processor 1 power vs Processor 1 temperature: Direct die dynamic heating"),
        ("fan0_0", "p0_vdd_temp", "Fan speed vs Processor temperature: Active closed-loop cooling response"),
        ("fan0_0", "total_power", "Fan speed vs Total power: Active cooling response to electrical workload"),
        ("ambient", "p0_vdd_temp", "Ambient temperature vs Processor temperature: Facility environmental baseline influence"),
        ("ambient", "total_power", "Ambient temperature vs Total power: Environmental workload coupling"),
        ("ps0_input_power", "total_power", "Power Supply 0 input vs Total power: PSU contribution coupling"),
        ("p0_vdd_temp", "p1_vdd_temp", "Processor 0 vs Processor 1 temperature: Dual-socket co-location thermal symmetry"),
    ]

    for m1, m2, desc in eval_pairs:
        rho = get_corr(m1, m2)
        if not np.isnan(rho):
            direction = "Positive" if rho > 0 else "Negative"
            strength = strength_category(rho)
            interpretations.append({
                "metric_pair": f"{m1} <-> {m2}",
                "spearman_rho": round(rho, 4),
                "strength": strength,
                "direction": direction,
                "domain_context": desc,
                "physical_interpretation": (
                    f"{strength} {direction.lower()} monotonic relationship. "
                    + ("Higher values directly align with increases in the paired metric." if rho > 0.4
                       else "Inverse relation: cooling accelerates to suppress rising heat or vice versa." if rho < -0.4
                       else "Weak or decoupled variation under current observed operating envelope.")
                ),
            })

    interp_df = pd.DataFrame(interpretations)
    interp_df.to_csv(output_dir / "correlation_interpretation.csv", index=False)
    print("Saved correlation_interpretation.csv")


# ============================================================
# 6.4 — ROLLING SUMMARIES (MEAN & STD FOR POWER, TEMP, FAN, AMBIENT)
# ============================================================

def calculate_rolling_summaries(
    df,
    output_dir,
    max_gap_seconds=DEFAULT_MAX_GAP_SECONDS,
    window=ROLLING_WINDOW,
    min_periods=ROLLING_MIN_PERIODS,
):
    """
    Computes rolling mean and rolling standard deviation for:
    - Power (total_power, p0_power, p1_power, ps0_input_power, ps1_input_power)
    - Temperature (p0_vdd_temp, p1_vdd_temp)
    - Fan speed (fan0_0, fan1_0)
    - Ambient temperature (ambient)
    Crucially respects segment boundaries (intervals > max_gap_seconds or nonpositive)
    so rolling statistics never bleed across telemetry gaps.
    Exports both tidy long-form and comprehensive wide-form CSVs and plots rolling trends.
    """
    metrics = get_available_metrics(df, ROLLING_METRICS)

    if not metrics:
        print("No supported metrics available for rolling summaries.")
        return

    working = df[["timestamp"] + metrics].copy()

    # Define segment boundaries based on timestamp intervals
    time_diff = working["timestamp"].diff().dt.total_seconds()
    new_segment = time_diff.isna() | time_diff.le(0) | time_diff.gt(max_gap_seconds)
    working["_segment"] = new_segment.cumsum()

    # Build long/tidy records and wide dataframe
    tidy_records = []
    wide_df = pd.DataFrame({"timestamp": working["timestamp"], "_segment": working["_segment"]})

    for metric in metrics:
        wide_df[f"{metric}_raw"] = working[metric]

        # Calculate rolling per segment
        rolling_mean_col = f"{metric}_rolling_mean_{window}"
        rolling_std_col = f"{metric}_rolling_std_{window}"

        means = []
        stds = []

        for _, segment in working.groupby("_segment", sort=False):
            vals = segment[metric]
            m_s = vals.rolling(window=window, min_periods=min_periods).mean()
            s_s = vals.rolling(window=window, min_periods=min_periods).std()
            means.append(m_s)
            stds.append(s_s)

            tidy_records.append(pd.DataFrame({
                "timestamp": segment["timestamp"].to_numpy(),
                "segment_id": segment["_segment"].to_numpy(),
                "metric": metric,
                "value": vals.to_numpy(),
                "rolling_mean": m_s.to_numpy(),
                "rolling_std": s_s.to_numpy(),
            }))

        wide_df[rolling_mean_col] = pd.concat(means)
        wide_df[rolling_std_col] = pd.concat(stds)

    tidy_df = pd.concat(tidy_records, ignore_index=True)
    tidy_df.to_csv(output_dir / "rolling_telemetry_summary.csv", index=False)
    wide_df.to_csv(output_dir / "rolling_telemetry_wide.csv", index=False)

    # Rolling statistics summary
    summary_stats = []
    for metric in metrics:
        r_mean = wide_df[f"{metric}_rolling_mean_{window}"].dropna()
        r_std = wide_df[f"{metric}_rolling_std_{window}"].dropna()
        summary_stats.append({
            "metric": metric,
            "window_size": window,
            "min_periods": min_periods,
            "mean_of_rolling_mean": float(r_mean.mean()) if not r_mean.empty else np.nan,
            "std_of_rolling_mean": float(r_mean.std()) if not r_mean.empty else np.nan,
            "average_rolling_volatility_std": float(r_std.mean()) if not r_std.empty else np.nan,
            "max_rolling_volatility_std": float(r_std.max()) if not r_std.empty else np.nan,
        })
    pd.DataFrame(summary_stats).to_csv(output_dir / "rolling_statistics_summary.csv", index=False)

    # Visualization of rolling trends for representative signals
    plot_rolling_trends(wide_df, output_dir, window=window, max_gap_seconds=max_gap_seconds)

    print("Saved rolling_telemetry_summary.csv, rolling_telemetry_wide.csv, and rolling_statistics_summary.csv")


def plot_rolling_trends(wide_df, output_dir, window=ROLLING_WINDOW, max_gap_seconds=DEFAULT_MAX_GAP_SECONDS):
    """Multi-panel visualization showing raw signal, rolling mean, and rolling std error band."""
    rep_metrics = [
        ("total_power", "Total Power (W)", "#1f77b4"),
        ("p0_vdd_temp", "Processor 0 Temp (°C)", "#d62728"),
        ("fan0_0", "Fan Speed 0 (RPM)", "#2ca02c"),
        ("ambient", "Ambient Temp (°C)", "#ff7f0e"),
    ]
    available_rep = [item for item in rep_metrics if f"{item[0]}_raw" in wide_df.columns]

    if not available_rep:
        return

    time_diff = wide_df["timestamp"].diff().dt.total_seconds()
    gap_mask = (time_diff > max_gap_seconds) | (time_diff <= 0)

    fig, axes = plt.subplots(len(available_rep), 1, figsize=(14, 3.2 * len(available_rep)), sharex=True)
    if len(available_rep) == 1:
        axes = [axes]

    for ax, (metric, label, color) in zip(axes, available_rep):
        raw = wide_df[f"{metric}_raw"].copy()
        rmean = wide_df[f"{metric}_rolling_mean_{window}"].copy()
        rstd = wide_df[f"{metric}_rolling_std_{window}"].copy()

        if gap_mask.any():
            raw.loc[gap_mask] = np.nan
            rmean.loc[gap_mask] = np.nan
            rstd.loc[gap_mask] = np.nan

        ax.plot(wide_df["timestamp"], raw, color=color, alpha=0.3, linewidth=0.8, label="Raw Telemetry")
        ax.plot(wide_df["timestamp"], rmean, color=color, linewidth=1.5, label=f"Rolling Mean (w={window})")

        # Volatility ribbon (+- 1 std)
        upper = rmean + rstd
        lower = rmean - rstd
        ax.fill_between(wide_df["timestamp"], lower, upper, color=color, alpha=0.2, label="±1 Std Band")

        ax.set_ylabel(label, fontsize=10)
        ax.grid(True, linestyle="--", alpha=0.3)
        ax.legend(loc="upper right", framealpha=0.9, fontsize=8)

    axes[-1].set_xlabel("Timestamp (UTC)", fontsize=11)
    fig.suptitle("Telemetry Signals with Windowed Rolling Means and Volatility Bands", fontsize=13, fontweight="bold")
    fig.autofmt_xdate()
    fig.tight_layout()

    fig.savefig(output_dir / "rolling_trends.png", dpi=180)
    plt.close(fig)
    print("Saved rolling_trends.png")


# ============================================================
# 6.5 — ENERGY CONSUMPTION ESTIMATION & UNIT VERIFICATION
# ============================================================

def verify_power_unit(power_series, confirmed_unit="W"):
    """
    Verifies that the power metric and declared units are physically plausible.
    Server node baseline checks:
    - Typical server idle/active load: 100W to 2000W.
    - If mean is ~300-700, unit is Watts (W).
    - If mean is ~0.3-0.7, unit is Kilowatts (kW).
    - If mean is ~300000-700000, unit is Milliwatts (mW).
    """
    valid = power_series.dropna()
    if valid.empty:
        return confirmed_unit, 1.0, "No valid data to verify; using fallback."

    p_mean = float(valid.mean())
    p_max = float(valid.max())

    conversion_factors = {"W": 1.0, "kW": 1000.0, "mW": 0.001}

    if confirmed_unit in ["auto", None]:
        if 50.0 <= p_mean <= 3000.0:
            verified_unit = "W"
            status = f"Plausibility verified: Mean value {p_mean:.1f} aligns with single-node server power in Watts (W)."
        elif 0.05 <= p_mean <= 3.0:
            verified_unit = "kW"
            status = f"Plausibility verified: Mean value {p_mean:.3f} aligns with Kilowatts (kW)."
        elif 50000.0 <= p_mean <= 3000000.0:
            verified_unit = "mW"
            status = f"Plausibility verified: Mean value {p_mean:.0f} aligns with Milliwatts (mW)."
        else:
            verified_unit = "W"
            status = f"Uncertain power scale (mean={p_mean:.1f}); assuming standard Watts (W)."
    else:
        verified_unit = confirmed_unit
        if verified_unit == "W" and (p_mean < 10.0 or p_mean > 5000.0):
            status = f"Warning: Declared unit W, but telemetry mean ({p_mean:.1f}) is unusual for a server node."
        else:
            status = f"Unit confirmed as {verified_unit}. Mean reading: {p_mean:.1f}."

    factor = conversion_factors.get(verified_unit, 1.0)
    return verified_unit, factor, status


def integrate_power_wh(
    df,
    power_column="total_power",
    confirmed_unit="W",
    max_gap_seconds=DEFAULT_MAX_GAP_SECONDS,
):
    """
    Estimate energy consumption (Wh and kWh) using trapezoidal integration.
    CRITICAL INTERVAL CORRECTION:
    Calculates gaps and dt on the continuous chronological telemetry timeline FIRST,
    BEFORE filtering missing power readings.
    An interval (t_{i-1}, t_i) is valid IF AND ONLY IF:
    - dt > 0 and dt <= max_gap_seconds
    - Both P_{i-1} and P_i are valid non-NaN numeric readings.
    """
    if power_column not in df.columns:
        raise ValueError(f"Power column '{power_column}' is missing from dataframe.")

    # 1. Timeline is established on full sorted dataframe
    temp = df[["timestamp", power_column]].copy()
    temp["timestamp"] = pd.to_datetime(temp["timestamp"], utc=True, errors="coerce")
    temp = temp.dropna(subset=["timestamp"]).sort_values("timestamp", kind="mergesort").reset_index(drop=True)

    temp[power_column] = pd.to_numeric(temp[power_column], errors="coerce").replace([np.inf, -np.inf], np.nan)

    # 2. Compute dt and segment breaks on the complete continuous timeline
    dt = temp["timestamp"].diff().dt.total_seconds()
    segment_break = dt.isna() | (dt <= 0) | (dt > max_gap_seconds)
    temp["segment_id"] = segment_break.cumsum()
    temp["interval_seconds"] = dt

    # 3. Unit verification
    verified_unit, unit_factor, unit_notes = verify_power_unit(temp[power_column], confirmed_unit)
    temp["power_watts"] = temp[power_column] * unit_factor

    # 4. Valid interval evaluation: Both endpoints must exist and be within the same valid interval
    prev_power = temp["power_watts"].shift(1)
    prev_segment = temp["segment_id"].shift(1)

    valid_interval = (
        (temp["interval_seconds"] > 0)
        & (temp["interval_seconds"] <= max_gap_seconds)
        & (temp["segment_id"] == prev_segment)
        & temp["power_watts"].notna()
        & prev_power.notna()
    )

    temp["valid_interval"] = valid_interval

    # 5. Trapezoidal integration: (P_{i-1} + P_i) / 2 * dt / 3600 = Wh
    temp["interval_Wh"] = np.where(
        valid_interval,
        ((prev_power + temp["power_watts"]) / 2.0) * (temp["interval_seconds"] / 3600.0),
        0.0,
    )
    temp["cumulative_Wh"] = temp["interval_Wh"].cumsum()

    total_wh = float(temp["interval_Wh"].sum())
    total_kwh = total_wh / 1000.0

    valid_intervals_count = int(valid_interval.sum())
    total_intervals_count = int(dt.notna().sum())
    excluded_intervals_count = total_intervals_count - valid_intervals_count

    valid_seconds = float(temp.loc[valid_interval, "interval_seconds"].sum())
    total_positive_seconds = float(dt[dt > 0].sum()) if (dt > 0).any() else 0.0
    coverage_pct = (100.0 * valid_seconds / total_positive_seconds) if total_positive_seconds > 0 else np.nan

    coverage_start = temp.loc[valid_interval, "timestamp"].iloc[0] if valid_intervals_count > 0 else pd.NaT
    coverage_end = temp.loc[valid_interval, "timestamp"].iloc[-1] if valid_intervals_count > 0 else pd.NaT

    summary = {
        "metric": power_column,
        "verified_power_unit": verified_unit,
        "unit_conversion_factor_to_watts": unit_factor,
        "unit_verification_notes": unit_notes,
        "integrated_total_Wh": round(total_wh, 4),
        "integrated_total_kWh": round(total_kwh, 6),
        "valid_intervals": valid_intervals_count,
        "excluded_intervals": excluded_intervals_count,
        "max_gap_seconds_threshold": max_gap_seconds,
        "covered_duration_seconds": round(valid_seconds, 1),
        "covered_duration_hours": round(valid_seconds / 3600.0, 3),
        "coverage_percentage": round(coverage_pct, 2),
        "coverage_start_utc": str(coverage_start),
        "coverage_end_utc": str(coverage_end),
        "energy_estimate_scope": "Valid gap-free intervals with confirmed dual endpoint readings",
    }

    return temp, summary


def run_energy_analysis(
    df,
    output_dir,
    power_column="total_power",
    confirmed_power_unit="W",
    max_gap_seconds=DEFAULT_MAX_GAP_SECONDS,
):
    """Executes energy integration, saves energy_analysis.csv and energy_integration_summary.csv."""
    try:
        detailed_df, summary = integrate_power_wh(
            df=df,
            power_column=power_column,
            confirmed_unit=confirmed_power_unit,
            max_gap_seconds=max_gap_seconds,
        )
    except Exception as exc:
        print(f"Energy integration error: {exc}")
        return

    # Export detailed row-by-row energy CSV
    export_cols = [
        "timestamp",
        "segment_id",
        "interval_seconds",
        power_column,
        "power_watts",
        "valid_interval",
        "interval_Wh",
        "cumulative_Wh",
    ]
    detailed_df[export_cols].to_csv(output_dir / "energy_analysis.csv", index=False)

    # Export summary CSV
    pd.DataFrame([summary]).to_csv(output_dir / "energy_integration_summary.csv", index=False)

    print("\n" + "=" * 50)
    print("ENERGY INTEGRATION SUMMARY")
    print("=" * 50)
    for k, v in summary.items():
        print(f"  {k}: {v}")
    print("Saved energy_analysis.csv and energy_integration_summary.csv")


def save_pue_requirements(output_dir):
    """Documents reasons why facility PUE cannot be inferred from single-node telemetry."""
    report = pd.DataFrame([{
        "pue_calculated": False,
        "reason": (
            "Single-node telemetry cannot establish total facility energy "
            "nor entire IT equipment energy over matched operational boundaries."
        ),
        "required_facility_energy": "Whole-facility utility power meter over reporting period (kWh)",
        "required_it_energy": "Sum of all IT server and network hardware power meters over same period (kWh)",
        "standard_formula": "PUE = Total Facility Energy / Total IT Equipment Energy",
        "scope_guidance": "Single server power informs asset thermal load, not facility-wide PUE.",
    }])
    report.to_csv(output_dir / "pue_requirements.csv", index=False)
    print("Saved pue_requirements.csv")


# ============================================================
# 6.6 — WHAT-IF POWER ANALYSIS
# ============================================================

def run_what_if_analysis(
    df,
    output_dir,
    power_column="total_power",
    reduction_scenarios=[0.0, 0.05, 0.10, 0.15, 0.20],
):
    """
    Compares baseline power consumption with hypothetical reductions (5%, 10%, 15%, 20%).
    Computes hypothetical power, energy savings over observed window, and projected annual savings.
    Documents assumptions and exports what_if_power_comparison.csv and what_if_power_comparison.png.
    """
    if power_column not in df.columns:
        print(f"What-if analysis skipped: {power_column} not found.")
        return

    power = pd.to_numeric(df[power_column], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()

    if power.empty:
        print("What-if analysis skipped: no valid power readings.")
        return

    baseline_mean = float(power.mean())
    baseline_median = float(power.median())
    baseline_p95 = float(power.quantile(0.95))

    # Calculate observed duration in hours
    dt = df["timestamp"].diff().dt.total_seconds()
    valid_dt = dt[(dt > 0) & (dt <= DEFAULT_MAX_GAP_SECONDS)]
    observed_hours = float(valid_dt.sum() / 3600.0) if not valid_dt.empty else 1.0

    scenarios_data = []

    for reduction in reduction_scenarios:
        hypothetical_mean = baseline_mean * (1.0 - reduction)
        power_diff = baseline_mean - hypothetical_mean

        # Energy consumed over observed duration in kWh
        energy_kwh = (hypothetical_mean * observed_hours) / 1000.0
        energy_saved_kwh = (power_diff * observed_hours) / 1000.0
        # Projected annual savings (8760 hours/year)
        projected_annual_saved_kwh = (power_diff * 8760.0) / 1000.0

        scenarios_data.append({
            "scenario": f"{int(reduction * 100)}%_power_reduction" if reduction > 0 else "baseline_0%",
            "assumed_reduction_fraction": reduction,
            "baseline_mean_power_W": round(baseline_mean, 2),
            "hypothetical_mean_power_W": round(hypothetical_mean, 2),
            "power_reduction_W": round(power_diff, 2),
            "observed_duration_hours": round(observed_hours, 2),
            "estimated_energy_kWh": round(energy_kwh, 4),
            "estimated_energy_saved_kWh": round(energy_saved_kwh, 4),
            "projected_annual_savings_kWh": round(projected_annual_saved_kwh, 2),
            "is_simulated": True,
            "assumption_note": "Mathematical proportional scenario; not a dynamic thermodynamic or CFD cooling simulation.",
        })

    what_if_df = pd.DataFrame(scenarios_data)
    what_if_df.to_csv(output_dir / "what_if_power_comparison.csv", index=False)

    # Visualization
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    # Bar chart 1: Mean power
    colors = ["#2b5c8f", "#3a7ebf", "#5c9edc", "#7ebef9", "#a8d5fa"]
    bars = ax1.bar(
        what_if_df["scenario"],
        what_if_df["hypothetical_mean_power_W"],
        color=colors[:len(what_if_df)],
        edgecolor="#1f3b5c",
        width=0.6,
    )
    for bar in bars:
        h = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width() / 2.0, h + 8, f"{h:.1f} W", ha="center", va="bottom", fontsize=9)

    ax1.set_title("Hypothetical Mean Power by Scenario", fontsize=11, fontweight="bold")
    ax1.set_ylabel("Mean Power (Watts)", fontsize=10)
    ax1.set_xticks(range(len(what_if_df)))
    ax1.set_xticklabels(what_if_df["scenario"], rotation=20, ha="right", fontsize=9)
    ax1.grid(True, linestyle="--", alpha=0.3, axis="y")

    # Bar chart 2: Projected annual energy savings
    bars2 = ax2.bar(
        what_if_df["scenario"],
        what_if_df["projected_annual_savings_kWh"],
        color=["#7f7f7f", "#2ca02c", "#28a745", "#20c997", "#17a2b8"][:len(what_if_df)],
        edgecolor="#222222",
        width=0.6,
    )
    for bar in bars2:
        h = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width() / 2.0, h + 10, f"{h:.0f} kWh", ha="center", va="bottom", fontsize=9)

    ax2.set_title("Projected Annual Energy Savings (8760 h/yr)", fontsize=11, fontweight="bold")
    ax2.set_ylabel("Projected Savings (kWh)", fontsize=10)
    ax2.set_xticks(range(len(what_if_df)))
    ax2.set_xticklabels(what_if_df["scenario"], rotation=20, ha="right", fontsize=9)
    ax2.grid(True, linestyle="--", alpha=0.3, axis="y")

    fig.suptitle("What-if Power Reduction Analysis (Mathematical Scenarios)", fontsize=13, fontweight="bold")
    fig.tight_layout()

    fig.savefig(output_dir / "what_if_power_comparison.png", dpi=180)
    plt.close(fig)

    print("\n" + "=" * 50)
    print("WHAT-IF POWER ANALYSIS")
    print("=" * 50)
    print(what_if_df[["scenario", "hypothetical_mean_power_W", "power_reduction_W", "projected_annual_savings_kWh"]].to_string(index=False))
    print("Saved what_if_power_comparison.csv and what_if_power_comparison.png")


# ============================================================
# 6.7 — FUTURE TEMPERATURE FORECASTING
# ============================================================

def prepare_forecasting_dataset(
    df,
    target_metric="p0_vdd_temp",
    horizon_steps=DEFAULT_FORECAST_HORIZON_STEPS,
    max_gap_seconds=DEFAULT_MAX_GAP_SECONDS,
):
    """
    Constructs feature set and future prediction target.
    Prevents data leakage:
    - Features only use present and historical values: lags [1, 2, 3, 5, 10], rolling stats.
    - Future target is y(t + horizon_steps).
    - Segment boundaries prevent lag features or future target from crossing gaps!
    """
    if target_metric not in df.columns:
        raise ValueError(f"Target metric '{target_metric}' not found in dataframe.")

    feature_cols_base = get_available_metrics(
        df,
        [target_metric, "p1_vdd_temp", "total_power", "p0_power", "fan0_0", "ambient"],
    )

    metadata_cols = [c for c in ["split", "anomaly_label", "fault_type", "label_valid", "segment_id"] if c in df.columns]
    work = df[["timestamp"] + feature_cols_base + metadata_cols].copy()

    # Define continuous segments (prefer segment_id from labeled dataset if present)
    if "segment_id" in df.columns:
        work["_segment"] = pd.to_numeric(df["segment_id"], errors="coerce").fillna(0).astype(int)
    else:
        dt = work["timestamp"].diff().dt.total_seconds()
        segment_break = dt.isna() | (dt <= 0) | (dt > max_gap_seconds)
        work["_segment"] = segment_break.cumsum()

    feature_names = []

    # 1. Target features within each segment: current reading + historical lags
    col_curr = f"{target_metric}_current"
    work[col_curr] = work[target_metric]
    feature_names.append(col_curr)

    for lag in [1, 2, 3, 5, 10]:
        col_name = f"{target_metric}_lag_{lag}"
        work[col_name] = work.groupby("_segment", sort=False)[target_metric].shift(lag)
        feature_names.append(col_name)

    # 2. Key exogenous sensor current & lags
    exogenous = [m for m in feature_cols_base if m != target_metric]
    for ex in exogenous:
        col_name_0 = f"{ex}_current"
        work[col_name_0] = work[ex]
        feature_names.append(col_name_0)

        for lag in [1, 3]:
            col_name_lag = f"{ex}_lag_{lag}"
            work[col_name_lag] = work.groupby("_segment", sort=False)[ex].shift(lag)
            feature_names.append(col_name_lag)

    # 3. Rolling statistics on target metric within segment
    work[f"{target_metric}_rolling_mean"] = work.groupby("_segment", sort=False)[target_metric].transform(
        lambda s: s.rolling(5, min_periods=3).mean()
    )
    work[f"{target_metric}_rolling_std"] = work.groupby("_segment", sort=False)[target_metric].transform(
        lambda s: s.rolling(5, min_periods=3).std()
    )
    feature_names.extend([f"{target_metric}_rolling_mean", f"{target_metric}_rolling_std"])

    # 4. Temperature rate of change (first difference: current vs lag 1)
    work[f"{target_metric}_delta_1"] = work[col_curr] - work[f"{target_metric}_lag_1"]
    feature_names.append(f"{target_metric}_delta_1")

    # 5. Future Target: y(t + horizon_steps) within same segment
    work["future_target"] = work.groupby("_segment", sort=False)[target_metric].shift(-horizon_steps)
    work["future_target_timestamp"] = work.groupby("_segment", sort=False)["timestamp"].shift(-horizon_steps)

    # Clean dataset: drop rows where features or future target are NaN
    valid_data = work.dropna(subset=feature_names + ["future_target"]).reset_index(drop=True)

    return valid_data, feature_names


def train_and_evaluate_temperature_forecast(
    df,
    output_dir,
    target_metric="p0_vdd_temp",
    horizon_minutes=5.0,
    asset_id="M100_NODE_1",
    max_gap_seconds=DEFAULT_MAX_GAP_SECONDS,
    synthetic_input=None,
):
    """
    Trains forecasting models from telemetry, evaluates forecast accuracy
    against a persistence baseline, generates future predictions, and
    saves standardized prediction records and plots.
    """
    if target_metric not in df.columns:
        print(f"Temperature forecasting skipped: {target_metric} not found.")
        return

    # Determine steps for horizon based on median interval
    dt = df["timestamp"].diff().dt.total_seconds()
    median_interval = float(dt[dt > 0].median()) if (dt > 0).any() else 20.0
    horizon_seconds = horizon_minutes * 60.0
    horizon_steps = max(int(round(horizon_seconds / median_interval)), 1)

    print("\n" + "=" * 50)
    print("TRAINING FUTURE TEMPERATURE FORECASTER")
    print("=" * 50)
    print(f"Target metric:     {target_metric}")
    print(f"Sampling cadence:  {median_interval:.1f} s")
    print(f"Forecast horizon:  {horizon_minutes:.1f} min ({horizon_steps} steps ahead)")

    try:
        data, feature_names = prepare_forecasting_dataset(
            df=df,
            target_metric=target_metric,
            horizon_steps=horizon_steps,
            max_gap_seconds=max_gap_seconds,
        )
    except Exception as exc:
        print(f"Forecasting preparation failed: {exc}")
        return

    if len(data) < 50:
        print("Insufficient samples for train/test split. Skipping forecast.")
        return

    # Chronological Train/Test Split (respect official 'split' column if available)
    if "split" in data.columns and (data["split"] == "train").any() and (data["split"] == "test").any():
        train_df = data[data["split"] == "train"]
        test_df = data[data["split"] == "test"].copy()
    else:
        split_idx = int(len(data) * 0.8)
        train_df = data.iloc[:split_idx]
        test_df = data.iloc[split_idx:].copy()

    X_train = train_df[feature_names]
    y_train = train_df["future_target"]
    X_test = test_df[feature_names]
    y_test = test_df["future_target"]

    # Candidate models
    candidate_models = {
        "HistGradientBoostingRegressor": HistGradientBoostingRegressor(
            max_iter=150,
            max_depth=6,
            min_samples_leaf=10,
            learning_rate=0.08,
            random_state=RANDOM_STATE,
        ),
        "RandomForestRegressor": RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            min_samples_leaf=5,
            random_state=RANDOM_STATE,
            n_jobs=-1,
        ),
    }

    # Naive Persistence Baseline: Predict that future temp equals current temp
    persistence_preds = test_df[f"{target_metric}_current"].to_numpy()
    test_df["persistence_baseline"] = persistence_preds

    base_mae = float(mean_absolute_error(y_test, persistence_preds))
    base_rmse = float(np.sqrt(mean_squared_error(y_test, persistence_preds)))
    base_r2 = float(r2_score(y_test, persistence_preds))
    base_mape = float(np.mean(np.abs((y_test - persistence_preds) / y_test)) * 100.0)

    best_pipeline = None
    best_name = None
    best_mae = float("inf")
    eval_records = []

    for name, regressor in candidate_models.items():
        pipeline = Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("regressor", regressor),
        ])
        pipeline.fit(X_train, y_train)
        preds = pipeline.predict(X_test)
        test_df[f"pred_{name}"] = preds

        mae = float(mean_absolute_error(y_test, preds))
        rmse = float(np.sqrt(mean_squared_error(y_test, preds)))
        r2 = float(r2_score(y_test, preds))
        mape = float(np.mean(np.abs((y_test - preds) / y_test)) * 100.0)

        mae_imp = ((base_mae - mae) / base_mae) * 100.0 if base_mae > 0 else 0.0
        rmse_imp = ((base_rmse - rmse) / base_rmse) * 100.0 if base_rmse > 0 else 0.0
        forecast_acc = max(0.0, 100.0 - mape)

        eval_records.append({
            "model": name,
            "target_metric": target_metric,
            "horizon_minutes": horizon_minutes,
            "horizon_steps": horizon_steps,
            "test_samples": len(test_df),
            "mae": round(mae, 4),
            "rmse": round(rmse, 4),
            "r2_score": round(r2, 4),
            "mape_percent": round(mape, 3),
            "forecast_accuracy_pct": round(forecast_acc, 2),
            "mae_improvement_over_baseline_pct": round(mae_imp, 2),
            "rmse_improvement_over_baseline_pct": round(rmse_imp, 2),
        })

        if mae < best_mae:
            best_mae = mae
            best_pipeline = pipeline
            best_name = name

    # Add persistence baseline record
    base_forecast_acc = max(0.0, 100.0 - base_mape)
    eval_records.append({
        "model": "PersistenceBaseline",
        "target_metric": target_metric,
        "horizon_minutes": horizon_minutes,
        "horizon_steps": horizon_steps,
        "test_samples": len(test_df),
        "mae": round(base_mae, 4),
        "rmse": round(base_rmse, 4),
        "r2_score": round(base_r2, 4),
        "mape_percent": round(base_mape, 3),
        "forecast_accuracy_pct": round(base_forecast_acc, 2),
        "mae_improvement_over_baseline_pct": 0.0,
        "rmse_improvement_over_baseline_pct": 0.0,
    })

    eval_df = pd.DataFrame(eval_records)
    eval_df.to_csv(output_dir / "temperature_forecast_evaluation.csv", index=False)

    print("\nFORECAST ACCURACY EVALUATION (ALL MODELS):")
    print(eval_df[["model", "mae", "rmse", "r2_score", "mape_percent", "forecast_accuracy_pct"]].to_string(index=False))

    # Designate the best ML model predictions as the primary prediction series
    test_df["predicted_future_temperature"] = test_df[f"pred_{best_name}"]

    # Save test set predictions
    export_pred_cols = [
        "timestamp",
        "future_target_timestamp",
        "future_target",
        "predicted_future_temperature",
        "persistence_baseline",
    ]
    test_df[export_pred_cols].rename(columns={"future_target": "actual_future_temperature"}).to_csv(
        output_dir / "future_temperature_predictions.csv",
        index=False,
    )

    # Save best trained model artifact
    joblib.dump(best_pipeline, output_dir / "temperature_forecast_model.joblib")

    # Locate evaluation metrics for the best model
    best_eval = next(r for r in eval_records if r["model"] == best_name)

    # Generate standardized prediction record for the most recent valid observation
    latest_row = test_df.iloc[-1]
    standardized_record = predict_future_temperature(
        model=best_pipeline,
        feature_row=test_df[feature_names].iloc[-1:],
        asset_id=asset_id,
        target_metric=target_metric,
        horizon_minutes=horizon_minutes,
        current_temp=float(latest_row[f"{target_metric}_current"]),
        model_version=f"member3-forecast-{best_name}",
        evaluation_metrics={"mae": best_eval["mae"], "rmse": best_eval["rmse"], "r2": best_eval["r2_score"]},
    )

    # Save standardized predictions in JSON and CSV
    with open(output_dir / "standardized_prediction_record.json", "w", encoding="utf-8") as f:
        json.dump(standardized_record, f, indent=2)

    pd.DataFrame([standardized_record]).to_csv(output_dir / "standardized_temperature_predictions.csv", index=False)

    # Plot actual vs predicted future temperature using best model
    plot_forecast_results(test_df, best_eval, output_dir, target_metric, horizon_minutes)

    # Benchmark best forecaster under synthetic fault scenarios
    syn_path = Path(synthetic_input) if synthetic_input else DEFAULT_SYNTHETIC_INPUT
    if syn_path.exists() and best_pipeline is not None:
        try:
            syn_df = pd.read_csv(syn_path)
            if "base_timestamp" in syn_df.columns and "timestamp" not in syn_df.columns:
                step_offsets = pd.to_numeric(syn_df.get("step_in_scenario", 0), errors="coerce").fillna(0)
                syn_df["timestamp"] = pd.to_datetime(syn_df["base_timestamp"], errors="coerce", utc=True) + pd.to_timedelta(step_offsets * 20, unit="s")
            elif "timestamp" in syn_df.columns:
                syn_df["timestamp"] = pd.to_datetime(syn_df["timestamp"], errors="coerce", utc=True)

            for m in POWER_METRICS + TEMPERATURE_METRICS + FAN_METRICS + ENVIRONMENT_METRICS:
                if m in syn_df.columns:
                    syn_df[m] = pd.to_numeric(syn_df[m], errors="coerce")

            syn_df["_segment"] = syn_df["scenario_id"] if "scenario_id" in syn_df.columns else 0

            syn_data, _ = prepare_forecasting_dataset(
                syn_df,
                target_metric=target_metric,
                horizon_steps=horizon_steps,
                max_gap_seconds=max_gap_seconds,
            )
            if "split" in syn_data.columns and (syn_data["split"] == "test").any():
                syn_test_df = syn_data[syn_data["split"] == "test"].copy()
            else:
                syn_test_df = syn_data.copy()

            if len(syn_test_df) >= 20 and all(f in syn_test_df.columns for f in feature_names):
                X_syn_test = syn_test_df[feature_names]
                y_syn_test = syn_test_df["future_target"]
                syn_preds = best_pipeline.predict(X_syn_test)

                syn_mae = float(mean_absolute_error(y_syn_test, syn_preds))
                syn_rmse = float(np.sqrt(mean_squared_error(y_syn_test, syn_preds)))
                syn_r2 = float(r2_score(y_syn_test, syn_preds))
                syn_mape = float(np.mean(np.abs((y_syn_test - syn_preds) / y_syn_test)) * 100.0)
                syn_forecast_acc = max(0.0, 100.0 - syn_mape)

                stress_eval_df = pd.DataFrame([
                    {
                        "condition": "Observed Telemetry (Normal Operation)",
                        "model": best_name,
                        "samples": len(test_df),
                        "mae": best_eval["mae"],
                        "rmse": best_eval["rmse"],
                        "r2_score": best_eval["r2_score"],
                        "mape_percent": best_eval["mape_percent"],
                        "forecast_accuracy_pct": best_eval.get("forecast_accuracy_pct", round(max(0.0, 100.0 - best_eval["mape_percent"]), 2)),
                    },
                    {
                        "condition": "Synthetic Fault Scenarios (Thermal/Fan/Power Faults)",
                        "model": best_name,
                        "samples": len(syn_test_df),
                        "mae": round(syn_mae, 4),
                        "rmse": round(syn_rmse, 4),
                        "r2_score": round(syn_r2, 4),
                        "mape_percent": round(syn_mape, 3),
                        "forecast_accuracy_pct": round(syn_forecast_acc, 2),
                    }
                ])
                stress_eval_df.to_csv(output_dir / "synthetic_fault_temperature_forecast_evaluation.csv", index=False)
                print("\nFORECAST EVALUATION ACROSS FAULT CONDITIONS (OBSERVED vs SYNTHETIC FAULT SCENARIOS):")
                print(stress_eval_df.to_string(index=False))
        except Exception as exc:
            print(f"Notice: Synthetic fault forecasting benchmark skipped: {exc}")

    print("Saved temperature_forecast_evaluation.csv, future_temperature_predictions.csv,")
    print("standardized_prediction_record.json, standardized_temperature_predictions.csv,")
    print("future_temperature_forecast.png, and temperature_forecast_model.joblib")


def predict_future_temperature(
    model,
    feature_row,
    asset_id,
    target_metric,
    horizon_minutes,
    current_temp=None,
    model_version="member3-temperature-forecast-v1",
    data_quality_status="verified_chronological_intervals",
    evaluation_metrics=None,
):
    """
    Generates a standardized prediction record conforming to the project schema.
    """
    pred_val = float(model.predict(feature_row)[0])
    prediction_time = pd.Timestamp.now(tz="UTC")

    delta = (pred_val - current_temp) if current_temp is not None else np.nan

    record = {
        "asset_id": str(asset_id),
        "prediction_type": "future_temperature",
        "target_metric": target_metric,
        "horizon_minutes": float(horizon_minutes),
        "predicted_value": round(pred_val, 3),
        "current_value": round(float(current_temp), 3) if current_temp is not None else np.nan,
        "predicted_delta": round(float(delta), 3) if np.isfinite(delta) else np.nan,
        "prediction_timestamp": prediction_time.isoformat(),
        "model_version": model_version,
        "data_quality_status": data_quality_status,
        "evaluation_mae": round(float(evaluation_metrics["mae"]), 4) if evaluation_metrics else np.nan,
        "evaluation_rmse": round(float(evaluation_metrics["rmse"]), 4) if evaluation_metrics else np.nan,
        "evaluation_r2": round(float(evaluation_metrics["r2"]), 4) if evaluation_metrics else np.nan,
        "is_estimated": True,
        "is_simulated": False,
        "interpretation": "Machine learning forecast from multi-sensor telemetry; not a confirmed hardware failure",
    }
    return record


def plot_forecast_results(test_df, eval_metrics, output_dir, target_metric, horizon_minutes):
    """Visualizes actual test future temperatures against model predictions."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True, gridspec_kw={"height_ratios": [3, 1]})

    time_x = test_df["future_target_timestamp"]
    actual = test_df["future_target"]
    pred = test_df["predicted_future_temperature"]
    residual = actual - pred

    ax1.plot(time_x, actual, label=f"Actual {target_metric} (°C)", color="#222222", linewidth=1.4)
    ax1.plot(time_x, pred, label=f"Model Forecast ({horizon_minutes:.0f}-min Ahead)", color="#d62728", linestyle="--", linewidth=1.4)
    ax1.plot(time_x, test_df["persistence_baseline"], label="Persistence Baseline", color="#888888", linestyle=":", alpha=0.7)

    stats_str = (
        f"Horizon: {horizon_minutes:.1f} min\n"
        f"MAE:  {eval_metrics['mae']:.3f} °C\n"
        f"RMSE: {eval_metrics['rmse']:.3f} °C\n"
        f"R²:   {eval_metrics['r2_score']:.3f}"
    )
    ax1.text(0.02, 0.95, stats_str, transform=ax1.transAxes, verticalalignment="top",
             bbox=dict(boxstyle="round,pad=0.4", facecolor="#ffffff", edgecolor="#cccccc", alpha=0.9), fontsize=10)

    ax1.set_title(f"Future Temperature Forecasting: Actual vs. Predicted ({target_metric})", fontsize=13, fontweight="bold")
    ax1.set_ylabel("Temperature (°C)", fontsize=11)
    ax1.legend(loc="upper right", framealpha=0.9)
    ax1.grid(True, linestyle="--", alpha=0.3)

    # Residuals
    ax2.plot(time_x, residual, color="#555555", linewidth=0.9, label="Residual (Actual - Predicted)")
    ax2.axhline(0, color="#d62728", linestyle="--", linewidth=0.8)
    ax2.set_ylabel("Error (°C)", fontsize=10)
    ax2.set_xlabel("Forecast Target Timestamp (UTC)", fontsize=11)
    ax2.legend(loc="upper right", framealpha=0.9)
    ax2.grid(True, linestyle="--", alpha=0.3)

    fig.autofmt_xdate()
    fig.tight_layout()

    fig.savefig(output_dir / "future_temperature_forecast.png", dpi=180)
    plt.close(fig)


def train_and_evaluate_power_thermal_health_model(
    df,
    output_dir,
    synthetic_input=None,
):
    """
    Supervised Power-Thermal Operational Health & Anomaly Classifier.
    Trains classifiers (HistGradientBoosting, RandomForest) to predict anomaly_label
    and operational degradation from correlated power and thermal multi-sensor telemetry.
    """
    if "anomaly_label" not in df.columns or df["anomaly_label"].notna().sum() < 20:
        print("\nNotice: Supervised operational health model skipped ('anomaly_label' not available in dataframe).")
        return

    print("\n" + "=" * 50)
    print("TRAINING SUPERVISED POWER-THERMAL HEALTH CLASSIFIER")
    print("=" * 50)

    # Base feature set: power metrics, thermal metrics, ambient, delta
    sensor_cols = [c for c in ["total_power", "p0_power", "p1_power", "ps0_input_power", "ps1_input_power",
                               "p0_vdd_temp", "p1_vdd_temp", "ambient", "fan0_0", "fan1_0"] if c in df.columns]

    work = df[sensor_cols].copy()
    if "p0_vdd_temp" in df.columns and "p1_vdd_temp" in df.columns:
        work["processor_temp_diff"] = df["p0_vdd_temp"] - df["p1_vdd_temp"]
    if "total_power" in df.columns and "p0_power" in df.columns and "p1_power" in df.columns:
        work["cpu_power_ratio"] = (df["p0_power"] + df["p1_power"]) / (df["total_power"] + 1e-5)

    # Valid mask for labels
    valid_mask = df["anomaly_label"].notna()
    if "label_valid" in df.columns:
        valid_mask = valid_mask & (df["label_valid"] == 1)

    X_valid = work.loc[valid_mask].replace([np.inf, -np.inf], np.nan)
    y_valid = df.loc[valid_mask, "anomaly_label"].astype(int)

    if "split" in df.columns and (df.loc[valid_mask, "split"] == "train").any() and (df.loc[valid_mask, "split"] == "test").any():
        tr_mask = df.loc[valid_mask, "split"] == "train"
        te_mask = df.loc[valid_mask, "split"] == "test"
    else:
        n_tot = len(X_valid)
        tr_mask = pd.Series(False, index=X_valid.index)
        te_mask = pd.Series(False, index=X_valid.index)
        tr_mask.iloc[:int(n_tot * 0.8)] = True
        te_mask.iloc[int(n_tot * 0.8):] = True

    X_tr, y_tr = X_valid[tr_mask], y_valid[tr_mask]
    X_te, y_te = X_valid[te_mask], y_valid[te_mask]

    models = {
        "HistGradientBoostingClassifier": HistGradientBoostingClassifier(
            max_iter=100, max_depth=5, learning_rate=0.08, class_weight="balanced", random_state=RANDOM_STATE
        ),
        "RandomForestClassifier": RandomForestClassifier(
            n_estimators=100, max_depth=8, min_samples_leaf=3, class_weight="balanced_subsample", random_state=RANDOM_STATE, n_jobs=-1
        ),
    }

    best_clf = None
    best_name = None
    best_f1 = -1.0
    records = []

    for name, clf in models.items():
        pipeline = Pipeline([
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("classifier", clf),
        ])
        pipeline.fit(X_tr, y_tr)
        test_probs = pipeline.predict_proba(X_te)[:, 1]
        test_preds = (test_probs >= 0.5).astype(int)

        acc = accuracy_score(y_te, test_preds)
        prec = precision_score(y_te, test_preds, zero_division=0)
        rec = recall_score(y_te, test_preds, zero_division=0)
        f1 = f1_score(y_te, test_preds, zero_division=0)
        pr_auc = average_precision_score(y_te, test_probs) if y_te.sum() > 0 else 0.0
        try:
            roc_auc = roc_auc_score(y_te, test_probs) if len(np.unique(y_te)) > 1 else np.nan
        except Exception:
            roc_auc = np.nan

        records.append({
            "model": name,
            "test_samples": len(y_te),
            "positives": int(y_te.sum()),
            "accuracy": round(acc, 4),
            "accuracy_pct": round(acc * 100.0, 2),
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1_score": round(f1, 4),
            "pr_auc": round(pr_auc, 4),
            "roc_auc": round(roc_auc, 4) if np.isfinite(roc_auc) else np.nan,
        })

        if f1 > best_f1 or best_clf is None:
            best_f1 = f1
            best_clf = pipeline
            best_name = name

    eval_df = pd.DataFrame(records)
    eval_df.to_csv(output_dir / "power_thermal_health_evaluation.csv", index=False)
    print("\nPOWER-THERMAL HEALTH CLASSIFICATION EVALUATION (TEST PARTITION):")
    print(eval_df.to_string(index=False))

    # Full predictions
    full_probs = best_clf.predict_proba(work.replace([np.inf, -np.inf], np.nan))[:, 1]
    pred_df = pd.DataFrame({
        "timestamp": df["timestamp"],
        "anomaly_label": df["anomaly_label"] if "anomaly_label" in df.columns else (full_probs >= 0.5).astype(int),
        "predicted_anomaly_probability": np.round(full_probs, 4),
        "predicted_operational_status": np.where(full_probs >= 0.5, "degraded_anomalous", "healthy_normal"),
    })
    for m in ["total_power", "p0_vdd_temp", "p1_vdd_temp"]:
        if m in df.columns:
            pred_df[m] = df[m].to_numpy()

    pred_df.to_csv(output_dir / "power_thermal_health_predictions.csv", index=False)
    joblib.dump(best_clf, output_dir / "power_thermal_health_model.joblib")
    print("Saved power_thermal_health_evaluation.csv, power_thermal_health_predictions.csv, and power_thermal_health_model.joblib")


# ============================================================
# ADDITIONAL PRESERVED ANALYTICS
# ============================================================

def analyze_processor_temperature_difference(df, output_dir):
    """Computes and visualizes processor temperature difference (p0_vdd_temp - p1_vdd_temp)."""
    required = {"timestamp", "p0_vdd_temp", "p1_vdd_temp"}
    if not required.issubset(df.columns):
        print(f"Temperature difference skipped: missing columns {required - set(df.columns)}")
        return

    working = df[["timestamp", "p0_vdd_temp", "p1_vdd_temp"]].copy()
    working["processor_temp_difference"] = working["p0_vdd_temp"] - working["p1_vdd_temp"]
    working.to_csv(output_dir / "processor_temperature_difference.csv", index=False)

    fig, ax = plt.subplots(figsize=(13, 4.5))
    ax.plot(working["timestamp"], working["processor_temp_difference"], color="#6f42c1", linewidth=1.1)
    ax.axhline(0, linestyle="--", color="#333333", linewidth=0.8)
    ax.set_title("Processor Temperature Differential (P0 VDD Temp - P1 VDD Temp)", fontsize=12, fontweight="bold")
    ax.set_xlabel("Timestamp (UTC)", fontsize=10)
    ax.set_ylabel("Δ Temperature (°C)", fontsize=10)
    ax.grid(True, linestyle="--", alpha=0.3)
    fig.autofmt_xdate()
    fig.tight_layout()

    fig.savefig(output_dir / "processor_temperature_difference.png", dpi=180)
    plt.close(fig)
    print("Saved processor_temperature_difference.png and processor_temperature_difference.csv")


def analyze_fan_trends(df, output_dir):
    """Visualizes fan speed metrics."""
    available = [m for m in FAN_METRICS if m in df.columns]
    if not available:
        print("Fan analysis skipped: no fan metrics found.")
        return

    for metric in available:
        fig, ax = plt.subplots(figsize=(13, 4))
        ax.plot(df["timestamp"], df[metric], color="#17a2b8", linewidth=1.0)
        ax.set_title(f"Fan Speed Telemetry Trend: {metric}", fontsize=12, fontweight="bold")
        ax.set_xlabel("Timestamp (UTC)", fontsize=10)
        ax.set_ylabel(f"{metric} (RPM)", fontsize=10)
        ax.grid(True, linestyle="--", alpha=0.3)
        fig.autofmt_xdate()
        fig.tight_layout()

        fig.savefig(output_dir / f"{metric}_trend.png", dpi=180)
        plt.close(fig)
        print(f"Saved {metric}_trend.png")


# ============================================================
# MAIN EXECUTION PIPELINE
# ============================================================

def main():
    args = parse_arguments()

    if args.max_gap_seconds <= 0:
        raise ValueError("--max-gap-seconds must be greater than zero.")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Ingestion & Quality check
    df, invalid_timestamps = load_telemetry(args.input)
    save_data_quality_report(df, output_dir, invalid_timestamps)

    print("\n" + "=" * 60)
    print("STARTING MODULE 6: POWER & TEMPERATURE ANALYTICS PIPELINE")
    print("=" * 60)

    # 6.1 — Power trend visualization
    print("\n[6.1] Power trend visualization...")
    plot_power_metrics(df, output_dir, max_gap_seconds=args.max_gap_seconds)

    # 6.2 — Temperature vs. power comparison
    print("\n[6.2] Temperature vs. power comparison...")
    plot_temperature_power(df, output_dir, max_gap_seconds=args.max_gap_seconds)

    # 6.3 — Correlation analysis (Spearman + Pearson + automated interpretation)
    print("\n[6.3] Correlation analysis...")
    calculate_correlations(df, output_dir)

    # 6.4 — Rolling summaries (Power, Temp, Fan, Ambient with gap-safe windows)
    print("\n[6.4] Rolling summaries...")
    calculate_rolling_summaries(
        df,
        output_dir,
        max_gap_seconds=args.max_gap_seconds,
        window=ROLLING_WINDOW,
        min_periods=ROLLING_MIN_PERIODS,
    )

    # 6.5 — Energy consumption estimation with unit verification
    print("\n[6.5] Energy consumption estimation...")
    run_energy_analysis(
        df=df,
        output_dir=output_dir,
        power_column=args.energy_column,
        confirmed_power_unit=args.confirm_power_unit,
        max_gap_seconds=args.max_gap_seconds,
    )
    save_pue_requirements(output_dir)

    # 6.6 — What-if power analysis
    print("\n[6.6] What-if power analysis...")
    run_what_if_analysis(
        df=df,
        output_dir=output_dir,
        power_column=args.energy_column,
    )

    # 6.7 — Future temperature forecasting
    print("\n[6.7] Future temperature forecasting...")
    train_and_evaluate_temperature_forecast(
        df=df,
        output_dir=output_dir,
        target_metric=args.forecast_target,
        horizon_minutes=args.forecast_horizon_minutes,
        asset_id=args.asset_id,
        max_gap_seconds=args.max_gap_seconds,
        synthetic_input=args.synthetic_input,
    )

    # 6.8 — Supervised Power-Thermal Operational Health & Anomaly Classifier
    print("\n[6.8] Supervised Power-Thermal Health Classification...")
    train_and_evaluate_power_thermal_health_model(
        df=df,
        output_dir=output_dir,
        synthetic_input=args.synthetic_input,
    )

    # Additional preserved domain diagnostics
    print("\n[Additional Diagnostics] Processor delta & fan telemetry...")
    analyze_processor_temperature_difference(df, output_dir)
    analyze_fan_trends(df, output_dir)

    # Consolidated Master Model Evaluation Metrics Table
    save_consolidated_evaluation_metrics(output_dir)

    print("\n" + "=" * 60)
    print("MODULE 6 ANALYTICS PIPELINE SUCCESSFULLY COMPLETED")
    print(f"All generated outputs and artifacts are located in: {output_dir.resolve()}")
    print("=" * 60)


def save_consolidated_evaluation_metrics(output_dir):
    """
    Consolidates all power and temperature analytics model evaluation metrics
    into a single structured evaluation table and saves as all_model_evaluation_metrics.csv.
    """
    output_dir = Path(output_dir)
    master_records = []

    # 1. Temperature Forecast Evaluation
    fc_file = output_dir / "temperature_forecast_evaluation.csv"
    if fc_file.exists():
        fc_df = pd.read_csv(fc_file)
        for _, row in fc_df.iterrows():
            master_records.append({
                "module": "power_temperature_analytics",
                "model_name": row.get("model", "Unknown"),
                "task_type": "Regression / Forecasting",
                "target_variable": f"{row.get('target_metric', 'p0_vdd_temp')} ({row.get('horizon_minutes', 5):.0f}min)",
                "condition": "Observed Telemetry (Test Set)",
                "test_samples": row.get("test_samples", np.nan),
                "accuracy_pct": row.get("forecast_accuracy_pct", np.nan),
                "mae": row.get("mae", np.nan),
                "rmse": row.get("rmse", np.nan),
                "r2_score": row.get("r2_score", np.nan),
                "mape_pct": row.get("mape_percent", np.nan),
                "precision": np.nan,
                "recall": np.nan,
                "f1_score": np.nan,
                "pr_auc": np.nan,
                "roc_auc": np.nan,
            })

    # 2. Synthetic Fault Forecast Benchmark
    syn_fc_file = output_dir / "synthetic_fault_temperature_forecast_evaluation.csv"
    if syn_fc_file.exists():
        syn_df = pd.read_csv(syn_fc_file)
        for _, row in syn_df.iterrows():
            if "Synthetic Fault Scenarios" in str(row.get("condition", "")):
                master_records.append({
                    "module": "power_temperature_analytics",
                    "model_name": f"{row.get('model', 'Unknown')}_StressTest",
                    "task_type": "Regression / Forecasting Under Stress",
                    "target_variable": "p0_vdd_temp (5min)",
                    "condition": "Synthetic Fault Scenarios (Stress Test)",
                    "test_samples": row.get("samples", np.nan),
                    "accuracy_pct": row.get("forecast_accuracy_pct", np.nan),
                    "mae": row.get("mae", np.nan),
                    "rmse": row.get("rmse", np.nan),
                    "r2_score": row.get("r2_score", np.nan),
                    "mape_pct": row.get("mape_percent", np.nan),
                    "precision": np.nan,
                    "recall": np.nan,
                    "f1_score": np.nan,
                    "pr_auc": np.nan,
                    "roc_auc": np.nan,
                })

    # 3. Supervised Power-Thermal Health Classification
    health_file = output_dir / "power_thermal_health_evaluation.csv"
    if health_file.exists():
        h_df = pd.read_csv(health_file)
        for _, row in h_df.iterrows():
            master_records.append({
                "module": "power_temperature_analytics",
                "model_name": row.get("model", "Unknown"),
                "task_type": "Binary Operational Health Classification",
                "target_variable": "anomaly_label",
                "condition": "Observed Telemetry (Test Set)",
                "test_samples": row.get("test_samples", np.nan),
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
        print("\n" + "=" * 60)
        print(f"CONSOLIDATED POWER & TEMPERATURE EVALUATION TABLE:")
        print(f"Saved: {all_metrics_path}")
        print("=" * 60)
        print(all_metrics_df[["model_name", "task_type", "target_variable", "accuracy_pct", "f1_score", "mae", "r2_score"]].to_string(index=False))


if __name__ == "__main__":
    main()
