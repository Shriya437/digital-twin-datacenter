# -*- coding: utf-8 -*-
"""Physical plausibility limits evaluation and reporting."""

import os
import numpy as np
import pandas as pd
from config import DATA_PATH, OUTPUT_DIR, METRICS, PLAUSIBILITY_LIMITS

def evaluate_plausibility():
    if not os.path.exists(DATA_PATH):
        raise FileNotFoundError(f"Prepared dataset not found: {DATA_PATH}")

    df = pd.read_csv(DATA_PATH)
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)

    missing_columns = [m for m in METRICS if m not in df.columns]
    if missing_columns:
        raise ValueError(f"Missing metric columns: {missing_columns}")

    for metric in METRICS:
        df[metric] = pd.to_numeric(df[metric], errors="coerce")
        df.loc[~np.isfinite(df[metric]), metric] = np.nan

    print("Dataset loaded:", df.shape)
    print("Invalid timestamps:", df["timestamp"].isna().sum())
    print("Output directory:", OUTPUT_DIR)
    print("Configured verified rules:", len(PLAUSIBILITY_LIMITS))

    if not PLAUSIBILITY_LIMITS:
        print("No physical limits enabled. Physical plausibility will be reported as not checked.")

    plausibility_rows = []
    for metric in METRICS:
        values = df[metric]
        missing = values.isna()
        non_finite = values.notna() & ~np.isfinite(values)
        checked = metric in PLAUSIBILITY_LIMITS

        if checked:
            rule = PLAUSIBILITY_LIMITS[metric]
            below_min = values.notna() & (values < rule["min"])
            above_max = values.notna() & (values > rule["max"])
            implausible = below_min | above_max
        else:
            below_min = pd.Series(False, index=df.index)
            above_max = pd.Series(False, index=df.index)
            implausible = pd.Series(False, index=df.index)

        plausibility_rows.append({
            "metric_name": metric,
            "total_records": len(df),
            "missing_count": int(missing.sum()),
            "non_finite_count": int(non_finite.sum()),
            "plausibility_checked": checked,
            "verified_min": (
                PLAUSIBILITY_LIMITS[metric]["min"]
                if checked else np.nan
            ),
            "verified_max": (
                PLAUSIBILITY_LIMITS[metric]["max"]
                if checked else np.nan
            ),
            "below_min_count": int(below_min.sum()),
            "above_max_count": int(above_max.sum()),
            "implausible_count": int(implausible.sum()),
            "plausibility_status": (
                "checked" if checked else "not_checked_limits_unverified"
            )
        })

    plausibility_report = pd.DataFrame(plausibility_rows)
    plausibility_report.to_csv(OUTPUT_DIR / "plausibility_report.csv", index=False)
    print(plausibility_report.to_string())
    print("Saved plausibility_report.csv")

if __name__ == "__main__":
    evaluate_plausibility()