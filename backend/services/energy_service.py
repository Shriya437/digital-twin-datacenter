"""Energy analytics, PUE diagnostics, and What-If power optimization simulation."""
from typing import Any, Dict, List, Optional
import pandas as pd

from backend.services.data_service import (
    get_energy_summary,
    get_energy_series,
    get_what_if_comparison,
    get_pue_info,
)

def get_energy_overview() -> Dict[str, Any]:
    """Returns total integrated energy and verification metadata."""
    summary = get_energy_summary()
    pue = get_pue_info()
    return {
        "summary": summary,
        "pue_metrics": pue
    }

def run_what_if_simulation(reduction_pct: float) -> Dict[str, Any]:
    """Calculates power reduction, energy savings, CO2 abatement, and estimated thermal relief."""
    baseline_power = 638.45  # Mean Watts for Marconi100 Node 1
    duration_hours = 24.0

    reduction_frac = max(0.0, min(0.50, reduction_pct / 100.0))
    hypothetical_power = baseline_power * (1.0 - reduction_frac)
    saved_power_watts = baseline_power - hypothetical_power
    daily_energy_saved_kwh = (saved_power_watts * duration_hours) / 1000.0
    monthly_energy_saved_kwh = daily_energy_saved_kwh * 30.0

    # Grid carbon factor (avg 0.38 kg CO2e per kWh)
    carbon_reduction_kg = round(daily_energy_saved_kwh * 0.385, 2)
    # Estimated CPU thermal relief: ~0.035 °C drop per Watt reduced
    estimated_temp_drop = round(saved_power_watts * 0.035, 2)

    return {
        "assumed_reduction_pct": reduction_pct,
        "assumed_reduction_fraction": round(reduction_frac, 3),
        "baseline_mean_power_w": round(baseline_power, 2),
        "hypothetical_mean_power_w": round(hypothetical_power, 2),
        "power_saved_w": round(saved_power_watts, 2),
        "daily_energy_saved_kwh": round(daily_energy_saved_kwh, 2),
        "monthly_energy_saved_kwh": round(monthly_energy_saved_kwh, 2),
        "estimated_temp_relief_c": estimated_temp_drop,
        "carbon_reduction_kg_daily": carbon_reduction_kg,
        "is_simulated": True,
        "methodology": "Mathematical power cap scenario based on empirical trapezoidal energy baseline",
        "thermodynamic_note": "Assumes linear fan power response and steady-state ambient boundary conditions."
    }
