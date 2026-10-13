# -*- coding: utf-8 -*-
"""Simulated delayed telemetry generator and staleness analysis."""

import os
import numpy as np
import pandas as pd
from config import (
    DATA_PATH,
    OUTPUT_DIR,
    DELAY_PATH,
    METRICS,
    RANDOM_STATE,
    LATE_THRESHOLD_SECONDS,
    STALE_THRESHOLD_SECONDS
)

def detect_stale_reading(event_timestamp, evaluation_time, stale_threshold_seconds=120):
    event_timestamp = pd.to_datetime(event_timestamp, errors="coerce", utc=True)
    evaluation_time = pd.to_datetime(evaluation_time, errors="coerce", utc=True)

    if pd.isna(event_timestamp) or pd.isna(evaluation_time):
        return {
            "age_seconds": np.nan,
            "stale": None,
            "status": "invalid_timestamp"
        }

    age_seconds = (evaluation_time - event_timestamp).total_seconds()
    if age_seconds < 0:
        return {
            "age_seconds": age_seconds,
            "stale": None,
            "status": "future_event_timestamp"
        }

    return {
        "age_seconds": age_seconds,
        "stale": age_seconds > stale_threshold_seconds,
        "status": "stale" if age_seconds > stale_threshold_seconds else "fresh"
    }

def run_delay_staleness_analysis():
    print("Late threshold:", LATE_THRESHOLD_SECONDS, "seconds")
    print("Stale threshold:", STALE_THRESHOLD_SECONDS, "seconds")

    if os.path.exists(DELAY_PATH):
        delay_df = pd.read_csv(DELAY_PATH)
        print("Loaded existing simulated-delay file.")
    else:
        df = pd.read_csv(DATA_PATH)
        delay_df = df[["timestamp"] + METRICS].melt(
            id_vars=["timestamp"],
            var_name="metric_name",
            value_name="value"
        ).rename(columns={"timestamp": "event_timestamp"})

        delay_df["source_record_id"] = [
            f"simulated_record_{i}" for i in range(len(delay_df))
        ]
        delay_df["asset_id"] = "M100_NODE_1"

        rng = np.random.default_rng(RANDOM_STATE)
        delay_df["simulated_delay_seconds"] = rng.integers(
            low=0, high=181, size=len(delay_df)
        )

        delay_df["event_timestamp"] = pd.to_datetime(
            delay_df["event_timestamp"], errors="coerce", utc=True
        )
        delay_df["received_timestamp"] = (
            delay_df["event_timestamp"]
            + pd.to_timedelta(delay_df["simulated_delay_seconds"], unit="s")
        )

        delay_df["is_simulated"] = True
        delay_df["delay_source"] = "synthetic_experiment"
        delay_df["original_arrival_time_available"] = False
        delay_df.to_csv(DELAY_PATH, index=False)

    delay_df["event_timestamp"] = pd.to_datetime(
        delay_df["event_timestamp"], errors="coerce", utc=True
    )
    delay_df["simulated_delay_seconds"] = pd.to_numeric(
        delay_df["simulated_delay_seconds"], errors="coerce"
    )
    delay_df["received_timestamp"] = (
        delay_df["event_timestamp"]
        + pd.to_timedelta(delay_df["simulated_delay_seconds"], unit="s")
    )

    delay_df["telemetry_age_at_receipt_seconds"] = (
        delay_df["received_timestamp"] - delay_df["event_timestamp"]
    ).dt.total_seconds()

    delay_df["simulated_late_flag"] = (
        delay_df["telemetry_age_at_receipt_seconds"] > LATE_THRESHOLD_SECONDS
    )
    delay_df["simulated_stale_flag"] = (
        delay_df["telemetry_age_at_receipt_seconds"] > STALE_THRESHOLD_SECONDS
    )

    delay_df["stale_status"] = np.select(
        [
            delay_df["event_timestamp"].isna(),
            delay_df["simulated_delay_seconds"].isna(),
            delay_df["simulated_stale_flag"],
            delay_df["simulated_late_flag"]
        ],
        [
            "invalid_event_timestamp",
            "invalid_simulated_delay",
            "stale_simulated",
            "late_simulated"
        ],
        default="fresh_under_experimental_thresholds"
    )

    delay_df["is_simulated"] = True
    delay_df["delay_source"] = "synthetic_experiment"
    delay_df["original_arrival_time_available"] = False
    delay_df.to_csv(DELAY_PATH, index=False)

    print("Late readings:", int(delay_df["simulated_late_flag"].sum()))
    print("Stale readings:", int(delay_df["simulated_stale_flag"].sum()))
    print("Invalid event timestamps:", int(delay_df["event_timestamp"].isna().sum()))

    stale_summary = (
        delay_df.groupby("metric_name", dropna=False)
        .agg(
            total_records=("value", "size"),
            late_records=("simulated_late_flag", "sum"),
            stale_records=("simulated_stale_flag", "sum"),
            mean_delay_seconds=("simulated_delay_seconds", "mean"),
            max_delay_seconds=("simulated_delay_seconds", "max")
        )
        .reset_index()
    )

    stale_summary["late_pct"] = (
        100 * stale_summary["late_records"]
        / stale_summary["total_records"].replace(0, np.nan)
    )
    stale_summary["stale_pct"] = (
        100 * stale_summary["stale_records"]
        / stale_summary["total_records"].replace(0, np.nan)
    )

    stale_summary.to_csv(OUTPUT_DIR / "stale_telemetry_report.csv", index=False)
    print(stale_summary.to_string())
    print("Saved stale_telemetry_report.csv")

    # Verification function sample run
    sample = delay_df.dropna(
        subset=["event_timestamp", "received_timestamp"]
    ).iloc[0]
    print("\nSample Staleness Detection:")
    print(detect_stale_reading(
        sample["event_timestamp"],
        sample["received_timestamp"],
        stale_threshold_seconds=STALE_THRESHOLD_SECONDS
    ))

if __name__ == "__main__":
    run_delay_staleness_analysis()