"""Dashboard adapter for outputs produced by the project's ML modules.

No illustrative asset scores are returned. Empty/missing model outputs are reported
as unavailable until the ML pipeline has been run.
"""
from pathlib import Path
from typing import Any, Dict, List
import numpy as np
import pandas as pd
from backend.config import PRED_MAINT_DIR, TELEMETRY_CSV
from backend.services.data_service import get_forecast_metrics, sanitize_records

METRIC_LABELS = {
    "p0_vdd_temp": "Processor 0 temperature",
    "p1_vdd_temp": "Processor 1 temperature",
    "fan0_0": "Fan 0 speed",
    "fan1_0": "Fan 1 speed",
    "p0_power": "Processor 0 power",
    "p1_power": "Processor 1 power",
    "ps0_input_power": "Power supply 0 input power",
    "ps1_input_power": "Power supply 1 input power",
    "total_power": "Total node power",
}


def _load_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def get_risk_ranked_assets() -> List[Dict[str, Any]]:
    """Rank telemetry metrics using the trained Isolation Forest output and current data.

    RUL and maintenance schedule are intentionally null: the project does not train a
    validated remaining-useful-life model or contain a real work-order system.
    """
    anomaly_path = PRED_MAINT_DIR / "anomaly_detection_results.csv"
    anomaly = _load_csv(anomaly_path)
    telemetry = _load_csv(TELEMETRY_CSV)
    if anomaly.empty or telemetry.empty or "anomaly_score" not in anomaly:
        return []
    anomaly["timestamp"] = pd.to_datetime(anomaly.get("timestamp"), utc=True, errors="coerce")
    anomaly = anomaly.dropna(subset=["timestamp"]).sort_values("timestamp")
    if anomaly.empty:
        return []
    latest = anomaly.iloc[-1]
    # Isolation Forest's decision_function: lower means more anomalous. Use the
    # empirical score distribution to normalize, rather than a hand-entered risk.
    scores = pd.to_numeric(anomaly["anomaly_score"], errors="coerce").dropna()
    if scores.empty:
        return []
    assets = []
    candidates = [m for m in METRIC_LABELS if m in anomaly.columns and m in telemetry.columns]
    for metric in candidates:
        series = pd.to_numeric(telemetry[metric], errors="coerce").dropna()
        value = pd.to_numeric(pd.Series([latest.get(metric)]), errors="coerce").iloc[0]
        if series.empty or pd.isna(value):
            continue
        std = float(series.std())
        z = abs((float(value) - float(series.mean())) / std) if std > 0 else 0.0
        # Risk combines actual model anomaly score percentile with observed metric deviation.
        score_pct = float((scores <= float(latest["anomaly_score"])).mean())
        anomaly_component = 1.0 - score_pct
        deviation_component = min(z / 4.0, 1.0)
        risk = float(np.clip(0.7 * anomaly_component + 0.3 * deviation_component, 0, 1))
        level = "CRITICAL" if risk >= .8 else "HIGH" if risk >= .6 else "ELEVATED" if risk >= .4 else "NOMINAL"
        assets.append({
            "rank": 0,
            "asset_id": f"M100_NODE_1::{metric}",
            "component_name": METRIC_LABELS[metric],
            "type": "Telemetry metric",
            "risk_score": round(risk, 4),
            "risk_level": level,
            "current_value": float(value),
            "historical_mean": float(series.mean()),
            "historical_std": std,
            "standardized_deviation": round(z, 4),
            "model_anomaly_score": float(latest["anomaly_score"]),
            "is_model_flagged_anomaly": bool(latest.get("is_anomaly", False)),
            "estimated_rul_days": None,
            "degradation_rate_pct": None,
            "early_warning": "Model flagged the latest telemetry row as anomalous." if bool(latest.get("is_anomaly", False)) else "Latest model output did not flag the row; risk ranking also considers the metric's historical deviation.",
            "predicted_downstream_impacts": [],
            "maintenance_task": None,
            "what_if_link": None,
            "data_timestamp": latest["timestamp"].isoformat(),
            "provenance": "Isolation Forest anomaly_detection_results.csv + telemetry dataset"
        })
    assets.sort(key=lambda x: x["risk_score"], reverse=True)
    for i, asset in enumerate(assets, 1):
        asset["rank"] = i
    return assets


def get_forecast_comparison() -> Dict[str, Any]:
    """Return forecasts and metrics produced by src.predictive_maintenance."""
    results: Dict[str, Any] = {}
    horizons = ["1min", "5min", "15min"]
    available = []
    for h in horizons:
        path = PRED_MAINT_DIR / f"predictions_p0_vdd_temp_{h}.csv"
        if path.exists():
            df = pd.read_csv(path).tail(200)
            results[f"p0_{h}"] = sanitize_records(df)
            if not df.empty:
                available.append(f"{h} (p0_vdd_temp)")
        else:
            results[f"p0_{h}"] = []
    metrics = get_forecast_metrics()
    return {
        "horizons_available": available,
        "metrics_summary": metrics,
        "sample_forecasts": results,
        "model_outputs_available": bool(available),
        "message": None if available else "Forecasts are unavailable. Run `python -m src.predictive_maintenance` from the project root first.",
        "provenance": "outputs/predictive_maintenance_op generated by src.predictive_maintenance"
    }
