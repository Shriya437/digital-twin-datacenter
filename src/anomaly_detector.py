"""Gap-aware anomaly screening for the Member 2 digital-twin prototype.

The four detectors are candidate generators, not confirmed fault classifiers.
Multivariate models include first-difference features so abrupt changes are not
hidden by otherwise correlated operating values.
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import RobustScaler, StandardScaler
from sklearn.decomposition import PCA
from .data_loader import METRICS

EVENT_COLUMNS = ["timestamp", "metric_name", "observed_value", "detector",
                 "anomaly_score", "threshold", "quality_warning", "is_simulated", "notes"]


def _robust_location_scale(series: pd.Series):
    x = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if x.empty:
        return np.nan, np.nan
    med = float(x.median())
    scale = 1.4826 * float((x - med).abs().median())
    if not np.isfinite(scale) or scale <= 1e-12:
        q1, q3 = x.quantile([.25, .75]); scale = float((q3 - q1) / 1.349)
    if not np.isfinite(scale) or scale <= 1e-12: scale = float(x.std(ddof=0))
    return med, scale if np.isfinite(scale) and scale > 1e-12 else np.nan


def _clean_matrix(frame, metrics):
    x = frame[metrics].apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    med = x.median().fillna(0.0)
    return x.fillna(med).fillna(0.0), med


def _segments_and_deltas(frame, metrics):
    """Past differences; a long gap makes the first delta in a segment missing."""
    x = frame[metrics].apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    ts = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
    dt = ts.diff().dt.total_seconds()
    typical = float(dt[dt > 0].median()) if (dt > 0).any() else 20.0
    gap_threshold = max(3.0 * typical, 60.0)
    segment = dt.gt(gap_threshold).fillna(False).cumsum()
    delta = x.groupby(segment).diff()
    # Clip only for model stability; raw values remain untouched in the output.
    delta = delta.replace([np.inf, -np.inf], np.nan)
    return x, delta, dt.gt(gap_threshold).fillna(False)


def detect_anomalies(df: pd.DataFrame, quality: pd.DataFrame | None = None,
                     contamination: float = 0.02, random_state: int = 42,
                     baseline_df: pd.DataFrame | None = None) -> pd.DataFrame:
    if not 0.001 <= contamination <= 0.20:
        raise ValueError("contamination must be between 0.001 and 0.20")
    work = df.copy().reset_index(drop=True)
    reference = (baseline_df.copy() if baseline_df is not None else df.copy()).reset_index(drop=True)
    for frame in (work, reference):
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
        absent = [m for m in METRICS if m not in frame]
        if absent: raise ValueError(f"Missing metrics required for detection: {absent}")
    ref = reference[METRICS].apply(pd.to_numeric, errors="coerce")
    cur = work[METRICS].apply(pd.to_numeric, errors="coerce")
    events = []

    def add(idx, metric, detector, score, threshold, note):
        value = cur.at[idx, metric] if metric in cur else np.nan
        events.append({"timestamp": work.at[idx, "timestamp"], "metric_name": metric,
            "observed_value": float(value) if pd.notna(value) else np.nan,
            "detector": detector, "anomaly_score": float(score), "threshold": float(threshold),
            "quality_warning": bool(work.loc[idx].get("calculated_gap_flag", False)),
            "is_simulated": bool(work.loc[idx].get("is_simulated", False)), "notes": note})

    # 1. Global robust Z-score. The reference 99th percentile limits excessive
    # alerts on skewed/quantized signals, while the minimum threshold catches clear outliers.
    for metric in METRICS:
        med, scale = _robust_location_scale(ref[metric])
        if not np.isfinite(scale): continue
        rz = (cur[metric] - med) / scale
        refz = ((ref[metric] - med) / scale).abs().dropna()
        cutoff = max(3.5, float(refz.quantile(.99)) if not refz.empty else 3.5)
        for i in np.flatnonzero(rz.abs().gt(cutoff).fillna(False).to_numpy()):
            add(i, metric, "robust_z_score", abs(rz.iloc[i]), cutoff,
                "Global robust deviation; anomaly candidate, not confirmed fault")

    # 2. Past-only rolling robust Z-score; reset after major timestamp gaps.
    _, current_delta, _ = _segments_and_deltas(work, METRICS)
    ts = work["timestamp"]
    dt = ts.diff().dt.total_seconds(); positive = dt[dt > 0]
    gap_threshold = max(3 * (float(positive.median()) if not positive.empty else 20.0), 60.0)
    segment = dt.gt(gap_threshold).fillna(False).cumsum()
    def rolling_score(frame, metric, global_scale):
        values = pd.to_numeric(frame[metric], errors="coerce")
        times = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
        deltas = times.diff().dt.total_seconds()
        pos = deltas[deltas > 0]
        typical = float(pos.median()) if not pos.empty else 20.0
        threshold_gap = max(3.0 * typical, 60.0)
        seg_ids = deltas.gt(threshold_gap).fillna(False).cumsum()
        result = pd.Series(np.nan, index=frame.index, dtype=float)
        floor = max((global_scale if np.isfinite(global_scale) else 1.0) * .05, 1e-6)
        for seg in seg_ids.unique():
            ids = seg_ids.index[seg_ids.eq(seg)]
            past = values.loc[ids].shift(1)
            med = past.rolling(31, min_periods=8).median()
            mad = past.rolling(31, min_periods=8).apply(lambda a: np.median(np.abs(a - np.median(a))), raw=True) * 1.4826
            std = past.rolling(31, min_periods=8).std(ddof=0)
            scale = mad.where(mad > 1e-9, std).fillna(floor).clip(lower=floor)
            result.loc[ids] = (values.loc[ids] - med) / scale
        return result

    for metric in METRICS:
        _, global_scale = _robust_location_scale(ref[metric])
        score = rolling_score(work, metric, global_scale)
        reference_score = rolling_score(reference, metric, global_scale).abs().dropna()
        empirical_cutoff = float(reference_score.quantile(.995)) if not reference_score.empty else 4.0
        cutoff = max(4.0, empirical_cutoff if np.isfinite(empirical_cutoff) else 4.0)
        for i in np.flatnonzero(score.abs().gt(cutoff).fillna(False).to_numpy()):
            add(i, metric, "rolling_robust_z_score", abs(score.iloc[i]), cutoff,
                "Deviation from preceding local window; threshold calibrated from reference tail; resets across long gaps")

    # Multivariate inputs combine operating levels with temporal changes. Fit all
    # transformations on reference telemetry only, then apply to target telemetry.
    usable = [m for m in METRICS if ref[m].notna().any()]
    if len(usable) >= 3 and len(reference) >= 50:
        ref_levels, ref_delta, _ = _segments_and_deltas(reference, usable)
        cur_levels, cur_delta, _ = _segments_and_deltas(work, usable)
        ref_feat = pd.concat([ref_levels.add_suffix("__level"), ref_delta.add_suffix("__delta")], axis=1)
        cur_feat = pd.concat([cur_levels.add_suffix("__level"), cur_delta.add_suffix("__delta")], axis=1)
        # Drop delta columns that have no meaningful variation in the reference.
        ref_feat = ref_feat.replace([np.inf, -np.inf], np.nan)
        cur_feat = cur_feat.replace([np.inf, -np.inf], np.nan)
        medians = ref_feat.median().fillna(0.0)
        ref_feat = ref_feat.fillna(medians).fillna(0.0)
        cur_feat = cur_feat.fillna(medians).fillna(0.0)
        varying = ref_feat.std(ddof=0) > 1e-10
        ref_feat, cur_feat = ref_feat.loc[:, varying], cur_feat.loc[:, varying]
        if ref_feat.shape[1] >= 3:
            # Isolation Forest uses contamination to establish an unsupervised
            # reference cutoff; temporal deltas make abrupt changes observable.
            scaler = RobustScaler(quantile_range=(10, 90))
            xr = scaler.fit_transform(ref_feat); xc = scaler.transform(cur_feat)
            forest = IsolationForest(n_estimators=300, contamination=contamination,
                                     random_state=random_state, n_jobs=-1)
            forest.fit(xr)
            ref_score = -forest.score_samples(xr); cur_score = -forest.score_samples(xc)
            threshold = max(float(np.quantile(ref_score, 1.0 - contamination)), float(-forest.offset_))
            for i in np.flatnonzero(cur_score > threshold):
                events.append({"timestamp": work.at[i, "timestamp"], "metric_name": "MULTIVARIATE",
                    "observed_value": np.nan, "detector": "isolation_forest", "anomaly_score": float(cur_score[i]),
                    "threshold": threshold, "quality_warning": bool(work.loc[i].get("calculated_gap_flag", False)),
                    "is_simulated": bool(work.loc[i].get("is_simulated", False)),
                    "notes": "Isolation Forest score on levels plus first differences; candidate only"})

            # PCA reconstruction error over same feature representation. Use a
            # held-out upper-tail reference threshold to reduce optimistic bias.
            if len(ref_feat) >= 100:
                pscaler = StandardScaler()
                pr = pscaler.fit_transform(ref_feat)
                pc = pscaler.transform(cur_feat)
                ncomp = min(0.95, max(1, min(ref_feat.shape[1] - 1, 8)) / ref_feat.shape[1])
                pca = PCA(n_components=ncomp, svd_solver="full", random_state=random_state)
                pca.fit(pr)
                re = np.mean((pr - pca.inverse_transform(pca.transform(pr))) ** 2, axis=1)
                ce = np.mean((pc - pca.inverse_transform(pca.transform(pc))) ** 2, axis=1)
                threshold = max(float(np.quantile(re, .99)), 1e-6)
                for i in np.flatnonzero(ce > threshold):
                    events.append({"timestamp": work.at[i, "timestamp"], "metric_name": "MULTIVARIATE",
                        "observed_value": np.nan, "detector": "pca_reconstruction", "anomaly_score": float(ce[i]),
                        "threshold": threshold, "quality_warning": bool(work.loc[i].get("calculated_gap_flag", False)),
                        "is_simulated": bool(work.loc[i].get("is_simulated", False)),
                        "notes": "PCA reconstruction error over levels and temporal deltas; candidate only"})

    result = pd.DataFrame(events, columns=EVENT_COLUMNS)
    if result.empty:
        result["quality_status"] = pd.Series(dtype="object")
        result["is_estimated"] = pd.Series(dtype="bool")
        result["member1_timestamp_gap_flag"] = pd.Series(dtype="bool")
        return result
    result = result.sort_values(["timestamp", "detector", "metric_name"]).reset_index(drop=True)
    if quality is not None and {"timestamp", "metric_name"}.issubset(quality.columns):
        q = quality.copy()
        if "event_timestamp" in q: q = q.rename(columns={"event_timestamp": "timestamp"})
        q["timestamp"] = pd.to_datetime(q["timestamp"], utc=True, errors="coerce")
        cols = [c for c in ["timestamp", "metric_name", "quality_status", "is_estimated", "is_simulated", "timestamp_gap_flag", "implausible_value_flag"] if c in q]
        q = q[cols].drop_duplicates(["timestamp", "metric_name"])
        result = result.merge(q, on=["timestamp", "metric_name"], how="left", suffixes=("", "_quality"))
    return result
