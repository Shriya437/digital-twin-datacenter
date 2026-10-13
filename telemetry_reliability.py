# -*- coding: utf-8 -*-
"""Telemetry quality records, sampling interval gaps, and reliability reports."""

import os
import numpy as np
import pandas as pd
from config import (
    DATA_PATH,
    OUTPUT_DIR,
    METRICS,
    PLAUSIBILITY_LIMITS
)

def compute_telemetry_reliability():
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(f"Prepared dataset not found: {DATA_PATH}")

    df = pd.read_csv(DATA_PATH)
    if "timestamp" not in df.columns:
        raise ValueError("The CSV must contain a timestamp column.")

    missing_columns = [m for m in METRICS if m not in df.columns]
    if missing_columns:
        raise ValueError(f"Missing metric columns: {missing_columns}")

    df["timestamp_raw"] = df["timestamp"]
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)

    for metric in METRICS:
        df[metric] = pd.to_numeric(df[metric], errors="coerce")

    print("Rows:", len(df))
    print("Columns:", df.columns.tolist())
    print("Invalid timestamps:", int(df["timestamp"].isna().sum()))
    print("Output folder:", OUTPUT_DIR)
    print(df.head().to_string())

    # Retain duplicate rows while sorting
    df = df.sort_values("timestamp", na_position="last").reset_index(drop=True)
    df["duplicate_timestamp_flag"] = (
        df["timestamp"].notna()
        & df["timestamp"].duplicated(keep=False)
    )
    df["gap_seconds"] = df["timestamp"].diff().dt.total_seconds()

    positive_intervals = df.loc[df["gap_seconds"] > 0, "gap_seconds"]
    if positive_intervals.empty:
        raise ValueError("Cannot calculate sampling interval.")

    typical_interval = positive_intervals.median()
    GAP_THRESHOLD_SECONDS = 1.5 * typical_interval

    df["timestamp_gap_flag"] = df["gap_seconds"] > GAP_THRESHOLD_SECONDS

    gap_report = df.loc[
        df["timestamp_gap_flag"] | df["duplicate_timestamp_flag"],
        [
            "timestamp",
            "gap_seconds",
            "timestamp_gap_flag",
            "duplicate_timestamp_flag"
        ]
    ].copy()
    gap_report["gap_minutes"] = gap_report["gap_seconds"] / 60
    gap_report.to_csv(OUTPUT_DIR / "timestamp_gap_report.csv", index=False)

    print("Typical interval (seconds):", typical_interval)
    print("Gap threshold (seconds):", GAP_THRESHOLD_SECONDS)
    print("Duplicate timestamp rows:", int(df["duplicate_timestamp_flag"].sum()))
    print("Timestamp gaps:", int(df["timestamp_gap_flag"].sum()))
    print(gap_report.head(20).to_string())

    # Summary rows
    summary_rows = []
    for metric in METRICS:
        series = df[metric]
        infinite_mask = series.notna() & ~np.isfinite(series)
        finite_mask = series.notna() & np.isfinite(series)
        missing_mask = series.isna()
        finite_values = series[finite_mask]

        summary_rows.append({
            "metric_name": metric,
            "total_rows": len(df),
            "missing_count": int(missing_mask.sum()),
            "missing_pct": round(100 * missing_mask.mean(), 3),
            "infinite_count": int(infinite_mask.sum()),
            "finite_count": int(finite_mask.sum()),
            "finite_pct": round(100 * finite_mask.mean(), 3),
            "unique_finite_values": int(finite_values.nunique()),
            "minimum": finite_values.min() if len(finite_values) else np.nan,
            "median": finite_values.median() if len(finite_values) else np.nan,
            "maximum": finite_values.max() if len(finite_values) else np.nan,
            "duplicate_timestamp_rows": int(df["duplicate_timestamp_flag"].sum()),
            "timestamp_gap_rows": int(df["timestamp_gap_flag"].sum())
        })

    metric_quality_summary = pd.DataFrame(summary_rows)
    metric_quality_summary.to_csv(OUTPUT_DIR / "metric_quality_summary.csv", index=False)
    print(metric_quality_summary.to_string())
    print("Saved metric_quality_summary.csv")

    # Quality records per metric reading
    records = []
    for row_idx, row in df.iterrows():
        ts = row["timestamp"]
        for metric in METRICS:
            value = row[metric]
            missing_flag = bool(pd.isna(value))
            infinite_flag = bool(not missing_flag and not np.isfinite(value))
            duplicate_flag = bool(row["duplicate_timestamp_flag"])
            gap_flag = bool(row["timestamp_gap_flag"])
            invalid_timestamp_flag = bool(pd.isna(ts))

            plausibility_checked = metric in PLAUSIBILITY_LIMITS
            implausible_flag = False

            if plausibility_checked and not missing_flag and not infinite_flag:
                limits = PLAUSIBILITY_LIMITS[metric]
                implausible_flag = bool(value < limits["min"] or value > limits["max"])

            issues = []
            if invalid_timestamp_flag:
                issues.append("invalid_timestamp")
            if missing_flag:
                issues.append("missing_value")
            if infinite_flag:
                issues.append("non_finite_value")
            if duplicate_flag:
                issues.append("duplicate_timestamp")
            if gap_flag:
                issues.append("timestamp_gap")
            if implausible_flag:
                issues.append("implausible_value")

            status = "valid" if not issues else "|".join(issues)

            records.append({
                "source_record_id": f"m100_node1_row{row_idx}_{metric}",
                "asset_id": "M100_NODE_1",
                "event_timestamp": ts,
                "metric_name": metric,
                "value": value,
                "quality_status": status,
                "missing_value_flag": missing_flag,
                "non_finite_flag": infinite_flag,
                "duplicate_timestamp_flag": duplicate_flag,
                "timestamp_gap_flag": gap_flag,
                "invalid_timestamp_flag": invalid_timestamp_flag,
                "plausibility_checked": plausibility_checked,
                "implausible_value_flag": implausible_flag,
                "is_estimated": False,
                "is_simulated": False,
                "source": "M100 historical dataset"
            })

    telemetry_quality_records = pd.DataFrame(records)
    telemetry_quality_records.to_csv(OUTPUT_DIR / "telemetry_quality_records.csv", index=False)
    print("Quality records:", len(telemetry_quality_records))
    print("Saved telemetry_quality_records.csv")

    # Reliability scoring
    reliability_rows = []
    for metric in METRICS:
        r = telemetry_quality_records[
            telemetry_quality_records["metric_name"] == metric
        ].copy()
        n = len(r)
        if n == 0:
            continue

        completeness = 1 - r["missing_value_flag"].mean()
        finite_ratio = 1 - r["non_finite_flag"].mean()
        timestamp_coverage = 1 - r["timestamp_gap_flag"].mean()

        if r["plausibility_checked"].all() and n > 0:
            plausibility_score = 1 - r["implausible_value_flag"].mean()
            plausibility_status = "checked"
        else:
            plausibility_score = np.nan
            plausibility_status = "not_checked_units_unverified"

        components = {
            "completeness": (0.40, completeness),
            "finite_ratio": (0.30, finite_ratio),
            "timestamp_coverage": (0.30, timestamp_coverage)
        }

        weighted_sum = sum(w * score for w, score in components.values())
        weight_total = sum(w for w, score in components.values())
        quality_score = 100 * weighted_sum / weight_total

        if quality_score >= 98:
            status = "high_data_quality"
        elif quality_score >= 90:
            status = "moderate_data_quality"
        else:
            status = "low_data_quality"

        reliability_rows.append({
            "metric_name": metric,
            "record_count": n,
            "completeness_pct": round(100 * completeness, 3),
            "finite_value_pct": round(100 * finite_ratio, 3),
            "timestamp_coverage_pct": round(100 * timestamp_coverage, 3),
            "missing_count": int(r["missing_value_flag"].sum()),
            "non_finite_count": int(r["non_finite_flag"].sum()),
            "duplicate_timestamp_count": int(r["duplicate_timestamp_flag"].sum()),
            "timestamp_gap_count": int(r["timestamp_gap_flag"].sum()),
            "plausibility_status": plausibility_status,
            "plausibility_score_pct": (
                round(100 * plausibility_score, 3)
                if pd.notna(plausibility_score) else np.nan
            ),
            "data_quality_score_pct": round(quality_score, 3),
            "data_quality_status": status,
            "score_is_heuristic": True,
            "actual_arrival_delay_available": False
        })

    metric_reliability_report = pd.DataFrame(reliability_rows)
    metric_reliability_report.to_csv(OUTPUT_DIR / "metric_reliability_report.csv", index=False)
    print(metric_reliability_report.to_string())
    print("Saved metric_reliability_report.csv")

if __name__ == "__main__":
    compute_telemetry_reliability()