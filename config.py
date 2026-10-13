# -*- coding: utf-8 -*-
"""Centralized configurations, paths, and constants."""

import os
from pathlib import Path

# Base Paths (VS Code project root)
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
SELECTED_METRICS_DIR = DATA_DIR / "m100_selected"
OUTPUT_DIR = BASE_DIR / "member1_outputs"
SHARED_DRIVE_DIR = BASE_DIR / "shared_drive" / "DataCenterDigitalTwin_Shared"

# Primary File Paths
TAR_URL = "https://zenodo.org/records/7588815/files/20-04.tar?download=1"
TAR_PATH = DATA_DIR / "20-04.tar"
DATA_PATH = DATA_DIR / "m100_node1_digital_twin.csv"
DELAY_PATH = OUTPUT_DIR / "simulated_delayed_telemetry.csv"
MODEL_PATH = OUTPUT_DIR / "state_estimation_models.joblib"

# Ensure runtime directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
SELECTED_METRICS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
SHARED_DRIVE_DIR.mkdir(parents=True, exist_ok=True)

# Domain Metrics
SELECTED_METRICS = [
    "ambient",
    "p0_vdd_temp",
    "p1_vdd_temp",
    "fan0_0",
    "fan1_0",
    "p0_power",
    "p1_power",
    "total_power",
    "ps0_input_power",
    "ps1_input_power"
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
    "total_power"
]

TARGETS = ["p0_vdd_temp", "p1_vdd_temp"]

# Plausibility Rules (kept empty until hardware units are verified)
PLAUSIBILITY_LIMITS = {}

# Constants & Thresholds
RANDOM_STATE = 42
NODE_ID = "1"
LATE_THRESHOLD_SECONDS = 60
STALE_THRESHOLD_SECONDS = 120

# Expected Output Contract
EXPECTED_FILES = {
    "metric_quality_summary.csv": [
        "metric_name",
        "total_rows",
        "missing_count",
        "infinite_count"
    ],
    "metric_reliability_report.csv": [
        "metric_name",
        "record_count",
        "completeness_pct",
        "data_quality_score_pct"
    ],
    "telemetry_quality_records.csv": [
        "source_record_id",
        "asset_id",
        "event_timestamp",
        "metric_name",
        "value",
        "quality_status"
    ],
    "timestamp_gap_report.csv": [
        "timestamp",
        "gap_seconds",
        "timestamp_gap_flag",
        "duplicate_timestamp_flag"
    ],
    "simulated_delayed_telemetry.csv": [
        "event_timestamp",
        "metric_name",
        "simulated_delay_seconds",
        "received_timestamp",
        "is_simulated"
    ],
    "plausibility_report.csv": [
        "metric_name",
        "plausibility_checked",
        "implausible_count",
        "plausibility_status"
    ],
    "stale_telemetry_report.csv": [
        "metric_name",
        "total_records",
        "late_records",
        "stale_records"
    ]
}

# Streaming & Real-time Integration Config
STREAMING_LOG_PATH = OUTPUT_DIR / "realtime_telemetry_stream_log.csv"
STREAM_PLAYBACK_SPEED = 50.0  # Speed multiplier for replaying timestamps (e.g., 50x faster than real-time)
MAX_STREAM_EVENTS = 100       # Number of events to process in a demo run