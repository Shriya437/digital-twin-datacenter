"""Create separate, reproducible synthetic faults for controlled evaluation.

Synthetic scenarios are evaluation data only. The source CSV is never modified.
"""
from dataclasses import dataclass
import numpy as np
import pandas as pd
from .data_loader import METRICS

@dataclass
class Scenario:
    scenario_id: str
    scenario_type: str
    expected_cause: str
    frame: pd.DataFrame
    labels: pd.DataFrame


def generate_scenarios(base_df: pd.DataFrame, start_fraction: float = 0.25,
                       duration: int = 20, seed: int = 42) -> list[Scenario]:
    if not 0.10 <= start_fraction <= 0.90:
        raise ValueError("start_fraction must be between 0.10 and 0.90")
    base = base_df.copy().reset_index(drop=True)
    if len(base) < 100:
        raise ValueError("At least 100 rows are required to generate scenarios")
    rng = np.random.default_rng(seed)
    start = min(max(int(len(base) * start_fraction), 10), len(base) - duration - 2)
    duration = min(duration, max(3, len(base) - start - 1))
    specs = [
        ("temperature_spike", "temperature_sensor_or_thermal_behaviour", "p0_vdd_temp", "spike"),
        ("fan_degradation_with_heating", "fan_related_issue", "fan0_0", "fan_heat"),
        ("power_spike", "power_telemetry_or_load_behaviour", "total_power", "spike"),
        ("temperature_sensor_bias", "temperature_sensor_or_thermal_behaviour", "p1_vdd_temp", "bias"),
        ("gradual_temperature_drift", "temperature_sensor_or_thermal_behaviour", "p0_vdd_temp", "drift"),
    ]
    scenarios = []
    for scenario_id, cause, metric, kind in specs:
        scenario = base.copy()
        scenario[METRICS] = scenario[METRICS].apply(pd.to_numeric, errors="coerce").astype(float)
        scenario["is_simulated"] = False
        indices = list(range(start, min(start + duration, len(scenario))))
        def robust_scale(column):
            values = pd.to_numeric(base[column], errors="coerce").dropna()
            if values.empty:
                return 1.0
            mad = float((values - values.median()).abs().median()) * 1.4826
            if not np.isfinite(mad) or mad <= 1e-9:
                q1, q3 = values.quantile([0.25, 0.75])
                mad = float((q3 - q1) / 1.349)
            if not np.isfinite(mad) or mad <= 1e-9:
                mad = float(values.std(ddof=0))
            return max(mad if np.isfinite(mad) else 1.0, 1.0)

        if kind == "spike":
            magnitude = max(20.0, 10.0 * robust_scale(metric))
            scenario.loc[indices, metric] = scenario.loc[indices, metric].astype(float) + magnitude
        elif kind == "fan_heat":
            # Severe but controlled fan degradation plus associated heating.
            scenario.loc[indices, "fan0_0"] = scenario.loc[indices, "fan0_0"].astype(float) * 0.20
            scenario.loc[indices, "p0_vdd_temp"] = scenario.loc[indices, "p0_vdd_temp"].astype(float) + max(20.0, 8.0 * robust_scale("p0_vdd_temp"))
        elif kind == "bias":
            scenario.loc[indices, metric] = scenario.loc[indices, metric].astype(float) + max(20.0, 10.0 * robust_scale(metric))
        elif kind == "drift":
            ramp = np.linspace(0.5, max(20.0, 8.0 * robust_scale(metric)), len(indices))
            scenario.loc[indices, metric] = scenario.loc[indices, metric].to_numpy(dtype=float) + ramp
        scenario.loc[indices, "is_simulated"] = True
        labels = pd.DataFrame({
            "timestamp": scenario.loc[indices, "timestamp"].to_numpy(),
            "scenario_id": scenario_id,
            "scenario_type": scenario_id,
            "expected_cause": cause,
            "injected_fault": True,
            "affected_metric": metric,
            "is_simulated": True,
        })
        if kind == "fan_heat":
            # The synthetic scenario changes both fan and temperature; labels retain both metrics.
            labels = pd.concat([labels, pd.DataFrame({
                "timestamp": scenario.loc[indices, "timestamp"].to_numpy(),
                "scenario_id": scenario_id, "scenario_type": scenario_id,
                "expected_cause": cause, "injected_fault": True,
                "affected_metric": "p0_vdd_temp", "is_simulated": True,
            })], ignore_index=True)
        # A scenario ID is recorded on every row; only injected rows have injected_fault=True.
        scenario["scenario_id"] = scenario_id
        scenario["scenario_type"] = "normal"
        scenario.loc[indices, "scenario_type"] = scenario_id
        scenario["injected_fault"] = False
        scenario.loc[indices, "injected_fault"] = True
        scenario["expected_cause"] = ""
        scenario.loc[indices, "expected_cause"] = cause
        scenarios.append(Scenario(scenario_id, scenario_id, cause, scenario, labels))
    return scenarios
