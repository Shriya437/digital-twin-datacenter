# -*- coding: utf-8 -*-
"""Master pipeline orchestrator and contract validation suite."""

import os
import numpy as np
import pandas as pd
from config import (
    OUTPUT_DIR,
    EXPECTED_FILES,
    METRICS,
    DELAY_PATH
)
from prepare_dataset import run_preparation_pipeline
from telemetry_reliability import compute_telemetry_reliability
from plausibility_validation import evaluate_plausibility
from delay_staleness import run_delay_staleness_analysis
from state_estimation import run_state_estimation_pipeline
from drive_copy import copy_artifacts_to_shared_drive

def validate_contract_outputs():
    validation_results = []

    for filename, required_columns in EXPECTED_FILES.items():
        path = OUTPUT_DIR / filename
        result = {
            "file_name": filename,
            "exists": os.path.exists(path),
            "readable": False,
            "row_count": np.nan,
            "missing_columns": "",
            "status": "FAIL"
        }

        if os.path.exists(path):
            try:
                report = pd.read_csv(path)
                result["readable"] = True
                result["row_count"] = len(report)
                missing = [
                    col for col in required_columns
                    if col not in report.columns
                ]
                result["missing_columns"] = ", ".join(missing)

                if not missing and len(report) > 0:
                    result["status"] = "PASS"
                elif missing:
                    result["status"] = "FAIL_MISSING_COLUMNS"
                else:
                    result["status"] = "FAIL_EMPTY_FILE"
            except Exception as exc:
                result["status"] = f"FAIL_READ_ERROR: {exc}"

        validation_results.append(result)

    validation_report = pd.DataFrame(validation_results)
    print(validation_report.to_string())
    validation_report.to_csv(OUTPUT_DIR / "output_file_validation_report.csv", index=False)

    print("\nPassed:", int((validation_report["status"] == "PASS").sum()))
    print("Total files:", len(validation_report))
    print("\nAll files passed:", bool((validation_report["status"] == "PASS").all()))

    checks = {}
    for filename in [
        "metric_quality_summary.csv",
        "metric_reliability_report.csv",
        "plausibility_report.csv",
        "stale_telemetry_report.csv"
    ]:
        path = OUTPUT_DIR / filename
        if os.path.exists(path):
            report = pd.read_csv(path)
            metric_col = (
                "metric_name" if "metric_name" in report.columns
                else "metric" if "metric" in report.columns
                else None
            )
            checks[f"{filename}: 10 metrics"] = (
                metric_col is not None
                and report[metric_col].nunique() == len(METRICS)
            )

    if os.path.exists(DELAY_PATH):
        delay_check = pd.read_csv(DELAY_PATH)
        checks["Delay records are marked simulated"] = (
            "is_simulated" in delay_check.columns
            and delay_check["is_simulated"].eq(True).all()
        )
        checks["Delay values are within 0–180 seconds"] = (
            "simulated_delay_seconds" in delay_check.columns
            and delay_check["simulated_delay_seconds"].notna().all()
            and delay_check["simulated_delay_seconds"].between(0, 180).all()
        )

        if {
            "event_timestamp",
            "received_timestamp",
            "simulated_delay_seconds"
        }.issubset(delay_check.columns):
            event_ts = pd.to_datetime(delay_check["event_timestamp"], errors="coerce", utc=True)
            received_ts = pd.to_datetime(delay_check["received_timestamp"], errors="coerce", utc=True)
            actual_simulated_age = (received_ts - event_ts).dt.total_seconds()
            checks["Received timestamps match simulated delays"] = (
                actual_simulated_age.notna().all()
                and np.allclose(
                    actual_simulated_age,
                    delay_check["simulated_delay_seconds"],
                    atol=0.001
                )
            )

    for name, passed in checks.items():
        print(f"{'PASS' if passed else 'FAIL'}: {name}")
    print("\nAll consistency checks passed:", all(checks.values()))

    print("\nMODULE 2 OUTPUT DIRECTORY")
    print("=" * 50)
    for filename in sorted(os.listdir(OUTPUT_DIR)):
        path = OUTPUT_DIR / filename
        if os.path.isfile(path):
            print(f"{filename:<45} {os.path.getsize(path) / 1024:.2f} KB")

def main():
    print("=== Step 1: Data Acquisition & Preprocessing ===")
    run_preparation_pipeline()

    print("\n=== Step 2: Telemetry Reliability & Gaps ===")
    compute_telemetry_reliability()

    print("\n=== Step 3: Plausibility Validation ===")
    evaluate_plausibility()

    print("\n=== Step 4: Delay & Staleness Analysis ===")
    run_delay_staleness_analysis()

    print("\n=== Step 5: State Estimation (ML Models) ===")
    run_state_estimation_pipeline()

    print("\n=== Step 6: Artifact Validation & Integrity Checks ===")
    validate_contract_outputs()

    print("\n=== Step 7: Local / Shared Copy ===")
    copy_artifacts_to_shared_drive()

if __name__ == "__main__":
    main()