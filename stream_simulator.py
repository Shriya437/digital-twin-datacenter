# -*- coding: utf-8 -*-
"""Real-time telemetry streaming simulator and online state-estimation consumer."""

import time
import datetime
import joblib
import pandas as pd
import numpy as np
from pathlib import Path

from config import (
    DATA_PATH,
    MODEL_PATH,
    OUTPUT_DIR,
    TARGETS,
    METRICS,
    STALE_THRESHOLD_SECONDS,
    STREAMING_LOG_PATH,
    STREAM_PLAYBACK_SPEED,
    MAX_STREAM_EVENTS
)
from delay_staleness import detect_stale_reading
from state_estimation import estimate_temperature, apply_estimation_gate

class TelemetryStreamEngine:
    def __init__(self, data_path, model_path):
        self.data_path = Path(data_path)
        self.model_path = Path(model_path)
        self.models_loaded = False
        self.bundle = None

        if self.model_path.exists():
            self.bundle = joblib.load(self.model_path)
            self.models_loaded = True
            print(f"[Streaming Engine] Loaded state estimation models from {self.model_path}")
        else:
            print("[Streaming Engine] Model bundle not found. Run state_estimation.py first.")

    def run_stream(self, max_events=MAX_STREAM_EVENTS, playback_multiplier=STREAM_PLAYBACK_SPEED):
        """Simulates an active telemetry ingestion stream."""
        if not self.data_path.exists():
            raise FileNotFoundError(f"Source telemetry dataset missing: {self.data_path}")

        print(f"\n[Streaming Engine] Starting real-time stream (Max events: {max_events})...")
        df = pd.read_csv(self.data_path)
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        sample_stream = df.head(max_events).copy()

        stream_records = []
        simulated_clock = datetime.datetime.now(datetime.timezone.utc)

        for idx, row in sample_stream.iterrows():
            event_ts = row["timestamp"]

            # Simulate network transport lag (0 - 5 seconds jitter)
            jitter_seconds = np.random.uniform(0.1, 5.0)
            arrival_clock = simulated_clock + datetime.timedelta(seconds=jitter_seconds)

            # Online staleness check
            staleness_check = detect_stale_reading(
                event_timestamp=event_ts,
                evaluation_time=arrival_clock,
                stale_threshold_seconds=STALE_THRESHOLD_SECONDS
            )

            record = {
                "stream_id": idx + 1,
                "asset_id": "M100_NODE_1",
                "event_timestamp": str(event_ts),
                "ingest_timestamp": str(arrival_clock),
                "transport_delay_seconds": round(jitter_seconds, 3),
                "is_stale": staleness_check["stale"],
                "staleness_status": staleness_check["status"]
            }

            # Online State Estimation if target metric is missing or for inference
            single_frame = pd.DataFrame([row])
            if self.models_loaded:
                for target in TARGETS:
                    est = estimate_temperature(
                        target=target,
                        input_frame=single_frame,
                        models_by_target=self.bundle["models_by_target"],
                        uncertainty_margins=self.bundle["uncertainty_margins"],
                        model_name="Random Forest"
                    )
                    gated = apply_estimation_gate(est, max_missing_features=2)
                    
                    record[f"{target}_actual"] = row.get(target, np.nan)
                    record[f"{target}_estimate"] = round(float(gated["estimated_value"].iloc[0]), 3)
                    record[f"{target}_uncertainty"] = round(float(gated["uncertainty_margin"].iloc[0]), 3)
                    record[f"{target}_status"] = gated["estimate_status"].iloc[0]

            stream_records.append(record)
            
            # Print heart-beat every 20 readings
            if (idx + 1) % 20 == 0:
                print(f" -> Processed {idx + 1} live telemetry events | Last Delay: {jitter_seconds:.2f}s")

            # Advance clock
            simulated_clock += datetime.timedelta(seconds=1.0)
            time.sleep(1.0 / playback_multiplier)

        stream_df = pd.DataFrame(stream_records)
        stream_df.to_csv(STREAMING_LOG_PATH, index=False)
        print(f"[Streaming Engine] Stream closed. Persisted stream log to {STREAMING_LOG_PATH}")
        return stream_df

if __name__ == "__main__":
    engine = TelemetryStreamEngine(DATA_PATH, MODEL_PATH)
    engine.run_stream()