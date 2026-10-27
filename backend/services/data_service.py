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
    ALL_MODEL_EVALUATION_CSV,
    ENERGY_SUMMARY_CSV,
    CORRELATIONS_CSV,
    CORRELATION_INTERPRETATION_CSV,
    PUE_CSV,
    WHAT_IF_CSV,
    TEMP_DIFFERENCE_CSV,
    MULTICLASS_PRED_CSV,
    INTEGRATED_FAULT_JSON,
    SCENARIO_IMPACT_MATRIX_JSON,
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
            df_anom = pd.read_csv(ANOMALY_EVENTS_CSV)
            if TELEMETRY_CSV.exists():
                try:
                    df_tel = pd.read_csv(TELEMETRY_CSV)
                    df_anom["_ts"] = pd.to_datetime(df_anom["timestamp"], utc=True, errors="coerce")
                    df_tel["_ts"] = pd.to_datetime(df_tel["timestamp"], utc=True, errors="coerce")
                    cols = [c for c in ["_ts", "total_power", "p0_vdd_temp", "p1_vdd_temp", "fan0_0", "fan1_0", "ambient", "p0_power", "p1_power"] if c in df_tel.columns]
                    merged = pd.merge(df_anom, df_tel[cols], on="_ts", how="left").drop(columns=["_ts"])
                    if "total_power" in merged.columns:
                        merged["power"] = merged["total_power"]
                    if "p0_vdd_temp" in merged.columns and "p1_vdd_temp" in merged.columns:
                        merged["temp_core_max"] = merged[["p0_vdd_temp", "p1_vdd_temp"]].max(axis=1)
                        merged["temperature"] = merged["p0_vdd_temp"]
                    elif "p0_vdd_temp" in merged.columns:
                        merged["temp_core_max"] = merged["p0_vdd_temp"]
                        merged["temperature"] = merged["p0_vdd_temp"]
                    if "fan0_0" in merged.columns:
                        merged["fan_rpm"] = merged["fan0_0"]
                    _CACHE["anomaly_events"] = sanitize_records(merged)
                except Exception:
                    _CACHE["anomaly_events"] = sanitize_records(df_anom)
            else:
                _CACHE["anomaly_events"] = sanitize_records(df_anom)
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
    if FORECAST_METRICS_CSV.exists():
        df = pd.read_csv(FORECAST_METRICS_CSV)
        return sanitize_records(df)
    return []

def get_all_model_evaluation_metrics() -> List[Dict[str, Any]]:
    if ALL_MODEL_EVALUATION_CSV.exists():
        df = pd.read_csv(ALL_MODEL_EVALUATION_CSV)
        return sanitize_records(df)
    return []

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

def get_multiclass_predictions(
    origin: Optional[str] = None,
    predicted_class: Optional[str] = None,
    limit: Optional[int] = 100,
    offset: int = 0
) -> Dict[str, Any]:
    if MULTICLASS_PRED_CSV.exists():
        df = pd.read_csv(MULTICLASS_PRED_CSV)
        if origin and origin.lower() != "all":
            df = df[df["data_origin"].str.lower() == origin.lower()]
        if predicted_class and predicted_class.lower() != "all":
            df = df[df["predicted_class"].str.lower() == predicted_class.lower()]
        total = len(df)
        subset = df.iloc[offset : offset + limit] if limit else df.iloc[offset:]
        records = sanitize_records(subset)
        counts_by_class = {str(k): int(v) for k, v in df["predicted_class"].value_counts().items()}
        counts_by_origin = {str(k): int(v) for k, v in df["data_origin"].value_counts().items()}
        return {
            "total": total,
            "offset": offset,
            "limit": limit,
            "counts_by_class": counts_by_class,
            "counts_by_origin": counts_by_origin,
            "records": records
        }
    return {
        "total": 0,
        "offset": offset,
        "limit": limit,
        "counts_by_class": {},
        "counts_by_origin": {},
        "records": []
    }

def get_integrated_fault_workflow() -> Dict[str, Any]:
    if INTEGRATED_FAULT_JSON.exists():
        with open(INTEGRATED_FAULT_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"generated_scenarios_evaluated": 0, "scenarios": []}

