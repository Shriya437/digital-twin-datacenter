"""Data loader service for CSV/JSON outputs and datasets with caching and sanitization."""
import json
import math
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from backend.config import (
    TELEMETRY_CSV,
    METRIC_RELIABILITY_CSV,
    GAP_REPORT_CSV,
    ASSET_REGISTRY_CSV,
    ASSET_RELATIONSHIPS_CSV,
    ASSET_GRAPH_JSON,
    ANOMALY_EVENTS_CSV,
    ROOT_CAUSE_CSV,
    POTENTIAL_IMPACT_CSV,
    TELEMETRY_FEATURES_CSV,
    GAP_REPORT_USED_CSV,
    FAULT_IMPACT_JSON,
    FAULT_IMPACT_CSV,
    FAULT_SCENARIOS_CSV,
    ENERGY_ANALYSIS_CSV,
    PRED_WARNINGS_CSV,
    EARLY_WARNINGS_CSV,
    DEGRADATION_CSV,
    FORECAST_METRICS_CSV,
    STANDARDIZED_PRED_CSV,
    ANOMALY_RESULTS_CSV,
    ENERGY_SUMMARY_CSV,
    CORRELATIONS_CSV,
    CORRELATION_INTERPRETATION_CSV,
    PUE_CSV,
    WHAT_IF_CSV,
    TEMP_DIFFERENCE_CSV,
    LATE_THRESHOLD_SECONDS,
    STALE_THRESHOLD_SECONDS,
)

_CACHE: Dict[str, Any] = {}

def sanitize_records(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Converts a DataFrame to records, replacing NaN/Inf with None."""
    records = df.to_dict(orient="records")
    for r in records:
        for k, v in r.items():
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                r[k] = None
            elif pd.isna(v):
                r[k] = None
    return records

def get_telemetry_df() -> pd.DataFrame:
    if "telemetry_df" not in _CACHE:
        if TELEMETRY_CSV.exists():
            df = pd.read_csv(TELEMETRY_CSV)
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
            _CACHE["telemetry_df"] = df
        else:
            _CACHE["telemetry_df"] = pd.DataFrame()
    return _CACHE["telemetry_df"]

def get_asset_registry() -> List[Dict[str, Any]]:
    if "asset_registry" not in _CACHE:
        if ASSET_REGISTRY_CSV.exists():
            df = pd.read_csv(ASSET_REGISTRY_CSV)
            _CACHE["asset_registry"] = sanitize_records(df)
        else:
            _CACHE["asset_registry"] = []
    return _CACHE["asset_registry"]

def get_asset_graph() -> Dict[str, Any]:
    if "asset_graph" not in _CACHE:
        if ASSET_GRAPH_JSON.exists():
            with open(ASSET_GRAPH_JSON, "r", encoding="utf-8") as f:
                _CACHE["asset_graph"] = json.load(f)
        else:
            _CACHE["asset_graph"] = {"nodes": [], "edges": []}
    return _CACHE["asset_graph"]

def get_anomaly_events(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    if "anomaly_events" not in _CACHE:
        if ANOMALY_EVENTS_CSV.exists():
            df = pd.read_csv(ANOMALY_EVENTS_CSV)
            _CACHE["anomaly_events"] = sanitize_records(df)
        else:
            _CACHE["anomaly_events"] = []
    events = _CACHE["anomaly_events"]
    return events[:limit] if limit else events

def get_root_causes(limit: Optional[int] = None) -> List[Dict[str, Any]]:
    if "root_causes" not in _CACHE:
        if ROOT_CAUSE_CSV.exists():
            df = pd.read_csv(ROOT_CAUSE_CSV)
            _CACHE["root_causes"] = sanitize_records(df)
        else:
            _CACHE["root_causes"] = []
    causes = _CACHE["root_causes"]
    return causes[:limit] if limit else causes

def get_predictive_warnings() -> Dict[str, Any]:
    warnings_data = {"early_warnings": [], "future_warnings": []}
    if EARLY_WARNINGS_CSV.exists():
        df_early = pd.read_csv(EARLY_WARNINGS_CSV)
        warnings_data["early_warnings"] = sanitize_records(df_early)
    if PRED_WARNINGS_CSV.exists():
        df_future = pd.read_csv(PRED_WARNINGS_CSV)
        warnings_data["future_warnings"] = sanitize_records(df_future)
    return warnings_data

def get_forecast_metrics() -> List[Dict[str, Any]]:
    if "forecast_metrics" not in _CACHE:
        if FORECAST_METRICS_CSV.exists():
            df = pd.read_csv(FORECAST_METRICS_CSV)
            _CACHE["forecast_metrics"] = sanitize_records(df)
        else:
            _CACHE["forecast_metrics"] = []
    return _CACHE["forecast_metrics"]

def get_degradation_indicators(limit: int = 100) -> List[Dict[str, Any]]:
    if DEGRADATION_CSV.exists():
        df = pd.read_csv(DEGRADATION_CSV).tail(limit)
        return sanitize_records(df)
    return []

def get_standardized_predictions() -> List[Dict[str, Any]]:
    if STANDARDIZED_PRED_CSV.exists():
        df = pd.read_csv(STANDARDIZED_PRED_CSV)
        return sanitize_records(df)
    return []

def get_fault_impact() -> Dict[str, Any]:
    if FAULT_IMPACT_JSON.exists():
        with open(FAULT_IMPACT_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"impacts": []}

def get_fault_scenarios() -> List[Dict[str, Any]]:
    if FAULT_SCENARIOS_CSV.exists():
        df = pd.read_csv(FAULT_SCENARIOS_CSV)
        return sanitize_records(df)
    return []

def get_energy_summary() -> Dict[str, Any]:
    summary = {}
    if ENERGY_SUMMARY_CSV.exists():
        df = pd.read_csv(ENERGY_SUMMARY_CSV)
        if not df.empty:
            summary.update(sanitize_records(df)[0])
    if not summary:
        return {"available": False, "reason": "Energy integration output is unavailable. Run `python src/power_temperature_analytics.py --output-dir outputs/member3_outputs` from the project root."}
    summary["available"] = True
    return summary

def get_energy_series(limit: int = 500) -> List[Dict[str, Any]]:
    if ENERGY_ANALYSIS_CSV.exists():
        df = pd.read_csv(ENERGY_ANALYSIS_CSV).tail(limit)
        return sanitize_records(df)
    return []

def get_correlations() -> Dict[str, Any]:
    data = {"matrix": [], "interpretation": []}
    if CORRELATIONS_CSV.exists():
        df_corr = pd.read_csv(CORRELATIONS_CSV)
        data["matrix"] = sanitize_records(df_corr)
    if CORRELATION_INTERPRETATION_CSV.exists():
        df_interp = pd.read_csv(CORRELATION_INTERPRETATION_CSV)
        data["interpretation"] = sanitize_records(df_interp)
    return data

def get_metric_reliability() -> List[Dict[str, Any]]:
    if METRIC_RELIABILITY_CSV.exists():
        df = pd.read_csv(METRIC_RELIABILITY_CSV)
        return sanitize_records(df)
    return []

def get_gap_report(limit: int = 200) -> List[Dict[str, Any]]:
    if GAP_REPORT_CSV.exists():
        df = pd.read_csv(GAP_REPORT_CSV).head(limit)
        return sanitize_records(df)
    return []

def get_what_if_comparison() -> List[Dict[str, Any]]:
    if WHAT_IF_CSV.exists():
        df = pd.read_csv(WHAT_IF_CSV)
        return sanitize_records(df)
    return []

def get_pue_info() -> Dict[str, Any]:
    if PUE_CSV.exists():
        df = pd.read_csv(PUE_CSV)
        if not df.empty:
            return sanitize_records(df)[0]
    return {
        "pue_calculated": False,
        "reason": "Facility cooling overhead not metered in node-level dataset.",
        "standard_formula": "PUE = Total Facility Power / IT Equipment Power",
        "scope_guidance": "Sub-facility telemetry requires chiller / CRAH metering for compliant PUE."
    }
