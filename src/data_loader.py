"""Load telemetry, validate timestamps and compute a consistent gap report."""
from pathlib import Path
import numpy as np
import pandas as pd

METRICS = ["ambient", "p0_vdd_temp", "p1_vdd_temp", "fan0_0", "fan1_0",
           "p0_power", "p1_power", "ps0_input_power", "ps1_input_power", "total_power"]


def load_data(data_dir: str | Path):
    data_dir = Path(data_dir)
    telemetry_path = data_dir / "m100_node1_digital_twin.csv"
    quality_path = data_dir / "telemetry_quality_records.csv"
    source_gap_path = data_dir / "timestamp_gap_report.csv"
    if not telemetry_path.exists():
        raise FileNotFoundError(f"Missing telemetry CSV: {telemetry_path}")
    df = pd.read_csv(telemetry_path)
    missing = [c for c in ["timestamp", *METRICS] if c not in df.columns]
    if missing: raise ValueError(f"Telemetry CSV is missing required columns: {missing}")
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    invalid_timestamps = int(df["timestamp"].isna().sum())
    df = df.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
    duplicate_timestamps = int(df["timestamp"].duplicated().sum())
    if duplicate_timestamps:
        df = df.drop_duplicates(subset=["timestamp"], keep="last").reset_index(drop=True)
    for metric in METRICS: df[metric] = pd.to_numeric(df[metric], errors="coerce")
    df[METRICS] = df[METRICS].replace([np.inf, -np.inf], np.nan)

    previous = df["timestamp"].shift(1)
    intervals = df["timestamp"].diff().dt.total_seconds()
    positive = intervals[intervals > 0]
    typical = float(positive.median()) if not positive.empty else np.nan
    threshold = max(3.0 * typical, 60.0) if np.isfinite(typical) else np.nan
    df["calculated_gap_seconds"] = intervals
    df["calculated_gap_flag"] = intervals.gt(threshold).fillna(False) if np.isfinite(threshold) else False
    # A newly computed report is used by Member 2. Member 1's report is counted
    # separately, not silently mixed with this threshold's definition.
    gap_report = pd.DataFrame({
        "previous_timestamp": previous,
        "timestamp": df["timestamp"],
        "gap_seconds": intervals,
        "typical_interval_seconds": typical,
        "gap_threshold_seconds": threshold,
        "is_major_gap": df["calculated_gap_flag"].astype(bool),
        "report_source": "recomputed_from_sorted_telemetry",
    })
    gap_report = gap_report[gap_report["gap_seconds"].notna()].reset_index(drop=True)

    quality = None
    if quality_path.exists():
        quality = pd.read_csv(quality_path)
        if "event_timestamp" in quality: quality = quality.rename(columns={"event_timestamp": "timestamp"})
        if {"timestamp", "metric_name"}.issubset(quality.columns):
            quality["timestamp"] = pd.to_datetime(quality["timestamp"], utc=True, errors="coerce")
            quality = quality[quality["metric_name"].isin(METRICS)].copy()
        else:
            print("WARNING: quality metadata schema not recognized; continuing without quality join.")
            quality = None
    source_gap_rows = 0
    if source_gap_path.exists():
        try: source_gap_rows = int(len(pd.read_csv(source_gap_path)))
        except (OSError, pd.errors.ParserError): source_gap_rows = 0
    summary = {
        "rows_loaded": int(len(df)),
        "invalid_timestamps_dropped": invalid_timestamps,
        "duplicate_timestamps_removed": duplicate_timestamps,
        "typical_interval_seconds": typical,
        "calculated_gap_threshold_seconds": threshold,
        "calculated_major_gap_count": int(df["calculated_gap_flag"].sum()),
        "missing_sensor_values": int(df[METRICS].isna().sum().sum()),
        "quality_records_loaded": int(len(quality)) if quality is not None else 0,
        "member1_gap_report_rows_loaded": source_gap_rows,
        "recomputed_gap_report_rows": int(len(gap_report)),
        "gap_report_definition": "interval > max(3 * median positive interval, 60 seconds)",
    }
    return df, quality, gap_report, summary