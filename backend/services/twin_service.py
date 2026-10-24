"""Digital Twin Service: Rack topology, server components, cooling zones, state estimation, and sensor staleness/plausibility."""
import datetime
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from backend.config import LATE_THRESHOLD_SECONDS, STALE_THRESHOLD_SECONDS
from backend.services.data_service import (
    get_telemetry_df,
    get_metric_reliability,
    get_standardized_predictions,
)

# Plausibility bounds based on hardware specs (IBM Power9 / Marconi100 node)
SENSOR_BOUNDS = {
    "ambient": {"min": 10.0, "max": 45.0, "unit": "°C", "nominal": 22.0},
    "p0_vdd_temp": {"min": 20.0, "max": 90.0, "unit": "°C", "nominal": 48.0},
    "p1_vdd_temp": {"min": 20.0, "max": 90.0, "unit": "°C", "nominal": 49.0},
    "fan0_0": {"min": 1500.0, "max": 12000.0, "unit": "RPM", "nominal": 4500.0},
    "fan1_0": {"min": 1500.0, "max": 12000.0, "unit": "RPM", "nominal": 4500.0},
    "p0_power": {"min": 20.0, "max": 350.0, "unit": "W", "nominal": 130.0},
    "p1_power": {"min": 20.0, "max": 350.0, "unit": "W", "nominal": 135.0},
    "ps0_input_power": {"min": 50.0, "max": 1200.0, "unit": "W", "nominal": 320.0},
    "ps1_input_power": {"min": 50.0, "max": 1200.0, "unit": "W", "nominal": 315.0},
    "total_power": {"min": 100.0, "max": 2400.0, "unit": "W", "nominal": 635.0},
}

def get_current_twin_state(row_index: Optional[int] = None) -> Dict[str, Any]:
    """Generates the full digital twin rack, chassis, server, and cooling state."""
    df = get_telemetry_df()
    if df.empty:
        return {"error": "No telemetry data loaded"}

    # Pick row by index or take recent row
    total_rows = len(df)
    idx = row_index if (row_index is not None and 0 <= row_index < total_rows) else (total_rows - 1)
    row = df.iloc[idx].to_dict()

    ts = row.get("timestamp")
    timestamp_str = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)

    # Historical telemetry has no actual ingestion/arrival timestamp, so live delay
    # and staleness cannot be truthfully inferred from this dataset.
    p0_measured = pd.to_numeric(pd.Series([row.get("p0_vdd_temp")]), errors="coerce").iloc[0]
    ambient = pd.to_numeric(pd.Series([row.get("ambient")]), errors="coerce").iloc[0]
    p1_measured = pd.to_numeric(pd.Series([row.get("p1_vdd_temp")]), errors="coerce").iloc[0]
    prediction_rows = get_standardized_predictions()
    def latest_model_prediction(metric: str):
        matches = [x for x in prediction_rows if x.get("target_metric") == metric and x.get("predicted_value") is not None]
        if not matches:
            return None
        matches.sort(key=lambda x: str(x.get("target_timestamp", "")))
        return float(matches[-1]["predicted_value"])
    p0_estimated = latest_model_prediction("p0_vdd_temp")
    p1_estimated = latest_model_prediction("p1_vdd_temp")
    p0_residual = round(abs(float(p0_measured) - p0_estimated), 2) if p0_estimated is not None and pd.notna(p0_measured) else None
    p1_residual = round(abs(float(p1_measured) - p1_estimated), 2) if p1_estimated is not None and pd.notna(p1_measured) else None
    # No validated prediction interval is currently produced by the ML module.
    p0_uncertainty = None
    p1_uncertainty = None

    # Reliability scores lookup
    reliability_list = get_metric_reliability()
    reliability_map = {r.get("metric_name"): r for r in reliability_list}

    def evaluate_sensor(metric_name: str, value: float) -> Dict[str, Any]:
        bounds = SENSOR_BOUNDS.get(metric_name, {"min": 0, "max": 1000, "unit": "", "nominal": value})
        is_plausible = bounds["min"] <= value <= bounds["max"] if value is not None else False
        rel_info = reliability_map.get(metric_name, {})
        rel_raw = rel_info.get("completeness_pct")
        rel_score = float(rel_raw) if rel_raw is not None and pd.notna(rel_raw) else None

        # Sensor health status
        health = "HEALTHY"
        if not is_plausible:
            health = "IMPLAUSIBLE"
        elif rel_score is not None and rel_score < 95.0:
            health = "UNRELIABLE"
        elif value is not None and abs(value - bounds["nominal"]) > (bounds["max"] - bounds["min"]) * 0.4:
            health = "WARNING"

        return {
            "metric": metric_name,
            "value": round(value, 2) if value is not None else None,
            "unit": bounds["unit"],
            "plausible": is_plausible,
            "min_limit": bounds["min"],
            "max_limit": bounds["max"],
            "reliability_pct": rel_score,
            "health_status": health,
            "staleness_status": "UNKNOWN",
            "delay_seconds": None
        }

    sensors = {m: evaluate_sensor(m, float(row[m]) if m in row and pd.notna(row[m]) else None) for m in SENSOR_BOUNDS.keys()}

    rack_structure = {
        "datacenter": "CINECA Marconi100 Supercomputing Tier-0",
        "hall": "Compute Hall B",
        "row": "Row 04",
        "rack_id": "RACK-A01",
        "rack_height_u": 42,
        "active_slot_u": "U19-U20",
        "status": "OPERATIONAL",
        "cooling_zones": {
            "cold_aisle": {
                "name": "Front Inflow (Cold Aisle)",
                "target_temp_c": None,
                "measured_temp_c": sensors["ambient"]["value"],
                "status": "UNKNOWN" if sensors["ambient"]["value"] is None else ("NOMINAL" if sensors["ambient"]["value"] < 28.0 else "ELEVATED")
            },
            "hot_aisle": {
                "name": "Rear Exhaust (Hot Aisle)",
                "measured_temp_c": None,
                "target_temp_c": None,
                "status": "UNMEASURED"
            }
        },
        "node": {
            "asset_id": "M100_NODE_1",
            "model": "IBM Power System AC922 (8335-GTH)",
            "form_factor": "2U Rackmount",
            "chassis_status": "UNKNOWN",
            "timestamp": timestamp_str,
            "telemetry_tick_index": idx,
            "total_telemetry_ticks": total_rows,
            "processors": [
                {
                    "id": "CPU_0",
                    "name": "Processor 0 (POWER9 16-Core)",
                    "measured_temp": p0_measured,
                    "estimated_temp": p0_estimated,
                    "residual": p0_residual,
                    "uncertainty_margin": p0_uncertainty,
                    "within_bounds": p0_residual is not None and p0_uncertainty is not None and p0_residual <= p0_uncertainty * 2.0,
                    "power_draw": sensors["p0_power"]["value"],
                    "health": sensors["p0_vdd_temp"]["health_status"],
                    "staleness": sensors["p0_vdd_temp"]["staleness_status"]
                },
                {
                    "id": "CPU_1",
                    "name": "Processor 1 (POWER9 16-Core)",
                    "measured_temp": p1_measured,
                    "estimated_temp": p1_estimated,
                    "residual": p1_residual,
                    "uncertainty_margin": p1_uncertainty,
                    "within_bounds": p1_residual is not None and p1_uncertainty is not None and p1_residual <= p1_uncertainty * 2.0,
                    "power_draw": sensors["p1_power"]["value"],
                    "health": sensors["p1_vdd_temp"]["health_status"],
                    "staleness": sensors["p1_vdd_temp"]["staleness_status"]
                }
            ],
            "cooling_fans": [
                {
                    "id": "FAN_0",
                    "name": "Chassis Intake Fan Zone 0",
                    "speed_rpm": sensors["fan0_0"]["value"],
                    "health": sensors["fan0_0"]["health_status"],
                    "duty_cycle_pct": None
                },
                {
                    "id": "FAN_1",
                    "name": "Chassis Exhaust Fan Zone 1",
                    "speed_rpm": sensors["fan1_0"]["value"],
                    "health": sensors["fan1_0"]["health_status"],
                    "duty_cycle_pct": None
                }
            ],
            "power_supplies": [
                {
                    "id": "PSU_0",
                    "name": "Primary 2200W Platinum PSU (PS0)",
                    "input_power_w": sensors["ps0_input_power"]["value"],
                    "status": "DATA_AVAILABLE" if sensors["ps0_input_power"]["value"] is not None else "UNKNOWN"
                },
                {
                    "id": "PSU_1",
                    "name": "Redundant 2200W Platinum PSU (PS1)",
                    "input_power_w": sensors["ps1_input_power"]["value"],
                    "status": "DATA_AVAILABLE" if sensors["ps1_input_power"]["value"] is not None else "UNKNOWN"
                }
            ],
            "total_power_w": sensors["total_power"]["value"],
            "ambient_temp_c": sensors["ambient"]["value"],
            "sensors_summary": sensors
        }
    }
    return rack_structure

def get_state_estimation_comparison(limit: int = 200) -> List[Dict[str, Any]]:
    """Join observed telemetry to actual model forecast records where timestamps match."""
    df = get_telemetry_df()
    if df.empty:
        return []
    predictions = get_standardized_predictions()
    if not predictions:
        return []
    pred_df = pd.DataFrame(predictions)
    if "target_timestamp" not in pred_df or "predicted_value" not in pred_df:
        return []
    pred_df["target_timestamp"] = pd.to_datetime(pred_df["target_timestamp"], utc=True, errors="coerce")
    pred_df["predicted_value"] = pd.to_numeric(pred_df["predicted_value"], errors="coerce")
    sample = df.tail(limit).copy()
    sample["timestamp"] = pd.to_datetime(sample["timestamp"], utc=True, errors="coerce")
    comparison = []
    for _, row in sample.iterrows():
        ts = row.get("timestamp")
        if pd.isna(ts):
            continue
        item = {"timestamp": ts.isoformat(), "ambient": row.get("ambient"), "total_power": row.get("total_power")}
        for metric, prefix in (("p0_vdd_temp", "p0"), ("p1_vdd_temp", "p1")):
            actual = pd.to_numeric(pd.Series([row.get(metric)]), errors="coerce").iloc[0]
            matches = pred_df[pred_df.get("target_metric", pd.Series(index=pred_df.index, dtype=object)) == metric]
            matches = matches[matches["target_timestamp"] == ts]
            predicted = float(matches.iloc[-1]["predicted_value"]) if not matches.empty and pd.notna(matches.iloc[-1]["predicted_value"]) else None
            actual_value = float(actual) if pd.notna(actual) else None
            item[f"{prefix}_measured"] = actual_value
            item[f"{prefix}_estimated"] = predicted
            item[f"{prefix}_lower"] = None
            item[f"{prefix}_upper"] = None
            item[f"{prefix}_residual"] = round(actual_value - predicted, 4) if actual_value is not None and predicted is not None else None
        comparison.append(item)
    return comparison
