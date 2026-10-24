"""Explainable, rule-based candidate cause ranking with an abstention option."""
import numpy as np
import pandas as pd
from .data_loader import METRICS

TEMP = {"p0_vdd_temp", "p1_vdd_temp", "ambient"}
FAN = {"fan0_0", "fan1_0"}
POWER = {"p0_power", "p1_power", "ps0_input_power", "ps1_input_power", "total_power"}
CAUSE_COLUMNS = ["timestamp", "candidate_cause", "rank", "ranking_score", "evidence",
                 "evidence_status", "is_simulated", "quality_warning", "interpretation"]


def _local_metric_evidence(df: pd.DataFrame, timestamp, reference_df: pd.DataFrame | None = None, window: int = 31, threshold: float = 4.0):
    """Find metrics deviating from their recent past at a timestamp (heuristic)."""
    if df.empty or "timestamp" not in df:
        return set(), {}
    ordered = df.copy().reset_index(drop=True)
    ordered["timestamp"] = pd.to_datetime(ordered["timestamp"], utc=True, errors="coerce")
    reference = (reference_df.copy() if reference_df is not None else df.copy()).reset_index(drop=True)
    reference["timestamp"] = pd.to_datetime(reference["timestamp"], utc=True, errors="coerce")
    positions = ordered.index[ordered["timestamp"].eq(pd.to_datetime(timestamp, utc=True))].tolist()
    if not positions:
        return set(), {}
    pos = positions[-1]
    gaps = reference["timestamp"].diff().dt.total_seconds()
    positive = gaps[gaps > 0]
    typical = float(positive.median()) if not positive.empty else 20.0
    segment_ids = gaps.gt(max(3 * typical, 60.0)).fillna(False).cumsum()
    segment_start = int(ordered.index[segment_ids.eq(segment_ids.iloc[pos])][0])
    evidence, scores = set(), {}
    for metric in METRICS:
        if metric not in ordered:
            continue
        current = pd.to_numeric(pd.Series([ordered.at[pos, metric]]), errors="coerce").iloc[0]
        if pd.isna(current):
            continue
        start = max(segment_start, pos - window)
        past = pd.to_numeric(reference.loc[start:pos - 1, metric], errors="coerce").dropna()
        if len(past) < 5:
            continue
        med = float(past.median())
        scale = float((past - med).abs().median()) * 1.4826
        if not np.isfinite(scale) or scale <= 1e-9:
            q1, q3 = past.quantile([0.25, 0.75])
            scale = float((q3 - q1) / 1.349)
        if not np.isfinite(scale) or scale <= 1e-9:
            scale = float(past.std(ddof=0))
        global_values = pd.to_numeric(reference[metric], errors="coerce").dropna()
        global_scale = float(global_values.std(ddof=0)) if not global_values.empty else 1.0
        floor = max(global_scale * 0.05, 1e-6)
        scale = max(scale if np.isfinite(scale) else floor, floor)
        z = float((current - med) / scale)
        scores[metric] = z
        if abs(z) >= threshold:
            evidence.add(metric)
    return evidence, scores


def rank_root_causes(df: pd.DataFrame, anomaly_events: pd.DataFrame, baseline_df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Rank possible causes using co-occurring anomaly evidence.

    Scores are heuristic evidence weights, not probabilities. This deliberately
    permits an unknown/insufficient-evidence result rather than inventing causes.
    """
    if anomaly_events is None or anomaly_events.empty:
        return pd.DataFrame(columns=CAUSE_COLUMNS)
    work = df.copy()
    work["timestamp"] = pd.to_datetime(work["timestamp"], utc=True, errors="coerce")
    indexed = work.drop_duplicates("timestamp", keep="last").set_index("timestamp", drop=False)
    output = []
    for timestamp, group in anomaly_events.groupby("timestamp", dropna=False):
        if pd.isna(timestamp) or timestamp not in indexed.index:
            continue
        names = set(group["metric_name"].astype(str))
        local_metrics, local_scores = _local_metric_evidence(df, timestamp, reference_df=baseline_df)
        names |= local_metrics
        temps, fans, powers = names & TEMP, names & FAN, names & POWER
        multi = bool(names & {"MULTIVARIATE"})
        quality_warning = bool(group.get("quality_warning", pd.Series(False, index=group.index)).fillna(False).any())
        simulated = bool(group.get("is_simulated", pd.Series(False, index=group.index)).fillna(False).any())
        candidates = []
        if fans and temps:
            candidates.append(("fan_related_issue", 3.0,
                               "Fan-related and temperature metrics are anomalous at the same timestamp; association is not proof of causation."))
        if temps and powers:
            candidates.append(("thermal_or_power_related_behaviour", 2.5,
                               "Temperature and power metrics are anomalous together; workload, sensor quality, and physical context need checking."))
        if fans and not temps:
            candidates.append(("fan_telemetry_or_fan_behaviour", 2.0,
                               "Fan telemetry is anomalous; actual fan degradation cannot be established from this metric alone."))
        if powers and not temps:
            candidates.append(("power_telemetry_or_load_behaviour", 2.0,
                               "Power-related telemetry is anomalous; verify units and metric definitions."))
        if temps and not fans and not powers:
            candidates.append(("temperature_sensor_or_thermal_behaviour", 1.5,
                               "Temperature telemetry is anomalous without matching fan/power anomaly evidence at this timestamp."))
        if multi:
            candidates.append(("unusual_multivariate_operating_condition", 1.0,
                               "A multivariate detector flagged the row; the specific cause is not identified by that detector alone."))
        if not candidates:
            candidates.append(("unknown_or_insufficient_evidence", 0.0,
                               "Available anomaly evidence does not support a specific candidate cause."))
        candidates.sort(key=lambda x: x[1], reverse=True)
        if local_metrics:
            strongest = sorted(local_metrics, key=lambda m: abs(local_scores.get(m, 0.0)), reverse=True)[:4]
            local_note = " Recent-window deviations: " + ", ".join(
                f"{m} (z={local_scores[m]:.2f})" for m in strongest
            ) + "."
            candidates = [(cause, score, evidence + local_note) for cause, score, evidence in candidates]
        for rank, (cause, score, evidence) in enumerate(candidates, start=1):
            if quality_warning:
                evidence += " A calculated telemetry gap is present; interpret cautiously."
            output.append({
                "timestamp": timestamp, "candidate_cause": cause, "rank": rank,
                "ranking_score": score, "evidence": evidence,
                "evidence_status": "preliminary_rule_evidence" if score >= 1 else "insufficient_evidence",
                "is_simulated": simulated, "quality_warning": quality_warning,
                "interpretation": "Heuristic ranking score, not probability or confirmed root cause",
            })
    result = pd.DataFrame(output, columns=CAUSE_COLUMNS)
    if not result.empty:
        result = result.sort_values(["timestamp", "rank"]).reset_index(drop=True)
    return result
