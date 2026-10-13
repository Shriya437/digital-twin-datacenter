"""Gap-aware, retrospective telemetry feature engineering for analysis."""
import numpy as np
import pandas as pd
from .data_loader import METRICS


def build_telemetry_features(df: pd.DataFrame, window: int = 15,
                             gap_threshold_seconds: float | None = None) -> pd.DataFrame:
    """Create deltas and rolling summaries without crossing major telemetry gaps.

    Rolling statistics use observations from the current segment only. This is for
    retrospective analysis; a real-time deployment should use strictly past-only
    windows and its actual telemetry-arrival timestamps.
    """
    if window < 3:
        raise ValueError("window must be >= 3")
    out = df[["timestamp"] + [m for m in METRICS if m in df.columns]].copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True, errors="coerce")
    out = out.sort_values("timestamp").reset_index(drop=True)
    gaps = out["timestamp"].diff().dt.total_seconds()
    if gap_threshold_seconds is None:
        positive = gaps[gaps > 0]
        typical = float(positive.median()) if not positive.empty else 20.0
        gap_threshold_seconds = max(3 * typical, 60.0)
    segment_start = gaps.isna() | gaps.gt(gap_threshold_seconds)
    out["segment_id"] = segment_start.cumsum().astype(int)
    for metric in METRICS:
        if metric not in out:
            continue
        values = pd.to_numeric(out[metric], errors="coerce")
        out[f"{metric}_delta"] = values.groupby(out["segment_id"]).diff()
        grouped = values.groupby(out["segment_id"], group_keys=False)
        out[f"{metric}_rolling_median"] = grouped.transform(
            lambda s: s.rolling(window, min_periods=max(3, window // 3)).median())
        out[f"{metric}_rolling_std"] = grouped.transform(
            lambda s: s.rolling(window, min_periods=max(3, window // 3)).std())
        med = out[f"{metric}_rolling_median"]
        scale = out[f"{metric}_rolling_std"].replace(0, np.nan)
        out[f"{metric}_local_deviation"] = (values - med) / scale
    return out
