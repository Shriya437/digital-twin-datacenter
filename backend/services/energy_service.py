"""Dataset-derived energy analytics and explicitly hypothetical what-if calculations."""
from typing import Any, Dict
import pandas as pd
from backend.config import TELEMETRY_CSV
from backend.services.data_service import get_energy_summary, get_energy_series, get_what_if_comparison, get_pue_info


def get_energy_overview() -> Dict[str, Any]:
    return {"summary": get_energy_summary(), "pue_metrics": get_pue_info()}


def run_what_if_simulation(reduction_pct: float) -> Dict[str, Any]:
    """Scenario calculator. Baseline comes from actual dataset; outputs remain hypothetical."""
    if not TELEMETRY_CSV.exists():
        return {"available": False, "reason": "Telemetry dataset is missing."}
    df = pd.read_csv(TELEMETRY_CSV)
    if "total_power" not in df.columns:
        return {"available": False, "reason": "Dataset has no total_power column."}
    power = pd.to_numeric(df["total_power"], errors="coerce").dropna()
    if power.empty:
        return {"available": False, "reason": "No valid total_power readings are available."}
    reduction_frac = max(0.0, min(0.50, reduction_pct / 100.0))
    baseline = float(power.mean())
    hypothetical = baseline * (1.0 - reduction_frac)
    saved = baseline - hypothetical
    # Duration and carbon intensity are user/environment assumptions, not model outputs.
    # Carbon is omitted to avoid presenting an unverified external factor as observed data.
    return {
        "available": True,
        "assumed_reduction_pct": reduction_pct,
        "assumed_reduction_fraction": reduction_frac,
        "baseline_mean_power_w": round(baseline, 4),
        "hypothetical_mean_power_w": round(hypothetical, 4),
        "power_saved_w": round(saved, 4),
        "daily_energy_saved_kwh": round(saved * 24.0 / 1000.0, 4),
        "monthly_energy_saved_kwh": round(saved * 24.0 * 30.0 / 1000.0, 4),
        "estimated_temp_relief_c": None,
        "carbon_reduction_kg_daily": None,
        "is_simulated": True,
        "methodology": "Hypothetical percentage reduction applied to mean total_power observed in the telemetry dataset; not an ML prediction.",
        "dataset_rows_used": int(len(power)),
        "dataset_power_mean_w": round(baseline, 4),
        "carbon_note": "Not calculated: no verified grid-carbon factor was supplied.",
        "thermal_note": "Not calculated: no validated power-to-temperature response model was supplied."
    }
