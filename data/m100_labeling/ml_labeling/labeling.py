"""Transparent, causal heuristic labeling for the M100 ExaData telemetry.

IMPORTANT: every label produced here is a HEURISTIC PROXY derived from telemetry
rules. None of them is a verified fault, maintenance event or RUL.

Causality: every quantity used to label row i uses rows <= i of the same
continuous segment only (trailing windows, trailing EWMA, trailing persistence).
Reference models and thresholds are fitted on the chronological TRAIN rows only.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import HuberRegressor

METRICS = ["ambient", "p0_vdd_temp", "p1_vdd_temp", "fan0_0", "fan1_0", "p0_power",
           "p1_power", "ps0_input_power", "ps1_input_power", "total_power"]
GAP_SECONDS = 60.0          # same rule as feature_engineering_1.py: max(3*typical, 60)
WINDOW = 15                 # same default as feature_engineering_1.py / Module 5 horizon
WARMUP = WINDOW - 1         # rows of segment history needed before a label is trusted
PERSIST = 3                 # consecutive exceedances required (current + 2 previous rows)
HORIZON = 15                # samples for future-anomaly target (~5 min at 20 s)
HARD_Q, SOFT_Q = 0.995, 0.98
HARD_MIN, SOFT_MIN = 4.0, 3.0   # minimum thresholds in scale units (see _thresholds)
TRAIN_FRAC, VAL_FRAC = 0.60, 0.20
PURGE = WINDOW + HORIZON    # rows dropped at each split boundary
FAMILIES = {
    "thermal": ["z_temp_p0", "z_temp_p1", "z_temp_gradient"],
    "fan": ["z_fan_level", "z_fan_mismatch"],
    "power": ["z_ps_total", "z_ps_balance"],
}
ONE_SIDED_UPPER = {"z_temp_p0", "z_temp_p1", "z_fan_mismatch"}
FAULT_CLASSES = ["normal", "thermal_anomaly", "fan_performance_anomaly", "power_anomaly",
                 "combined_anomaly", "ambiguous_unknown", "insufficient_context"]
FAMILY_TO_CLASS = {"thermal": "thermal_anomaly", "fan": "fan_performance_anomaly",
                   "power": "power_anomaly"}


# ----------------------------------------------------------------- loading / segments
def load_observed(path) -> pd.DataFrame:
    """Load the original CSV WITHOUT dropping, reordering or altering any row."""
    df = pd.read_csv(path)
    df["timestamp_utc"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    if df["timestamp_utc"].isna().any():
        raise ValueError("unparseable timestamps present")
    if not df["timestamp_utc"].is_monotonic_increasing:
        raise ValueError("input is not chronologically ordered; refusing to reorder silently")
    df.insert(0, "row_id", np.arange(len(df)))
    return df


def segment_ids(ts: pd.Series, gap_seconds: float = GAP_SECONDS) -> pd.Series:
    gaps = ts.diff().dt.total_seconds()
    return (gaps.isna() | gaps.gt(gap_seconds)).cumsum().astype(int)


def split_labels(n: int) -> np.ndarray:
    """Chronological 60/20/20 split with PURGE rows removed after each boundary."""
    idx = np.arange(n)
    a, b = int(TRAIN_FRAC * n), int((TRAIN_FRAC + VAL_FRAC) * n)
    s = np.where(idx < a, "train", np.where(idx < b, "val", "test")).astype(object)
    s[(idx >= a) & (idx < a + PURGE)] = "purge"
    s[(idx >= b) & (idx < b + PURGE)] = "purge"
    return s


# ----------------------------------------------------------------- causal features
def _ewm(s, seg, span):
    return s.groupby(seg).transform(lambda x: x.ewm(span=span, adjust=False).mean())


def causal_features(df: pd.DataFrame, seg: pd.Series, window: int = WINDOW) -> pd.DataFrame:
    """Past-only features. Mirrors feature_engineering_1.py conventions
    (<metric>_delta / _rolling_median / _rolling_std / _local_deviation) and adds
    derived cross-sensor quantities. Nothing here crosses a segment boundary."""
    out = pd.DataFrame(index=df.index)
    out["segment_id"] = seg.values
    out["pos_in_segment"] = df.groupby(seg).cumcount().values
    minp = max(3, window // 3)
    for m in METRICS:
        v = pd.to_numeric(df[m], errors="coerce")
        g = v.groupby(seg)
        out[f"{m}_delta"] = g.diff()
        med = g.transform(lambda s: s.rolling(window, min_periods=minp).median())
        std = g.transform(lambda s: s.rolling(window, min_periods=minp).std())
        out[f"{m}_rolling_median"] = med
        out[f"{m}_rolling_std"] = std
        out[f"{m}_local_deviation"] = (v - med) / std.replace(0, np.nan)
    cp = df["p0_power"] + df["p1_power"]
    out["cpu_power_sum"] = cp
    out["ps_input_sum"] = df["ps0_input_power"] + df["ps1_input_power"]
    out["cpu_power_ewma3"] = _ewm(cp, seg, 3)
    out["cpu_power_ewma8"] = _ewm(cp, seg, 8)
    out["temp_max"] = df[["p0_vdd_temp", "p1_vdd_temp"]].max(axis=1)
    out["temp_gradient"] = df["p0_vdd_temp"] - df["p1_vdd_temp"]
    out["fan_mean"] = df[["fan0_0", "fan1_0"]].mean(axis=1)
    out["fan_mismatch_ratio"] = (df["fan0_0"] - df["fan1_0"]).abs() / out["fan_mean"]
    out["ps_balance"] = df["ps0_input_power"] - df["ps1_input_power"]
    out["cpu_power_balance"] = df["p0_power"] - df["p1_power"]
    out["temp_max_rise_15"] = out["temp_max"] - out["temp_max"].groupby(seg).shift(window)
    out["cpu_power_rise_15"] = cp - cp.groupby(seg).shift(window)
    return out


# ----------------------------------------------------------------- reference model
def _quant_step(x: pd.Series) -> float:
    u = np.unique(x.dropna().values)
    d = np.diff(u)
    return float(d[d > 0].min()) if (d > 0).any() else 1.0


def _huber(X, y):
    mu, sd = X.mean(0), X.std(0).replace(0, 1)
    m = HuberRegressor(max_iter=1000).fit(((X - mu) / sd).values, y.values)
    return {"kind": "huber", "mu": mu, "sd": sd, "model": m, "lo": X.min(0), "hi": X.max(0)}


def _mono(X, y):
    """Small monotone-increasing tree model: expected fan speed rises with temperature/load."""
    m = HistGradientBoostingRegressor(loss="absolute_error", max_depth=2, max_iter=60,
                                      learning_rate=0.1, min_samples_leaf=40,
                                      monotonic_cst=[1] * X.shape[1], random_state=42)
    m.fit(X.values, y.values)
    return {"kind": "mono_hgb", "model": m, "lo": X.min(0), "hi": X.max(0)}


def _pred(ref, X):
    X = X.clip(ref["lo"], ref["hi"], axis=1)   # never extrapolate outside the TRAIN envelope
    if ref["kind"] == "huber":
        return ref["model"].predict(((X - ref["mu"]) / ref["sd"]).values)
    return ref["model"].predict(X.values)


# channel -> (target column, predictor columns, resolution source column)
CHANNELS = {
    "z_temp_p0": ("p0_vdd_temp", ["cpu_power_ewma8", "cpu_power_ewma3", "ambient"]),
    "z_temp_p1": ("p1_vdd_temp", ["cpu_power_ewma8", "cpu_power_ewma3", "ambient"]),
    "z_temp_gradient": ("temp_gradient", ["cpu_power_ewma8"]),
    "z_fan_level": ("fan_mean", ["temp_max", "cpu_power_ewma8"]),
    "z_fan_mismatch": ("fan_mismatch_ratio", None),          # zero-referenced ratio
    "z_ps_total": ("ps_input_sum", ["cpu_power_sum", "cpu_power_ewma3"]),
    "z_ps_balance": ("ps_balance", ["ps_input_sum"]),
}


def fit_reference(df, feats, train_mask) -> dict:
    """Fit robust (Huber) normal-behaviour references on valid TRAIN rows only."""
    ok = train_mask & (feats["pos_in_segment"] >= WARMUP)
    allc = pd.concat([df[METRICS], feats], axis=1)
    ref = {}
    for ch, (target, preds) in CHANNELS.items():
        y = allc.loc[ok, target]
        if preds is None:
            center, res = float(y.median()), y - float(y.median())
            model = None
        else:
            model = (_mono if ch == "z_fan_level" else _huber)(allc.loc[ok, preds], y)
            center, res = None, y - _pred(model, allc.loc[ok, preds])
        mad = 1.4826 * float(np.median(np.abs(res - np.median(res))))
        step = _quant_step(allc.loc[train_mask, target]) if target != "fan_mismatch_ratio" else 100 / 4400
        scale = max(mad, step)
        z = res / scale
        zz = z if ch in ONE_SIDED_UPPER else z.abs()
        ref[ch] = {"target": target, "preds": preds, "model": model, "center": center,
                   "median_res": float(np.median(res)), "mad": mad, "quant_step": step, "scale": scale,
                   "hard": max(float(np.quantile(zz, HARD_Q)), HARD_MIN),
                   "soft": max(float(np.quantile(zz, SOFT_Q)), SOFT_MIN),
                   "n_fit": int(ok.sum())}
    return ref


def channel_z(df, feats, ref) -> pd.DataFrame:
    allc = pd.concat([df[METRICS], feats], axis=1)
    z = pd.DataFrame(index=df.index)
    for ch, r in ref.items():
        y = allc[r["target"]]
        pred = r["center"] if r["model"] is None else _pred(r["model"], allc[r["preds"]])
        zc = (y - pred - r["median_res"]) / r["scale"]
        z[ch] = zc if ch in ONE_SIDED_UPPER else zc.abs()
    return z


# ----------------------------------------------------------------- label rules
def apply_rules(z: pd.DataFrame, feats: pd.DataFrame, ref: dict) -> pd.DataFrame:
    seg = feats["segment_id"]
    out = pd.DataFrame(index=z.index)
    hard_any, soft_any, persist_any = {}, {}, {}
    for fam, chans in FAMILIES.items():
        hard = pd.concat([z[c] >= ref[c]["hard"] for c in chans], axis=1).any(axis=1)
        soft = pd.concat([z[c] >= ref[c]["soft"] for c in chans], axis=1).any(axis=1)
        pers = hard.astype(int).groupby(seg).transform(lambda s: s.rolling(PERSIST, min_periods=PERSIST).min()).fillna(0).astype(bool)
        out[f"rule_{fam}_hard"], out[f"rule_{fam}_persistent"] = hard, pers
        out[f"rule_{fam}_soft"] = soft
        out[f"rule_{fam}_score"] = pd.concat([z[c] / ref[c]["hard"] for c in chans], axis=1).max(axis=1)
    fams = list(FAMILIES)
    n_pers = sum(out[f"rule_{f}_persistent"].astype(int) for f in fams)
    any_soft = pd.concat([out[f"rule_{f}_soft"] for f in fams], axis=1).any(axis=1)
    warm = feats["pos_in_segment"] < WARMUP
    ftype = np.full(len(z), "normal", dtype=object)
    ftype[any_soft.values] = "ambiguous_unknown"
    for f in fams:
        ftype[(n_pers == 1).values & out[f"rule_{f}_persistent"].values] = FAMILY_TO_CLASS[f]
    ftype[(n_pers >= 2).values] = "combined_anomaly"
    ftype[warm.values] = "insufficient_context"
    out["fault_type"] = ftype
    out["label_status"] = np.select(
        [ftype == "insufficient_context", ftype == "ambiguous_unknown", ftype == "normal"],
        ["insufficient_context", "ambiguous", "confident_normal"], "rule_triggered")
    al = pd.array(np.where(np.isin(ftype, ["normal"]), 0, np.where(
        np.isin(ftype, ["ambiguous_unknown", "insufficient_context"]), -1, 1)), dtype="Int64")
    al = al.astype("Int64"); al[np.isin(ftype, ["ambiguous_unknown", "insufficient_context"])] = pd.NA
    out["anomaly_label"] = al
    out["label_valid"] = out["anomaly_label"].notna().astype(int)
    return out


def future_target(anom: pd.Series, seg: pd.Series, horizon: int = HORIZON) -> pd.Series:
    """1 if any of the NEXT `horizon` rows (same segment) is anomaly_label==1;
    0 if all are 0; NA if the horizon leaves the segment or contains unknown labels.
    This is a TARGET (uses the future by definition); it must never be a feature."""
    a = anom.astype("float")
    res = np.full(len(a), np.nan)
    arr, sg = a.values, seg.values
    for i in range(len(a)):
        j = i + horizon
        if j >= len(a) or sg[j] != sg[i]:
            continue
        w = arr[i + 1:j + 1]
        if (w == 1).any():
            res[i] = 1
        elif not np.isnan(w).any():
            res[i] = 0
    return pd.Series(pd.array(res, dtype="Float64").astype("Int64"), index=anom.index)


def label_series(df, feats, ref):
    z = channel_z(df, feats, ref)
    rules = apply_rules(z, feats, ref)
    return z, rules
