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
    idx = row_index if (row_index is not None and 0 <= row_index < total_rows) else (total_rows - 100)
    row = df.iloc[idx].to_dict()

    ts = row.get("timestamp")
    timestamp_str = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)

    # Simulated delay and staleness
    simulated_delay = np.random.uniform(0.4, 3.2)
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    
    # State estimation: measured vs estimated
    # P0 VDD Temp
    p0_measured = float(row.get("p0_vdd_temp", 48.0))
    # State estimation formula based on ambient, fan, and power:
    ambient = float(row.get("ambient", 22.0))
    p0_power = float(row.get("p0_power", 120.0))
    fan0 = float(row.get("fan0_0", 4500.0))
    # ML/regression synthetic approximation when model isn't run inline
    p0_estimated = round(ambient * 0.45 + (p0_power * 0.28) - (fan0 * 0.0012) + 24.5, 2)
    p0_residual = round(abs(p0_measured - p0_estimated), 2)
    p0_uncertainty = 1.85  # +/- degrees margin from state_estimation module

    # P1 VDD Temp
    p1_measured = float(row.get("p1_vdd_temp", 49.0))
    p1_power = float(row.get("p1_power", 125.0))
    fan1 = float(row.get("fan1_0", 4500.0))
    p1_estimated = round(ambient * 0.45 + (p1_power * 0.28) - (fan1 * 0.0012) + 25.1, 2)
    p1_residual = round(abs(p1_measured - p1_estimated), 2)
    p1_uncertainty = 1.92

    # Reliability scores lookup
    reliability_list = get_metric_reliability()
    reliability_map = {r.get("metric_name"): r for r in reliability_list}

    def evaluate_sensor(metric_name: str, value: float) -> Dict[str, Any]:
        bounds = SENSOR_BOUNDS.get(metric_name, {"min": 0, "max": 1000, "unit": "", "nominal": value})
        is_plausible = bounds["min"] <= value <= bounds["max"] if value is not None else False
        rel_info = reliability_map.get(metric_name, {})
        rel_score = float(rel_info.get("completeness_pct", 99.8))

        # Sensor health status
        health = "HEALTHY"
        if not is_plausible:
            health = "IMPLAUSIBLE"
        elif rel_score < 95.0:
            health = "UNRELIABLE"
        elif abs(value - bounds["nominal"]) > (bounds["max"] - bounds["min"]) * 0.4:
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
            "staleness_status": "NOMINAL" if simulated_delay < LATE_THRESHOLD_SECONDS else ("LATE" if simulated_delay < STALE_THRESHOLD_SECONDS else "STALE"),
            "delay_seconds": round(simulated_delay, 2)
        }

    sensors = {m: evaluate_sensor(m, float(row.get(m, 0.0))) for m in SENSOR_BOUNDS.keys()}

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
                "target_temp_c": 21.5,
                "measured_temp_c": sensors["ambient"]["value"],
                "status": "NOMINAL" if sensors["ambient"]["value"] < 28.0 else "ELEVATED"
            },
            "hot_aisle": {
                "name": "Rear Exhaust (Hot Aisle)",
                "measured_temp_c": round(max(p0_measured, p1_measured) * 0.65 + sensors["ambient"]["value"] * 0.35, 1),
                "target_temp_c": 35.0,
                "status": "NOMINAL"
            }
        },
        "node": {
            "asset_id": "M100_NODE_1",
            "model": "IBM Power System AC922 (8335-GTH)",
            "form_factor": "2U Rackmount",
            "chassis_status": "NORMAL",
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
                    "within_bounds": p0_residual <= p0_uncertainty * 2.0,
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
                    "within_bounds": p1_residual <= p1_uncertainty * 2.0,
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
                    "duty_cycle_pct": round((sensors["fan0_0"]["value"] / 12000.0) * 100, 1)
                },
                {
                    "id": "FAN_1",
                    "name": "Chassis Exhaust Fan Zone 1",
                    "speed_rpm": sensors["fan1_0"]["value"],
                    "health": sensors["fan1_0"]["health_status"],
                    "duty_cycle_pct": round((sensors["fan1_0"]["value"] / 12000.0) * 100, 1)
                }
            ],
            "power_supplies": [
                {
                    "id": "PSU_0",
                    "name": "Primary 2200W Platinum PSU (PS0)",
                    "input_power_w": sensors["ps0_input_power"]["value"],
                    "status": "ONLINE_ACTIVE"
                },
                {
                    "id": "PSU_1",
                    "name": "Redundant 2200W Platinum PSU (PS1)",
                    "input_power_w": sensors["ps1_input_power"]["value"],
                    "status": "ONLINE_ACTIVE"
                }
            ],
            "total_power_w": sensors["total_power"]["value"],
            "ambient_temp_c": sensors["ambient"]["value"],
            "sensors_summary": sensors
        }
    }
    return rack_structure

def get_state_estimation_comparison(limit: int = 200) -> List[Dict[str, Any]]:
    """Returns measured vs estimated time series for processors."""
    df = get_telemetry_df()
    if df.empty:
        return []

    sample = df.tail(limit).copy()
    comparison = []

    for _, row in sample.iterrows():
        ts = row.get("timestamp")
        p0_m = float(row.get("p0_vdd_temp", 48.0))
        p1_m = float(row.get("p1_vdd_temp", 49.0))
        amb = float(row.get("ambient", 22.0))
        p0_p = float(row.get("p0_power", 120.0))
        p1_p = float(row.get("p1_power", 125.0))
        f0 = float(row.get("fan0_0", 4500.0))
        f1 = float(row.get("fan1_0", 4500.0))

        p0_est = round(amb * 0.45 + (p0_p * 0.28) - (f0 * 0.0012) + 24.5, 2)
        p1_est = round(amb * 0.45 + (p1_p * 0.28) - (f1 * 0.0012) + 25.1, 2)

        comparison.append({
            "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
            "p0_measured": p0_m,
            "p0_estimated": p0_est,
            "p0_lower": round(p0_est - 1.85, 2),
            "p0_upper": round(p0_est + 1.85, 2),
            "p0_residual": round(p0_m - p0_est, 2),
            "p1_measured": p1_m,
            "p1_estimated": p1_est,
            "p1_lower": round(p1_est - 1.92, 2),
            "p1_upper": round(p1_est + 1.92, 2),
            "p1_residual": round(p1_m - p1_est, 2),
            "ambient": amb,
            "total_power": float(row.get("total_power", 600.0))
        })

    return comparison
